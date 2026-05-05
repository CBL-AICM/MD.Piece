<div align="center">

# 🩺 MD.Piece

**AI 驅動的醫療輔助 PWA 平台 — 讓醫病溝通更順暢，讓健康管理更智慧**

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-mdpiece.life-blue?style=for-the-badge)](https://www.mdpiece.life/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-000?style=flat-square&logo=vercel)](https://vercel.com)
[![PWA](https://img.shields.io/badge/PWA-Enabled-5A0FC8?style=flat-square&logo=pwa&logoColor=white)](#)
[![CI](https://github.com/CBL-AICM/MD.Piece/actions/workflows/python-app.yml/badge.svg)](https://github.com/CBL-AICM/MD.Piece/actions/workflows/python-app.yml)

</div>

---

## 📖 簡介

**MD.Piece** 是一個漸進式網頁應用（PWA）醫療輔助平台，目標是：

1. **改善醫病溝通**：以結構化病歷與雙端介面（病患 / 醫師），讓資訊傳遞更完整
2. **AI 症狀分析**：突發症狀時提供智慧化建議與分診指引
3. **慢性病管理**：結合情緒追蹤、衛教資源與個人化基準值，協助長期健康管理

> 🔗 **線上體驗**：[www.mdpiece.life](https://www.mdpiece.life/)（病患端） · [www.mdpiece.life/doctor](https://www.mdpiece.life/doctor)（醫師端）

---

## ✨ 核心功能

### 🏥 病歷管理
- 病患 / 醫師資料 CRUD、就診紀錄、處方、臨床筆記
- 醫師端獨立介面（`frontend-doctor`）：病患總覽、用藥變更追蹤、檢驗報告
- 多條件進階篩選（病患 / 醫師 / 診斷 / 日期區間）

### 🤖 AI 症狀分析
- 常見症狀快速查詢（發燒、頭痛、咳嗽等）
- 多症狀綜合分析：緊急程度判定、可能診斷與機率、推薦科別
- 症狀分析歷史追蹤

### 🌱 小禾 — AI 情緒支持夥伴
- LLM 驅動的溫暖對話陪伴，支援病患 / 家屬模式切換
- 長輩友善介面、隱私保護式情緒摘要
- 靜默守護者：持續低落情緒預警

### 🚦 智慧分診系統
- 雙層判斷：規則式急症偵測 + LLM 個人化分析
- 個人化健康基準值（2 週平均症狀 / 用藥 / 情緒）

### 📚 慢性病衛教
- 品質把關的靜態衛教文章（非 LLM 生成）
- ICD-10 診斷碼連動個人化衛教
- 情境式健康提醒

### 🔬 AutoResearch 實驗追蹤
- ML 模型訓練實驗管理（整合 Colab / Kaggle）
- 驗證指標追蹤（val_bpb）與排行榜
- 統計儀表板、趨勢圖表、TSV 批次匯入 / 匯出

---

## 🛠 技術架構

| 層級 | 技術 |
|------|------|
| **病患前端** | Vanilla JS PWA（Service Worker 離線支援） |
| **醫師前端** | `frontend-doctor/`（獨立靜態建置） |
| **後端** | FastAPI (Python 3.10+) |
| **資料庫** | Supabase (PostgreSQL)，SQLite 本地備援 |
| **LLM** | 多 Provider 支援：Ollama（本地）/ Groq / Anthropic Claude，含自動 fallback |
| **MCP Server** | FastMCP — 暴露工具供 Claude Code 等 AI Agent 使用 |
| **部署** | Vercel（Serverless Python `api/index.py` + 靜態前端 CDN） |
| **CI/CD** | GitHub Actions（flake8 + pytest + CodeQL） |

### LLM Provider 切換

透過 `LLM_PROVIDER` 環境變數選擇：

- `ollama` — 本地零成本、資料不出本機（預設、開發用）
- `groq` — 雲端免費 API，速度快
- `anthropic` — Claude API（推薦給 Vercel 部署）

主 provider 失敗會自動依序嘗試 `anthropic → groq → ollama`，只要任一可用即可運作。

---

## 📁 專案結構

```
md.piece/
├── api/
│   └── index.py                  # Vercel Serverless 入口
├── backend/
│   ├── main.py                   # FastAPI 入口
│   ├── models.py                 # Pydantic 資料模型
│   ├── db.py                     # 資料庫連線
│   ├── routers/                  # API 路由模組
│   │   ├── auth.py               # 認證
│   │   ├── patients.py           # 病患管理
│   │   ├── doctors.py            # 醫師管理
│   │   ├── records.py            # 病歷紀錄
│   │   ├── symptoms.py           # 症狀分析
│   │   ├── triage.py             # 智慧分診
│   │   ├── emotions.py           # 情緒追蹤
│   │   ├── xiaohe.py             # 小禾聊天機器人
│   │   ├── education.py          # 衛教資訊
│   │   ├── medications.py        # 藥物管理
│   │   ├── medication_changes.py # 用藥變更追蹤
│   │   ├── doctor_notes.py       # 醫師筆記
│   │   ├── labs.py               # 檢驗報告
│   │   ├── diet.py               # 飲食記錄
│   │   ├── alerts.py             # 健康警示
│   │   ├── reports.py            # 報告生成
│   │   └── research.py           # AutoResearch 實驗
│   ├── services/
│   │   ├── llm_service.py        # 多 Provider LLM 抽象層
│   │   ├── claude_service.py     # Anthropic Claude 整合
│   │   ├── supabase_service.py   # Supabase 整合
│   │   ├── ai_analyzer.py        # 症狀分析邏輯
│   │   ├── knowledge_analysis.py # 知識庫分析
│   │   ├── education_content.py  # 衛教內容
│   │   └── news_feed.py          # 新聞訂閱
│   └── utils/                    # 分診規則、基準值、ICD-10
├── frontend/                     # 病患端 PWA
│   ├── index.html
│   ├── manifest.json
│   ├── sw.js                     # Service Worker
│   ├── js/ · css/ · icons/
├── frontend-doctor/              # 醫師端應用（獨立建置）
├── mcp_server/                   # MCP Server（AI Agent 整合）
├── docs/                         # 專案文件
├── config/                       # 設定檔
├── tests/                        # 測試
└── vercel.json                   # Vercel 部署設定
```

---

## 🚀 快速開始

### 環境需求

- Python 3.10+
- 任一 LLM Provider（擇一即可）：
  - 本地 [Ollama](https://ollama.com/)（預設、零成本）
  - [Groq API Key](https://console.groq.com/keys)（免費）
  - [Anthropic API Key](https://console.anthropic.com/)
- [Supabase](https://supabase.com/) 專案（選用，無則使用 SQLite）

### 安裝與啟動

```bash
# 1. Clone 專案
git clone https://github.com/CBL-AICM/MD.Piece.git
cd MD.Piece

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env，至少設定 LLM_PROVIDER 與對應的 key

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 啟動後端（http://localhost:8000）
uvicorn backend.main:app --reload --port 8000

# 5. 啟動病患端前端（http://localhost:3000）
python -m http.server 3000 --directory frontend
```

API 文件可至 `http://localhost:8000/docs` 查看（FastAPI 自動產生）。

### 醫師端前端

```bash
cd frontend-doctor
npm install
npm run dev
```

### MCP Server（搭配 Claude Code 使用）

```bash
cd mcp_server
uv sync
uv run server.py
```

MCP Server 透過 STDIO 與 Claude Code 溝通，連接 `http://localhost:8000` 的後端 API。

---

## 📄 環境變數

完整列表參考 [`.env.example`](.env.example)：

| 變數 | 說明 |
|------|------|
| `LLM_PROVIDER` | LLM 提供者：`ollama` / `groq` / `anthropic` |
| `ANTHROPIC_API_KEY` | Claude API Key（provider=anthropic 或 fallback） |
| `GROQ_API_KEY` | Groq API Key（provider=groq 或 fallback） |
| `OLLAMA_BASE_URL` | Ollama 伺服器位址（預設 `http://localhost:11434`） |
| `SUPABASE_URL` | Supabase 專案 URL |
| `SUPABASE_KEY` | Supabase API Key |
| `DATABASE_URL` | 資料庫連線字串（預設 SQLite） |
| `APP_ENV` | 環境（`development` / `production`） |
| `APP_SECRET_KEY` | 應用程式密鑰 |

---

## 🧪 測試

```bash
pytest
```

測試設定見 `pytest.ini`，CI 由 GitHub Actions 自動執行（flake8 + pytest + CodeQL）。

---

## 🤝 貢獻

歡迎貢獻！流程：

1. Fork 此專案
2. 建立功能分支：`git checkout -b claude/your-feature`
3. 提交變更並開啟 Pull Request（不直接 push 到 `main`）

### 貢獻者

<!-- CONTRIBUTORS:START -->
<table>
  <tr>
    <td align="center"><a href="https://github.com/human530"><img src="https://avatars.githubusercontent.com/u/268499868?v=4" width="60" style="border-radius:50%" /><br /><sub><b>human530</b></sub></a><br /><sub>46 commits</sub></td>
    <td align="center"><a href="https://github.com/claude"><img src="https://avatars.githubusercontent.com/u/81847?v=4" width="60" style="border-radius:50%" /><br /><sub><b>claude</b></sub></a><br /><sub>27 commits</sub></td>
    <td align="center"><a href="https://github.com/lisa980530"><img src="https://avatars.githubusercontent.com/u/259302424?v=4" width="60" style="border-radius:50%" /><br /><sub><b>lisa980530</b></sub></a><br /><sub>2 commits</sub></td>
  </tr>
</table>
<!-- CONTRIBUTORS:END -->

---

## 📊 專案狀態

<!-- STATUS:START -->
| 指標 | 數值 |
|------|------|
| 總 Commits | 75 |
| 追蹤檔案數 | 740 |
| Python 程式碼行數 | 31169 |
| API 模組數 | 17 |
| 最後更新 | 2026-04-03 |

_自動更新於 2026-04-03 22:00 (UTC+8)_
<!-- STATUS:END -->

---

## 🔒 安全性

如發現安全性議題，請參考 [SECURITY.md](SECURITY.md) 回報流程。

---

## 📜 授權

本專案為研究用途開發。

---

<div align="center">

**[🌐 www.mdpiece.life](https://www.mdpiece.life/)**

Made with ❤️ for better healthcare communication

</div>
