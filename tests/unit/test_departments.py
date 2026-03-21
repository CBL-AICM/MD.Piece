"""
Unit tests for departments router.
Uses FastAPI TestClient with mocked Supabase.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Patch supabase before importing app
mock_sb = MagicMock()

with patch("backend.db.get_supabase", return_value=mock_sb):
    from backend.main import app

client = TestClient(app)

SAMPLE_DEPT = {
    "id": "dept-uuid-1",
    "name": "內科",
    "code": "IM",
    "description": "內科疾病診治",
    "created_at": "2026-03-20T00:00:00Z",
    "updated_at": "2026-03-20T00:00:00Z",
}


def _mock_table(data, *, single=False):
    """Helper: return a mock chain that resolves to given data."""
    result = MagicMock()
    result.data = [data] if single else data
    chain = MagicMock()
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.order.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = result
    return chain


# ─── GET /departments/ ────────────────────────────────────

def test_get_departments_empty():
    mock_sb.table.return_value = _mock_table([])
    res = client.get("/departments/")
    assert res.status_code == 200
    assert res.json() == {"departments": []}


def test_get_departments_with_data():
    mock_sb.table.return_value = _mock_table([SAMPLE_DEPT])
    res = client.get("/departments/")
    assert res.status_code == 200
    data = res.json()
    assert len(data["departments"]) == 1
    assert data["departments"][0]["name"] == "內科"


# ─── GET /departments/{id} ────────────────────────────────

def test_get_department_found():
    mock_sb.table.return_value = _mock_table([SAMPLE_DEPT])
    res = client.get("/departments/dept-uuid-1")
    assert res.status_code == 200
    assert res.json()["name"] == "內科"


def test_get_department_not_found():
    mock_sb.table.return_value = _mock_table([])
    res = client.get("/departments/nonexistent")
    assert res.status_code == 404


# ─── POST /departments/ ───────────────────────────────────

def test_create_department():
    mock_sb.table.return_value = _mock_table([SAMPLE_DEPT])
    res = client.post("/departments/", json={"name": "內科", "code": "IM", "description": "內科疾病診治"})
    assert res.status_code == 200
    assert res.json()["name"] == "內科"


def test_create_department_minimal():
    dept = {**SAMPLE_DEPT, "code": None, "description": None}
    mock_sb.table.return_value = _mock_table([dept])
    res = client.post("/departments/", json={"name": "家醫科"})
    assert res.status_code == 200


# ─── PUT /departments/{id} ────────────────────────────────

def test_update_department():
    updated = {**SAMPLE_DEPT, "description": "更新說明"}
    mock_sb.table.return_value = _mock_table([updated])
    res = client.put("/departments/dept-uuid-1", json={"description": "更新說明"})
    assert res.status_code == 200
    assert res.json()["description"] == "更新說明"


def test_update_department_no_data():
    res = client.put("/departments/dept-uuid-1", json={})
    assert res.status_code == 400


def test_update_department_not_found():
    mock_sb.table.return_value = _mock_table([])
    res = client.put("/departments/nonexistent", json={"name": "X"})
    assert res.status_code == 404


# ─── DELETE /departments/{id} ────────────────────────────

def test_delete_department():
    mock_sb.table.return_value = _mock_table([SAMPLE_DEPT])
    res = client.delete("/departments/dept-uuid-1")
    assert res.status_code == 200
    assert res.json()["id"] == "dept-uuid-1"


def test_delete_department_not_found():
    mock_sb.table.return_value = _mock_table([])
    res = client.delete("/departments/nonexistent")
    assert res.status_code == 404


# ─── POST /departments/seed ──────────────────────────────

def test_seed_departments_fresh():
    existing = MagicMock()
    existing.data = []
    insert_result = MagicMock()
    insert_result.data = [SAMPLE_DEPT] * 15

    chain = MagicMock()
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.execute.side_effect = [existing, insert_result]
    mock_sb.table.return_value = chain

    res = client.post("/departments/seed")
    assert res.status_code == 200
    assert res.json()["count"] == 15


def test_seed_departments_already_exists():
    existing = MagicMock()
    existing.data = [{"code": d} for d in ["IM","SU","PE","OB","OR","DE","NE","OP","EN","PS","CA","ON","ER","FM","RE"]]

    chain = MagicMock()
    chain.select.return_value = chain
    chain.execute.return_value = existing
    mock_sb.table.return_value = chain

    res = client.post("/departments/seed")
    assert res.status_code == 200
    assert res.json()["count"] == 0
