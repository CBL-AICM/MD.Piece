-- Supabase migration: 建立 reward_redemptions 表（健康積分／獎勵中心的兌換紀錄）
-- 執行方式：在 Supabase Dashboard → SQL Editor 貼上執行
-- 對應 backend/routers/rewards.py 的 POST /rewards/redeem 與 GET /rewards/redemptions。
--
-- 說明：積分本身（earned）是對既有紀錄表的唯讀換算，不需建表；唯一需要持久化的
--      新狀態是「兌換意願」——使用者花點數登記一項獎勵，由院方線下發放。
--      available = earned − sum(reward_redemptions.cost)。

CREATE TABLE IF NOT EXISTS reward_redemptions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   TEXT NOT NULL,
    reward_id    TEXT NOT NULL,
    reward_name  TEXT,
    cost         INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'requested',  -- requested | fulfilled | cancelled
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 加速 GET /rewards/redemptions 與餘額加總
CREATE INDEX IF NOT EXISTS reward_redemptions_patient_idx
    ON reward_redemptions (patient_id, created_at DESC);

-- 規則 7：沿用目前「實際生效」的安全姿態——RLS 開啟 + 一條 stopgap_anon_all
-- 允許全表 policy，與其他所有使用者資料表（symptom_entries / survey_responses /
-- ehl_results …）一致。後端目前仍帶 anon key，若不建 policy，anon 寫入會被 RLS
-- 擋下（PostgREST 4xx），導致兌換失敗。待後端全面切換 service_role 後，再隨其他表
-- 一起把這些 stopgap policy 收斂掉。見 backend/db.py 開頭說明。
ALTER TABLE reward_redemptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY stopgap_anon_all ON reward_redemptions
    FOR ALL TO anon, authenticated
    USING (true) WITH CHECK (true);
