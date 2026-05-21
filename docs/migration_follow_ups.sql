-- Supabase migration: 回診排程（多筆回診）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/follow_ups.py
--
-- 設計：一個病患可以同時有多筆未來的回診（不同科別／醫院／時段），
-- 與 medical_records（過去的就診紀錄）解耦。前端有獨立「回診排程」頁，
-- Pieces 頁與首頁 chip 只顯示「最近一筆狀態為 scheduled 的回診」。

CREATE TABLE IF NOT EXISTS follow_ups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      TEXT NOT NULL,
    scheduled_date  DATE NOT NULL,
    session         TEXT CHECK (session IN ('am', 'pm')),
    department      TEXT,
    hospital        TEXT,
    doctor_name     TEXT,
    status          TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'completed', 'missed', 'cancelled')),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS follow_ups_patient_date_idx
    ON follow_ups (patient_id, scheduled_date);

CREATE INDEX IF NOT EXISTS follow_ups_patient_status_idx
    ON follow_ups (patient_id, status, scheduled_date);

ALTER TABLE follow_ups DISABLE ROW LEVEL SECURITY;
