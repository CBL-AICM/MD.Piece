-- Supabase migration: 建立 disease_reference 表（疾病百科快取）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/diseases.py 的疾病查詢結果快取，命中即跳過 LLM。

CREATE TABLE IF NOT EXISTS public.disease_reference (
    id              TEXT PRIMARY KEY,
    name_zh         TEXT,
    name_en         TEXT,
    aliases         JSONB DEFAULT '[]'::jsonb,
    icd10_code      TEXT,
    icd10_category  TEXT,
    overview        TEXT,
    causes          JSONB DEFAULT '[]'::jsonb,
    symptoms        JSONB DEFAULT '{"common":[],"warning":[]}'::jsonb,
    common_medications JSONB DEFAULT '[]'::jsonb,
    treatments      JSONB DEFAULT '[]'::jsonb,
    complications   JSONB DEFAULT '[]'::jsonb,
    prognosis       TEXT,
    self_care       JSONB DEFAULT '[]'::jsonb,
    red_flags       JSONB DEFAULT '[]'::jsonb,
    references_data JSONB DEFAULT '[]'::jsonb,
    source          TEXT DEFAULT 'claude',
    disclaimer      TEXT,
    query_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_disease_reference_name_zh ON public.disease_reference (lower(name_zh));
CREATE INDEX IF NOT EXISTS idx_disease_reference_name_en ON public.disease_reference (lower(name_en));
CREATE INDEX IF NOT EXISTS idx_disease_reference_icd10  ON public.disease_reference (icd10_code);
CREATE INDEX IF NOT EXISTS idx_disease_reference_query_count ON public.disease_reference (query_count DESC);

-- 開放匿名讀取與寫入（與 drug_reference 相同 policy）
ALTER TABLE public.disease_reference ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "disease_reference read all" ON public.disease_reference;
CREATE POLICY "disease_reference read all" ON public.disease_reference
    FOR SELECT USING (true);

DROP POLICY IF EXISTS "disease_reference insert all" ON public.disease_reference;
CREATE POLICY "disease_reference insert all" ON public.disease_reference
    FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "disease_reference update all" ON public.disease_reference;
CREATE POLICY "disease_reference update all" ON public.disease_reference
    FOR UPDATE USING (true) WITH CHECK (true);
