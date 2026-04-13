# MD.Piece 醫師端（本機版）

給臨床醫師在本機使用的簡易前端，對接現有 FastAPI backend。

## 啟動方式

雙擊 `start-doctor.bat`，或手動執行：

```bash
# 1. 啟動後端（另一個終端機）
cd md.piece
uvicorn backend.main:app --reload --port 8000

# 2. 啟動醫師端前端
python -m http.server 3001 --directory frontend-doctor
```

開啟瀏覽器：http://localhost:3001

## 目錄結構

```
frontend-doctor/
├── index.html         # 入口頁
├── css/doctor.css     # 樣式
├── js/doctor.js       # 前端邏輯
└── README.md
```

## 功能規劃（待確認）

目前為骨架，尚未實作任何醫師功能。待與團隊討論後加入。
