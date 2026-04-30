"""
醫師端儀表板 — 患者優先序排列 + 回診前快速預覽卡片。

優先序規則：
- needs_immediate_attention：未處理急診/critical 警示、靜默守護 critical
- needs_attention：高/中等警示、連續惡化、新部位、靜默守護 warning
- stable：以上皆無
"""

import json
import logging
import statistics
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from backend.db import get_supabase
from backend.utils.baseline import build_baseline_from_db, compare_to_baseline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/priority")
def patient_priority(doctor_id: str | None = None):
    """
    依需要關注程度排序所有追蹤中的患者。
    回傳：[{patient, priority, reason, summary_card}]
    """
    sb = get_supabase()
    patients = sb.table("patients").select("*").execute().data or []

    ranked = []
    for p in patients:
        pid = p["id"]
        card = _build_priority_card(sb, p)
        ranked.append(card)

    # 排序：immediate > attention > stable，同層按警示數倒序
    order = {"needs_immediate_attention": 0, "needs_attention": 1, "stable": 2}
    ranked.sort(key=lambda x: (order.get(x["priority"], 3), -x["alerts_count"]))

    return {"patients": ranked, "total": len(ranked)}


@router.get("/preview/{patient_id}")
def pre_visit_preview(patient_id: str):
    """
    回診前快速預覽卡片：
    - 整體燈號
    - 本期重點摘要
    - 用藥順從性
    - 情緒概況
    - 上次備註提醒
    """
    sb = get_supabase()
    p_res = sb.table("patients").select("*").eq("id", patient_id).execute()
    if not p_res.data:
        raise HTTPException(status_code=404, detail="找不到患者")
    patient = p_res.data[0]

    card = _build_priority_card(sb, patient, include_full_card=True)

    # 上次備註
    notes = (
        sb.table("doctor_notes")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    last_note = notes[0] if notes else None

    return {
        **card,
        "last_note": last_note,
    }


def _build_priority_card(sb, patient: dict, include_full_card: bool = False) -> dict:
    pid = patient["id"]
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # 警示
    alerts = (
        sb.table("alerts")
        .select("*")
        .eq("patient_id", pid)
        .eq("resolved", 0)
        .execute()
        .data
        or []
    )
    critical_alerts = [a for a in alerts if a.get("severity") in ("critical", "high")]
    has_unack_emergency = any(
        a.get("alert_type") == "er_visit" and not a.get("acknowledged") for a in alerts
    )

    # 情緒
    emotions = (
        sb.table("emotions")
        .select("score,created_at")
        .eq("patient_id", pid)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    emo_scores = [e.get("score") for e in emotions if e.get("score") is not None]
    avg_emotion = round(statistics.mean(emo_scores), 1) if emo_scores else None
    consecutive_low = _consecutive_low_emotion(emotions)

    # 用藥順從
    med_logs = (
        sb.table("medication_logs")
        .select("taken,taken_at")
        .eq("patient_id", pid)
        .gte("taken_at", since)
        .execute()
        .data
        or []
    )
    adherence = (
        round(sum(1 for m in med_logs if m.get("taken")) / len(med_logs) * 100, 1)
        if med_logs
        else None
    )

    # 基準線比對 → 當日是否惡化
    baseline_data = build_baseline_from_db(sb, pid, days=14)
    baseline = baseline_data["baseline"]
    deviation = compare_to_baseline(
        {"pain": baseline.get("pain_max"), "emotion": avg_emotion, "locations": baseline.get("known_locations", [])},
        baseline,
    )

    # 判斷優先級
    priority, reason = _classify_priority(
        critical_alerts=len(critical_alerts),
        has_unack_emergency=has_unack_emergency,
        consecutive_low=consecutive_low,
        deviation=deviation,
        adherence=adherence,
    )

    card = {
        "patient_id": pid,
        "patient_name": patient.get("name"),
        "age": patient.get("age"),
        "icd10_codes": patient.get("icd10_codes") or [],
        "priority": priority,
        "reason": reason,
        "alerts_count": len(alerts),
        "critical_alerts_count": len(critical_alerts),
    }

    if include_full_card:
        card.update({
            "signal": _signal_from_priority(priority),
            "highlights": _build_highlights(deviation, adherence, consecutive_low, critical_alerts),
            "adherence": adherence,
            "emotion_avg": avg_emotion,
            "emotion_consecutive_low_days": consecutive_low,
            "baseline": baseline,
            "deviation": deviation,
        })

    return card


def _classify_priority(critical_alerts, has_unack_emergency, consecutive_low, deviation, adherence):
    if has_unack_emergency or critical_alerts >= 1:
        return "needs_immediate_attention", _format_reason(
            "存在未處理的高/critical 警示" if not has_unack_emergency else "未確認的急診警示",
        )
    triggers = []
    if consecutive_low >= 5:
        triggers.append(f"情緒連續低落 {consecutive_low} 天")
    if deviation.get("new_locations"):
        triggers.append(f"新症狀部位 {len(deviation['new_locations'])} 處")
    if adherence is not None and adherence < 70:
        triggers.append(f"服藥率 {adherence}%")
    if deviation.get("deviation_pain") and deviation["deviation_pain"] >= 1.5:
        triggers.append(f"嚴重度偏離 {deviation['deviation_pain']}σ")
    if triggers:
        return "needs_attention", "；".join(triggers)
    return "stable", "近期數據穩定"


def _format_reason(*reasons):
    return "；".join(r for r in reasons if r)


def _signal_from_priority(priority):
    return {
        "needs_immediate_attention": "red",
        "needs_attention": "yellow",
        "stable": "green",
    }.get(priority, "gray")


def _build_highlights(deviation, adherence, consecutive_low, critical_alerts):
    bits = []
    if critical_alerts:
        bits.append(f"高警示 {len(critical_alerts)} 筆待處理")
    if consecutive_low >= 5:
        bits.append(f"情緒連續 {consecutive_low} 天偏低")
    if adherence is not None:
        if adherence < 70:
            bits.append(f"服藥率 {adherence}%（偏低）")
        else:
            bits.append(f"服藥率 {adherence}%")
    if deviation.get("new_locations"):
        bits.append(f"新部位：{', '.join(deviation['new_locations'][:3])}")
    if deviation.get("deviation_pain") and deviation["deviation_pain"] >= 1:
        bits.append(f"症狀嚴重度上升 {deviation['deviation_pain']}σ")
    if not bits:
        bits.append("近期穩定")
    return bits


def _consecutive_low_emotion(emotions: list[dict]) -> int:
    """情緒連續低落天數（依日期排序）"""
    if not emotions:
        return 0
    sorted_e = sorted(emotions, key=lambda e: e.get("created_at", ""))
    longest = 0
    current = 0
    for e in sorted_e:
        if (e.get("score") or 5) <= 2:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest
