-- Supabase migration: 使用者 email（註冊時選填，收集後存在帳號上）
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/models.py 的 UserCreate.email、backend/routers/auth.py register()
--
-- email 為選填（nullable），不影響既有無 email 的帳號；目前僅「收集並存」，
-- 尚未啟用 email 驗證/重設（那需要可自動寄信的服務）。
-- 註：production 已透過 MCP apply_migration 加上此欄位；此檔為版本庫紀錄與
--     全新環境重建之用（ADD COLUMN IF NOT EXISTS 為冪等）。

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS email TEXT;
