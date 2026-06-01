-- Supabase migration: disease_reference 增加 recurrence_data 欄位（復發風險預測的文獻錨）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
--
-- 用途：快取 backend/services/llm_service.lookup_disease_recurrence() 整理的
-- 「族群層級復發知識」（復發率 band/區間、復發驅動因子 maps_to/weight/evidence、
-- 要注意的徵兆）。復發風險引擎 backend/utils/recurrence.py 讀此欄當疾病別基線與
-- 「根據」。首次 predict 暖快取，之後直接命中、不再打 LLM（對齊 disease_reference 既有快取策略）。

ALTER TABLE public.disease_reference
    ADD COLUMN IF NOT EXISTS recurrence_data JSONB;

-- 結構（範例）：
-- {
--   "matched": true,
--   "name_zh": "...", "name_en": "...",
--   "recurrence_rate": { "band": "low|medium|high",
--                        "range_text": "5 年內約 20–30%",
--                        "horizon": "5 年", "summary": "..." },
--   "drivers": [ { "label": "血壓控制不佳", "maps_to": "adherence",
--                  "direction": "up", "weight": "high", "modifiable": true,
--                  "plain_text": "...", "evidence": "文獻根據一句話" } ],
--   "watch_signs": ["復發前最該留意的徵兆 1", "..."],
--   "disclaimer": "此為文獻整理的一般性資訊，非個人診斷；是否復發請由醫師判斷。"
-- }
