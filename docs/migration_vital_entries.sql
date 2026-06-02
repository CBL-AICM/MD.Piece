-- Supabase migration: 生理量測（血壓／體重／血糖／BMI 等病患自記數值）
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/vitals.py
--
-- 以 (patient_id, client_id) 幂等 upsert。value2 給雙值指標（如血壓舒張壓）。
-- 註：production 已透過 MCP apply_migration 建立本表；此檔為版本庫紀錄與
--     全新環境重建之用（冪等，可安全重跑）。

CREATE TABLE IF NOT EXISTS vital_entries (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   TEXT NOT NULL,
    client_id    TEXT NOT NULL,
    metric_id    TEXT,
    value        DOUBLE PRECISION,
    value2       DOUBLE PRECISION,
    context      TEXT,
    method       TEXT,
    notes        TEXT,
    recorded_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS vital_entries_patient_client_idx
    ON vital_entries (patient_id, client_id);

CREATE INDEX IF NOT EXISTS vital_entries_patient_recorded_idx
    ON vital_entries (patient_id, recorded_at DESC);

ALTER TABLE vital_entries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stopgap_anon_all ON vital_entries;
CREATE POLICY stopgap_anon_all ON vital_entries
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
