# Subagents 使用範例

在 Claude Code 對話中直接使用，不需額外設定。

## 範例 1：並行研究 + 分析

```text
請同時幫我做以下三件事：
1. 用一個 agent 檢查 backend/routers/ 所有路由的錯誤處理是否完整
2. 用一個 agent 分析 frontend/ 的效能瓶頸
3. 用一個 agent 檢查 Supabase 資料表結構是否與程式碼一致
```

## 範例 2：並行開發

```text
用多個 subagent 並行處理：
1. Agent A：在 backend/routers/symptoms.py 加入症狀嚴重度評分 API
2. Agent B：在 frontend/ 建立對應的症狀評分 UI 元件
3. Agent C：寫測試覆蓋新功能
```

## 範例 3：程式碼審查

```text
用 subagent 並行審查以下模組：
1. 安全性審查：檢查所有 API 端點的認證和授權
2. 效能審查：檢查 N+1 查詢和不必要的資料庫呼叫
3. 程式碼品質：檢查命名規範和重複程式碼
```

## 適用場景

- 快速並行研究/分析（成本低、無額外設定）
- 程式碼審查（多角度同時進行）
- 探索性調查（subagent 讀取大量檔案不污染主對話）
