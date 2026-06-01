"""復發風險預測 — 疾病別、文獻為錨、可解釋的決定性引擎。

設計（對齊使用者需求 + 既有安全憲法 backend/services/llm_service.py:502）：

  1. 連結病患的「疾病」當錨（規則：對 user 疾病做連結）
     - 從 patient_profiles.current_disease 取病名；沒有就退而求其次看 medical_records.diagnosis。
     - 該疾病的「族群層級復發知識」（復發率 band + 復發驅動因子 + 文獻引用）由
       llm_service.lookup_disease_recurrence 整理、快取進 disease_reference.recurrence_data。
       這就是「根據」：每個驅動因子都帶 evidence + PubMed 引用。

  2. 連結病患「所有縱向紀錄」當核心材料（規則：連結患者所有紀錄作分析）
     - 一次掃齊情緒 / 用藥 / 症狀 / 睡眠 / 檢驗 / 就診 / 飲食 / 月經等紀錄表，
       實際有資料才納入評分，並回傳完整 records_analyzed 清單（透明）。

  3. 評斷方式（規則：甚麼去評斷的）
     - 疾病別基線（文獻復發 band → 起始風險）✕ 病患近期紀錄相對自身基準的變化。
     - 文獻說「與此病復發有關」的因子會被加權並掛上引用；對不上的因子照常計分但標明為一般訊號。
     - 最可能的復發原因（top driver）= 病患正在惡化、且文獻證實與此病復發相關的因子排序第一名（預估參考）。

  4. 呈現（規則：band 為主、% 收起、帶去問醫師）＋ 誠實（規則 12）
     - band 優先、百分比次要；沒疾病 / 沒文獻 / 沒資料一律明白標示，不捏造數字或引用。

時間窗：以 as_of 回看 60 天。近期窗 = 最近 14 天；基準窗 = 第 15~60 天。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── 時間窗常數 ────────────────────────────────────────────────
HORIZON_DAYS = 14          # 預測未來 14 天復發風險
RECENT_WINDOW = 14         # 近期窗
BASELINE_WINDOW = 60       # 基準窗（近期之外到第 60 天）
THRESHOLD_DAYS = 14        # 冷啟動門檻：少於這麼多「有紀錄的天數」就不預測

# ── band 邊界（與前端 RiskBandBadge 對齊）─────────────────────
BASE_RISK = 0.15           # 未綁定疾病時的一般基線（無文獻錨）
RISK_FLOOR = 0.05
RISK_CEIL = 0.85
BAND_LOW_MAX = 0.30        # < 0.30 穩定
BAND_MED_MAX = 0.60        # 0.30-0.60 中度關注；> 0.60 較需留意

# 疾病復發 band → 起始基線風險（文獻為錨；以區間/分級呈現，非精確值）
DISEASE_BASELINE = {"low": 0.10, "medium": 0.18, "high": 0.28}

# 文獻關聯強度 → 對「疾病相關因子」貢獻的加權（讓疾病錨真的影響評分，但有界）
DRIVER_WEIGHT = {"high": 1.25, "medium": 1.0, "low": 0.85}

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


def _fetch_safely(sb, table: str, patient_id: str, key: str = "patient_id"):
    """缺表 / RLS / 離線都回空陣列，不阻擋預測（對齊 timeline.py）。

    key 為過濾欄位：多數表是 patient_id，少數（sleep_sessions / patient_profiles）是 user_id。
    本專案 patient_id 與 user_id 同值（getStablePatientId），只是欄名不同。
    """
    try:
        result = sb.table(table).select("*").eq(key, patient_id).execute()
        return getattr(result, "data", None) or []
    except Exception as e:
        logger.info(f"recurrence: table {table} unavailable: {e}")
        return []


# ── 縱向訊號來源（一次抓齊；trend 在記憶體內重算，不重複查 DB）──────
# 每筆：(table, date_key, key_col, scored)
#   scored=True 表示有對應的 factor 計分器；False 僅納入 records_analyzed 清單（透明）。
SIGNAL_TABLES = (
    ("emotions",         "created_at", "patient_id", True),
    ("medication_logs",  "taken_at",   "patient_id", True),
    ("symptoms_log",     "created_at", "patient_id", True),
    ("bedside_logs",     "created_at", "patient_id", True),
    ("sleep_sessions",   "created_at", "user_id",    True),
    ("medical_records",  "visit_date", "patient_id", True),
    ("diet_records",     "eaten_at",   "patient_id", True),
    ("labs",             "created_at", "patient_id", True),
    ("menstrual_cycles", "start_date", "patient_id", False),
)

# 每個 feature 對應的人看得懂的中文標籤（與前端一致）
FEATURE_LABEL = {
    "stress": "壓力 / 情緒",
    "adherence": "服藥順從性",
    "symptoms": "症狀活動度",
    "sleep": "睡眠",
    "visits": "就診 / 急性事件",
    "diet": "飲食 / 生活型態",
    "labs": "檢驗數值",
}

# records_analyzed 清單顯示用：table → 中文紀錄類別
TABLE_LABEL = {
    "emotions": "情緒 / 壓力",
    "medication_logs": "用藥",
    "symptoms_log": "症狀",
    "bedside_logs": "睡眠 / 心情",
    "sleep_sessions": "睡眠量測",
    "medical_records": "就診紀錄",
    "diet_records": "飲食",
    "labs": "檢驗",
    "menstrual_cycles": "生理週期",
}


def _load_sources(sb, patient_id: str, disease_hint: Optional[str] = None) -> dict:
    """一次抓齊所有來源表 + 疾病脈絡（每張表各一次查詢）。

    trend 沿時間窗取數十個點，每點都用同一批原始資料切窗，先抓一次、記憶體內重算，
    避免 O(取樣點 × 表) 的重複查詢拖垮 serverless（這是 #487 修過的逾時根因）。

    疾病脈絡（病名 + 已快取的復發知識）放在 sources["_context"]；此處為唯讀，
    不觸發 LLM。需要時由 warm_disease_knowledge() 一次性填快取。
    disease_hint：前端本地檔案的 current_disease，讓未同步 profile 的使用者也能對準疾病。
    """
    sources = {
        table: _fetch_safely(sb, table, patient_id, key)
        for table, _date, key, _scored in SIGNAL_TABLES
    }
    sources["_context"] = _load_disease_context(sb, patient_id, sources, disease_hint)
    return sources


def _load_disease_context(sb, patient_id: str, sources: dict, disease_hint: Optional[str] = None) -> dict:
    """找出病患疾病 + 讀取（唯讀）已快取的復發知識。"""
    disease_name, disease_source = _resolve_disease(sb, patient_id, sources, disease_hint)
    ctx = {
        "disease_name": disease_name,
        "disease_source": disease_source,
        "recurrence": None,
        "references": [],
    }
    if not disease_name:
        return ctx
    row = _find_disease_row(sb, disease_name)
    if row:
        ctx["recurrence"] = _decode_recurrence(row.get("recurrence_data"))
        ctx["references"] = _decode_json(row.get("references_data")) or []
    return ctx


def _resolve_disease(sb, patient_id: str, sources: dict, disease_hint: Optional[str] = None):
    """病名來源優先序：前端明示 hint → 個人檔案 current_disease → 最近一次就診 diagnosis。"""
    if disease_hint and disease_hint.strip():
        return disease_hint.strip(), "hint"
    profiles = _fetch_safely(sb, "patient_profiles", patient_id, key="user_id")
    if profiles:
        name = (profiles[0].get("current_disease") or "").strip()
        if name:
            return name, "profile"
    # 退而求其次：最近一次就診的正式診斷
    records = sources.get("medical_records", [])
    latest, latest_dt = None, None
    for r in records:
        dx = (r.get("diagnosis") or "").strip()
        if not dx:
            continue
        dt = _parse_dt(r.get("visit_date") or r.get("created_at"))
        if dt and (latest_dt is None or dt > latest_dt):
            latest, latest_dt = dx, dt
    if latest:
        return latest, "medical_records"
    return None, None


def _norm(s) -> str:
    return (str(s or "")).strip().lower()


def _find_disease_row(sb, disease_name: str) -> Optional[dict]:
    """在 disease_reference 找這個病（名稱 / 英文名 / 別名比對），回整列。"""
    qn = _norm(disease_name)
    if not qn:
        return None
    try:
        rows = sb.table("disease_reference").select("*").execute()
        rows = getattr(rows, "data", None) or []
    except Exception as e:
        logger.info(f"recurrence: disease_reference unavailable: {e}")
        return None
    for r in rows:
        if _norm(r.get("name_zh")) == qn or _norm(r.get("name_en")) == qn:
            return r
        aliases = _decode_json(r.get("aliases")) or []
        if isinstance(aliases, list) and any(_norm(a) == qn for a in aliases):
            return r
    return None


def _decode_json(value):
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            import json
            return json.loads(value)
        except Exception:
            return None
    return None


def _decode_recurrence(value) -> Optional[dict]:
    """把 disease_reference.recurrence_data 解成引擎可用的結構（容錯）。"""
    data = _decode_json(value)
    if not isinstance(data, dict):
        return None
    if not data.get("matched"):
        return None
    rr = data.get("recurrence_rate") if isinstance(data.get("recurrence_rate"), dict) else {}
    drivers = data.get("drivers") if isinstance(data.get("drivers"), list) else []
    return {
        "band": rr.get("band") if rr.get("band") in ("low", "medium", "high") else None,
        "range_text": rr.get("range_text"),
        "horizon": rr.get("horizon"),
        "summary": rr.get("summary"),
        "drivers": [d for d in drivers if isinstance(d, dict) and d.get("maps_to")],
        "watch_signs": data.get("watch_signs") if isinstance(data.get("watch_signs"), list) else [],
        "disclaimer": data.get("disclaimer"),
    }


def _ensure_recurrence_knowledge(sb, sources: dict) -> None:
    """predict（POST）專用：若疾病已知但復發知識未快取，一次性整理 + 寫快取。

    trend / explain 不呼叫此函式（避免 LLM 延遲重蹈 #487 逾時）；首次 predict 暖快取後，
    後續端點直接讀 disease_reference.recurrence_data。失敗一律靜默退回一般基線（規則 12：不捏造）。
    """
    ctx = sources.get("_context") or {}
    name = ctx.get("disease_name")
    if not name or ctx.get("recurrence"):
        return
    try:
        from backend.services.llm_service import lookup_disease_recurrence, pubmed_search
    except Exception:
        return
    try:
        info = lookup_disease_recurrence(name)
    except Exception as e:
        logger.info(f"recurrence: lookup_disease_recurrence failed: {e}")
        return
    if not info.get("matched"):
        return
    # 文獻引用：優先沿用 disease_reference 既有 references_data；沒有才現抓 PubMed
    refs = ctx.get("references") or []
    if not refs:
        try:
            refs = pubmed_search(info.get("name_en") or info.get("name_zh") or name, max_results=3)
        except Exception:
            refs = []
    _cache_recurrence(sb, name, info, refs)
    ctx["recurrence"] = _decode_recurrence(_dumps({**info}))
    ctx["references"] = refs


def _dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _cache_recurrence(sb, disease_name: str, info: dict, refs: list) -> None:
    """把復發知識寫回 disease_reference.recurrence_data；沒有疾病主檔列就建一筆最小列。

    建最小列只填 name/aliases/recurrence_data/references_data，不假裝有完整衛教內容
    （百科欄位由 diseases.py 的查詢流程各自負責，互不干擾）。
    """
    row = _find_disease_row(sb, disease_name)
    try:
        # Supabase 是 jsonb 可直接存 dict；SQLite fallback 需字串
        from backend.routers.diseases import _is_supabase_native
        native = _is_supabase_native()
    except Exception:
        native = True
    value = info if native else _dumps(info)
    refs_value = refs if native else _dumps(refs or [])
    try:
        if row and row.get("id"):
            update = {"recurrence_data": value}
            if not (_decode_json(row.get("references_data")) or []):
                update["references_data"] = refs_value
            sb.table("disease_reference").update(update).eq("id", row["id"]).execute()
            return
        import uuid
        aliases = [disease_name]
        sb.table("disease_reference").insert({
            "id": str(uuid.uuid4()),
            "name_zh": info.get("name_zh") or disease_name,
            "name_en": info.get("name_en"),
            "aliases": aliases if native else _dumps(aliases),
            "recurrence_data": value,
            "references_data": refs_value,
            "source": "claude",
        }).execute()
    except Exception as e:
        logger.info(f"recurrence: cache write skipped: {e}")


def warm_disease_knowledge(sb, patient_id: str, disease_hint: Optional[str] = None) -> dict:
    """整理 / 暖快取病患疾病的復發知識（給前端「收集資訊」流程明確觸發，避免拖慢 predict 熱路徑）。

    回傳疾病區塊 + status：
      - no_disease：尚未綁定疾病
      - cached：已有快取，直接命中
      - fetched：本次整理成功並寫入快取
      - unavailable：查不到 / LLM 失敗（誠實回報，不捏造）
    """
    sources = _load_sources(sb, patient_id, disease_hint)
    ctx = sources.get("_context") or {}
    if not ctx.get("disease_name"):
        return {"status": "no_disease", "disease": _disease_block(ctx)}
    if ctx.get("recurrence"):
        return {"status": "cached", "disease": _disease_block(ctx)}
    _ensure_recurrence_knowledge(sb, sources)
    ctx = sources.get("_context") or {}
    status = "fetched" if ctx.get("recurrence") else "unavailable"
    return {"status": status, "disease": _disease_block(ctx)}


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
def _factor_emotion(rows, as_of):
    recent, base = _split_windows(rows, "created_at", as_of)
    r_avg = _avg([x.get("score") for x in recent])
    if r_avg is None:
        return None
    b_avg = _avg([x.get("score") for x in base])
    # 情緒分數 1(差)~5(好)。低分=高壓力=推升風險。以 3 為中性點。
    level = (3 - r_avg) / 2.0 * 0.18
    drift = 0.0
    if b_avg is not None:
        drift = max(-1.0, min(1.0, (b_avg - r_avg) / 2.0)) * 0.07
    contrib = max(-0.20, min(0.20, level + drift))
    worse = b_avg is not None and r_avg < b_avg - 0.3
    if contrib >= 0:
        text = "壓力升高，情緒分數偏低" if r_avg < 3 else "情緒大致平穩"
        if worse:
            text = "壓力升高，情緒較前兩週變差"
    else:
        text = "情緒穩定，有助降低風險"
    return _mk("stress", contrib, text, True, len(recent))


def _factor_adherence(rows, as_of):
    recent, base = _split_windows(rows, "taken_at", as_of)
    if not recent:
        return None
    taken = sum(1 for x in recent if (x.get("taken") in (1, True, "1")))
    total = len(recent)
    rate = taken / total if total else 1.0
    contrib = max(-0.12, min(0.18, (0.85 - rate) * 0.35))
    if contrib <= 0:
        text = "規律服藥，有助降低風險"
    elif rate >= 0.5:
        text = "近期偶有漏藥"
    else:
        text = "近期漏藥次數偏多"
    return _mk("adherence", contrib, text, True, total)


def _factor_symptoms(rows, as_of):
    recent, base = _split_windows(rows, "created_at", as_of)
    if not recent and not base:
        return None
    r_n = len(recent)
    b_rate = len(base) / max(1, (BASELINE_WINDOW - RECENT_WINDOW)) * RECENT_WINDOW
    delta = r_n - b_rate
    contrib = max(-0.05, min(0.22, delta * 0.05))
    if contrib > 0.02:
        text = "症狀記錄變頻繁"
    elif contrib < -0.02:
        text = "症狀記錄減少"
    else:
        text = "症狀記錄大致持平"
    return _mk("symptoms", contrib, text, False, r_n)


def _factor_sleep(bedside_rows, session_rows, as_of):
    """睡眠：合併床邊自由文字（bedside_logs.sleep）與睡眠量測（sleep_sessions）。"""
    recent_b, _ = _split_windows(bedside_rows, "created_at", as_of)
    poor_words = ("差", "不好", "失眠", "睡不", "難睡", "少", "淺", "poor")
    poor, counted = 0, 0
    for x in recent_b:
        s = str(x.get("sleep") or "")
        if not s:
            continue
        counted += 1
        if any(w in s for w in poor_words):
            poor += 1
    # 量測：效率/總睡眠時數偏低也算「差」
    recent_s, _ = _split_windows(session_rows, "created_at", as_of)
    for s in recent_s:
        eff = s.get("efficiency")
        mins = s.get("total_sleep_min") or s.get("duration_min")
        if eff is None and mins is None:
            continue
        counted += 1
        try:
            bad = (eff is not None and float(eff) < 80) or (mins is not None and float(mins) < 360)
        except (TypeError, ValueError):
            bad = False
        if bad:
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
    return _mk("sleep", contrib, text, True, counted)


def _factor_visits(rows, as_of):
    """就診 / 急性事件頻率：近期就診比基準頻繁 → 可能病情不穩（推升）。"""
    recent, base = _split_windows(rows, "visit_date", as_of)
    if not recent and not base:
        return None
    r_n = len(recent)
    b_rate = len(base) / max(1, (BASELINE_WINDOW - RECENT_WINDOW)) * RECENT_WINDOW
    delta = r_n - b_rate
    contrib = max(-0.04, min(0.20, delta * 0.06))
    if contrib > 0.03:
        text = "近期就診變頻繁"
    elif contrib < -0.02:
        text = "就診頻率下降"
    else:
        text = "就診頻率穩定"
    return _mk("visits", contrib, text, False, r_n)


def _factor_diet(rows, as_of):
    """飲食 / 生活型態：以紀錄活躍度當輕量代理（資料少時不過度解讀）。"""
    recent, base = _split_windows(rows, "eaten_at", as_of)
    if not recent and not base:
        return None
    r_n = len(recent)
    b_rate = len(base) / max(1, (BASELINE_WINDOW - RECENT_WINDOW)) * RECENT_WINDOW
    # 飲食紀錄變少（自我管理鬆懈）輕微推升；變多輕微降低
    delta = b_rate - r_n
    contrib = max(-0.04, min(0.10, delta * 0.02))
    if contrib > 0.02:
        text = "飲食紀錄變少，自我管理可留意"
    else:
        text = "持續記錄飲食"
    return _mk("diet", contrib, text, True, r_n)


def _factor_labs(rows, as_of):
    """檢驗：近期異常（high/critical/low）筆數相對基準上升 → 推升。"""
    recent, base = _split_windows(rows, "created_at", as_of)
    if not recent and not base:
        return None

    def _abn(rs):
        return sum(1 for x in rs if str(x.get("status") or "").lower() in ("high", "low", "critical", "abnormal"))

    r_abn = _abn(recent)
    contrib = max(-0.04, min(0.22, r_abn * 0.06))
    if contrib > 0.05:
        text = "近期檢驗有異常值"
    elif r_abn == 0 and recent:
        text = "近期檢驗數值大致正常"
    else:
        text = "檢驗數值持平"
    return _mk("labs", contrib, text, False, len(recent))


def _mk(feature, contrib, text, modifiable, data_points):
    return {
        "feature": feature,
        "label": FEATURE_LABEL.get(feature, feature),
        "value": round(contrib, 4),
        "plain_text": text,
        "modifiable": modifiable,
        "data_points": data_points,
        "disease_linked": False,   # 之後由 _apply_disease_grounding 決定
        "weight": None,
        "evidence": None,
    }


def _distinct_record_days_from(sources: dict, as_of) -> int:
    """近 60 天內有任何紀錄的「不重複天數」，用來判斷冷啟動與信心。"""
    days = set()
    cut = as_of - timedelta(days=BASELINE_WINDOW)
    for table, key, _kc, _scored in SIGNAL_TABLES:
        for r in sources.get(table, []):
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


def _baseline_for(ctx: dict) -> float:
    """疾病別起始基線：文獻復發 band → 風險錨；未知則一般基線。"""
    rec = (ctx or {}).get("recurrence") or {}
    band = rec.get("band")
    return DISEASE_BASELINE.get(band, BASE_RISK)


def compute_factors_from(sources: dict, as_of: datetime):
    """從已抓好的紀錄算每個訊號的因子貢獻（已濾掉 None；尚未套疾病加權）。"""
    raw = [
        _factor_emotion(sources.get("emotions", []), as_of),
        _factor_adherence(sources.get("medication_logs", []), as_of),
        _factor_symptoms(sources.get("symptoms_log", []), as_of),
        _factor_sleep(sources.get("bedside_logs", []), sources.get("sleep_sessions", []), as_of),
        _factor_visits(sources.get("medical_records", []), as_of),
        _factor_diet(sources.get("diet_records", []), as_of),
        _factor_labs(sources.get("labs", []), as_of),
    ]
    return [f for f in raw if f is not None]


def compute_factors(sb, patient_id: str, as_of: datetime):
    return _apply_disease_grounding(
        compute_factors_from(_load_sources(sb, patient_id), as_of),
        {},
    )


def _driver_map(ctx: dict) -> dict:
    """feature → 該疾病文獻驅動因子（maps_to 對齊 feature）。"""
    rec = (ctx or {}).get("recurrence") or {}
    out = {}
    for d in rec.get("drivers", []):
        mt = d.get("maps_to")
        if mt and mt not in out:
            out[mt] = d
    return out


def _apply_disease_grounding(factors, ctx: dict):
    """把文獻驅動因子的加權 + 引用掛到對得上的病患因子上（這就是「演算法↔此病復發」的連結）。"""
    dmap = _driver_map(ctx)
    for f in factors:
        d = dmap.get(f["feature"])
        if not d:
            continue
        f["disease_linked"] = True
        f["weight"] = d.get("weight") or "medium"
        f["evidence"] = d.get("evidence") or None
        # 文獻說此因子與此病復發相關 → 對「推升方向」的貢獻按關聯強度加權（有界）
        if f["value"] > 0:
            f["value"] = round(min(0.30, f["value"] * DRIVER_WEIGHT.get(f["weight"], 1.0)), 4)
    return factors


def score_from_factors(factors, base: float = BASE_RISK) -> float:
    total = base + sum(f["value"] for f in factors)
    return max(RISK_FLOOR, min(RISK_CEIL, total))


def risk_from(sources: dict, as_of: datetime):
    """單一時間點的完整推估（疾病別基線 + 病患紀錄因子，已套文獻加權）。"""
    ctx = sources.get("_context") or {}
    factors = _apply_disease_grounding(compute_factors_from(sources, as_of), ctx)
    return score_from_factors(factors, _baseline_for(ctx)), factors


def risk_at(sb, patient_id: str, as_of: datetime):
    return risk_from(_load_sources(sb, patient_id), as_of)


def _records_analyzed(sources: dict, as_of: datetime):
    """完整列出「分析用到病患哪些紀錄」（透明：所有紀錄都是評估核心材料）。"""
    cut = as_of - timedelta(days=BASELINE_WINDOW)
    out = []
    for table, key, _kc, scored in SIGNAL_TABLES:
        n = 0
        for r in sources.get(table, []):
            dt = _parse_dt(r.get(key) or r.get("created_at"))
            if dt and cut <= dt <= as_of:
                n += 1
        out.append({
            "table": table,
            "label": TABLE_LABEL.get(table, table),
            "count": n,
            "scored": bool(scored),
            "present": n > 0,
        })
    return out


def _top_recurrence_cause(factors, ctx: dict):
    """最可能的復發原因（預估參考）：正在惡化、且文獻證實與此病復發相關的因子排第一。

    優先取 disease_linked 的推升因子（依 weight×value）；沒有就退而取一般推升因子。
    """
    pushers = [f for f in factors if f["value"] > 0]
    if not pushers:
        return None
    w_rank = {"high": 3, "medium": 2, "low": 1}
    linked = [f for f in pushers if f.get("disease_linked")]
    pool = linked or pushers
    pool.sort(key=lambda f: (w_rank.get(f.get("weight"), 0), f["value"]), reverse=True)
    top = pool[0]
    return {
        "feature": top["feature"],
        "label": top["label"],
        "plain_text": top["plain_text"],
        "modifiable": top["modifiable"],
        "disease_linked": top.get("disease_linked", False),
        "evidence": top.get("evidence"),
    }


def _disease_block(ctx: dict) -> dict:
    """整理「疾病 / 文獻」區塊給前端（band 為主、區間文字、引用）。"""
    rec = (ctx or {}).get("recurrence") or {}
    return {
        "disease_name": (ctx or {}).get("disease_name"),
        "disease_source": (ctx or {}).get("disease_source"),
        "bound": bool((ctx or {}).get("disease_name")),
        "has_literature": bool(rec.get("band") or rec.get("drivers")),
        "recurrence_band": rec.get("band"),
        "recurrence_range_text": rec.get("range_text"),
        "recurrence_horizon": rec.get("horizon"),
        "recurrence_summary": rec.get("summary"),
        "watch_signs": rec.get("watch_signs") or [],
        "references": (ctx or {}).get("references") or [],
    }


def predict(sb, patient_id: str, as_of: Optional[datetime] = None, disease_hint: Optional[str] = None) -> dict:
    """主預測：RiskCard / ConfidenceMeter / ColdStartCard + 疾病錨 + 最可能復發原因。"""
    as_of = as_of or datetime.utcnow()
    sources = _load_sources(sb, patient_id, disease_hint)
    ctx = sources.get("_context") or {}
    data_days = _distinct_record_days_from(sources, as_of)
    disease = _disease_block(ctx)

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
            "records_analyzed": _records_analyzed(sources, as_of),
            "disease": disease,
            "horizon_days": HORIZON_DAYS,
            "disclaimer": DISCLAIMER_PREDICT,
            "generated_at": as_of.isoformat(),
        }

    risk, factors = risk_from(sources, as_of)

    # 趨勢方向：與 7 天前的推估比較（方向比絕對值重要）
    prev_risk, _ = risk_from(sources, as_of - timedelta(days=7))
    diff = risk - prev_risk
    if diff > 0.04:
        trend, trend_label = "up", "上升中"
    elif diff < -0.04:
        trend, trend_label = "down", "下降中"
    else:
        trend, trend_label = "flat", "持平"

    confidence, confidence_label = _confidence_for(data_days)
    band = _band_for(risk)
    top_driver = _top_recurrence_cause(factors, ctx)

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
        "disease": disease,
        "records_analyzed": _records_analyzed(sources, as_of),
        "low_data": data_days < 25,
        "disclaimer": DISCLAIMER_PREDICT,
        "generated_at": as_of.isoformat(),
    }


def explain(sb, patient_id: str, as_of: datetime, disease_hint: Optional[str] = None) -> dict:
    """畫面 C：每個因子攤成 SHAP-like 水平條（紅推升/藍降低）+ 文獻根據 + 要注意什麼。"""
    sources = _load_sources(sb, patient_id, disease_hint)
    ctx = sources.get("_context") or {}
    risk, factors = risk_from(sources, as_of)
    data_days = _distinct_record_days_from(sources, as_of)
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
            "disease_linked": f.get("disease_linked", False),
            "evidence": f.get("evidence"),
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
        "top_driver": _top_recurrence_cause(factors, ctx),
        "disease": _disease_block(ctx),
        "disclaimer": DISCLAIMER_SHAP,
    }


def trend_series(sb, patient_id: str, window_days: int, as_of: Optional[datetime] = None,
                 disease_hint: Optional[str] = None) -> dict:
    """畫面 B：時間序列風險線 + 信心區間 + 實際 flare 事件標記。

    為了效能，沿時間窗取約 24 個取樣點，每點以該日為 as_of 重新推估（決定性 → 可重現）。
    一次抓齊原始資料（含疾病脈絡），所有取樣點在記憶體內重算（不重複查 DB → 不逾時）。
    """
    as_of = as_of or datetime.utcnow()
    window_days = max(7, min(180, window_days))
    n_points = 24
    step = max(1, window_days // n_points)

    sources = _load_sources(sb, patient_id, disease_hint)

    points = []
    d = window_days
    while d >= 0:
        sample_dt = as_of - timedelta(days=d)
        risk, _ = risk_from(sources, sample_dt)
        dd = _distinct_record_days_from(sources, sample_dt)
        half = max(0.05, 0.18 - (min(dd, 45) / 45.0) * 0.13)
        pct = risk * 100
        points.append({
            "date": sample_dt.date().isoformat(),
            "risk_percent": round(pct),
            "confidence_low": round(max(0, pct - half * 100)),
            "confidence_high": round(min(100, pct + half * 100)),
        })
        d -= step

    # 實際發生過的事件（✦）：就診紀錄當作可觀察的臨床事件標記（重用已載入的 medical_records）
    flare_events = []
    cut = as_of - timedelta(days=window_days)
    for r in sources.get("medical_records", []):
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
        "disease": _disease_block(sources.get("_context") or {}),
        "disclaimer": DISCLAIMER_PREDICT,
    }
