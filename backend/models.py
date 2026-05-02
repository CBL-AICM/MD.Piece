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


# ─── User / Auth ──────────────────────────────────────────

class UserCreate(BaseModel):
    nickname: str
    role: str  # 'doctor' or 'patient'
    avatar_color: str | None = None


class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str
    role: str  # 'doctor' or 'patient'
    avatar_color: str | None = None
    linked_doctor_id: str | None = None
    linked_patient_id: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ─── Doctor Notes ─────────────────────────────────────────

class DoctorNoteCreate(BaseModel):
    patient_id: str
    doctor_id: str | None = None
    record_id: str | None = None
    content: str
    next_focus: str | None = None
    tags: list[str] = []


class DoctorNoteUpdate(BaseModel):
    content: str | None = None
    next_focus: str | None = None
    tags: list[str] | None = None


# ─── Medication Changes ───────────────────────────────────

class MedicationChangeCreate(BaseModel):
    patient_id: str
    medication_id: str
    doctor_id: str | None = None
    change_type: str  # start | stop | dose_up | dose_down | switch | frequency | other
    previous_dosage: str | None = None
    new_dosage: str | None = None
    previous_frequency: str | None = None
    new_frequency: str | None = None
    reason: str | None = None
    effective_date: datetime | None = None


# ─── Alerts ───────────────────────────────────────────────

class AlertCreate(BaseModel):
    patient_id: str
    alert_type: str
    severity: str = "medium"
    title: str
    detail: str | None = None
    metadata: dict | None = None
    source: str | None = None


class AlertUpdate(BaseModel):
    acknowledged: bool | None = None
    acknowledged_by: str | None = None
    resolved: bool | None = None
