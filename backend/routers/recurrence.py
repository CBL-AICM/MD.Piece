"""復發風險 API（疾病導向）

讀患者 patient_profiles 的「登入疾病」+ 日常 symptoms_log / medication_logs /
emotions → 規則引擎評估 → 回 JSON 給前端；可選把高風險寫進既有 alerts 表
（不另建通知系統，Rule 7）。
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.db import get_supabase
from backend.utils.recurrence_rules import assess_recurrence

logger = logging.getLogger(__name__)
router = APIRouter()

ALERT_TYPE = "recurrence_risk"
DEDUPE_HOURS = 24


def _safe(fetch, name: str):
    try:
        return fetch() or []
    except Exception as e:
        logger.warning(f"讀 {name} 失敗（不阻擋評估）: {e}")
        return []


def _load_patient_history(patient_id: str) -> dict:
    """從 Supabase 一次拉齊評估所需的所有資料。

    Returns: {
      symptoms: [...], medications: [...], emotions: [...],
      current_disease: str | None, conditions: str | None,
    }
    任一表錯不擋整體流程。
    """
    sb = get_supabase()

    symptoms = _safe(
        lambda: sb.table("symptoms_log").select("*").eq("patient_id", patient_id).execute().data,
        "symptoms_log",
    )
    meds = _safe(
        lambda: sb.table("medication_logs").select("taken_at").eq("patient_id", patient_id).execute().data,
        "medication_logs",
    )
    emotions = _safe(
        lambda: sb.table("emotions").select("*").eq("patient_id", patient_id).execute().data,
        "emotions",
    )
    # patient_profiles 的 PK 是 user_id（= patient_id 對於登入用戶；demo 模式下也共用）
    profile_rows = _safe(
        lambda: sb.table("patient_profiles").select("current_disease, conditions")
        .eq("user_id", patient_id).execute().data,
        "patient_profiles",
    )
    profile = profile_rows[0] if profile_rows else {}

    return {
        "symptoms": symptoms,
        "medications": meds,
        "emotions": emotions,
        "current_disease": profile.get("current_disease"),
        "conditions": profile.get("conditions"),
    }


@router.get("/{patient_id}")
def get_recurrence_assessment(patient_id: str):
    """讀取單一患者的復發風險評估（不寫入任何狀態）。"""
    h = _load_patient_history(patient_id)
    result = assess_recurrence(
        symptom_logs=h["symptoms"],
        medication_logs=h["medications"],
        emotion_logs=h["emotions"],
        current_disease=h["current_disease"],
        conditions=h["conditions"],
    )
    result["patient_id"] = patient_id
    return result


@router.post("/{patient_id}/snapshot")
def snapshot_recurrence(patient_id: str, min_level: str = Query("high")):
    """評估並把 level >= min_level 的結果寫進 alerts 表。

    - 24h 內已有未 resolve 的同型別 alert 則跳過（dedupe）
    - 回 {"assessment": ..., "alert": ... | None, "skipped_reason": ... | None}
    """
    if min_level not in ("medium", "high", "critical"):
        raise HTTPException(status_code=400, detail="min_level 必須是 medium|high|critical")

    h = _load_patient_history(patient_id)
    assessment = assess_recurrence(
        symptom_logs=h["symptoms"],
        medication_logs=h["medications"],
        emotion_logs=h["emotions"],
        current_disease=h["current_disease"],
        conditions=h["conditions"],
    )
    assessment["patient_id"] = patient_id

    level_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    if level_order[assessment["level"]] < level_order[min_level]:
        return {
            "assessment": assessment,
            "alert": None,
            "skipped_reason": f"level={assessment['level']} 未達 {min_level}",
        }

    sb = get_supabase()
    dedupe_iso = (datetime.now(timezone.utc) - timedelta(hours=DEDUPE_HOURS)).isoformat()
    try:
        existing = (
            sb.table("alerts").select("id, resolved")
            .eq("patient_id", patient_id).eq("alert_type", ALERT_TYPE)
            .gte("created_at", dedupe_iso).execute().data or []
        )
    except Exception as e:
        logger.warning(f"查 dedupe alerts 失敗（照常寫入）: {e}")
        existing = []
    if any(not a.get("resolved") for a in existing):
        return {
            "assessment": assessment,
            "alert": None,
            "skipped_reason": f"{DEDUPE_HOURS}h 內已有未處理的同型別 alert",
        }

    top = assessment["diseases"][0] if assessment["diseases"] else None
    disease_name = top["name"] if top else "症狀"
    alert_row = {
        "patient_id": patient_id,
        "alert_type": ALERT_TYPE,
        "severity": assessment["level"],
        "title": f"{disease_name} 復發風險：{assessment['level']}",
        "detail": "；".join(top["reasons"]) if top else "依過去紀錄評估為高風險",
        "metadata": {
            "score": assessment["score"],
            "top_disease": disease_name,
            "source": top["source"] if top else None,
            "data_summary": assessment["data_summary"],
        },
        "source": "recurrence_engine",
    }
    try:
        inserted = sb.table("alerts").insert(alert_row).execute().data
        created = inserted[0] if inserted else None
    except Exception as e:
        logger.error(f"寫入 alerts 失敗: {e}")
        raise HTTPException(status_code=500, detail=f"寫入 alerts 失敗: {e}")

    return {"assessment": assessment, "alert": created, "skipped_reason": None}
