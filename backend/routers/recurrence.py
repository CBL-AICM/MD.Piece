"""復發風險 API

讀取患者歷史 → 規則引擎評估 → 回傳 JSON（給前端卡片）
+ 可選把 high/critical 結果寫進 alerts 表（沿用既有 alerts pipeline，
  自動觸發家屬通知 / 列表卡片，不另建通知系統）。

對應 CLAUDE.md：
- Rule 5（純規則）：分數計算交給 utils/recurrence_rules.py
- Rule 7（不混用 pattern）：寫入動作直接用 alerts 表，與 alerts.py 同管線
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.db import get_supabase
from backend.utils.recurrence_rules import assess_recurrence

logger = logging.getLogger(__name__)
router = APIRouter()

# 寫入 alerts 表時用的型別字串（同步於 alerts.py 的 VALID_TYPES）
ALERT_TYPE = "recurrence_risk"
# 同一患者在這個時間窗內若已有未 resolve 的 recurrence_risk alert，不重複寫
DEDUPE_HOURS = 24


def _load_patient_history(patient_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    """從 Supabase 拉患者的 symptoms_log / medication_logs / emotions。

    任一表讀取失敗都不擋整體流程，回空 list（讓引擎照樣可算其他面向）。
    """
    sb = get_supabase()

    def _safe(fetch, name):
        try:
            return fetch() or []
        except Exception as e:
            logger.warning(f"讀 {name} 失敗（不阻擋評估）: {e}")
            return []

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
    return symptoms, meds, emotions


@router.get("/{patient_id}")
def get_recurrence_assessment(patient_id: str):
    """讀取單一患者的復發風險評估（不寫入任何狀態）。

    前端可直接拿來顯示「復發風險卡片」。
    """
    symptoms, meds, emotions = _load_patient_history(patient_id)
    result = assess_recurrence(symptoms, meds, emotions)
    result["patient_id"] = patient_id
    return result


@router.post("/{patient_id}/snapshot")
def snapshot_recurrence(patient_id: str, min_level: str = Query("high")):
    """評估並把 level >= min_level 的結果寫進 alerts 表。

    - 預設 min_level=high：只有高風險才產生 alert，避免噪音。
    - 24h 內已有未 resolve 的同型別 alert 則跳過（dedupe）。
    - 回傳 {"assessment": {...}, "alert": {...} | None, "skipped_reason": str | None}
    """
    if min_level not in ("medium", "high", "critical"):
        raise HTTPException(status_code=400, detail="min_level 必須是 medium|high|critical")

    symptoms, meds, emotions = _load_patient_history(patient_id)
    assessment = assess_recurrence(symptoms, meds, emotions)
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

    top = assessment["clusters"][0] if assessment["clusters"] else None
    cluster_name = top["cluster"] if top else "症狀"
    alert_row = {
        "patient_id": patient_id,
        "alert_type": ALERT_TYPE,
        "severity": assessment["level"],
        "title": f"{cluster_name} 復發風險：{assessment['level']}",
        "detail": "；".join(assessment["reasons"]) or "依過去症狀紀錄評估為高風險",
        "metadata": {
            "score": assessment["score"],
            "cluster": cluster_name,
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
