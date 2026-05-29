-- 睡眠紀錄模組 — Supabase / PostgreSQL
-- 對應 backend/routers/sleep.py、backend/utils/sleep_pipeline.py 與 db.py 的 SQLite fallback。
-- 純記錄工具：不下診斷、不給建議、不做風險警示。三種來源並存（auto/manual/imported）。

CREATE TABLE IF NOT EXISTS sleep_sessions (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              text NOT NULL,
    bed_time             timestamptz NOT NULL,
    sleep_onset          timestamptz,
    wake_time            timestamptz,
    out_of_bed_time      timestamptz,
    total_sleep_minutes  integer,
    time_in_bed_minutes  integer,
    sleep_efficiency     real,
    waso_minutes         integer,
    awakenings_count     integer,
    source               text NOT NULL DEFAULT 'manual' CHECK (source IN ('auto', 'manual', 'imported')),
    is_edited            boolean DEFAULT false,
    classifier           text,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sleep_sessions_user ON sleep_sessions (user_id, bed_time DESC);

-- 修正 log：保留 auto 紀錄被手動修正前的原值，供研究端比對自動 vs 修正差異。
CREATE TABLE IF NOT EXISTS sleep_edits (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       uuid NOT NULL,
    user_id          text,
    previous_values  jsonb,
    edited_at        timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sleep_edits_session ON sleep_edits (session_id);

-- 與專案其他病人資料表一致（anon key 存取、RLS 已停用）。
ALTER TABLE sleep_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE sleep_edits DISABLE ROW LEVEL SECURITY;
