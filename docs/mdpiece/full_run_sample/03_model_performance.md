# 3. Layer-3 模型表現

## 整體 test 指標（80/10/10 patient-level split）
- 訓練資料：424960 / val 53120 / test 53120 個 sliding window
- 最佳 epoch：6（val loss 0.1560）
- 模型參數：82371
- 特徵數：125

### Activity 回歸
- MAE  = 0.164  CI95=[0.1618366800248623, 0.1661989413201809]
- RMSE = 0.307
- R²   = 0.927
- baseline (mean predictor) MAE = 0.853

### Flare 分類
- AUROC = 0.933  CI95=[0.9289221218745316, 0.9368378052695597]
- AUPRC = 0.693
- F1@0.5 = 0.630
- positive rate = 0.06543675065040588

## 各疾病平均 MAE / 召回 / 準確率
| 疾病 | n | MAE | flare 召回 | 準確 |
|---|---|---|---|---|
| anca_vasculitis | 200 | 0.130 | 59% | 73% |
| ankylosing_spondylitis | 200 | 0.138 | 41% | 71% |
| asthma | 200 | 0.570 | 23% | 63% |
| behcet_disease | 200 | 0.124 | 44% | 52% |
| chronic_urticaria | 200 | 0.351 | 17% | 70% |
| gout | 200 | 0.245 | 15% | 50% |
| idiopathic_pulmonary_fibrosis | 200 | 0.068 | 25% | 97% |
| igg4_related_disease | 200 | 0.088 | 61% | 42% |
| inflammatory_bowel_disease | 200 | 0.140 | 45% | 63% |
| multiple_sclerosis | 200 | 0.101 | 52% | 71% |
| osteoarthritis | 200 | 0.078 | 52% | 57% |
| psoriatic_arthritis | 200 | 0.127 | 53% | 70% |
| rheumatoid_arthritis | 200 | 0.153 | 67% | 89% |
| sjogren_syndrome | 200 | 0.104 | 46% | 52% |
| systemic_lupus_erythematosus | 200 | 0.176 | 64% | 77% |
| systemic_sclerosis | 200 | 0.072 | 35% | 36% |