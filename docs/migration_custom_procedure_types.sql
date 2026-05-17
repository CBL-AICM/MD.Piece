-- Supabase migration: 建立 custom_procedure_types 表（住院模式「今日治療」自訂處置類型）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/procedure_types.py，讓使用者在內建 _IP_EXAM_TYPES 目錄之外
-- 自訂屬於自己的處置類型（per-patient，可跨多次 admission 重用）。

CREATE TABLE IF NOT EXISTS public.custom_procedure_types (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   TEXT NOT NULL,
    key          TEXT NOT NULL,
    label        TEXT NOT NULL,
    icon         TEXT NOT NULL DEFAULT 'clipboard-list',
    category     TEXT NOT NULL DEFAULT 'exam' CHECK (category IN ('exam', 'treatment', 'nursing')),
    default_prep TEXT DEFAULT '',
    description  TEXT DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (patient_id, key)
);

-- 取某位患者全部自訂類型時用
CREATE INDEX IF NOT EXISTS custom_procedure_types_patient_idx
    ON public.custom_procedure_types (patient_id, created_at DESC);

-- 與專案其他表一致：disable RLS（anon key 直接存取）
ALTER TABLE public.custom_procedure_types DISABLE ROW LEVEL SECURITY;
