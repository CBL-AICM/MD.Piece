# assumptions.md — SLE 減藥翻轉預警

## 界線值總表狀態

| 名稱 | status | 值 | 出處 |
|---|---|---|---|
| mu_c | anchored | 0.3849001794597505 | 數學常數 2/(3√3)：摺疊分岔臨界值 |
| x_stable | anchored | [-1.0, 1.0] | 數學常數：μ=0 時雙穩態平衡點 |
| traj_egfr_proportions | anchored | {"stable": 0.879, "late_decline": 0.07, "persistent_decline": 0.051} | Ning 2026, PMID 41611465（摘要；全文 Fig1） |
| traj_upcr_proportions | anchored | {"low_decreasing": 0.815, "high_decreasing": 0.114, "high_increasing": 0.071} | Ning 2026, PMID 41611465（摘要） |
| flare_rate_late_decline | anchored | {"late_decline": 0.91, "stable": 0.25} | Ning 2026, PMID 41611465（摘要；蛋白尿發作，全追蹤期中位 5.5 年） |
| traj_baseline_egfr_median | anchored | {"stable": 100, "late_decline": 127, "persistent_decline": 70} | Ning 2026 全文 Table 2（切片時，非減藥起點） |
| withdrawal_flare_rate_24m | anchored | 0.3055555555555556 | De Rosa 2018, PMID 30045812：11/36 於停藥後 24 個月 |
| withdrawal_flare_rate_52w | anchored | 0.32142857142857145 | Gopal 2023, PMID 37987842：9/28 於 52 週 |
| biopsy_rule_sensitivity | anchored | 1.0 | De Rosa 2018, PMID 30045812 |
| biopsy_rule_specificity | anchored | 0.88 | De Rosa 2018, PMID 30045812 |
| biopsy_rule_misclassification | anchored | 0.083 | De Rosa 2018, PMID 30045812 |
| nih_ai_flare_threshold | anchored | 2 | De Rosa 2018, PMID 30045812：活性指數 > 2 者全部發作 |
| derosa_flare_counts | anchored | {"completed": 36, "flared": 11, "flared_with_residual_activity": 10} | De Rosa 2018, PMID 30045812（摘要） |
| traj_slopes | pending_extraction | {"late_decline": null, "persistent_decline": null} | 待抽取：Ning 2026 全文 Fig1／補充表（PMC12863332）；全文正文無數字表，需讀圖 |
| traj_slope_sd | pending_extraction | null（佔位 {"persistent_decline_x_per_year_sd": 0.15}） | 待抽取：Ning 2026 全文 |
| taper_schedule | pending_extraction | null（佔位 {"taper_duration_days": 180, "shape": "linear", "complete_withdrawal": true, "presets": [{"name": "placeholder_fast", "taper_duration_days": 90}, {"name": "placeholder_default", "taper_duration_days": 180}, {"name": "placeholder_slow", "taper_duration_days": 365}], "note": "佔位：自 t_onset 起線性遞減至 0；三個文獻情境預設待 EULAR 全文補齊後替換"}） | 待抽取：EULAR 2025 更新（Fanouriakis 等，PMID 41107121）全文『類固醇遞減與停藥、療程長度』 |
| monitoring_items_and_interval | pending_extraction | null（佔位 {"default_interval_days": 30, "note": "佔位：每月回診取樣"}） | 待抽取：EULAR 2025 全文『治療目標與里程碑』 |
| flare_definition_threshold | pending_extraction | null（佔位 {"x_threshold": 0.0, "note": "佔位：x 跨 0（兩穩態中點）記為 t_threshold 里程碑；僅描述性"}） | 待抽取：Gopal 2023 使用 SELENA-SLEDAI 發作指數；原始工具文獻 Petri 2005 NEJM（SELENA 試驗，PMID 16354891）方法／補充材料之操作型門檻 |
| tau | study_defined | 30 | 本研究設定：預設待新設定下 τ 掃描後由裁決決定（CKD 版結論不可沿用）；此值為掃描前的暫定值 |
| tau_ou | study_defined | null（佔位 null） | 本研究設定：與 tau 同量級；null = 依健康態線性化回復率配對，使有色雜訊與翻轉型的 lag-1 自相關可比 |
| sigma | study_defined | 0.1 | 本研究設定：緩解態 x 波動的定態 SD（x 單位）；OU 力 ξ 的振幅由 Var(x)=s_ξ²·τ_OU/(a(1+aτ_OU)) 反推（a=λ_lin/τ） |
| map_weight_a | study_defined | 0.5 | 本研究設定：蛋白尿與腎功能在 x 映射中的權重 |
| sigma_biopsy | study_defined | null（佔位 null） | 本研究設定：由校準步驟二反推（敏感度→1.00、特異度→0.88） |
| meas_error_levels | study_defined | {"none": 0.0, "small": 0.05, "medium": 0.15, "large": 0.3} | 本研究設定：量測誤差 SD（x 單位）四階，醫院檢驗至自填 |
| sampling_intervals | study_defined | {"daily": 1, "weekly": 7, "monthly": 30, "half_year": 182} | 本研究設定：平台紀錄至年度回診 |
| window | study_defined | 30 | 本研究設定：滾動窗長，須與 tau 同量級 |
| T | study_defined | 730 | 本研究設定：對齊 De Rosa 24 個月追蹤；自 t_onset 起算 |
| run_in_days | study_defined | 90 | 本研究設定：減藥起始前的定態觀察期（G3 需要 t < t_onset 的資料）；總序列長 = run_in_days + T |
| N | study_defined | 3000 | 本研究設定 |
| g0 | study_defined | 1.5 | 本研究設定：全劑量免疫抑制的穩定效果（x 單位）；須使 μ_intrinsic − g0 < μ_c 對全體成立 |
| mu_intrinsic_dist | study_defined | {"mean": null, "sd": 0.35} | 本研究設定：常態分布；mean 由校準步驟一反推（停藥後 24 個月發作率 → 0.306），sd 為設定 |
| hazard | study_defined | {"lambda0_per_day": 0.0005, "beta_per_x": 2.08} | 本研究設定（由 De Rosa 2018 計數推算的量級：無殘餘活性者 24 個月約 1/22 發作 → λ(x=−1)≈6.3e-5/天；翻轉者約 10/13 於一年內發作 → λ(x=+1)≈4.0e-3/天；曝露時間為假設） |
| kappa | study_defined | 0.5 | 本研究設定：基線臨床特徵與 μ_intrinsic 的相關強度；靜態 C 不在區間時走格點 |
| k_max | study_defined | 8 | 本研究設定：撞頂須記錄為 k_ceiling_hit |
| bic_improve_tol | study_defined | 0.05 | 本研究設定 |
| stability_min | study_defined | 0.6 | 本研究設定（Hennig 慣例） |
| bootstrap_n | study_defined | 200 | 本研究設定 |
| null_subjects | study_defined | 200 | 本研究設定 |
| null_perms | study_defined | 100 | 本研究設定 |
| alarm_percentile | study_defined | 95 | 本研究設定 |
| leak_brake_delta_c | study_defined | 0.05 | 本研究設定 |
| gate2_max_delta_c | study_defined | 0.01 | 本研究設定 |
| gate3_auroc_range | study_defined | [0.45, 0.55] | 本研究設定 |
| gate1_max_type_share | study_defined | 0.9 | 本研究設定 |
| burn_in_days | study_defined | 90 | 本研究設定：趨勢外推基準的暖身期 |
| landmarks | study_defined | [90, 180, 365, 540] | 本研究設定：自 t_onset 起算 |
| static_c_target | study_defined | [0.65, 0.75] | 本研究設定（校準步驟三） |
| eval_every_days | study_defined | 7 | 本研究設定：警報評估頻率 |
| high_risk_top_share | study_defined | 0.2 | 本研究設定：相對閾值前 20% |

## 世代生成設定（cohort.json）

| 名稱 | status | 設定 | 出處 |
|---|---|---|---|
| upcr_g_per_g | study_defined | {"dist": "lognormal", "median": 0.25, "sigma_log": 0.5, "clip": [0.02, 0.5]} | 本研究設定：完全緩解定義蛋白尿 <0.5 g/day（Ning 2026 定義；EULAR），中位數為假設 |
| egfr | study_defined | {"dist": "normal", "mean": 95, "sd": 15, "clip": [45, 130]} | 本研究設定：緩解世代腎功能；Ning 2026 Table 2 穩定型切片時中位 100 供參 |
| c3_mg_dl | study_defined | {"dist": "normal", "mean": 100, "sd": 20, "clip": [50, 160]} | 本研究設定：緩解時補體多正常；Ning 2026 Table 1 切片時 C3 中位 0.50 g/L 供參（活動期） |
| anti_dsdna_iu_ml | study_defined | {"dist": "lognormal", "median": 30, "sigma_log": 1.0, "clip": [1, 800]} | 本研究設定：緩解時多低滴度；Ning 2026 Table 1 活動期中位 493 供參 |
| disease_duration_yr | study_defined | {"dist": "lognormal", "median": 6.0, "sigma_log": 0.4, "clip": [4, 30]} | 本研究設定：下界 4 年由 De Rosa 2018 納入條件（≥36 個月治療＋≥12 個月緩解）推得 |
| prior_flares | study_defined | {"dist": "poisson", "lam": 1.0, "clip": [0, 6]} | 本研究設定 |

## ※ 佔位參數（5 項）：traj_slopes, traj_slope_sd, taper_schedule, monitoring_items_and_interval, flare_definition_threshold

本次結果使用佔位參數，不得對外引用。

## 校準三步達成值

| 步驟 | 目標 | 達成 | 備註 |
|---|---|---|---|
| 一 μ_intrinsic 平均 | 24 個月發作率 0.306（檢核 52 週 0.321） | 24 個月 0.305、52 週 0.103 | ；52 週偏差 -0.218 |
| 二 σ_biopsy | 敏感度 1.00／特異度 0.88 | σ=0 時 敏感度 0.989／特異度 0.305 | unreachable：無誤差時特異度已低於目標；發作者中 4% 的 μ 低於非發作者中位（基線風險造成的低 μ 發作）。對照：敏感度目標取 10/11 時 σ=0 特異度 0.631 |
| 三 靜態基線 C | [0.65, 0.75] | C = 0.673（kappa=0.5） |  |

## 四道閘門

| 閘門 | 值 | 條件 | 結果 |
|---|---|---|---|
| G1 各風險層內單一型別最高佔比 | 0.983 | <= 0.9 | 未過：起點未重疊，H1 被設定成偽 |
| G2 β=0 時 max_L |ΔC_L| | 0.0203 | < 0.01 | 未過：結局仍與 x(t) 耦合，存在洩漏 |
| G3 僅用 t<t_onset 資料的型別分類 AUROC | 0.596 | [0.45, 0.55] | 未過：兩型在減藥前即可分，存在混淆 |
| G4 mu_intrinsic 未進入非侵入臂 | 簽章 無／原始碼 無／置換後雜湊 相同 | 完全未進入 | 通過 |
