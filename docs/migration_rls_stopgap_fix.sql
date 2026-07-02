-- RLS 修補（2026-07-02 已套用至 production）：
-- 修復兩類 Supabase RLS 問題，沿用既有 stopgap_anon_all 過渡模式，行為保持一致。
--
-- 背景：後端目前以 anon key 存取 Supabase（events.py 原設計假設 service_role），
-- 因此「RLS 已啟用但沒有 policy」的表寫入一律被 PostgREST 401 擋下：
--   - app_events：事件日誌（TEL）從未成功寫入
--   - ema_rules / ema_deliveries：EMA 規則與派送讀寫失效
-- 另有四張表 RLS 完全關閉（Supabase security advisor: rls_disabled）。
--
-- 真正的修法（日後清理）：後端改用 service_role key，並把所有表的
-- stopgap_anon_all 改成依身分收緊的 policy。

-- (1) RLS 已啟用但無 policy → 補全通 stopgap policy
CREATE POLICY stopgap_anon_all ON public.app_events
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY stopgap_anon_all ON public.ema_rules
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY stopgap_anon_all ON public.ema_deliveries
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- (2) RLS 關閉的表：sleep_sessions / sleep_edits 已有 stopgap_anon_all，
--     啟用 RLS 後行為不變；sim_world_state / sim_persona 先補同款 policy 再啟用。
CREATE POLICY stopgap_anon_all ON public.sim_world_state
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY stopgap_anon_all ON public.sim_persona
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

ALTER TABLE public.sleep_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sleep_edits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sim_world_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sim_persona ENABLE ROW LEVEL SECURITY;
