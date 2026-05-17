# MD.Piece — 精華資料包

> **MD.Piece** 是一個 PWA 醫療輔助平台，結合 AI 疾病模擬、活動度預測、與醫病共決決策輔助。
> 本資料包是從完整專案中精選出的「**文件 + 資料 + 報告**」，不含原始程式碼。

---

## 📦 包含什麼？

| 資料夾 | 內容 | 適合什麼時候看 |
|---|---|---|
| **01_cohort報告_v2.5** | 200 患者×16 疾病的完整模擬報告（含 48 個代表性患者 AI 心得） | 想了解模擬出來的患者長什麼樣子 |
| **02_App介入效果_反事實實驗** | 「用 App vs 沒用 App」對照實驗結果 | 想知道 MD.Piece 到底有沒有效 |
| **03_PDF整合版** | 上述兩份合併成的 PDF（6.4 MB） | 列印 / 給長輩 / 簡報附件 |
| **04_資料樣本** | 3200 位虛擬患者的 CSV/JSON 原始資料 | 想自己跑 pandas 分析 |
| **05_疾病模型設定_YAML** | 16 個疾病的醫學參數設定檔 | 想知道每個疾病怎麼建模 |
| **06_產品設計原則** | 「7 條設計憲法」+「3 個策略場景」 | 想了解產品定位與設計哲學 |
| **07_技術文件** | 系統設計、Model Card、簡報大綱、樣本報告 | 想理解模型架構與技術細節 |

---

## 🚀 5 分鐘快速導覽

如果你只能看 5 分鐘，按這個順序：

1. **`02_App介入效果_反事實實驗/intervention_effect.md`** — 結論先看：MD.Piece 平均讓 flare 持續天數 ↓26%、漏藥 ↓21%
2. **`02_App介入效果_反事實實驗/figures/01_flare_reduction_by_disease.png`** — 16 種疾病各自的受益程度（一張圖）
3. **`01_cohort報告_v2.5/05_patient_samples.md`** — 看 48 個虛擬患者的完整 AI 心得，感受「每個人都不一樣」
4. **`06_產品設計原則/CLAUDE_專案說明.md`** — 7 條設計憲法

---

## 🔬 30 分鐘深度導覽

如果有 30 分鐘，再加看：

5. **`01_cohort報告_v2.5/01_cohort_overview.md`** — 3200 患者的整體統計
6. **`01_cohort報告_v2.5/03_model_performance.md`** — AI 預測效能（MAE / Flare recall / precision）
7. **`07_技術文件/02_Model_Card.md`** — 模型卡（限制、偏差、評估指標）
8. **`07_技術文件/01_系統設計.md`** — 系統架構圖與資料流
9. **任意 `05_疾病模型設定_YAML/*.yaml`** — 看一個疾病怎麼用 30 行 YAML 定義

---

## 📊 想自己跑分析？

**最簡單**：用 Excel / Google Sheets 開 `04_資料樣本/patients_summary.csv`
   → 3200 位患者 × 33 欄（人口學 + 社經 + 人格 + 行為 + 模型結果）

**進階**：用 Python pandas
```python
import pandas as pd
df = pd.read_csv('04_資料樣本/patients_summary.csv')

# 例：神經質 vs 主觀放大關聯
df.groupby(pd.cut(df['big5_neuroticism'], 5))['model_mae'].mean()
```

**完整時序**：解壓 `04_資料樣本/cohort_full.json.gz`（49MB → 248MB）
```python
import json, gzip
with gzip.open('cohort_full.json.gz', 'rt') as f:
    cohort = json.load(f)
patient = cohort['diseases']['rheumatoid_arthritis']['patients'][0]
patient['timeseries']         # list[180]，每天 14 個指標
patient['model_predictions']  # list[166]，AI 每天預測 vs 實際
patient['social_profile']     # 7 大類 33 欄位社經/人格
```

`04_資料樣本/sample_16_patients_full.json`（2 MB）是 16 疾病各 1 位完整資料，方便直接點開瀏覽。

---

## 🎯 三個關鍵發現

### 1. 模擬出來的患者真的「不一樣」
- 9 個獨立的不可預測性來源（年齡、亞型、反應者類型、placebo、共病、生活事件、長尾事件、treatment access、**社經/人格/行為**）
- 每位患者隨機抽樣 33 個欄位（婚姻、學歷、收入、保險、抽菸、酒、睡眠、神經質、PHQ-9...）
- 老年（≥70 歲）自動觸發 polypharmacy + 共病疊加 + CRP 反應遲鈍

### 2. AI 模型對個案層級顯著優於 cohort 平均
- 16 種疾病中，多數患者 MAE < 0.15（cohort 平均 0.26）
- Flare 預測準確率最高的是 SLE 89%、SPMS 100%（小樣本下）
- 詳見 `01_cohort報告_v2.5/03_model_performance.md`

### 3. MD.Piece App **真的有用**，但**因人而異**
- 整體 flare 持續天數 ↓25.9%、漏藥天數 ↓21.3%
- **痛風 ↓58%、僵直性脊椎炎 ↓50%** 受益最大（行為可避免 trigger 多）
- **IPF / SSc / IgG4 ≈ 0%** 受益最小（不可逆病程，App 改不了病理）
- **App 縮減健康不平等**：低收入族群 -10%、PHQ-9≥10 -13%、老年高家屬支持 -9%
- 老年獨居無家屬支持者效益最小（-2.4%）→ 凸顯「家屬模式」必要性

---

## 📐 資料規模

| 項目 | 數量 |
|---|---|
| 疾病 | 16 種風濕免疫 / 過敏氣喘 / 退化性疾病 |
| 虛擬患者 | 3,200 位（每疾病 200 位） |
| 模擬天數 | 180 天 / 患者 |
| 不可預測性來源 | 9 個獨立維度 |
| Patient-day 總數 | 576,000（v2.5 cohort）+ 1,152,000（counterfactual） |
| AI 預測點 | ~520,000 |
| 個別 AI 心得 | 3,200 條（每條 11 行） |

---

## 🛠 完整 repo 在哪？

GitHub（如果有權限）：https://github.com/CBL-AICM/MD.Piece
- 完整 Python 程式碼（`md_piece/`、`ml/`、`scripts/`）
- PWA 前端（`pwa/`、`frontend/`）
- E2E 測試（`tests/e2e/`）
- 部署設定（Vercel + Supabase）

本精華包不含程式碼，只包含**人類可讀**的文件與資料。

---

*產生時間：2026-05-17 · MD.Piece v2.5 + counterfactual extension*
