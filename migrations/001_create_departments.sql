-- Migration 001: 建立科別資料表，並為醫師資料表加入科別欄位
-- 執行環境：Supabase / PostgreSQL
-- 執行日期：2026-03-20

-- ─── 建立 departments 資料表 ──────────────────────────────

CREATE TABLE IF NOT EXISTS departments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    code        TEXT,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 科別名稱唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS departments_name_idx ON departments (name);

-- 科別代碼唯一索引（允許 NULL）
CREATE UNIQUE INDEX IF NOT EXISTS departments_code_idx ON departments (code) WHERE code IS NOT NULL;

-- ─── 自動更新 updated_at ──────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─── 為 doctors 加入 department_id 外鍵 ──────────────────

ALTER TABLE doctors
    ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS doctors_department_id_idx ON doctors (department_id);

-- ─── Row Level Security (RLS) ────────────────────────────

ALTER TABLE departments ENABLE ROW LEVEL SECURITY;

-- 允許已驗證使用者讀取
CREATE POLICY "departments_select" ON departments
    FOR SELECT USING (true);

-- 允許已驗證使用者新增/修改/刪除
CREATE POLICY "departments_insert" ON departments
    FOR INSERT WITH CHECK (true);

CREATE POLICY "departments_update" ON departments
    FOR UPDATE USING (true);

CREATE POLICY "departments_delete" ON departments
    FOR DELETE USING (true);

-- ─── 預設科別種子資料 ─────────────────────────────────────
-- 執行 POST /departments/seed 或手動執行以下 SQL

INSERT INTO departments (name, code, description) VALUES
    ('內科',   'IM', '內科疾病診治'),
    ('外科',   'SU', '外科手術與術後照護'),
    ('小兒科', 'PE', '兒童與青少年醫療'),
    ('婦產科', 'OB', '婦女健康與產科'),
    ('骨科',   'OR', '骨骼肌肉系統疾病'),
    ('皮膚科', 'DE', '皮膚、毛髮、指甲疾病'),
    ('神經科', 'NE', '神經系統疾病診治'),
    ('眼科',   'OP', '眼部疾病與視力'),
    ('耳鼻喉科','EN', '耳鼻喉頭頸疾病'),
    ('精神科', 'PS', '心理與精神健康'),
    ('心臟科', 'CA', '心臟血管疾病'),
    ('腫瘤科', 'ON', '癌症與腫瘤治療'),
    ('急診科', 'ER', '緊急醫療處置'),
    ('家醫科', 'FM', '全人照護與慢性病管理'),
    ('復健科', 'RE', '物理治療與復健')
ON CONFLICT (name) DO NOTHING;
