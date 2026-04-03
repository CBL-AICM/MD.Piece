<div align="center">

# 🩺 MD.Piece

**AI 驅動的醫療輔助 PWA 平台 — 讓醫病溝通更順暢，讓健康管理更智慧**

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-mdpiece.life-blue?style=for-the-badge)](https://www.mdpiece.life/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-000?style=flat-square&logo=vercel)](https://vercel.com)
[![PWA](https://img.shields.io/badge/PWA-Enabled-5A0FC8?style=flat-square&logo=pwa&logoColor=white)](#)
[![CI](https://github.com/human530/MD.Piece/actions/workflows/python-app.yml/badge.svg)](https://github.com/human530/MD.Piece/actions/workflows/python-app.yml)

</div>

---

## 📖 簡介

**MD.Piece** 是一個漸進式網頁應用（PWA）醫療輔助平台，旨在：

1. **改善醫病溝通**：透過數位化病歷管理，讓醫師與病患之間的資訊傳遞更完整
2. **AI 症狀分析**：當病患突發症狀時，提供智慧化建議與分診指引
3. **慢性病管理**：結合情緒追蹤、衛教資源與個人化基準值，協助長期健康管理

> 🔗 **線上體驗**：[www.mdpiece.life](https://www.mdpiece.life/)

---

## ✨ 核心功能

### 🏥 病歷管理
- 病患 / 醫師資料 CRUD
- 就診紀錄建立與查詢（症狀、診斷、處方、臨床筆記）
- 多條件進階篩選（依病患、醫師、診斷、日期區間）

### 🤖 AI 症狀分析
- 常見症狀快速查詢（發燒、頭痛、咳嗽等）
- Claude AI 多症狀綜合分析：
  - 緊急程度判定（急診 / 高 / 中 / 低）
  - 可能診斷與機率評分
  - 推薦就診科別
- 症狀分析歷史追蹤

### 🌱 小禾 — AI 情緒支持夥伴
- Claude Haiku 驅動的溫暖對話陪伴
- 病患 / 家屬模式切換
- 長輩友善介面
- 隱私保護式情緒摘要
- 靜默守護者：持續低落情緒預警

### 🚦 智慧分診系統
- 雙層 AI 分診：規則式急症偵測 + LLM 個人化判斷
- 個人化健康基準值（2 週平均症狀 / 用藥 / 情緒）

### 📚 慢性病衛教
- 品質把關的靜態衛教文章（非 LLM 生成）
- ICD-10 診斷碼連動個人化衛教
- 情境式健康提醒

### 🔬 AutoResearch 實驗追蹤
- ML 模型訓練實驗管理（整合 Colab / Kaggle）
- 驗證指標追蹤（val_bpb）與排行榜
- 實驗統計儀表板與趨勢圖表
- TSV 批次匯入 / 匯出

---

## 🛠 技術架構

| 層級 | 技術 |
|------|------|
| **前端** | Vanilla JS PWA（Service Worker 離線支援） |
| **後端** | FastAPI (Python 3.10+) |
| **資料庫** | Supabase (PostgreSQL)，SQLite 本地備援 |
| **AI 服務** | Anthropic Claude API |
| **MCP Server** | FastMCP — 暴露 10+ 工具供 AI Agent 使用 |
| **部署** | Vercel（Serverless Python + CDN 靜態資源） |
| **CI/CD** | GitHub Actions（flake8 + pytest + CodeQL） |

---

## 📁 專案結構

```
md.piece/
├── backend/
│   ├── main.py               # FastAPI 入口
│   ├── models.py             # Pydantic 資料模型
│   ├── routers/              # API 路由模組
│   │   ├── patients.py       # 病患管理
│   │   ├── doctors.py        # 醫師管理
│   │   ├── records.py        # 病歷紀錄
│   │   ├── symptoms.py       # 症狀分析
│   │   ├── triage.py         # 智慧分診
│   │   ├── emotions.py       # 情緒追蹤
│   │   ├── xiaohe.py         # 小禾聊天機器人
│   │   ├── education.py      # 衛教資訊
│   │   ├── medications.py    # 藥物管理
│   │   ├── reports.py        # 報告生成
│   │   └── research.py       # AutoResearch 實驗
│   └── services/             # 業務邏輯
│       ├── claude_service.py # Claude AI 整合
│       └── supabase_service.py
├── frontend/                 # PWA 前端
│   ├── index.html
│   ├── manifest.json
│   ├── sw.js                 # Service Worker
│   ├── js/app.js
│   └── css/style.css
├── mcp_server/               # MCP Server（AI Agent 整合）
├── api/index.py              # Vercel 部署入口
├── docs/                     # 專案文件
├── config/                   # 設定檔
└── tests/                    # 測試
```

---

## 🚀 快速開始

### 環境需求

- Python 3.10+
- [Anthropic API Key](https://console.anthropic.com/)（選用，AI 功能）
- [Supabase](https://supabase.com/) 專案（選用，無則使用 SQLite）

### 安裝與啟動

```bash
# 1. Clone 專案
git clone https://github.com/human530/MD.Piece.git
cd MD.Piece

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env 填入你的 API keys

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 啟動後端
uvicorn backend.main:app --reload --port 8000

# 5. 啟動前端
python -m http.server 3000 --directory frontend
```

### MCP Server（搭配 Claude Code 使用）

```bash
cd mcp_server
uv sync
uv run server.py
```

---

## 📄 環境變數

參考 [`.env.example`](.env.example)：

| 變數 | 說明 |
|------|------|
| `SUPABASE_URL` | Supabase 專案 URL |
| `SUPABASE_KEY` | Supabase API Key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key |
| `APP_ENV` | 環境（development / production） |

---

## 🤝 貢獻

歡迎貢獻！請參考以下流程：

1. Fork 此專案
2. 建立功能分支：`git checkout -b feature/your-feature`
3. 提交變更並開啟 Pull Request

---

## 📜 授權

本專案為研究用途開發。

---

<div align="center">

**[🌐 www.mdpiece.life](https://www.mdpiece.life/)**

Made with ❤️ for better healthcare communication

</div>
