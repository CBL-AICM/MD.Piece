-- Supabase migration: 症狀日記條目（病患自記的症狀）
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/symptoms.py 的 /entries 端點
--
-- 與 symptoms_log（AI 分析紀錄）分屬不同表：本表存病患自己記的單筆症狀
-- （categoryId/intensity/frequency/notes…），以 (patient_id, client_id) 幂等 upsert。
-- 註：production 已透過 MCP apply_migration 建立本表；此檔為版本庫紀錄與
--     全新環境重建之用（冪等，可安全重跑）。

CREATE TABLE IF NOT EXISTS symptom_entries (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   TEXT NOT NULL,
    client_id    TEXT NOT NULL,
    category_id  TEXT,
    intensity    INTEGER,
    frequency    INTEGER,
    notes        TEXT,
    proxy_for    TEXT,
    recorded_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS symptom_entries_patient_client_idx
    ON symptom_entries (patient_id, client_id);

CREATE INDEX IF NOT EXISTS symptom_entries_patient_recorded_idx
    ON symptom_entries (patient_id, recorded_at DESC);

ALTER TABLE symptom_entries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stopgap_anon_all ON symptom_entries;
CREATE POLICY stopgap_anon_all ON symptom_entries
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
