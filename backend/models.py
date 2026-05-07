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
    username: str
    password: str
    nickname: str
    role: str = "patient"
    avatar_color: str | None = None
    avatar_url: str | None = None
    id_number: str | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    nickname: str | None = None
    avatar_color: str | None = None
    avatar_url: str | None = None
    id_number: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


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
