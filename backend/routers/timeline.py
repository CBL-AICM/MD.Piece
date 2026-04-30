"""
治療時間軸與跨回診比較 — 醫師端核心功能。

時間軸：將就診、用藥變更、症狀趨勢、療效對照整合在單一時間線上。
跨回診比較：本次 vs 上次的療效量化對照。
"""

import json
import logging
import statistics
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from backend.db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 治療時間軸 ───────────────────────────────────────────


@router.get("/{patient_id}")
def treatment_timeline(patient_id: str, days: int = Query(180)):
    """
    時間軸事件：就診、調藥、症狀峰值、情緒低谷、警示
    依時間排序回傳，前端依此繪製時間線。
    """
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    since_date = since[:10]

    events = []

    # 就診
    visits = (
        sb.table("medical_records")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("visit_date", since_date)
        .execute()
        .data
        or []
    )
    for v in visits:
        events.append({
            "type": "visit",
            "date": (v.get("visit_date") or v.get("created_at") or "")[:10],
            "title": "回診",
            "detail": v.get("diagnosis") or "未填診斷",
            "raw": v,
        })

    # 調藥
    changes = (
        sb.table("medication_changes")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("effective_date", since_date)
        .execute()
        .data
        or []
    )
    for c in changes:
        change_label = {
            "start": "開始用藥",
            "stop": "停藥",
            "dose_up": "加量",
            "dose_down": "減量",
            "switch": "換藥",
            "frequency": "頻率調整",
            "other": "其他調整",
        }.get(c.get("change_type"), c.get("change_type", "用藥變更"))
        events.append({
            "type": "medication_change",
            "date": (c.get("effective_date") or c.get("created_at") or "")[:10],
            "title": change_label,
            "detail": _format_med_change(c),
            "raw": c,
        })

    # 醫師備註
    notes = (
        sb.table("doctor_notes")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    for n in notes:
        events.append({
            "type": "doctor_note",
            "date": (n.get("created_at") or "")[:10],
            "title": "醫師備註",
            "detail": (n.get("content") or "")[:60],
            "next_focus": n.get("next_focus"),
            "raw": n,
        })

    # 警示
    alerts = (
        sb.table("alerts")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    for a in alerts:
        events.append({
            "type": "alert",
            "date": (a.get("created_at") or "")[:10],
            "title": a.get("title", "警示"),
            "detail": a.get("detail"),
            "severity": a.get("severity"),
            "raw": a,
        })

    events.sort(key=lambda e: e["date"], reverse=True)

    # 症狀嚴重度峰值（每日最大值）
    severity_series = _daily_severity_series(sb, patient_id, days)

    return {
        "patient_id": patient_id,
        "period_days": days,
        "events": events,
        "severity_trend": severity_series,
    }


def _format_med_change(c):
    bits = []
    if c.get("previous_dosage") and c.get("new_dosage"):
        bits.append(f"{c['previous_dosage']} → {c['new_dosage']}")
    if c.get("reason"):
        bits.append(f"原因：{c['reason']}")
    return "；".join(bits) or "—"


def _daily_severity_series(sb, patient_id, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = (
        sb.table("symptoms_log")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    daily: dict[str, list[float]] = {}
    for r in rows:
        day = (r.get("created_at") or "")[:10]
        ai = r.get("ai_response")
        if isinstance(ai, str):
            try:
                ai = json.loads(ai)
            except Exception:
                continue
        if isinstance(ai, dict):
            sev = ai.get("severity_index")
            if sev is not None:
                daily.setdefault(day, []).append(float(sev))
    series = [
        {"date": d, "severity": round(max(v), 1)} for d, v in sorted(daily.items())
    ]
    return series


# ── 跨回診比較 ───────────────────────────────────────────


@router.get("/{patient_id}/compare")
def compare_two_visits(patient_id: str):
    """
    比較最近兩次回診之間的變化：
    - 症狀嚴重度均值差
    - 情緒均值差
    - 服藥率差
    - 期間調藥次數
    """
    sb = get_supabase()
    visits = (
        sb.table("medical_records")
        .select("*")
        .eq("patient_id", patient_id)
        .order("visit_date", desc=True)
        .limit(2)
        .execute()
        .data
        or []
    )
    if len(visits) < 2:
        return {
            "patient_id": patient_id,
            "comparison": None,
            "message": "尚未有兩次以上的就診紀錄，無法跨回診比較",
        }

    current_visit, previous_visit = visits[0], visits[1]
    prev_date = (previous_visit.get("visit_date") or previous_visit.get("created_at"))[:10]
    curr_date = (current_visit.get("visit_date") or current_visit.get("created_at"))[:10]

    prev_metrics = _period_metrics(sb, patient_id, prev_date, curr_date)
    # 上一段：往前推 30 天作為對照（若無就診紀錄）
    earlier_anchor = (datetime.fromisoformat(prev_date) - timedelta(days=30)).isoformat()[:10]
    earlier_metrics = _period_metrics(sb, patient_id, earlier_anchor, prev_date)

    return {
        "patient_id": patient_id,
        "previous_visit": {"date": prev_date, "diagnosis": previous_visit.get("diagnosis")},
        "current_visit": {"date": curr_date, "diagnosis": current_visit.get("diagnosis")},
        "this_period": prev_metrics,  # 上次到本次之間
        "last_period": earlier_metrics,  # 上次之前 30 天
        "deltas": _compute_deltas(prev_metrics, earlier_metrics),
    }


def _period_metrics(sb, patient_id, start: str, end: str):
    sym = (
        sb.table("symptoms_log")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", start)
        .lte("created_at", end + "T23:59:59")
        .execute()
        .data
        or []
    )
    severities = []
    for r in sym:
        ai = r.get("ai_response")
        if isinstance(ai, str):
            try:
                ai = json.loads(ai)
            except Exception:
                continue
        if isinstance(ai, dict):
            sev = ai.get("severity_index")
            if sev is not None:
                severities.append(float(sev))

    emotions = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", start)
        .lte("created_at", end + "T23:59:59")
        .execute()
        .data
        or []
    )
    emotion_scores = [e.get("score") for e in emotions if e.get("score") is not None]

    med_logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("taken_at", start)
        .lte("taken_at", end + "T23:59:59")
        .execute()
        .data
        or []
    )
    total = len(med_logs)
    taken = sum(1 for m in med_logs if m.get("taken"))

    changes = (
        sb.table("medication_changes")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("effective_date", start)
        .lte("effective_date", end + "T23:59:59")
        .execute()
        .data
        or []
    )

    return {
        "start": start,
        "end": end,
        "severity_mean": round(statistics.mean(severities), 2) if severities else None,
        "severity_max": max(severities) if severities else None,
        "emotion_mean": round(statistics.mean(emotion_scores), 2) if emotion_scores else None,
        "adherence_rate": round(taken / total, 2) if total else None,
        "medication_changes": len(changes),
    }


def _compute_deltas(this_p, last_p):
    """簡單的 this - last 變化向量"""
    out = {}
    for key in ("severity_mean", "severity_max", "emotion_mean", "adherence_rate"):
        t = this_p.get(key)
        l = last_p.get(key)
        if t is None or l is None:
            out[key] = None
        else:
            out[key] = round(t - l, 2)
    return out
