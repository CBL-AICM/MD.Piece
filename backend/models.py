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


# ─── Patient-initiated measurement reminder plan ──────────

class MeasurementPlanCreate(BaseModel):
    """病患在 vitals 頁設定的「定期量測提醒」計畫。

    一個 plan 會展開成多筆 reminders（每個時間點一筆，共用同一個 plan_id 當 source_id）。
    若 doctor_requested=True 且 measure_type 為標準 5 種之一，會同時建一筆
    measurement_requests 記錄，讓醫師端看到「病患自報醫師要求 X 頻率量測」。
    """
    patient_id: str
    measure_type: str  # bp | glucose | heart_rate | weight | temperature | <custom-id>
    measure_label: str | None = None  # 顯示用名稱（自訂指標必填，例：尿酸）
    frequency_preset: str  # once_daily | twice_daily | thrice_daily | weekly | custom
    times: list[str]  # ["HH:MM", ...] 該日要量測的時間（UTC offset 由前端事先換算為「目標 UTC ISO」）
    scheduled_dates: list[str] | None = None  # 對應 times[] 的第一次觸發 UTC ISO；若未提供由後端推算
    days_of_week: list[int] | None = None  # 0=Mon..6=Sun，weekly 才用
    doctor_requested: bool = True
    doctor_id: str | None = None
    note: str | None = None


# ─── Custom bell sound metadata ───────────────────────────

class BellSoundCreate(BaseModel):
    owner_patient_id: str
    name: str
    file_url: str
    duration_sec: float | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
