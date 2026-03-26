# 知識庫層（Knowledge Base Layer）

此層負責將衛教文章向量化，提供 RAG（Retrieval-Augmented Generation）能力，
讓 AI 問答能根據實際文獻回答，而非憑空生成。

## 子模組

| 資料夾 | 工具 | 職責 |
|--------|------|------|
| `dify/` | Dify | 低代碼 RAG 平台，管理知識庫與 AI 應用流程 |
| `flowise/` | Flowise | 視覺化 LLM 流程編排，建構 RAG pipeline |

## 資料流

```
research/ 產出文章
    ↓
向量化（Embedding）→ 儲存至向量資料庫
    ↓
interaction/ 查詢時語意檢索 → 取得相關段落
```
