-- Supabase migration: App 事件日誌（app_events）— codebook v3「使用行為 / 遺失與錯誤事件」的 TEL 底層
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行（或 MCP apply_migration）
-- 對應 docs/research/app_events_schema.md（事件目錄）與 backend/db.py 的 SQLite fallback schema。
--
-- 為什麼：codebook 的「使用行為(40)」約 30 項、「遺失與錯誤事件(30)」約 16 項屬 App 遙測，
--   現行只有 symptom/vital/sleep/medication entries，缺 session / 點擊 / 錯誤 / 推播 事件。
--   本表為通用事件日誌（一列一事件），後端再以純程式碼聚合成 codebook 的衍生變項（規則 5）。
--
-- RLS（採 2026-05-29 後全表硬化作法，非 migration_surveys.sql 的舊 stopgap_anon_all）：
--   ENABLE RLS 且「不」建寬鬆 anon policy；後端必須帶 SUPABASE_SERVICE_ROLE_KEY（繞過 RLS）
--   才能寫入。前端埋點一律透過後端 API 代寫，不讓瀏覽器 anon 直接 insert。
-- 冪等，可安全重跑。

CREATE TABLE IF NOT EXISTS app_events (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      text NOT NULL,                       -- 受試者（對應 users.id / patient_id）
    session_id   text,                                -- 同一工作階段聚合用（前端產生）
    event_type   text NOT NULL,                       -- 大類：session|screen|feature|reminder|error|crash|api|data|edit|push
    event_name   text,                                -- 具體事件名（見 app_events_schema.md 目錄）
    target       text,                                -- 功能/畫面/題項識別（如 'risk_dashboard'、'survey:mdpiece-c5-mauq'）
    value        double precision,                    -- 選填數值 payload（時長秒、延遲分、HTTP 狀態碼…）
    metadata     jsonb,                               -- 任意附加，務必去識別化（不放姓名/原始作答）
    occurred_at  timestamptz NOT NULL DEFAULT now(),  -- 事件「實際發生」時間（前端帶，支援離線補送）
    created_at   timestamptz NOT NULL DEFAULT now()   -- 後端寫入時間
);

-- 聚合查詢：依使用者＋時間（每日/streak/時段）、依事件型別（錯誤率/功能採用）。
CREATE INDEX IF NOT EXISTS idx_app_events_user_time ON app_events (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_events_type      ON app_events (event_type, event_name);
CREATE INDEX IF NOT EXISTS idx_app_events_session   ON app_events (session_id);

ALTER TABLE app_events ENABLE ROW LEVEL SECURITY;
-- 刻意不建 anon 寬鬆 policy（規則 7：採較新的硬化作法）。後端 service_role 寫入；
-- 若日後要讓 authenticated 使用者讀自己的事件，再加 user_id = auth.uid() 的窄 policy。
