-- Supabase migration: diet_records 增加 calories 欄位（拍照算熱量功能）
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/diet.py（POST /diet/recognize、POST /diet/records）
--
-- calories：整餐估算熱量（kcal），來自食物照片辨識或手動，可為 null。
-- 註：production 已透過 MCP apply_migration 套用此欄位；此檔為版本庫紀錄與
--     全新環境重建之用（冪等，可安全重跑）。

ALTER TABLE diet_records ADD COLUMN IF NOT EXISTS calories INTEGER;
