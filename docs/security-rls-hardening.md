# 安全修補 Runbook：Supabase 金鑰外洩 + RLS 全關

> ⚠️ 重大風險。此 repo 為 **public**，而 `backend/db.py` 內嵌了 Supabase **anon 金鑰**
> （`_DEFAULT_SUPABASE_KEY`），且 Supabase 上 **23 張表 RLS（Row Level Security）全關閉**。
> 兩者疊加 = **任何人都能用公開的 anon key 直接打 Supabase REST API，繞過後端讀寫全部病患資料**
> （patients / users / medications / symptoms_log…）。這是醫療個資外洩等級的問題。

## 為什麼不能「直接開 RLS」一鍵修

目前後端（`db.py`）用的是 **anon** 金鑰，靠 FastAPI 層自己的 JWT + `_enforce_self` 擋權限。
若現在就 `ENABLE ROW LEVEL SECURITY` 而不先換金鑰，anon 角色會被 RLS 擋下 →
**整個 App 的資料庫查詢立刻全掛**。所以必須照下面的順序，且其中幾步只能你在
Supabase / Vercel 後台操作（自動化工具沒有權限）。

## 修補順序（務必照順序）

### 步驟 1 — 後端改用 service_role 金鑰（你操作）
`service_role` 金鑰**會繞過 RLS**，所以後端改用它之後，即使開了 RLS、擋掉 anon，
後端仍能正常運作。

1. Supabase Dashboard → 專案 `tbqvpqvvvgfgaezxbhkz` → Project Settings → API Keys
2. 複製 **service_role** 金鑰（標示 `secret`，**絕不可外流 / 不可放進前端或 repo**）
3. Vercel → 專案 `md-piece` → Settings → Environment Variables（Production）：
   - `SUPABASE_URL = https://tbqvpqvvvgfgaezxbhkz.supabase.co`
   - `SUPABASE_KEY = <剛剛的 service_role 金鑰>`
4. Redeploy，確認 App 功能正常（此時仍未開 RLS，anon 也還能用，只是後端已改吃 env 的 service_role）。

### 步驟 2 — 啟用 RLS（套用本目錄的 migration）
後端確定走 service_role 後，套用 `enable_rls.sql`（見下）。RLS 開啟、且**不建任何 policy**
→ anon / authenticated 角色一律無權限，service_role 照常（後端不受影響）。

可用 Supabase MCP `apply_migration` 套用，或在 Dashboard → SQL Editor 貼上執行。
（你確認步驟 1 完成後，我也可以幫你用 MCP 套這支 migration。）

### 步驟 3 — 移除程式碼內嵌金鑰（PR）
確認 Vercel 已有 `SUPABASE_URL` / `SUPABASE_KEY` env 後，把 `db.py` 的
`_DEFAULT_SUPABASE_URL` / `_DEFAULT_SUPABASE_KEY` 改為「只讀 env、無內建預設」，
避免再把金鑰寫在 public repo。本步驟在 Vercel env 設好前**不可合併**，否則
serverless 缺憑證會 500。

### 步驟 4 — 輪換已外洩的 anon 金鑰（你操作）
舊 anon 金鑰已永久存在於 public git 歷史，**必須在 Supabase 輪換 / 失效**。
完成 RLS（步驟 2）後，舊 anon key 即使沒輪換也已無法存取資料，但仍建議輪換以求乾淨。

---

## enable_rls.sql（步驟 2 用；先完成步驟 1 再套）

```sql
-- 先決條件：後端 SUPABASE_KEY 已改為 service_role（service_role 繞過 RLS）。
-- 開 RLS、不建 policy → anon / authenticated 一律拒絕；service_role 照常。
ALTER TABLE public.patients            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctors             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_records     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.symptoms_log        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotions            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medications         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medication_logs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medication_effects  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medication_changes  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctor_notes        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diet_records        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.water_intake_daily  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reminders           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.push_subscriptions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_inbox  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_bell_prefs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.measurement_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bell_sounds         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.custom_procedure_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_profiles    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.follow_ups          ENABLE ROW LEVEL SECURITY;
```

## 補充：後端層權限漏洞（與上獨立，需另修）

即使資料庫層收緊，FastAPI 層仍有未做擁有權檢查的 router（例如 `alerts.py` 的
`GET /alerts/` 不帶 patient_id 會回全表）。應比照 `patients.py` 的 `_enforce_self`
用 token 的 `sub` 強制過濾。這部分屬程式碼修正，可另開 PR 處理。
