# MD.Piece — 海邊記憶書 / Seaside Memory Book
## Visual Design Language (Art Direction v4)

> 「每一筆病歷，都是一塊回家的記憶碎片。」
> *Every medical record is a lost memory piece returning home.*

This is the complete visual design language for MD.Piece. It is **not** hospital
software, a SaaS dashboard, a productivity tool, or an electronic medical record.
It is a **healing illustrated storybook** that helps patients slowly rebuild the
puzzle of their lives through medical self-management.

**Production artifacts that ship with this document**

| File | Role |
| --- | --- |
| `frontend/css/seaside-tokens.css` | Production CSS tokens + primitive classes (`.sea-*`). Light · 夜紙 dark · 長者 senior. |
| `frontend/design-system.html` | Living styleguide — open in a browser to see every surface, with theme/senior toggles and the puzzle-collect microinteraction. |
| `docs/design-language.md` | This document — the brand bible (all 20 sections). |
| `frontend/design-system/tailwind.preset.js` | Tailwind token preset for the React/shadcn future (§16–17). |

---

## 0 · How this fits the existing codebase (Rule 7 — conflicts surfaced, not blended)

The repo already carries three competing skins and one contradicting reward model.
This language **supersedes the skins and reframes the reward model**, while
**re-using the existing semantic token names** so adoption is a re-skin, not a rewrite.

| Existing | Status under v4 | Action |
| --- | --- | --- |
| `css/tokens.css` ("Quiet Companion", navy+teal, *single source of truth*) | **Re-skinned.** v4 keeps its semantic names (`--surface-0/1/2`, `--content*`, `--status-*`, `--ev-*`, `.dark`, `[data-elder]`) and replaces the values. | Load `seaside-tokens.css` after `tokens.css`, or migrate values in. |
| `css/puzzle-tokens.css` ("Hanako-kun" cream/manga) | **Superseded** as the brand skin. The puzzle *concept* is kept; the cream/vermilion palette is retired. | Replace `.pz-*` usage with `.sea-*` over time. |
| `css/ghibli-theme.css` (education storybook) | **Absorbed.** v4 is storybook everywhere, so the education-only override becomes redundant. | Fold into global once v4 ships. |
| `css/rewards.css` + `docs/rewards-system.md` (**points / levels / badges**) | **Contradicts the brief** ("never earn points / never level up"). v4 reward model = pieces, not points. | **Follow-up:** `backend/utils/rewards_rules.py` still computes points. Keep the deterministic engine (Rule 5) but remap the *presentation* layer to pieces/chapters. Tracked in §5. |

> **Why surface this instead of averaging:** a UI that is half-points/half-pieces is
> worse than either. v4 picks the piece model (it *is* the product's core metaphor and
> the brief's explicit instruction) and flags the points engine for a clean remap.

This language also satisfies the **產品設計憲法** (`docs/product-principles.md`):
PWA-native, explainable AI (every AI line carries a "why"), customizable reminders,
cross-hospital timeline, decision-aid output, 長者/家屬 mode, and 繁中-first localization.

---

## 1 · Full Design System

### 1.1 Color
Five anchors, a closed family of derived steps (everything mixes from the five).

| Token | Hex | Role |
| --- | --- | --- |
| `--ocean-deep` | `#2C3943` | primary ink, headlines, deep water, `--primary` |
| `--cloudy-stone` | `#77726F` | secondary text, captions, `--content-muted` |
| `--ocean-breeze` | `#9DABB4` | quiet accents, lines, the calm `--action` (deepened for contrast) |
| `--coral-milk` | `#E5D4CA` | reward / care / warmth, `--accent` |
| `--soft-shell` | `#ECE6E3` | page paper, `--background-primary` |

**Semantic roles** (mirror `tokens.css` so components re-skin untouched):
`--surface-0/1/2`, `--surface-sunk`, `--content` / `--content-muted` / `--content-subtle`,
`--line` / `--line-soft` / `--line-ink`, `--primary` / `--action` / `--accent`,
`--on-fill` (text on deep fills) / `--on-fill-warm` (text on pale fills),
washes `--wash-ocean/coral/stone/deep`.

**Clinical severity** is muted to match the brief, but kept *separable* — patient
safety requires that ER never reads as ambiguous:
`--status-calm #7E9A86` → `--status-watch #C9A95E` → `--status-elevated #C98763` → `--status-urgent #C25A4C`,
plus the 5-tier 分級醫療 set (`--sev-self/clinic/regional/medical/er`).
**Rule: severity is always colour + icon + text, never colour alone.**

**Health-event registry** colour-codes the timeline/journey: `--ev-medication`,
`--ev-symptom`, `--ev-lab`, `--ev-appointment`, `--ev-hospitalization`, `--ev-emotion`,
`--ev-education`, `--ev-milestone`.

Forbidden: bright medical blue, neon, pure `#000`/`#fff`, Material palette, tech-startup gradients.

### 1.2 Typography
| Use | Family | Token |
| --- | --- | --- |
| Headlines 標題 | **Zen Old Mincho** → Noto Serif TC | `--font-display` |
| Editorial display / numerals | **Cormorant Garamond** (italic) → Noto Serif TC | `--font-serif` |
| Chinese body | **Noto Serif TC** | `--font-cjk` |
| Latin body / UI | **Inter** → Noto Serif TC (CJK glyph fallback) | `--font-body` |

Scale (`--scale` drives 長者 mode): `xs .8125 → 4xl 3rem`, leading `--lh-base 1.7`,
display tracking `.04em`, eyebrow tracking `.22em`. Feels editorial, book-like, timeless.

### 1.3 Space · Radius · Elevation · Texture
- Space: 4 → 64 px (`--space-1..16`).
- Radius: `--radius-small 16` / `--radius-medium 24` / `--radius-large 32` / `--radius-pill`,
  plus `--radius-wobble` for a hand-drawn storybook edge.
- Shadows: `--shadow-soft 0 8 24/.08`, `--shadow-medium 0 12 32/.12`, `--shadow-float`,
  `--shadow-press`. Watercolour-diffuse, never hard.
- Texture: `--grain-*` — a faint dotted paper tooth (`.sea-grain`). Organic, imperfect, handcrafted.

Forbidden: glassmorphism, cyberpunk, web3, corporate SaaS cards, generic healthcare UI.

### 1.4 Primitive classes (additive, prefix `.sea-`)
`sea-page` · `sea-grain` · `sea-card` (`--wobble`/`--raised`) · `sea-btn`
(`--primary`/`--accent`/`--quiet`) · `sea-chip` · `sea-sev--*` · `sea-why`
(required margin-note on AI output) · `sea-ic` (hand-drawn icon) · `sea-piece` / `sea-slot`
· `sea-reward` · `sea-empty` · `sea-bi` (bilingual). Full source in `seaside-tokens.css`.

---

## 2 · Information Architecture

The app is a **book of chapters**, not a tab bar of tools.

```
家 Home  ……………  今天的旅程 (Today's Journey) — the open page of the book
└ 我的拼圖旅程 Journey … the story map (8 chapters), entry to everything collected
   ├ 症狀手記        Symptom Tracking      (場景 A)
   ├ 服藥旅程        Medication            (場景 B)
   ├ 檢驗光譜        Lab Results           (場景 C)
   ├ 回診準備        Appointments          (場景 C)
   ├ 住院日誌        Hospitalization       (場景 C)
   ├ 情緒潮汐        Emotions              (場景 B)
   └ 衛教書房        Education
記憶圖書館 Library …… everything recovered, re-readable: timeline + summaries (場景 C)
小核 Xiaohe ………… the gentle guide (decision-aid AI), reachable from any page (場景 A)
我 / 我幫家人 ……… self / caregiver toggle (憲法 §6) — global, top-level
設定 Settings ……… reminders (時段/頻率/語氣), 長者 mode, 夜紙 mode, language
```

**Navigation model**
- **Mobile:** a 4-slot bottom "compass" — 家 · 旅程 · ＋記一筆 (center, the primary act) · 圖書館 — plus 小核 as a floating shell button. Center action is recording, because recording *is* how pieces return.
- **Tablet/Desktop:** a left "spine" rail (the book's binding) replaces the bottom compass; the journey map can sit permanently in a side column.

---

## 3 · UX Flow (the core loop)

The product has exactly one loop, told as a story:

```
看見今天的旅程  →  記一筆 (服藥/症狀/檢驗/回診/住院/情緒/衛教)
   →  一塊碎片浮起、緩緩旋轉、嵌入 (600–900ms 水彩漣漪)
   →  小核用一句話說「為什麼這件事重要」(explainable AI, 憲法 §2)
   →  章節更完整一點  →  回到首頁：「今天的旅程，又完整了一些。」
```

Design tensions resolved:
- **Never nag.** Calm-core. A missed dose shows a kind line, not a red alarm; severity colour is reserved for genuine clinical urgency.
- **Recording is one tap to start.** Voice, a single face, or a sentence all count (長者/家屬 friendly).
- **Every AI output is reversible and explainable** — the `sea-why` note + adjustable inputs, per the decision-aid constitution.

---

## 4 · Home Screen

Large hero on an **Ocean Breeze gradient** with illustrated clouds and a couple of
floating puzzle pieces (slow `sea-float`). Content:
- **Eyebrow:** *今天的旅程 · Today's Journey*
- **Headline (Zen Old Mincho):** 「今天的旅程，又完整了一些。」
- **Sub:** current chapter + pieces found today.
- **Pieces row:** today's collected `sea-piece`s next to empty `sea-slot`s.
- **Today's list:** 2–3 gentle items, each with an illustrated icon and a `sea-reward` note.

**Voice rule (this is the whole product in one example):**
✗ "3 Tasks Completed" → ✓ 「你找回了 3 塊記憶碎片。」
Numbers describe *memory returning*, never *productivity*. See `design-system.html#home`.

---

## 5 · Reward System

**Users never earn points, coins, or levels.** They collect:
- **生活碎片 / Life Pieces** — one per meaningful act.
- **拼圖碎片 / Puzzle Fragments** — pieces that belong to a specific chapter illustration.
- **找回的記憶 / Recovered Memories** — a completed illustration (chapter milestone).

Earning actions: medication completed · symptom recorded · appointment prepared · lab
uploaded · hospitalization documented · education article finished. **Each action
restores part of a memory illustration** — the reward *is* the picture becoming whole.

Visual grammar: `sea-reward` = an italic-serif "＋1 記憶碎片" on a coral wash — calm, no
number-go-up energy. Restoration plays `sea-restore` (soft glow + watercolour ripple).

> **Backend remap (follow-up, do not silently blend — §0):** keep the deterministic
> `rewards_rules.py` engine (Rule 5: scoring is if-else math, zero LLM) but rename the
> *presentation contract* — `earned → pieces`, `level → chapter`, `badge → recovered
> memory`. The API can stay numeric internally; the UI must never surface points/levels.

---

## 6 · Puzzle Journey (我的拼圖旅程)

A **story map**, not a dashboard. Eight illustrated chapters, each with a unique
illustration, collectible pieces, story moments, and a milestone:

1. 春日復健室 · **Spring Recovery Room** — `--chapter-spring`
2. 雨天診間 · **Rainy Day Clinic** — `--chapter-rain`
3. 夏日研究室 · **Summer Research Room** — `--chapter-summer`
4. 海邊走廊 · **Seaside Corridor** — `--chapter-seaside`
5. 黃昏醫院庭園 · **Twilight Hospital Garden** — `--chapter-twilight`
6. 星之迴廊 · **Star Corridor** — `--chapter-star`
7. 記憶圖書館 · **Memory Library** — `--chapter-library`
8. 未來的地平線 · **Future Horizon** — `--chapter-horizon`

Layout: a winding path; completed nodes carry a small ribbon, the active node glows
(`--memory-glow-on`), locked nodes are dashed and faint. See `design-system.html#journey`.

---

## 7 · Symptom Tracking · 症狀手記  (場景 A)

- **Prompt as poetry:** 「今天的身體，像什麼天氣？」 — a sentence, a single face, or voice.
- Severity surfaced via `sea-sev--*` (colour + text), never colour alone.
- 小核 returns a decision-aid card: 選項 + 利弊 + 個人化風險 + 下一步, each with a `sea-why`
  (which symptoms triggered it, what weight, why this tier — `routers/symptoms.py` + `triage.py`).
- Recording restores a Symptom-chapter piece.

## 8 · Medication Management · 服藥旅程  (場景 B)

- **Customizable reminders** (憲法 §3): 時段 · 頻率 · 語氣 (嚴肅/鼓勵/極簡) · channel.
- **Caregiver mirror:** 家屬 receives the reminder and can reply 「已協助服藥」.
- Missed/refused dose links to **情緒潮汐** (emotions), with a kind line — never an alarm.
- Each logged dose restores a Medication-chapter piece. 長者 mode = oversized targets + voice confirm.

## 9 · Lab Results · 檢驗光譜  (場景 C)

- **Camera-first:** photograph a report → OCR + LLM extraction (Rule 5: deterministic
  parse, model only for unstructured extraction) → structured, ICD-10 tagged, placed on the timeline.
- Trends drawn as **soft watercolour curves**, not clinical tables; out-of-range points
  carry a `sea-why` in plain language. Uploading restores a Lab-chapter piece.

## 10 · Appointment Management · 回診準備  (場景 C)

- Before a visit, 小核 drafts a one-page **就診摘要** (questions to ask + recent changes)
  to bring along (decision-aid, 憲法 §5).
- Reminders are customizable and caregiver-shareable. Preparing restores an Appointment piece.

## 11 · Hospitalization Module · 住院日誌  (場景 C)

- Reframes a hospital stay as a **re-readable chapter**, not a discharge-summary stack:
  day-by-day moments, medications, labs, who visited.
- Generates a shareable **出院故事 / discharge story** PDF. Documenting restores Hospitalization pieces.

---

## 12 · Achievement System

Never "Achievement Unlocked". Milestones are narrated as memory returning:
- 「新的記憶碎片被找回了」
- 「一段遺失的故事重新浮現」
- 「海風帶來了新的線索」
- 「你的旅程更加完整了」

Presented as a `toast` with a wax-seal/anchor/compass illustration + an italic English
subtitle, animated with `sea-restore`. See `design-system.html#achievements`.

---

## 13 · Illustration Guidelines

- **Atmosphere:** Studio Ghibli quiet + Japanese watercolour + vintage travel journal +
  detective/memory-archive notebook. A quiet seaside town; a notebook on a hospital
  windowsill; summer breeze through curtains.
- **Technique:** soft gouache/watercolour washes within the closed palette; visible paper
  tooth (`--grain`); hand-drawn single-weight ink line (`stroke-width 1.7`, round caps);
  organic, slightly imperfect shapes; soft diffuse shadows.
- **Icons:** illustrated, hand-drawn, line-based. Subjects: notebook, medicine bottle, lab
  droplet, calendar, hospital bed, camera, compass, wave, cloud, book, wax seal, anchor,
  flower, star. **No emoji. No Material icons.** (Sprite lives in `design-system.html`.)
- **Puzzle pieces:** a true piece silhouette (one knob, one blank). Empty = dashed slot in
  `--ocean-breeze`; filled = `--coral-milk` with a soft shadow.
- **Chapters:** each chapter has one signature illustration that *completes* as its pieces return.
- **Avoid:** glassmorphism, cyberpunk, web3, stock corporate healthcare imagery, flat-vector clip-art.

---

## 14 · Motion Design System

Calm-core, storybook, accessible. Tokens: `--ease-settle` (gentle snap), `--ease-out`,
`--ease-page` (page turn); durations `--motion-fast 180` / `base 280` / `slow 460` /
`piece 760` / `breathe 6s`.

| Interaction | Motion | Duration |
| --- | --- | --- |
| Puzzle collect | float in · slow rotate · snap into place · watercolour ripple (`sea-collect`) | **600–900ms** |
| Memory restore | soft glow swell + settle (`sea-restore`) | 900ms |
| Button | subtle lift on hover, paper-press on active | 180ms |
| Page transition | storybook page turn / journal opening (`sea-pageturn`) | 460ms |
| Ambient | clouds & floating pieces drift (`sea-float`) | 6s loop |

**`prefers-reduced-motion`** collapses all of the above to ~1ms and disables loops.
Calm by default; still on request.

---

## 15 · React Component Architecture

> The live app today is **Vanilla JS PWA** (Rule 7 conflict noted: the brief asks for
> React/Tailwind/shadcn). The CSS layer (`seaside-tokens.css` + `.sea-*`) ships *today*
> in the vanilla app; the React layer below is the **forward path** — same tokens, same
> class semantics, so migration is incremental, not a rewrite.

```
src/design-system/
  tokens.css                  // = seaside-tokens.css (single source of truth)
  primitives/                 // 1:1 with .sea-* classes
    Surface.tsx               // <Surface variant="page|card|raised|sunk" wobble?>
    Button.tsx                // variant: primary | accent | quiet | ghost
    Chip.tsx | SeverityTag.tsx // tier: self|clinic|regional|medical|er
    WhyNote.tsx               // REQUIRED wrapper for any AI output (憲法 §2)
    Icon.tsx                  // <Icon name="notebook|pill|droplet|…"> from the sprite
    PuzzlePiece.tsx           // state: empty | filling | filled (drives sea-collect)
    RewardNote.tsx | EmptyState.tsx | Eyebrow.tsx | BilingualLabel.tsx
  patterns/
    HeroJourney.tsx           // home hero
    JourneyMap.tsx            // 8-chapter story map
    ChapterNode.tsx           // locked | active | complete
    AchievementToast.tsx      // memory-returned language
    DecisionAidCard.tsx       // 選項+利弊+風險+下一步 (+WhyNote)
    TimelineRibbon.tsx        // 記憶圖書館 horizontal timeline (場景 C)
  modes/
    ThemeProvider.tsx         // toggles .dark / [data-theme], [data-elder]/[data-mode]
    useReducedMotion.ts | useCaregiverView.ts   // 我 / 我幫家人
```

Principles: primitives are dumb + token-driven; patterns compose primitives; **every AI
surface is wrapped in `<WhyNote>`**; mode is context, never per-component props.

---

## 16 · Tailwind Design Tokens

Ships as `frontend/design-system/tailwind.preset.js` (consume via `presets: [...]`).
It maps every CSS variable to a Tailwind scale so utilities read from the same source:

```js
// excerpt — full file in frontend/design-system/tailwind.preset.js
colors: {
  ocean:  { deep:'#2C3943', breeze:'#9DABB4', 'breeze-d':'#6E828E' },
  stone:  '#77726F', coral:{ milk:'#E5D4CA', d:'#C99F8C' }, shell:'#ECE6E3',
  surface:{ 0:'var(--surface-0)',1:'var(--surface-1)',2:'var(--surface-2)' },
  content:{ DEFAULT:'var(--content)', muted:'var(--content-muted)', subtle:'var(--content-subtle)' },
  sev:{ self:'var(--sev-self)', clinic:'var(--sev-clinic)', regional:'var(--sev-regional)',
        medical:'var(--sev-medical)', er:'var(--sev-er)' },
},
borderRadius:{ sm:'16px', md:'24px', lg:'32px', pill:'999px' },
boxShadow:{ soft:'0 8px 24px rgba(44,57,67,.08)', medium:'0 12px 32px rgba(44,57,67,.12)' },
fontFamily:{ display:['Zen Old Mincho','Noto Serif TC','serif'],
             serif:['Cormorant Garamond','Noto Serif TC','serif'],
             body:['Inter','Noto Serif TC','system-ui','sans-serif'] },
```

Dark mode is `class` strategy (`.dark`); senior scale via the `--scale` CSS var (utilities
need no change). Keep using CSS vars in the preset so light/dark/senior switch with no rebuild.

---

## 17 · shadcn/ui Mapping

shadcn primitives are adopted **but re-skinned** to the Seaside language (never shipped
with default Material-ish styling):

| shadcn | Re-skin | Notes |
| --- | --- | --- |
| `Button` | `.sea-btn` variants | pill, paper-press, `--ease-settle` |
| `Card` | `.sea-card` | soft shadow, hairline ink, optional `--wobble` |
| `Badge` | `.sea-chip` / `SeverityTag` | severity = colour + text |
| `Alert` | `WhyNote` (`.sea-why`) | italic serif margin-note for AI "why" |
| `Toast` (sonner) | `AchievementToast` | memory-returned copy + `sea-restore`, never "unlocked" |
| `Progress` | `JourneyMap` pieces | replace bars with collected pieces |
| `Dialog`/`Sheet` | storybook `sea-pageturn` open | journal-opening feel |
| `Tabs` | chapter spine | tabs styled as book chapters |
| `Tooltip`/`Popover` | paper card + ink line | no glassmorphism |
| `Avatar` | self / 家屬 view | ties to `useCaregiverView` |

Disable shadcn's default ring/радius; point its CSS vars at ours
(`--background`, `--foreground`, `--primary`, `--radius` → seaside tokens).

---

## 18 · Mobile UI (≤ 640px — the primary surface, PWA)

- One-column book page; generous leading; min body 16px (18px in 長者).
- Bottom **compass** nav (家 · 旅程 · ＋記一筆 · 圖書館) + floating 小核 shell.
- Hero fills the first screen; pieces row + 2–3 journey items below the fold.
- Sheets open with `sea-pageturn`. Touch targets ≥ 48px (56px senior). Safe-area aware
  (`viewport-fit=cover`). Offline-cached records readable (PWA, 憲法 §1).

## 19 · Tablet UI (641–1024px)

- Two-column **spread**: left = story map / chapter list (the binding), right = open page.
- Bottom compass → left spine rail. Journey map can stay persistent.
- Hero spans full width; module cards in a 2-up grid. Great for 家屬 reviewing with the patient.

## 20 · Desktop UI (≥ 1025px)

- Three zones: **spine rail** (left, ~240px) · **open page** (center, max ~720px reading
  measure) · **margin** (right — 小核 notes, `WhyNote`s, today's pieces).
- Content stays book-width; never edge-to-edge dashboard. 記憶圖書館 timeline uses the
  full width as a horizontal scroll (場景 C). Same tokens, same components — only the
  frame changes.

---

## Adoption checklist

1. Add the four Google Font families to the app `<head>` (see `design-system.html`).
2. `<link>` `css/seaside-tokens.css` **after** `tokens.css` (override) — or migrate values in.
3. Replace `.pz-*` / ad-hoc skin classes with `.sea-*` incrementally.
4. Remap the rewards presentation layer (points→pieces) per §5; keep the deterministic engine.
5. For the React future: `presets:[require('./frontend/design-system/tailwind.preset.js')]`,
   re-skin shadcn vars (§17), wrap every AI surface in `<WhyNote>`.

> **Target quality:** Apple HIG + Linear + Notion + Studio Ghibli art direction + modern
> healthcare UX. The result should feel like a seaside memory book that helps patients
> slowly rebuild the puzzle of their lives.
