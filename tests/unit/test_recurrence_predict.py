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
    """window 越大取樣點越多，但來源表只該被抓一次，總查詢數維持個位數。"""
    counts = {}
    for window in (7, 30, 90, 180):
        sb = _FakeSB(_rich_rows())
        out = r.trend_series(sb, "p", window, as_of=_AS_OF)
        counts[window] = (len(out["points"]), sb.store["count"])

    # 取樣點數應隨 window 變多（證明確實有多點，不是只算一個點魚目混珠）
    assert counts[180][0] > counts[7][0]

    # 但每個 window 的查詢次數都該是常數級（4 來源表 + medical_records = 5，
    # 給一點寬容上限 8）。若改回每點查一次，window=180 會是上百次 → 爆掉。
    for window, (n_points, n_queries) in counts.items():
        assert n_queries <= 8, f"window={window} 用了 {n_queries} 次查詢（取樣 {n_points} 點）— 疑似每點重複查 DB"


def test_predict_and_explain_query_budget():
    """predict / explain 也不該重複載入來源表。"""
    sb = _FakeSB(_rich_rows())
    r.predict(sb, "p", as_of=_AS_OF)
    assert sb.store["count"] <= 5

    sb2 = _FakeSB(_rich_rows())
    r.explain(sb2, "p", _AS_OF)
    assert sb2.store["count"] <= 5


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
