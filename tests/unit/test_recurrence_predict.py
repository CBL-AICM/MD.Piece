"""復發風險預測引擎（backend/utils/recurrence.py）的回歸測試。

鎖住兩件「為什麼重要」的事（規則 9）：

  1. 查詢次數有上限、與取樣點數無關。
     trend 會沿時間窗取數十個點，若每點都重新查 DB，在 serverless 上會逾時，
     前端就顯示「載入失敗」。本測試用會計次的假 Supabase client：window 從 7
     拉到 180、取樣點數從幾個變二十幾個，但來源表查詢次數必須維持個位數。
     若有人把「先抓一次、記憶體內重算」改回「每點各自查」，這裡會立刻變紅。

  2. 冷啟動門檻是真的依「有紀錄的天數」判斷，不是寫死。
     資料不足必須回 cold_start（不給誤導性數字）；資料足夠才給 band。
"""

from datetime import datetime, timedelta

from backend.utils import recurrence as r


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, store, table):
        self.store, self.table = store, table

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        self.store["count"] += 1
        return _FakeResult(self.store["rows"].get(self.table, []))


class _FakeSB:
    """記錄被查詢過幾次，並回傳預先準備好的資料列。"""

    def __init__(self, rows):
        self.store = {"count": 0, "rows": rows}

    def table(self, name):
        return _FakeQuery(self.store, name)


_AS_OF = datetime(2026, 6, 1)


def _rich_rows(days=45):
    """造 days 天的情緒 + 服藥紀錄，確保越過冷啟動門檻。"""
    emo = [{"patient_id": "p", "score": 2,
            "created_at": (_AS_OF - timedelta(days=i)).isoformat()} for i in range(days)]
    meds = [{"patient_id": "p", "taken": True,
             "taken_at": (_AS_OF - timedelta(days=i)).isoformat()} for i in range(days)]
    return {"emotions": emo, "medication_logs": meds,
            "symptoms_log": [], "bedside_logs": [], "medical_records": []}


# ── 1. 查詢次數與取樣點數脫鉤（核心回歸）──────────────────────

def test_trend_queries_do_not_scale_with_window():
    """window 越大取樣點越多，但來源表只該被抓一次 → 查詢數必須與取樣點數脫鉤。"""
    counts = {}
    for window in (7, 30, 90, 180):
        sb = _FakeSB(_rich_rows())
        out = r.trend_series(sb, "p", window, as_of=_AS_OF)
        counts[window] = (len(out["points"]), sb.store["count"])

    # 取樣點數應隨 window 變多（證明確實有多點，不是只算一個點魚目混珠）
    assert counts[180][0] > counts[7][0]

    # 核心回歸：查詢次數必須「與 window/取樣點數無關」=> 四個 window 完全相同。
    # 若有人把「先抓一次、記憶體內重算」改回「每點各自查」，window=180 會是上百次，
    # 這個相等斷言會立刻變紅。
    query_counts = {w: v[1] for w, v in counts.items()}
    assert len(set(query_counts.values())) == 1, f"查詢數隨 window 變動了：{query_counts}"

    # 並給一個與「掃齊所有紀錄表 + 疾病脈絡」相稱的常數上限（無疾病時不查 disease_reference）。
    for window, (n_points, n_queries) in counts.items():
        assert n_queries <= 12, f"window={window} 用了 {n_queries} 次查詢（取樣 {n_points} 點）— 疑似每點重複查 DB"


def test_predict_and_explain_query_budget():
    """predict / explain 也不該重複載入來源表（與取樣/重算次數無關的常數級查詢）。"""
    sb = _FakeSB(_rich_rows())
    r.predict(sb, "p", as_of=_AS_OF)
    assert sb.store["count"] <= 12

    sb2 = _FakeSB(_rich_rows())
    r.explain(sb2, "p", _AS_OF)
    assert sb2.store["count"] <= 12


# ── 2. 冷啟動門檻依真實天數，不是寫死 ────────────────────────

def test_cold_start_when_insufficient_history():
    sb = _FakeSB(_rich_rows(days=5))      # 只有 5 天 < THRESHOLD_DAYS(14)
    out = r.predict(sb, "p", as_of=_AS_OF)
    assert out["cold_start"] is True
    assert out["data_days"] == 5
    assert out["days_remaining"] == r.THRESHOLD_DAYS - 5
    # 冷啟動時不可給出會誤導的 band / 百分比
    assert "risk_band" not in out


def test_predict_returns_band_when_enough_history():
    sb = _FakeSB(_rich_rows(days=45))
    out = r.predict(sb, "p", as_of=_AS_OF)
    assert out["cold_start"] is False
    assert out["risk_band"] in ("low", "medium", "high")
    assert 0 <= out["risk_percent"] <= 100
    assert out["confidence_label"] in ("低", "中", "高")


def test_no_data_is_cold_start_not_fake_zero():
    """完全沒資料 → 冷啟動，而非謊報 0%（規則 12：禁止隱性失敗 / 假資料）。"""
    sb = _FakeSB({})
    out = r.predict(sb, "p", as_of=_AS_OF)
    assert out["cold_start"] is True
    assert out["data_days"] == 0


# ── 3. trend 取樣點與單點推估一致（決定性、可重現）──────────

def test_trend_point_matches_direct_risk_estimate():
    """趨勢線上某一天的風險，必須等於直接對那天做的推估（同一套決定性邏輯）。"""
    rows = _rich_rows(days=60)
    sb = _FakeSB(rows)
    out = r.trend_series(sb, "p", 30, as_of=_AS_OF)

    sources = r._load_sources(_FakeSB(rows), "p")
    for pt in out["points"]:
        day = datetime.fromisoformat(pt["date"])
        expected_risk, _ = r.risk_from(sources, day)
        assert pt["risk_percent"] == round(expected_risk * 100)


# ── 4. 疾病別錨：演算法確實「連結到 user 的疾病復發」（核心需求）──────

def _rows_with_disease(rec_data, days=45, low_score=2):
    rows = _rich_rows(days=days)
    rows["emotions"] = [{"patient_id": "p", "score": low_score,
                         "created_at": (_AS_OF - timedelta(days=i)).isoformat()} for i in range(days)]
    rows["patient_profiles"] = [{"user_id": "p", "current_disease": "高血壓"}]
    rows["disease_reference"] = [{
        "id": "d1", "name_zh": "高血壓", "name_en": "Hypertension",
        "aliases": ["高血壓"], "recurrence_data": rec_data,
        "references_data": [{"title": "BP control & recurrence", "pmid": "123", "url": "u"}],
    }]
    return rows


def _rec(band, drivers=None):
    return {
        "matched": True, "name_zh": "高血壓", "name_en": "Hypertension",
        "recurrence_rate": {"band": band, "range_text": "5 年內約 20–30%",
                            "horizon": "5 年", "summary": "好好控制血壓可降低復發"},
        "drivers": drivers or [],
        "watch_signs": ["頭痛、頭暈持續不退"],
        "disclaimer": "此為文獻整理，非個人診斷。",
    }


def test_disease_band_sets_baseline():
    """同樣的病患紀錄，疾病文獻復發 band 越高 → 起始風險越高（證明錨真的接到疾病復發）。

    若有人把疾病別基線改回固定 0.15，high 與 low 會相等，這裡就會變紅。
    """
    hi = r.predict(_FakeSB(_rows_with_disease(_rec("high"))), "p", as_of=_AS_OF)
    lo = r.predict(_FakeSB(_rows_with_disease(_rec("low"))), "p", as_of=_AS_OF)
    assert hi["risk_percent"] > lo["risk_percent"]
    assert hi["disease"]["recurrence_band"] == "high"
    assert hi["disease"]["bound"] is True
    assert hi["disease"]["has_literature"] is True


def test_disease_literature_and_watch_signs_surface():
    """疾病區塊要帶出文獻區間、徵兆與引用（『要注意什麼』有根據）。"""
    out = r.predict(_FakeSB(_rows_with_disease(_rec("medium"))), "p", as_of=_AS_OF)
    d = out["disease"]
    assert d["disease_name"] == "高血壓"
    assert d["recurrence_range_text"]
    assert "頭痛、頭暈持續不退" in d["watch_signs"]
    assert d["references"] and d["references"][0].get("pmid") == "123"


def test_no_disease_is_honest_not_fabricated():
    """沒綁定疾病 → bound=False、has_literature=False，且不捏造復發率（規則 12）。"""
    out = r.predict(_FakeSB(_rich_rows()), "p", as_of=_AS_OF)
    assert out["disease"]["bound"] is False
    assert out["disease"]["has_literature"] is False
    assert out["disease"]["recurrence_band"] is None


def test_top_cause_prefers_disease_linked_driver():
    """最可能的復發原因：優先挑『正在惡化且文獻證實與此病復發相關』的因子，並帶出 evidence。"""
    drivers = [{"label": "壓力", "maps_to": "stress", "direction": "up",
                "weight": "high", "modifiable": True,
                "plain_text": "長期壓力與血壓控制不佳有關",
                "evidence": "文獻顯示慢性壓力與高血壓復發相關"}]
    out = r.predict(_FakeSB(_rows_with_disease(_rec("medium", drivers), low_score=2)), "p", as_of=_AS_OF)
    td = out["top_driver"]
    assert td is not None
    assert td["feature"] == "stress"
    assert td["disease_linked"] is True
    assert td["evidence"]


def test_records_analyzed_lists_all_record_types():
    """透明：predict 要回報分析用到病患哪些紀錄（所有紀錄都是評估核心材料）。"""
    out = r.predict(_FakeSB(_rich_rows()), "p", as_of=_AS_OF)
    tables = {row["table"] for row in out["records_analyzed"]}
    for table, _date, _key, _scored in r.SIGNAL_TABLES:
        assert table in tables
