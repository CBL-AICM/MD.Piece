# MD.Piece — Claude Code Project Guide

## 專案概述

MD.Piece 是一個 PWA 醫療輔助平台，支援醫病溝通與症狀分析。

- **後端**：FastAPI（Python），port 8000
- **前端**：Vanilla JS PWA，port 3000（`python -m http.server`）
- **資料庫**：Supabase（PostgreSQL）
- **AI 服務**：Claude / Ollama / Groq 多 provider（透過 `backend/services/llm_service.py`）
- **MCP Server**：`mcp_server/server.py`，連接 backend API

---

## 專案結構

```
md.piece/
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── routers/                 # API 路由
│   │   ├── patients.py          # 病患管理
│   │   ├── doctors.py           # 醫生管理
│   │   ├── symptoms.py          # 症狀記錄
│   │   ├── medications.py       # 藥物管理
│   │   ├── emotions.py          # 情緒追蹤
│   │   ├── triage.py            # 分診建議
│   │   ├── reports.py           # 報告生成
│   │   ├── education.py         # 衛教資訊
│   │   └── xiaohe.py            # 小核功能
│   ├── services/
│   │   └── llm_service.py       # 多 provider LLM 整合（Claude/Ollama/Groq）
│   └── utils/
│       ├── triage_rules.py      # 分診規則
│       ├── baseline.py          # 基準值
│       └── icd10.py             # ICD-10 編碼
├── frontend/                    # PWA 前端（HTML/CSS/JS）
├── mcp_server/
│   └── server.py                # MCP server（連接 backend）
├── docs/                        # 專案文件
├── config/                      # 設定檔
└── tests/                       # 測試

```

---

## 開發指令

```bash
# 啟動後端
uvicorn backend.main:app --reload --port 8000

# 啟動前端
python -m http.server 3000 --directory frontend

# 安裝後端依賴
pip install -r backend/requirements.txt

# 安裝 MCP server 依賴
cd mcp_server && uv sync
```

---

## 重要規則

- 後端使用 `backend.xxx` 絕對 import，不用相對 import
- Supabase 憑證存在環境變數（不寫死在程式碼）
- API 路由需在 `backend/main.py` 的 `include_router` 註冊才生效
- MCP server 透過 STDIO 與 Claude Code 溝通，base URL 為 `http://localhost:8000`

---

## 產品設計憲法（必讀）

開發任何功能前，必須先讀 [`docs/product-principles.md`](docs/product-principles.md)，
並在 PR 描述中對照「7 條設計憲法」與「3 個策略場景（A/B/C）」自我檢核。

7 條設計憲法摘要：
1. PWA 原生體驗
2. 可信任、可解釋的 AI（必附「為什麼」）
3. 可客製化的提醒（時段、頻率、語氣）
4. 跨院整合視圖（患者自上傳 + OCR）
5. 醫病共決（Decision Aid）等級的輸出
6. 長者／家屬模式（大字、語音、代理）
7. 本地化與文化敏感（繁中、台灣分級醫療、長照）

3 個策略場景：
- **A**：症狀分析 → Decision Aid 等級分診（`routers/symptoms.py` + `routers/triage.py` + `xiaohe.py`）
- **B**：客製化提醒 + 家屬視角（`routers/medications.py` + `routers/emotions.py`）
- **C**：「我的健康時間軸」跨次就診整合（新 `routers/timeline.py`）

---

## Git 工作流程

- 主分支：`main`
- 功能分支命名：`claude/feature-name`
- 每個功能開獨立 PR，不直接 push main

---

## 部署規則

- Production domain：`www.mdpiece.life/`（由 Vercel 綁定 `main` 分支）
- **全自動部署流程**：使用者回報 bug 或要求功能後，Claude 完成 commit + push + 建立 PR 後，**不需要等使用者再說「部署」**，直接依下列自動化流程跑到底：
  1. **自動跑 e2e 實驗室測試**：執行 `cd tests/e2e && npm run test:rx`（以及其他 e2e 套件）
  2. **自動修復 bug**：若測試失敗，分析失敗原因、修改程式碼、重新跑測試，**循環直到所有 e2e 測試通過為止**
  3. **自動合併部署**：所有 e2e 測試通過後，把 draft PR 標 ready、squash 合併到 `main`，由 Vercel 自動發布到 production domain
- 過程中若遇到無法自動修復的問題（例如需要環境變數、外部服務權限、架構性決策），暫停並回報使用者，不要強行合併
