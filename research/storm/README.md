# Storm / Co-Storm 整合模組

## 用途

使用 Stanford STORM 框架（`knowledge-storm`），針對指定醫療主題自動：
1. 多輪搜尋調研（多專家觀點模擬）
2. 組織文章大綱
3. 產出含引用的長篇衛教文章

Co-STORM 變體支援人類專家（醫師）介入共同策展。

## 安裝

```bash
pip install knowledge-storm litellm
```

已加入 `backend/requirements.txt`。

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Claude API 金鑰（必要） | — |
| `STORM_LLM_MODEL` | LLM 模型 | `anthropic/claude-haiku-4-5-20251001` |
| `STORM_SEARCH_ENGINE` | 搜尋引擎：`duckduckgo`/`you`/`tavily`/`bing`/`serper` | `duckduckgo` |
| `STORM_OUTPUT_DIR` | 文章輸出目錄 | 系統暫存目錄 |
| `YDC_API_KEY` | You.com Search API key（選填） | — |
| `TAVILY_API_KEY` | Tavily Search API key（選填） | — |
| `BING_SEARCH_API_KEY` | Bing Search API key（選填） | — |
| `SERPER_API_KEY` | Serper API key（選填） | — |

## API 端點

### STORM 全自動研究

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/storm/research` | 啟動非同步研究任務 |
| GET | `/storm/research` | 列出所有任務 |
| GET | `/storm/research/{task_id}` | 查詢任務狀態與結果 |

### Co-STORM 協作式研究

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/storm/costorm/sessions` | 建立協作會話 |
| POST | `/storm/costorm/sessions/{id}/step` | 推進一輪對話 |
| POST | `/storm/costorm/sessions/{id}/report` | 生成最終報告 |
| DELETE | `/storm/costorm/sessions/{id}` | 關閉會話 |

## 使用範例

```bash
# 啟動 STORM 研究
curl -X POST http://localhost:8000/storm/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "第二型糖尿病的飲食管理"}'

# 查詢結果
curl http://localhost:8000/storm/research/{task_id}
```

## 相關後端檔案

- `backend/services/storm_service.py` — STORM/Co-STORM 服務封裝
- `backend/routers/storm.py` — API 路由
- `backend/routers/education.py` — 衛教文章 CRUD API

## 架構

```
使用者/醫師 → POST /storm/research → BackgroundTask
                                        ↓
                                   STORM Pipeline
                                   (搜尋 → 多專家對話 → 大綱 → 文章 → 潤稿)
                                        ↓
                                   GET /storm/research/{id} → 取得文章
```
