"""vitals（生理量測）路由的單元測試（SQLite，不碰線上）。

鎖住為什麼重要（規則 9）：
- 量測必須真的寫進 vital_entries，欄位對映正確（含雙值血壓 value/value2）。
- (patient_id, client_id) 幂等：補傳/編輯不重複。
- 刪除精準；跨病患隔離。
"""
import pytest


@pytest.fixture
def vit(tmp_path):
    import backend.db as db
    db.SUPABASE_URL = None
    db.SUPABASE_KEY = None
    db._client = None
    db.DB_PATH = str(tmp_path / "vit.db")
    db._init_db()
    from backend.routers import vitals
    return vitals


def test_upsert_then_list_maps_fields(vit):
    vit.upsert_vital(vit.VitalUpsert(
        patient_id="p1", client_id="v_1", metric_id="bp",
        value=128, value2=82, context="morning", notes="飯前",
        recorded_at="2026-06-01T07:00:00+00:00"))
    out = vit.list_vitals(patient_id="p1")["entries"]
    assert len(out) == 1
    e = out[0]
    assert e["id"] == "v_1"
    assert e["metricId"] == "bp"
    assert e["value"] == 128
    assert e["value2"] == 82
    assert e["context"] == "morning"
    assert e["recordedAt"] == "2026-06-01T07:00:00+00:00"


def test_idempotent_on_client_id(vit):
    for _ in range(3):
        vit.upsert_vital(vit.VitalUpsert(patient_id="p1", client_id="v_d", metric_id="weight", value=70))
    assert len(vit.list_vitals(patient_id="p1")["entries"]) == 1


def test_edit_overwrites_same_client_id(vit):
    vit.upsert_vital(vit.VitalUpsert(patient_id="p1", client_id="v_e", metric_id="weight", value=70))
    vit.upsert_vital(vit.VitalUpsert(patient_id="p1", client_id="v_e", metric_id="weight", value=68.5))
    out = vit.list_vitals(patient_id="p1")["entries"]
    assert len(out) == 1
    assert out[0]["value"] == 68.5


def test_delete_only_that_entry(vit):
    vit.upsert_vital(vit.VitalUpsert(patient_id="p1", client_id="v_a", metric_id="bp", value=120))
    vit.upsert_vital(vit.VitalUpsert(patient_id="p1", client_id="v_b", metric_id="bp", value=130))
    vit.delete_vital(patient_id="p1", client_id="v_a")
    out = vit.list_vitals(patient_id="p1")["entries"]
    assert [e["id"] for e in out] == ["v_b"]


def test_scoped_per_patient(vit):
    vit.upsert_vital(vit.VitalUpsert(patient_id="p1", client_id="v1", metric_id="weight", value=70))
    vit.upsert_vital(vit.VitalUpsert(patient_id="p2", client_id="v1", metric_id="weight", value=80))
    out1 = vit.list_vitals(patient_id="p1")["entries"]
    assert len(out1) == 1
    assert out1[0]["value"] == 70
