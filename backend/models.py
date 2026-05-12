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
    role: str | None = None  # 後端強制覆寫為 'patient'
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


# ─── Reminders ────────────────────────────────────────────

class ReminderCreate(BaseModel):
    patient_id: str
    reminder_type: str  # medication | appointment | lab | measurement | custom
    title: str
    body: str | None = None
    source_id: str | None = None
    url: str | None = None
    frequency: str = "once"  # once | daily | weekly | monthly
    time_of_day: str | None = None  # "HH:MM" 用於 daily / weekly / monthly
    days_of_week: list[int] | None = None  # 0=Mon..6=Sun，weekly 用
    scheduled_at: datetime  # 首次觸發時間（ISO 8601）
    active: bool = True
    bell_sound_id: str | None = None
    priority: str = "normal"  # low | normal | high | urgent
    source: str = "manual"  # manual | auto | doctor


class ReminderUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    url: str | None = None
    frequency: str | None = None
    time_of_day: str | None = None
    days_of_week: list[int] | None = None
    scheduled_at: datetime | None = None
    active: bool | None = None
    bell_sound_id: str | None = None
    priority: str | None = None


class PushSubscriptionCreate(BaseModel):
    patient_id: str
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None


class InboxUpdate(BaseModel):
    read: bool = True


# ─── Bell sound preferences ───────────────────────────────

class BellPrefUpsert(BaseModel):
    patient_id: str
    kind: str  # medication | appointment | lab | measurement | doctor_request | custom
    bell_sound: str = "gentle"
    volume: int = 70
    enabled: bool = True


# ─── Doctor → patient measurement requests ────────────────

class MeasurementRequestCreate(BaseModel):
    doctor_id: str
    patient_id: str
    measure_type: str  # bp | glucose | heart_rate | weight | temperature
    note: str | None = None
    due_in_minutes: int | None = None  # 多少分鐘後過期；None = 不過期


class MeasurementRequestComplete(BaseModel):
    result_value: str | None = None


# ─── Custom bell sound metadata ───────────────────────────

class BellSoundCreate(BaseModel):
    owner_patient_id: str
    name: str
    file_url: str
    duration_sec: float | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
