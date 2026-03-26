# 使用者互動層（Interaction Layer）

此層負責症狀問答、衛教引導與就診建議，是病患與 AI 直接對話的核心層。

## 子模組

| 資料夾 | 工具 | 職責 |
|--------|------|------|
| `rasa/` | Rasa | 開源對話 AI 框架，處理症狀收集對話流程 |
| `botpress/` | Botpress | 視覺化 Chatbot 建構平台，適合非工程師設計對話 |

## 資料流

```
病患輸入症狀
    ↓
Chatbot 引導問診（Rasa / Botpress）
    ↓
查詢 knowledge_base/ RAG → 取得衛教回應
    ↓
回傳給 interface/ 顯示
```

## 與現有 backend 的關係

- 症狀記錄 → `backend/routers/symptoms.py`
- 分診建議 → `backend/routers/triage.py`
- 衛教問答 → `backend/routers/education.py`
