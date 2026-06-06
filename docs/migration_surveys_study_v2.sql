-- Supabase migration: 通用問卷引擎擴充 — 研究施測時點 / 結構化計分 / 受試者代號
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行（或 MCP apply_migration）
-- 對應 backend/routers/surveys.py 與 backend/db.py 的 SQLite fallback schema。
--
-- 為什麼：對接《MD_Piece_整合實驗設計與問卷_v2》三實驗可行性研究，需要
--   1) timepoint        — 同一份問卷分 D0 / D14 / D28 / FU48（回診後 48h）多時點施測，
--                          配對前後測分析（RQ3）必須能區分時點。
--   2) scores           — 量表計分非單一整數（MAUQ 三分量表、collaboRATE top-score、
--                          反向題、缺漏規則…），改存結構化 JSON；既有整數 score 欄保留相容。
--   3) participant_code — 選填 P01–P12 研究代號（姓名對照表仍依文件離線彌封，不進 App）。
--
-- 全部欄位 nullable、ADD COLUMN IF NOT EXISTS，向後相容既有 survey_responses 資料。冪等，可安全重跑。
-- RLS 沿用 migration_surveys.sql 既有 stopgap_anon_all policy（免再建）。

ALTER TABLE survey_responses ADD COLUMN IF NOT EXISTS timepoint        text;
ALTER TABLE survey_responses ADD COLUMN IF NOT EXISTS scores           jsonb;
ALTER TABLE survey_responses ADD COLUMN IF NOT EXISTS participant_code text;

-- summary / analysis 都以 (survey_key, patient_id, timepoint) 取每位受試者每時點最新一筆。
CREATE INDEX IF NOT EXISTS idx_survey_responses_study
    ON survey_responses (survey_key, patient_id, timepoint, created_at DESC);
