# MD.Piece — Claude Code Project Guide

## 專案概述

MD.Piece 是一個 PWA 醫療輔助平台，支援醫病溝通與症狀分析。

- **後端**：FastAPI（Python），port 8000
- **前端**：Vanilla JS PWA，port 3000（`python -m http.server`）
- **資料庫**：Supabase（PostgreSQL）
- **AI 服務**：Claude / Ollama / Groq 多 provider（透過 `backend/services/llm_service.py`）
- **MCP Server**：`mcp_server/server.py`，連接 backend API

---

## AI 協作 12 條鐵則（必讀，優先級最高）

開始寫任何程式碼前先過一遍這 12 條。與本文件其他任何規則衝突時，這裡優先。

### 規則 1 — 寫程式前先思考

實作前務必釐清所有假設與模糊地帶，絕不盲目猜測或替使用者做決定；若有更簡單的解法應主動提出，遇到任何不清楚的地方必須立刻停下來發問。

### 規則 2 — 簡單至上

只用最少的程式碼解決當下問題，嚴格拒絕任何過度工程化、推測未來需求的功能或不必要的抽象層，確保產出符合資深工程師眼中的「精簡」標準。

### 規則 3 — 手術式修改

只精準更動與需求直接相關的範圍，絕對不去「順手改善」或重構旁邊未損壞的程式碼及排版，並且只負責清理因本次修改才變成無用的變數或引入。

### 規則 4 — 目標導向執行

將任務轉化為「可被驗證的具體目標」（例如：寫出測試並讓它通過），為多步驟任務建立帶有檢查點的計畫，讓 AI 能基於明確的成功標準自主迭代到完成。

### 規則 5 — 只讓 AI 做需要判斷力的事

將 AI 用於分類、摘要、草擬等主觀判斷工作，嚴禁讓 AI 去處理狀態碼判斷、API 重試或路由分配。

只要能用傳統程式碼以 if-else 邏輯寫死的確定性任務，就應交由純程式碼執行，避免模型產生隨機且不可靠的決策。

> **Rule 5 — Use the model only for judgment calls**
> Use Claude for: classification, drafting, summarization, extraction from unstructured text.
> Do NOT use Claude for: routing, retries, status-code handling, deterministic transforms.
> If a status code already answers the question, plain code answers the question.

### 規則 6 — 強制設定詞元預算上限

明確規範單一任務（如 4,000 tokens）與單次對話（如 30,000 tokens）的消耗上限。當運算資源即將耗盡時，模型必須主動總結當前進度並要求重新啟動對話。

此舉可防止模型在無法解決的錯誤中陷入無限迴圈，造成不必要的資源與成本浪費。

> **Rule 6 — Token budgets are not advisory**
> Per-task budget: 4,000 tokens.
> Per-session budget: 30,000 tokens.
> If a task is approaching budget, summarize and start fresh. Do not push through.
> Surfacing the breach > silently overrunning.

### 規則 7 — 衝突要攤開講，禁止混合寫法

當程式庫中存在兩種相互矛盾的寫法時，AI 傾向「兩種都照顧到」，寫出一個試圖同時滿足兩種規範的程式碼。這比任何一種原始寫法都更難維護。

規則 7 要求 AI 選擇其中一種（優先選較新或測試較完整的），說明理由，並標記另一種待日後清理。

> **Rule 7 — Surface conflicts, don't average them**
> If two existing patterns in the codebase contradict, don't blend them.
> Pick one (the more recent / more tested), explain why, and flag the other for cleanup.
> "Average" code that satisfies both rules is the worst code.

### 規則 8 — 寫程式前先讀懂周邊程式碼

在新增或修改任何程式碼之前，模型必須先讀取該檔案的輸出 (exports)、直接呼叫者函數以及相關的共用工具程式碼。

不允許模型在未完全理解現有程式碼結構的情況下，以兩者互不相關為由直接寫入新功能。

> **Rule 8 — Read before you write**
> Before adding code in a file, read the file's exports, the immediate caller, and any obvious shared utilities.
> If you don't understand why existing code is structured the way it is, ask before adding to it.
> "Looks orthogonal to me" is the most dangerous phrase in this codebase.

### 規則 9 — 測試要驗證為什麼，不只是有沒有

模型編寫的測試程式碼必須能真實反映商業邏輯的運作。如果一項業務邏輯發生改變，相關的測試卻依然能夠通過（例如模型為了讓測試亮綠燈而將回傳值寫死），即代表該測試無效。

測試的目的是驗證行為為何重要，而非僅驗證程式有在執行。

> **Rule 9 — Tests verify intent, not just behavior**
> Every test must encode WHY the behavior matters, not just WHAT it does.
> A test like `expect(getUserName()).toBe('John')` is worthless if the function takes a hardcoded ID.
> If you can't write a test that would fail when business logic changes, the function is wrong.

### 規則 10 — 多步驟任務每完成一步就要回報

長時間的重構或功能開發橫跨多個步驟，一旦中途出錯，後續步驟可能全部建立在錯誤的基礎上。

規則 10 要求 AI 在完成每個重要步驟後，主動回報「已完成事項、已驗證事項、剩餘事項」，若模型在執行過程中遺失上下文，無法精確描述當前狀態，就必須立即中止任務並重新釐清，防止錯誤進度持續疊加。

> **Rule 10 — Checkpoint after every significant step**
> After completing each step in a multi-step task: summarize what was done, what's verified, what's left.
> Don't continue from a state you can't describe back to me.
> If you lose track, stop and restate.

### 規則 11 — 遵從現有慣例，不要偷偷引入新風格

每個程式庫都有自己的命名規則、元件寫法與錯誤處理模式。AI 即便認為自己的寫法更好，也不應在沒有告知的情況下引入新風格，因為「兩種風格並存」比任何一種風格單獨使用都更難維護。

無論模型是否認為某種新框架或寫法更優良，只要專案既定採用特定的命名規則或舊有架構，模型就必須完全配合，禁止在未經討論的情況下擅自引入新風格。

> **Rule 11 — Match the codebase's conventions, even if you disagree**
> If the codebase uses snake_case and you'd prefer camelCase: snake_case.
> If the codebase uses class-based components and you'd prefer hooks: class-based.
> Disagreement is a separate conversation. Inside the codebase, conformance > taste.
> If you genuinely think the convention is harmful, surface it. Don't fork it silently.

### 規則 12 — 主動揭露錯誤，禁止隱性失敗

這是最受關注的一條。規則要求 AI 在任何步驟有疑問、有遺漏，或無法完整驗證結果時，必須明確回報異常，絕對不允許回報「執行完成」或「測試通過」。

必須將所有不確定性或未執行的步驟完整呈現給開發者，確保沒有任何錯誤被默默忽略。

> **Rule 12 — Fail loud**
> If you can't be sure something worked, say so explicitly.
> "Migration completed" is wrong if 30 records were skipped silently.
> "Tests pass" is wrong if you skipped any.
> "Feature works" is wrong if you didn't verify the edge case I asked about.
> Default to surfacing uncertainty, not hiding it.

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
