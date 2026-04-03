"""Integration tests for all API routers via TestClient."""

import pytest
from unittest.mock import MagicMock, patch


# ─── Root ──────────────────────────────────────────────────


class TestRoot:
    def test_root(self, client):
        res = client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == "MD.Piece API is running"
        assert data["version"] == "2.0.0"


# ─── Patients ──────────────────────────────────────────────


class TestPatients:
    def test_list_patients(self, client, mock_supabase):
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "1", "name": "Alice", "age": 30, "created_at": "2025-01-01"}
        ]
        mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value = (
            mock_response
        )
        res = client.get("/patients/")
        assert res.status_code == 200

    def test_create_patient(self, client, mock_supabase):
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "1", "name": "Bob", "age": 25, "created_at": "2025-01-01"}
        ]
        # The chain is: table().insert().execute()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_response
        )
        res = client.post("/patients/", json={"name": "Bob", "age": 25})
        assert res.status_code == 200
        assert res.json()["name"] == "Bob"

    def test_create_patient_validation_error(self, client):
        res = client.post("/patients/", json={"name": "", "age": 25})
        assert res.status_code == 422

    def test_create_patient_invalid_age(self, client):
        res = client.post("/patients/", json={"name": "Test", "age": -1})
        assert res.status_code == 422

    def test_delete_patient(self, client, mock_supabase):
        # delete returns 404 when result.data is empty
        mock_response = MagicMock()
        mock_response.data = [{"id": "some-uuid"}]
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = (
            mock_response
        )
        res = client.delete("/patients/some-uuid")
        assert res.status_code == 200

    def test_delete_patient_not_found(self, client, mock_supabase):
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = (
            mock_response
        )
        res = client.delete("/patients/missing-uuid")
        assert res.status_code == 404


# ─── Doctors ───────────────────────────────────────────────


class TestDoctors:
    def test_list_doctors(self, client, mock_supabase):
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "1", "name": "Dr. Wang", "specialty": "內科", "created_at": "2025-01-01"}
        ]
        mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value = (
            mock_response
        )
        res = client.get("/doctors/")
        assert res.status_code == 200

    def test_create_doctor(self, client, mock_supabase):
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "1", "name": "Dr. Wang", "specialty": "外科", "created_at": "2025-01-01"}
        ]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_response
        )
        res = client.post(
            "/doctors/", json={"name": "Dr. Wang", "specialty": "外科"}
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Dr. Wang"

    def test_create_doctor_missing_specialty(self, client):
        res = client.post("/doctors/", json={"name": "Dr. Wang"})
        assert res.status_code == 422


# ─── Symptoms ──────────────────────────────────────────────


class TestSymptoms:
    def test_get_advice(self, client):
        res = client.get("/symptoms/advice?symptom=fever")
        assert res.status_code == 200
        data = res.json()
        assert "advice" in data

    def test_analyze_symptoms(self, client):
        """Test symptom analysis falls back to rule-based when no API key."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            res = client.post(
                "/symptoms/analyze", json={"symptoms": ["headache", "fever"]}
            )
            assert res.status_code == 200
            data = res.json()
            assert "urgency" in data

    def test_analyze_empty_symptoms_rejected(self, client):
        res = client.post("/symptoms/analyze", json={"symptoms": []})
        assert res.status_code == 422


# ─── Records ──────────────────────────────────────────────


class TestRecords:
    def test_list_records(self, client, mock_supabase):
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value = (
            mock_response
        )
        res = client.get("/records/")
        assert res.status_code == 200

    def test_create_record(self, client, mock_supabase):
        mock_response = MagicMock()
        mock_response.data = [{"id": "r1", "patient_id": "p1"}]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_response
        )
        res = client.post(
            "/records/",
            json={"patient_id": "p1", "symptoms": ["fever"], "diagnosis": "flu"},
        )
        assert res.status_code == 200
        assert res.json()["id"] == "r1"

    def test_create_record_missing_patient(self, client):
        res = client.post("/records/", json={"symptoms": ["fever"]})
        assert res.status_code == 422


# ─── Triage ───────────────────────────────────────────────


class TestTriage:
    def test_evaluate(self, client):
        res = client.post(
            "/triage/evaluate",
            json={"patient_id": "p1", "today_data": {"temperature": 37.0}},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["result"] == "stable"
        assert data["patient_id"] == "p1"

    def test_get_baseline(self, client):
        res = client.get("/triage/baseline/p1")
        assert res.status_code == 200
        data = res.json()
        assert "baseline" in data
        assert data["patient_id"] == "p1"


# ─── Education ─────────────────────────────────────────────


class TestEducation:
    def test_get_articles(self, client):
        res = client.get("/education/articles")
        assert res.status_code == 200

    def test_idle_hints(self, client):
        res = client.get("/education/idle-hints")
        assert res.status_code == 200

    def test_dimensions(self, client):
        res = client.get("/education/knowledge-analysis/dimensions")
        assert res.status_code == 200
        data = res.json()
        assert "dimensions" in data
        assert "comprehension_levels" in data

    def test_disease_analysis_known_code(self, client):
        res = client.get("/education/knowledge-analysis/disease/E11")
        assert res.status_code == 200

    def test_disease_analysis_unknown_code(self, client):
        res = client.get("/education/knowledge-analysis/disease/ZZZZ")
        assert res.status_code == 200
        data = res.json()
        assert "error" in data

    def test_compare_diseases(self, client):
        res = client.get("/education/knowledge-analysis/compare")
        assert res.status_code == 200

    def test_by_category(self, client):
        res = client.get("/education/knowledge-analysis/by-category")
        assert res.status_code == 200

    def test_priorities(self, client):
        res = client.get("/education/knowledge-analysis/priorities")
        assert res.status_code == 200

    def test_distribution(self, client):
        res = client.get("/education/knowledge-analysis/distribution")
        assert res.status_code == 200


# ─── Emotions ──────────────────────────────────────────────


class TestEmotions:
    def test_get_emotions(self, client):
        res = client.get("/emotions/?patient_id=p1")
        assert res.status_code == 200

    def test_log_emotion(self, client):
        res = client.post(
            "/emotions/", json={"patient_id": "p1", "score": 4, "note": "good day"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "logged"
        assert data["score"] == 4

    def test_log_emotion_invalid_score(self, client):
        res = client.post(
            "/emotions/", json={"patient_id": "p1", "score": 0}
        )
        assert res.status_code == 422

    def test_silent_guardian(self, client):
        res = client.get("/emotions/silent-guardian?patient_id=p1")
        assert res.status_code == 200
        data = res.json()
        assert "alert" in data


# ─── Medications ───────────────────────────────────────────


class TestMedications:
    def test_get_medications(self, client):
        res = client.get("/medications/?patient_id=p1")
        assert res.status_code == 200

    def test_create_medication(self, client):
        res = client.post(
            "/medications/",
            json={
                "patient_id": "p1",
                "name": "Aspirin",
                "dosage": "100mg",
                "timing": "morning",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "added"

    def test_create_medication_invalid_timing(self, client):
        res = client.post(
            "/medications/",
            json={
                "patient_id": "p1",
                "name": "Aspirin",
                "dosage": "100mg",
                "timing": "lunch",
            },
        )
        assert res.status_code == 422

    def test_log_medication(self, client):
        res = client.post(
            "/medications/log",
            json={"patient_id": "p1", "medication_id": "m1", "taken": True},
        )
        assert res.status_code == 200


# ─── Xiaohe ───────────────────────────────────────────────


class TestXiaohe:
    def test_chat(self, client):
        res = client.post(
            "/xiaohe/chat",
            json={"user_id": "u1", "message": "你好"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "patient"
        assert data["version"] == "normal"

    def test_chat_family_mode(self, client):
        res = client.post(
            "/xiaohe/chat",
            json={"user_id": "u1", "message": "你好", "mode": "family"},
        )
        assert res.status_code == 200
        assert res.json()["mode"] == "family"

    def test_chat_invalid_mode(self, client):
        res = client.post(
            "/xiaohe/chat",
            json={"user_id": "u1", "message": "你好", "mode": "admin"},
        )
        assert res.status_code == 422

    def test_chat_empty_message(self, client):
        res = client.post(
            "/xiaohe/chat",
            json={"user_id": "u1", "message": ""},
        )
        assert res.status_code == 422

    def test_emotion_summary(self, client):
        res = client.get("/xiaohe/emotion-summary/p1")
        assert res.status_code == 200
        data = res.json()
        assert "trend" in data


# ─── Reports ──────────────────────────────────────────────


class TestReports:
    def test_monthly_report(self, client):
        res = client.get("/reports/p1/monthly")
        assert res.status_code == 200
        data = res.json()
        assert "report" in data

    def test_consultation_checklist(self, client):
        res = client.get("/reports/p1/checklist")
        assert res.status_code == 200
        data = res.json()
        assert "checklist" in data


# ─── Research ─────────────────────────────────────────────


class TestResearch:
    def test_list_experiments(self, client):
        res = client.get("/research/")
        assert res.status_code == 200

    def test_stats(self, client):
        res = client.get("/research/stats")
        assert res.status_code == 200

    def test_leaderboard(self, client):
        res = client.get("/research/leaderboard")
        assert res.status_code == 200

    def test_gpu_status(self, client):
        res = client.get("/research/status/gpu")
        assert res.status_code == 200
