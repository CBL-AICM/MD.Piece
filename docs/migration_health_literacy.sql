-- Supabase migration: 健康識能（eHealth Literacy / eHEALS）篩檢結果
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行（或 MCP apply_migration）
-- 對應 backend/routers/health_literacy.py 與 backend/db.py 的 SQLite fallback schema。
--
-- 住院模式 v2 之 M07：啟動 8 題 eHEALS → 低分自動套用「簡化模式」。
-- eHEALSResult 跨住院期次保存（app 層級，非單次住院），居家版亦可重用。
-- 冪等，可安全重跑。
--
-- RLS 取捨（規則 7 — 攤開講）：本專案 migration 對 RLS 有三種寫法並存：
--   (a) migration_inpatient.sql      → DISABLE RLS（最舊）
--   (b) migration_vital_entries.sql  → ENABLE RLS + stopgap_anon_all 寬鬆 policy
--   (c) backend/db.py 註解(2026-05-29) → ENABLE RLS + 不建任何 policy，後端改帶
--       service_role secret 繞過 RLS（最新、刻意收緊的現況）。
-- 本檔採 (c)：與目前 production 安全姿態一致。後端 get_supabase() 已強制
-- 要求 service_role（偵測到 anon 會 loud-fail），故無 policy 也能正常讀寫。

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
