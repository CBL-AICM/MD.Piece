"""新增端點整合測試（使用 FastAPI TestClient + SQLite）"""
import os
import sys
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# 用臨時 db
TEST_DB = tempfile.NamedTemporaryFile(delete=False, suffix=".db").name
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)


@pytest.fixture(scope="module")
def client():
    # patch db path before import
    import backend.db as db
    db.DB_PATH = TEST_DB
    db._client = None
    db._db_initialized = False

    from backend.main import app
    return TestClient(app)


def test_questionnaire_schema(client):
    r = client.get("/symptoms/questionnaire")
    assert r.status_code == 200
    data = r.json()
    assert len(data["layers"]) == 5


def test_disease_knowledge_includes_not_your_disease(client):
    r = client.get("/education/knowledge/M06")
    assert r.status_code == 200
    data = r.json()
    assert "not_your_disease" in data
    assert any("退化性" in nyd["name"] for nyd in data["not_your_disease"])


def test_disease_knowledge_unknown_404(client):
    r = client.get("/education/knowledge/Z99")
    assert r.status_code == 404


def test_emergency_symptom_list(client):
    r = client.get("/triage/emergency-symptoms")
    assert r.status_code == 200
    syms = r.json()["symptoms"]
    assert "胸痛" in syms
    assert "中風症狀" in syms


def test_lab_codes(client):
    r = client.get("/vitals/lab-codes")
    assert r.status_code == 200
    codes = [c["code"] for c in r.json()["codes"]]
    assert "CRP" in codes
    assert "HbA1c" in codes


def test_lab_translate(client):
    r = client.post("/vitals/translate", json={"code": "CRP", "value": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == "normal"


def test_xiaohe_silent_guardian_stable_when_no_data(client):
    r = client.get("/xiaohe/silent-guardian/test-user-no-data")
    assert r.status_code == 200
    assert r.json()["level"] == "stable"


def test_priority_returns_list(client):
    r = client.get("/doctor-dashboard/priority")
    assert r.status_code == 200
    body = r.json()
    assert "patients" in body
    assert "total" in body


def test_5layer_submit_then_baseline(client):
    # Create patient first
    pres = client.post("/patients/", json={"name": "測試患者", "age": 50})
    assert pres.status_code == 200
    patient_id = pres.json()["id"]

    # Submit a few day's worth of records
    for sev in [3, 4, 3, 5, 4, 6, 7]:
        r = client.post("/symptoms/questionnaire/submit", json={
            "patient_id": patient_id,
            "overall_feeling": "uncomfortable",
            "body_locations": ["left_knee"],
            "symptom_types": ["pain"],
            "severity": sev,
            "change_pattern": "same",
        })
        assert r.status_code == 200

    # Heatmap should show left_knee
    r = client.get(f"/symptoms/heatmap/{patient_id}")
    assert r.status_code == 200
    keys = [h["key"] for h in r.json()["heatmap"]]
    assert "left_knee" in keys

    # Baseline
    r = client.get(f"/triage/baseline/{patient_id}")
    assert r.status_code == 200
    baseline = r.json()["baseline"]
    assert baseline["data_points"] >= 1


def test_timeline_empty_patient(client):
    pres = client.post("/patients/", json={"name": "時間軸測試", "age": 35})
    pid = pres.json()["id"]
    r = client.get(f"/timeline/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["events"] == []


def test_compare_visits_needs_two(client):
    pres = client.post("/patients/", json={"name": "跨回診測試", "age": 40})
    pid = pres.json()["id"]
    r = client.get(f"/timeline/{pid}/compare")
    assert r.status_code == 200
    assert r.json()["comparison"] is None
