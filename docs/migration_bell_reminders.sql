-- Supabase migration: 鈴聲提醒系統
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/reminders.py 與新的 bell-sound / measurement-request 功能。
--
-- 內容：
--   1. reminders 加欄位：bell_sound_id, priority, source（不破壞既有資料）
--   2. patient_bell_prefs：每位病患針對每種提醒類型的鈴聲偏好
--   3. measurement_requests：醫師主動要求病患量測（血壓 / 血糖 / 心率 / 體重）
--   4. bell_sounds：自訂上傳鈴聲清單（預設音由前端合成，不入庫）

-- ─── 1. reminders 擴充欄位 ─────────────────────────────────
ALTER TABLE reminders
    ADD COLUMN IF NOT EXISTS bell_sound_id TEXT,
    ADD COLUMN IF NOT EXISTS priority      TEXT NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    ADD COLUMN IF NOT EXISTS source        TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'auto', 'doctor'));

-- 既有 reminder_type CHECK 是 (medication, appointment, lab, custom)。
-- 新增 measurement 類型供慢病量測使用；舊資料不動。
ALTER TABLE reminders DROP CONSTRAINT IF EXISTS reminders_reminder_type_check;
ALTER TABLE reminders ADD CONSTRAINT reminders_reminder_type_check
    CHECK (reminder_type IN ('medication', 'appointment', 'lab', 'measurement', 'custom'));

-- ─── 2. patient_bell_prefs ────────────────────────────────
CREATE TABLE IF NOT EXISTS patient_bell_prefs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  TEXT NOT NULL,
    kind        TEXT NOT NULL
        CHECK (kind IN ('medication', 'appointment', 'lab', 'measurement', 'doctor_request', 'custom')),
    bell_sound  TEXT NOT NULL DEFAULT 'gentle',  -- 預設音 id 或 bell_sounds.id
    volume      INT  NOT NULL DEFAULT 70 CHECK (volume BETWEEN 0 AND 100),
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, kind)
);

CREATE INDEX IF NOT EXISTS patient_bell_prefs_patient_idx
    ON patient_bell_prefs (patient_id);

ALTER TABLE patient_bell_prefs DISABLE ROW LEVEL SECURITY;

-- ─── 3. measurement_requests ──────────────────────────────
CREATE TABLE IF NOT EXISTS measurement_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id       TEXT NOT NULL,
    patient_id      TEXT NOT NULL,
    measure_type    TEXT NOT NULL
        CHECK (measure_type IN ('bp', 'glucose', 'heart_rate', 'weight', 'temperature')),
    note            TEXT,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    due_by          TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'done', 'expired', 'cancelled')),
    result_value    TEXT,
    result_recorded_at TIMESTAMPTZ,
    reminder_id     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS measurement_requests_patient_idx
    ON measurement_requests (patient_id, status, requested_at DESC);
CREATE INDEX IF NOT EXISTS measurement_requests_doctor_idx
    ON measurement_requests (doctor_id, requested_at DESC);

ALTER TABLE measurement_requests DISABLE ROW LEVEL SECURITY;

-- ─── 4. bell_sounds（自訂上傳鈴聲） ──────────────────────
CREATE TABLE IF NOT EXISTS bell_sounds (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_patient_id TEXT NOT NULL,
    name        TEXT NOT NULL,
    file_url    TEXT NOT NULL,
    duration_sec NUMERIC(6, 2),
    file_size_bytes INT,
    mime_type   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bell_sounds_owner_idx ON bell_sounds (owner_patient_id);

ALTER TABLE bell_sounds DISABLE ROW LEVEL SECURITY;
