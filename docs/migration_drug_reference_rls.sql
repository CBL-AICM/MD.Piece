-- Supabase migration: 補上 drug_reference 的 RLS policies
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
--
-- 背景：drug_reference 表的 RLS 已啟用，但 read / insert / update 三條 policy
-- 都沒有建立，導致 backend `_save_to_cache` 的 insert 一律被 PostgREST 擋下
-- （Postgres log 噴 "new row violates row-level security policy for table
-- drug_reference"）。表永遠是空的，「藥物百科」熱門查詢列表也永遠空白。
--
-- 補上和 disease_reference 同一組 public read/insert/update policy；服務本身
-- 不存個資，欄位都是公開的衛教資料，目前沒有按使用者隔離的需求。

ALTER TABLE public.drug_reference ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "drug_reference read all" ON public.drug_reference;
CREATE POLICY "drug_reference read all" ON public.drug_reference
    FOR SELECT USING (true);

DROP POLICY IF EXISTS "drug_reference insert all" ON public.drug_reference;
CREATE POLICY "drug_reference insert all" ON public.drug_reference
    FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "drug_reference update all" ON public.drug_reference;
CREATE POLICY "drug_reference update all" ON public.drug_reference
    FOR UPDATE USING (true) WITH CHECK (true);
