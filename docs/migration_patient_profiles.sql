-- Supabase migration: 個人檔案 / 慢性病 / 緊急聯絡人（per-user 持久化）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/profile.py、解決 Issue #131
--
-- 設計：把原本只存 localStorage 的 mdpiece_basic_info 同步到後端，避免清快取
-- 換瀏覽器／換手機就遺失。一個 user 對應一筆 profile（UNIQUE user_id）。
-- 存取控制：本專案用 backend 自有 username+scrypt 而非 Supabase Auth，
-- 所以這邊 RLS 走 disable + backend layer 做檢查，與 follow_ups / labs
-- 等表一致。如未來改 Supabase Auth，再加 policy (auth.uid() = user_id)。

CREATE TABLE IF NOT EXISTS patient_profiles (
    user_id          TEXT PRIMARY KEY,
    gender           TEXT,
    birthday         DATE,
    blood            TEXT,
    height_cm        NUMERIC(5,1),
    weight_kg        NUMERIC(5,1),
    allergies        TEXT,
    conditions       TEXT,
    current_disease  TEXT,
    meds             TEXT,
    doctor_name      TEXT,
    hospital         TEXT,
    emergency_name   TEXT,
    emergency_phone  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE patient_profiles DISABLE ROW LEVEL SECURITY;
