# MD.Piece — Claude Code Project Guide

## 專案概述

MD.Piece 是一個 PWA 醫療輔助平台，支援醫病溝通與症狀分析。

- **後端**：FastAPI（Python），port 8000
- **前端**：Vanilla JS PWA，port 3000（`python -m http.server`）
- **資料庫**：Supabase（PostgreSQL）
- **AI 服務**：Claude API（透過 `backend/services/claude_service.py`）
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
│   │   ├── claude_service.py    # Claude AI 整合
│   │   └── supabase_service.py  # Supabase 整合
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

## Git 工作流程

- 主分支：`main`
- 功能分支命名：`claude/feature-name`
- 每個功能開獨立 PR，不直接 push main

---

## 多工並行開發

本專案支援四種 Claude Code 多工方式，腳本位於 `scripts/multi-task/`。

### 1. Subagents（子 Agent）
在對話中直接請 Claude 用多個 subagent 並行處理任務，無需額外設定。
適合：快速並行研究、程式碼審查、探索性調查。
參考：`scripts/multi-task/subagents-example.md`

### 2. Git Worktrees
用獨立的工作目錄同時開發多個功能，不互相干擾。
```bash
# 建立 worktree
./scripts/multi-task/worktree-manager.sh create auth-feature
# 列出所有 worktrees
./scripts/multi-task/worktree-manager.sh list
# 在 worktree 中啟動 Claude Code
./scripts/multi-task/worktree-manager.sh launch auth-feature
```

### 3. Agent Teams（實驗功能）
已在 `.claude/settings.json` 啟用 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`。
多個 Agent 組成團隊協作，適合複雜多模組任務。

### 4. 非互動模式批次處理
用 `claude -p` 並行跑多個任務，結果輸出到 `output/batch-results/`。
```bash
# 並行分析所有後端模組
./scripts/multi-task/batch-runner.sh analyze
# 並行程式碼審查（安全/效能/前端）
./scripts/multi-task/batch-runner.sh review
# 並行生成測試
./scripts/multi-task/batch-runner.sh test-gen
# 自訂任務
./scripts/multi-task/batch-runner.sh custom scripts/multi-task/sample-tasks.txt
```
