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

- **Phase 0** ✓ 骨架（本 PR）
- **Phase 1** 後端補表（`doctor_notes`、`medication_changes`、`alerts`）
- **Phase 2** 患者優先序 + 警示燈號
- **Phase 3** 快速預覽 + 時間軸 + 備註
- **Phase 4** 三十天整合報告（Recharts 圖表）+ 調藥追蹤 + 跨回診比較
- **Phase 5** 建議問診清單 + 衛教審核推送（LLM）
