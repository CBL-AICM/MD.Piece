# EHR / 臨床變項對應設計（codebook v3 §2 疾病、§5 醫療利用）

> 標 `EHR` 的變項需**醫師端輸入或匯入**。本文件把這些變項對應到 MD.Piece 既有資料表，
> 標出「已可承接 / 需新欄位 / 需新表」，供審核後決定實作範圍。**設計文件，尚未實作。**

---

## 1. 既有可承接的表

| 既有表 | 既有欄位（節選） | 可承接的 codebook 變項 |
|---|---|---|
| `medical_records` | visit_date, diagnosis, prescription, notes | scheduled/attended_visits、visit 基本資訊 |
| `medication_changes` | change_type(start/stop/dose_up…), reason, effective_date | **medication_changes_count**（直接 count）、new_prescriptions |
| `admissions` | admit/discharge_date, diagnosis_icd10, status, ward | **hospitalizations_count**、hospital_los_days、readmission_30d |
| `alerts` | alert_type(`er_visit`…), severity, created_at | **er_visits_count**（count type=er_visit）、unplanned_visits |
| `vital_entries` | metric_id, value, recorded_at | **baseline_sbp/dbp**（metric=BP 的基線值） |
| `doctor_notes` | content, next_focus, tags | 質性／醫師端補充 |

> 結論：**醫療利用(20)** 約 7–8 項可由既有表 **聚合衍生**（純程式碼，規則 5），不需新欄位。

---

## 2. 需新欄位 / 新表

### 2a. 病人層級診斷與臨床基線（§2 疾病）
現況：診斷散在 `medical_records.diagnosis`(text) 與 `admissions.diagnosis_icd10`，**沒有病人層級的結構化診斷與基線檢驗**。建議新表：

```sql
-- docs/migration_clinical_baseline.sql（草案）
CREATE TABLE IF NOT EXISTS clinical_baseline (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    text NOT NULL,
    primary_dx_icd10   text,           -- ICD-10-CM 主診斷
    secondary_dx_icd10 jsonb,          -- 次診斷陣列
    ckd_stage     integer,             -- 1–5
    hba1c         double precision,    -- %
    egfr          double precision,    -- mL/min/1.73m²
    bmi           double precision,
    charlson_score integer,            -- 由共病清單衍生
    recorded_by   text,                -- 醫師 id
    recorded_at   timestamptz NOT NULL DEFAULT now()
);
-- RLS：採硬化作法（ENABLE RLS、無 anon policy、後端 service_role）。
```

對應變項：primary_diagnosis_icd10、secondary_diagnoses_icd10、ckd_stage、baseline_hba1c、
baseline_egfr、baseline_bmi、charlson_index_score（亦可由 G2 共病複選後端衍生）。

> ICD-10 編碼可用本環境的 ICD-10-CM MCP 工具輔助醫師查碼填入。

### 2b. 檢驗 / 醫療利用明細（§5）
若要精細到「檢驗開單數 / 影像數 / 轉診數 / 看診時長」，現況無 `labs`/`orders` 結構化表。
**建議分階段**：第一階段先用既有表能衍生的（住院/急診/用藥調整/回診），
第二階段再評估是否值得為 n=10–12 可行性研究建檢驗明細表（成本/效益）。

---

## 3. 衍生（後端純程式碼，規則 5）

可比照 `surveys.py` 的 `_adherence` / `events.py` 的 `_aggregate`，新增 `GET /research/utilization?patient_id=`：
- `visit_attendance_rate` = attended / scheduled
- `er_visits_count` = count(alerts where type=er_visit, 研究期間)
- `hospitalizations_count` = count(admissions, 研究期間)
- `medication_changes_count` = count(medication_changes, 研究期間)
- `readmission_30d_flag` = 任兩次 admission 間隔 ≤30 天

---

## 4. 實作順序（待審核後）

1. 套 `migration_clinical_baseline.sql` + db.py `_SCHEMAS` 鏡像（§2a）。
2. 醫師後台表單：填 clinical_baseline（ICD-10 用 MCP 查碼輔助）。
3. 新增 `GET /research/utilization` 聚合端點（§3，純程式碼）。
4. （選配）檢驗明細表 §2b 視需求再評估。

> 倫理：ICD-10、檢驗值、醫療利用屬敏感個資；IRB 與知情同意需涵蓋，後台僅 doctor 可讀、匯出去識別化。
