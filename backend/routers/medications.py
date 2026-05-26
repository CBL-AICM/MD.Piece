import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging

from backend.db import get_supabase
from backend.security import current_user
from backend.services.llm_service import (
    recognize_medicine_bag,
    extract_medications_from_ocr_text,
    call_claude,
)
from backend.utils.medication_schedule import (
    DEFAULT_MIN_INTERVAL_HOURS,
    annotate_medication,
    check_dose_safety,
    parse_custom_schedule,
    parse_time_slots,
)

logger = logging.getLogger(__name__)
router = APIRouter()


_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _enforce_self_patient(patient_id: str, me: dict) -> str:
    """Query/body 的 patient_id 必須等於 token.sub。"""
    if not isinstance(patient_id, str) or not _ID_RE.fullmatch(patient_id):
        raise HTTPException(status_code=400, detail="patient_id 格式不合法")
    if me.get("id") != patient_id:
        raise HTTPException(status_code=403, detail="不可存取他人藥物資料")
    return patient_id


def _assert_owns_medication(sb, medication_id: str, me: dict) -> dict:
    """確認 medication_id 屬於 caller。回傳 med row。"""
    if not isinstance(medication_id, str) or not _ID_RE.fullmatch(medication_id):
        raise HTTPException(status_code=400, detail="medication_id 格式不合法")
    res = sb.table("medications").select("*").eq("id", medication_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="找不到該藥物")
    med = res.data[0]
    if med.get("patient_id") != me.get("id"):
        raise HTTPException(status_code=403, detail="不可存取他人藥物")
    return med


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _find_existing_active_medication(
    sb, patient_id: str, name: str, dosage: str | None
) -> dict | None:
    """
    回傳同一患者下已存在、且 name+dosage 相同的有效藥物。

    用於避免拍到同一張藥單時，重複建立藥物紀錄。比對採大小寫不敏感、去頭尾空白；
    name 為空白時不比對（交給呼叫者另外處理）。
    """
    norm_name = _norm(name)
    if not norm_name:
        return None
    try:
        rows = (
            sb.table("medications")
            .select("*")
            .eq("patient_id", patient_id)
            .execute()
            .data
            or []
        )
    except Exception as e:
        # 不把 patient_id 寫進 log（屬於 PHI），只記錄錯誤類型
        logger.warning("medication dedup lookup failed: %s", type(e).__name__)
        return None
    norm_dose = _norm(dosage)
    for r in rows:
        if r.get("active", 1) == 0:
            continue
        if _norm(r.get("name")) != norm_name:
            continue
        if _norm(r.get("dosage")) != norm_dose:
            continue
        return r
    return None


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
        sb.table("patients").insert({"id": patient_id, "name": name, "age": 0}).execute()
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
    # 非統一時刻自訂排程。格式：{"entries":[{"weekdays":[0..6],"time":"HH:MM"}, ...]}
    # 0=Mon..6=Sun（與 datetime.weekday() 一致）。傳 None 代表沿用 frequency 文字解析。
    custom_schedule: dict | None = None
    # 病人自寫的「我的用法」note，覆寫藥袋預設文字。例：醫師口頭交代「飯前 30 分鐘吃」。
    custom_note: str | None = None


class MedicationNoteUpdate(BaseModel):
    # 顯式 None / 空字串 = 清空自訂用法（回到藥袋預設顯示）；其他字串會 strip 前後空白後存。
    custom_note: str | None = None


class MedicationScheduleUpdate(BaseModel):
    # 顯式 None = 清空自訂排程、回到 frequency 文字解析；非 None 會被 parse_custom_schedule 正規化。
    custom_schedule: dict | None = None


class MedicationPhotoUpload(BaseModel):
    patient_id: str
    image_base64: str
    media_type: str = "image/jpeg"
    # 前端可選擇先在瀏覽器跑 Tesseract.js OCR，把純文字直接送上來，
    # 後端就跳過影像辨識（省 LLM 成本 + 跳過不準的 vision OCR），
    # 直接拿 ocr_text 餵 Haiku 抽結構化欄位。空字串視為沒提供。
    ocr_text: str | None = None


class MedicationLogCreate(BaseModel):
    patient_id: str
    medication_id: str
    taken: bool = True
    taken_at: str | None = None
    skip_reason: str | None = None
    notes: str | None = None
    # 「其他」分類（每 X 小時 / PRN）的藥按下打卡時，前端可帶上 force=true
    # 表示已看過 4 小時間隔風險警告、堅持要記錄
    force: bool = False


class EffectRecord(BaseModel):
    patient_id: str
    medication_id: str
    effectiveness: int  # 1-5
    side_effects: str | None = None
    symptom_changes: str | None = None
    notes: str | None = None


# ── 藥物 CRUD ─────────────────────────────────────────────

def _augment_with_schedule(meds: list[dict]) -> list[dict]:
    """在每個 medication dict 上掛 slots / interval_hours / bucket / is_other。"""
    out = []
    for m in meds or []:
        mm = dict(m)
        mm.update(annotate_medication(mm))
        out.append(mm)
    return out


@router.get("/")
def get_medications(patient_id: str = Query(...), me: dict = Depends(current_user)):
    """取得患者的所有藥物，附加服藥時段標籤（早 / 中 / 晚 / 其他）。"""
    pid = _enforce_self_patient(patient_id, me)
    sb = get_supabase()
    result = sb.table("medications").select("*").eq("patient_id", pid).order("created_at", desc=True).execute()
    return {"medications": _augment_with_schedule(result.data or [])}


@router.post("/")
def create_medication(body: MedicationCreate, me: dict = Depends(current_user)):
    """
    手動新增藥物。

    若已存在同患者、同名稱（大小寫不敏感）且同劑量的有效藥物，
    視為「拍到同一張藥單」的情境，直接回傳既有紀錄並標記 _deduped=True，
    避免清單裡塞滿同一顆藥。
    """
    _enforce_self_patient(body.patient_id, me)
    sb = get_supabase()
    _ensure_patient_exists(sb, body.patient_id)

    existing = _find_existing_active_medication(sb, body.patient_id, body.name, body.dosage)
    if existing:
        out = dict(existing)
        out["_deduped"] = True
        return out

    data = body.model_dump(exclude_none=True)
    if "custom_schedule" in data:
        # 把使用者送進來的物件正規化；不合法就當沒設（避免污染 DB）。
        normalized = parse_custom_schedule(data["custom_schedule"])
        if normalized is None:
            data.pop("custom_schedule", None)
        else:
            data["custom_schedule"] = normalized
    try:
        result = sb.table("medications").insert(data).execute()
    except Exception as e:
        logger.error(f"Create medication failed: {e}")
        raise HTTPException(status_code=400, detail=f"新增藥物失敗：{e}")
    if not result.data:
        raise HTTPException(status_code=400, detail="新增失敗（資料庫未回傳資料）")
    return result.data[0]


@router.put("/{medication_id}/schedule")
def update_medication_schedule(medication_id: str, body: MedicationScheduleUpdate, me: dict = Depends(current_user)):
    """
    設定／清空單一藥物的非統一時刻自訂排程。

    傳 body.custom_schedule = {"entries":[{"weekdays":[0..6],"time":"HH:MM"}, ...]} 設定排程。
    傳 None / 空 dict / 不合法格式都會清空（custom_schedule 設為 NULL），
    讓 annotate_medication 退回去用 frequency 文字解析。
    """
    sb = get_supabase()
    _assert_owns_medication(sb, medication_id, me)
    normalized = parse_custom_schedule(body.custom_schedule)
    try:
        result = (
            sb.table("medications")
            .update({"custom_schedule": normalized})
            .eq("id", medication_id)
            .execute()
        )
    except Exception as e:
        logger.error(f"Update medication schedule failed: {e}")
        raise HTTPException(status_code=400, detail=f"更新排程失敗：{e}")
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該藥物")
    row = dict(result.data[0])
    row.update(annotate_medication(row))
    return row


# 自訂用法上限。Rationale：給病人寫一句覆寫藥袋預設（例：「飯前 30 分鐘」、
# 「跟著食物配溫水、不要躺著吃」），不是長篇病歷描述。超過會在 router 端截斷
# 而非 raise — 避免使用者一句話打到上限被踢掉、輸入很挫。
MAX_CUSTOM_NOTE_LEN = 200


@router.put("/{medication_id}/note")
def update_medication_note(medication_id: str, body: MedicationNoteUpdate, me: dict = Depends(current_user)):
    """
    設定／清空單一藥物的「我的用法」note（覆寫藥袋預設）。

    傳 body.custom_note = "我的私下用法描述" → 寫入（最多 MAX_CUSTOM_NOTE_LEN
    字、超過會截斷）。傳 None 或 strip 後空字串 → 設成 NULL，前端顯示退回到
    藥袋預設文字。
    """
    sb = get_supabase()
    _assert_owns_medication(sb, medication_id, me)
    raw = body.custom_note
    if raw is None:
        normalized = None
    else:
        s = raw.strip()
        normalized = s[:MAX_CUSTOM_NOTE_LEN] if s else None
    try:
        result = (
            sb.table("medications")
            .update({"custom_note": normalized})
            .eq("id", medication_id)
            .execute()
        )
    except Exception as e:
        logger.error(f"Update medication note failed: {e}")
        raise HTTPException(status_code=400, detail=f"更新用法失敗：{e}")
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該藥物")
    row = dict(result.data[0])
    row.update(annotate_medication(row))
    return row


@router.delete("/{medication_id}")
def delete_medication(medication_id: str, me: dict = Depends(current_user)):
    """刪除藥物（標記停用）"""
    sb = get_supabase()
    _assert_owns_medication(sb, medication_id, me)
    result = sb.table("medications").update({"active": 0}).eq("id", medication_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該藥物")
    return {"message": "藥物已停用", "id": medication_id}


# ── 藥袋拍照辨識 ──────────────────────────────────────────

@router.post("/recognize")
def recognize_from_photo(body: MedicationPhotoUpload, me: dict = Depends(current_user)):
    """
    上傳藥袋照片 → Claude Vision 辨識 → 自動建立藥物紀錄。
    回傳：
      - recognized: 成功寫入資料庫的筆數
      - medications: 已寫入的藥物 rows
      - parsed: 從影像辨識出來的原始資料（即使寫入失敗也會回傳，供前端手動編輯）
      - raw_text: LLM 原始文字（方便 debug）
      - errors: 若有寫入錯誤，逐筆回報
    """
    _enforce_self_patient(body.patient_id, me)
    try:
        if body.ocr_text and len(body.ocr_text.strip()) >= 20:
            # 前端已用 Tesseract.js 做完 OCR，直接抽結構化欄位（跳過影像 LLM）
            recognition = extract_medications_from_ocr_text(body.ocr_text)
        else:
            recognition = recognize_medicine_bag(body.image_base64, body.media_type)
    except Exception as e:
        logger.error(f"recognize_medicine_bag failed: {e}")
        raise HTTPException(status_code=500, detail=f"影像辨識服務失敗：{e}")

    meds = recognition.get("medications", []) or []
    raw_text = recognition.get("raw_text", "")

    if not meds:
        # 所有 vision provider 都失敗或都沒辨識出內容 → 把每個 provider 的失敗訊息
        # 一併回傳，方便前端與後端排查（例如 Vercel 上看不到任何 provider 是否被啟用）。
        return {
            "recognized": 0,
            "medications": [],
            "parsed": [],
            "raw_text": raw_text,
            "provider": recognition.get("provider"),
            "errors": recognition.get("errors", []),
            "message": "無法辨識藥袋內容，請嘗試拍攝更清晰的照片，或手動填寫下方資料。",
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

    # 為每筆 parsed 結果預先標記它會被歸到哪個時段（早 / 中 / 晚 / 其他），
    # 讓前端在「確認加入」前就能顯示分類，使用者比較有信心。
    for p in parsed:
        p["schedule"] = parse_time_slots(p.get("frequency"), p.get("usage"))

    return {
        "recognized": 0,
        "medications": [],
        "parsed": parsed,
        "raw_text": raw_text,
        "provider": recognition.get("provider"),
        "errors": recognition.get("errors", []),
        "message": f"辨識出 {len(parsed)} 種藥物，請確認後加入我的藥物。",
    }


# ── 服藥日誌 ──────────────────────────────────────────────

def _recent_logs(sb, patient_id: str, medication_id: str, days: int = 2) -> list[dict]:
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .eq("medication_id", medication_id)
        .gte("taken_at", since)
        .order("taken_at", desc=True)
        .execute()
    )
    return res.data or []


def _load_med(sb, medication_id: str) -> dict | None:
    res = sb.table("medications").select("*").eq("id", medication_id).limit(1).execute()
    return res.data[0] if res.data else None


@router.get("/can-take")
def can_take(patient_id: str = Query(...), medication_id: str = Query(...), me: dict = Depends(current_user)):
    """
    檢查現在是否能服這顆藥（前端在打卡前 call，可預覽風險）。

    回傳 dose safety 結果（含 hours_since_last / required_hours / level / message）
    以及該藥物目前的 schedule（slots / interval_hours / is_other），
    讓前端決定要不要彈跳安全警告。
    """
    pid = _enforce_self_patient(patient_id, me)
    sb = get_supabase()
    med = _assert_owns_medication(sb, medication_id, me)
    schedule = annotate_medication(med)
    logs = _recent_logs(sb, pid, medication_id)
    safety = check_dose_safety(
        logs,
        interval_hours=schedule.get("interval_hours"),
        is_prn=schedule.get("is_prn", False),
    )
    return {
        "medication_id": medication_id,
        "name": med.get("name"),
        "schedule": schedule,
        "safety": safety,
    }


@router.post("/log")
def log_medication(body: MedicationLogCreate, me: dict = Depends(current_user)):
    """
    記錄服藥（打卡）。

    所有藥都會檢查「同一顆藥距離上次服藥時間」：
      - 一般預設安全間隔 6 小時（DEFAULT_MIN_INTERVAL_HOURS）
      - 絕對底線 4 小時（ABSOLUTE_FLOOR_HOURS）：即使醫師寫「每 3 小時」也守住
      - PRN + 醫師明確指定 interval：信醫師（可低於 4，例：止痛藥 q2h prn）
    若 body.force == False 且未達安全間隔，回 409 dose_too_soon，
    前端 showDoseSafetyDialog 讓使用者按「我了解風險仍要記錄」才強制送出。

    跳過服藥（taken == False）不會被擋。
    寫入後若近 7 天服藥率 < 50% 自動建立 missed_medication 警示。
    """
    _enforce_self_patient(body.patient_id, me)
    sb = get_supabase()
    med = _assert_owns_medication(sb, body.medication_id, me)
    safety_payload: dict | None = None

    if body.taken:
        schedule = annotate_medication(med)
        # 所有藥（早/中/晚 + 其他 + PRN）都做同一顆藥的劑量間隔檢查：
        #   - 早/中/晚（沒有 interval_hours）：用 6 小時一般預設
        #   - 其他間隔藥：max(4, interval_hours)，守住 4 小時底線
        #   - PRN 有醫師指定 interval：用醫師指示（可 < 4）
        logs = _recent_logs(sb, body.patient_id, body.medication_id)
        safety = check_dose_safety(
            logs,
            interval_hours=schedule.get("interval_hours"),
            is_prn=schedule.get("is_prn", False),
        )
        safety_payload = safety
        if not safety["allowed"] and not body.force:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "dose_too_soon",
                    "message": safety["message"],
                    "safety": safety,
                    "schedule": schedule,
                    "min_hours": DEFAULT_MIN_INTERVAL_HOURS,
                },
            )

    data = {
        "patient_id": body.patient_id,
        "medication_id": body.medication_id,
        "taken": 1 if body.taken else 0,
        "taken_at": body.taken_at or datetime.utcnow().isoformat(),
        "skip_reason": body.skip_reason,
        "notes": body.notes,
    }
    result = sb.table("medication_logs").insert(data).execute()
    out = dict(result.data[0]) if result.data else {}
    if safety_payload is not None:
        out["safety"] = safety_payload

    # ── 自動警示：近 7 天打卡 >= 5 筆且服藥率 < 50% → missed_medication ──
    try:
        since = (datetime.utcnow() - timedelta(days=7)).isoformat()
        recent = (
            sb.table("medication_logs").select("taken")
            .eq("patient_id", body.patient_id).gte("taken_at", since)
            .execute().data or []
        )
        if len(recent) >= 5:
            taken = sum(1 for r in recent if r.get("taken"))
            rate = taken / len(recent)
            if rate < 0.5:
                day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
                existing = (
                    sb.table("alerts").select("id")
                    .eq("patient_id", body.patient_id)
                    .eq("alert_type", "missed_medication")
                    .eq("resolved", 0)
                    .gte("created_at", day_ago)
                    .limit(1).execute().data or []
                )
                if not existing:
                    sb.table("alerts").insert({
                        "patient_id": body.patient_id,
                        "alert_type": "missed_medication",
                        "severity": "high" if rate < 0.3 else "medium",
                        "title": f"服藥順從率偏低（近 7 天 {int(rate*100)}%）",
                        "detail": "建議下次回診詢問是否有副作用或忘記服藥的原因。",
                        "acknowledged": 0,
                        "resolved": 0,
                    }).execute()
    except Exception:
        pass

    return out


@router.get("/logs")
def get_medication_logs(
    patient_id: str = Query(...),
    medication_id: Optional[str] = Query(None),
    days: int = Query(30, description="查詢最近幾天"),
    me: dict = Depends(current_user),
):
    """取得服藥日誌"""
    pid = _enforce_self_patient(patient_id, me)
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    query = sb.table("medication_logs").select("*").eq("patient_id", pid).gte("taken_at", since).order("taken_at", desc=True)
    if medication_id:
        query = query.eq("medication_id", medication_id)
    result = query.execute()
    return {"logs": result.data, "days": days}


# ── 療效追蹤 ──────────────────────────────────────────────

@router.post("/effects")
def record_effect(body: EffectRecord, me: dict = Depends(current_user)):
    """記錄藥物療效與副作用"""
    _enforce_self_patient(body.patient_id, me)
    if body.effectiveness < 1 or body.effectiveness > 5:
        raise HTTPException(status_code=400, detail="effectiveness 必須在 1-5 之間")
    sb = get_supabase()
    _assert_owns_medication(sb, body.medication_id, me)
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
    me: dict = Depends(current_user),
):
    """取得療效紀錄"""
    pid = _enforce_self_patient(patient_id, me)
    sb = get_supabase()
    query = sb.table("medication_effects").select("*").eq("patient_id", pid).order("recorded_at", desc=True)
    if medication_id:
        query = query.eq("medication_id", medication_id)
    result = query.execute()
    return {"effects": result.data}


# ── 統計與圖表資料 ────────────────────────────────────────

def _compute_stats_data(sb, patient_id: str, days: int) -> dict:
    """純資料計算，已由呼叫者完成 auth check。"""
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


@router.get("/stats")
def medication_stats(
    patient_id: str = Query(...),
    days: int = Query(30),
    me: dict = Depends(current_user),
):
    """取得藥物管理統計：服藥率、療效趨勢、各藥物狀態。"""
    pid = _enforce_self_patient(patient_id, me)
    sb = get_supabase()
    return _compute_stats_data(sb, pid, days)


CHECK_IN_INTERVAL_DAYS = 3


@router.get("/check-in/due")
def check_in_due(
    patient_id: str = Query(...),
    interval_days: int = Query(CHECK_IN_INTERVAL_DAYS, ge=1, le=30),
    me: dict = Depends(current_user),
):
    """
    服藥追蹤提醒：每 interval_days（預設 3 天）至少問一次。

    回傳是否該觸發提醒、距離上次紀錄幾天、下次到期日。
    判斷依據：medication_logs 的 taken_at 與 medication_effects 的 recorded_at 取最新者。
    若該病患有開立藥物但從未紀錄，視為立即到期。
    """
    patient_id = _enforce_self_patient(patient_id, me)
    sb = get_supabase()

    meds = (
        sb.table("medications")
        .select("id, active")
        .eq("patient_id", patient_id)
        .execute()
        .data
        or []
    )
    has_active_med = any(m.get("active", 1) for m in meds)
    if not has_active_med:
        return {
            "due": False,
            "reason": "no_active_medication",
            "interval_days": interval_days,
            "last_check_in": None,
            "days_since_last": None,
            "next_due_at": None,
        }

    last_log = (
        sb.table("medication_logs")
        .select("taken_at")
        .eq("patient_id", patient_id)
        .order("taken_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    last_effect = (
        sb.table("medication_effects")
        .select("recorded_at")
        .eq("patient_id", patient_id)
        .order("recorded_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )

    candidates = []
    if last_log:
        candidates.append(last_log[0].get("taken_at"))
    if last_effect:
        candidates.append(last_effect[0].get("recorded_at"))
    candidates = [c for c in candidates if c]

    if not candidates:
        return {
            "due": True,
            "reason": "never_logged",
            "interval_days": interval_days,
            "last_check_in": None,
            "days_since_last": None,
            "next_due_at": datetime.utcnow().isoformat(),
            "message": "尚未填過服藥/療效紀錄，請完成首次回報。",
        }

    last_iso = max(candidates)
    try:
        last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        last_dt = datetime.utcnow() - timedelta(days=interval_days + 1)

    delta = datetime.utcnow() - last_dt
    days_since = round(delta.total_seconds() / 86400, 2)
    next_due = last_dt + timedelta(days=interval_days)
    due = datetime.utcnow() >= next_due

    return {
        "due": due,
        "reason": "interval_elapsed" if due else "within_interval",
        "interval_days": interval_days,
        "last_check_in": last_iso,
        "days_since_last": days_since,
        "next_due_at": next_due.isoformat(),
        "message": (
            f"距離上次紀錄已 {days_since} 天，請更新服藥/療效。"
            if due
            else f"下次請在 {next_due.date().isoformat()} 前再回報一次。"
        ),
    }


@router.get("/daily-improvement")
def daily_improvement(
    patient_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    me: dict = Depends(current_user),
):
    """
    每日用藥改善：把每天的服藥率與療效平均值合成 improvement_score，
    並計算與前一天的差值（delta），用於折線圖呈現病患每日的用藥改善程度。

    - improvement_score：服藥率（50%）+ 療效（50%, 1-5 → 0-100），缺一項則只用另一項。
    - 沒有任何資料的日期不會出現。
    - summary.trend：improving / declining / stable / insufficient_data。
    """
    patient_id = _enforce_self_patient(patient_id, me)
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("taken_at", since)
        .execute()
        .data
        or []
    )
    effects = (
        sb.table("medication_effects")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("recorded_at", since)
        .execute()
        .data
        or []
    )

    by_day: dict[str, dict] = {}
    for log in logs:
        day = (log.get("taken_at") or "")[:10]
        if not day:
            continue
        d = by_day.setdefault(day, {"taken": 0, "total": 0, "effects": []})
        d["total"] += 1
        if log.get("taken"):
            d["taken"] += 1
    for e in effects:
        day = (e.get("recorded_at") or "")[:10]
        if not day:
            continue
        score = e.get("effectiveness")
        if score is None:
            continue
        d = by_day.setdefault(day, {"taken": 0, "total": 0, "effects": []})
        d["effects"].append(score)

    daily = []
    prev_score: Optional[float] = None
    for day in sorted(by_day.keys()):
        d = by_day[day]
        adherence = round(d["taken"] / d["total"] * 100, 1) if d["total"] else None
        avg_eff = round(sum(d["effects"]) / len(d["effects"]), 2) if d["effects"] else None

        adherence_part = adherence  # 0-100 or None
        eff_part = (avg_eff / 5 * 100) if avg_eff is not None else None  # 0-100 or None
        parts = [p for p in (adherence_part, eff_part) if p is not None]
        if not parts:
            continue
        if adherence_part is not None and eff_part is not None:
            improvement_score = round(adherence_part * 0.5 + eff_part * 0.5, 1)
        else:
            improvement_score = round(parts[0], 1)

        delta = round(improvement_score - prev_score, 1) if prev_score is not None else None
        daily.append({
            "date": day,
            "adherence_rate": adherence,
            "taken": d["taken"],
            "total_doses": d["total"],
            "avg_effectiveness": avg_eff,
            "effect_records": len(d["effects"]),
            "improvement_score": improvement_score,
            "delta_vs_prev": delta,
        })
        prev_score = improvement_score

    if len(daily) >= 2:
        first, last = daily[0]["improvement_score"], daily[-1]["improvement_score"]
        diff = round(last - first, 1)
        if diff >= 5:
            trend = "improving"
        elif diff <= -5:
            trend = "declining"
        else:
            trend = "stable"
        summary = {
            "trend": trend,
            "first_score": first,
            "last_score": last,
            "overall_delta": diff,
        }
    else:
        summary = {
            "trend": "insufficient_data",
            "first_score": daily[0]["improvement_score"] if daily else None,
            "last_score": daily[0]["improvement_score"] if daily else None,
            "overall_delta": 0.0,
        }

    return {
        "patient_id": patient_id,
        "days": days,
        "daily": daily,
        "days_logged": len(daily),
        "summary": summary,
    }


# ── 回診報告 ──────────────────────────────────────────────

@router.get("/report")
def generate_report(
    patient_id: str = Query(...),
    days: int = Query(30, description="報告涵蓋天數"),
    me: dict = Depends(current_user),
):
    """
    產出回診藥物報告：統計數據 + AI 摘要
    供醫師參考藥物反應
    """
    pid = _enforce_self_patient(patient_id, me)
    sb = get_supabase()
    stats = _compute_stats_data(sb, pid, days)

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
