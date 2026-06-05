-- Supabase migration: 通用問卷（survey）引擎
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行（或 MCP apply_migration）
-- 對應 backend/routers/surveys.py 與 backend/db.py 的 SQLite fallback schema。
--
-- 讓醫護端自行「定義任意問卷 → 收集作答 → 後台統計分析」，用來整合自家研究 / 實驗問卷。
-- 與 ehl_results（寫死的 eHEALS 量表）共存、互不影響。冪等，可安全重跑。
--
-- RLS（沿用 migration_health_literacy.sql 作法）：production 後端目前帶 anon key，
-- 故 ENABLE RLS + stopgap_anon_all 寬鬆 policy，anon/authenticated 皆可讀寫。
-- 較安全的作法是後端改帶 service_role secret + 移除此 policy，屬跨表基礎建設，另案處理。

CREATE TABLE IF NOT EXISTS surveys (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key          text UNIQUE NOT NULL,          -- slug，URL 用
    title        text NOT NULL,
    description  text,
    items        jsonb,                          -- [{id, text, type, options?, ...}]
    scoring      jsonb,                          -- {"method": "sum_likert" | "none"}
    created_by   text,
    active       integer NOT NULL DEFAULT 1,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS survey_responses (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_key   text NOT NULL,
    patient_id   text,
    answers      jsonb,                          -- {item_id: value}
    score        integer,                        -- sum_likert 計分結果（可為 NULL）
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_survey_responses_key
    ON survey_responses (survey_key, created_at DESC);

ALTER TABLE surveys ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stopgap_anon_all ON surveys;
CREATE POLICY stopgap_anon_all ON surveys
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

ALTER TABLE survey_responses ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stopgap_anon_all ON survey_responses;
CREATE POLICY stopgap_anon_all ON survey_responses
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
