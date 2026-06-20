# MD.Piece — Design Language

## “The Seaside Memory Book” — 海邊的記憶之書

> Every medical record is a lost memory piece returning home.
> 每一筆醫療紀錄，都是一塊回家的記憶碎片。

A patient-centered medical companion that feels like a **healing illustrated storybook** — a quiet seaside town, a notebook left on a hospital windowsill, a summer breeze through curtains, a story slowly recovering itself. Not hospital software. Not a dashboard. A memory archive that helps people rebuild the puzzle of their lives.

---

## 0 · North Star & Principles

| # | Principle | In practice |
|---|---|---|
| 1 | **Story over status** | Never “3 tasks done”. Always “你找回了 3 塊記憶碎片。” |
| 2 | **Restore, don’t reward** | No points/coins/levels/streaks. Actions *restore* a memory illustration. |
| 3 | **Calm by default** | Generous negative space, slow motion, muted palette, one focal point per view. |
| 4 | **Handcrafted, imperfect** | Organic shapes, paper grain, slightly off-grid placement, illustrated icons. |
| 5 | **Editorial typography** | Serif headlines set like a printed book; long line-height; real hierarchy. |
| 6 | **Explainable & gentle** | Every AI/derived value shows a quiet “為什麼”. No alarms, no red dashboards. |
| 7 | **Elder & family first** | Scales to large type, high contrast, voice; nothing breaks at `--scale: 1.25`. |
| 8 | **Bilingual, literary** | zh-TW primary (Noto Serif TC / Zen Old Mincho), en secondary (Cormorant / Inter), both written like prose, never machine-tone, never AI-tone. |

**Anti-patterns (never):** glassmorphism, neon, pure #000/#fff, Material colors, SaaS cards, tech gradients, OLED black, emoji, “Achievement Unlocked”.

---

## 1 · Full Design System (Foundations)

### 1.1 Color — primitives

```
--ocean-deep:    #2C3943;   /* Deep Ocean   — primary text, ink */
--cloudy-stone:  #77726F;   /* Cloudy Stone — secondary text */
--ocean-breeze:  #9DABB4;   /* Ocean Breeze — accent, sky, calm */
--coral-milk:    #E5D4CA;   /* Coral Milk   — warmth, highlight, sand */
--soft-shell:    #ECE6E3;   /* Soft Shell   — page background */
```

### 1.2 Color — semantic (light)

```
--background-primary:   #ECE6E3;  /* soft-shell */
--background-secondary: #F5F1EE;  /* lifted paper */
--surface-primary:      #F7F4F2;  /* cards, sheets */
--surface-sunk:         #E7E0DB;  /* wells, tracks, locked pieces */

--text-primary:         #2C3943;
--text-secondary:       #77726F;
--text-tertiary:        #9DABB4;  /* captions, metadata, romaji */
--text-on-accent:       #F7F4F2;

--line:                 rgba(44,57,67,.10);   /* hairlines, paper seams */
--line-strong:          rgba(44,57,67,.18);

--accent:               #9DABB4;  /* ocean breeze — primary action tint */
--accent-deep:          #6E828E;  /* darkened breeze for AA text on light */
--accent-warm:          #E5D4CA;  /* coral milk — collectible, warmth */
--accent-warm-deep:     #C9A892;  /* darkened coral for borders/labels */

/* States — all muted, never alarm-bright */
--state-restored:       #8AA39B;  /* a piece returned (soft sea-green) */
--state-gentle-warn:    #C9A892;  /* attention, dusty terracotta — not red */
--state-rest:           #9DABB4;  /* info / night */
```

> **Why darkened variants:** Ocean Breeze `#9DABB4` on Soft Shell is ~1.6:1 — decorative only. For any *text or icon that must be read*, use `--accent-deep #6E828E` (≈4.6:1 on `--soft-shell`) or `--text-primary`. Deep Ocean on Soft Shell ≈ 10.8:1. Document AA pairings in §accessibility.

### 1.3 Color — semantic (dark · “paper at night”)

```
--ocean-night:   #1F2830;  /* Dark Ocean   — page */
--ocean-muted:   #3A4954;  /* Muted Ocean  — surface */
--blue-gray:     #7F919D;  /* Soft Gray Blue — secondary text/accent */
--warm-mist:     #CFC5BF;  /* Warm Mist    — primary text */

--background-primary:   #1F2830;
--background-secondary: #243038;
--surface-primary:      #2A3741;   /* muted-ocean lifted */
--surface-sunk:         #1A222A;
--text-primary:         #CFC5BF;   /* warm mist, not white */
--text-secondary:       #9DA7AD;
--accent:               #7F919D;
--accent-warm:          #B89B8B;   /* coral milk, dimmed */
--line:                 rgba(207,197,191,.10);
```

Dark mode keeps **warmth** (warm-mist text, never #fff; ocean-night page, never #000). Shadows become inner-glow + slightly raised surfaces rather than dark drop shadows.

### 1.4 Typography

| Role | Font | Notes |
|---|---|---|
| Display / Chapter titles | **Zen Old Mincho** | mincho headline, the “book cover” voice |
| Headlines zh | **Noto Serif TC** (700) | section + card titles |
| Body zh | **Noto Serif TC** (400) | reading-grade serif, line-height 1.8 |
| Display / Headlines en | **Cormorant Garamond** | editorial, italic for quiet emphasis |
| Body / UI en + numerals | **Inter** | legibility, tabular numerals for data |

```
--font-display: "Zen Old Mincho","Noto Serif TC",serif;
--font-serif:   "Noto Serif TC","Cormorant Garamond",serif;
--font-body:    "Inter","Noto Serif TC",system-ui,sans-serif;  /* UI chrome, numbers */
--font-reading: "Noto Serif TC","Cormorant Garamond",serif;     /* long copy */
```

**Type scale** (1.2 minor-third, fluid via `clamp`, scaled by `--scale` for elder mode):

```
--text-xs:   calc(0.75rem  * var(--scale,1));  /* 12 — romaji, meta */
--text-sm:   calc(0.875rem * var(--scale,1));  /* 14 — captions */
--text-base: calc(1.0rem   * var(--scale,1));  /* 16 — body, lh 1.8 */
--text-lg:   calc(1.25rem  * var(--scale,1));  /* 20 — card title */
--text-xl:   calc(1.5rem   * var(--scale,1));  /* 24 — section */
--text-2xl:  calc(2.0rem   * var(--scale,1));  /* 32 — page title */
--text-3xl:  clamp(2.25rem, 6vw, 3.25rem);     /* chapter display */
--leading-reading: 1.8;
--leading-tight:   1.25;
--tracking-display: 0.04em;  /* mincho breathes */
```

Headlines: Zen Old Mincho, `--tracking-display`, `--leading-tight`. Body: Noto Serif TC, `--leading-reading`, max line length **38 zh chars / 68 en chars**.

### 1.5 Spacing, radius, elevation, texture

```
/* 8-pt soft grid, but layouts may sit slightly off-grid on purpose */
--space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px;
--space-5:24px; --space-6:32px; --space-7:48px; --space-8:64px; --space-9:96px;

--radius-small:16px; --radius-medium:24px; --radius-large:32px;
--radius-pill:999px; --radius-organic:42% 58% 60% 40% / 45% 45% 55% 55%; /* blob */

--shadow-soft:   0 8px 24px rgba(44,57,67,.08);
--shadow-medium: 0 12px 32px rgba(44,57,67,.12);
--shadow-lifted: 0 18px 48px rgba(44,57,67,.14);
--shadow-press:  inset 0 2px 6px rgba(44,57,67,.10);

/* Paper grain — applied as a low-opacity overlay, never tiling that distracts */
--paper-grain: url("/textures/paper-grain.png");   /* 200×200, 2–4% opacity */
--paper-edge:  1px solid var(--line);               /* torn/deckle handled by mask */
```

No hard 1px tech borders by default — separation comes from **paper elevation + grain + hairline**, not boxes.

### 1.6 Motion primitives

```
--ease-page:   cubic-bezier(.22,.61,.36,1);    /* storybook turn */
--ease-soft:   cubic-bezier(.34,1.2,.64,1);    /* gentle overshoot (paper settle) */
--ease-out:    cubic-bezier(.16,1,.3,1);
--dur-quick:120ms; --dur-base:240ms; --dur-slow:480ms;
--dur-piece:750ms;   /* puzzle piece float→snap, 600–900ms */
--dur-page:520ms;    /* page turn */
```

All motion respects `@media (prefers-reduced-motion: reduce)` → cross-fade ≤120ms, no float/rotation.

---

## 2 · Information Architecture

```
MD.Piece
├── 首頁  Today’s Journey            (home — chapter + today’s pieces)
├── 我的拼圖旅程  Puzzle Journey      (story map of 8 chapters)
│     └── Chapter → pieces / story moments / milestones
├── 紀錄  The Notebook               (record hub)
│     ├── 症狀  Symptoms
│     ├── 用藥  Medication
│     ├── 檢驗  Lab Results
│     ├── 情緒  Mood / 電量
│     └── 生理 · 飲食 · 睡眠
├── 回診  Appointments               (visit prep + timeline)
├── 住院  Hospitalization            (survival companion)
├── 衛教  Reading Room               (educational stories)
└── 我的  Me                         (profile, family/elder mode, settings, the book’s “colophon”)
```

**Nav model**
- **Mobile:** bottom “journal tabs” — 首頁 · 旅程 · ＋紀錄 · 回診 · 我的. Center “＋” is a wax-seal/inkwell FAB that opens the record sheet.
- **Tablet:** left rail (icons + labels) + content; journey can be a 2-pane (map + chapter detail).
- **Desktop:** left rail + a wide reading canvas (max-width 1120, centered like a book spread). Optional right “margin notes” column for AI explanations.

Records always roll up into the **Journey**: each record restores a piece in the *current chapter*.

---

## 3 · UX Flow (key journeys)

**A. Record → Restore (the core loop)**
1. Tap ＋ (wax seal) → record sheet rises like a turning page.
2. User logs (symptom / med / lab…) with minimal friction, serif prompts, gentle copy.
3. On save: a **piece floats up, rotates slowly, glows, snaps** into the current chapter’s illustration (750ms).
4. Toast (no badge): *“海風帶來了新的線索。你找回了 1 塊記憶碎片。”*
5. Home’s “Today’s Journey” line updates: *“今天的旅程又完整了一些。”*

**B. Open the Journey**
Home “current chapter” card → page-turn into the **story map**; the active chapter is partially illustrated, locked chapters are misty silhouettes. Tap a chapter → its illustrated board (the 3×3+ puzzle) + story moments.

**C. Visit preparation**
Appointment card → “為回診收拾行囊” checklist (symptoms summary, meds, questions). Completing prep restores pieces in *Seaside Corridor*.

**D. Onboarding**
A 4-spread “picture book intro”: who you are → what a piece is → the journey → your first piece (free, to teach the loop). No forms-first.

---

## 4 · Home Screen — “Today’s Journey / 今天的旅程”

**Hero** (full-bleed top):
- Background: **Ocean Breeze vertical gradient** `#9DABB4 → #C3CDD2 → #ECE6E3`, illustrated **clouds** drifting (very slow parallax), 2–3 **floating puzzle pieces** with soft glow.
- Greeting in Zen Old Mincho: *「午安，{name}。」* + date set as a quiet caption.
- One sentence, the soul line: **「今天的旅程又完整了一些。」**

**Today’s pieces** (not a counter):
> 「你找回了 **3** 塊記憶碎片。」 — the number in Cormorant, oversized, warm; below it three small restored-piece thumbnails with a watercolor ripple on appear.

**Current chapter card** (tappable → Journey):
- Chapter illustration (partial), title in mincho (e.g. *Rainy Day Clinic / 雨天的診間*), a thin progress “tide line” (not a bar — a watercolor shoreline that fills).
- Caption: *「這一章，還差 4 塊就完整了。」*

**Today’s gentle invitations** (max 3, never “tasks”):
- 「為今天的身體留一句話」 → Symptoms
- 「別忘了中午的藥」 → Medication
- 「上次的檢驗，想一起收進旅程嗎？」 → Labs

**Empty/first-run:** misty hero, one piece, *「你的故事正要開始。」*

No KPIs, no red counts, no streak flames.

---

## 5 · Reward System — **Life Pieces**

There are **no points, coins, levels, or streaks.** There are only **pieces of a life returning home.**

| Concept | Name | Meaning |
|---|---|---|
| Unit | **記憶碎片 / Life Piece** | one restored fragment of a chapter illustration |
| Set | **章節拼圖 / Chapter Mosaic** | a complete illustrated scene |
| Archive | **記憶之書 / Memory Book** | all chapters collected over time |

**Restoring actions** (deterministic, explainable, monotonic — never taken back):
- 服藥完成 · 症狀紀錄 · 回診準備 · 檢驗上傳 · 住院紀錄 · 讀完一篇衛教 → each restores part of a memory illustration.

**Rules of feeling**
- Pieces are **earned by living, not spending.** No store, no gacha, no loss aversion.
- Progress is **monotonic**: a restored piece never disappears.
- Every piece carries a **“為什麼這塊回來了 / 還差什麼”** note (explainability, constitution §2).
- Completing a chapter does **not** unlock a transaction; it reveals a **story moment** and quietly invites the next chapter.

(Engineering note: the live product already computes pieces deterministically from existing records — this language renames *points→pieces*, *level→chapter*, *badge→story moment*, and re-skins, with **zero gambling mechanics**.)

---

## 6 · Puzzle Journey — 我的拼圖旅程

A **story map**, not a dashboard. A meandering seaside path connecting 8 illustrated rooms; the path is hand-inked, the user’s position marked by a small drifting paper boat.

**Chapters** (each = unique illustration + collectible pieces + story moments + milestones):
1. **Spring Recovery Room / 春日療癒室** — first light, sprouts, open window
2. **Rainy Day Clinic / 雨天的診間** — umbrella, rain on glass, warm lamp
3. **Summer Research Room / 夏日研究室** — notebooks, specimens, sea-light
4. **Seaside Corridor / 海邊的迴廊** — long windows, breeze, curtains
5. **Twilight Hospital Garden / 黃昏的醫院花園** — dusk, lanterns, blooming beds
6. **Star Corridor / 星之迴廊** — night, constellations, quiet
7. **Memory Library / 記憶圖書館** — shelves of recovered stories
8. **Future Horizon / 遠方的地平線** — dawn over the sea, open road

**Chapter board**
- The illustration is split into pieces (3×3 baseline, larger for late chapters). Restored pieces show full art; unrestored are **misty silhouettes** (not grey lock boxes) with a one-line clue.
- **Story moments** appear at milestones (¼, ½, full) as a turned journal page with a short literary passage.
- Completion: the full scene blooms with a watercolor ripple; a pressed-flower bookmark is added to the **Memory Book**.

---

## 7 · Symptom Tracking — 「為身體留一句話」

- Entry feels like **writing in a notebook**, not filling a form: serif prompt *「今天，身體想說什麼？」*, a soft paper field, optional body-map illustration (hand-drawn) to tap where it hurts.
- Severity as a **tide** (1–5 watercolor levels), never red 1–10 clinical scale on screen (store clinically, show gently).
- Each entry → a piece in the current chapter + a quiet timeline ribbon.
- **Empty state:** illustration of an empty notebook. *「今天還沒有留下任何紀錄。」*

## 8 · Medication Management — 「照顧自己的一部分」

- Meds shown as **illustrated bottles/blisters** on a windowsill, not a table.
- “Today’s doses” = soft cards with a gentle time-of-day sun/moon illustration; taking a dose = a **paper-press** check + ripple, restores a piece.
- Reminders are **customizable in time / frequency / tone** (warm · plain · brief), per constitution §3 — copy never nags.
- **Empty state:** illustration of a medicine bottle. *「記錄每一次服藥，也是照顧自己的一部分。」*

## 9 · Lab Results — 「把數字收進故事裡」

- Upload (photo/PDF/manual) framed as **pressing a leaf into the book**.
- Each value shown with a **plain-language one-liner** + a calm range illustration (a shoreline marking low/normal/high), never a red/green dashboard.
- Trends as **watercolor sparklines** on cream.
- Restores pieces in *Summer Research Room*.

## 10 · Appointment Management — 「為回診收拾行囊」

- Next visit as a **train-ticket / luggage-tag** illustrated card with a soft countdown (“還有 12 天”).
- Visit-prep checklist (symptoms recap, meds list, questions to ask) presented as packing a small bag; completion restores pieces in *Seaside Corridor* and produces a one-page **“給醫師的小紙條”** summary (Decision-Aid grade, constitution §5).

## 11 · Hospitalization Module — 「住院生存手記」

- A **survival companion**, not a management console: “現在發生什麼／接下來會怎樣／我可以做什麼”.
- Day-by-day **journal spreads**; vitals/measurements entered as notes; a calm “今天的醫院花園” illustration evolves through the stay.
- Family/elder mode: large type, voice notes, a shareable daily digest. Restores pieces in *Twilight Hospital Garden*.

## 12 · Achievement System — copy as story

Never “Achievement Unlocked”. Rotate, fit context:
- 「新的記憶碎片被找回了。」
- 「一段遺失的故事重新浮現。」
- 「海風帶來了新的線索。」
- 「你的旅程更加完整了。」

Presented as a **turned page / pressed bookmark**, with the *why* beneath. Never modal-blocking; it settles in like a note slipped into a book.

---

## 13 · Illustration Guidelines

- **Medium:** Japanese watercolor + ink line; Studio-Ghibli atmosphere; vintage travel-journal framing.
- **Line:** confident, slightly imperfect ink; variable weight; never vector-perfect.
- **Color:** the 5-color palette + tints only; layered translucent washes; grain; soft edges (washes may breathe past the line).
- **Light:** warm, low-contrast, “golden hour / overcast morning”.
- **Subjects:** windows, clouds, sea, curtains, notebooks, lanterns, sprouts, pressed flowers, paper boats, medical objects rendered *tenderly* (a bottle, a thermometer, a chart as keepsakes).
- **Icons:** hand-drawn / watercolor; consistent 1.5–2px ink at 24px; categories — notebook, archive, camera, medical-journal, puzzle, seaside motifs. **No emoji, no Material icons.**
- **Puzzle art spec (for production):** 1:1 square, ≥1200px, detail balanced across all 9 zones, nothing critical on the 33%/67% seams, ~5% safe margin, no baked-in text. PNG/SVG/JPG.
- **Sourcing:** commission or AI-generate to this spec; keep a **style bible** (palette chips, line samples, do/don’t). Avoid stock that breaks the world.

---

## 14 · Motion Design System

| Interaction | Behavior | Duration / ease |
|---|---|---|
| **Piece collection** | float up · slow rotate (≤8°) · soft glow · snap to slot · watercolor ripple | 600–900ms · `--ease-soft` |
| **Button** | subtle lift on hover; **paper-press** (scale .98 + inset shadow) on down | 120/240ms · `--ease-out` |
| **Page transition** | **storybook page-turn** (skew+shadow sweep) between major sections; **journal-open** for record sheet | 520ms · `--ease-page` |
| **Card enter** | rise 8px + fade + tiny settle | 240–360ms · `--ease-soft`, staggered ≤90ms |
| **Chapter complete** | full-scene bloom + ripple + bookmark slides into book | 900ms · `--ease-out` |
| **Tide/progress** | shoreline wash fills, not a bar sliding | 480ms |
| **Reduced motion** | all of the above → ≤120ms cross-fade, no float/rotate/parallax | — |

Motion is **slow, soft, and rare** — it punctuates meaning (a piece returning), it doesn’t decorate every tap.

---

## 15 · React Component Architecture (portable spec)

> The shipping app is vanilla-JS (see §21). This is the canonical component model — use it as the spec for a future React build *or* as the contract the vanilla components mirror.

```
<AppShell>                     // background grain, theme + scale providers
 ├─ <SeaTabBar/> | <SeaRail/>  // responsive nav (journal tabs / rail)
 ├─ <PageTurn>                 // route transition wrapper (storybook)
 │   └─ <Screen>
 ├─ <RecordSheet/>            // ＋ inkwell → rising journal sheet
 └─ <PieceLayer/>             // portal for floating-piece animations

Primitives
 <PaperSurface variant="card|sheet|well" elevation="soft|medium|lifted">
 <SerifHeading level rhythm>        // Zen Old Mincho / Noto Serif TC
 <Prose>                            // reading-grade serif body
 <SeaButton variant="ink|breeze|ghost" press="paper">
 <TideMeter value/>                 // shoreline progress
 <Clue/> <StoryMoment/>             // explainability + milestone page
 <WatercolorIcon name/>             // hand-drawn icon set
 <EmptyState illo copy/>

Domain
 <JourneyMap chapters/> <ChapterBoard pieces/> <PuzzlePiece state/>
 <TodayJourney/> <PieceCounterProse/>          // “你找回了 N 塊…”
 <SymptomNote/> <MedWindowsill/> <DoseCard/>
 <LabPressedLeaf/> <RangeShoreline/>
 <VisitTicket/> <PackingChecklist/> <DoctorNote/>
 <StayJournal/> <GardenScene/>
```

State: server state via TanStack Query; derived “pieces” computed deterministically (pure, testable). Animations via Framer Motion mapped to §14 tokens. Strict a11y props on every interactive node.

## 16 · Tailwind Design Tokens

```js
// tailwind.config.js — theme.extend
colors: {
  ocean:   { deep:'#2C3943', breeze:'#9DABB4', breezeDeep:'#6E828E', night:'#1F2830', muted:'#3A4954' },
  stone:   { DEFAULT:'#77726F', blue:'#7F919D' },
  coral:   { milk:'#E5D4CA', deep:'#C9A892' },
  shell:   { DEFAULT:'#ECE6E3', soft:'#F5F1EE', surface:'#F7F4F2', sunk:'#E7E0DB' },
  mist:    '#CFC5BF',
},
fontFamily: {
  display:['"Zen Old Mincho"','"Noto Serif TC"','serif'],
  serif:  ['"Noto Serif TC"','"Cormorant Garamond"','serif'],
  body:   ['Inter','"Noto Serif TC"','system-ui','sans-serif'],
},
borderRadius:{ sm:'16px', md:'24px', lg:'32px' },
boxShadow:{
  soft:'0 8px 24px rgba(44,57,67,.08)',
  medium:'0 12px 32px rgba(44,57,67,.12)',
  lifted:'0 18px 48px rgba(44,57,67,.14)',
  press:'inset 0 2px 6px rgba(44,57,67,.10)',
},
transitionTimingFunction:{ page:'cubic-bezier(.22,.61,.36,1)', soft:'cubic-bezier(.34,1.2,.64,1)' },
backgroundImage:{ grain:"url('/textures/paper-grain.png')", breeze:'linear-gradient(180deg,#9DABB4,#C3CDD2,#ECE6E3)' },
```

Plugins: `@tailwindcss/typography` (retune `prose` to Noto Serif TC, lh 1.8, max 38ch). Dark mode: `class` strategy, remap `shell.* → ocean-night/muted`, `text → mist`.

## 17 · shadcn/ui Mapping

Keep shadcn’s structure/accessibility; **replace the skin** with the Memory-Book language.

| shadcn | Re-skin |
|---|---|
| `Button` | `SeaButton` — ink (filled `--ocean-deep`), breeze (filled `--ocean-breeze`/`accent-deep` text), ghost; **paper-press** active state |
| `Card` | `PaperSurface` — no hard border; grain + `--shadow-soft`, `radius-medium` |
| `Dialog`/`Sheet` | journal-open / page-turn motion; deckle-edge mask |
| `Tabs` | `SeaTabBar` journal tabs (wax-seal active marker) |
| `Progress` | `TideMeter` (shoreline wash) |
| `Tooltip`/`HoverCard` | margin-note “為什麼” |
| `Badge` | **removed** → `StoryMoment` bookmark (no “unlocked” badges) |
| `Toast` (sonner) | slipped-in paper note, literary copy, 6s, no red variants |
| `Skeleton` | faint paper rectangles, no shimmer |
| `Accordion` | folded letter / page fold |

Override shadcn CSS vars (`--background`, `--foreground`, `--primary`, `--radius`…) to the §1 tokens. Disable default ring-blue; focus = `--accent-deep` 2px offset.

---

## 18 · Mobile UI (≤640)

- Single column, 16–20px margins, big touch (≥44px), bottom journal tabs + center inkwell ＋.
- Home: hero ~52vh, then pieces-prose, chapter card, ≤3 invitations.
- Record sheet rises full-height; one question per “page”, swipe to advance.
- Journey map scrolls vertically as a winding path; chapters snap.

## 19 · Tablet UI (641–1024)

- Two-pane where it helps: Journey = **map (left) + chapter detail (right)**; Records = list + entry.
- Left rail (icon+label). Home hero becomes a wide watercolor banner; pieces and chapter sit side-by-side like a spread.
- Comfortable reading column for Reading Room (max 64ch).

## 20 · Desktop UI (≥1025)

- **Book-spread canvas**, centered max-width ~1120; left rail nav; optional **right margin-notes** column for AI explanations/clues.
- Journey as a full illustrated map with parallax clouds; hover reveals chapter previews.
- Generous whitespace; never edge-to-edge dense; data views (labs) become quiet editorial charts, not grids.

---

## 21 · Bridging to the *real* MD.Piece (vanilla-JS PWA)

The shipping app uses `frontend/css/tokens.css` + vanilla JS, with **three stacked theme skins today (modern + ghibli + hanako, the last `!important`-overriding everything)**. To realize this language safely:

1. **Consolidate to one theme.** Retire `hanako`/`ghibli` overrides; create `seaside.css` that *sets the §1 tokens* and becomes the single source of truth. Keep additive `.rw-`/`.mp-` prefixes; verify no regressions screen-by-screen.
2. **Map tokens → existing variable names** (`--surface-1`, `--line`, `--content`, `--primary`, `--space-*`, `--radius-*`, `--font-sans`) so current components inherit the new look with no markup change.
3. **Load fonts** (Noto Serif TC, Zen Old Mincho, Cormorant Garamond, Inter) via `@font-face`/Google Fonts, `font-display:swap`, Noto safety net (no tofu, elder-readable).
4. **Re-language the reward system** in copy/i18n only: points→pieces, level→chapter, badge→story moment (logic already deterministic & gambling-free).
5. **Roll out by surface** (home → journey → record hubs), each behind a verified preview, never a big-bang that breaks production.

## 22 · Accessibility & i18n (non-negotiable)

- **Contrast:** body/UI text uses `--text-primary`/`--text-secondary` (AA+ on shell). Ocean Breeze is decorative; for read text use `--accent-deep`. Verify every pairing ≥4.5:1 (≥3:1 for ≥24px).
- **Elder mode:** `--scale` 1.0/1.25/1.5; layouts reflow, nothing clips; voice input/readout; family proxy.
- **Motion/ίfocus:** honor reduced-motion; visible focus ring (`--accent-deep`); full keyboard path.
- **Bilingual:** every string zh-TW + en, both written as prose (Noto Serif TC / Cormorant), never machine-tone, never AI-tone, never “Achievement Unlocked”.
- **Clinical safety:** show gentle, store clinical; AI/derived values always carry a quiet “為什麼”.

---

### One line to hold it all
> It should feel like a **seaside memory book** that helps patients slowly rebuild the puzzle of their lives — calm, nostalgic, safe, and quietly hopeful.
