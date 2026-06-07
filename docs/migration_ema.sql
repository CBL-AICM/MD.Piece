-- Supabase migration: EMA（生態瞬時評估）觸發引擎 — config 驅動的不定時 / 情境問卷推送
-- 執行方式：Supabase Dashboard → SQL Editor 貼上執行（或 MCP apply_migration）
-- 對應 backend/routers/ema.py 與其 _SCHEMAS.setdefault（SQLite fallback）。
--
-- 為什麼：把問卷融合進 App，依「時間窗（不定時）」與「使用情境（app_events 事件）」
--   推送問卷，結果走既有 surveys 引擎回後端。觸發規則由研究者後台用 config 定義
--   （data-driven，不改 code）。兩表：
--     ema_rules      — 規則定義（觸發條件 + 要推哪份 survey）
--     ema_deliveries — 觸發後產生的「待作答」佇列；in-app 與 Web Push 兩通道共用。
--
-- RLS：採 2026-05-29 後硬化作法（ENABLE RLS、無 anon policy、後端 service_role 寫入）。
-- 冪等，可安全重跑。

CREATE TABLE IF NOT EXISTS ema_rules (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    study             text,
    name              text NOT NULL,
    survey_key        text NOT NULL,                 -- 要推送的問卷（surveys.key；可為短微問卷或完整量表）
    trigger_config    jsonb NOT NULL,                -- {type:'event'|'time', match/windows, cooldown_min, max_per_day, per_window}
    expires_after_min integer NOT NULL DEFAULT 120,  -- 推送後多久未作答即過期
    active            integer NOT NULL DEFAULT 1,
    created_by        text,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ema_deliveries (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       text NOT NULL,
    rule_id       text,
    survey_key    text NOT NULL,
    trigger_type  text,                              -- 'time' | 'event'
    status        text NOT NULL DEFAULT 'pending',   -- pending | completed | expired
    context       jsonb,                             -- 觸發脈絡（事件內容 / 時間窗）
    scheduled_at  text,                              -- 預定surface時間（本地 ISO）
    shown_at      text,                              -- 已 push / 已彈出（避免重複 push）
    completed_at  text,
    response_id   text,                              -- 連結 survey_responses.id
    expires_at    text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ema_rules_study   ON ema_rules (study, active);
CREATE INDEX IF NOT EXISTS idx_ema_deliv_user    ON ema_deliveries (user_id, status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_ema_deliv_rule    ON ema_deliveries (rule_id, user_id, scheduled_at);

ALTER TABLE ema_rules      ENABLE ROW LEVEL SECURITY;
ALTER TABLE ema_deliveries ENABLE ROW LEVEL SECURITY;
-- 刻意不建 anon 寬鬆 policy（規則 7：硬化作法）。後端 service_role 寫入；
-- 前端讀自己的 pending 走後端 API（GET /ema/pending），不直接 anon 查表。
