<div align="center">

# MD.Piece

**AI 驅動的醫療輔助 PWA 平台 — 將日常碎片拼起,醫起走出治療的迷霧**

[![Live Demo](https://img.shields.io/badge/Live_Demo-mdpiece.life-blue?style=for-the-badge)](https://www.mdpiece.life/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-000?style=flat-square&logo=vercel)](https://vercel.com)
[![PWA](https://img.shields.io/badge/PWA-Enabled-5A0FC8?style=flat-square&logo=pwa&logoColor=white)](#)
[![CI](https://github.com/CBL-AICM/MD.Piece/actions/workflows/python-app.yml/badge.svg)](https://github.com/CBL-AICM/MD.Piece/actions/workflows/python-app.yml)

_Piece by Piece, Patient connects Doctor and Patient_

</div>

---

## 目錄

- [專案總結](#專案總結)
- [核心功能](#核心功能)
- [技術架構](#技術架構)
- [專案結構](#專案結構)
- [API 模組總覽](#api-模組總覽)
- [快速開始](#快速開始)
- [環境變數](#環境變數)
- [開發工作流程](#開發工作流程)
- [部署](#部署)
- [測試](#測試)
- [MCP Server](#mcp-server)
- [貢獻](#貢獻)

---

## 專案總結

**MD.Piece** 是一個由 CBL-AICM Lab 開發的漸進式網頁應用 (PWA),
聚焦在 **慢性病長期管理 × 醫病溝通 × AI 情緒陪伴** 三大場景。

平台同時服務病患與醫師兩端:

- **病患端 PWA** (`frontend/`):症狀追蹤、用藥管理、情緒陪伴、衛教資訊、檢驗解讀。
- **醫師端 Portal** (`frontend-doctor/`):病患總覽、月報、看診清單、醫囑筆記。
- **後端 API** (`backend/`):FastAPI 提供 17 個業務模組,與 Supabase Postgres 整合。
- **MCP Server** (`mcp_server/`):14 個 AI Agent 工具,讓 Claude Code 直接操作 MD.Piece 資料。

設計理念:把就診之間零碎的健康訊號 (一天三次體溫、一週兩次情緒分數、藥物副作用、飲食、檢驗值)
逐塊拼回完整圖像,讓醫師看診不再從零開始問診,讓病患在治療過程中不再孤單。

> 線上體驗:[www.mdpiece.life](https://www.mdpiece.life/)

---

## 核心功能

### 病歷與身份

- **雙角色帳號**:病患 / 醫師,醫師註冊與登入需要通行碼 (`DOCTOR_VERIFICATION_KEY`)
- **scrypt 密碼雜湊**:n=16384、salt 16-byte
- **病患 / 醫師 CRUD**:基本資料、ICD-10 慢性病標籤
- **病歷紀錄**:就診日期、症狀、診斷、處方、筆記;支援多條件篩選

### AI 症狀分析

- 10 種常見症狀的快速建議 (`/symptoms/advice`)
- LLM 多症狀綜合分析 (`/symptoms/analyze`):
  - 緊急程度 (急診 / 高 / 中 / 低)
  - 可能診斷 + 機率評分
  - 推薦就診科別
- 症狀分析歷史與歷次比對

### 智慧分診 (Triage)

- **雙層判斷**:規則引擎先過急症關鍵字 → LLM 做個人化判斷
- **個人化基準值**:取近 2 週平均症狀 / 用藥 / 情緒分數,作為 LLM 對照組
- 免疫低下患者特別標記 (`is_immunosuppressed`)

### 用藥管理

- 用藥 CRUD + **服藥提醒排程** (`backend/utils/medication_schedule.py`)
- **藥單拍照辨識**:前端 Tesseract.js OCR → 後端 Claude Haiku 抽欄位
- **多通道辨識 fallback**:Google Vision API → LLM Vision → 純 OCR
- 服藥紀錄、副作用紀錄、check-in、每日改善統計、月度用藥報告
- 用藥變更追蹤 (start/stop/dose_up/dose_down/switch/frequency)

### 小禾 — AI 情緒支持夥伴

- 由 Claude Haiku 驅動的對話陪伴 (支援 SSE streaming)
- **多種人格切換**:`patient_normal` / `patient_elderly` / `family`
- 病患版口吻像 IG 私訊好朋友;長輩版用全形標點、緩慢語速
- **隱私保護的情緒摘要**:醫師僅看得到趨勢,看不到對話內容
- 靜默守護者:持續低落情緒會主動觸發 alert

### 情緒追蹤 (Emotions)

- 0–10 分自評 + 文字日記
- 與症狀、用藥、睡眠的相關係數分析 (Pearson)

### 飲食模組 (Diet)

- AI 個人化飲食指南 (依病史 ICD-10 + 用藥 + 近期飲食生成)
- 三餐 + 點心紀錄
- 近 N 週滾動 7 天彙整 (純統計、無 LLM)

### 檢驗報告解讀 (Labs)

- 使用者輸入任意檢驗項目 + 數值
- LLM 回傳:常見參考範圍、判讀 (偏低/正常/偏高/嚴重異常)、白話解釋、生活建議、是否建議就醫
- 嚴重異常 (鉀過高、血糖極低、肝指數爆高) 強制 `see_doctor=true`

### 衛教資訊 (Education)

- 品質把關的靜態文章 (非 LLM 生成,避免幻覺)
- 依 ICD-10 診斷碼 連動個人化推薦
- 情境式提醒 (例:糖尿病患在飲食頁看到血糖控制提醒)

### 醫師工具

- **看診清單** (`/reports/{patient_id}/checklist`):本次回診重點問項
- **病患月報** (`/reports/{patient_id}/monthly`):症狀曲線、用藥順從度、情緒趨勢
- **健康關聯分析** (`/reports/{patient_id}/wellness-correlation`):跨指標 Pearson 相關
- **醫師筆記** (`/doctor-notes`):臨床觀察、下次回診聚焦點、標籤

### 警示系統 (Alerts)

- 7 種類型:急診就診、漏服藥、自行停藥、感染、低落情緒、精神危機、其他
- 4 級嚴重度:low / medium / high / critical
- 醫師 acknowledge / resolve 工作流

### AutoResearch 實驗追蹤

- 整合 [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- ML 模型訓練實驗管理 (Colab T4 / Kaggle / 本地 GPU)
- 驗證指標 `val_bpb` 排行榜
- TSV 批次匯入 / 匯出
- 實驗統計儀表板 (改善率、總訓練時數、最佳成績)

---

## 技術架構

| 層級 | 技術 |
|------|------|
| **前端 (病患)** | Vanilla JS PWA, Service Worker, Tesseract.js OCR, lucide icons |
| **前端 (醫師)** | `frontend-doctor/` 獨立 build (`@vercel/static-build`) |
| **後端** | FastAPI (Python 3.10+), Pydantic v2 |
| **資料庫** | Supabase (PostgreSQL),DB 離線時自動 503 |
| **LLM Provider** | 自建 fallback chain:Ollama (本地) → Anthropic Claude → Groq |
| **AI 模型** | Claude Haiku 4.5 (預設)、Llama 3.3 70B (Groq)、Qwen 2.5 7B + LLaVA (Ollama) |
| **OCR** | 前端 Tesseract.js + Google Cloud Vision API + LLM Vision fallback |
| **MCP Server** | FastMCP, STDIO transport |
| **i18n** | 自製 i18n.js,zh-TW / EN 雙語 |
| **部署** | Vercel (`@vercel/python` serverless + 靜態 CDN) |
| **CI/CD** | GitHub Actions:flake8 + pytest + CodeQL |

### LLM Fallback 機制

預設順序:`anthropic → groq → ollama`。
任何一個 provider 失敗,自動嘗試下一個,只要鏈中有一個能用就 OK。
本地開發推薦 `LLM_PROVIDER=ollama` (零成本、資料不出本機),雲端部署推薦 `anthropic`。

---

## 專案結構

```
md.piece/
├── api/
│   └── index.py                 # Vercel serverless 入口 (re-export FastAPI app)
├── backend/
│   ├── main.py                  # FastAPI app + router 註冊 + DB offline handler
│   ├── models.py                # Pydantic schema (Patient/Doctor/Record/Alert/...)
│   ├── db.py                    # Supabase client + connection retry
│   ├── routers/                 # 17 個 API 模組
│   │   ├── auth.py              # 註冊 / 登入 / 改密 (scrypt)
│   │   ├── patients.py
│   │   ├── doctors.py
│   │   ├── records.py           # 病歷
│   │   ├── symptoms.py          # 症狀記錄 + AI 分析
│   │   ├── triage.py            # 雙層分診
│   │   ├── medications.py       # 藥物 CRUD + OCR + 服藥紀錄
│   │   ├── medication_changes.py
│   │   ├── emotions.py
│   │   ├── xiaohe.py            # 小禾對話 (含 SSE streaming)
│   │   ├── education.py
│   │   ├── diet.py              # 飲食指南 + 紀錄
│   │   ├── labs.py              # 檢驗解讀
│   │   ├── alerts.py            # 警示
│   │   ├── doctor_notes.py
│   │   ├── reports.py           # 月報 / 看診清單 / 相關分析
│   │   ├── research.py          # AutoResearch
│   │   └── debug.py
│   ├── services/
│   │   ├── llm_service.py       # LLM 多 provider + fallback chain
│   │   ├── claude_service.py    # 純 Anthropic 封裝
│   │   ├── ai_analyzer.py       # 症狀分析 prompt
│   │   ├── education_content.py # 衛教文章池
│   │   ├── knowledge_analysis.py
│   │   ├── news_feed.py
│   │   └── supabase_service.py
│   └── utils/
│       ├── triage_rules.py      # 急症規則引擎
│       ├── baseline.py          # 個人基準值計算
│       ├── icd10.py             # ICD-10 對照表
│       └── medication_schedule.py
├── frontend/                    # 病患端 PWA
│   ├── index.html               # SPA 主頁 (含 landing / auth / app)
│   ├── manifest.json            # PWA manifest
│   ├── sw.js                    # Service Worker (離線快取)
│   ├── js/
│   │   ├── app.js               # 主邏輯 (~9k 行)
│   │   ├── i18n.js              # 雙語切換
│   │   └── landing.js           # 啟動畫面動畫
│   └── css/style.css            # ~11k 行 (含暗色 / 亮色 theme)
├── frontend-doctor/             # 醫師端 Portal (獨立 build)
├── mcp_server/
│   ├── server.py                # 14 個 AI Agent 工具
│   ├── pyproject.toml           # uv 管理
│   └── uv.lock
├── tests/
│   ├── unit/                    # pytest unit tests
│   ├── integration/             # router 整合測試
│   └── e2e/                     # Tesseract.js → API 完整 pipeline 測試
├── docs/
│   ├── API.md
│   ├── SETUP.md
│   └── migration_*.sql          # Supabase schema
├── config/                      # database/env/deploy 設定
├── scripts/                     # 部署 / 維護腳本
├── .env.example
├── vercel.json                  # 部署 routes + headers
├── requirements.txt
├── pytest.ini
├── CLAUDE.md                    # Claude Code 專案指引
└── program.md                   # AutoResearch 迴圈說明
```

---

## API 模組總覽

| Prefix | 主要端點 | 功能 |
|--------|----------|------|
| `/auth` | `/register`, `/login`, `/change-password` | scrypt 帳號驗證 |
| `/patients` | `GET /`, `POST /`, `PUT /{id}`, `DELETE /{id}` | 病患 CRUD |
| `/doctors` | `GET /`, `POST /` | 醫師 CRUD |
| `/records` | `POST /`, `GET /patient/{id}` | 病歷紀錄 |
| `/symptoms` | `POST /analyze`, `GET /advice`, `GET /history/{id}` | 症狀記錄 + AI 分析 |
| `/triage` | `POST /evaluate`, `GET /baseline/{id}`, `GET /emergency-symptoms` | 雙層分診 |
| `/medications` | `POST /recognize`, `POST /log`, `GET /can-take`, `GET /report` | 藥物管理 + OCR |
| `/medication-changes` | `POST /` | 處方變更紀錄 |
| `/emotions` | `POST /`, `GET /{id}` | 情緒追蹤 |
| `/xiaohe` | `POST /chat`, `POST /chat/stream`, `GET /emotion-summary/{id}` | AI 陪伴 |
| `/education` | `GET /list`, `GET /article/{id}` | 衛教資訊 |
| `/diet` | `GET /guide/{id}`, `POST /records`, `GET /weekly/{id}` | 飲食模組 |
| `/labs` | `POST /interpret` | 檢驗解讀 |
| `/alerts` | `GET /`, `POST /`, `PATCH /{id}` | 警示 |
| `/doctor-notes` | `POST /`, `GET /patient/{id}` | 醫師筆記 |
| `/reports` | `/monthly`, `/checklist`, `/patient-summary`, `/wellness-correlation` | 醫師報表 |
| `/research` | `POST /`, `GET /stats`, `GET /leaderboard`, `POST /batch` | AutoResearch |
| `/health/llm` | LLM provider 連線狀態 |  |

完整 API 文件於開發環境啟動後可瀏覽 `http://localhost:8000/docs` (FastAPI 自動產生)。

---

## 快速開始

### 環境需求

- Python 3.10+
- (選用) Anthropic API Key — 沒有則 fallback 到 Groq / Ollama
- (選用) Supabase 專案 — 沒有則使用 SQLite (`md_piece.db`)
- (選用) [uv](https://docs.astral.sh/uv/) — 給 MCP server 用

### 一鍵啟動

```bash
# 1. Clone
git clone https://github.com/CBL-AICM/MD.Piece.git
cd MD.Piece

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env,至少填 SUPABASE_URL / SUPABASE_KEY,以及任一 LLM provider

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 啟動後端 (port 8000)
uvicorn backend.main:app --reload --port 8000

# 5. 啟動前端 (port 3000)
python -m http.server 3000 --directory frontend
```

開啟瀏覽器訪問 `http://localhost:3000` (病患端) 或 `http://localhost:8000/docs` (API 文件)。

### 醫師端 Portal

```bash
cd frontend-doctor
npm install
npm run dev
```

醫師端會在 `http://localhost:5173` 之類的 Vite 預設 port 啟動,
經 `vercel.json` 路由規則對應到 `/doctor` 路徑。

---

## 環境變數

完整範本在 [`.env.example`](.env.example),關鍵變數:

| 變數 | 說明 | 必要性 |
|------|------|--------|
| `SUPABASE_URL` | Supabase 專案 URL | 線上必要 |
| `SUPABASE_KEY` | Supabase anon / service-role key | 線上必要 |
| `LLM_PROVIDER` | `ollama` / `groq` / `anthropic` | 預設 ollama |
| `ANTHROPIC_API_KEY` | Claude API Key | 用 anthropic 時必要 |
| `ANTHROPIC_MODEL` | 預設 `claude-haiku-4-5-20251001` | 選填 |
| `GROQ_API_KEY` | Groq API Key | 用 groq 時必要 |
| `OLLAMA_BASE_URL` | 預設 `http://localhost:11434` | 用 ollama 時必要 |
| `GOOGLE_VISION_API_KEY` | OCR 增強 (1000 次/月免費) | 選填 |
| `DOCTOR_VERIFICATION_KEY` | 醫師註冊通行碼 | 預設 `310530` |
| `APP_ENV` | `development` / `production` | 選填 |

> 注意:Supabase 憑證**不要**寫死在程式碼裡,只能用環境變數。

---

## 開發工作流程

### 分支策略

- 主分支:`main` (Vercel 自動部署到 production)
- 功能分支:`claude/<feature-name>` (例如 `claude/add-diet-module-v2`)
- 一個 feature 一個 PR,絕不直接 push `main`

### Import 慣例

後端統一使用絕對 import:

```python
# Good
from backend.routers import patients
from backend.services.llm_service import call_claude

# Bad (relative import)
from .routers import patients
```

### 新增 API 路由

1. 在 `backend/routers/` 新增模組
2. 在 `backend/main.py` 用 `app.include_router()` 註冊
3. 若 Vercel 部署,要在 `vercel.json` 的 `routes` 區塊加對應 prefix
4. (選用) 在 `mcp_server/server.py` 加對應 MCP tool

---

## 部署

Production domain:`www.mdpiece.life` (Vercel 綁定 `main` 分支)

`vercel.json` 設定:
- 後端 `api/index.py` 用 `@vercel/python` (max 50MB / 60s)
- 病患 PWA 直接走 `@vercel/static`
- 醫師 Portal 走 `@vercel/static-build` (Vite build)
- `sw.js` / `index.html` 強制 no-cache,避免舊 PWA 卡死

### 全自動部署流程 (CLAUDE.md 規範)

當 Claude Code 完成一個 feature 後:

1. commit + push + 開 draft PR
2. **自動跑 e2e**:`cd tests/e2e && npm run test:rx`
3. 若失敗,自動分析 → 修 → 重跑,**直到全綠**
4. 全綠後:draft → ready → squash merge → Vercel 自動部署

---

## 測試

```bash
# Unit + Integration
pytest

# E2E (藥單 OCR pipeline)
cd tests/e2e
npm install
python3 fixtures/generate_rx_images.py    # 產合成藥單 (需要 Pillow + 中文字型)
node run_rx_recognition.mjs               # 對 production 跑
API_BASE=http://localhost:8000 node run_rx_recognition.mjs  # 對本機跑
```

E2E 驗證 `Tesseract.js OCR → POST /medications/recognize → Haiku 抽欄位` 全鏈路,
6 張合成藥單 + 13 種藥,目標每張回 200 且抽出 ≥ 1 筆 medication。

---

## MCP Server

讓 Claude Code (或任何支援 MCP 的 AI Agent) 直接操作 MD.Piece:

```bash
cd mcp_server
uv sync
uv run server.py        # STDIO 模式
```

### 提供的 14 個工具

| 工具 | 說明 |
|------|------|
| `get_patients` / `create_patient` / `delete_patient` | 病患管理 |
| `get_doctors` / `create_doctor` | 醫師管理 |
| `create_medical_record` / `get_medical_records` / `get_patient_history` | 病歷 |
| `get_symptom_advice` / `analyze_symptoms` / `get_symptom_history` | 症狀 |
| `get_experiments` / `get_experiment_stats` / `get_experiment_leaderboard` / `submit_experiment_result` | AutoResearch |

### Claude Code 設定範例

於 `.claude/mcp.json` (或對應設定檔) 加入:

```json
{
  "mcpServers": {
    "md-piece": {
      "command": "uv",
      "args": ["--directory", "/path/to/MD.Piece/mcp_server", "run", "server.py"]
    }
  }
}
```

啟動前先確保 backend 已在 `localhost:8000` 跑起來。

---

## 貢獻

1. Fork 此 repo
2. 建立功能分支:`git checkout -b claude/your-feature`
3. 提交變更:遵循 commit message 慣例 (feat / fix / docs / refactor)
4. 開 PR 並請 reviewer 看 CI

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

## 專案狀態

<!-- STATUS:START -->
| 指標 | 數值 |
|------|------|
| 總 Commits | 75 |
| 追蹤檔案數 | 740 |
| Python 程式碼行數 | 31169 |
| API 模組數 | 17 |
| 最後更新 | 2026-05-08 |

_自動更新於 2026-05-08 (UTC+8)_
<!-- STATUS:END -->

---

## 授權

本專案為 CBL-AICM Lab 研究用途開發。

---

<div align="center">

**[www.mdpiece.life](https://www.mdpiece.life/)**

Made with care for better healthcare communication
— CBL-AICM Lab —

</div>
