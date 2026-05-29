"""
住院模式核心 router — 補齊 admissions.py 未涵蓋的「六大功能」。

依《MD.Piece 住院模組設計 prompt》：
  F1 交接報告      GET  /inpatient/handover               讀取彙整 + LLM 一句「為何此時入院」
  F2 床邊自我記錄   POST/GET /inpatient/bedside            極低負擔的床邊紀錄（寫入）
                   GET  /inpatient/qpl-bank               「想問醫師」建議題庫（靜態）
                   POST/GET/PUT/DELETE /inpatient/questions  我的提問清單（查房前用）
  F3 用藥核對      GET  /inpatient/med-reconciliation     居家 vs 住院醫囑並排（純程式碼比對）
  F4 個人化衛教     GET  /inpatient/education              從 disease_reference 取材 + LLM 轉白話
  F6 出院銜接      GET  /inpatient/discharge-checklist    Coleman CTI 四支柱 + 惡化紅旗

核心架構（不可動搖）：資料只有一份。本 router 只「讀取 / 整理 / 寫入」與門診共用的縱向資料，
不自建第二套病歷。F5「我的住院時間軸」已有 timeline.py + 前端 renderInpatientTimeline，不重做。

法規紅線（最高優先）：所有輸出都是「呈現病人自有資料 / 整理趨勢 / 衛教資訊」——
不做診斷、不判定正常／異常、不給「該不該吃」指示。
規則 5：比對、分類、狀態判定一律純程式碼；AI 只做「轉白話 / 草擬摘要」這種判斷力工作。
規則 12：AI 失敗時 fallback 到可溯源的原始資料，並把降級狀態揭露給前端（_ai 欄位）。
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 免責框架（每個畫面 / 報告都要有）──────────────────────────
DISCLAIMER = (
    "本 App 不提供醫療診斷、治療建議或處方，僅供健康資訊記錄、整理與衛教參考；"
    "如有疑問請諮詢您的醫師。"
)
HANDOVER_DISCLAIMER = (
    "本報告為病人自行記錄之資訊，非診斷依據。每項資料均標註來源與時間，"
    "請臨床人員獨立查核後使用。"
)
RECON_DISCLAIMER = (
    "本表僅呈現「居家用藥」與「住院醫囑」的差異，不代表任何用藥建議。"
    "差異原因與該不該調整，請與您的醫師或藥師確認。"
)


# ── 共用小工具 ─────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _norm(s: Optional[str]) -> str:
    """藥名 / 劑量正規化：去頭尾空白、轉小寫，供比對用。"""
    return (s or "").strip().lower()


def _fetch_safely(sb, table: str, patient_id: str, *, eq_col: str = "patient_id"):
    """讀某表某病患的資料；表不存在 / DB 異常時回 []（與 timeline.py 同 pattern）。"""
    try:
        result = sb.table(table).select("*").eq(eq_col, patient_id).execute()
        return getattr(result, "data", None) or []
    except Exception as e:
        logger.info(f"inpatient: table {table} unavailable: {e}")
        return []


def _get_profile(sb, patient_id: str) -> dict:
    try:
        r = sb.table("patient_profiles").select("*").eq("user_id", patient_id).limit(1).execute()
        return (r.data or [{}])[0] if r.data else {}
    except Exception as e:
        logger.info(f"inpatient: patient_profiles unavailable: {e}")
        return {}


def _active_home_meds(sb, patient_id: str) -> list[dict]:
    """居家用藥（門診側 medications，active=1）。"""
    meds = _fetch_safely(sb, "medications", patient_id)
    out = []
    for m in meds:
        # active 欄位 SQLite 存 1/0、Supabase 可能存 bool；兩者都當真
        if m.get("active") in (0, "0", False):
            continue
        out.append(m)
    return out


def _resolve_admission(sb, patient_id: str, admission_id: Optional[str]) -> dict:
    """取指定住院；未指定時取該病患最近一筆 active 住院。找不到回 {}。"""
    try:
        if admission_id:
            r = sb.table("admissions").select("*").eq("id", admission_id).limit(1).execute()
            return (r.data or [{}])[0] if r.data else {}
        r = (
            sb.table("admissions")
            .select("*")
            .eq("patient_id", patient_id)
            .eq("status", "active")
            .order("admit_date", desc=True)
            .limit(1)
            .execute()
        )
        return (r.data or [{}])[0] if r.data else {}
    except Exception as e:
        logger.info(f"inpatient: resolve admission failed: {e}")
        return {}


def _admission_meds(sb, admission_id: str) -> list[dict]:
    if not admission_id:
        return []
    return _fetch_safely(sb, "admission_medications", admission_id, eq_col="admission_id")


def _safe_llm(system: str, user: str, *, max_tokens: int = 200, timeout: float = 20.0) -> Optional[str]:
    """呼叫 LLM；任何失敗（含離線 / 無 key）回 None，讓 caller fallback。

    規則 12：不讓 AI 失敗變成隱性錯誤——回 None 由 caller 用可溯源原始資料補位。
    """
    try:
        from backend.services import llm_service
        text = llm_service.call_claude(system, user, max_tokens=max_tokens, timeout=timeout)
        text = (text or "").strip()
        return text or None
    except Exception as e:
        logger.info(f"inpatient: LLM unavailable, falling back: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# F1 — 居家紀錄交接報告（讀取）
# ══════════════════════════════════════════════════════════════

_SITUATION_SYSTEM = (
    "你是醫療交接摘要助手。只能根據使用者提供的『病人自填資料』，"
    "用一句繁體中文（台灣用語、≤40 字）寫出「為何此時入院 / 開始此次療程」。"
    "規則：(1) 只重述病人提供的資訊，不得新增。(2) 不下診斷、不判定病情。"
    "(3) 不確定就保守描述。(4) 直接輸出那句話，不要任何前後綴。"
)


@router.get("/handover")
def handover(
    patient_id: str = Query(...),
    admission_id: Optional[str] = Query(None),
):
    """F1 交接報告資料：仿 SBAR / I-PASS。前端負責排版成 1–2 頁 PDF。

    結構：situation（為何入院，一句）→ background（慢病/基線/過敏）
         → medications（居家用藥，逐筆標來源+時間）→ monitoring（近期自我監測）。
    每項資料標註來源與時間，讓臨床人員可獨立查核（提升信任 + 守在法規安全側）。
    """
    sb = get_supabase()
    profile = _get_profile(sb, patient_id)
    admission = _resolve_admission(sb, patient_id, admission_id)
    home_meds = _active_home_meds(sb, patient_id)

    # 近期自我監測：症狀 + 情緒（共用縱向資料；取最近數筆呈現「趨勢」而非判讀）
    symptoms = _fetch_safely(sb, "symptoms_log", patient_id)
    symptoms.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    emotions = _fetch_safely(sb, "emotions", patient_id)
    emotions.sort(key=lambda r: r.get("created_at") or "", reverse=True)

    # situation：LLM 草擬一句（規則 5：草擬屬判斷力工作）。失敗則用診斷字串保守 fallback。
    diagnosis = (admission.get("diagnosis") or "").strip()
    recent_sym = "；".join(
        str(s.get("symptoms") or "")[:60] for s in symptoms[:3] if s.get("symptoms")
    )
    ai_status = "ok"
    situation = None
    if diagnosis or recent_sym:
        user_msg = (
            f"入院 / 療程原因（病人填）：{diagnosis or '未填'}\n"
            f"近期自覺症狀（病人填）：{recent_sym or '未填'}"
        )
        situation = _safe_llm(_SITUATION_SYSTEM, user_msg, max_tokens=120)
    if not situation:
        ai_status = "fallback"
        situation = (
            f"因「{diagnosis}」入院。" if diagnosis
            else "（病人未填寫入院原因，請於床邊詢問。）"
        )

    background = {
        "chronic_conditions": profile.get("conditions") or profile.get("current_disease") or "",
        "allergies": profile.get("allergies") or "",
        "blood_type": profile.get("blood") or "",
        "height_cm": profile.get("height_cm"),
        "weight_kg": profile.get("weight_kg"),
        "regular_doctor": profile.get("doctor_name") or "",
        "regular_hospital": profile.get("hospital") or "",
        "source": "病人自填於個人檔案",
    }

    med_items = [
        {
            "name": m.get("name") or "",
            "dose": m.get("dosage") or "",
            "frequency": m.get("frequency") or "",
            "purpose": m.get("purpose") or "",
            "source": "病人自填",
            "as_of": (m.get("created_at") or "")[:10],
        }
        for m in home_meds
    ]

    monitoring = []
    for s in symptoms[:5]:
        monitoring.append({
            "kind": "symptom",
            "summary": str(s.get("symptoms") or "")[:80],
            "as_of": (s.get("created_at") or "")[:16],
            "source": "病人自填",
        })
    for e in emotions[:5]:
        monitoring.append({
            "kind": "mood",
            "summary": f"情緒分數 {e.get('score')}／5" + (f"，{e.get('note')}" if e.get("note") else ""),
            "as_of": (e.get("created_at") or "")[:16],
            "source": "病人自填",
        })

    return {
        "generated_at": _now_iso(),
        "format": "SBAR / I-PASS",
        "patient": {
            "id": patient_id,
            "gender": profile.get("gender") or "",
            "birthday": profile.get("birthday") or "",
        },
        "admission": {
            "diagnosis": diagnosis,
            "diagnosis_icd10": admission.get("diagnosis_icd10") or "",
            "ward": admission.get("ward") or "",
            "admit_date": (admission.get("admit_date") or "")[:10],
            "hospital": admission.get("hospital_name") or background["regular_hospital"],
        },
        "situation": situation,
        "background": background,
        "medications": med_items,
        "monitoring_trend": monitoring,
        "_ai": ai_status,
        "disclaimer": HANDOVER_DISCLAIMER,
    }


# ══════════════════════════════════════════════════════════════
# F3 — 個人化用藥核對（讀取 + 純程式碼對照）
# ══════════════════════════════════════════════════════════════

@router.get("/med-reconciliation")
def med_reconciliation(
    patient_id: str = Query(...),
    admission_id: Optional[str] = Query(None),
):
    """F3：居家用藥 vs 住院醫囑並排，標示 新增／停用／劑量改變／維持。

    規則 5：差異判定是確定性任務 → 純程式碼比對（依正規化藥名配對、比劑量字串），
    不丟 LLM。僅作資訊呈現，不給「該不該吃」指示（法規紅線）。
    """
    sb = get_supabase()
    admission = _resolve_admission(sb, patient_id, admission_id)
    adm_id = admission.get("id")

    home = _active_home_meds(sb, patient_id)
    inpatient = _admission_meds(sb, adm_id) if adm_id else []

    home_by = {_norm(m.get("name")): m for m in home}
    inp_by = {_norm(m.get("name")): m for m in inpatient}

    # 維持原始出現順序：先居家、再住院新增
    ordered_names: list[str] = []
    for m in home:
        k = _norm(m.get("name"))
        if k and k not in ordered_names:
            ordered_names.append(k)
    for m in inpatient:
        k = _norm(m.get("name"))
        if k and k not in ordered_names:
            ordered_names.append(k)

    rows = []
    counts = {"added": 0, "stopped": 0, "changed": 0, "same": 0}
    for k in ordered_names:
        h = home_by.get(k)
        a = inp_by.get(k)
        home_dose = (h.get("dosage") if h else "") or ""
        inp_dose = (a.get("dose") if a else "") or ""
        if h and a:
            status = "changed" if _norm(home_dose) != _norm(inp_dose) else "same"
        elif a and not h:
            status = "added"     # 住院新增
        else:
            status = "stopped"   # 住院停用（居家有、住院醫囑沒有）
        counts[status] += 1
        rows.append({
            "name": (a or h).get("name") or "",
            "status": status,           # added | stopped | changed | same
            "home": {
                "dose": home_dose,
                "frequency": (h.get("frequency") if h else "") or "",
            } if h else None,
            "inpatient": {
                "dose": inp_dose,
                "frequency": (a.get("frequency") if a else "") or "",
            } if a else None,
        })

    return {
        "admission_id": adm_id,
        "rows": rows,
        "summary": counts,
        "disclaimer": RECON_DISCLAIMER,
    }


# ══════════════════════════════════════════════════════════════
# F2 — 床邊自我記錄（寫入）+ 想問醫師的問題（QPL）
# ══════════════════════════════════════════════════════════════

class BedsideCreate(BaseModel):
    patient_id: str
    admission_id: Optional[str] = None
    pain: Optional[int] = None              # 0–10
    food: Optional[str] = None             # 預設選項：none | little | half | most
    sleep: Optional[str] = None            # good | fair | poor
    bowel: Optional[str] = None            # yes | no
    activity: Optional[str] = None         # bed | sit | walk
    treatment_response: Optional[str] = None  # better | same | worse
    mood: Optional[int] = None             # 1–5
    note: Optional[str] = None


@router.post("/bedside")
def create_bedside(body: BedsideCreate):
    """床邊自我記錄：極低操作負擔，全部欄位可選（躺著一隻手點完）。"""
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if body.pain is not None and not (0 <= body.pain <= 10):
        raise HTTPException(status_code=400, detail="pain 需介於 0–10")
    if body.mood is not None and not (1 <= body.mood <= 5):
        raise HTTPException(status_code=400, detail="mood 需介於 1–5")
    try:
        result = sb.table("bedside_logs").insert(data).execute()
    except Exception as e:
        logger.error(f"create bedside failed: {e}")
        raise HTTPException(status_code=400, detail="床邊紀錄寫入失敗")
    return result.data[0] if result.data else data


@router.get("/bedside")
def list_bedside(
    patient_id: str = Query(...),
    admission_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    sb = get_supabase()
    rows = _fetch_safely(sb, "bedside_logs", patient_id)
    if admission_id:
        rows = [r for r in rows if r.get("admission_id") == admission_id]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"logs": rows[:limit]}


# QPL（Question Prompt List）建議題庫 — 靜態，不入 DB（同 taiwan_hospitals pattern）。
# 實證：查房前提供建議問句能增加病人提問、不增焦慮、不降滿意度。
_QPL_BANK = [
    {"category": "病情", "text": "我現在的狀況，跟昨天比是好轉還是一樣？"},
    {"category": "病情", "text": "接下來幾天的治療計畫大概是什麼？"},
    {"category": "檢查", "text": "今天 / 等一下要做的檢查是為了看什麼？會不舒服嗎？"},
    {"category": "用藥", "text": "現在打的 / 吃的藥，跟我在家原本的藥有什麼不一樣？"},
    {"category": "用藥", "text": "這個藥可能會有什麼讓我不舒服的反應？"},
    {"category": "飲食", "text": "我現在可以吃什麼、不能吃什麼？什麼時候可以恢復正常吃？"},
    {"category": "活動", "text": "我可以自己下床走動嗎？有沒有要注意的？"},
    {"category": "出院", "text": "大概還要住幾天？出院前我需要先準備什麼？"},
    {"category": "出院", "text": "回家後出現什麼狀況要趕快回來或打電話？"},
]


@router.get("/qpl-bank")
def qpl_bank():
    """回傳「想問醫師」建議題庫，供前端讓病人一鍵加入自己的清單。"""
    return {"questions": _QPL_BANK}


class QuestionCreate(BaseModel):
    patient_id: str
    admission_id: Optional[str] = None
    text: str


class QuestionUpdate(BaseModel):
    status: Optional[str] = None   # open | asked
    text: Optional[str] = None


_Q_STATUS = {"open", "asked"}


@router.get("/questions")
def list_questions(
    patient_id: str = Query(...),
    admission_id: Optional[str] = Query(None),
):
    sb = get_supabase()
    rows = _fetch_safely(sb, "inpatient_questions", patient_id)
    if admission_id:
        rows = [r for r in rows if r.get("admission_id") == admission_id]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"questions": rows}


@router.post("/questions")
def create_question(body: QuestionCreate):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="問題內容不可空白")
    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "admission_id": body.admission_id,
        "text": text,
        "status": "open",
    }
    try:
        result = sb.table("inpatient_questions").insert(data).execute()
    except Exception as e:
        logger.error(f"create question failed: {e}")
        raise HTTPException(status_code=400, detail="新增問題失敗")
    return result.data[0] if result.data else data


@router.put("/questions/{question_id}")
def update_question(question_id: str, body: QuestionUpdate):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    if "status" in data and data["status"] not in _Q_STATUS:
        raise HTTPException(status_code=400, detail=f"status 必須是 {_Q_STATUS} 之一")
    sb = get_supabase()
    result = sb.table("inpatient_questions").update(data).eq("id", question_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該問題")
    return result.data[0]


@router.delete("/questions/{question_id}")
def delete_question(question_id: str):
    sb = get_supabase()
    sb.table("inpatient_questions").delete().eq("id", question_id).execute()
    return {"deleted": question_id}


# ══════════════════════════════════════════════════════════════
# F4 — 個人化住院衛教（讀取 + LLM 轉白話）
# ══════════════════════════════════════════════════════════════

def _lookup_disease(sb, diagnosis: str, icd10: str) -> dict:
    """從 disease_reference 取材（可信來源）。先比 ICD-10，再比名稱模糊。"""
    if not diagnosis and not icd10:
        return {}
    try:
        if icd10:
            r = sb.table("disease_reference").select("*").eq("icd10_code", icd10).limit(1).execute()
            if r.data:
                return r.data[0]
        if diagnosis:
            rows = sb.table("disease_reference").select("*").execute().data or []
            key = diagnosis.strip()
            for row in rows:
                if key and (key in (row.get("name_zh") or "") or key in (row.get("aliases") or "")):
                    return row
    except Exception as e:
        logger.info(f"inpatient: disease_reference lookup failed: {e}")
    return {}


_PLAINIFY_SYSTEM = (
    "你是住院衛教轉譯助手。把使用者提供的衛教資料改寫成更白話、好懂的繁體中文（台灣用語），"
    "2–4 句、避免醫學術語。規則：(1) 只根據提供的內容改寫，不得新增資料。"
    "(2) 不下診斷、不對個別病情做判斷。(3) 直接輸出白話版，不要前後綴。"
)


def _generic_edu_cards() -> list[dict]:
    """沒有對應疾病資料時的通用住院衛教（與前端 inpatientEdu 同主題）。"""
    return [
        {"topic": "hygiene", "title": "住院時的清潔", "body": "點滴部位不要弄濕，可以擦澡或部分淋浴；有問題隨時問護理師。", "source": "通用住院衛教", "personalized": False},
        {"topic": "sleep", "title": "睡不好怎麼辦", "body": "病房光線、夜間查房都會影響睡眠，需要時可請護理師協助調整。", "source": "通用住院衛教", "personalized": False},
        {"topic": "mobility", "title": "下床走動的安全", "body": "依醫囑下床，先在床邊坐 1–2 分鐘再站，避免頭暈跌倒；帶好點滴架。", "source": "通用住院衛教", "personalized": False},
    ]


@router.get("/education")
def education(
    patient_id: str = Query(...),
    admission_id: Optional[str] = Query(None),
):
    """F4：只推與「這次住院診斷」相關的衛教，內容以 disease_reference 為底，
    AI 只負責轉白話（規則 5）。附 teach-back 互動確認。"""
    sb = get_supabase()
    admission = _resolve_admission(sb, patient_id, admission_id)
    diagnosis = (admission.get("diagnosis") or "").strip()
    icd10 = (admission.get("diagnosis_icd10") or "").strip()

    disease = _lookup_disease(sb, diagnosis, icd10)
    cards: list[dict] = []
    ai_status = "n/a"

    if disease:
        # 取可信來源素材的兩段：總覽 + 自我照護，分別轉白話。
        for field, title in (("overview", f"認識「{disease.get('name_zh') or diagnosis}」"),
                             ("self_care", "住院期間的自我照護")):
            raw = (disease.get(field) or "").strip()
            if not raw:
                continue
            plain = _safe_llm(_PLAINIFY_SYSTEM, raw, max_tokens=260)
            if plain:
                ai_status = "ok"
            else:
                plain = raw  # 規則 12：AI 不可用就回原始可信來源文字
                if ai_status != "ok":
                    ai_status = "fallback"
            cards.append({
                "topic": field,
                "title": title,
                "body": plain,
                "source": disease.get("source") or "disease_reference",
                "personalized": True,
            })

    if not cards:
        cards = _generic_edu_cards()

    teach_back = "你能不能用自己的話，跟家人說說看：這次住院主要是在處理什麼？"

    return {
        "diagnosis": diagnosis,
        "personalized": bool(disease),
        "cards": cards,
        "teach_back": teach_back,
        "_ai": ai_status,
        "disclaimer": DISCLAIMER,
    }


# ══════════════════════════════════════════════════════════════
# F6 — 出院銜接（Coleman CTI 四支柱 + 惡化紅旗）
# ══════════════════════════════════════════════════════════════

def _split_red_flags(raw) -> list[str]:
    """disease_reference.red_flags 可能是 JSON 字串、list 或換行字串，統一成 list[str]。"""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    try:
        import json
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [line.strip("•- 　") for line in s.replace("；", "\n").splitlines() if line.strip()]


@router.get("/discharge-checklist")
def discharge_checklist(
    patient_id: str = Query(...),
    admission_id: Optional[str] = Query(None),
):
    """F6：出院「帶回家」清單，依 Coleman CTI 四支柱組裝。
    惡化紅旗以衛教語氣呈現（「若出現 X 請聯絡醫療人員」），
    不由 App 判定「你病情惡化了」（法規紅線）。"""
    sb = get_supabase()
    admission = _resolve_admission(sb, patient_id, admission_id)
    adm_id = admission.get("id")
    diagnosis = (admission.get("diagnosis") or "").strip()
    icd10 = (admission.get("diagnosis_icd10") or "").strip()

    # 支柱一：用藥自我管理 — 帶回家要繼續吃的藥（住院醫囑為主）
    inpatient_meds = _admission_meds(sb, adm_id) if adm_id else []
    med_items = [
        {
            "label": (m.get("name") or "") + (f"（{m.get('dose')}）" if m.get("dose") else ""),
            "detail": m.get("frequency") or "",
        }
        for m in inpatient_meds
    ] or [{"label": "出院藥單", "detail": "請逐一核對每顆藥「為什麼吃／飯前飯後／漏吃怎麼辦」"}]

    # 支柱四：認識惡化紅旗 — 取自 disease_reference（可信來源），衛教語氣
    disease = _lookup_disease(sb, diagnosis, icd10)
    red_flags = _split_red_flags(disease.get("red_flags")) if disease else []
    if not red_flags:
        red_flags = ["持續發燒、傷口紅腫流膿", "喘不過氣、胸悶胸痛", "意識不清、嚴重頭暈", "無法進食、嚴重嘔吐或腹瀉"]

    pillars = [
        {
            "key": "medication",
            "title": "用藥自我管理",
            "items": med_items,
        },
        {
            "key": "record",
            "title": "個人健康紀錄",
            "items": [
                {"label": "出院病摘 / 診斷證明", "detail": "理賠、轉診、下次就診都會用到"},
                {"label": "繼續用床邊紀錄追蹤", "detail": "回家後的不舒服、進食、睡眠都先記下來"},
            ],
        },
        {
            "key": "follow_up",
            "title": "及時追蹤",
            "items": [
                {"label": "確認回診時間與科別", "detail": "建議在出院前就把回診加入提醒"},
                {"label": "留好可聯絡的窗口", "detail": "病房 / 個管師 / 護理站電話"},
            ],
        },
        {
            "key": "red_flags",
            "title": "認識惡化紅旗",
            "note": "下列狀況屬衛教提醒，若出現請主動聯絡醫療人員或回診，App 不會替您判斷病情。",
            "items": [{"label": f"若出現「{f}」，請聯絡醫療人員", "detail": ""} for f in red_flags],
        },
    ]

    return {
        "admission_id": adm_id,
        "diagnosis": diagnosis,
        "pillars": pillars,
        "teach_back": "出院前，你能用自己的話說說看：回家後每天要做哪幾件事、出現什麼狀況要回來嗎？",
        "disclaimer": DISCLAIMER,
    }
