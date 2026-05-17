# UI 改善 Prompt（依 AutoResearch 結論）

> 此 prompt 可貼給 Claude Code 或其他 AI agent 執行，分階段改善 MD.Piece 的前端 UI。
> 依據：[`docs/research/ui_color_research.md`](../research/ui_color_research.md)
> 對應：[`docs/product-principles.md`](../product-principles.md) 7 條設計憲法

---

## 任務

依據 `docs/research/ui_color_research.md` 的研究結論，分階段改善 MD.Piece 的前端 UI。
每個階段獨立 commit / 獨立 PR，方便 review。

## 背景脈絡（必讀）
1. `docs/product-principles.md` — 7 條設計憲法（特別第 2、6、7 條）
2. `docs/research/ui_color_research.md` — 配色與長者特化研究
3. `frontend/css/style.css` — 目前的 `:root` 變數定義
4. `frontend/index.html` — 主入口
5. 主要使用者為台灣繁中、含長者與家屬族群

## 設計約束（不可違反）
- 主色保留 `#4A90C2`（已符合醫療藍共識）
- 輔色保留 `#5BB5A8`（sage teal）
- WCAG AA：內文對比 ≥ 4.5:1、標題 ≥ 3:1
- 長者模式：字級 ≥ 18 px、按鈕命中 ≥ 48 px、行高 ≥ 1.6
- 繁中字型保留 Noto Sans TC
- 一頁同時最多 1 個 CTA 顏色
- 警示色用「點」不用「面」（避免「過年感」）
- 不要大面積 Glassmorphism、不要 Neumorphism、不要純黑底

---

## 階段 1：設計 Token 集中化（P0）

在 `frontend/css/style.css` 的 `:root` 補上：

```css
/* Typography scale (mobile-first, 繁中筆畫密集 +1 階) */
--font-xs:    13px;
--font-sm:    14px;
--font-base:  16px;
--font-lg:    18px;
--font-xl:    20px;
--font-2xl:   24px;
--font-3xl:   32px;

/* Line height */
--lh-tight:   1.3;
--lh-base:    1.6;
--lh-loose:   1.8;

/* Spacing (4px grid) */
--space-1: 4px;  --space-2: 8px;   --space-3: 12px;
--space-4: 16px; --space-5: 20px;  --space-6: 24px;
--space-8: 32px; --space-10: 40px; --space-12: 48px;

/* Touch targets */
--tap-min:    44px;
--tap-elder:  56px;

/* Severity colors（搭配 routers/triage.py 回傳 severity_color） */
--sev-self:    var(--success);   /* 自我照護 */
--sev-clinic:  var(--accent);    /* 基層診所 */
--sev-regional:#1F3D58;          /* 區域醫院 */
--sev-medical: #5C4B8A;          /* 醫學中心 */
--sev-er:      var(--danger);    /* 急診 */
```

把現有元件的 hard-coded `px` / `line-height` 全部改用 token。

---

## 階段 2：新增 `.elder-mode`（P0）

新增 `frontend/css/elder-mode.css` 並在 `index.html` `<link>` 進來。

```css
html.elder-mode {
  --bg-deep:    #FFFBF5;   /* 暖白，HSL L≈97% */
  --bg-mid:     #FAF3E8;
  --accent:     #3B7AAA;   /* 加深 1 階以維持對比 */
  --danger:     #B84444;   /* 暗一階，避免刺激 */
  --font-base:  20px;
  --font-lg:    22px;
  --font-xl:    26px;
  --lh-base:    1.75;
  --tap-min:    var(--tap-elder);
}

html.elder-mode button,
html.elder-mode .btn {
  min-height: var(--tap-elder);
  min-width:  var(--tap-elder);
  font-size:  var(--font-lg);
  padding:    var(--space-4) var(--space-6);
}

html.elder-mode .icon { stroke-width: 2.5; }  /* filled-like */
```

在 `frontend/js/app.js` 加入切換按鈕：
- localStorage key: `md.elderMode`
- 預設值：跟隨 `?elder=1` query param 或 `false`
- 切換時 `toggle('elder-mode')` 在 `<html>`

---

## 階段 3：全 app 深淺主題（P1）

把 `#landing[data-theme="dark|light"]` pattern 抽到 `<html data-theme>`：

```css
html[data-theme="light"] { /* 現有 :root 值 */ }
html[data-theme="dark"] {
  --bg-deep: #0F1A24;
  --bg-mid:  #1A2A38;
  --text:    #E8F4F8;
  /* ... */
}
@media (prefers-color-scheme: dark) {
  html:not([data-theme]) { /* 套用 dark token */ }
}
```

規則（依研究第 5 章）：
- 預設：跟隨系統
- 症狀分析頁 (`#symptoms`)、報告頁 (`#reports`)：**強制 light**
- 夜間提醒 (`/medications` 推播)：**強制 dark**
- Landing：保留現有兩主題切換

---

## 階段 4：分級醫療色彩編碼（P1）

修改 `backend/routers/triage.py`：
- 回傳 JSON 增加 `severity_color` 欄位（值：`self | clinic | regional | medical | er`）
- 規則沿用 `backend/utils/triage_rules.py`

修改前端：
- 不要前端硬寫顏色
- 用 `data-severity="er"` attribute，由 CSS 套 `var(--sev-er)`

---

## 階段 5：Bento Grid 套用於健康時間軸（P1）

新增 `backend/routers/timeline.py`（場景 C）：
- `GET /api/timeline?patient_id=...`
- 回傳：`list[{date, type, title, summary, icd10, source}]`

前端：
- CSS Grid `grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))`
- 卡片大小依事件重要性變化（重要事件 `grid-column: span 2`）
- 卡片內：日期 + ICD-10 chip + 標題 + 一句話摘要

---

## 階段 6：對比與無障礙稽核（P0，每階段都要）

每個 PR push 前：
1. 跑 `npx @axe-core/cli http://localhost:3000`
2. 跑 Lighthouse Accessibility ≥ 95
3. 用 Chrome DevTools `Rendering > Emulate vision deficiencies` 看 protanopia / deuteranopia 是否仍可辨識
4. 開 `.elder-mode` 跑一遍主要流程

驗收標準：
- [ ] axe 0 violations
- [ ] Lighthouse Accessibility ≥ 95
- [ ] Color blindness simulation 下功能仍可辨識
- [ ] 長者模式下所有按鈕 ≥ 56 px、字 ≥ 20 px

---

## 交付規則

- 每階段獨立 branch：
  - `claude/ui-tokens`
  - `claude/elder-mode`
  - `claude/global-theme`
  - `claude/severity-color`
  - `claude/timeline-bento`
- 每個 PR 描述要對照憲法 7 條與場景 A/B/C
- 每個 PR 附前後對照截圖（含 light / dark / elder 三種模式）
- 跑 `tests/e2e` 通過後才能 ready for review
