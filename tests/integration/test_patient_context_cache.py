"""compute_patient_context TTL 快取測試 — 確認小禾連續對話不會每則都打 4 次 DB。

規則 9：驗證「為什麼」——快取存在的理由是省掉重複 DB 往返（降低小禾首字延遲）。
若有人把快取拿掉，test_context_cache_avoids_repeat_db_calls 會失敗。
"""

import pytest

import backend.db as db_mod
import backend.services.llm_service as llm

PID = "ctx-cache-test"


@pytest.fixture(autouse=True)
def _reset():
    # DB 隔離由 tests/conftest.py 統一處理；這裡只需重置 llm_service 的
    # in-process 病患脈絡快取，避免上一個測試的快取洩漏到下一個。
    llm._CTX_CACHE.clear()
    llm._CTX_TTL_SEC = 120.0
    yield


def _count_table_calls():
    """包住 get_supabase().table 以計數 DB round-trips。回傳 (sb, calls_dict)。"""
    sb = db_mod.get_supabase()
    calls = {"n": 0}
    orig = sb.table

    def counting(name):
        calls["n"] += 1
        return orig(name)

    sb.table = counting
    db_mod.get_supabase = lambda: sb  # compute_patient_context 內部會 local import 這個
    return sb, calls


def test_context_cache_avoids_repeat_db_calls():
    sb, calls = _count_table_calls()
    sb.table("symptoms_log").insert({"patient_id": PID, "symptoms": "頭痛"}).execute()
    calls["n"] = 0

    c1 = llm.compute_patient_context(PID)
    first = calls["n"]
    c2 = llm.compute_patient_context(PID)
    delta = calls["n"] - first

    assert first > 0, "第一次應該真的查 DB"
    assert delta == 0, "TTL 內第二次應命中快取、零 DB 查詢"
    assert c1 == c2
    assert c1.record_count == 1


def test_context_cache_expires():
    sb, calls = _count_table_calls()
    sb.table("symptoms_log").insert({"patient_id": PID, "symptoms": "頭痛"}).execute()

    llm.compute_patient_context(PID)
    n_after_first = calls["n"]
    llm._CTX_TTL_SEC = -1  # 立即過期
    llm.compute_patient_context(PID)
    assert calls["n"] > n_after_first, "TTL 過期後應重新查 DB"
