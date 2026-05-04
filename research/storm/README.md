# Storm / Co-Storm 整合模組

## 用途

使用 Stanford STORM 框架，針對指定醫療主題自動：
1. 多輪搜尋調研
2. 組織文章大綱
3. 產出含引用的長篇衛教文章

Co-Storm 變體支援人類專家（醫師）介入共同策展。

## 相關後端路由

- `backend/routers/education.py` — 衛教文章 CRUD API

## 待整合事項

- [ ] Storm CLI / Python SDK 安裝設定
- [ ] 與 `backend/services/` 的整合介面
- [ ] Co-Storm 醫師審核 webhook
