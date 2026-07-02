"""menstrual router 整合測試 — 用本地 SQLite fallback。

驗證「為什麼」而非只是「有沒有」（規則 9）：
  - summary 的平均週期長度是相鄰兩次經期起始日的天數差——若有人把它寫死，
    test_summary_computes_cycle_and_estimate 會失敗。
  - 預估下次 = 上次起始 + 平均週期，且必帶 estimate=True + 「僅供參考」字樣（法規紅線）。
  - daily 以 (patient_id, date) upsert：同一天再寫一次是更新不是新增一列。
"""

from datetime import date, timedelta

import pytest

from fastapi.testclient import TestClient

from backend.main import app

PATIENT_ID = "menstrual-test-1"
client = TestClient(app)  # menstrual router 不強制 JWT（同 admissions/inpatient）


def _add_cycle(start, end=None, flow=None, symptoms=None):
    body = {"patient_id": PATIENT_ID, "start_date": start}
    if end:
        body["end_date"] = end
    if flow:
        body["flow"] = flow
    if symptoms is not None:
        body["symptoms"] = symptoms
    r = client.post("/menstrual/cycles", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_cycle_crud_and_symptoms_roundtrip():
    c = _add_cycle("2026-05-01", "2026-05-05", "medium", ["經痛", "情緒低落"])
    assert c["symptoms"] == ["經痛", "情緒低落"]
    assert c["flow"] == "medium"

    lst = client.get("/menstrual/cycles", params={"patient_id": PATIENT_ID})
    assert lst.status_code == 200
    assert len(lst.json()["cycles"]) == 1

    upd = client.put(f"/menstrual/cycles/{c['id']}", json={"flow": "heavy"})
    assert upd.status_code == 200 and upd.json()["flow"] == "heavy"

    dele = client.delete(f"/menstrual/cycles/{c['id']}")
    assert dele.status_code == 200
    assert client.get("/menstrual/cycles", params={"patient_id": PATIENT_ID}).json()["cycles"] == []


def test_cycle_validation():
    # end 早於 start 要擋
    bad = client.post("/menstrual/cycles", json={
        "patient_id": PATIENT_ID, "start_date": "2026-05-10", "end_date": "2026-05-01"})
    assert bad.status_code == 400
    # 非法 flow 要擋
    bad2 = client.post("/menstrual/cycles", json={
        "patient_id": PATIENT_ID, "start_date": "2026-05-10", "flow": "huge"})
    assert bad2.status_code == 400
    # 壞日期格式要擋
    bad3 = client.post("/menstrual/cycles", json={"patient_id": PATIENT_ID, "start_date": "2026/05/10"})
    assert bad3.status_code == 400


def test_summary_computes_cycle_and_estimate():
    """週期長度 = 相鄰起始日天數差；預估下次 = 上次起始 + 平均週期。"""
    # 三次經期，起始間隔 28、30 天（平均 29）
    _add_cycle("2026-03-01", "2026-03-05")
    _add_cycle("2026-03-29", "2026-04-02")   # +28
    _add_cycle("2026-04-28", "2026-05-02")   # +30

    s = client.get("/menstrual/summary", params={"patient_id": PATIENT_ID})
    assert s.status_code == 200, s.text
    body = s.json()

    assert body["cycle_count"] == 3
    assert body["recent_cycle_lengths"] == [28, 30]
    assert body["avg_cycle_length"] == 29            # round((28+30)/2)
    assert body["avg_period_length"] == 5            # 每次 3/1..3/5 = 5 天
    assert body["last_start"] == "2026-04-28"
    # 預估下次 = 2026-04-28 + 29 天 = 2026-05-27
    assert body["estimated_next_start"] == "2026-05-27"
    assert body["estimate"] is True
    # 法規紅線：估算必須標「僅供參考 / 非醫學預測」；摘要不對週期下「正常/異常」判斷，
    # 且免責聲明明確聲明「不判斷」、「不做診斷」（intent，而非單純字串比對）。
    assert "估" in body["estimate_note"]
    assert "不判斷" in body["disclaimer"] and "不做醫療診斷" in body["disclaimer"]
    # 回傳結構裡不得出現任何「正常/異常」分類欄位
    assert not any(k for k in body if "normal" in k.lower() or "abnormal" in k.lower())


def test_summary_insufficient_data_no_estimate():
    """只有一次經期 → 無法算週期 → 不預估（estimate=False）。"""
    _add_cycle("2026-05-01", "2026-05-05")
    body = client.get("/menstrual/summary", params={"patient_id": PATIENT_ID}).json()
    assert body["avg_cycle_length"] is None
    assert body["estimated_next_start"] is None
    assert body["estimate"] is False


def test_daily_upsert_by_date():
    """同一天再寫一次是更新（不是新增第二列）。"""
    r1 = client.post("/menstrual/daily", json={
        "patient_id": PATIENT_ID, "date": "2026-05-10", "bbt_c": 36.5, "pill_taken": True})
    assert r1.status_code == 200 and r1.json()["_upserted"] == "created"

    r2 = client.post("/menstrual/daily", json={
        "patient_id": PATIENT_ID, "date": "2026-05-10", "bbt_c": 36.7, "ovulation_test": "positive"})
    assert r2.status_code == 200 and r2.json()["_upserted"] == "updated"

    lst = client.get("/menstrual/daily", params={"patient_id": PATIENT_ID})
    rows = lst.json()["daily"]
    assert len(rows) == 1                         # 仍是一列
    assert rows[0]["bbt_c"] == 36.7
    assert rows[0]["ovulation_test"] == "positive"
    assert rows[0]["pill_taken"] == 1             # 第一次寫的 pill_taken 保留

    # 非法排卵試紙值要擋
    bad = client.post("/menstrual/daily", json={
        "patient_id": PATIENT_ID, "date": "2026-05-11", "ovulation_test": "maybe"})
    assert bad.status_code == 400
