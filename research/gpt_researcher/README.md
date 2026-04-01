# gpt-researcher 整合模組

## 用途

使用 gpt-researcher 針對醫療主題自動蒐集：
- PubMed / 醫學期刊論文
- 衛生機構指引（CDC、WHO、衛福部）
- 最新臨床研究報告

## 輸出格式

JSON 格式的研究摘要，包含來源 URL 與摘錄段落，
供 Storm 作為原始素材使用。

## 整合事項

- [x] gpt-researcher 安裝與設定（`pip install gpt-researcher`）
- [x] 醫療專用搜尋來源設定（`backend/services/gpt_researcher_service.py`）
- [x] 與 Storm 的資料交接介面（`/gpt-researcher/sources` → STORM input）

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/gpt-researcher/research` | 產出完整研究報告 |
| POST | `/gpt-researcher/sources` | 蒐集來源 URL 與摘錄 |
| GET  | `/gpt-researcher/health` | 檢查服務狀態 |

## 必要環境變數

```bash
OPENAI_API_KEY=your-openai-api-key
TAVILY_API_KEY=your-tavily-api-key
```

## MCP 工具（Claude Code 整合）

- `research_medical_topic(topic, report_type)` — 深度研究並產出報告
- `collect_medical_sources(topic, max_sources)` — 蒐集來源供 STORM 使用

