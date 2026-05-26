-- Supabase migration: 建立 education_cache 表（衛教生成內容快取）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行（或透過 MCP apply_migration）
-- 對應 backend/routers/education.py 的 /education/generate，相同 (icd10_code+dimension)
-- 或同一 topic 只生一次、後續直接 cache 命中，避免反覆打 Groq 命中 rate limit。
--
-- 此檔已透過 Supabase MCP apply_migration("create_education_cache") 上線於 production。

CREATE TABLE IF NOT EXISTS public.education_cache (
    cache_key       TEXT PRIMARY KEY,
    mode            TEXT NOT NULL,
    icd10_code      TEXT,
    dimension       TEXT,
    topic           TEXT,
    disease_name    TEXT,
    content         TEXT NOT NULL,
    provider        TEXT,
    query_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT education_cache_mode_check CHECK (mode IN ('icd10_dim', 'topic'))
);

CREATE INDEX IF NOT EXISTS idx_education_cache_icd_dim
    ON public.education_cache (icd10_code, dimension);
CREATE INDEX IF NOT EXISTS idx_education_cache_topic
    ON public.education_cache (topic);

COMMENT ON TABLE public.education_cache IS '衛教生成內容快取 (education content cache). 相同 disease+dimension 或同 topic 只 LLM 生一次、之後直接 cache 命中，避免反覆打 Groq 命中 rate limit。';
