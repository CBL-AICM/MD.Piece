-- Supabase migration: 病患備忘（memo，文字／照片小紙條，可標記給醫師看）
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/memos.py
--
-- 以 (patient_id, client_id) 做幂等 upsert：client_id = 前端產生的 id，
-- 讓本機既有 memo 可補傳、編輯覆蓋、重送不重複。
-- 註：production 已透過 MCP apply_migration 建立本表；此檔為版本庫紀錄與
--     全新環境重建之用（CREATE ... IF NOT EXISTS 為冪等，可安全重跑）。

CREATE TABLE IF NOT EXISTS memos (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  TEXT NOT NULL,
    client_id   TEXT,
    kind        TEXT,
    content     TEXT,
    photo_data  TEXT,
    for_doctor  BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS memos_patient_client_idx
    ON memos (patient_id, client_id);

-- RLS：與其餘表一致，啟用後掛 stopgap 政策（後端帶 service_role 繞過 RLS；
-- 此政策供直連 anon/authenticated 用，詳見 docs/security-rls-hardening.md）。
ALTER TABLE memos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stopgap_anon_all ON memos;
CREATE POLICY stopgap_anon_all ON memos
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
