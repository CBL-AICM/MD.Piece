-- 人格化(persona)表 — 每位虛擬患者的第一人稱人生自述 + 跨 cohort 家族連結。
-- 由 ml/personify.py 寫入；已於 2026-06 apply 到正式 Supabase。
--
-- persona jsonb 內含：nickname / life_story(第一人稱、扣合出生年代時空背景) /
--   birth_minguo / era(世代) / hometown / region_macro / occupation /
--   household / spouse / parents[] / children[] / siblings[] / family_summary
-- patient_id 與 sim_world_state 一致；user_id 僅已註冊者有。

create table if not exists sim_persona (
  patient_id text primary key,
  user_id    uuid,
  disease_id text,
  persona    jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists idx_sim_persona_user on sim_persona(user_id);

-- 後端以 anon client 寫入(與其他 sim 表一致)，關閉 RLS
alter table sim_persona disable row level security;
