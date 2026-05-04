from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging

from backend.db import get_supabase
from backend.services.llm_service import recognize_medicine_bag, call_claude
from backend.utils.medication_schedule import (
    DEFAULT_MIN_INTERVAL_HOURS,
    annotate_medication,
    check_dose_safety,
    parse_time_slots,
)

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
def get_medications(patient_id: str = Query(...)):
    """取得患者的所有藥物，附加服藥時段標籤（早 / 中 / 晚 / 其他）。"""
    sb = get_supabase()
    result = sb.table("medications").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()
    return {"medications": _augment_with_schedule(result.data or [])}


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
    try:
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
def can_take(patient_id: str = Query(...), medication_id: str = Query(...)):
    """
    檢查現在是否能服這顆藥（前端在打卡前 call，可預覽風險）。

    回傳 dose safety 結果（含 hours_since_last / required_hours / level / message）
    以及該藥物目前的 schedule（slots / interval_hours / is_other），
    讓前端決定要不要彈跳安全警告。
    """
    sb = get_supabase()
    med = _load_med(sb, medication_id)
    if not med:
        raise HTTPException(status_code=404, detail="找不到該藥物")
    schedule = annotate_medication(med)
    logs = _recent_logs(sb, patient_id, medication_id)
    safety = check_dose_safety(logs, interval_hours=schedule.get("interval_hours"))
    return {
        "medication_id": medication_id,
        "name": med.get("name"),
        "schedule": schedule,
        "safety": safety,
    }


@router.post("/log")
def log_medication(body: MedicationLogCreate):
    """
    記錄服藥（打卡）。

    對「其他」分類（每 X 小時 / PRN）的藥：服藥前會檢查最近一次打卡時間，
    若距離 < 安全間隔（預設 4 小時，或藥物標示的間隔較長者），
    且 body.force == False，會回 409 並附帶風險訊息，前端再決定要不要強制送出。

    跳過服藥（taken == False）或固定時段藥（早 / 中 / 晚）不會被擋。
    """
    sb = get_supabase()
    safety_payload: dict | None = None

    if body.taken:
        med = _load_med(sb, body.medication_id)
        if not med:
            raise HTTPException(status_code=404, detail="找不到該藥物")
        schedule = annotate_medication(med)
        # 只對「其他」分類強制安全檢查（每 X 小時 / PRN 才會有過量風險）；
        # 早 / 中 / 晚 是固定時段，醫師指定怎麼吃就怎麼吃，不要擋。
        if schedule.get("is_other"):
            logs = _recent_logs(sb, body.patient_id, body.medication_id)
            safety = check_dose_safety(logs, interval_hours=schedule.get("interval_hours"))
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
    return out


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
