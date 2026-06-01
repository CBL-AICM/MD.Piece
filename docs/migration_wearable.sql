-- 穿戴裝置雲端連接 — Supabase / PostgreSQL
-- 對應 backend/services/wearable_sync.py、backend/routers/sleep.py 的 OAuth 端點
-- 與 db.py 的 SQLite fallback（_SCHEMAS["wearable_connections"]）。
--
-- 用途：存使用者授權後的廠商 OAuth token（參考實作 provider='fitbit'），
-- 供後端定期/手動同步睡眠紀錄，寫成 sleep_sessions 的 source='imported'。

CREATE TABLE IF NOT EXISTS wearable_connections (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        text NOT NULL,
    provider       text NOT NULL,          -- 'fitbit'（未來：'oura' / 'withings' …）
    access_token   text,
    refresh_token  text,
    scope          text,
    expires_at     timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_wearable_conn_user ON wearable_connections (user_id);

-- 安全性（與 db.py 2026-05-29 之後的姿態一致，刻意不照舊 migration 的
-- DISABLE RLS）：本表存第三方 OAuth token，屬機密。啟用 RLS 且「不建任何
-- policy」→ anon 角色讀寫一律被拒，只有帶 service_role secret 的後端能存取。
ALTER TABLE wearable_connections ENABLE ROW LEVEL SECURITY;
