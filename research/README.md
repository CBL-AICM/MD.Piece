# 自動研究層（Auto Research Layer）

此層負責自動調研與生產有引用來源的醫療衛教知識。

## 子模組

| 資料夾 | 工具 | 職責 |
|--------|------|------|
| `storm/` | Stanford STORM / Co-STORM | 自動產生結構化長篇衛教文章，支援醫師審核介入 |
| `gpt_researcher/` | gpt-researcher | 蒐集醫學文獻、研究報告、最新指引 |

## 輸出流向

產出的衛教文章 → 存入 Supabase → 供 `knowledge_base/` 向量化使用
