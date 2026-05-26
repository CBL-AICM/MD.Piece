"""復發風險規則引擎

純規則式（不走 LLM），依患者歷史 symptoms_log / medication_logs / emotions
算出復發風險分數與原因。對外只暴露 `assess_recurrence`。

對應 CLAUDE.md Rule 5：確定性任務由純程式碼處理。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Iterable


# ─── 症狀同義詞 → canonical cluster ───────────────────────────
# MVP：手寫常見聚類，足以覆蓋 symptoms.py 既有 SYMPTOM_ADVICE 與多數中文輸入。
# 未涵蓋的症狀字串會以「原字串小寫去空白」自成一類。
_SYNONYMS: dict[str, str] = {
    # 頭痛
    "頭痛": "頭痛", "偏頭痛": "頭痛", "headache": "頭痛", "migraine": "頭痛",
    # 發燒
    "發燒": "發燒", "發熱": "發燒", "fever": "發燒",
    # 咳嗽
    "咳嗽": "咳嗽", "cough": "咳嗽",
    # 胸痛
    "胸痛": "胸痛", "胸悶": "胸痛", "chest pain": "胸痛",
    # 喉嚨痛
    "喉嚨痛": "喉嚨痛", "sore throat": "喉嚨痛",
    # 噁心 / 嘔吐
    "噁心": "噁心嘔吐", "嘔吐": "噁心嘔吐", "nausea": "噁心嘔吐", "vomit": "噁心嘔吐",
    # 暈眩
    "暈眩": "暈眩", "頭暈": "暈眩", "dizziness": "暈眩",
    # 疲倦
    "疲倦": "疲倦", "疲勞": "疲倦", "fatigue": "疲倦",
    # 腹痛 / 胃痛
    "胃痛": "腹痛", "腹痛": "腹痛", "stomach pain": "腹痛", "abdominal pain": "腹痛",
    # 呼吸困難
    "呼吸困難": "呼吸困難", "喘": "呼吸困難", "shortness of breath": "呼吸困難",
    # 失眠
    "失眠": "失眠", "睡不著": "失眠", "insomnia": "失眠",
    # 焦慮 / 憂鬱
    "焦慮": "焦慮", "anxiety": "焦慮",
    "憂鬱": "憂鬱", "情緒低落": "憂鬱", "depression": "憂鬱",
}


def normalize_symptom(raw: str) -> str:
    """單一症狀字串 → canonical cluster 名稱。"""
    if not raw:
        return ""
    key = raw.strip().lower()
    if key in _SYNONYMS:
        return _SYNONYMS[key]
    # 中文 key 已經是 lower-noop；英文 key 才會差。再試一次原字串。
    if raw.strip() in _SYNONYMS:
        return _SYNONYMS[raw.strip()]
    return raw.strip()


# ─── 時間工具 ────────────────────────────────────────────────

def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _days_between(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 86400.0


# ─── 主入口 ──────────────────────────────────────────────────

# 分數權重（單位 = points，總分 0-100 封頂）
_W_FREQ_90D_GTE_3 = 20
_W_FREQ_90D_GTE_5 = 15      # 與上者疊加 → 5 次以上 = 35 分
_W_FREQ_30D_GTE_2 = 15
_W_ACCELERATION = 25        # last_interval < avg * 0.8
_W_SEVERITY_RISING = 20     # 最近 3 筆 severity 單調上升
_W_MED_MISSED = 15          # 14 天內無服藥紀錄
_W_EMOTION_LOW = 10         # 14 天內 emotions 平均 <= 2

_LEVEL_BANDS = [
    (70, "critical"),
    (45, "high"),
    (20, "medium"),
]


def _level_from_score(score: int) -> str:
    for threshold, level in _LEVEL_BANDS:
        if score >= threshold:
            return level
    return "low"


def _extract_severity(entry: dict) -> int | None:
    """從 symptoms_log 一筆紀錄盡力取出 severity（0-10）。

    schema 沒寫死 severity 欄位，所以 fallback 順序：
      1) entry['severity']                    （未來若加欄位）
      2) entry['ai_response']['severity']     （AI 回傳）
      3) entry['ai_response']['urgency']      （另一種命名）
    取不到回 None，該筆不參與 severity_trend 計算。
    """
    if entry.get("severity") is not None:
        try:
            return int(entry["severity"])
        except (TypeError, ValueError):
            pass
    ai = entry.get("ai_response") or {}
    if isinstance(ai, dict):
        for k in ("severity", "urgency", "risk_score"):
            v = ai.get(k)
            if isinstance(v, (int, float)):
                return int(v)
    return None


def _cluster_symptoms(logs: Iterable[dict]) -> dict[str, list[dict]]:
    """把 symptoms_log 攤平成 {cluster_name: [log_entry_with_cluster, ...]}。

    同一 log 若涵蓋多種症狀，會被掛到多個 cluster（這是想要的：頭痛+發燒 兩條線都算）。
    """
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for log in logs:
        raw_symptoms = log.get("symptoms") or []
        if isinstance(raw_symptoms, str):
            raw_symptoms = [raw_symptoms]
        seen_clusters_in_log: set[str] = set()
        for s in raw_symptoms:
            cluster = normalize_symptom(str(s))
            if not cluster or cluster in seen_clusters_in_log:
                continue
            seen_clusters_in_log.add(cluster)
            by_cluster[cluster].append(log)
    return by_cluster


def _score_cluster(
    cluster: str,
    entries: list[dict],
    now: datetime,
    missed_med_days: float | None,
    low_emotion: bool,
) -> dict:
    """計算單一症狀聚類的風險分數。"""
    reasons: list[str] = []
    score = 0

    # 按時間排序（早 → 晚）
    timed = []
    for e in entries:
        dt = _parse_iso(e.get("created_at"))
        if dt:
            timed.append((dt, e))
    timed.sort(key=lambda x: x[0])

    iso_90d = now - timedelta(days=90)
    iso_30d = now - timedelta(days=30)
    count_90d = sum(1 for dt, _ in timed if dt >= iso_90d)
    count_30d = sum(1 for dt, _ in timed if dt >= iso_30d)

    if count_90d >= 3:
        score += _W_FREQ_90D_GTE_3
        reasons.append(f"過去 90 天「{cluster}」發作 {count_90d} 次")
    if count_90d >= 5:
        score += _W_FREQ_90D_GTE_5
    if count_30d >= 2:
        score += _W_FREQ_30D_GTE_2
        reasons.append(f"過去 30 天內「{cluster}」已發作 {count_30d} 次")

    # 加速：last_interval < avg_interval * 0.8
    avg_interval = None
    last_interval = None
    if len(timed) >= 3:
        intervals = [
            _days_between(timed[i][0], timed[i - 1][0])
            for i in range(1, len(timed))
        ]
        prior_intervals = intervals[:-1]
        last_interval = intervals[-1]
        if prior_intervals:
            avg_interval = mean(prior_intervals)
            if avg_interval > 0 and last_interval < avg_interval * 0.8:
                score += _W_ACCELERATION
                reasons.append(
                    f"間隔縮短（上次 {last_interval:.1f} 天 vs 平均 {avg_interval:.1f} 天）"
                )

    # severity 上升
    sev_trend = None
    if len(timed) >= 3:
        recent_sevs = [_extract_severity(e) for _, e in timed[-3:]]
        if all(s is not None for s in recent_sevs):
            if recent_sevs[0] < recent_sevs[1] < recent_sevs[2]:
                sev_trend = "rising"
                score += _W_SEVERITY_RISING
                reasons.append(
                    f"嚴重度逐次上升（{recent_sevs[0]}→{recent_sevs[1]}→{recent_sevs[2]}）"
                )
            elif recent_sevs[0] > recent_sevs[1] > recent_sevs[2]:
                sev_trend = "falling"
            else:
                sev_trend = "stable"

    # 跨域：服藥中斷 + 情緒低落（共用同一個 score budget，每位患者只加一次）
    if missed_med_days is not None and missed_med_days >= 14:
        score += _W_MED_MISSED
        reasons.append(f"已 {missed_med_days:.0f} 天未回報服藥")
    if low_emotion:
        score += _W_EMOTION_LOW
        reasons.append("近 14 天情緒紀錄偏低")

    score = min(score, 100)

    return {
        "cluster": cluster,
        "count_30d": count_30d,
        "count_90d": count_90d,
        "avg_interval_days": round(avg_interval, 1) if avg_interval else None,
        "last_interval_days": round(last_interval, 1) if last_interval else None,
        "severity_trend": sev_trend,
        "score": score,
        "level": _level_from_score(score),
        "reasons": reasons,
    }


def _missed_med_days(med_logs: Iterable[dict], now: datetime) -> float | None:
    """距離上次 medication_logs.taken_at 多少天；無紀錄回 None。"""
    latest = None
    for m in med_logs:
        dt = _parse_iso(m.get("taken_at"))
        if dt and (latest is None or dt > latest):
            latest = dt
    if latest is None:
        return None
    return _days_between(now, latest)


def _emotion_low(emotion_logs: Iterable[dict], now: datetime) -> bool:
    """近 14 天 emotions 平均 <= 2（假設 1-5 量表）；資料不足回 False。"""
    cutoff = now - timedelta(days=14)
    scores: list[int] = []
    for e in emotion_logs:
        dt = _parse_iso(e.get("recorded_at") or e.get("created_at"))
        if not dt or dt < cutoff:
            continue
        v = e.get("score") or e.get("mood_score") or e.get("level")
        if isinstance(v, (int, float)):
            scores.append(int(v))
    if len(scores) < 3:
        return False
    return mean(scores) <= 2


def assess_recurrence(
    symptom_logs: list[dict],
    medication_logs: list[dict] | None = None,
    emotion_logs: list[dict] | None = None,
    now: datetime | None = None,
) -> dict:
    """主入口：算出整個患者的復發風險。

    Args:
        symptom_logs: symptoms_log 全部紀錄，每筆需有 created_at + symptoms。
        medication_logs: medication_logs（可選），用來判斷漏服。
        emotion_logs: emotions（可選），用來判斷情緒低落加分。
        now: 注入時間方便測試，預設 UTC now。

    Returns:
        {
          "level": "low|medium|high|critical",
          "score": int,            # 全患者最高 cluster 分數
          "clusters": [ ... ],     # 每個 cluster 的詳細
          "reasons": [str],        # 取自最高分 cluster
          "assessed_at": iso str,
          "data_summary": {...}    # 用了多少筆資料，方便除錯
        }
    """
    now = now or datetime.now(timezone.utc)
    medication_logs = medication_logs or []
    emotion_logs = emotion_logs or []

    missed_med = _missed_med_days(medication_logs, now)
    low_emotion = _emotion_low(emotion_logs, now)

    clustered = _cluster_symptoms(symptom_logs or [])
    cluster_results = [
        _score_cluster(c, entries, now, missed_med, low_emotion)
        for c, entries in clustered.items()
    ]
    # 依分數高 → 低排序
    cluster_results.sort(key=lambda x: x["score"], reverse=True)

    top_score = cluster_results[0]["score"] if cluster_results else 0
    top_reasons = cluster_results[0]["reasons"] if cluster_results else []
    top_level = _level_from_score(top_score)

    return {
        "level": top_level,
        "score": top_score,
        "clusters": cluster_results,
        "reasons": top_reasons,
        "assessed_at": now.isoformat(),
        "data_summary": {
            "symptom_logs": len(symptom_logs or []),
            "medication_logs": len(medication_logs),
            "emotion_logs": len(emotion_logs),
            "missed_med_days": missed_med,
            "low_emotion_14d": low_emotion,
        },
    }
