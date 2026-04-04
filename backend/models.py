from pydantic import BaseModel
from datetime import datetime


# ─── Patient ───────────────────────────────────────────────

class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str | None = None
    phone: str | None = None
    icd10_codes: list[str] = []


class PatientUpdate(BaseModel):
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    phone: str | None = None
    icd10_codes: list[str] | None = None


# ─── Doctor ────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    name: str
    specialty: str
    phone: str | None = None


class DoctorUpdate(BaseModel):
    name: str | None = None
    specialty: str | None = None
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
    symptoms: list[str]
    patient_id: str | None = None
