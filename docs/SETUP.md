# 安裝與設定說明

## 環境需求

- Python 3.10+
- [Supabase](https://supabase.com) 帳號（資料庫）
- Anthropic API Key（AI 症狀分析，選填）

---

## 快速開始

### 1. 複製專案

```bash
git clone https://github.com/human530/MD.Piece.git
cd MD.Piece
```

### 2. 環境變數

```bash
cp .env.example .env
```

編輯 `.env`，填入以下必要設定：

| 變數 | 說明 | 必填 |
|------|------|------|
| `SUPABASE_URL` | Supabase 專案 URL | ✅ |
| `SUPABASE_KEY` | Supabase anon/service key | ✅ |
| `ANTHROPIC_API_KEY` | Claude API Key（AI 分析） | 選填 |
| `APP_ENV` | `development` / `production` | 選填 |
| `APP_PORT` | 後端 port（預設 8000） | 選填 |

### 3. 資料庫建立（Supabase）

前往 **Supabase Dashboard → SQL Editor**，依序執行：

```
migrations/001_create_departments.sql
```

> 此 migration 會建立 `departments` 資料表、為 `doctors` 加入 `department_id` 欄位，並設定 RLS policy。

執行後可呼叫 API 初始化預設科別：

```bash
curl -X POST http://localhost:8000/departments/seed
```

或在前端「科別管理」頁點擊「初始化預設科別」按鈕。

### 4. 後端

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 5. 前端

```bash
python -m http.server 3000 --directory frontend
```

開啟瀏覽器：`http://localhost:3000`

---

## Supabase 資料表結構

| 資料表 | 說明 |
|--------|------|
| `departments` | 科別（內科、外科、小兒科…） |
| `doctors` | 醫師（含 `department_id` 外鍵） |
| `patients` | 病患資料 |
| `medical_records` | 就診病歷 |
| `symptoms_log` | AI 症狀分析記錄 |

> 除 `departments` 外，其餘資料表需在 Supabase 手動建立或透過 Supabase Studio。

---

## MCP Server（Claude Code 整合）

```bash
cd mcp_server
uv sync
uv run server.py
```

---

## 開發指令摘要

```bash
# 啟動後端（開發模式）
uvicorn backend.main:app --reload --port 8000

# 啟動前端
python -m http.server 3000 --directory frontend

# 執行測試
pytest tests/

# 初始化科別資料
curl -X POST http://localhost:8000/departments/seed
```
