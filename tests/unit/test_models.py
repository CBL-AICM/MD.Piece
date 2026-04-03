"""Unit tests for backend/models.py — Pydantic validation."""

import pytest
from pydantic import ValidationError

from backend.models import (
    PatientCreate,
    PatientUpdate,
    DoctorCreate,
    MedicalRecordCreate,
    SymptomAnalysisRequest,
    EmotionLog,
    MedicationCreate,
    MedicationLogEntry,
    TriageRequest,
    XiaoheChatRequest,
)


class TestPatientCreate:
    def test_valid(self):
        p = PatientCreate(name="Alice", age=30)
        assert p.name == "Alice"
        assert p.age == 30

    def test_optional_fields(self):
        p = PatientCreate(name="Bob", age=25, gender="male", phone="0912345678")
        assert p.gender == "male"
        assert p.phone == "0912345678"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            PatientCreate(name="", age=30)

    def test_negative_age_rejected(self):
        with pytest.raises(ValidationError):
            PatientCreate(name="Test", age=-1)

    def test_age_over_200_rejected(self):
        with pytest.raises(ValidationError):
            PatientCreate(name="Test", age=201)


class TestDoctorCreate:
    def test_valid(self):
        d = DoctorCreate(name="Dr. Wang", specialty="內科")
        assert d.name == "Dr. Wang"

    def test_empty_specialty_rejected(self):
        with pytest.raises(ValidationError):
            DoctorCreate(name="Dr. Wang", specialty="")


class TestMedicalRecordCreate:
    def test_minimal(self):
        r = MedicalRecordCreate(patient_id="uuid-123")
        assert r.patient_id == "uuid-123"
        assert r.symptoms == []

    def test_full(self):
        r = MedicalRecordCreate(
            patient_id="uuid-123",
            doctor_id="doc-456",
            symptoms=["fever", "cough"],
            diagnosis="flu",
            prescription="rest",
            notes="follow up in 1 week",
        )
        assert len(r.symptoms) == 2


class TestSymptomAnalysisRequest:
    def test_valid(self):
        s = SymptomAnalysisRequest(symptoms=["fever", "headache"])
        assert len(s.symptoms) == 2

    def test_empty_symptoms_rejected(self):
        with pytest.raises(ValidationError):
            SymptomAnalysisRequest(symptoms=[])


class TestEmotionLog:
    def test_valid(self):
        e = EmotionLog(patient_id="p1", score=3)
        assert e.score == 3

    def test_score_below_range(self):
        with pytest.raises(ValidationError):
            EmotionLog(patient_id="p1", score=0)

    def test_score_above_range(self):
        with pytest.raises(ValidationError):
            EmotionLog(patient_id="p1", score=6)


class TestMedicationCreate:
    def test_valid(self):
        m = MedicationCreate(
            patient_id="p1", name="Aspirin", dosage="100mg", timing="morning"
        )
        assert m.timing == "morning"

    def test_invalid_timing(self):
        with pytest.raises(ValidationError):
            MedicationCreate(
                patient_id="p1", name="Aspirin", dosage="100mg", timing="lunch"
            )

    def test_valid_timings(self):
        for t in ("morning", "after_meal", "bedtime"):
            m = MedicationCreate(patient_id="p1", name="Med", dosage="10mg", timing=t)
            assert m.timing == t


class TestMedicationLogEntry:
    def test_taken(self):
        entry = MedicationLogEntry(
            patient_id="p1", medication_id="m1", taken=True
        )
        assert entry.taken is True

    def test_skipped_with_reason(self):
        entry = MedicationLogEntry(
            patient_id="p1", medication_id="m1", taken=False, skip_reason="噁心"
        )
        assert entry.skip_reason == "噁心"


class TestTriageRequest:
    def test_minimal(self):
        t = TriageRequest(patient_id="p1")
        assert t.today_data == {}

    def test_with_data(self):
        t = TriageRequest(
            patient_id="p1",
            today_data={"temperature": 38.5, "symptoms": ["胸痛"]},
        )
        assert t.today_data["temperature"] == 38.5


class TestXiaoheChatRequest:
    def test_valid(self):
        c = XiaoheChatRequest(user_id="u1", message="你好")
        assert c.mode == "patient"
        assert c.version == "normal"

    def test_family_mode(self):
        c = XiaoheChatRequest(user_id="u1", message="你好", mode="family")
        assert c.mode == "family"

    def test_elderly_version(self):
        c = XiaoheChatRequest(user_id="u1", message="你好", version="elderly")
        assert c.version == "elderly"

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            XiaoheChatRequest(user_id="u1", message="你好", mode="admin")

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            XiaoheChatRequest(user_id="u1", message="")
