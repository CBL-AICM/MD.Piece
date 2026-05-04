from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
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
    try:
        recognition = recognize_medicine_bag(body.image_base64, body.media_type)
    except Exception as e:
        logger.error(f"recognize_medicine_bag failed: {e}")
        raise HTTPException(status_code=500, detail=f"影像辨識服務失敗：{e}")

    meds = recognition.get("medications", []) or []
    raw_text = recognition.get("raw_text", "")

    if not meds:
        return {
            "recognized": 0,
            "medications": [],
            "parsed": [],
            "raw_text": raw_text,
            "message": "無法辨識藥袋內容，請嘗試拍攝更清晰的照片，或手動填寫下方資料。",
            "errors": [],
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


@router.get("/daily-improvement")
def daily_improvement(
    patient_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
):
    """
    每日用藥改善：把每天的服藥率與療效平均值合成 improvement_score，
    並計算與前一天的差值（delta），用於折線圖呈現病患每日的用藥改善程度。

    - improvement_score：服藥率（50%）+ 療效（50%, 1-5 → 0-100），缺一項則只用另一項。
    - 沒有任何資料的日期不會出現。
    - summary.trend：improving / declining / stable / insufficient_data。
    """
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
