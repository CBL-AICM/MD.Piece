# 衛教專欄內容（Markdown）

此目錄存放給病患看的衛教文章。每篇文章是一個 `.md` 檔，
透過 GitHub Pull Request 進行審稿與校對。

## 工作流程

1. **研究**：使用 Claude / autoresearch / STORM 對主題做深度文獻搜尋。
2. **彙整**：將學術內容改寫成口語、淺顯、安撫為主的患者版本。
3. **撰稿**：在此目錄新增一個 `<slug>.md`，填妥 frontmatter。
4. **審稿**：開 PR，在 GitHub 上逐字檢查內容、來源、語氣。
5. **發布**：合併到 `main` 後 Vercel 自動上線。

---

## ⚠️ 文獻來源強制規範（2026-05 起所有衛教文必須符合）

MD.Piece 是醫療輔助平台，**每一篇衛教文（包含今日精選、每日故事、疾病百科、所有書本章節、AI 生成內容）
都必須附「至少 3 條 Impact Factor > 5 的同儕審查文獻」**。

### A. 強制門檻

| 項目 | 要求 |
| --- | --- |
| Peer-reviewed 期刊文章 | **≥ 3 條** |
| 期刊 Impact Factor | **> 5.0** |
| 台灣／國際權威指引（補充） | 0–3 條（可選） |
| DOI / PMID | 至少前 3 條應附 |

不符規範的文章前端會顯示 ⚠️ 黃色警示，且不會進入「今日精選」輪播池。

### B. 標準格式（嚴格遵守，方便系統解析）

每條 `sources` 條目使用以下字串格式（系統會用正規式抓 IF / 年份 / DOI）：

```
"作者 et al. (YYYY). 文章標題. 期刊名 (IF=XX.X). doi:10.xxxx/yyyy"
```

範例：

```yaml
sources:
  - "Whelton PK, et al. (2018). 2017 ACC/AHA Hypertension Guideline. Hypertension (IF=7.7). doi:10.1161/HYP.0000000000000065"
  - "Williams B, et al. (2018). 2018 ESC/ESH Guidelines for hypertension. European Heart Journal (IF=37.6). doi:10.1093/eurheartj/ehy339"
  - "GBD 2019 Risk Factors Collaborators (2020). Global burden of risk factors. Lancet (IF=98.4). doi:10.1016/S0140-6736(20)30752-2"
  - "中華民國心臟學會：2022 年台灣高血壓治療指引（補充指引）"
```

### C. 可接受的高 IF 期刊（IF > 5，常用清單）

完整清單見 `backend/services/education_content.py` 的 `HIGH_IF_JOURNALS`。

| 領域 | 期刊（IF） |
| --- | --- |
| **一般醫學** | NEJM (158.5) · Lancet (98.4) · BMJ (93.6) · JAMA (63.1) · Nature Medicine (58.7) · Annals of Internal Medicine (19.6) |
| **心血管** | Circulation (37.8) · European Heart Journal (37.6) · JACC (21.7) · Hypertension (7.7) · Stroke (7.8) |
| **內分泌／糖尿病** | Lancet Diabetes Endocrinol (44.0) · Diabetes Care (16.2) · Diabetologia (8.4) |
| **呼吸** | Lancet Respir Med (76.2) · AJRCCM (24.7) · Chest (9.6) |
| **神經** | Lancet Neurology (48.0) · JAMA Neurology (20.4) · Neurology (7.7) |
| **腫瘤** | Lancet Oncology (51.1) · JAMA Oncology (22.5) |
| **腎臟／肝膽腸胃** | Kidney International (14.8) · JASN (13.6) · Gut (23.0) · Hepatology (12.9) |
| **系統性回顧** | Cochrane Database of Systematic Reviews (8.4) |

### D. 嚴格禁止

- ❌ **不要編造 DOI、PMID、期刊名、IF 數值**——稽核會逐條驗證
- ❌ **不要把指引當作 peer-reviewed 文獻計算 IF 門檻**——指引是補充
- ❌ **不確定 IF 數值就改引用 NEJM、Lancet、JAMA 這類確定 > 5 的期刊**
- ❌ **不要省略 IF 註記**——前端會檢查 `IF=XX` 字樣是否存在

---

## Frontmatter 欄位

```yaml
---
title: 文章標題（必填）
slug: 檔名相同的識別字（小寫、連字號）
icd10: I10            # 對應的 ICD-10 prefix；通用文章可省略
dimension: disease_awareness   # 六大維度之一；通用可省略
category: disease     # disease | quick_tip | news（影響每日故事輪播分類）
tags:
  - 高血壓
  - 入門
featured: true         # 是否進入今日精選輪播池（建議精選池 ≥ 30 篇才有日日不同的效果）
summary: 一句話讓患者知道這篇在講什麼（用於卡片預覽）
sources:               # ≥3 條 IF>5 同儕審查文獻 + 可選指引
  - "Whelton PK, et al. (2018). 2017 ACC/AHA Hypertension Guideline. Hypertension (IF=7.7). doi:10.1161/HYP.0000000000000065"
  - "Williams B, et al. (2018). 2018 ESC/ESH Guidelines. European Heart Journal (IF=37.6). doi:10.1093/eurheartj/ehy339"
  - "GBD 2019 Risk Factors Collaborators (2020). Global burden. Lancet (IF=98.4). doi:10.1016/S0140-6736(20)30752-2"
  - "台灣高血壓學會：2022 年治療指引"
  - "WHO Global report on hypertension 2023"
reviewed_at: 2026-05-10   # 最後一次人工審稿日期
---
```

frontmatter 之後是文章本文（Markdown）。建議結構：

- **一句話懂**：第一段就說重點，給趕時間的人。
- **想多了解**：分節說明，配生活化比喻。
- **可以怎麼做**：具體的、可立刻執行的小行動。
- **什麼時候要找醫師**：明確警訊。

## 六大衛教維度

對應 `dimension` 欄位的合法值：

| key | 中文 |
| --- | --- |
| `disease_awareness` | 疾病認知 |
| `symptom_recognition` | 症狀辨識 |
| `medication_knowledge` | 用藥知識 |
| `self_management` | 自我管理 |
| `emergency_response` | 緊急應對 |
| `complication_awareness` | 併發症認知 |

## 撰稿準則（節錄）

- **安撫為先**：患者夠擔心了，你的任務是讓他們安心。
- **淺顯易懂**：避免術語；非用不可就立刻括號解釋。
- **給予希望**：每篇文章都要讓患者感受到「這是可以管理好的」。
- **實用具體**：不要只說「多注意」，給可以立刻做的事。
- **台灣情境**：醫療制度、健保、飲食用台灣的脈絡。
- **實證為本**：所有醫學建議都要對應到上方 sources 中的 IF>5 文獻。

---

## 今日精選 / 每日故事輪播機制（2026-05 起）

| 區塊 | 後端 endpoint | 輪播規則 |
| --- | --- | --- |
| **今日精選** | `GET /education/articles/featured?limit=6` | 每日依 `date.toordinal() % pool_size` 從精選池抽 6 篇 |
| **每日故事 - 疾病故事** | `GET /education/articles/daily` `disease` 分類 | 每日換一篇（用 stride+offset 打散順序） |
| **每日故事 - 健康快訊** | 同上 `quick_tip` 分類 | 同上 |
| **每日故事 - 最新資訊** | 同上 `news` 分類 | RSS 自動更新 |

**要讓使用者真的每天都看到不同**：建議精選池（`featured: true` 文章）保持 **≥ 30 篇**。
若精選池不夠，後端會自動把「有 reviewed_at 且有 sources」的審稿過文章補進輪播池。
