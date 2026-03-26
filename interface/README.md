# 介面層（Interface Layer）

此層是病患與醫師實際操作的前端介面，提供對話 UI 與視訊看診功能。

## 子模組

| 資料夾 | 工具 | 職責 |
|--------|------|------|
| `chat_ui/` | chat-ui-kit-react | 病患端對話介面元件 |
| `jitsi/` | Jitsi Meet | 視訊看診整合 |

## 與現有 frontend/ 的關係

此層的元件最終整合進 `frontend/` 的 PWA，
作為獨立模組開發後再引入主前端。
