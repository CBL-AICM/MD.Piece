-- Supabase migration: 健康識能（eHealth Literacy / eHEALS）篩檢結果
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行（或 MCP apply_migration）
-- 對應 backend/routers/health_literacy.py 與 backend/db.py 的 SQLite fallback schema。
--
-- 住院模式 v2 之 M07：啟動 8 題 eHEALS → 低分自動套用「簡化模式」。
-- eHEALSResult 跨住院期次保存（app 層級，非單次住院），居家版亦可重用。
-- 冪等，可安全重跑。
--
-- RLS（規則 7 — 攤開講）：production 後端目前實際帶的是 anon key（db.py 內建預設），
-- 故沿用 migration_vital_entries.sql 作法：ENABLE RLS + stopgap_anon_all 寬鬆 policy，
-- anon/authenticated 皆可讀寫（與其他既有可寫表一致）。
-- 少了這條 policy，anon 寫入會被 RLS 擋下 → /screen 回 _persisted:false（部署時實際踩到）。
-- 較安全的作法是後端改帶 service_role secret + 移除此 policy（db.py 2026-05-29 註解方向），
-- 屬跨表基礎建設，另案處理。

CREATE TABLE IF NOT EXISTS ehl_results (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id        text NOT NULL,
    answers           jsonb,                 -- 8 題作答，每項 1–5
    total_score       integer,               -- 8–40
    literacy_level    text,                  -- low | adequate | high
    recommended_mode  text,                  -- simplified | standard
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ehl_results_patient
    ON ehl_results (patient_id, created_at DESC);

ALTER TABLE ehl_results ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stopgap_anon_all ON ehl_results;
CREATE POLICY stopgap_anon_all ON ehl_results
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
