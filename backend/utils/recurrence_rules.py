"""復發風險規則引擎（疾病導向）

主流程：
  1. 從 patient_profiles 拉到患者「登入的疾病」（current_disease + conditions）
  2. 對每個能對到 DISEASE_CATALOG 的疾病，套用該病專屬的閾值規則
  3. 對沒對照的疾病字串 → 提示「不在規則庫」
  4. 額外把日常 symptom log 的高頻症狀以 fallback 聚類補上一條（防止漏看）

純規則式，不走 LLM（CLAUDE.md Rule 5）。
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Iterable


# ─── 症狀同義詞 normalize（給 fallback 路徑與 disease 對症狀比對共用） ──
_SYMPTOM_SYNONYMS: dict[str, str] = {
    # 頭痛
    "頭痛": "頭痛", "偏頭痛": "頭痛", "headache": "頭痛", "migraine": "頭痛",
    # 發燒
    "發燒": "發燒", "發熱": "發燒", "fever": "發燒",
    # 咳嗽
    "咳嗽": "咳嗽", "cough": "咳嗽", "夜咳": "咳嗽",
    # 胸痛
    "胸痛": "胸痛", "胸悶": "胸痛", "chest pain": "胸痛",
    # 喉嚨痛
    "喉嚨痛": "喉嚨痛", "sore throat": "喉嚨痛",
    # 噁心嘔吐
    "噁心": "噁心嘔吐", "嘔吐": "噁心嘔吐", "nausea": "噁心嘔吐", "vomit": "噁心嘔吐",
    # 暈眩
    "暈眩": "暈眩", "頭暈": "暈眩", "dizziness": "暈眩",
    # 疲倦
    "疲倦": "疲倦", "疲勞": "疲倦", "fatigue": "疲倦",
    # 腹痛
    "胃痛": "腹痛", "腹痛": "腹痛", "stomach pain": "腹痛", "abdominal pain": "腹痛",
    "腹瀉": "腹痛", "便秘": "腹痛", "腹脹": "腹痛",
    # 呼吸困難
    "呼吸困難": "呼吸困難", "喘": "呼吸困難", "喘鳴": "呼吸困難",
    "shortness of breath": "呼吸困難",
    # 失眠
    "失眠": "失眠", "睡不著": "失眠", "insomnia": "失眠",
    # 焦慮 / 憂鬱
    "焦慮": "焦慮", "anxiety": "焦慮", "心悸": "焦慮", "恐慌": "焦慮",
    "憂鬱": "憂鬱", "情緒低落": "憂鬱", "depression": "憂鬱", "想哭": "憂鬱",
    # 過敏症狀
    "鼻塞": "鼻過敏", "流鼻水": "鼻過敏", "打噴嚏": "鼻過敏", "鼻癢": "鼻過敏",
    # 痛風相關
    "關節痛": "關節痛", "紅腫": "關節痛", "腳趾痛": "關節痛",
}


def normalize_symptom(raw: str) -> str:
    """單一症狀字串 → canonical cluster 名稱。"""
    if not raw:
        return ""
    key = raw.strip().lower()
    return _SYMPTOM_SYNONYMS.get(key) or _SYMPTOM_SYNONYMS.get(raw.strip()) or raw.strip()


# ─── 疾病對照表 ──────────────────────────────────────────────
# 設計原則：
#   - 「發作型」（attack）：看症狀頻率 + 加速 + 嚴重度上升
#   - 「精神型」（mental）：主要看情緒分數，症狀為輔
#   - 閾值因病而異（氣喘 30 天 2 次就警示，過敏性鼻炎要 3 次才警示）

DISEASE_CATALOG: dict[str, dict] = {
    "氣喘": {
        "aliases": ["asthma", "哮喘"],
        "type": "attack",
        "relevant_clusters": {"咳嗽", "呼吸困難"},
        "thresholds": {
            "count_30d_warn": 2, "count_30d_high": 4,
            "count_90d_warn": 4, "count_90d_high": 8,
        },
    },
    "偏頭痛": {
        "aliases": ["migraine", "頭痛", "headache"],
        "type": "attack",
        "relevant_clusters": {"頭痛"},
        "thresholds": {
            "count_30d_warn": 2, "count_30d_high": 4,
            "count_90d_warn": 4, "count_90d_high": 8,
        },
    },
    "腸躁症": {
        "aliases": ["ibs", "IBS", "大腸激躁症"],
        "type": "attack",
        "relevant_clusters": {"腹痛", "噁心嘔吐"},
        "thresholds": {
            "count_30d_warn": 3, "count_30d_high": 6,
            "count_90d_warn": 6, "count_90d_high": 12,
        },
    },
    "痛風": {
        "aliases": ["gout"],
        "type": "attack",
        "relevant_clusters": {"關節痛"},
        "thresholds": {
            "count_30d_warn": 1, "count_30d_high": 2,
            "count_90d_warn": 2, "count_90d_high": 4,
        },
    },
    "過敏性鼻炎": {
        "aliases": ["allergic rhinitis", "鼻過敏", "過敏性鼻炎"],
        "type": "attack",
        "relevant_clusters": {"鼻過敏", "咳嗽"},
        "thresholds": {
            "count_30d_warn": 3, "count_30d_high": 7,
            "count_90d_warn": 6, "count_90d_high": 14,
        },
    },
    "憂鬱症": {
        "aliases": ["depression", "重鬱症", "MDD", "mdd"],
        "type": "mental",
        "relevant_clusters": {"憂鬱", "失眠", "疲倦"},
        "thresholds": {
            "emotion_low_streak_days_warn": 5,
            "emotion_low_streak_days_high": 10,
            "emotion_avg_threshold": 2,  # 1-5 量表，平均 ≤2 視為低
        },
    },
    "焦慮症": {
        "aliases": ["anxiety", "GAD", "gad", "panic", "恐慌症", "廣泛性焦慮"],
        "type": "mental",
        "relevant_clusters": {"焦慮", "失眠"},
        "thresholds": {
            "emotion_low_streak_days_warn": 3,
            "emotion_low_streak_days_high": 7,
            "emotion_avg_threshold": 2,
        },
    },
}

# 反向索引：別名 → canonical disease key
_DISEASE_ALIAS_INDEX: dict[str, str] = {}
for _canonical, _meta in DISEASE_CATALOG.items():
    _DISEASE_ALIAS_INDEX[_canonical.lower()] = _canonical
    for _alias in _meta["aliases"]:
        _DISEASE_ALIAS_INDEX[_alias.lower()] = _canonical


def match_disease(raw: str) -> str | None:
    """患者填的疾病字串 → DISEASE_CATALOG canonical key；對不到回 None。

    用「子字串包含」放寬比對（讓「重度憂鬱症」也能對到「憂鬱症」）。
    """
    if not raw:
        return None
    needle = raw.strip().lower()
    if not needle:
        return None
    if needle in _DISEASE_ALIAS_INDEX:
        return _DISEASE_ALIAS_INDEX[needle]
    for alias, canonical in _DISEASE_ALIAS_INDEX.items():
        if alias in needle:
            return canonical
    return None


def split_patient_diseases(current_disease: str | None, conditions: str | None) -> list[str]:
    """從 patient_profiles.current_disease + conditions 拆出疾病字串陣列。

    支援分隔符：英文逗號、中文逗號「，」、「、」、分號、換行。
    去重保留順序。
    """
    raw_chunks: list[str] = []
    for src in (current_disease, conditions):
        if not src:
            continue
        for chunk in re.split(r"[,，、;；\n]+", src):
            chunk = chunk.strip()
            if chunk:
                raw_chunks.append(chunk)
    seen = set()
    out: list[str] = []
    for c in raw_chunks:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


# ─── 時間 / parsing 工具 ───────────────────────────────────

def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _days_between(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 86400.0


def _extract_severity(entry: dict) -> int | None:
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


# ─── Level / score 共用 ───────────────────────────────────

_LEVEL_BANDS = [(70, "critical"), (45, "high"), (20, "medium")]


def _level_from_score(score: int) -> str:
    for threshold, level in _LEVEL_BANDS:
        if score >= threshold:
            return level
    return "low"


_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# ─── 規則：發作型疾病 ──────────────────────────────────────

def _attack_logs_for_disease(
    canonical: str,
    relevant_clusters: set[str],
    symptom_logs: list[dict],
) -> list[tuple[datetime, dict]]:
    """挑出「跟這個疾病有關」的 symptom log 條目（去重，含時間）。"""
    picked: list[tuple[datetime, dict]] = []
    for log in symptom_logs or []:
        dt = _parse_iso(log.get("created_at"))
        if not dt:
            continue
        raw_symptoms = log.get("symptoms") or []
        if isinstance(raw_symptoms, str):
            raw_symptoms = [raw_symptoms]
        # 命中任一相關 cluster 即算這次發作
        for s in raw_symptoms:
            if normalize_symptom(str(s)) in relevant_clusters:
                picked.append((dt, log))
                break
    picked.sort(key=lambda x: x[0])
    return picked


def _score_attack_disease(
    canonical: str,
    meta: dict,
    symptom_logs: list[dict],
    now: datetime,
    missed_med_days: float | None,
) -> dict:
    """發作型疾病的 per-disease 分數計算。"""
    thr = meta["thresholds"]
    relevant = meta["relevant_clusters"]
    timed = _attack_logs_for_disease(canonical, relevant, symptom_logs)

    iso_90d = now - timedelta(days=90)
    iso_30d = now - timedelta(days=30)
    count_30d = sum(1 for dt, _ in timed if dt >= iso_30d)
    count_90d = sum(1 for dt, _ in timed if dt >= iso_90d)

    reasons: list[str] = []
    score = 0

    if count_30d >= thr["count_30d_high"]:
        score += 35
        reasons.append(f"過去 30 天「{canonical}」相關症狀發作 {count_30d} 次（高頻）")
    elif count_30d >= thr["count_30d_warn"]:
        score += 20
        reasons.append(f"過去 30 天「{canonical}」相關症狀發作 {count_30d} 次")

    if count_90d >= thr["count_90d_high"]:
        score += 15
    elif count_90d >= thr["count_90d_warn"]:
        score += 10
        reasons.append(f"過去 90 天累計 {count_90d} 次")

    # 加速
    avg_interval = last_interval = None
    if len(timed) >= 3:
        intervals = [
            _days_between(timed[i][0], timed[i - 1][0])
            for i in range(1, len(timed))
        ]
        prior = intervals[:-1]
        last_interval = intervals[-1]
        if prior:
            avg_interval = mean(prior)
            if avg_interval > 0 and last_interval < avg_interval * 0.8:
                score += 25
                reasons.append(
                    f"發作間隔縮短（上次 {last_interval:.1f} 天 vs 平均 {avg_interval:.1f} 天）"
                )

    # 嚴重度上升
    sev_trend = None
    if len(timed) >= 3:
        recent_sevs = [_extract_severity(e) for _, e in timed[-3:]]
        if all(s is not None for s in recent_sevs):
            if recent_sevs[0] < recent_sevs[1] < recent_sevs[2]:
                sev_trend = "rising"
                score += 20
                reasons.append(
                    f"嚴重度逐次上升（{recent_sevs[0]}→{recent_sevs[1]}→{recent_sevs[2]}）"
                )
            elif recent_sevs[0] > recent_sevs[1] > recent_sevs[2]:
                sev_trend = "falling"
            else:
                sev_trend = "stable"

    # 服藥中斷加分（控制不住 → 容易復發）
    if missed_med_days is not None and missed_med_days >= 14:
        score += 15
        reasons.append(f"已 {missed_med_days:.0f} 天未回報服藥")

    score = min(score, 100)
    return {
        "name": canonical,
        "source": "registered",
        "type": "attack",
        "level": _level_from_score(score),
        "score": score,
        "reasons": reasons,
        "evidence": {
            "count_30d": count_30d,
            "count_90d": count_90d,
            "avg_interval_days": round(avg_interval, 1) if avg_interval else None,
            "last_interval_days": round(last_interval, 1) if last_interval else None,
            "severity_trend": sev_trend,
        },
    }


# ─── 規則：精神類疾病 ─────────────────────────────────────

def _emotion_streak_below(
    emotion_logs: list[dict],
    threshold: int,
    now: datetime,
) -> tuple[int, float | None]:
    """連續多少天 emotions 分數 ≤ threshold（從 today 往回算）。

    回 (streak_days, last_14d_avg | None)。streak 中斷即停。
    """
    by_day: dict[str, list[int]] = defaultdict(list)
    for e in emotion_logs or []:
        dt = _parse_iso(e.get("recorded_at") or e.get("created_at"))
        if not dt:
            continue
        v = e.get("score") or e.get("mood_score") or e.get("level")
        if isinstance(v, (int, float)):
            by_day[dt.date().isoformat()].append(int(v))

    # 連續 streak（today 起往回）
    streak = 0
    for offset in range(0, 30):
        day = (now - timedelta(days=offset)).date().isoformat()
        if day in by_day:
            day_avg = mean(by_day[day])
            if day_avg <= threshold:
                streak += 1
            else:
                break
        elif offset == 0:
            # 今天沒紀錄不算斷，繼續往回
            continue
        else:
            break

    cutoff_14d = now - timedelta(days=14)
    recent_scores = [
        s
        for e in emotion_logs or []
        for s in [e.get("score") or e.get("mood_score") or e.get("level")]
        if isinstance(s, (int, float))
        and (_parse_iso(e.get("recorded_at") or e.get("created_at")) or now) >= cutoff_14d
    ]
    avg_14d = mean(recent_scores) if recent_scores else None
    return streak, avg_14d


def _score_mental_disease(
    canonical: str,
    meta: dict,
    symptom_logs: list[dict],
    emotion_logs: list[dict],
    now: datetime,
) -> dict:
    """精神類疾病：主看情緒連續低落天數，相關症狀為輔助。"""
    thr = meta["thresholds"]
    streak, avg_14d = _emotion_streak_below(emotion_logs, thr["emotion_avg_threshold"], now)

    reasons: list[str] = []
    score = 0

    if streak >= thr["emotion_low_streak_days_high"]:
        score += 50
        reasons.append(f"情緒分數已連續 {streak} 天偏低（≤{thr['emotion_avg_threshold']}）")
    elif streak >= thr["emotion_low_streak_days_warn"]:
        score += 30
        reasons.append(f"情緒分數已連續 {streak} 天偏低（≤{thr['emotion_avg_threshold']}）")

    if avg_14d is not None and avg_14d <= thr["emotion_avg_threshold"]:
        score += 10
        reasons.append(f"近 14 天情緒平均 {avg_14d:.1f}")

    # 相關症狀加成（憂鬱：失眠 + 疲倦；焦慮：心悸 + 失眠）
    relevant = meta["relevant_clusters"]
    iso_30d = now - timedelta(days=30)
    sym_30d = 0
    for log in symptom_logs or []:
        dt = _parse_iso(log.get("created_at"))
        if not dt or dt < iso_30d:
            continue
        raw_syms = log.get("symptoms") or []
        if isinstance(raw_syms, str):
            raw_syms = [raw_syms]
        if any(normalize_symptom(str(s)) in relevant for s in raw_syms):
            sym_30d += 1
    if sym_30d >= 3:
        score += 15
        reasons.append(f"30 天內相關身體症狀（失眠／疲倦等）回報 {sym_30d} 次")

    score = min(score, 100)
    return {
        "name": canonical,
        "source": "registered",
        "type": "mental",
        "level": _level_from_score(score),
        "score": score,
        "reasons": reasons,
        "evidence": {
            "low_emotion_streak_days": streak,
            "emotion_avg_14d": round(avg_14d, 2) if avg_14d is not None else None,
            "related_symptom_count_30d": sym_30d,
        },
    }


# ─── Fallback：通用症狀聚類（給對照表外的疾病或無 profile） ──

def _fallback_cluster_scores(
    symptom_logs: list[dict],
    now: datetime,
    consumed_clusters: set[str],
) -> list[dict]:
    """把症狀按 cluster 聚集，產生「症狀導向」評估列。

    consumed_clusters 是已被 registered disease 用過的 cluster 名稱，避免重複展示。
    """
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for log in symptom_logs or []:
        raw_symptoms = log.get("symptoms") or []
        if isinstance(raw_symptoms, str):
            raw_symptoms = [raw_symptoms]
        seen_in_log: set[str] = set()
        for s in raw_symptoms:
            cluster = normalize_symptom(str(s))
            if not cluster or cluster in consumed_clusters or cluster in seen_in_log:
                continue
            seen_in_log.add(cluster)
            by_cluster[cluster].append(log)

    iso_30d = now - timedelta(days=30)
    iso_90d = now - timedelta(days=90)
    out: list[dict] = []
    for cluster, entries in by_cluster.items():
        timed = sorted(
            [(_parse_iso(e.get("created_at")), e) for e in entries if e.get("created_at")],
            key=lambda x: x[0] or now,
        )
        count_30d = sum(1 for dt, _ in timed if dt and dt >= iso_30d)
        count_90d = sum(1 for dt, _ in timed if dt and dt >= iso_90d)
        if count_90d < 3:
            continue  # 頻率太低不入 fallback 列
        score = 0
        reasons = []
        if count_90d >= 3:
            score += 20
            reasons.append(f"過去 90 天「{cluster}」回報 {count_90d} 次")
        if count_30d >= 2:
            score += 15
            reasons.append(f"30 天內「{cluster}」回報 {count_30d} 次")
        out.append({
            "name": cluster,
            "source": "fallback_symptom",
            "type": "symptom_cluster",
            "level": _level_from_score(score),
            "score": min(score, 100),
            "reasons": reasons,
            "evidence": {"count_30d": count_30d, "count_90d": count_90d},
        })
    return out


# ─── 服藥中斷天數 ─────────────────────────────────────────

def _missed_med_days(med_logs: Iterable[dict], now: datetime) -> float | None:
    latest = None
    for m in med_logs or []:
        dt = _parse_iso(m.get("taken_at"))
        if dt and (latest is None or dt > latest):
            latest = dt
    if latest is None:
        return None
    return _days_between(now, latest)


# ─── 主入口 ──────────────────────────────────────────────

def assess_recurrence(
    symptom_logs: list[dict],
    medication_logs: list[dict] | None = None,
    emotion_logs: list[dict] | None = None,
    current_disease: str | None = None,
    conditions: str | None = None,
    now: datetime | None = None,
) -> dict:
    """主入口：依患者「登入疾病 + 日常紀錄」計算復發風險。

    Returns:
      {
        "level": "low|medium|high|critical",     # 全患者最高 score 對應等級
        "score": int,
        "diseases": [                             # 每個被評估單元一條
          {
            "name": "氣喘",
            "source": "registered" | "fallback_symptom",
            "type": "attack" | "mental" | "symptom_cluster",
            "level": ..., "score": ..., "reasons": [...], "evidence": {...},
          },
          ...
        ],
        "patient_diseases": ["氣喘", "高血壓"],    # 原始字串
        "unrecognized_diseases": ["高血壓"],       # 對不到 catalog 的
        "assessed_at": iso, "data_summary": {...}
      }
    """
    now = now or datetime.now(timezone.utc)
    medication_logs = medication_logs or []
    emotion_logs = emotion_logs or []

    patient_diseases = split_patient_diseases(current_disease, conditions)
    missed_med = _missed_med_days(medication_logs, now)

    registered_results: list[dict] = []
    consumed_clusters: set[str] = set()
    unrecognized: list[str] = []
    seen_canonical: set[str] = set()

    for raw in patient_diseases:
        canonical = match_disease(raw)
        if canonical is None:
            unrecognized.append(raw)
            continue
        if canonical in seen_canonical:
            continue  # 同義詞已算過
        seen_canonical.add(canonical)
        meta = DISEASE_CATALOG[canonical]
        consumed_clusters |= meta["relevant_clusters"]

        if meta["type"] == "attack":
            result = _score_attack_disease(canonical, meta, symptom_logs, now, missed_med)
        elif meta["type"] == "mental":
            result = _score_mental_disease(canonical, meta, symptom_logs, emotion_logs, now)
        else:
            continue
        # 保留原始字串方便顯示
        if raw != canonical:
            result["matched_from"] = raw
        registered_results.append(result)

    fallback = _fallback_cluster_scores(symptom_logs, now, consumed_clusters)

    all_results = registered_results + fallback
    all_results.sort(key=lambda x: x["score"], reverse=True)

    top_score = all_results[0]["score"] if all_results else 0
    top_level = _level_from_score(top_score)

    return {
        "level": top_level,
        "score": top_score,
        "diseases": all_results,
        "patient_diseases": patient_diseases,
        "unrecognized_diseases": unrecognized,
        "assessed_at": now.isoformat(),
        "data_summary": {
            "symptom_logs": len(symptom_logs or []),
            "medication_logs": len(medication_logs),
            "emotion_logs": len(emotion_logs),
            "missed_med_days": missed_med,
            "registered_count": len(registered_results),
            "fallback_count": len(fallback),
        },
    }
