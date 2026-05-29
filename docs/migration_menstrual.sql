-- 月經紀錄 — Supabase / PostgreSQL
-- 對應 backend/routers/menstrual.py 與 backend/db.py 的 SQLite fallback schema。
-- 個人化縱向分析：以使用者自己的週期基線呈現，不做診斷、不判定正常/異常。

-- 經期（每筆 = 一次月經）
CREATE TABLE IF NOT EXISTS menstrual_cycles (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  text NOT NULL,
    start_date  date NOT NULL,
    end_date    date,
    flow        text,              -- light | medium | heavy
    symptoms    text,              -- JSON array 字串：["經痛","情緒低落"]
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_menstrual_cycles_patient ON menstrual_cycles (patient_id, start_date DESC);

-- 每日紀錄（基礎體溫 / 排卵試紙 / 避孕藥），以 (patient_id, date) 為邏輯鍵
CREATE TABLE IF NOT EXISTS menstrual_daily (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      text NOT NULL,
    date            date NOT NULL,
    bbt_c           real,          -- 基礎體溫（攝氏）
    ovulation_test  text,          -- positive | negative | peak
    pill_taken      integer,       -- 0/1：今天避孕藥是否已服用
    note            text,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_menstrual_daily_patient_date ON menstrual_daily (patient_id, date);

-- 與專案其他病人資料表一致（anon key 存取、RLS 已停用）。
ALTER TABLE menstrual_cycles DISABLE ROW LEVEL SECURITY;
ALTER TABLE menstrual_daily DISABLE ROW LEVEL SECURITY;
