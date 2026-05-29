-- Supabase migration: 登錄/註冊強化 — 安全問題重設 + 登入鎖定
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/auth.py、backend/db.py（users 表）
--
-- 新增欄位：
--   recovery_question     安全問題題目（明文，可顯示給使用者）
--   recovery_answer_hash  安全問題答案的 scrypt 雜湊（與 password_hash 同格式）
--   failed_login_count    連續登入/重設失敗次數（達 5 次上鎖）
--   locked_until          鎖定到期時間（ISO 字串；用 TEXT 以與 SQLite fallback 及
--                         supabase-py 回傳值一致，後端以字串解析比較）
--
-- 設計：本專案用 backend 自有 username+scrypt（非 Supabase Auth），鎖定狀態
-- 存在 users 列上，serverless 才能跨 lambda 持久（不可用記憶體計數）。

ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_question    TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_answer_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_count   INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until         TEXT;
