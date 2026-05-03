# 衛教專欄內容（Markdown）

此目錄存放給病患看的衛教文章。每篇文章是一個 `.md` 檔，
透過 GitHub Pull Request 進行審稿與校對。

## 工作流程

1. **研究**：使用 Claude / autoresearch / STORM 對主題做深度文獻搜尋。
2. **彙整**：將學術內容改寫成口語、淺顯、安撫為主的患者版本。
3. **撰稿**：在此目錄新增一個 `<slug>.md`，填妥 frontmatter。
4. **審稿**：開 PR，在 GitHub 上逐字檢查內容、來源、語氣。
5. **發布**：合併到 `main` 後 Vercel 自動上線。

## Frontmatter 欄位

```yaml
---
title: 文章標題（必填）
slug: 檔名相同的識別字（小寫、連字號）
icd10: I10            # 對應的 ICD-10 prefix；通用文章可省略
dimension: disease_awareness   # 六大維度之一；通用可省略
tags:
  - 高血壓
  - 入門
featured: true         # 是否在首頁推送
summary: 一句話讓患者知道這篇在講什麼（用於卡片預覽）
sources:               # 文獻 / 來源清單，會原樣顯示在文末
  - 台灣高血壓學會 2022 治療指引
  - WHO Global report on hypertension 2023
reviewed_at: 2026-05-03   # 最後一次人工審稿日期
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
