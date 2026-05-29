"""復發風險預測 — 透明、可解釋的決定性引擎（規則 5：決定性任務用程式碼，不用 LLM）。

設計原則（對齊 docs CLAUDE_predict_ui_ux.md）：
  - band 優先、百分比次要：模型本質是縱向訊號的啟發式推估，準確度有限，
    不該製造假精確感，因此回傳 band + 方向，百分比僅作參考小字。
  - 每個因子的貢獻（SHAP-like）都由「近期 vs 基準」的真實差異算出，
    沒有資料的因子直接省略，絕不捏造（規則 12：禁止隱性失敗 / 假資料）。
  - 「為什麼」用模板化人話組出，不丟給 LLM（規則 5）。

訊號來源（皆以 timeline._fetch_safely 風格防禦式讀取，缺表不致崩）：
  - emotions.score (1-5)        → 情緒 / 壓力 proxy
  - medication_logs.taken       → 服藥順從性
  - symptoms_log                → 症狀記錄頻率
  - bedside_logs.sleep / mood   → 睡眠（若有）

時間窗：以 as_of 為基準回看 60 天。
  近期窗 = 最近 14 天；基準窗 = 第 15~60 天。比較兩窗差異產生風險貢獻。
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional

logger = logging.getLogger(__name__)

# ── 時間窗常數 ────────────────────────────────────────────────
HORIZON_DAYS = 14          # 預測未來 14 天復發風險
RECENT_WINDOW = 14         # 近期窗
BASELINE_WINDOW = 60       # 基準窗（近期之外到第 60 天）
THRESHOLD_DAYS = 14        # 冷啟動門檻：少於這麼多「有紀錄的天數」就不預測

# ── band 邊界（與前端 RiskBandBadge 對齊）─────────────────────
BASE_RISK = 0.15           # 無任何不利訊號時的基線風險
RISK_FLOOR = 0.05
RISK_CEIL = 0.85
BAND_LOW_MAX = 0.30        # < 0.30 穩定
BAND_MED_MAX = 0.60        # 0.30-0.60 中度關注；> 0.60 較需留意

DISCLAIMER_PREDICT = "此為長期紀錄推估的輔助參考，非診斷，最終由醫師判斷。"
DISCLAIMER_SHAP = "以上為統計相關性，非因果；最終由醫師判斷。"


def _parse_dt(raw) -> Optional[datetime]:
    if not raw:
        return None
    s = str(raw).replace("Z", "").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[: len(fmt) + 6], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(raw)[:19].replace("Z", ""))
    except Exception:
        return None


def _fetch_safely(sb, table: str, patient_id: str):
    """缺表 / RLS / 離線都回空陣列，不阻擋預測（對齊 timeline.py）。"""
    try:
        result = sb.table(table).select("*").eq("patient_id", patient_id).execute()
        return getattr(result, "data", None) or []
    except Exception as e:
        logger.info(f"recurrence: table {table} unavailable: {e}")
        return []


def _avg(nums):
    nums = [n for n in nums if n is not None]
    return sum(nums) / len(nums) if nums else None


def _split_windows(rows, date_key, as_of: datetime):
    """把資料列依日期切成 (近期窗, 基準窗)。"""
    recent_cut = as_of - timedelta(days=RECENT_WINDOW)
    baseline_cut = as_of - timedelta(days=BASELINE_WINDOW)
    recent, baseline = [], []
    for r in rows:
        dt = _parse_dt(r.get(date_key) or r.get("created_at"))
        if not dt or dt > as_of:
            continue
        if dt >= recent_cut:
            recent.append(r)
        elif dt >= baseline_cut:
            baseline.append(r)
    return recent, baseline


# ── 單一因子貢獻 ──────────────────────────────────────────────
# contribution 為「風險百分點」的有號小數（正=推升、負=降低）。
# 每個因子最多影響 ±0.25，避免單一訊號獨大（保守、臨床取向）。
def _factor_emotion(sb, pid, as_of):
    rows = _fetch_safely(sb, "emotions", pid)
    recent, base = _split_windows(rows, "created_at", as_of)
    r_avg = _avg([x.get("score") for x in recent])
    if r_avg is None:
        return None
    b_avg = _avg([x.get("score") for x in base])
    # 情緒分數 1(差)~5(好)。低分=高壓力=推升風險。
    # 以 3 為中性點，低於 3 推升；並比較近期相對基準是否惡化。
    level = (3 - r_avg) / 2.0 * 0.18           # r_avg=1 → +0.18, r_avg=5 → -0.18
    drift = 0.0
    if b_avg is not None:
        drift = max(-1.0, min(1.0, (b_avg - r_avg) / 2.0)) * 0.07  # 變差→正
    contrib = max(-0.20, min(0.20, level + drift))
    worse = b_avg is not None and r_avg < b_avg - 0.3
    if contrib >= 0:
        text = "壓力升高，情緒分數偏低" if r_avg < 3 else "情緒大致平穩"
        if worse:
            text = "壓力升高，情緒較前兩週變差"
    else:
        text = "情緒穩定，有助降低風險"
    return {
        "feature": "stress",
        "label": "壓力 / 情緒",
        "value": contrib,
        "plain_text": text,
        "modifiable": True,
        "data_points": len(recent),
    }


def _factor_adherence(sb, pid, as_of):
    rows = _fetch_safely(sb, "medication_logs", pid)
    recent, base = _split_windows(rows, "taken_at", as_of)
    if not recent and not base:
        return None
    if not recent:
        return None
    taken = sum(1 for x in recent if (x.get("taken") in (1, True, "1")))
    total = len(recent)
    rate = taken / total if total else 1.0
    # 順從性高(≈1)→降低風險(藍)；低→推升(紅)
    contrib = max(-0.12, min(0.18, (0.85 - rate) * 0.35))
    if contrib <= 0:
        text = "規律服藥，有助降低風險"
    elif rate >= 0.5:
        text = "近期偶有漏藥"
    else:
        text = "近期漏藥次數偏多"
    return {
        "feature": "adherence",
        "label": "服藥順從性",
        "value": contrib,
        "plain_text": text,
        "modifiable": True,
        "data_points": total,
    }


def _factor_symptoms(sb, pid, as_of):
    rows = _fetch_safely(sb, "symptoms_log", pid)
    recent, base = _split_windows(rows, "created_at", as_of)
    if not recent and not base:
        return None
    r_n = len(recent)
    # 基準窗較長（約 46 天），換算成每 14 天的速率再比較
    b_rate = len(base) / max(1, (BASELINE_WINDOW - RECENT_WINDOW)) * RECENT_WINDOW
    delta = r_n - b_rate
    contrib = max(-0.05, min(0.22, delta * 0.05))
    if contrib > 0.02:
        text = "症狀記錄變頻繁"
    elif contrib < -0.02:
        text = "症狀記錄減少"
    else:
        text = "症狀記錄大致持平"
    return {
        "feature": "symptoms",
        "label": "症狀活動度",
        "value": contrib,
        "plain_text": text,
        "modifiable": False,
        "data_points": r_n,
    }


def _factor_sleep(sb, pid, as_of):
    rows = _fetch_safely(sb, "bedside_logs", pid)
    recent, base = _split_windows(rows, "created_at", as_of)
    # sleep 欄位為自由文字，抽出可量化的「不足」訊號
    poor_words = ("差", "不好", "失眠", "睡不", "難睡", "少", "淺")
    if not recent:
        return None
    poor = 0
    counted = 0
    for x in recent:
        s = str(x.get("sleep") or "")
        if not s:
            continue
        counted += 1
        if any(w in s for w in poor_words):
            poor += 1
    if counted == 0:
        return None
    poor_rate = poor / counted
    contrib = max(-0.04, min(0.22, (poor_rate - 0.2) * 0.30))
    if contrib > 0.04:
        text = "睡眠連續變差"
    elif contrib < -0.02:
        text = "睡眠品質尚可"
    else:
        text = "睡眠大致穩定"
    return {
        "feature": "sleep",
        "label": "睡眠",
        "value": contrib,
        "plain_text": text,
        "modifiable": True,
        "data_points": counted,
    }


def _distinct_record_days(sb, pid, as_of) -> int:
    """近 60 天內有任何紀錄的「不重複天數」，用來判斷冷啟動與信心。"""
    days = set()
    cut = as_of - timedelta(days=BASELINE_WINDOW)
    for table, key in (
        ("emotions", "created_at"),
        ("medication_logs", "taken_at"),
        ("symptoms_log", "created_at"),
        ("bedside_logs", "created_at"),
    ):
        for r in _fetch_safely(sb, table, pid):
            dt = _parse_dt(r.get(key) or r.get("created_at"))
            if dt and cut <= dt <= as_of:
                days.add(dt.date())
    return len(days)


def _confidence_for(data_days: int):
    if data_days >= 45:
        return "high", "高"
    if data_days >= 25:
        return "medium", "中"
    return "low", "低"


def _band_for(score: float) -> str:
    if score < BAND_LOW_MAX:
        return "low"
    if score < BAND_MED_MAX:
        return "medium"
    return "high"


def compute_factors(sb, patient_id: str, as_of: datetime):
    """回傳該時間點所有「有資料」的因子貢獻（已濾掉 None）。"""
    raw = [
        _factor_emotion(sb, patient_id, as_of),
        _factor_adherence(sb, patient_id, as_of),
        _factor_symptoms(sb, patient_id, as_of),
        _factor_sleep(sb, patient_id, as_of),
    ]
    return [f for f in raw if f is not None]


def score_from_factors(factors) -> float:
    total = BASE_RISK + sum(f["value"] for f in factors)
    return max(RISK_FLOOR, min(RISK_CEIL, total))


def risk_at(sb, patient_id: str, as_of: datetime):
    """單一時間點的完整推估（不含趨勢方向）。"""
    factors = compute_factors(sb, patient_id, as_of)
    risk = score_from_factors(factors)
    return risk, factors


def predict(sb, patient_id: str, as_of: Optional[datetime] = None) -> dict:
    """主預測：回傳 RiskCard / ConfidenceMeter / ColdStartCard 所需欄位。"""
    as_of = as_of or datetime.utcnow()
    data_days = _distinct_record_days(sb, patient_id, as_of)

    # ── 冷啟動：資料不足，不給誤導性數字（畫面 D）──────────────
    if data_days < THRESHOLD_DAYS:
        return {
            "prediction_id": f"{patient_id}:{as_of.date().isoformat()}",
            "patient_id": patient_id,
            "cold_start": True,
            "data_days": data_days,
            "threshold_days": THRESHOLD_DAYS,
            "days_remaining": max(0, THRESHOLD_DAYS - data_days),
            "collecting": ["睡眠", "壓力", "症狀", "用藥"],
            "horizon_days": HORIZON_DAYS,
            "disclaimer": DISCLAIMER_PREDICT,
            "generated_at": as_of.isoformat(),
        }

    risk, factors = risk_at(sb, patient_id, as_of)

    # 趨勢方向：與 7 天前的推估比較（方向比絕對值重要）
    prev_risk, _ = risk_at(sb, patient_id, as_of - timedelta(days=7))
    diff = risk - prev_risk
    if diff > 0.04:
        trend, trend_label = "up", "上升中"
    elif diff < -0.04:
        trend, trend_label = "down", "下降中"
    else:
        trend, trend_label = "flat", "持平"

    confidence, confidence_label = _confidence_for(data_days)
    band = _band_for(risk)

    # top driver = 推升風險最多的「正貢獻」因子（給 RiskCard 一句話）
    pushers = sorted([f for f in factors if f["value"] > 0],
                     key=lambda f: f["value"], reverse=True)
    top_driver = None
    if pushers:
        top_driver = {
            "feature": pushers[0]["feature"],
            "plain_text": pushers[0]["plain_text"],
            "modifiable": pushers[0]["modifiable"],
        }

    return {
        "prediction_id": f"{patient_id}:{as_of.date().isoformat()}",
        "patient_id": patient_id,
        "cold_start": False,
        "horizon_days": HORIZON_DAYS,
        "risk_score": round(risk, 3),
        "risk_percent": round(risk * 100),
        "risk_band": band,
        "trend": trend,
        "trend_label": trend_label,
        "confidence": confidence,
        "confidence_label": confidence_label,
        "data_days": data_days,
        "threshold_days": THRESHOLD_DAYS,
        "top_driver": top_driver,
        "low_data": data_days < 25,
        "disclaimer": DISCLAIMER_PREDICT,
        "generated_at": as_of.isoformat(),
    }


def explain(sb, patient_id: str, as_of: datetime) -> dict:
    """畫面 C：把每個因子攤成 SHAP-like 水平條（紅推升/藍降低）。"""
    risk, factors = risk_at(sb, patient_id, as_of)
    data_days = _distinct_record_days(sb, patient_id, as_of)
    confidence, confidence_label = _confidence_for(data_days)

    explanations = []
    for f in sorted(factors, key=lambda x: abs(x["value"]), reverse=True):
        explanations.append({
            "feature": f["feature"],
            "label": f["label"],
            "shap_value": round(f["value"], 3),
            "shap_percent": round(f["value"] * 100),
            "direction": "up" if f["value"] >= 0 else "down",
            "plain_text": f["plain_text"],
            "modifiable": f["modifiable"],
        })

    modifiable = [e["label"] for e in explanations if e["modifiable"] and e["direction"] == "up"]

    return {
        "prediction_id": f"{patient_id}:{as_of.date().isoformat()}",
        "patient_id": patient_id,
        "risk_band": _band_for(risk),
        "risk_percent": round(risk * 100),
        "horizon_days": HORIZON_DAYS,
        "confidence": confidence,
        "confidence_label": confidence_label,
        "data_days": data_days,
        "explanations": explanations,
        "modifiable_factors": modifiable,
        "disclaimer": DISCLAIMER_SHAP,
    }


def trend_series(sb, patient_id: str, window_days: int, as_of: Optional[datetime] = None) -> dict:
    """畫面 B：時間序列風險線 + 信心區間 + 實際 flare 事件標記。

    為了效能，沿時間窗取約 24 個取樣點，每點以該日為 as_of 重新推估
    （決定性 → 可重現）。信心區間寬度隨資料量縮放（資料少→帶變寬）。
    """
    as_of = as_of or datetime.utcnow()
    window_days = max(7, min(180, window_days))
    n_points = 24
    step = max(1, window_days // n_points)

    points = []
    d = window_days
    while d >= 0:
        sample_dt = as_of - timedelta(days=d)
        risk, _ = risk_at(sb, patient_id, sample_dt)
        dd = _distinct_record_days(sb, patient_id, sample_dt)
        # 信心半寬：資料越少越寬（從 ±18% 收斂到 ±5%）
        half = max(0.05, 0.18 - (min(dd, 45) / 45.0) * 0.13)
        pct = risk * 100
        points.append({
            "date": sample_dt.date().isoformat(),
            "risk_percent": round(pct),
            "confidence_low": round(max(0, pct - half * 100)),
            "confidence_high": round(min(100, pct + half * 100)),
        })
        d -= step

    # 實際發生過的事件（✦）：就診紀錄當作可觀察的臨床事件標記
    flare_events = []
    cut = as_of - timedelta(days=window_days)
    for r in _fetch_safely(sb, "medical_records", patient_id):
        dt = _parse_dt(r.get("visit_date") or r.get("created_at"))
        if dt and cut <= dt <= as_of:
            flare_events.append({
                "date": dt.date().isoformat(),
                "label": r.get("diagnosis") or "就診",
            })

    return {
        "patient_id": patient_id,
        "window_days": window_days,
        "horizon_days": HORIZON_DAYS,
        "bands": {"low": [0, 30], "medium": [30, 60], "high": [60, 100]},
        "points": points,
        "flare_events": flare_events,
        "disclaimer": DISCLAIMER_PREDICT,
    }
