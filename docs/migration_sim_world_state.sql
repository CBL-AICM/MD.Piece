-- 活世界(living world)狀態表 — 持久化每位虛擬患者的可變模擬狀態，
-- 供 ml/world.py 每日 tick 續推。已於 2026-06 apply 到正式 Supabase。
--
-- sim jsonb 內含：age/sex/disease_id/sim_day/registered_sim_day/activity/
--   irreversible_burden/active_triggers/treatments/archetype/adopted/
--   adherence_mult/comorbidities/severity_band/severity_score/tick_seed/
--   churn_at_day/nickname …
-- status：candidate(未註冊) / active / churned / deceased / recovered

create table if not exists sim_world_state (
  patient_id     text primary key,
  user_id        uuid,
  disease_id     text not null,
  status         text not null default 'candidate',
  last_tick_date date,
  sim            jsonb not null default '{}'::jsonb,
  updated_at     timestamptz not null default now()
);

create index if not exists idx_sim_world_status on sim_world_state(status);

-- 後端以 anon client 寫入(與其他 sim 表一致)，關閉 RLS
alter table sim_world_state disable row level security;
