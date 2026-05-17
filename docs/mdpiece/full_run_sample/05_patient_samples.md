# 5. 代表性患者樣本（每疾病 k=3）

（依模型 MAE 由低到高排序，呈現模型對各疾病最有把握的案例）


## ANCA-associated Vasculitis (`anca_vasculitis`)


### AAV_0139 — MAE 0.101
- 63 歲 F, subtype=mpa, responder=partial
```
📋 患者畫像：63 歲 女性，診斷為 anca_vasculitis（mpa 亞型），被分類為 部分反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持中、居住with_family；學歷高中職、中等收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.41、神經質 0.52、樂觀 0.38；PHQ-9=11、GAD-7=0。
💼 行為：抽菸 former、酒 0.6u/週、運動 4/週、睡眠 7.3h (佳)、健康識讀=中、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.54（神經質/憂鬱影響）。
💊 治療：prednisone（強度 0.23），並在第 169 天停藥。
🎲 生活事件：infection, infection。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型發出 6 個誤警，實際未發生 flare — 可能受到夜間活動度高峰或 life event 訊號干擾。
📝 結論：典型病程，持續追蹤即可。
```

### AAV_0176 — MAE 0.102
- 85 歲 M, subtype=gpa, responder=typical
```
📋 患者畫像：85 歲 男性，診斷為 anca_vasculitis（gpa 亞型），被分類為 典型反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持中、居住alone；學歷大專、中下收入、保險健保+私保、退休、鄉村地區。
🧠 人格/心理：盡責性 0.92、神經質 0.78、樂觀 0.55；PHQ-9=3、GAD-7=10。
💼 行為：抽菸 current、酒 8.1u/週、運動 3/週、睡眠 6.8h (差)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.69（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 5 項，自動疊加共病：osteoarthritis, cataract。
💊 治療：prednisone（強度 0.64），共漏吃 10 天。
🎲 生活事件：infection。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### AAV_0066 — MAE 0.106
- 47 歲 M, subtype=gpa, responder=non_responder
```
📋 患者畫像：47 歲 男性，診斷為 anca_vasculitis（gpa 亞型），被分類為 無反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持低、居住with_family；學歷大專、中等收入、保險健保+私保、自雇、城鎮地區。
🧠 人格/心理：盡責性 0.31、神經質 0.55、樂觀 0.31；PHQ-9=6、GAD-7=4。
💼 行為：抽菸 never、酒 3.0u/週、運動 3/週、睡眠 7.2h (普通)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.42（神經質/憂鬱影響）。
💊 治療：azathioprine（強度 0.12）, prednisone（強度 0.15），共漏吃 47 天。
🎲 生活事件：infection。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 11 個 flare 窗口，模型預警 5 個，召回率 45%、準確率 100%。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

## Ankylosing Spondylitis (`ankylosing_spondylitis`)


### AS_0040 — MAE 0.104
- 46 歲 F, subtype=axial_peripheral, responder=typical
```
📋 患者畫像：46 歲 女性，診斷為 ankylosing_spondylitis（axial_peripheral 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持中、居住with_family；學歷大專、低收收入、保險健保+企業團保、全職、城鎮地區。
🧠 人格/心理：盡責性 0.29、神經質 0.74、樂觀 0.70；PHQ-9=7、GAD-7=8。
💼 行為：抽菸 never、酒 1.2u/週、運動 3/週、睡眠 7.9h (普通)、健康識讀=高、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.41（神經質/憂鬱影響）。
💊 治療：未接受任何處方治療。
🎲 生活事件：physical_overuse, prolonged_sitting, physical_overuse, prolonged_sitting, prolonged_sitting 等共 20 件。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### AS_0013 — MAE 0.106
- 53 歲 F, subtype=axial_only, responder=typical
```
📋 患者畫像：53 歲 女性，診斷為 ankylosing_spondylitis（axial_only 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持中、居住with_family；學歷研究所以上、中下收入、保險健保_only、全職、城鎮地區。
🧠 人格/心理：盡責性 0.55、神經質 0.49、樂觀 0.50；PHQ-9=11、GAD-7=3。
💼 行為：抽菸 never、酒 3.6u/週、運動 0/週、睡眠 5.8h (普通)、健康識讀=高、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.52（神經質/憂鬱影響）。
💊 治療：nsaid（強度 1.27）, physiotherapy（強度 0.07），共漏吃 21 天。
🎲 生活事件：prolonged_sitting, prolonged_sitting, prolonged_sitting, prolonged_sitting, prolonged_sitting 等共 12 件。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### AS_0176 — MAE 0.107
- 85 歲 M, subtype=axial_only, responder=typical
```
📋 患者畫像：85 歲 男性，診斷為 ankylosing_spondylitis（axial_only 亞型），被分類為 典型反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持中、居住alone；學歷大專、中下收入、保險健保+私保、退休、鄉村地區。
🧠 人格/心理：盡責性 0.92、神經質 0.78、樂觀 0.55；PHQ-9=3、GAD-7=10。
💼 行為：抽菸 current、酒 8.1u/週、運動 3/週、睡眠 6.8h (差)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.69（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 5 項，自動疊加共病：osteoarthritis, cataract。
💊 治療：nsaid（強度 0.26），共漏吃 13 天。
🎲 生活事件：prolonged_sitting, prolonged_sitting, physical_overuse, prolonged_sitting, prolonged_sitting 等共 12 件。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

## Asthma (`asthma`)


### Asthma_0002 — MAE 0.295
- 74 歲 M, subtype=eosinophilic, responder=partial
```
📋 患者畫像：74 歲 男性，診斷為 氣喘（eosinophilic 亞型），被分類為 部分反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持低、居住with_family；學歷大專、中上收入、保險健保_only、退休、城鎮地區。
🧠 人格/心理：盡責性 0.39、神經質 0.75、樂觀 0.30；PHQ-9=11、GAD-7=4。
💼 行為：抽菸 never、酒 0.0u/週、運動 1/週、睡眠 6.4h (佳)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.78（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 3 項，自動疊加共病：diabetes_t2, osteoarthritis。
💊 治療：laba（強度 0.63）, saba_rescue（強度 0.64），共漏吃 63 天。
🎲 生活事件：travel_pollution。
🤖 AI 預測表現：活動度 MAE = 0.29，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### Asthma_0123 — MAE 0.330
- 84 歲 M, subtype=neutrophilic, responder=non_responder
```
📋 患者畫像：84 歲 男性，診斷為 氣喘（neutrophilic 亞型），被分類為 無反應者。
🏠 家庭/社經：離婚、子女 3 位、家庭支持中、居住with_family；學歷高中職、高收收入、保險健保+私保、全職、都會地區。
🧠 人格/心理：盡責性 0.57、神經質 0.68、樂觀 0.63；PHQ-9=5、GAD-7=1。
💼 行為：抽菸 never、酒 1.6u/週、運動 5/週、睡眠 7.0h (差)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.75（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 3 項，自動疊加共病：cataract。
💊 治療：saba_rescue（強度 0.10），共漏吃 24 天。
🎲 生活事件：travel_pollution。
🤖 AI 預測表現：活動度 MAE = 0.33，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型發出 3 個誤警，實際未發生 flare — 可能受到夜間活動度高峰或 life event 訊號干擾。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

### Asthma_0100 — MAE 0.334
- 73 歲 F, subtype=eosinophilic, responder=super
```
📋 患者畫像：73 歲 女性，診斷為 氣喘（eosinophilic 亞型），被分類為 超級反應者。
🏠 家庭/社經：喪偶、子女 3 位、家庭支持中、居住with_family；學歷國中以下、中等收入、保險健保_only、家管、鄉村地區。
🧠 人格/心理：盡責性 0.34、神經質 0.16、樂觀 0.39；PHQ-9=9、GAD-7=0。
💼 行為：抽菸 never、酒 0.2u/週、運動 1/週、睡眠 7.0h (普通)、健康識讀=低、使用中醫=否。
⚖️ 模型考量：漏吃藥風險 ×1.40。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：hypertension, ckd, cataract。
💊 治療：ics（強度 1.46）, laba（強度 0.57）, saba_rescue（強度 2.61），共漏吃 134 天。
🎲 生活事件：viral_uri, travel_pollution, smoke_exposure, smoke_exposure, smoke_exposure。
🤖 AI 預測表現：活動度 MAE = 0.33，接近 cohort 平均（0.26）。
🔍 Flare 預測：實際有 7 個 flare 但模型未預警 — 可能因為亞型/反應者組合在此 cohort 中較罕見。
📌 可能觸發因子：實際 flare 附近出現 viral_uri(d24)。
📝 結論：超級反應者，當前治療可維持。
```

## Behçet's Disease (`behcet_disease`)


### Behcet_0046 — MAE 0.104
- 43 歲 M, subtype=vascular_neuro, responder=non_responder
```
📋 患者畫像：43 歲 男性，診斷為 behcet_disease（vascular_neuro 亞型），被分類為 無反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持低、居住with_family；學歷高中職、中等收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.69、神經質 0.53、樂觀 0.62；PHQ-9=4、GAD-7=7。
💼 行為：抽菸 current、酒 3.3u/週、運動 6/週、睡眠 4.9h (普通)、健康識讀=低、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.45（神經質/憂鬱影響）、漏吃藥風險 ×1.37。
💊 治療：colchicine（強度 0.07）, anti_tnf（強度 0.06），共漏吃 47 天。
🎲 生活事件：viral_infection, oral_trauma, oral_trauma。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

### Behcet_0072 — MAE 0.104
- 45 歲 F, subtype=mucocutaneous, responder=typical
```
📋 患者畫像：45 歲 女性，診斷為 behcet_disease（mucocutaneous 亞型），被分類為 典型反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持高、居住with_family；學歷大專、中上收入、保險健保+企業團保、兼職、鄉村地區。
🧠 人格/心理：盡責性 0.53、神經質 0.27、樂觀 0.26；PHQ-9=0、GAD-7=4。
💼 行為：抽菸 never、酒 0.8u/週、運動 2/週、睡眠 7.7h (佳)、健康識讀=中、使用中醫=是。
💊 治療：colchicine（強度 0.82），共漏吃 7 天。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### Behcet_0032 — MAE 0.105
- 27 歲 F, subtype=mucocutaneous, responder=non_responder
```
📋 患者畫像：27 歲 女性，診斷為 behcet_disease（mucocutaneous 亞型），被分類為 無反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持高、居住with_family；學歷研究所以上、中上收入、保險健保+私保、全職、城鎮地區。
🧠 人格/心理：盡責性 0.54、神經質 0.13、樂觀 0.71；PHQ-9=0、GAD-7=3。
💼 行為：抽菸 never、酒 0.1u/週、運動 2/週、睡眠 6.8h (佳)、健康識讀=高、使用中醫=否。
💊 治療：colchicine（強度 0.10），共漏吃 2 天。
🎲 生活事件：viral_infection, stress_major, oral_trauma。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型發出 1 個誤警，實際未發生 flare — 可能受到夜間活動度高峰或 life event 訊號干擾。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

## Chronic Spontaneous Urticaria (`chronic_urticaria`)


### CSU_0174 — MAE 0.216
- 83 歲 F, subtype=inducible, responder=typical
```
📋 患者畫像：83 歲 女性，診斷為 chronic_urticaria（inducible 亞型），被分類為 典型反應者。
🏠 家庭/社經：離婚、子女 1 位、家庭支持高、居住alone；學歷高中職、中下收入、保險健保+企業團保、全職、都會地區。
🧠 人格/心理：盡責性 0.63、神經質 0.80、樂觀 0.47；PHQ-9=2、GAD-7=10。
💼 行為：抽菸 never、酒 0.1u/週、運動 2/週、睡眠 6.8h (普通)、健康識讀=高、使用中醫=是。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 6 項，自動疊加共病：hypertension, cataract。
💊 治療：h1_antihistamine（強度 0.53），共漏吃 16 天。
🎲 生活事件：emotional_stress_major, nsaid_use。
🤖 AI 預測表現：活動度 MAE = 0.22，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### CSU_0123 — MAE 0.223
- 84 歲 M, subtype=inducible, responder=non_responder
```
📋 患者畫像：84 歲 男性，診斷為 chronic_urticaria（inducible 亞型），被分類為 無反應者。
🏠 家庭/社經：離婚、子女 3 位、家庭支持中、居住with_family；學歷高中職、高收收入、保險健保+私保、全職、都會地區。
🧠 人格/心理：盡責性 0.57、神經質 0.68、樂觀 0.63；PHQ-9=5、GAD-7=1。
💼 行為：抽菸 never、酒 1.6u/週、運動 5/週、睡眠 7.0h (差)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.75（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 3 項，自動疊加共病：cataract。
💊 治療：h1_antihistamine（強度 0.11），共漏吃 22 天。
🎲 生活事件：nsaid_use, nsaid_use, nsaid_use, nsaid_use。
🤖 AI 預測表現：活動度 MAE = 0.22，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

### CSU_0138 — MAE 0.226
- 89 歲 F, subtype=spontaneous, responder=partial
```
📋 患者畫像：89 歲 女性，診斷為 chronic_urticaria（spontaneous 亞型），被分類為 部分反應者。
🏠 家庭/社經：喪偶、子女 0 位、家庭支持低、居住alone；學歷國中以下、中上收入、保險健保_only、退休、城鎮地區。
🧠 人格/心理：盡責性 0.60、神經質 0.41、樂觀 0.55；PHQ-9=14、GAD-7=4。
💼 行為：抽菸 never、酒 1.8u/週、運動 3/週、睡眠 7.5h (普通)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.56（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 9 項，自動疊加共病：hypertension, diabetes_t2, osteoarthritis。
💊 治療：h1_antihistamine（強度 0.41）, omalizumab（強度 0.41），共漏吃 85 天。
🎲 生活事件：nsaid_use, nsaid_use, nsaid_use。
🤖 AI 預測表現：活動度 MAE = 0.23，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

## Gout (`gout`)


### Gout_0047 — MAE 0.169
- 71 歲 M, subtype=intermittent, responder=partial
```
📋 患者畫像：71 歲 男性，診斷為 gout（intermittent 亞型），被分類為 部分反應者。
🏠 家庭/社經：喪偶、子女 2 位、家庭支持高、居住alone；學歷大專、中下收入、保險健保+企業團保、退休、城鎮地區。
🧠 人格/心理：盡責性 0.58、神經質 0.30、樂觀 0.53；PHQ-9=8、GAD-7=7。
💼 行為：抽菸 never、酒 5.7u/週、運動 2/週、睡眠 6.1h (佳)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.44（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 9 項，自動疊加共病：hypertension, cataract。
💊 治療：allopurinol（強度 0.22），並在第 17 天停藥。
🎲 生活事件：alcohol_binge, purine_meal, purine_meal, purine_meal, alcohol_binge 等共 12 件。
🤖 AI 預測表現：活動度 MAE = 0.17，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### Gout_0063 — MAE 0.177
- 80 歲 F, subtype=intermittent, responder=super
```
📋 患者畫像：80 歲 女性，診斷為 gout（intermittent 亞型），被分類為 超級反應者。
🏠 家庭/社經：離婚、子女 1 位、家庭支持高、居住with_family；學歷高中職、低收收入、保險健保+企業團保、自雇、都會地區。
🧠 人格/心理：盡責性 0.37、神經質 0.45、樂觀 0.84；PHQ-9=0、GAD-7=8。
💼 行為：抽菸 never、酒 0.3u/週、運動 3/週、睡眠 8.5h (普通)、健康識讀=低、使用中醫=是。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 2 項，自動疊加共病：osteoarthritis。
💊 治療：colchicine（強度 1.19）, nsaid（強度 0.70），共漏吃 47 天。
🎲 生活事件：alcohol_binge, dehydration, purine_meal, purine_meal, purine_meal 等共 13 件。
🤖 AI 預測表現：活動度 MAE = 0.18，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：超級反應者，當前治療可維持。
```

### Gout_0138 — MAE 0.178
- 89 歲 M, subtype=intermittent, responder=partial
```
📋 患者畫像：89 歲 男性，診斷為 gout（intermittent 亞型），被分類為 部分反應者。
🏠 家庭/社經：喪偶、子女 0 位、家庭支持低、居住alone；學歷國中以下、中上收入、保險健保_only、退休、城鎮地區。
🧠 人格/心理：盡責性 0.60、神經質 0.41、樂觀 0.55；PHQ-9=14、GAD-7=4。
💼 行為：抽菸 never、酒 8.8u/週、運動 3/週、睡眠 7.5h (普通)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.56（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 9 項，自動疊加共病：hypertension, diabetes_t2, osteoarthritis。
💊 治療：allopurinol（強度 0.14）, colchicine（強度 0.73），共漏吃 86 天。
🎲 生活事件：purine_meal, dehydration, purine_meal, purine_meal, alcohol_binge 等共 13 件。
🤖 AI 預測表現：活動度 MAE = 0.18，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

## Idiopathic Pulmonary Fibrosis (`idiopathic_pulmonary_fibrosis`)


### IPF_0095 — MAE 0.064
- 57 歲 M, subtype=rapid_progressor, responder=typical
```
📋 患者畫像：57 歲 男性，診斷為 idiopathic_pulmonary_fibrosis（rapid_progressor 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 3 位、家庭支持高、居住with_family；學歷高中職、中下收入、保險健保_only、家管、城鎮地區。
🧠 人格/心理：盡責性 0.37、神經質 0.26、樂觀 0.43；PHQ-9=4、GAD-7=6。
💼 行為：抽菸 never、酒 0.1u/週、運動 0/週、睡眠 8.4h (普通)、健康識讀=中、使用中醫=是。
💊 治療：oxygen_therapy（強度 0.24），共漏吃 8 天。
🎲 生活事件：infection, infection。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### IPF_0093 — MAE 0.064
- 88 歲 M, subtype=rapid_progressor, responder=partial
```
📋 患者畫像：88 歲 男性，診斷為 idiopathic_pulmonary_fibrosis（rapid_progressor 亞型），被分類為 部分反應者。
🏠 家庭/社經：喪偶、子女 3 位、家庭支持中、居住with_family；學歷高中職、中等收入、保險健保+私保、退休、都會地區。
🧠 人格/心理：盡責性 0.72、神經質 0.21、樂觀 0.87；PHQ-9=0、GAD-7=0。
💼 行為：抽菸 never、酒 8.0u/週、運動 0/週、睡眠 5.5h (佳)、健康識讀=高、使用中醫=是。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 7 項，自動疊加共病：無自動加註的共病。
💊 治療：nintedanib（強度 0.16）, pirfenidone（強度 0.10）, oxygen_therapy（強度 0.04），共漏吃 20 天。
🎲 生活事件：infection, acute_exacerbation。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### IPF_0105 — MAE 0.071
- 55 歲 M, subtype=slow_progressor, responder=typical
```
📋 患者畫像：55 歲 男性，診斷為 idiopathic_pulmonary_fibrosis（slow_progressor 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持中、居住with_family；學歷高中職、中等收入、保險健保+企業團保、全職、都會地區。
🧠 人格/心理：盡責性 0.51、神經質 0.00、樂觀 0.46；PHQ-9=0、GAD-7=2。
💼 行為：抽菸 never、酒 2.2u/週、運動 3/週、睡眠 6.5h (佳)、健康識讀=高、使用中醫=是。
💊 治療：nintedanib（強度 0.23）, oxygen_therapy（強度 0.13），共漏吃 21 天。
🎲 生活事件：infection。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## IgG4-Related Disease (`igg4_related_disease`)


### IgG4RD_0154 — MAE 0.068
- 51 歲 M, subtype=systemic, responder=typical
```
📋 患者畫像：51 歲 男性，診斷為 igg4_related_disease（systemic 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持高、居住with_family；學歷大專、高收收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.30、神經質 0.51、樂觀 0.33；PHQ-9=12、GAD-7=4。
💼 行為：抽菸 never、酒 0.7u/週、運動 0/週、睡眠 7.9h (普通)、健康識讀=中、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.65（神經質/憂鬱影響）。
💊 治療：未接受任何處方治療。
🎲 生活事件：imaging_finding, imaging_finding。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### IgG4RD_0143 — MAE 0.071
- 68 歲 M, subtype=pancreatobiliary, responder=typical
```
📋 患者畫像：68 歲 男性，診斷為 igg4_related_disease（pancreatobiliary 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持中、居住with_family；學歷研究所以上、高收收入、保險健保+私保、自雇、都會地區。
🧠 人格/心理：盡責性 0.36、神經質 0.54、樂觀 0.51；PHQ-9=10、GAD-7=7。
💼 行為：抽菸 never、酒 4.0u/週、運動 1/週、睡眠 7.3h (普通)、健康識讀=高、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.70（神經質/憂鬱影響）。
💊 治療：prednisone（強度 1.19）, rituximab（強度 0.98），共漏吃 15 天。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### IgG4RD_0180 — MAE 0.071
- 60 歲 M, subtype=head_neck, responder=partial
```
📋 患者畫像：60 歲 男性，診斷為 igg4_related_disease（head_neck 亞型），被分類為 部分反應者。
🏠 家庭/社經：離婚、子女 4 位、家庭支持中、居住with_family；學歷大專、中下收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.42、神經質 0.53、樂觀 0.21；PHQ-9=2、GAD-7=6。
💼 行為：抽菸 never、酒 0.9u/週、運動 0/週、睡眠 6.5h (佳)、健康識讀=高、使用中醫=否。
💊 治療：prednisone（強度 0.58），並在第 149 天停藥。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Inflammatory Bowel Disease (`inflammatory_bowel_disease`)


### IBD_0124 — MAE 0.113
- 63 歲 M, subtype=uc, responder=typical
```
📋 患者畫像：63 歲 男性，診斷為 inflammatory_bowel_disease（uc 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 3 位、家庭支持中、居住with_family；學歷大專、中等收入、保險健保_only、自雇、都會地區。
🧠 人格/心理：盡責性 0.64、神經質 0.34、樂觀 0.44；PHQ-9=1、GAD-7=5。
💼 行為：抽菸 never、酒 7.8u/週、運動 2/週、睡眠 8.6h (差)、健康識讀=中、使用中醫=是。
💊 治療：mesalazine（強度 0.06），共漏吃 10 天。
🎲 生活事件：dietary_indiscretion, stress_major, nsaid_use, dietary_indiscretion, dietary_indiscretion 等共 11 件。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### IBD_0010 — MAE 0.118
- 36 歲 M, subtype=uc, responder=typical
```
📋 患者畫像：36 歲 男性，診斷為 inflammatory_bowel_disease（uc 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持中、居住with_family；學歷研究所以上、中下收入、保險健保+企業團保、家管、都會地區。
🧠 人格/心理：盡責性 0.18、神經質 0.16、樂觀 0.47；PHQ-9=1、GAD-7=5。
💼 行為：抽菸 current、酒 2.5u/週、運動 4/週、睡眠 5.0h (普通)、健康識讀=高、使用中醫=否。
💊 治療：mesalazine（強度 0.99）, azathioprine（強度 0.58），共漏吃 19 天。
🎲 生活事件：dietary_indiscretion, infection, dietary_indiscretion, infection, infection 等共 7 件。
🤖 AI 預測表現：活動度 MAE = 0.12，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### IBD_0026 — MAE 0.121
- 36 歲 M, subtype=uc, responder=partial
```
📋 患者畫像：36 歲 男性，診斷為 inflammatory_bowel_disease（uc 亞型），被分類為 部分反應者。
🏠 家庭/社經：離婚、子女 1 位、家庭支持高、居住with_family；學歷國中以下、高收收入、保險健保+企業團保、兼職、都會地區。
🧠 人格/心理：盡責性 0.43、神經質 0.30、樂觀 0.30；PHQ-9=5、GAD-7=3。
💼 行為：抽菸 former、酒 4.6u/週、運動 1/週、睡眠 7.1h (普通)、健康識讀=中、使用中醫=是。
💊 治療：mesalazine（強度 0.39）, azathioprine（強度 0.29）, anti_tnf（強度 0.59），並在第 132 天停藥。
🎲 生活事件：dietary_indiscretion, dietary_indiscretion, dietary_indiscretion, dietary_indiscretion。
🤖 AI 預測表現：活動度 MAE = 0.12，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Multiple Sclerosis (`multiple_sclerosis`)


### MS_0187 — MAE 0.076
- 64 歲 F, subtype=spms, responder=partial
```
📋 患者畫像：64 歲 女性，診斷為 multiple_sclerosis（spms 亞型），被分類為 部分反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持中、居住alone；學歷高中職、中下收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.06、神經質 0.57、樂觀 0.62；PHQ-9=1、GAD-7=2。
💼 行為：抽菸 never、酒 0.8u/週、運動 2/週、睡眠 5.7h (普通)、健康識讀=中、使用中醫=是。
💊 治療：未接受任何處方治療。
🎲 生活事件：heat_exposure, heat_exposure, heat_exposure, heat_exposure, heat_exposure 等共 9 件。
🤖 AI 預測表現：活動度 MAE = 0.08，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### MS_0169 — MAE 0.081
- 41 歲 F, subtype=rrms, responder=typical
```
📋 患者畫像：41 歲 女性，診斷為 multiple_sclerosis（rrms 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 3 位、家庭支持低、居住with_family；學歷大專、中上收入、保險健保_only、家管、都會地區。
🧠 人格/心理：盡責性 0.43、神經質 0.74、樂觀 0.49；PHQ-9=12、GAD-7=10。
💼 行為：抽菸 never、酒 0.6u/週、運動 2/週、睡眠 5.9h (差)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.52（神經質/憂鬱影響）。
💊 治療：未接受任何處方治療。
🎲 生活事件：heat_exposure, stress_major。
🤖 AI 預測表現：活動度 MAE = 0.08，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型發出 9 個誤警，實際未發生 flare — 可能受到夜間活動度高峰或 life event 訊號干擾。
📝 結論：典型病程，持續追蹤即可。
```

### MS_0118 — MAE 0.081
- 53 歲 M, subtype=spms, responder=partial
```
📋 患者畫像：53 歲 男性，診斷為 multiple_sclerosis（spms 亞型），被分類為 部分反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持中、居住with_family；學歷研究所以上、中等收入、保險健保+企業團保、自雇、都會地區。
🧠 人格/心理：盡責性 0.67、神經質 0.29、樂觀 0.88；PHQ-9=5、GAD-7=6。
💼 行為：抽菸 never、酒 5.2u/週、運動 0/週、睡眠 8.5h (差)、健康識讀=高、使用中醫=是。
💊 治療：interferon_beta（強度 0.22），共漏吃 8 天。
🎲 生活事件：stress_major, heat_exposure, heat_exposure, heat_exposure。
🤖 AI 預測表現：活動度 MAE = 0.08，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 15 個 flare 窗口，模型預警 8 個，召回率 53%、準確率 100%。
📌 可能觸發因子：實際 flare 附近出現 stress_major(d32)。
📝 結論：典型病程，持續追蹤即可。
```

## Osteoarthritis (`osteoarthritis`)


### OA_0166 — MAE 0.061
- 66 歲 M, subtype=hand, responder=typical
```
📋 患者畫像：66 歲 男性，診斷為 osteoarthritis（hand 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持低、居住with_family；學歷高中職、中等收入、保險健保_only、退休、都會地區。
🧠 人格/心理：盡責性 0.53、神經質 0.65、樂觀 0.43；PHQ-9=1、GAD-7=6。
💼 行為：抽菸 never、酒 1.6u/週、運動 2/週、睡眠 6.5h (普通)、健康識讀=低、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.60（神經質/憂鬱影響）、漏吃藥風險 ×1.54。
💊 治療：acetaminophen（強度 0.33）, nsaid_oral（強度 0.27）, physiotherapy（強度 0.51），共漏吃 138 天。
🎲 生活事件：physical_overuse, physical_overuse, physical_overuse, physical_overuse。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### OA_0002 — MAE 0.064
- 74 歲 F, subtype=knee, responder=partial
```
📋 患者畫像：74 歲 女性，診斷為 osteoarthritis（knee 亞型），被分類為 部分反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持低、居住with_family；學歷大專、中上收入、保險健保_only、退休、城鎮地區。
🧠 人格/心理：盡責性 0.39、神經質 0.75、樂觀 0.30；PHQ-9=11、GAD-7=4。
💼 行為：抽菸 never、酒 0.0u/週、運動 1/週、睡眠 6.4h (佳)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.78（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 3 項，自動疊加共病：diabetes_t2, osteoarthritis。
💊 治療：nsaid_topical（強度 0.12）, nsaid_oral（強度 0.13），共漏吃 55 天。
🎲 生活事件：physical_overuse, physical_overuse, injury_minor, physical_overuse, physical_overuse 等共 6 件。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型發出 1 個誤警，實際未發生 flare — 可能受到夜間活動度高峰或 life event 訊號干擾。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### OA_0110 — MAE 0.065
- 65 歲 F, subtype=hip, responder=partial
```
📋 患者畫像：65 歲 女性，診斷為 osteoarthritis（hip 亞型），被分類為 部分反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持高、居住with_family；學歷高中職、低收收入、保險健保+私保、退休、都會地區。
🧠 人格/心理：盡責性 0.52、神經質 0.44、樂觀 0.02；PHQ-9=13、GAD-7=10。
💼 行為：抽菸 never、酒 0.8u/週、運動 3/週、睡眠 5.8h (普通)、健康識讀=中、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.60（神經質/憂鬱影響）。
💊 治療：nsaid_oral（強度 0.26）, physiotherapy（強度 0.17），共漏吃 31 天。
🎲 生活事件：physical_overuse, cold_winter, physical_overuse, physical_overuse, physical_overuse。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Psoriatic Arthritis (`psoriatic_arthritis`)


### PsA_0064 — MAE 0.100
- 58 歲 M, subtype=poly, responder=typical
```
📋 患者畫像：58 歲 男性，診斷為 psoriatic_arthritis（poly 亞型），被分類為 典型反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持高、居住alone；學歷大專、高收收入、保險健保+私保、全職、都會地區。
🧠 人格/心理：盡責性 0.50、神經質 0.28、樂觀 0.72；PHQ-9=11、GAD-7=7。
💼 行為：抽菸 current、酒 1.8u/週、運動 0/週、睡眠 8.4h (普通)、健康識讀=中、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.55（神經質/憂鬱影響）。
💊 治療：methotrexate（強度 0.49）, nsaid（強度 0.26），共漏吃 28 天。
🎲 生活事件：skin_flare。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 7 個 flare 窗口，模型預警 2 個，召回率 14%、準確率 50%。
📝 結論：典型病程，持續追蹤即可。
```

### PsA_0036 — MAE 0.101
- 48 歲 M, subtype=poly, responder=non_responder
```
📋 患者畫像：48 歲 男性，診斷為 psoriatic_arthritis（poly 亞型），被分類為 無反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持高、居住with_family；學歷高中職、高收收入、保險健保+私保、自雇、都會地區。
🧠 人格/心理：盡責性 0.42、神經質 0.56、樂觀 0.53；PHQ-9=8、GAD-7=1。
💼 行為：抽菸 former、酒 11.5u/週、運動 2/週、睡眠 7.4h (普通)、健康識讀=中、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.52（神經質/憂鬱影響）。
💊 治療：methotrexate（強度 0.04），共漏吃 13 天。
🎲 生活事件：skin_flare, skin_flare, stress_major, stress_major。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際有 3 個 flare 但模型未預警 — 可能因為亞型/反應者組合在此 cohort 中較罕見。
📌 可能觸發因子：實際 flare 附近出現 stress_major(d134), stress_major(d166)。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

### PsA_0014 — MAE 0.103
- 49 歲 F, subtype=poly, responder=typical
```
📋 患者畫像：49 歲 女性，診斷為 psoriatic_arthritis（poly 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持高、居住with_family；學歷大專、中下收入、保險健保_only、兼職、都會地區。
🧠 人格/心理：盡責性 0.46、神經質 0.17、樂觀 0.37；PHQ-9=6、GAD-7=1。
💼 行為：抽菸 never、酒 1.0u/週、運動 4/週、睡眠 10.1h (普通)、健康識讀=高、使用中醫=是。
💊 治療：methotrexate（強度 0.63）, nsaid（強度 0.35），共漏吃 12 天。
🎲 生活事件：skin_flare。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Rheumatoid Arthritis (`rheumatoid_arthritis`)


### RA_0149 — MAE 0.100
- 79 歲 F, subtype=seropositive, responder=partial
```
📋 患者畫像：79 歲 女性，診斷為 類風濕關節炎（seropositive 亞型），被分類為 部分反應者。
🏠 家庭/社經：喪偶、子女 2 位、家庭支持中、居住with_family；學歷高中職、高收收入、保險健保+私保、退休、鄉村地區。
🧠 人格/心理：盡責性 0.71、神經質 0.43、樂觀 0.48；PHQ-9=1、GAD-7=1。
💼 行為：抽菸 never、酒 0.0u/週、運動 2/週、睡眠 7.3h (普通)、健康識讀=高、使用中醫=是。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：ckd。
💊 治療：methotrexate（強度 0.24）, tnf_inhibitor（強度 0.21）, nsaid（強度 0.10），共漏吃 29 天。
🎲 生活事件：seasonal_change, seasonal_change, seasonal_change, travel_jetlag, seasonal_change 等共 6 件。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 7 個 flare 窗口，模型預警 1 個，召回率 14%、準確率 100%。
📌 可能觸發因子：實際 flare 附近出現 seasonal_change(d96)。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### RA_0040 — MAE 0.112
- 63 歲 F, subtype=seronegative, responder=typical
```
📋 患者畫像：63 歲 女性，診斷為 類風濕關節炎（seronegative 亞型），被分類為 典型反應者。
🏠 家庭/社經：未婚、子女 0 位、家庭支持中、居住alone；學歷大專、低收收入、保險健保+企業團保、全職、城鎮地區。
🧠 人格/心理：盡責性 0.34、神經質 0.74、樂觀 0.70；PHQ-9=6、GAD-7=8。
💼 行為：抽菸 never、酒 1.2u/週、運動 1/週、睡眠 8.5h (佳)、健康識讀=高、使用中醫=是。
💊 治療：未接受任何處方治療。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 20 個 flare 窗口，模型預警 20 個，召回率 80%、準確率 80%。
📝 結論：典型病程，持續追蹤即可。
```

### RA_0061 — MAE 0.114
- 75 歲 F, subtype=seronegative, responder=typical
```
📋 患者畫像：75 歲 女性，診斷為 類風濕關節炎（seronegative 亞型），被分類為 典型反應者。
🏠 家庭/社經：喪偶、子女 1 位、家庭支持中、居住alone；學歷國中以下、中上收入、保險健保_only、自雇、城鎮地區。
🧠 人格/心理：盡責性 0.56、神經質 0.54、樂觀 0.51；PHQ-9=5、GAD-7=4。
💼 行為：抽菸 never、酒 0.2u/週、運動 5/週、睡眠 8.1h (佳)、健康識讀=低、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.65（神經質/憂鬱影響）。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 7 項，自動疊加共病：hypertension, ckd。
💊 治療：tnf_inhibitor（強度 0.41），共漏吃 24 天。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

## Sjögren's Syndrome (`sjogren_syndrome`)


### Sjogren_0141 — MAE 0.084
- 89 歲 F, subtype=primary, responder=typical
```
📋 患者畫像：89 歲 女性，診斷為 sjogren_syndrome（primary 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持中、居住with_family；學歷國中以下、中等收入、保險健保_only、兼職、都會地區。
🧠 人格/心理：盡責性 0.61、神經質 0.51、樂觀 0.76；PHQ-9=6、GAD-7=6。
💼 行為：抽菸 former、酒 0.3u/週、運動 3/週、睡眠 7.3h (佳)、健康識讀=低、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.46（神經質/憂鬱影響）、漏吃藥風險 ×1.76。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：osteoarthritis。
💊 治療：hydroxychloroquine（強度 0.42），共漏吃 31 天。
🎲 生活事件：dry_environment, dry_environment, dry_environment, dry_environment, dry_environment 等共 11 件。
🤖 AI 預測表現：活動度 MAE = 0.08，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### Sjogren_0100 — MAE 0.087
- 57 歲 F, subtype=secondary, responder=typical
```
📋 患者畫像：57 歲 女性，診斷為 sjogren_syndrome（secondary 亞型），被分類為 典型反應者。
🏠 家庭/社經：離婚、子女 2 位、家庭支持高、居住alone；學歷高中職、中等收入、保險健保_only、自雇、都會地區。
🧠 人格/心理：盡責性 0.54、神經質 0.67、樂觀 0.43；PHQ-9=5、GAD-7=6。
💼 行為：抽菸 never、酒 0.6u/週、運動 1/週、睡眠 5.4h (普通)、健康識讀=低、使用中醫=否。
⚖️ 模型考量：主觀症狀放大 ×1.59（神經質/憂鬱影響）。
💊 治療：未接受任何處方治療。
🎲 生活事件：viral_infection, dry_environment, dry_environment。
🤖 AI 預測表現：活動度 MAE = 0.09，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### Sjogren_0049 — MAE 0.088
- 64 歲 F, subtype=secondary, responder=typical
```
📋 患者畫像：64 歲 女性，診斷為 sjogren_syndrome（secondary 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 4 位、家庭支持高、居住with_family；學歷高中職、低收收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.73、神經質 0.85、樂觀 0.47；PHQ-9=13、GAD-7=4。
💼 行為：抽菸 current、酒 1.1u/週、運動 2/週、睡眠 4.9h (普通)、健康識讀=中、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.95（神經質/憂鬱影響）。
💊 治療：artificial_tears（強度 0.20）, hydroxychloroquine（強度 0.28），共漏吃 16 天。
🎲 生活事件：dry_environment, dry_environment, dry_environment, dry_environment, dry_environment 等共 9 件。
🤖 AI 預測表現：活動度 MAE = 0.09，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Systemic Lupus Erythematosus (`systemic_lupus_erythematosus`)


### SLE_0191 — MAE 0.146
- 63 歲 F, subtype=renal, responder=typical
```
📋 患者畫像：63 歲 女性，診斷為 systemic_lupus_erythematosus（renal 亞型），被分類為 典型反應者。
🏠 家庭/社經：已婚、子女 2 位、家庭支持中、居住with_family；學歷國中以下、高收收入、保險健保+私保、全職、都會地區。
🧠 人格/心理：盡責性 0.64、神經質 0.11、樂觀 0.67；PHQ-9=2、GAD-7=0。
💼 行為：抽菸 never、酒 0.4u/週、運動 2/週、睡眠 6.8h (普通)、健康識讀=中、使用中醫=否。
💊 治療：hydroxychloroquine（強度 0.52）, mycophenolate（強度 0.59），共漏吃 38 天。
🎲 生活事件：viral_infection, viral_infection, uv_exposure, stress_major。
🤖 AI 預測表現：活動度 MAE = 0.15，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 18 個 flare 窗口，模型預警 9 個，召回率 44%、準確率 89%。
📌 可能觸發因子：實際 flare 附近出現 stress_major(d149)。
📝 結論：典型病程，持續追蹤即可。
```

### SLE_0120 — MAE 0.152
- 55 歲 F, subtype=hematologic, responder=super
```
📋 患者畫像：55 歲 女性，診斷為 systemic_lupus_erythematosus（hematologic 亞型），被分類為 超級反應者。
🏠 家庭/社經：喪偶、子女 0 位、家庭支持低、居住with_family；學歷大專、中下收入、保險健保_only、全職、城鎮地區。
🧠 人格/心理：盡責性 0.54、神經質 0.29、樂觀 0.53；PHQ-9=6、GAD-7=2。
💼 行為：抽菸 former、酒 3.1u/週、運動 2/週、睡眠 8.2h (普通)、健康識讀=高、使用中醫=是。
💊 治療：hydroxychloroquine（強度 0.47）, mycophenolate（強度 0.74）, prednisone（強度 1.23），並在第 57 天停藥。
🎲 生活事件：uv_exposure, uv_exposure。
🤖 AI 預測表現：活動度 MAE = 0.15，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 10 個 flare 窗口，模型預警 7 個，召回率 60%、準確率 86%。
📝 結論：超級反應者，當前治療可維持。
```

### SLE_0039 — MAE 0.152
- 24 歲 F, subtype=cutaneous, responder=partial
```
📋 患者畫像：24 歲 女性，診斷為 systemic_lupus_erythematosus（cutaneous 亞型），被分類為 部分反應者。
🏠 家庭/社經：已婚、子女 1 位、家庭支持高、居住with_family；學歷高中職、中下收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.24、神經質 0.49、樂觀 0.78；PHQ-9=0、GAD-7=0。
💼 行為：抽菸 never、酒 1.0u/週、運動 3/週、睡眠 6.7h (佳)、健康識讀=中、使用中醫=是。
💊 治療：hydroxychloroquine（強度 0.55），共漏吃 5 天。
🎲 生活事件：menstruation, uv_exposure, menstruation, stress_major, menstruation 等共 11 件。
🤖 AI 預測表現：活動度 MAE = 0.15，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型發出 2 個誤警，實際未發生 flare — 可能受到夜間活動度高峰或 life event 訊號干擾。
📝 結論：典型病程，持續追蹤即可。
```

## Systemic Sclerosis (`systemic_sclerosis`)


### SSc_0039 — MAE 0.056
- 41 歲 F, subtype=diffuse, responder=partial
```
📋 患者畫像：41 歲 女性，診斷為 全身性硬化症（diffuse 亞型），被分類為 部分反應者。
🏠 家庭/社經：離婚、子女 2 位、家庭支持高、居住alone；學歷高中職、中等收入、保險健保_only、全職、城鎮地區。
🧠 人格/心理：盡責性 0.29、神經質 0.49、樂觀 0.78；PHQ-9=5、GAD-7=5。
💼 行為：抽菸 never、酒 1.0u/週、運動 3/週、睡眠 6.7h (佳)、健康識讀=低、使用中醫=是。
💊 治療：未接受任何處方治療。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### SSc_0149 — MAE 0.058
- 62 歲 F, subtype=limited, responder=non_responder
```
📋 患者畫像：62 歲 女性，診斷為 全身性硬化症（limited 亞型），被分類為 無反應者。
🏠 家庭/社經：離婚、子女 3 位、家庭支持高、居住with_family；學歷大專、低收收入、保險健保+企業團保、家管、城鎮地區。
🧠 人格/心理：盡責性 0.45、神經質 0.58、樂觀 0.48；PHQ-9=13、GAD-7=5。
💼 行為：抽菸 never、酒 0.2u/週、運動 3/週、睡眠 5.9h (普通)、健康識讀=中、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.83（神經質/憂鬱影響）。
💊 治療：ccb_vasodilator（強度 0.05），共漏吃 11 天。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

### SSc_0142 — MAE 0.058
- 42 歲 F, subtype=limited, responder=super
```
📋 患者畫像：42 歲 女性，診斷為 全身性硬化症（limited 亞型），被分類為 超級反應者。
🏠 家庭/社經：已婚、子女 0 位、家庭支持中、居住with_family；學歷大專、中等收入、保險健保_only、全職、都會地區。
🧠 人格/心理：盡責性 0.34、神經質 0.63、樂觀 0.74；PHQ-9=8、GAD-7=3。
💼 行為：抽菸 never、酒 1.2u/週、運動 0/週、睡眠 9.6h (差)、健康識讀=中、使用中醫=是。
⚖️ 模型考量：主觀症狀放大 ×1.70（神經質/憂鬱影響）。
💊 治療：ccb_vasodilator（強度 0.52），共漏吃 12 天。
🎲 生活事件：cold_winter, cold_winter。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：超級反應者，當前治療可維持。
```