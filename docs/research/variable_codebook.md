# MD.Piece 可行性研究 — 變項字典 / Codebook（v3，160 變項）

> **狀態：草案，待審核。** 本文件是「設計文件」，尚未實作。請審閱後再決定哪些進
> `seed_study_surveys.py`（自填問卷）、哪些需新建 telemetry 捕捉、哪些走病歷/醫師端輸入。
>
> **研究 study key（沿用）**：`mdpiece_feasibility_v2`
> **總變項數**：160 ＝ 人口學 20 ＋ 疾病資料 30 ＋ 使用行為 40 ＋ 遺失與錯誤事件 30 ＋ 醫療利用 20 ＋ 結果指標 20

---

## 0. 圖例（Legend）

**資料來源 Source**

| 代碼 | 意義 | 在 MD.Piece 的落點 |
|---|---|---|
| `SR` | 自填問卷（self-report） | 既有問卷引擎（`surveys` / `survey_responses`），可直接 seed |
| `TEL` | App 遙測 / 事件日誌（telemetry） | **多數需新建**事件日誌表（見 §7）；少數已存在（symptom/vital/sleep entries） |
| `EHR` | 病歷 / 臨床（醫師端輸入或匯入） | 既有 `doctor_notes` / `medication_changes` / `admissions`，部分需新欄位 |
| `DRV` | 衍生變項（由上述計算） | 後端純程式碼計算（規則 5），不丟 LLM |

**型別 Type**：`cat` 類別｜`ord` 順序｜`cont` 連續｜`bin` 二元｜`cnt` 計數｜`dt` 日期時間｜`txt` 自由文字｜`multi` 複選

**時點 Timepoint**：`D0` 基線｜`D14`｜`D28`｜`FU48` 回診後 48h｜`daily` 每日｜`cont` 連續累計｜`event` 事件觸發

---

## 1. 人口學 Demographics（20）— 主要 D0 自填

| # | 變項名稱 | 中文標籤 | 型別 | 編碼 / 值域 | 來源 | 時點 |
|---|---|---|---|---|---|---|
| 1 | `participant_code` | 受試者代號 | cat | P01–P12 | SR/admin | D0 |
| 2 | `birth_year` | 出生年（西元） | cnt | 1900–2010 | SR | D0 |
| 3 | `age_years` | 年齡（歲） | cont | 由出生年推算 | DRV | D0 |
| 4 | `sex` | 生理性別 | cat | 男/女/其他·不願透露 | SR | D0 |
| 5 | `education_level` | 教育程度 | ord | 國小/國中/高中職/大學專科/研究所以上 | SR | D0 |
| 6 | `marital_status` | 婚姻狀態 | cat | 未婚/已婚/離異/喪偶 | SR | D0 |
| 7 | `living_arrangement` | 居住狀態 | cat | 獨居/與家人同住/機構 | SR | D0 |
| 8 | `household_size` | 同住人數 | cnt | 0–10+ | SR | D0 |
| 9 | `employment_status` | 就業狀態 | cat | 全職/兼職/退休/無業/家管 | SR | D0 |
| 10 | `occupation_category` | 職業類別 | cat | 標準職業分類簡版 | SR | D0 |
| 11 | `monthly_income_band` | 家庭月收入級距 | ord | <3萬/3–6萬/6–10萬/>10萬/不願答 | SR | D0 |
| 12 | `insurance_status` | 健保身分 | cat | 一般/重大傷病卡/低收入戶 | SR/EHR | D0 |
| 13 | `residence_urbanicity` | 居住地城鄉 | cat | 都會/鄉鎮/偏遠 | SR | D0 |
| 14 | `preferred_language` | 慣用語言 | cat | 國語/台語/客語/其他 | SR | D0 |
| 15 | `caregiver_available` | 照顧者協助 3C | ord | 否/偶爾/經常 | SR | D0 |
| 16 | `caregiver_relationship` | 照顧者關係 | cat | 配偶/子女/其他親屬/看護/無 | SR | D0 |
| 17 | `smartphone_proficiency` | 智慧型手機熟練度 | ord | 1–5 | SR | D0 |
| 18 | `internet_access_home` | 家中網路可及性 | cat | 有 Wi-Fi/僅行動數據/無 | SR | D0 |
| 19 | `device_os` | 裝置作業系統 | cat | iOS/Android/其他 | TEL/SR | D0 |
| 20 | `prior_health_app_use` | 曾用過健康 App | bin | 是/否 | SR | D0 |

> 多數沿用既有 A 背景問卷（a1–a10），可擴充。

---

## 2. 疾病資料 Disease data（30）— SR ＋ EHR

> 共病以 **Charlson Comorbidity Index（CCI）** 清單＋計分為骨幹（自填與病歷一致性極佳）。
> 主診斷以 **ICD-10-CM** 編碼。

| # | 變項名稱 | 中文標籤 | 型別 | 編碼 / 值域 | 來源 | 時點 |
|---|---|---|---|---|---|---|
| 1 | `primary_diagnosis_text` | 主要慢性病診斷 | txt | — | SR/EHR | D0 |
| 2 | `primary_diagnosis_icd10` | 主診斷 ICD-10 | cat | ICD-10-CM | EHR | D0 |
| 3 | `secondary_diagnoses_icd10` | 次診斷 ICD-10 | multi | ICD-10-CM | EHR | D0 |
| 4 | `disease_duration_years` | 病程長度（年） | ord | <1/1–5/5–10/>10 | SR | D0 |
| 5 | `age_at_diagnosis` | 診斷時年齡 | cont | 0–110 | SR | D0 |
| 6 | `num_chronic_conditions` | 慢性病共病數 | cnt | 0–10+ | SR/EHR | D0 |
| 7 | `comorbidity_checklist` | 共病清單（CCI 19 項） | multi | CCI 條件 | SR | D0 |
| 8 | `charlson_index_score` | Charlson 共病指數 | cnt | 0–37 | DRV | D0 |
| 9 | `hypertension_flag` | 高血壓 | bin | 是/否 | SR/EHR | D0 |
| 10 | `diabetes_t2_flag` | 第二型糖尿病 | bin | 是/否 | SR/EHR | D0 |
| 11 | `copd_flag` | 慢性阻塞性肺病 | bin | 是/否 | SR/EHR | D0 |
| 12 | `ckd_stage` | 慢性腎病分期 | ord | 無/1–5 | SR/EHR | D0 |
| 13 | `cvd_flag` | 心血管疾病 | bin | 是/否 | SR/EHR | D0 |
| 14 | `dyslipidemia_flag` | 血脂異常 | bin | 是/否 | SR/EHR | D0 |
| 15 | `baseline_sbp` | 基線收縮壓 | cont | mmHg | EHR/TEL | D0 |
| 16 | `baseline_dbp` | 基線舒張壓 | cont | mmHg | EHR/TEL | D0 |
| 17 | `baseline_hba1c` | 基線糖化血色素 | cont | % | EHR | D0 |
| 18 | `baseline_egfr` | 基線 eGFR | cont | mL/min/1.73m² | EHR | D0 |
| 19 | `baseline_bmi` | 基線 BMI | cont | kg/m² | SR/EHR | D0 |
| 20 | `smoking_status` | 抽菸狀態 | cat | 從不/已戒/目前 | SR | D0 |
| 21 | `alcohol_use` | 飲酒習慣 | cat | 從不/偶爾/經常 | SR | D0 |
| 22 | `num_regular_medications` | 長期用藥種類數 | cnt | 0–20+ | SR/EHR | D0 |
| 23 | `polypharmacy_flag` | 多重用藥（≥5 種） | bin | 是/否 | DRV | D0 |
| 24 | `medication_classes` | 用藥類別 | multi | 降壓/降糖/降脂/抗凝… | SR/EHR | D0 |
| 25 | `medication_adherence_baseline` | 基線服藥依從 | ord | 單題/Morisky 簡版 | SR | D0 |
| 26 | `baseline_symptom_burden` | 基線症狀負荷 | ord | 0–10 | SR | D0 |
| 27 | `disease_severity_selfrated` | 自評疾病嚴重度 | ord | 1–5 | SR | D0 |
| 28 | `hospitalization_history_12m` | 過去 12 月住院次數 | cnt | 0–10+ | SR/EHR | D0 |
| 29 | `er_visits_history_12m` | 過去 12 月急診次數 | cnt | 0–10+ | SR/EHR | D0 |
| 30 | `family_history_flag` | 慢性病家族史 | bin | 是/否 | SR | D0 |

---

## 3. 使用行為 Usage behavior（40）— 多數 TEL / DRV

> 依 **Perski & Michie 2017** engagement 框架：分「**行為面**（usage logs）」與「**體驗面**（自評）」。
> 行為面變項**需新建事件日誌**（見 §7），少數（symptom/vital/sleep/medication entries）已存在。

| # | 變項名稱 | 中文標籤 | 型別 | 編碼 / 值域 | 來源 | 時點 |
|---|---|---|---|---|---|---|
| 1 | `first_launch_at` | 首次啟用時間 | dt | — | TEL | event |
| 2 | `onboarding_completed` | 完成新手導引 | bin | 是/否 | TEL | event |
| 3 | `onboarding_duration_sec` | 導引耗時 | cont | 秒 | TEL | event |
| 4 | `total_active_days` | 活躍天數 | cnt | 0–28 | TEL | cont |
| 5 | `active_days_rate` | 活躍天數率 | cont | 0–1（活躍/可用天數） | DRV | cont |
| 6 | `days_since_last_use` | 距上次使用天數 | cnt | — | DRV | cont |
| 7 | `total_sessions` | 總工作階段數 | cnt | — | TEL | cont |
| 8 | `sessions_per_active_day` | 每活躍日階段數 | cont | — | DRV | cont |
| 9 | `mean_session_duration_sec` | 平均階段時長 | cont | 秒 | TEL | cont |
| 10 | `median_session_duration_sec` | 中位階段時長 | cont | 秒 | DRV | cont |
| 11 | `total_time_in_app_min` | 累計使用時間 | cont | 分 | TEL | cont |
| 12 | `longest_streak_days` | 最長連續使用 | cnt | 天 | DRV | cont |
| 13 | `current_streak_days` | 目前連續使用 | cnt | 天 | DRV | cont |
| 14 | `weekly_active_rate` | 每週活躍率 | cont | 0–1 | DRV | cont |
| 15 | `usage_time_of_day` | 主要使用時段 | cat | 晨/午/晚/夜 | DRV | cont |
| 16 | `daily_log_count` | 每日記錄筆數 | cnt | — | TEL | daily |
| 17 | `daily_log_completion_rate` | 每日記錄完成率 | cont | 0–1（已填/應填日） | DRV | cont |
| 18 | `symptom_entries_count` | 症狀記錄筆數 | cnt | — | TEL | cont |
| 19 | `vital_entries_count` | 生理值記錄筆數 | cnt | — | TEL | cont |
| 20 | `sleep_records_count` | 睡眠記錄筆數 | cnt | — | TEL | cont |
| 21 | `medication_log_count` | 服藥打卡筆數 | cnt | — | TEL | cont |
| 22 | `emotion_entries_count` | 情緒記錄筆數 | cnt | — | TEL | cont |
| 23 | `reminder_response_rate` | 提醒回應率 | cont | 0–1（回應/發送） | DRV | cont |
| 24 | `reminder_response_latency_min` | 提醒回應延遲中位數 | cont | 分 | DRV | cont |
| 25 | `notification_opt_in` | 開啟推播 | bin | 是/否 | TEL | event |
| 26 | `feature_breadth_used` | 使用功能廣度 | cnt | 不重複功能數 | DRV | cont |
| 27 | `risk_dashboard_views` | 風險儀表板瀏覽 | cnt | — | TEL | cont |
| 28 | `shap_explanation_views` | 主要貢獻特徵瀏覽 | cnt | — | TEL | cont |
| 29 | `previsit_summary_generated` | 就診前摘要生成 | cnt | — | TEL | cont |
| 30 | `previsit_summary_shared` | 摘要分享/出示 | cnt | — | TEL | event |
| 31 | `education_content_views` | 衛教內容瀏覽 | cnt | — | TEL | cont |
| 32 | `xiaohe_chat_messages` | 小核對話則數 | cnt | — | TEL | cont |
| 33 | `self_assessment_completions` | 自我評估完成數 | cnt | — | TEL | cont |
| 34 | `timeline_views` | 健康時間軸瀏覽 | cnt | — | TEL | cont |
| 35 | `data_export_actions` | 資料匯出次數 | cnt | — | TEL | cont |
| 36 | `push_received_count` | 推播收到數 | cnt | — | TEL | cont |
| 37 | `push_opened_count` | 推播開啟數 | cnt | — | TEL | cont |
| 38 | `app_version` | App 版本 | cat | semver | TEL | event |
| 39 | `engagement_experiential_sr` | 自評投入感（體驗面） | ord | 1–7（單題） | SR | D14/D28 |
| 40 | `intended_use_adherence_ratio` | 對「預期使用」之依從比 | cont | 0–1（實際/協定） | DRV | cont |

---

## 4. 遺失與錯誤事件 Loss & error events（30）— 資料品質 / 缺漏 / 技術錯誤

> 缺漏機制參考 **Courvoisier 2012**（EMA 順從度隨時間衰減、缺漏常**非隨機**，分析需納入缺漏預測因子）。
> 資料品質依完整性 / 正確性 / 時效性 / 一致性四維度。多為 TEL/DRV。

| # | 變項名稱 | 中文標籤 | 型別 | 編碼 / 值域 | 來源 | 時點 |
|---|---|---|---|---|---|---|
| 1 | `expected_observations_total` | 應觀測總數 | cnt | — | DRV | cont |
| 2 | `observed_observations_total` | 實得觀測總數 | cnt | — | DRV | cont |
| 3 | `overall_missing_rate` | 整體缺漏率 | cont | 0–1 | DRV | cont |
| 4 | `item_missing_rate` | 題項缺漏率 | cont | 0–1（逐問卷） | DRV | per-survey |
| 5 | `completion_rate_by_timepoint` | 各時點完成率 | cont | 0–1（D0/D14/D28/FU48） | DRV | per-tp |
| 6 | `dropout_flag` | 中途退出 | bin | 是/否 | DRV | cont |
| 7 | `dropout_timepoint` | 退出時點 | cat | D0/D14/D28/FU48 | DRV | event |
| 8 | `days_to_dropout` | 退出前天數 | cnt | — | DRV | event |
| 9 | `mnar_indicator` | 缺漏非隨機指標 | bin | 順從度衰減型樣 | DRV | cont |
| 10 | `intermittent_missing_count` | 間歇缺漏次數 | cnt | — | DRV | cont |
| 11 | `daily_log_missed_days` | 漏填每日記錄天數 | cnt | — | DRV | cont |
| 12 | `max_consecutive_missed_days` | 最長連續漏填 | cnt | 天 | DRV | cont |
| 13 | `reminder_ignored_count` | 忽略提醒次數 | cnt | — | TEL | cont |
| 14 | `app_crash_count` | App 崩潰次數 | cnt | — | TEL | cont |
| 15 | `app_error_count` | 非崩潰錯誤次數 | cnt | — | TEL | cont |
| 16 | `api_request_failures` | API 請求失敗數 | cnt | 4xx/5xx | TEL | cont |
| 17 | `sync_failure_count` | 同步失敗次數 | cnt | — | TEL | cont |
| 18 | `offline_event_count` | 離線事件次數 | cnt | — | TEL | cont |
| 19 | `login_failure_count` | 登入失敗次數 | cnt | — | TEL | cont |
| 20 | `session_timeout_count` | 階段逾時次數 | cnt | — | TEL | cont |
| 21 | `data_submission_failures` | 資料送出失敗 | cnt | — | TEL | cont |
| 22 | `page_load_error_count` | 頁面載入錯誤 | cnt | — | TEL | cont |
| 23 | `out_of_range_value_count` | 超出合理範圍值數 | cnt | 例：BP/血糖異常 | DRV | cont |
| 24 | `duplicate_entry_count` | 重複輸入次數 | cnt | — | DRV | cont |
| 25 | `inconsistent_response_count` | 矛盾作答次數 | cnt | — | DRV | cont |
| 26 | `straightlining_flag` | 一直線作答（敷衍） | bin | 是/否 | DRV | per-survey |
| 27 | `too_fast_completion_flag` | 作答過快 | bin | 低於門檻 | DRV | per-survey |
| 28 | `self_reported_input_error` | 自陳輸入錯誤 | cnt | — | SR | event |
| 29 | `correction_edit_count` | 事後修正次數 | cnt | — | TEL | cont |
| 30 | `data_quality_composite` | 資料品質綜合分 | cont | 完整×正確×時效 | DRV | D28 |

---

## 5. 醫療利用 Healthcare utilization（20）— SR ＋ EHR

| # | 變項名稱 | 中文標籤 | 型別 | 編碼 / 值域 | 來源 | 時點 |
|---|---|---|---|---|---|---|
| 1 | `scheduled_visits_count` | 排定回診次數 | cnt | — | EHR/SR | cont |
| 2 | `attended_visits_count` | 實際回診次數 | cnt | — | EHR/SR | cont |
| 3 | `visit_attendance_rate` | 回診出席率 | cont | 0–1 | DRV | cont |
| 4 | `no_show_count` | 爽約次數 | cnt | — | EHR | cont |
| 5 | `unplanned_visits_count` | 計畫外就診次數 | cnt | — | SR/EHR | cont |
| 6 | `er_visits_count` | 急診次數（研究期間） | cnt | — | SR/EHR | cont |
| 7 | `hospitalizations_count` | 住院次數（研究期間） | cnt | — | SR/EHR | cont |
| 8 | `hospital_los_days` | 住院總天數 | cont | 天 | EHR | event |
| 9 | `readmission_30d_flag` | 30 天再入院 | bin | 是/否 | EHR | event |
| 10 | `outpatient_specialties_count` | 就診專科數 | cnt | — | EHR | cont |
| 11 | `telehealth_visits_count` | 遠距/視訊就診次數 | cnt | — | EHR/SR | cont |
| 12 | `medication_changes_count` | 用藥調整次數 | cnt | 起/停/增/減 | EHR | cont |
| 13 | `new_prescriptions_count` | 新增處方數 | cnt | — | EHR | cont |
| 14 | `lab_tests_ordered_count` | 檢驗開單數 | cnt | — | EHR | cont |
| 15 | `imaging_orders_count` | 影像檢查數 | cnt | — | EHR | cont |
| 16 | `referral_count` | 轉診次數 | cnt | — | EHR | cont |
| 17 | `visit_duration_min` | 看診時長 | cont | 分 | EHR/SR | event |
| 18 | `questions_asked_per_visit` | 每次看診提問數 | cnt | 由就診前清單 | SR/TEL | event |
| 19 | `previsit_summary_used_in_visit` | 看診時使用 App 摘要 | bin | 是/否 | SR | FU48 |
| 20 | `healthcare_cost_estimate` | 醫療花費估計 | cont | 元 | EHR/DRV | D28 |

---

## 6. 結果指標 Outcome metrics（20）— 已驗證 PRO ＋ 衍生

> 多數沿用既有研究量表（B1/B2/B3/C5/D1–D4/E）。**新增 PAM-13** 病人賦能量表作主要次級結果。

| # | 變項名稱 | 中文標籤 | 型別 | 值域 | 來源 | 時點 | 工具/文獻 |
|---|---|---|---|---|---|---|---|
| 1 | `secd6_mean` | 慢性病自我效能 | cont | 1–10 | DRV←SR | D0/D14/D28 | SECD-6（PMID 11769298） |
| 2 | `secd6_change_d0d28` | 自我效能變化 | cont | Δ | DRV | D28 | — |
| 3 | `eheals_total` | 數位健康識能 | cont | 8–40 | DRV←SR | D0 | eHEALS（PMID 17213046） |
| 4 | `pam13_score` | 病人賦能（活化）分 | cont | 0–100 | DRV←SR | D0/D28 | **PAM-13（新增）** |
| 5 | `pam13_level` | 病人活化等級 | ord | 1–4 | DRV | D0/D28 | PAM-13 |
| 6 | `previsit_prep_mean` | 就診前準備度 | cont | 1–6 | DRV←SR | D0/D14/D28 | 自編 B3 |
| 7 | `comm_behavior_change_mean` | 溝通行為改變 | cont | 1–6 | DRV←SR | D28 | 自編 D4 |
| 8 | `care_total` | 醫師同理 | cont | 10–50 | DRV←SR | FU48 | CARE（PMID 15528286） |
| 9 | `wfpts_total` | 醫師信任 | cont | 5–25 | DRV←SR | FU48 | WFPTS-5（PMID 16202125） |
| 10 | `collaborate_top_score` | 共享決策（top-box 率） | bin/cont | 0/1 | DRV←SR | FU48 | collaboRATE（PMID 23768763） |
| 11 | `mauq_ease_mean` | App 易用性 | cont | 1–7 | DRV←SR | D28 | MAUQ（PMID 30973342） |
| 12 | `mauq_interface_mean` | 介面滿意 | cont | 1–7 | DRV←SR | D28 | MAUQ |
| 13 | `mauq_useful_mean` | 有用性 | cont | 1–7 | DRV←SR | D28 | MAUQ |
| 14 | `mauq_total_mean` | App 可用性總體 | cont | 1–7 | DRV | D28 | MAUQ |
| 15 | `continuance_intention_mean` | 繼續使用意圖 | cont | 1–7 | DRV←SR | D28 | 自編 E1（TAM） |
| 16 | `nps_score` | 淨推薦值 | cont | −100…100 | DRV←SR | D28 | NPS |
| 17 | `symptom_burden_change` | 症狀負荷變化 | cont | Δ 0–10 | DRV | D28 | — |
| 18 | `self_efficacy_mid_met` | 自我效能達 MID | bin | 是/否 | DRV | D28 | — |
| 19 | `retention_completed_study` | 完成全程（留存） | bin | 是/否 | DRV | D28 | 可行性主結果 |
| 20 | `feasibility_overall_met` | 可行性綜合達標 | bin | 是/否 | DRV | D28 | 留存×依從×滿意門檻 |

---

## 7. 實作落差（必讀 — 規則 12 誠實揭露）

本 codebook **跨出目前 App 已收集的範圍**，請審核時一併決定：

1. **`SR` 自填（人口學/疾病自填/結果 PRO）— 既有引擎可直接做。**
   新增的 **PAM-13** 與擴充的人口學/疾病題，照 `seed_study_surveys.py` 模式即可（config 驅動計分）。
   ⚠️ PAM-13 屬授權量表（Insignia Health），商用/研究使用**需取得授權**，需先確認。

2. **`TEL` 使用行為＋技術錯誤事件 — 目前缺基礎建設。**
   App 現在只記 `symptom_entries` / `vital_entries` / `sleep_sessions` / `medication_logs`，
   **沒有** session / crash / API 失敗 / 功能點擊 / 推播開啟 的事件日誌。使用行為（40）約
   30 項、錯誤事件（30）約 16 項依賴一個**新的 `app_events` 事件表＋前端埋點**。
   這是獨立的一塊工程（可對接 product-tracking 工具）。

3. **`EHR` 病歷/臨床 — 需醫師端輸入或匯入。**
   ICD-10、檢驗值、醫療利用多需醫師後台補錄或串接，現有 `doctor_notes` /
   `medication_changes` / `admissions` 可承接一部分，其餘需新欄位。

4. **`DRV` 衍生變項 — 後端純程式碼計算（規則 5）。**
   依從率、缺漏率、效應量等已有先例（`surveys.py` 的 `_adherence` / `_describe` / `_rank_biserial`），
   可延伸；不丟 LLM。

5. **倫理 / IRB**：人口學（收入）、ICD-10、醫療利用屬敏感個資；錯誤事件含裝置遙測。
   研究計畫與知情同意需涵蓋這些欄位的蒐集與去識別化。

---

## 8. 參考文獻（據 PubMed；含 DOI）

> 以下引用來自 **PubMed**。

- 使用行為 engagement 框架：Perski O, Blandford A, West R, Michie S. *Conceptualising engagement with digital behaviour change interventions.* Transl Behav Med. 2017;7(2):254-267. [DOI](https://doi.org/10.1007/s13142-016-0453-1)（PMID 27966189）
- 缺漏 / 順從度機制：Courvoisier DS, Eid M, Lischetzke T. *Compliance to a cell phone-based ecological momentary assessment study: the effect of time and personality characteristics.* Psychol Assess. 2012;24(3):713-20. [DOI](https://doi.org/10.1037/a0026733)（PMID 22250597）
- 共病指數：Charlson ME, Carrozzino D, Guidi J, Patierno C. *Charlson Comorbidity Index: A Critical Review of Clinimetric Properties.* Psychother Psychosom. 2022;91(1):8-35. [DOI](https://doi.org/10.1159/000521288)（PMID 34991091）
- 病人賦能 PAM-13（驗證）：Ngooi BX, et al. *Validation of the Patient Activation Measure (PAM-13) among adults with cardiac conditions in Singapore.* Qual Life Res. 2016;26(4):1071-1080. [DOI](https://doi.org/10.1007/s11136-016-1412-5)（PMID 27645458）；Xie HX, et al. J Spinal Cord Med. 2024. [DOI](https://doi.org/10.1080/10790268.2024.2391594)（PMID 39392460）
- 數位健康 App 可行性 / engagement-retention 範例（MAUQ 應用）：Gudmundsdóttir SL, et al. JMIR Form Res. 2023;7:e41227. [DOI](https://doi.org/10.2196/41227)（PMID 36975050）

**既有研究量表（已在 `seed_study_surveys.py` 留存 PMID/DOI）**：SECD-6（PMID 11769298）、eHEALS（[DOI](https://doi.org/10.2196/jmir.8.4.e27)，PMID 17213046）、MAUQ（[DOI](https://doi.org/10.2196/11500)，PMID 30973342）、CARE（[DOI](https://doi.org/10.1093/fampra/cmh621)，PMID 15528286）、WFPTS-5（[DOI](https://doi.org/10.1186/1472-6963-5-64)，PMID 16202125）、collaboRATE（[DOI](https://doi.org/10.1016/j.pec.2013.05.009)，PMID 23768763）。
