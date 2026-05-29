-- 住院模式（六大功能）新增資料表 — Supabase / PostgreSQL
-- 對應 backend/routers/inpatient.py 與 backend/db.py 的 SQLite fallback schema。
-- 核心架構：資料只有一份。這兩張表是「床邊寫入」用的縱向資料延伸，
-- 與門診共用同一個 patient_id；F1/F3/F4/F6 皆只讀取既有共用資料，不另建表。

-- F2 床邊自我記錄（極低操作負擔，全欄位可選）
CREATE TABLE IF NOT EXISTS bedside_logs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          text NOT NULL,
    admission_id        uuid,
    pain                integer,            -- 0–10
    food                text,               -- none | little | half | most
    sleep               text,              -- good | fair | poor
    bowel               text,              -- yes | no
    activity            text,              -- bed | sit | walk
    treatment_response  text,              -- better | same | worse
    mood                integer,           -- 1–5
    note                text,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bedside_logs_patient ON bedside_logs (patient_id);
CREATE INDEX IF NOT EXISTS idx_bedside_logs_admission ON bedside_logs (admission_id);

-- F2 想問醫師的問題清單（QPL；查房前用）
CREATE TABLE IF NOT EXISTS inpatient_questions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    text NOT NULL,
    admission_id  uuid,
    text          text NOT NULL,
    status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'asked')),
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_inpatient_questions_patient ON inpatient_questions (patient_id);
CREATE INDEX IF NOT EXISTS idx_inpatient_questions_admission ON inpatient_questions (admission_id);

-- RLS 與專案其他表一致（md_piece_full_schema_and_anon_access 已 disable RLS）。
ALTER TABLE bedside_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE inpatient_questions DISABLE ROW LEVEL SECURITY;
