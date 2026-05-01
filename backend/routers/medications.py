from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta, date
import logging

from backend.db import get_supabase
from backend.services.llm_service import recognize_medicine_bag, call_claude

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_patient_exists(sb, patient_id: str) -> None:
    """
    確保 patients 表裡有對應的 row，避免 medications.patient_id FK 失敗。
    若不存在：嘗試用 users 表的 nickname 建 stub；都查不到就用 "訪客"。
    """
    try:
        existing = sb.table("patients").select("id").eq("id", patient_id).limit(1).execute()
        if existing.data:
            return
        name = "訪客"
        try:
            u = sb.table("users").select("nickname").eq("id", patient_id).limit(1).execute()
            if u.data and u.data[0].get("nickname"):
                name = u.data[0]["nickname"]
        except Exception:
            pass
        sb.table("patients").insert({"id": patient_id, "name": name}).execute()
    except Exception as e:
        # 如果 patients 表 schema 或 RLS 不允許，這裡就不硬插；交給後續 insert 的錯誤回報
        logger.warning(f"ensure_patient_exists skipped for {patient_id}: {e}")


# ── Models ────────────────────────────────────────────────

class MedicationCreate(BaseModel):
    patient_id: str
    name: str
    dosage: str | None = None
    frequency: str | None = None
    category: str | None = None
    purpose: str | None = None
    instructions: str | None = None


class MedicationPhotoUpload(BaseModel):
    patient_id: str
    image_base64: str
    media_type: str = "image/jpeg"


class MedicationLogCreate(BaseModel):
    patient_id: str
    medication_id: str
    taken: bool = True
    taken_at: str | None = None
    skip_reason: str | None = None
    notes: str | None = None


class EffectRecord(BaseModel):
    patient_id: str
    medication_id: str
    effectiveness: int  # 1-5
    side_effects: str | None = None
    symptom_changes: str | None = None
    notes: str | None = None


class ParsedMedication(BaseModel):
    name: str
    dosage: str | None = None
    frequency: str | None = None
    usage: str | None = None
    duration: str | None = None
    category: str | None = None
    purpose: str | None = None
    instructions: str | None = None
    hospital: str | None = None
    prescribed_date: str | None = None


class BulkConfirmRecognized(BaseModel):
    patient_id: str
    medications: List[ParsedMedication]


class BulkLogItem(BaseModel):
    medication_id: str
    taken: bool = True
    skip_reason: str | None = None
    notes: str | None = None


class BulkLog(BaseModel):
    patient_id: str
    taken_at: str | None = None
    items: List[BulkLogItem] = Field(default_factory=list)


# ── 藥物 CRUD ─────────────────────────────────────────────

@router.get("/")
def get_medications(patient_id: str = Query(...)):
    """取得患者的所有藥物"""
    sb = get_supabase()
    result = sb.table("medications").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()
    return {"medications": result.data}


@router.post("/")
def create_medication(body: MedicationCreate):
    """手動新增藥物"""
    sb = get_supabase()
    _ensure_patient_exists(sb, body.patient_id)
    data = body.model_dump(exclude_none=True)
    try:
        result = sb.table("medications").insert(data).execute()
    except Exception as e:
        logger.error(f"Create medication failed: {e}")
        raise HTTPException(status_code=400, detail=f"新增藥物失敗：{e}")
    if not result.data:
        raise HTTPException(status_code=400, detail="新增失敗（資料庫未回傳資料）")
    return result.data[0]


@router.delete("/{medication_id}")
def delete_medication(medication_id: str):
    """刪除藥物（標記停用）"""
    sb = get_supabase()
    result = sb.table("medications").update({"active": 0}).eq("id", medication_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該藥物")
    return {"message": "藥物已停用", "id": medication_id}


# ── 藥袋拍照辨識 ──────────────────────────────────────────

@router.post("/recognize")
def recognize_from_photo(body: MedicationPhotoUpload):
    """
    上傳藥袋照片 → Claude Vision 辨識 → 自動建立藥物紀錄。
    回傳：
      - recognized: 成功寫入資料庫的筆數
      - medications: 已寫入的藥物 rows
      - parsed: 從影像辨識出來的原始資料（即使寫入失敗也會回傳，供前端手動編輯）
      - raw_text: LLM 原始文字（方便 debug）
      - errors: 若有寫入錯誤，逐筆回報
    """
    # 拍照辨識常見故障：Ollama 沒開、模型沒下載、超時、JSON 解析失敗。
    # 一律不丟 500，回 200 + 明確訊息，前端才能優雅地切到「手動選單」流程。
    try:
        recognition = recognize_medicine_bag(body.image_base64, body.media_type)
    except Exception as e:
        logger.error(f"recognize_medicine_bag failed: {e}")
        return {
            "recognized": 0,
            "medications": [],
            "parsed": [],
            "raw_text": "",
            "message": f"影像辨識服務暫時無法使用（{type(e).__name__}），請改用手動方式新增藥物。",
            "errors": [str(e)],
            "fallback": "manual",
        }

    meds = recognition.get("medications", []) or []
    raw_text = recognition.get("raw_text", "")
    err_kind = recognition.get("error")

    if not meds:
        # 依錯誤類型給更精準的訊息
        if err_kind and "Timeout" in err_kind:
            msg = "影像辨識超時（本機 LLM 在 CPU 上需數分鐘）。請稍後再試一次，或改用手動填寫。"
        elif err_kind == "json_parse_failed":
            msg = "辨識完成但回傳格式異常（模型輸出無法解析），請改用手動填寫，下方有原始文字可參考。"
        elif err_kind in ("ConnectError", "ConnectionError") or (err_kind and "Connect" in err_kind):
            msg = "辨識服務未啟動（Ollama 沒回應）。請啟動 Ollama 或改用手動填寫。"
        elif err_kind == "empty_image":
            msg = "未收到影像資料，請重新拍攝。"
        else:
            msg = "無法辨識藥袋內容，請嘗試拍攝更清晰的照片，或手動填寫下方資料。"
        return {
            "recognized": 0,
            "medications": [],
            "parsed": [],
            "raw_text": raw_text,
            "message": msg,
            "errors": [err_kind] if err_kind else [],
            "fallback": "manual",
        }

    # 只做辨識，不自動寫入 DB
    # 讓前端顯示可編輯卡片，由使用者確認後再按「加入我的藥物」寫入
    # 原因：每家醫院版型不同，辨識結果需人工確認；強迫走確認流程可避免錯誤資料污染藥物清單
    parsed = []
    for med in meds:
        parsed.append({
            "name": (med.get("name") or "").strip() or "未知藥物",
            "dosage": med.get("dosage"),
            "frequency": med.get("frequency"),
            "usage": med.get("usage"),
            "duration": med.get("duration"),
            "category": med.get("category"),
            "purpose": med.get("purpose"),
            "instructions": med.get("instructions"),
            "hospital": med.get("hospital"),
            "prescribed_date": med.get("prescribed_date"),
        })

    return {
        "recognized": 0,
        "medications": [],
        "parsed": parsed,
        "raw_text": raw_text,
        "message": f"辨識出 {len(parsed)} 種藥物，請確認後加入我的藥物。",
        "errors": [],
        "fallback": None,
    }


def _merge_instructions(p: ParsedMedication) -> str | None:
    """把辨識結果中沒有對應欄位的補充資訊合併進 instructions 欄。"""
    parts = []
    if p.instructions:
        parts.append(p.instructions.strip())
    if p.usage:
        parts.append(f"用法：{p.usage}")
    if p.duration:
        parts.append(f"療程：{p.duration}")
    if p.hospital:
        parts.append(f"來源：{p.hospital}")
    if p.prescribed_date:
        parts.append(f"開立日期：{p.prescribed_date}")
    return " / ".join(parts) if parts else None


@router.post("/confirm")
def confirm_recognized_medications(body: BulkConfirmRecognized):
    """
    辨識→確認→批次寫入「我的藥物」。
    前端流程：呼叫 /recognize 拿到 parsed，使用者編輯/勾選後再 POST 到這裡。
    """
    if not body.medications:
        raise HTTPException(status_code=400, detail="沒有要新增的藥物")

    sb = get_supabase()
    _ensure_patient_exists(sb, body.patient_id)

    inserted = []
    errors = []
    for idx, p in enumerate(body.medications):
        name = (p.name or "").strip()
        if not name:
            errors.append({"index": idx, "error": "藥名為空"})
            continue
        data = {
            "patient_id": body.patient_id,
            "name": name,
            "dosage": p.dosage,
            "frequency": p.frequency,
            "category": p.category,
            "purpose": p.purpose,
            "instructions": _merge_instructions(p),
            "recognized_from_photo": 1,
        }
        data = {k: v for k, v in data.items() if v is not None}
        try:
            result = sb.table("medications").insert(data).execute()
            if result.data:
                inserted.append(result.data[0])
        except Exception as e:
            logger.error(f"confirm_recognized insert failed for {name}: {e}")
            errors.append({"index": idx, "name": name, "error": str(e)})

    return {
        "inserted": len(inserted),
        "medications": inserted,
        "errors": errors,
        "message": f"已加入 {len(inserted)} 筆藥物到我的藥物清單" + (f"，{len(errors)} 筆失敗" if errors else ""),
    }


# ── 服藥日誌 ──────────────────────────────────────────────

@router.post("/log")
def log_medication(body: MedicationLogCreate):
    """記錄服藥（打卡）"""
    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "medication_id": body.medication_id,
        "taken": 1 if body.taken else 0,
        "taken_at": body.taken_at or datetime.utcnow().isoformat(),
        "skip_reason": body.skip_reason,
        "notes": body.notes,
    }
    result = sb.table("medication_logs").insert(data).execute()
    return result.data[0]


@router.post("/log/bulk")
def log_medications_bulk(body: BulkLog):
    """
    患者一次勾選多個藥物打卡（搭配 /menu 使用）。
    回傳每筆 log 的寫入結果。
    """
    if not body.items:
        raise HTTPException(status_code=400, detail="沒有要打卡的藥物")

    sb = get_supabase()
    taken_at = body.taken_at or datetime.utcnow().isoformat()
    inserted = []
    errors = []
    for item in body.items:
        data = {
            "patient_id": body.patient_id,
            "medication_id": item.medication_id,
            "taken": 1 if item.taken else 0,
            "taken_at": taken_at,
            "skip_reason": item.skip_reason,
            "notes": item.notes,
        }
        try:
            result = sb.table("medication_logs").insert(data).execute()
            if result.data:
                inserted.append(result.data[0])
        except Exception as e:
            logger.error(f"bulk log failed for {item.medication_id}: {e}")
            errors.append({"medication_id": item.medication_id, "error": str(e)})

    return {
        "logged": len(inserted),
        "logs": inserted,
        "errors": errors,
    }


@router.get("/menu")
def medication_menu(patient_id: str = Query(...)):
    """
    產生今日服藥選單：列出患者所有有效藥物，附上今日是否已打卡，
    讓患者直接勾選「今天吃了哪些」。
    回傳：
      - items: 每筆藥物 + taken_today / log_count_today / last_taken_at
      - today: ISO 日期（UTC）
    """
    sb = get_supabase()
    today = date.today().isoformat()
    since = today + "T00:00:00"
    until = today + "T23:59:59"

    meds = sb.table("medications").select("*").eq("patient_id", patient_id).execute().data or []
    active_meds = [m for m in meds if m.get("active", 1)]

    today_logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("taken_at", since)
        .lte("taken_at", until)
        .execute()
        .data
        or []
    )
    all_logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .order("taken_at", desc=True)
        .execute()
        .data
        or []
    )

    last_taken_map: dict[str, str] = {}
    for log in all_logs:
        mid = log.get("medication_id")
        if mid and log.get("taken") and mid not in last_taken_map:
            last_taken_map[mid] = log.get("taken_at")

    items = []
    for m in active_meds:
        mid = m["id"]
        today_for_med = [l for l in today_logs if l.get("medication_id") == mid]
        items.append({
            "id": mid,
            "name": m.get("name"),
            "dosage": m.get("dosage"),
            "frequency": m.get("frequency"),
            "category": m.get("category"),
            "purpose": m.get("purpose"),
            "instructions": m.get("instructions"),
            "taken_today": any(l.get("taken") for l in today_for_med),
            "log_count_today": len(today_for_med),
            "last_taken_at": last_taken_map.get(mid),
        })

    return {
        "today": today,
        "patient_id": patient_id,
        "total": len(items),
        "items": items,
    }


@router.get("/logs")
def get_medication_logs(
    patient_id: str = Query(...),
    medication_id: Optional[str] = Query(None),
    days: int = Query(30, description="查詢最近幾天"),
):
    """取得服藥日誌"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    query = sb.table("medication_logs").select("*").eq("patient_id", patient_id).gte("taken_at", since).order("taken_at", desc=True)
    if medication_id:
        query = query.eq("medication_id", medication_id)
    result = query.execute()
    return {"logs": result.data, "days": days}


# ── 療效追蹤 ──────────────────────────────────────────────

@router.post("/effects")
def record_effect(body: EffectRecord):
    """記錄藥物療效與副作用"""
    if body.effectiveness < 1 or body.effectiveness > 5:
        raise HTTPException(status_code=400, detail="effectiveness 必須在 1-5 之間")
    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "medication_id": body.medication_id,
        "effectiveness": body.effectiveness,
        "side_effects": body.side_effects,
        "symptom_changes": body.symptom_changes,
        "notes": body.notes,
        "recorded_at": datetime.utcnow().isoformat(),
    }
    result = sb.table("medication_effects").insert(data).execute()
    return result.data[0]


@router.get("/effects")
def get_effects(
    patient_id: str = Query(...),
    medication_id: Optional[str] = Query(None),
):
    """取得療效紀錄"""
    sb = get_supabase()
    query = sb.table("medication_effects").select("*").eq("patient_id", patient_id).order("recorded_at", desc=True)
    if medication_id:
        query = query.eq("medication_id", medication_id)
    result = query.execute()
    return {"effects": result.data}


# ── 統計與圖表資料 ────────────────────────────────────────

@router.get("/stats")
def medication_stats(
    patient_id: str = Query(...),
    days: int = Query(30),
):
    """
    取得藥物管理統計：服藥率、療效趨勢、各藥物狀態
    用於前端折線圖與圖表
    """
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # 所有藥物
    meds = sb.table("medications").select("*").eq("patient_id", patient_id).execute().data or []
    active_meds = [m for m in meds if m.get("active", 1)]

    # 服藥日誌
    logs = sb.table("medication_logs").select("*").eq("patient_id", patient_id).gte("taken_at", since).order("taken_at").execute().data or []

    # 療效紀錄
    effects = sb.table("medication_effects").select("*").eq("patient_id", patient_id).order("recorded_at").execute().data or []

    # 計算服藥率
    total_logs = len(logs)
    taken_count = sum(1 for l in logs if l.get("taken"))
    adherence_rate = round(taken_count / total_logs * 100, 1) if total_logs else 0

    # 每日服藥率趨勢（折線圖資料）
    daily_adherence = {}
    for log in logs:
        day = log.get("taken_at", "")[:10]
        if day not in daily_adherence:
            daily_adherence[day] = {"taken": 0, "total": 0}
        daily_adherence[day]["total"] += 1
        if log.get("taken"):
            daily_adherence[day]["taken"] += 1

    adherence_trend = [
        {
            "date": day,
            "rate": round(d["taken"] / d["total"] * 100, 1) if d["total"] else 0,
            "taken": d["taken"],
            "total": d["total"],
        }
        for day, d in sorted(daily_adherence.items())
    ]

    # 療效趨勢（折線圖資料）
    effect_trend = [
        {
            "date": e.get("recorded_at", "")[:10],
            "effectiveness": e.get("effectiveness"),
            "medication_id": e.get("medication_id"),
        }
        for e in effects
    ]

    # 各藥物統計
    med_stats = []
    for med in active_meds:
        med_id = med["id"]
        med_logs = [l for l in logs if l.get("medication_id") == med_id]
        med_taken = sum(1 for l in med_logs if l.get("taken"))
        med_effects = [e for e in effects if e.get("medication_id") == med_id]
        avg_effect = round(sum(e.get("effectiveness", 0) for e in med_effects) / len(med_effects), 1) if med_effects else None

        med_stats.append({
            "id": med_id,
            "name": med["name"],
            "dosage": med.get("dosage"),
            "category": med.get("category"),
            "adherence_rate": round(med_taken / len(med_logs) * 100, 1) if med_logs else 0,
            "total_logs": len(med_logs),
            "avg_effectiveness": avg_effect,
            "effect_records": len(med_effects),
        })

    return {
        "summary": {
            "total_medications": len(active_meds),
            "adherence_rate": adherence_rate,
            "total_logs": total_logs,
            "days": days,
        },
        "adherence_trend": adherence_trend,
        "effect_trend": effect_trend,
        "medications": med_stats,
    }


# ── 回診報告 ──────────────────────────────────────────────

@router.get("/report")
def generate_report(
    patient_id: str = Query(...),
    days: int = Query(30, description="報告涵蓋天數"),
):
    """
    產出回診藥物報告：統計數據 + AI 摘要
    供醫師參考藥物反應
    """
    stats = medication_stats(patient_id=patient_id, days=days)

    if not stats["medications"]:
        return {"report": "此患者尚無藥物紀錄", "stats": stats}

    # 組合資料給 Claude 產出報告
    data_summary = f"統計期間：最近 {days} 天\n\n"
    data_summary += f"整體服藥率：{stats['summary']['adherence_rate']}%\n"
    data_summary += f"用藥數量：{stats['summary']['total_medications']} 種\n\n"
    data_summary += "各藥物明細：\n"
    for med in stats["medications"]:
        data_summary += f"- {med['name']}"
        if med.get("dosage"):
            data_summary += f"（{med['dosage']}）"
        data_summary += f"：服藥率 {med['adherence_rate']}%"
        if med.get("avg_effectiveness"):
            data_summary += f"，平均療效 {med['avg_effectiveness']}/5"
        data_summary += "\n"

    # 療效變化
    if stats["effect_trend"]:
        data_summary += "\n療效追蹤紀錄：\n"
        for e in stats["effect_trend"][-10:]:
            data_summary += f"- {e['date']}：療效 {e['effectiveness']}/5\n"

    report_prompt = (
        "你是一位醫療報告助手。請根據以下藥物管理數據，產出一份簡潔的回診藥物報告。\n"
        "報告對象是醫師，用專業但清楚的語言。\n"
        "包含：1) 用藥概況  2) 服藥順從性分析  3) 療效觀察  4) 建議關注事項\n"
        "使用 Markdown 格式，保持簡潔。"
    )

    try:
        report_text = call_claude(report_prompt, data_summary)
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        report_text = f"報告生成失敗：{e}"

    return {
        "report": report_text,
        "stats": stats,
        "period_days": days,
    }


# ── 醫師端：整體用藥概覽 ──────────────────────────────────

@router.get("/doctor-summary")
def doctor_summary(
    patient_id: str = Query(...),
    days: int = Query(30, description="統計區間（天），對應「上次回診至今」"),
):
    """
    醫師端視角：患者整體用藥折線、服藥情況、藥物使用總結。
    回傳結構供醫師端 UI 直接渲染：
      - patient: 病患基本資料
      - period: { days, since, until }
      - overall: 整體服藥率、總用藥數、區間紀錄筆數
      - per_medication: 各藥物服藥率/最近一次服用/平均療效/副作用紀錄
      - adherence_trend: 每日服藥率折線
      - effect_trend: 療效折線
      - missed_alerts: 連續漏服 ≥ 2 天的警示
      - summary: AI 摘要（可給醫師當回診筆記參考）
    """
    sb = get_supabase()

    patient_rows = sb.table("patients").select("*").eq("id", patient_id).limit(1).execute().data or []
    patient = patient_rows[0] if patient_rows else {"id": patient_id, "name": "未知"}

    until_dt = datetime.utcnow()
    since_dt = until_dt - timedelta(days=days)
    since = since_dt.isoformat()
    until = until_dt.isoformat()

    meds = sb.table("medications").select("*").eq("patient_id", patient_id).execute().data or []
    active_meds = [m for m in meds if m.get("active", 1)]
    inactive_meds = [m for m in meds if not m.get("active", 1)]

    logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("taken_at", since)
        .order("taken_at")
        .execute()
        .data
        or []
    )
    effects = (
        sb.table("medication_effects")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("recorded_at", since)
        .order("recorded_at")
        .execute()
        .data
        or []
    )

    total_logs = len(logs)
    taken_count = sum(1 for l in logs if l.get("taken"))
    overall_adherence = round(taken_count / total_logs * 100, 1) if total_logs else 0.0

    # 每日服藥率
    daily: dict[str, dict] = {}
    for log in logs:
        day = (log.get("taken_at") or "")[:10]
        if not day:
            continue
        d = daily.setdefault(day, {"taken": 0, "total": 0})
        d["total"] += 1
        if log.get("taken"):
            d["taken"] += 1
    adherence_trend = [
        {
            "date": day,
            "rate": round(d["taken"] / d["total"] * 100, 1) if d["total"] else 0.0,
            "taken": d["taken"],
            "total": d["total"],
        }
        for day, d in sorted(daily.items())
    ]

    effect_trend = [
        {
            "date": (e.get("recorded_at") or "")[:10],
            "effectiveness": e.get("effectiveness"),
            "medication_id": e.get("medication_id"),
            "side_effects": e.get("side_effects"),
        }
        for e in effects
    ]

    # 各藥物明細
    per_medication = []
    for m in active_meds:
        mid = m["id"]
        m_logs = [l for l in logs if l.get("medication_id") == mid]
        m_taken = [l for l in m_logs if l.get("taken")]
        m_effects = [e for e in effects if e.get("medication_id") == mid]
        avg_eff = (
            round(sum(e.get("effectiveness", 0) for e in m_effects) / len(m_effects), 2)
            if m_effects
            else None
        )
        side_effects_seen = sorted({
            (e.get("side_effects") or "").strip()
            for e in m_effects
            if (e.get("side_effects") or "").strip()
        })
        last_taken_at = m_taken[-1].get("taken_at") if m_taken else None
        per_medication.append({
            "id": mid,
            "name": m.get("name"),
            "dosage": m.get("dosage"),
            "frequency": m.get("frequency"),
            "category": m.get("category"),
            "purpose": m.get("purpose"),
            "adherence_rate": round(len(m_taken) / len(m_logs) * 100, 1) if m_logs else 0.0,
            "log_count": len(m_logs),
            "last_taken_at": last_taken_at,
            "avg_effectiveness": avg_eff,
            "effect_records": len(m_effects),
            "side_effects": side_effects_seen,
        })

    # 漏服警示：最近 7 天每天服藥率 < 50% 的藥物
    missed_alerts = []
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    recent_logs = [l for l in logs if (l.get("taken_at") or "") >= cutoff]
    for m in active_meds:
        mid = m["id"]
        m_recent = [l for l in recent_logs if l.get("medication_id") == mid]
        if not m_recent:
            missed_alerts.append({
                "medication_id": mid,
                "name": m.get("name"),
                "reason": "近 7 天無服藥紀錄",
            })
            continue
        m_taken = sum(1 for l in m_recent if l.get("taken"))
        rate = m_taken / len(m_recent) * 100 if m_recent else 0
        if rate < 50:
            missed_alerts.append({
                "medication_id": mid,
                "name": m.get("name"),
                "reason": f"近 7 天服藥率 {round(rate, 1)}%",
            })

    # AI 摘要（給醫師當回診筆記參考）
    summary_text: str | None = None
    if active_meds:
        digest = (
            f"病患：{patient.get('name', '未知')}（{days} 天區間）\n"
            f"整體服藥率：{overall_adherence}%（{taken_count}/{total_logs} 筆紀錄）\n"
            f"用藥數：{len(active_meds)} 種，停用 {len(inactive_meds)} 種\n\n"
            "各藥物：\n"
        )
        for pm in per_medication:
            digest += f"- {pm['name']}"
            if pm.get("dosage"):
                digest += f"（{pm['dosage']}）"
            digest += f"：服藥率 {pm['adherence_rate']}%"
            if pm.get("avg_effectiveness") is not None:
                digest += f"，平均療效 {pm['avg_effectiveness']}/5"
            if pm.get("side_effects"):
                digest += f"，回報副作用：{', '.join(pm['side_effects'])}"
            digest += "\n"
        if missed_alerts:
            digest += "\n警示：\n"
            for a in missed_alerts:
                digest += f"- {a['name']}：{a['reason']}\n"

        prompt = (
            "你是一位協助醫師的回診摘要助手。請根據以下患者用藥資料，"
            "用條列式產出『回診重點摘要』供醫師快速判讀，不要套話、不要說『建議就醫』。\n"
            "格式（Markdown）：\n"
            "## 用藥概況\n"
            "## 服藥順從性\n"
            "## 療效與副作用觀察\n"
            "## 需要醫師關注的重點\n"
        )
        try:
            summary_text = call_claude(prompt, digest)
        except Exception as e:
            logger.error(f"doctor-summary AI failed: {e}")
            summary_text = None

    return {
        "patient": {
            "id": patient.get("id"),
            "name": patient.get("name"),
            "age": patient.get("age"),
            "gender": patient.get("gender"),
        },
        "period": {"days": days, "since": since, "until": until},
        "overall": {
            "adherence_rate": overall_adherence,
            "total_log_records": total_logs,
            "taken_count": taken_count,
            "active_medications": len(active_meds),
            "inactive_medications": len(inactive_meds),
        },
        "per_medication": per_medication,
        "adherence_trend": adherence_trend,
        "effect_trend": effect_trend,
        "missed_alerts": missed_alerts,
        "summary": summary_text,
    }
