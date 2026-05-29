-- Supabase migration: Phase 2.1 — users.supabase_user_id（隱型 provision 對應欄位）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/services/supabase_auth.py、backend/routers/auth.py
--
-- 用途：把自管 scrypt 帳號對應到 Supabase Auth user 的 uid。additive、可回滾。
-- 仍藏在 feature flag AUTH_SUPABASE_ENABLED 後，加欄位本身對現有流程零影響。

ALTER TABLE users ADD COLUMN IF NOT EXISTS supabase_user_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_supabase_uid
  ON users(supabase_user_id) WHERE supabase_user_id IS NOT NULL;
