# MD.Piece 醫師端（本機版）

給臨床醫師在本機使用的前端（Vite + React + Recharts + React Router），對接現有 FastAPI backend。

## 啟動方式

首次使用先裝依賴：

```bash
cd frontend-doctor
npm install
```

之後雙擊專案根目錄的 `start-doctor.bat`，或手動：

```bash
# 另一個終端機：後端
cd md.piece
uvicorn backend.main:app --reload --port 8000

# 本目錄：前端（dev 模式 HMR）
npm run dev
```

開啟瀏覽器：http://localhost:3001

## 技術棧

- Vite + React 19
- React Router（SPA 路由）
- Recharts（折線圖 / 順從率圖）
- Fetch API 透過 Vite proxy 轉發到 `http://localhost:8000`

## 目錄

```
frontend-doctor/
├── src/
│   ├── App.jsx                # 路由 + 佈局
│   ├── main.jsx               # React 入口
│   ├── lib/api.js             # fetch 包裝
│   ├── pages/                 # 各頁面
│   │   ├── Dashboard.jsx
│   │   ├── PatientList.jsx
│   │   ├── PatientDetail.jsx
│   │   ├── Alerts.jsx
│   │   └── Settings.jsx
│   └── styles/index.css
└── vite.config.js             # port 3001 + /api proxy
```

## 功能規劃

依 proposal 7.3 分 Phase 實作：

- **Phase 0** ✓ 骨架
- **Phase 1** ✓ 後端補表（`doctor_notes`、`medication_changes`、`alerts`）
- **Phase 2** ✓ 患者優先序 + 警示燈號（`PatientList`、`Alerts`）
- **Phase 3** ✓ 快速預覽 + 時間軸 + 備註（`PatientDetail`）
- **Phase 4**（部分）患者整合報告：情緒 × 服藥順從率（`Reports`）；待補：跨回診比較、LLM 文字摘要
- **Phase 5** 建議問診清單 + 衛教審核推送（LLM）

## 與患者端的串接

醫師端與患者端 PWA 共用同一個 FastAPI 後端與 Supabase 資料庫：

- 患者每日情緒（`/emotions`）、服藥打卡（`/medications/log`）、症狀分析會即時呈現在患者詳情頁
- 醫師寫入的備註（`/doctor-notes`）、調藥（`/medication-changes`）、警示確認/結案（`/alerts`）會反過來影響後續排序與提醒
- 後端 API 主機若不在 localhost，請至「設定」頁覆蓋 API base（存於 `localStorage.mdp.apiBase`）
- 進行寫入時的醫師身份也存在「設定」（`localStorage.mdp.doctorId`）

## 線上部署（子路徑 `/doctor`）

醫師端與患者端共用同一個 Vercel 專案，醫師端掛在 `https://mdpiece.life/doctor`：

- 根目錄 `vercel.json` 用 `@vercel/static-build` 在部署時跑 `npm run build`，輸出 `frontend-doctor/dist/`
- 路由：`/doctor/assets/*` → 靜態資源；`/doctor` 與其他 SPA 路徑 → `index.html`（React Router 接手）
- `vite.config.js` 在 build 模式下自動把 `base` 設為 `/doctor/`，所以 dev (`npm run dev`) 仍走 `http://localhost:3001/`
- `main.jsx` 用 `import.meta.env.BASE_URL` 設 React Router `basename`，dev 與線上都對
- `.env.production` 的 `VITE_API_URL=` 為空字串 → 線上 build 走相對 root 路徑，例如 `fetch('/patients/')` 會被 Vercel 路由到 `api/index.py`
