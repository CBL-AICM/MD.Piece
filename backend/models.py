from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


# ─── Patient ───────────────────────────────────────────────

class PatientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=200)
    gender: str | None = None
    phone: str | None = None


class PatientUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    age: int | None = Field(None, ge=0, le=200)
    gender: str | None = None
    phone: str | None = None


# ─── Doctor ────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    specialty: str = Field(..., min_length=1, max_length=100)
    phone: str | None = None


class DoctorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    specialty: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = None


# ─── Medical Record ───────────────────────────────────────

class MedicalRecordCreate(BaseModel):
    patient_id: str
    doctor_id: str | None = None
    visit_date: datetime | None = None
    symptoms: list[str] = []
    diagnosis: str | None = None
    prescription: str | None = None
    notes: str | None = None


class MedicalRecordUpdate(BaseModel):
    doctor_id: str | None = None
    visit_date: datetime | None = None
    symptoms: list[str] | None = None
    diagnosis: str | None = None
    prescription: str | None = None
    notes: str | None = None


# ─── Symptom Analysis ─────────────────────────────────────

class SymptomAnalysisRequest(BaseModel):
    symptoms: list[str] = Field(..., min_length=1)
    patient_id: str | None = None


# ─── Emotions ─────────────────────────────────────────────

class EmotionLog(BaseModel):
    patient_id: str
    score: int = Field(..., ge=1, le=5, description="情緒分數 1-5，1 最低落、5 最好")
    note: str = ""


# ─── Medications ──────────────────────────────────────────

class MedicationCreate(BaseModel):
    patient_id: str
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=200)
    timing: str = Field(..., pattern=r"^(morning|after_meal|bedtime)$")


class MedicationLogEntry(BaseModel):
    patient_id: str
    medication_id: str
    taken: bool
    skip_reason: str = ""


# ─── Triage ───────────────────────────────────────────────

class TriageRequest(BaseModel):
    patient_id: str
    today_data: dict[str, Any] = Field(
        default_factory=dict,
        description="今天的症狀/體溫/服藥/情緒資料",
    )


# ─── Xiaohe Chat ──────────────────────────────────────────

class XiaoheChatRequest(BaseModel):
    user_id: str
    message: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field("patient", pattern=r"^(patient|family)$")
    version: str = Field("normal", pattern=r"^(normal|elderly)$")
