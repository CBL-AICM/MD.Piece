## 變更摘要

<!-- 一兩句話描述「為什麼」做這個改動 -->

## 部署前檢查

- [ ] 若新增 / 修改了 router 或 model：對應的 Supabase migration 是否已 apply？
  （如 `docs/migration_*.sql` 中的 DDL，須在 Supabase Dashboard → SQL Editor 執行，或透過 MCP `apply_migration` 套用；否則 prod 會 500）
- [ ] 若新增 router：是否已在 `api/index.py` 與 `backend/main.py` 兩處都 `include_router`？
- [ ] 若改了前端：是否已 bump `frontend/index.html` 的 `app.js?v=` 版本號（避免 PWA cache）？

## 產品憲法自檢（依 `docs/product-principles.md`）

- 對應策略場景：☐ A 症狀分析　☐ B 客製化提醒　☐ C 健康時間軸　☐ 其他
- 7 條設計憲法中本次涉及：<!-- 例：規則 2「可信任、可解釋的 AI」 -->
