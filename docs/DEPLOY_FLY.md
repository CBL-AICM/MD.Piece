# 部署到 Fly.io（取代 Vercel）

> 背景：Vercel Hobby 免費方案把本站判定為商用（fair-use），帳號被標記 `limited`，
> 所有新部署在 provisioning 階段就被拒（`Resource provisioning failed`），production 卡在舊版。
> 改用 Fly.io（容器型、常駐不睡、允許商用）。Supabase 資料庫不變。

## 架構對照

| 項目 | Vercel（舊） | Fly.io（新） |
|---|---|---|
| 進入點 | `api/index.py`（serverless，僅 API） | `backend.main:app`（單一程序：API + 前端靜態檔）|
| 前端靜態檔 | `@vercel/static` 獨立服務 | 由 FastAPI `StaticFiles` 一起服務 |
| 容器 | 無（serverless） | `Dockerfile`（python:3.12-slim）|
| 設定 | `vercel.json` | `fly.toml` |
| Cron | `vercel.json` crons | `.github/workflows/cron-ema.yml`（GitHub Actions）|
| 資料庫 | Supabase | Supabase（不變）|

> `vercel.json` / `api/index.py` 仍保留在 repo（未刪），需要時可回退 Vercel。

## 前置

```bash
# 安裝 flyctl 並登入（用一個「非 limited」的帳號）
curl -L https://fly.io/install.sh | sh
fly auth login
```

## 1. 建立 app

```bash
cd <repo 根目錄>
fly launch --no-deploy        # 偵測到 fly.toml / Dockerfile；若 app 名稱 "md-piece" 被佔用，
                              # 依提示改一個唯一名稱，並把 fly.toml 的 app 一併改掉
```

## 2. 設定 secrets

把目前 Vercel 上設的環境變數搬過來。**關鍵**：資料庫要帶 **service_role**（繞過 RLS），
否則所有寫入會被 RLS 擋成 500。

```bash
fly secrets set \
  SUPABASE_URL="https://tbqvpqvvvgfgaezxbhkz.supabase.co" \
  SUPABASE_SERVICE_ROLE_KEY="<Supabase service_role secret>" \
  LLM_PROVIDER="groq" \
  GROQ_API_KEY="<...>" \
  GEMINI_API_KEY="<...>" \
  ANTHROPIC_API_KEY="<...>" \
  JWT_SECRET="<隨機 64 字元；python -c 'import secrets;print(secrets.token_urlsafe(48))'>" \
  APP_SECRET_KEY="<隨機字串>" \
  VAPID_PUBLIC_KEY="<...>" \
  VAPID_PRIVATE_KEY="<...>" \
  VAPID_CONTACT_EMAIL="mailto:admin@mdpiece.life" \
  CRON_TOKEN="<隨機字串，與 GitHub Actions 的同值>"
```

完整清單與說明見 `.env.example`。對照重點：

| Secret | 必填? | 說明 |
|---|---|---|
| `SUPABASE_URL` | ✅ | Supabase 專案 URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | **service_role** secret（不是 anon！否則寫入全 500）|
| `LLM_PROVIDER` | ✅ | production 目前用 `groq` |
| `GROQ_API_KEY` | ✅ | 主 LLM |
| `GEMINI_API_KEY` | 建議 | fallback，繁中品質佳 |
| `ANTHROPIC_API_KEY` | 選填 | fallback |
| `JWT_SECRET` | ✅ | 未設 `/auth/login` 會 500 |
| `APP_SECRET_KEY` | ✅ | 應用密鑰 |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CONTACT_EMAIL` | 推播需要 | 未設則手機推播停用、僅站內通知 |
| `CRON_TOKEN` | ✅(cron) | 與 GitHub Actions secret 同值 |

## 3. 部署

```bash
fly deploy
fly open            # 開啟 *.fly.dev 預設網址先驗證
curl https://<app>.fly.dev/healthz          # {"ok":true}
curl https://<app>.fly.dev/health/llm       # groq/gemini ready
```

## 4. 綁定自訂網域 www.mdpiece.life

```bash
fly certs add www.mdpiece.life
fly certs show www.mdpiece.life     # 顯示要設的 DNS 記錄
```

到網域 DNS 後台（目前由 Vercel 管理）把 `www` 指向 Fly：
- **CNAME** `www` → `<app>.fly.dev`（或依 `fly certs show` 給的 A/AAAA）
- 等憑證簽發（`fly certs show` 變綠）後，把 production 流量切到 Fly。

> ⚠️ DNS 與憑證簽發有傳播延遲；建議先用 `*.fly.dev` 驗證功能無誤，再切 DNS。

## 5. Cron

GitHub Actions（`.github/workflows/cron-ema.yml`）每日 01:00 UTC 打 `/ema/cron/run`。
到 repo **Settings → Secrets and variables → Actions** 新增 secret `CRON_TOKEN`，
值與步驟 2 的 Fly `CRON_TOKEN` 相同。可在 Actions 頁手動 `Run workflow` 測試。

## 成本

Fly.io 已改為 pay-as-you-go（無傳統免費 tier）。一台常駐 `shared-cpu-1x/512MB`
約 **US$2-3/月**，比 Vercel Pro（US$20/月）省；要更省可把 `fly.toml` 的
`auto_stop_machines` 設回開啟（會有冷啟動）。
