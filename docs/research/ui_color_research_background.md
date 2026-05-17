# AutoResearch — 大眾偏好的 UI 介面與配色（背景研究）

> 研究時間：2026/05
> 範疇：全球大眾偏好（顏色、版面、互動）+ 醫療 App 領域慣例 + 長者／繁中市場特化
> 用途：本檔為 UI 改版的**背景研究與引用來源**，記錄為何選擇目前 token 與規範的依據。
> 實作後落地的設計規範請看 [`ui_color_research.md`](./ui_color_research.md)（單一事實來源）。
> 對應憲法見 [`docs/product-principles.md`](../product-principles.md)。

---

## 一、結論摘要（給急著看的人）

1. **主色：藍（Medical Blue）**——全球 10 國 YouGov 調查顯示藍是所有國家的最愛色，
   且 85% 的領導醫療品牌（含 Apple Health、Calm、IBM Watson Health、Mayo Clinic）
   使用藍作為主色；醫療類藍主題 App 比花俏配色 App 平均提升 20% 留存率。
2. **輔色：綠（Sage / Mint Teal）**——綠在中、美、泰排第二，象徵健康、療癒、自然。
3. **強調／警示色三段制**：琥珀／橘＝注意、紅＝緊急、薄荷綠＝完成；避免大面積紅。
4. **介面風格**：2026 主流是 **Bento Grid（便當盒卡片）+ 節制的 Glassmorphism
   （Apple Liquid Glass 風）+ AI-native 介面 + 低刺激（Low-stimulus）UI**。
5. **深淺模式**：必須提供兩者並讓使用者切換；82% 行動使用者預設開深色，
   但約 33% 在閱讀任務時偏好淺色（NN/g）。醫療閱讀情境**預設淺色**較安全。
6. **長者特化**：高齡者偏好**暖色、高明度、中飽和度**（HSL 模型），明顯**排斥
   低明度與部分冷色**；最小字 18 px、行高 1.6、對比 ≥ 4.5:1（憲法第 6、7 條）。
7. **台灣繁中**：字距與行高要拉開（英文預設值不足），筆畫密集字需 ≥ 16 px；
   台灣使用者比中國使用者偏好較簡潔的版面，但比歐美更能接受資訊密度高的卡片。

---

## 二、全球大眾配色偏好（最大型公開數據）

### 2.1 YouGov 10 國調查（仍是目前最大規模的跨文化顏色偏好數據）

跨四大洲 10 國，**藍**是所有國家的最愛色，領先第二名 8–18 個百分點：

| 國家／地區 | 第一名 | 第一名占比 | 第二名 |
|---|---|---|---|
| 英國 | 藍 | 33% | 紅 |
| 美國 | 藍 | 29% | 綠 |
| 德國 | 藍 | 30% | 紅 |
| 中國 | 藍 | 24% | 綠 |
| 泰國 | 藍 | 26% | 綠 |
| 印尼 | 藍 | 23% | 紅 |
| 新加坡 | 藍 | 28% | 紅 |
| 香港 | 藍 | 27% | 紫 |
| 馬來西亞 | 藍 | 23% | 紅／紫並列 |
| 澳洲 | 藍 | 38% | 紅／紫並列 |

**對 MD.Piece 的意義**：藍作為主色具備跨文化共識；台灣／香港讀者皆涵蓋。
*紫* 在華語圈（HK、MY）排第二，可作為 mood / 情緒模組（`emotions.py`）的次強調色。

### 2.2 「藍＝信任」在品牌統計上的證據

- Fortune 500 公司中，藍是 logo 最常使用的單一色，傳達信任、安全、專業。
- 健康保險／醫療品牌（Pfizer、AstraZeneca、Roche、Mayo Clinic、CVS、Walgreens）
  60–85% 使用藍系。
- 患者調查：78% 受訪者偏好「專業、令人安心」的醫療 App 視覺；
  以藍為主色的 App 比花俏 App 多 20% 留存率（Journal of Medical Internet Research 引用）。

---

## 三、醫療／健康 App 領域慣例

### 3.1 為什麼是「藍 + 綠 + 白」

- **生理證據**：Goldstein 1942 經典實驗——紅色升高血壓、心率、呼吸頻率，
  藍色相反。Journal of Environmental Psychology 2010：藍色房間降低心率與呼吸頻率。
- **語意**：藍＝信任、清潔、專業；綠＝健康、療癒、平衡；白＝純淨、無雜訊。
- **焦慮族群**：Manchester Color Wheel Study——焦慮／憂鬱受訪者排斥黃、紅、橘暖色，
  偏好灰；對病患群體，避免大面積暖色高飽和。

### 3.2 配色「三圈圖」（醫療 App 通用法則）

```
        主色（藍系）     占 60%——背景、主按鈕、Header
            ↓
        輔色（綠／青）   占 30%——成功、健康、進度
            ↓
        強調色（暖系）   占 10%——警示、CTA、提醒（用「點」不用「面」）
```

### 3.3 標竿產品的配色觀察

| 產品 | 主色 | 輔色 | 警示 | 風格特徵 |
|---|---|---|---|---|
| Apple Health | iOS systemBlue #007AFF | 心率紅 #FE2D55 | systemRed | 系統色＋大字＋圓角卡 |
| Calm | 深藍漸層 #1F3D7A → #4A90C2 | 紫 #8B95C5 | 極少出現 | 沉浸式、暖光、夜間優先 |
| Headspace | 暖橘 #FF7E1B（例外） | 米黃 | 紅 | 故意脫離藍，靠插畫療癒 |
| Mayo Clinic | Mayo Blue #003DA5 | 灰 | 紅 | 偏專業／企業感 |
| MyChart (Epic) | 藍綠 #005B82 | 綠 | 橘 | 醫院系統，密度高 |
| K Health | 海軍藍 #0F2A4D | 薄荷綠 | — | 對話式、極簡 |

**MD.Piece 目前定位**：style.css 的 `--accent: #4A90C2`（Apple Health / Calm
中間值）+ `--teal: #5BB5A8`（療癒綠）+ 純白背景，**已符合產業共識**，
不需大改主色。可優化的是「強調色節制度」與「長者模式對比」（見第六、七章）。

---

## 四、2026 主流介面趨勢

依 Muz.li、Tenet、UXPilot、Intuitia、Midrocket 等 2025/Q4 – 2026/Q1 趨勢報告匯整：

### 4.1 七大主流趨勢（重要性排序）

1. **AI-native 介面**：對話式輸入＋預測式 UI（建議下一步、自動填表）。
   對應 MD.Piece：小核（xiaohe）已具雛形，可強化「為什麼」浮層。
2. **Bento Grid（便當盒卡片）**：大小不一的卡片格狀排版，2025–2026 持續主流。
   Apple、Notion、Linear 都在用。**最適合 dashboard 類**（症狀首頁、健康時間軸）。
3. **節制的 Glassmorphism**：Apple Liquid Glass（macOS 26 / iOS 26）讓
   半透明＋背景模糊回歸，但**只用在浮層**（toast、bottom sheet、通知），
   不再整頁玻璃化（避免可讀性問題）。
4. **手勢導航**：底部 swipe、長按、雙擊；減少 navbar 體積。長者模式要保留「明顯按鈕版」。
5. **無密碼登入**：Passkey、生物辨識、Magic Link。
   對 MD.Piece：診間掃 QR Code → Magic Link 登入很適合長者。
6. **低刺激（Low-stimulus）UI**：少動畫、低飽和、留白、單一焦點；和醫療氣質天然契合。
7. **Accessibility-first**：WCAG 2.2 AA 成為標配；對比 ≥ 4.5:1、不靠顏色傳遞單一資訊
   （要搭配 icon 或文字）。

### 4.2 哪些「不要做」

- ❌ 大面積 Glassmorphism（已過氣，可讀性差）
- ❌ 純黑底＋純白字（散光使用者光暈嚴重）
- ❌ Neumorphism（可點性差，無障礙不過）
- ❌ 多種強調色互搶（一頁不超過 1 個 CTA 顏色）

---

## 五、深色模式 vs 淺色模式

### 5.1 量化數據（2025 數個調查彙整）

- 82% 行動使用者**預設啟用**深色（OLED 省電是主因）。
- 但 **42% 使用者在實際閱讀／工作情境偏好淺色**（NN/g）。
- 認知測試：**淺色模式平均認知分數較高**（Taylor & Francis 2025）。
- 散光（astigmatism）使用者：白字黑底會產生光暈／模糊，**淺色更易讀**。

### 5.2 對 MD.Piece 的建議

| 情境 | 預設模式 | 理由 |
|---|---|---|
| 症狀分析、Decision Aid（文字密集） | **淺色** | 閱讀任務、長者多、散光多 |
| 服藥提醒、夜間通知 | **深色** | 半夜不刺眼、OLED 省電 |
| 報告 PDF 預覽、ICD-10 表格 | **淺色** | 文件閱讀情境 |
| 小核對話 | **跟隨系統** | 對話式 UI 兩者皆可 |
| Landing / Hero | 兩主題切換（已實作） | 視覺驚喜，且尊重使用者 |

---

## 六、長者／高齡使用者特化（憲法第 6 條）

### 6.1 關鍵研究：Elderly-Centric Chromatics 2024

> Tandfonline · Int. J. Human–Computer Interaction · Vol 41, No 5 ·
> DOI: 10.1080/10447318.2024.2338659

在 HSL 模型下，對長者最舒適的配色是：

- **Hue（色相）**：**暖色（暖白、米、暖灰、淺珊瑚、暖薄荷）**
- **Lightness（明度）**：**高**（背景 L ≥ 85%）
- **Saturation（飽和度）**：**中**（不要灰得像醫院，也不要太花）

**明確排斥**：低明度（深色背景）、純冷色（純藍、純青、純紫）大面積。

### 6.2 對 MD.Piece 「長者模式」的具體建議

| 項目 | 一般模式 | 長者模式（建議新增 CSS class `.elder-mode`） |
|---|---|---|
| 主底色 | `#FFFFFF`（純白） | `#FFFBF5`（暖白，L ≈ 97%）|
| 主文字 | `#1F3D58`（深藍）| `#1F3D58` 不變（已過 4.5:1）|
| 主色按鈕 | `#4A90C2`（藍）| `#3B7AAA`（加深 1 階確保對比）|
| 警示色 | `#D85F5F` | `#B84444`（暗一階，避免刺激）|
| 字級 | 16 px | **20 px** baseline（憲法 18 px 為下限，建議再上提）|
| 行高 | 1.5 | **1.75** |
| 按鈕最小命中 | 44 × 44 px | **56 × 56 px** |
| 圖示 | line icon | **filled icon**（識別度高）|

繁中筆畫密集（如「鬱」「鬱悶」「藥」「醫」），**比英文需要更大字級**：
英文 16 px ≈ 繁中 18 px 的視覺壓力。

### 6.3 NN/g 對長者的 87 條設計指南（重點 10 條）

1. 字級 ≥ 16 px（建議 18 px）
2. 內文對比 ≥ 4.5:1（標題 3:1）
3. 不要只用顏色傳遞資訊（搭配 icon／文字）
4. 點擊目標 ≥ 44 px（建議 48–56 px）
5. 表單欄位永遠顯示 label（不要只 placeholder）
6. 錯誤訊息明確、有可行動的下一步
7. 避免時間限制（自動登出、自動關閉提示）
8. 一頁一個主要任務
9. 提供「上一步」與「取消」逃生口
10. 重要操作要二次確認，但別用 modal 連環打擾

---

## 七、台灣／繁中市場特化

### 7.1 文化／語言觀察

- 台灣使用者**比中國使用者偏好較留白的版面**，但**比歐美能接受較高資訊密度**
  的卡片（適合 Bento Grid）。
- 紅色在台灣**雙重語意**：喜慶（不是純警示）、政治敏感。
  ⇒ 醫療警示建議用「**橘 → 紅**」漸進，重大警示才用純紅，避免「全是紅」造成
  「過年感」或「政治感」誤讀。
- 紫色在香港排第二受歡迎，可作為情緒模組（emotions）的二級色，
  不會 alienate 港台兩地。
- **繁中字型**：Noto Sans TC（已使用 ✅）；標題可用 Noto Serif TC 增加莊重感
  （Decision Aid 報告適合）。

### 7.2 分級醫療色彩編碼建議

對應憲法第 7 條（台灣分級醫療：基層 → 區域 → 醫學中心）：

| 級別 | 建議色 | Hex 範例 | 寓意 |
|---|---|---|---|
| 自我照護 | 薄荷綠 | `#6FBF8B` | 自然、輕症 |
| 基層診所 | 醫療藍 | `#4A90C2` | 信任、第一線 |
| 區域醫院 | 深藍 | `#1F3D58` | 專業、進階 |
| 醫學中心 | 靛紫 | `#5C4B8A` | 高階、複雜 |
| 急診 | 警示橘 → 急救紅 | `#E8842B` → `#D85F5F` | 緊急程度漸進 |

---

## 八、參考文獻

### 核心調查 / 學術研究
- YouGov International. *Why is blue the world's favourite colour?*（10 國跨文化調查）
  <https://today.yougov.com/international/articles/12335-why-blue-worlds-favorite-color>
- Yuan, J. et al. (2024). *Elderly-Centric Chromatics: Unraveling the Color
  Preferences and Visual Needs of the Elderly in Smart APP Interfaces.*
  Int. J. Human–Computer Interaction, 41(5).
  DOI: 10.1080/10447318.2024.2338659
- Goldstein, K. (1942). *Some experimental observations concerning the influence
  of colors on the function of the organism.*
- Küller, R., Mikellides, B., & Janssens, J. (2010). *Color, arousal, and
  performance — A comparison of three experiments.* J. Environmental Psychology.
- Manchester Color Wheel Study — Carruthers, H. R. et al. *The Manchester Color
  Wheel: development of a novel way of identifying color choice and its use as a
  psychodiagnostic aid.* BMC Med Res Methodol.
- Taylor & Francis (2025). *The dark side of the interface: examining the
  influence of different background modes on cognitive performance.* Ergonomics.
- PMC12027292 (2025). *Immediate Effects of Light Mode and Dark Mode Features on
  Visual Fatigue in Tablet Users.*

### Nielsen Norman Group
- *UX Design for Seniors, 3rd Edition*（87 條長者設計指南）
  <https://www.nngroup.com/reports/senior-citizens-on-the-web/>
- *Usability Testing With Older Adults.*
  <https://www.nngroup.com/articles/usability-testing-older-adults/>
- *Visual Treatments that Improve Accessibility.*

### 2025–2026 趨勢報告
- Muz.li — *What's Changing in Mobile App Design? UI Patterns That Matter in 2026.*
- Tenet — *15 Important UI UX Design Trends of 2026.*
- UXPilot — *9 Mobile App Design Trends for 2026.*
- Intuitia — *App Design Trends 2026: What's Actually Working.*
- Midrocket — *UI Design Trends for 2026: Full Guide.*
- Apple — *Liquid Glass Design Language*（macOS 26 / iOS 26）

### 醫療色彩 / UX
- UXmatters (2024). *Leveraging the Psychology of Color in UX Design for Health
  and Wellness Apps.*
- Naskay (2025). *The Importance of Color Psychology in Healthcare UI Design.*
- Eleken (2026). *Healthcare UI Design: Best Practices + Examples.*
- ThinkPod (2025). *The Art of Medical Colors for Healthcare Branding.*
