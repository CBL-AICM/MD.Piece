-- Supabase migration: 建立 diet_records 表（飲食紀錄）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/diet.py 的飲食紀錄寫入 / 讀取與「吃什麼神器」歷史避重邏輯。

CREATE TABLE IF NOT EXISTS diet_records (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  TEXT NOT NULL,
    meal_type   TEXT NOT NULL CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    foods       TEXT NOT NULL,
    note        TEXT DEFAULT '',
    eaten_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 加速 _recent_eaten_foods / get_diet_records 的查詢
CREATE INDEX IF NOT EXISTS diet_records_patient_eaten_idx
    ON diet_records (patient_id, eaten_at DESC);

-- 與專案其他表一致：disable RLS（anon key 直接存取）
ALTER TABLE diet_records DISABLE ROW LEVEL SECURITY;
