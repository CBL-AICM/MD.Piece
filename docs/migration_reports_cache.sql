-- Supabase migration: 建立 reports_cache 表（診前報告整合摘要 TTL 快取）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行（或透過 MCP apply_migration）
-- 對應 backend/routers/reports.py 的 /reports/{pid}/monthly + /reports/{pid}/patient-summary
-- + SSE /integrated-summary/stream，同 patient_id + days + audience 在 TTL 內直接回 cache。
--
-- 跟 education_cache 不同 — reports 內容會隨病人記錄改變，所以用 TTL（預設 1 小時）。
--
-- 此檔已透過 Supabase MCP apply_migration("create_reports_cache") 上線於 production。

CREATE TABLE IF NOT EXISTS public.reports_cache (
    cache_key       TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    days            INTEGER NOT NULL,
    audience        TEXT NOT NULL,
    payload         JSONB NOT NULL,
    generated_at    TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    CONSTRAINT reports_cache_audience_check CHECK (audience IN ('monthly', 'patient_summary'))
);

CREATE INDEX IF NOT EXISTS idx_reports_cache_patient ON public.reports_cache (patient_id);
CREATE INDEX IF NOT EXISTS idx_reports_cache_expires ON public.reports_cache (expires_at);

COMMENT ON TABLE public.reports_cache IS '診前報告 LLM 整合摘要 TTL 快取，避開 Groq 429 突發 (預設 TTL 1 小時)';
