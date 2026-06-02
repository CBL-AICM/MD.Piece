"""symptoms /entries（症狀日記）的單元測試（SQLite，不碰線上 Supabase）。

鎖住為什麼重要（規則 9）：
- 症狀日記必須真的寫進 symptom_entries，且欄位對映正確
  （前端 categoryId/intensity/frequency/notes/recordedAt ↔ DB 欄位）。
- (patient_id, client_id) 幂等：編輯與「開 App 補傳本機既有」不會產生重複。
- 刪除精準；不同病患同 client_id 不互相干擾。
- 與 symptoms_log（AI 分析紀錄）分屬不同表，寫日記不污染分析紀錄。
"""
import pytest


@pytest.fixture
def sym(tmp_path):
    import backend.db as db
    db.SUPABASE_URL = None
    db.SUPABASE_KEY = None
    db._client = None
    db.DB_PATH = str(tmp_path / "sym.db")
    db._init_db()
    from backend.routers import symptoms
    return symptoms


def test_upsert_then_list_maps_fields(sym):
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(
        patient_id="p1", client_id="s_1", category_id="headache",
        intensity=4, frequency=2, notes="後腦勺悶痛",
        recorded_at="2026-06-01T08:00:00+00:00"))
    out = sym.list_symptom_entries(patient_id="p1")["entries"]
    assert len(out) == 1
    e = out[0]
    assert e["id"] == "s_1"
    assert e["categoryId"] == "headache"
    assert e["intensity"] == 4
    assert e["frequency"] == 2
    assert e["notes"] == "後腦勺悶痛"
    assert e["recordedAt"] == "2026-06-01T08:00:00+00:00"


def test_idempotent_on_client_id(sym):
    for _ in range(3):
        sym.upsert_symptom_entry(sym.SymptomEntryUpsert(
            patient_id="p1", client_id="s_dup", category_id="fatigue", intensity=3))
    out = sym.list_symptom_entries(patient_id="p1")["entries"]
    assert len(out) == 1


def test_edit_overwrites_same_client_id(sym):
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(
        patient_id="p1", client_id="s_e", category_id="headache", intensity=2))
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(
        patient_id="p1", client_id="s_e", category_id="headache", intensity=5, notes="變嚴重"))
    out = sym.list_symptom_entries(patient_id="p1")["entries"]
    assert len(out) == 1
    assert out[0]["intensity"] == 5
    assert out[0]["notes"] == "變嚴重"


def test_delete_only_that_entry(sym):
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(patient_id="p1", client_id="s_a", category_id="cough"))
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(patient_id="p1", client_id="s_b", category_id="fever"))
    sym.delete_symptom_entry(patient_id="p1", client_id="s_a")
    out = sym.list_symptom_entries(patient_id="p1")["entries"]
    assert [e["id"] for e in out] == ["s_b"]


def test_scoped_per_patient(sym):
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(patient_id="p1", client_id="s1", notes="病患1"))
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(patient_id="p2", client_id="s1", notes="病患2"))
    out1 = sym.list_symptom_entries(patient_id="p1")["entries"]
    assert len(out1) == 1
    assert out1[0]["notes"] == "病患1"


def test_entries_separate_from_symptoms_log(sym):
    # 寫症狀日記不應寫進 symptoms_log（AI 分析紀錄表），兩者分開
    sym.upsert_symptom_entry(sym.SymptomEntryUpsert(patient_id="p1", client_id="s1", category_id="headache"))
    hist = sym.get_symptom_history(patient_id="p1")["history"]
    assert hist == []
