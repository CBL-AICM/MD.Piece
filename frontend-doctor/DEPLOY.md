# 醫師端部署到 doctor.mdpiece.life

醫師端 (`frontend-doctor/`) 是獨立的 Vite + React SPA，與患者端 (`frontend/`) 共用同一個 FastAPI 後端與 Supabase 資料庫，但部署為**獨立的 Vercel 專案**，掛在子網域。

## 為什麼分兩個 Vercel 專案

- 患者端是純靜態 + Python serverless（用 root `vercel.json` 的 legacy `builds + routes`）
- 醫師端需要先 `npm run build` 才能部署（Vite SPA）
- 一個 `vercel.json` 同時做兩種 build target 會很複雜，分開最乾淨

## 兩個專案的關係

```
mdpiece.life / www.mdpiece.life     ←  Vercel 專案 A（既有）
  ├── frontend/                          靜態 PWA（含「年長版」切換）
  └── api/index.py                       FastAPI（所有後端 API）

doctor.mdpiece.life                  ←  Vercel 專案 B（要新增）
  └── frontend-doctor/                   Vite + React，build 後丟 dist/
                                         API 呼叫跨網域到 www.mdpiece.life
                                         （CORS 已開 allow_origins=["*"]）
```

## 你要在 Vercel + DNS 做的事

### 1. Vercel — 建立第二個專案

1. Vercel Dashboard → **Add New Project**
2. 選同一個 GitHub repo（CBL-AICM/MD.Piece）
3. **Project Name**：例如 `mdpiece-doctor`
4. **Framework Preset**：Vite（會自動偵測；本目錄已放 `vercel.json` 與 `.env.production` 強制設定）
5. **Root Directory**：`frontend-doctor`
6. **Production Branch**：`main`（或先用本 feature 分支驗證 preview）

部署一次，確認 preview URL 開得起來、能讀患者資料、能新增備註。

### 2. Vercel — 加 domain

新專案 → Settings → **Domains** → 新增 `doctor.mdpiece.life`。

Vercel 會給你一筆 DNS 設定（通常是 CNAME）。

### 3. DNS provider

加一筆 CNAME：

```
doctor.mdpiece.life   CNAME   cname.vercel-dns.com
```

> 如果 DNS 是放在 Vercel，這步會自動完成。
>
> 如果是 Cloudflare，記得把 proxy（橘色雲）關掉，改成 DNS only，否則 Vercel 拿不到 SSL 驗證。

等個 2–10 分鐘 DNS propagate，回 Vercel Domain 那頁按 Refresh，看到綠勾就完成。

## 驗證

打開 `https://doctor.mdpiece.life`：

- 看得到醫師端介面（深色、左上 MD Piece 醫師端）
- 儀表板能讀到患者數（代表 API 正常）
- 新增備註成功（代表寫入也跨網域成功）

如果儀表板顯示「離線：…」：
- 打開瀏覽器 console 看實際錯誤
- 通常是 CORS 或 API URL 錯，去「設定」頁手動覆寫 API base 試試

## 環境變數

`.env.production` 已內含 `VITE_API_URL=https://www.mdpiece.life`。如果以後要改成獨立的 API 子網域（例如 `api.mdpiece.life`），改這個檔案重新 build 即可。

也可以在 Vercel 專案 → Settings → Environment Variables 設 `VITE_API_URL`，會覆寫 `.env.production`。
