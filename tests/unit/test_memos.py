"""memos 路由的單元測試（SQLite fallback，絕不碰線上 Supabase）。

鎖住「為什麼重要」（規則 9）：
- 備忘必須真的寫進 DB，且欄位對映正確
  （前端 type/text/photo/forDoctor ↔ DB kind/content/photo_data/for_doctor）。
- 以 client_id 幂等：同一 client_id 再送是「覆蓋」而非新增——
  這正是「編輯」與「開 App 補傳本機既有 memo」不會產生重複的保證。
- 刪除依 (patient_id, client_id) 精準刪；不同病患同 client_id 不互相干擾。
若有人把 upsert 改回每次都 insert、或把欄位對映寫錯，這些測試會立刻變紅。
"""
import os
import tempfile

import pytest


@pytest.fixture
def memos_mod():
    # 強制走 SQLite：db.py 預設會指向 production Supabase，這裡務必清掉。
    import backend.db as db
    db.SUPABASE_URL = None
    db.SUPABASE_KEY = None
    db._client = None
    db.DB_PATH = tempfile.mktemp(suffix=".db")
    db._init_db()
    from backend.routers import memos
    yield memos
    try:
        os.remove(db.DB_PATH)
    except OSError:
        pass


def test_upsert_then_list_maps_fields(memos_mod):
    memos_mod.upsert_memo(memos_mod.MemoUpsert(
        patient_id="p1", client_id="m_1",
        kind="text", content="記得問醫師血壓藥", for_doctor=True,
    ))
    out = memos_mod.list_memos(patient_id="p1")["memos"]
    assert len(out) == 1
    m = out[0]
    assert m["id"] == "m_1"
    assert m["type"] == "text"
    assert m["text"] == "記得問醫師血壓藥"
    assert m["forDoctor"] is True


def test_for_doctor_false_round_trips(memos_mod):
    # bool 在 SQLite 存成 0/1，務必還原成 False（不是「非空字串都 True」那種 bug）
    memos_mod.upsert_memo(memos_mod.MemoUpsert(
        patient_id="p1", client_id="m_self", content="只給自己看", for_doctor=False))
    out = memos_mod.list_memos(patient_id="p1")["memos"]
    assert out[0]["forDoctor"] is False


def test_upsert_is_idempotent_on_client_id(memos_mod):
    for _ in range(3):
        memos_mod.upsert_memo(memos_mod.MemoUpsert(
            patient_id="p1", client_id="m_dup", content="一樣的 memo"))
    out = memos_mod.list_memos(patient_id="p1")["memos"]
    assert len(out) == 1  # 三次送出仍只有一筆


def test_edit_overwrites_same_client_id(memos_mod):
    memos_mod.upsert_memo(memos_mod.MemoUpsert(
        patient_id="p1", client_id="m_e", content="舊內容"))
    memos_mod.upsert_memo(memos_mod.MemoUpsert(
        patient_id="p1", client_id="m_e", content="新內容", for_doctor=True))
    out = memos_mod.list_memos(patient_id="p1")["memos"]
    assert len(out) == 1
    assert out[0]["text"] == "新內容"
    assert out[0]["forDoctor"] is True


def test_delete_removes_only_that_memo(memos_mod):
    memos_mod.upsert_memo(memos_mod.MemoUpsert(patient_id="p1", client_id="m_a", content="A"))
    memos_mod.upsert_memo(memos_mod.MemoUpsert(patient_id="p1", client_id="m_b", content="B"))
    memos_mod.delete_memo(patient_id="p1", client_id="m_a")
    out = memos_mod.list_memos(patient_id="p1")["memos"]
    assert [m["id"] for m in out] == ["m_b"]


def test_memos_scoped_per_patient(memos_mod):
    # 同一 client_id 但不同病患 → 各自一筆，互不污染
    memos_mod.upsert_memo(memos_mod.MemoUpsert(patient_id="p1", client_id="m1", content="病患1"))
    memos_mod.upsert_memo(memos_mod.MemoUpsert(patient_id="p2", client_id="m1", content="病患2"))
    out1 = memos_mod.list_memos(patient_id="p1")["memos"]
    assert len(out1) == 1
    assert out1[0]["text"] == "病患1"
