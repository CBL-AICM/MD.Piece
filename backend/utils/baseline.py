"""
個人化基準線計算與比對工具。

設計原則：以患者前 14 天數據建立個人正常範圍，後續判斷以「偏離自身基準」為依據，
而非比對族群正常值。降低假陽性、避免過度警示。
"""

import json
import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# 連續惡化才升級警示，避免單次異常造成誤報
ESCALATION_DAYS = 3
EMOTION_LOW_DAYS = 5  # 情緒連續低落天數
MISSED_MED_DAYS = 2   # 連續漏藥天數


def calculate_baseline(records: list[dict]) -> dict:
    """
    以前兩週數據建立個人化基準線。
    records: [{"pain": 3, "medication_rate": 0.9, "emotion": 4}, ...]
    """
    if not records:
        return {}

    pain_scores = [r["pain"] for r in records if r.get("pain") is not None]
    emotion_scores = [r["emotion"] for r in records if r.get("emotion") is not None]
    med_rates = [r["medication_rate"] for r in records if r.get("medication_rate") is not None]

    return {
        "pain_mean": round(statistics.mean(pain_scores), 2) if pain_scores else None,
        "pain_stdev": round(statistics.stdev(pain_scores), 2) if len(pain_scores) > 1 else 0,
        "pain_max": max(pain_scores) if pain_scores else None,
        "emotion_mean": round(statistics.mean(emotion_scores), 2) if emotion_scores else None,
        "emotion_stdev": round(statistics.stdev(emotion_scores), 2) if len(emotion_scores) > 1 else 0,
        "medication_rate_mean": round(statistics.mean(med_rates), 2) if med_rates else None,
        "data_points": len(records),
    }


def build_baseline_from_db(sb, patient_id: str, days: int = 14) -> dict:
    """從資料庫拉資料、組成 records 並計算基準線"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    emotions = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    med_logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("taken_at", since)
        .execute()
        .data
        or []
    )
    sym_logs = (
        sb.table("symptoms_log")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )

    # 將 symptoms_log 的 ai_response 解析成嚴重度指數
    daily_pain: dict[str, list[float]] = {}
    daily_locations: dict[str, set[str]] = {}
    for r in sym_logs:
        day = (r.get("created_at") or "")[:10]
        if not day:
            continue
        ai = r.get("ai_response")
        if isinstance(ai, str):
            try:
                ai = json.loads(ai)
            except Exception:
                ai = None
        if not isinstance(ai, dict):
            continue
        sev = ai.get("severity_index")
        if sev is not None:
            daily_pain.setdefault(day, []).append(float(sev))
        for loc in ai.get("body_locations", []) or []:
            daily_locations.setdefault(day, set()).add(loc)

    # 將 emotions 與 med_logs 依日期聚合
    daily_emotion: dict[str, list[float]] = {}
    for e in emotions:
        day = (e.get("created_at") or "")[:10]
        if day and e.get("score") is not None:
            daily_emotion.setdefault(day, []).append(float(e["score"]))

    daily_med: dict[str, dict[str, int]] = {}
    for m in med_logs:
        day = (m.get("taken_at") or m.get("created_at") or "")[:10]
        if not day:
            continue
        slot = daily_med.setdefault(day, {"taken": 0, "total": 0})
        slot["total"] += 1
        if m.get("taken"):
            slot["taken"] += 1

    all_days = sorted(set(daily_pain) | set(daily_emotion) | set(daily_med))
    records = []
    for day in all_days:
        p = daily_pain.get(day, [])
        e = daily_emotion.get(day, [])
        m = daily_med.get(day)
        records.append({
            "date": day,
            "pain": max(p) if p else None,
            "emotion": statistics.mean(e) if e else None,
            "medication_rate": (m["taken"] / m["total"]) if m and m["total"] else None,
            "locations": list(daily_locations.get(day, set())),
        })

    baseline = calculate_baseline(records)

    # 分析症狀部位模式（識別新出現部位）
    location_freq: dict[str, int] = {}
    for r in records:
        for loc in r.get("locations", []):
            location_freq[loc] = location_freq.get(loc, 0) + 1
    baseline["known_locations"] = sorted(location_freq, key=location_freq.get, reverse=True)

    return {"baseline": baseline, "records": records}


def compare_to_baseline(today: dict, baseline: dict) -> dict:
    """
    比較今日數據 vs 個人基準線。
    回傳偏離指標供分流引擎使用。

    deviation_pain: 今日疼痛超過基準的幅度（標準差倍數）
    new_locations: 從未出現過的部位
    emotion_drop: 今日情緒比基準低多少
    """
    pain_today = today.get("pain")
    pain_mean = baseline.get("pain_mean")
    pain_std = baseline.get("pain_stdev") or 1
    deviation_pain = None
    if pain_today is not None and pain_mean is not None:
        deviation_pain = round((pain_today - pain_mean) / max(pain_std, 0.5), 2)

    today_locs = set(today.get("locations", []))
    known = set(baseline.get("known_locations", []))
    new_locations = list(today_locs - known)

    emotion_today = today.get("emotion")
    emotion_mean = baseline.get("emotion_mean")
    emotion_drop = None
    if emotion_today is not None and emotion_mean is not None:
        emotion_drop = round(emotion_mean - emotion_today, 2)

    return {
        "deviation_pain": deviation_pain,
        "new_locations": new_locations,
        "emotion_drop": emotion_drop,
        "has_baseline": baseline.get("data_points", 0) >= 3,
    }


def detect_consecutive_low_emotion(scores: list[float], threshold: float = 2) -> int:
    """偵測連續情緒低落天數（最大連續區間）"""
    longest = 0
    current = 0
    for s in scores:
        if s is not None and s <= threshold:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def detect_consecutive_missed(daily_med: list[dict]) -> int:
    """偵測連續漏藥天數（依時間排序，依 0% 服藥率連續判斷）"""
    longest = 0
    current = 0
    for d in daily_med:
        if d.get("rate", 1) == 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest
