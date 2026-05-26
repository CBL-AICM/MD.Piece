-- Supabase migration: 住院地理圍欄（自動判定出院）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
--
-- 對應 backend/routers/admissions.py 的 hospital picker + check-location 功能。
-- 設計憲法第 6 條（長者／家屬模式）：病患常忘記按「出院」，靠地理位置自動結案。
--
-- 內容：
--   1. admissions 加欄位：hospital_name / hospital_lat / hospital_lng
--      + auto_discharged_at（自動結案時間，作為審計紀錄，供醫師日後辨認哪些是
--        系統判定而非病人手動結案）

ALTER TABLE admissions
    ADD COLUMN IF NOT EXISTS hospital_name       TEXT,
    ADD COLUMN IF NOT EXISTS hospital_lat        DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS hospital_lng        DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS auto_discharged_at  TIMESTAMPTZ;
