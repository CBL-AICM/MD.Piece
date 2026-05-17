# 5. 代表性患者樣本（每疾病 k=3）

（依模型 MAE 由低到高排序，呈現模型對各疾病最有把握的案例）


## ANCA-associated Vasculitis (`anca_vasculitis`)


### AAV_0068 — MAE 0.103
- 57 歲 F, subtype=mpa, responder=typical
```
📋 患者畫像：57 歲 女性，診斷為 anca_vasculitis（mpa 亞型），被分類為 典型反應者。
💊 治療：rituximab（強度 1.53）, azathioprine（強度 0.50）, prednisone（強度 0.43），並在第 179 天停藥。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### AAV_0041 — MAE 0.104
- 83 歲 F, subtype=mpa, responder=partial
```
📋 患者畫像：83 歲 女性，診斷為 anca_vasculitis（mpa 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 6 項，自動疊加共病：hypertension, osteoarthritis。
💊 治療：prednisone（強度 0.19），共漏吃 26 天。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### AAV_0082 — MAE 0.105
- 68 歲 M, subtype=gpa, responder=partial
```
📋 患者畫像：68 歲 男性，診斷為 anca_vasculitis（gpa 亞型），被分類為 部分反應者。
💊 治療：rituximab（強度 0.55），共漏吃 19 天。
🎲 生活事件：infection。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Ankylosing Spondylitis (`ankylosing_spondylitis`)


### AS_0034 — MAE 0.108
- 31 歲 M, subtype=axial_only, responder=super
```
📋 患者畫像：31 歲 男性，診斷為 ankylosing_spondylitis（axial_only 亞型），被分類為 超級反應者。
💊 治療：nsaid（強度 0.41），共漏吃 16 天。
🎲 生活事件：prolonged_sitting, physical_overuse, prolonged_sitting, prolonged_sitting, physical_overuse 等共 15 件。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：超級反應者，當前治療可維持。
```

### AS_0115 — MAE 0.114
- 49 歲 M, subtype=axial_only, responder=partial
```
📋 患者畫像：49 歲 男性，診斷為 ankylosing_spondylitis（axial_only 亞型），被分類為 部分反應者。
💊 治療：nsaid（強度 0.28）, physiotherapy（強度 0.10），共漏吃 46 天。
🎲 生活事件：physical_overuse, cold_winter, prolonged_sitting, prolonged_sitting, prolonged_sitting 等共 17 件。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型發出 2 個誤警，實際未發生 flare — 可能受到夜間活動度高峰或 life event 訊號干擾。
📝 結論：典型病程，持續追蹤即可。
```

### AS_0024 — MAE 0.115
- 43 歲 M, subtype=axial_only, responder=typical
```
📋 患者畫像：43 歲 男性，診斷為 ankylosing_spondylitis（axial_only 亞型），被分類為 典型反應者。
💊 治療：physiotherapy（強度 0.52），共漏吃 17 天。
🎲 生活事件：prolonged_sitting, prolonged_sitting, prolonged_sitting, prolonged_sitting, prolonged_sitting 等共 12 件。
🤖 AI 預測表現：活動度 MAE = 0.12，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際有 4 個 flare 但模型未預警 — 可能因為亞型/反應者組合在此 cohort 中較罕見。
📌 可能觸發因子：實際 flare 附近出現 cold_winter(d88), physical_overuse(d170)。
📝 結論：典型病程，持續追蹤即可。
```

## Asthma (`asthma`)


### Asthma_0090 — MAE 0.307
- 84 歲 M, subtype=eosinophilic, responder=partial
```
📋 患者畫像：84 歲 男性，診斷為 氣喘（eosinophilic 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 7 項，自動疊加共病：hypertension, osteoarthritis, cataract。
💊 治療：ics（強度 0.78）, saba_rescue（強度 0.89），共漏吃 81 天。
🎲 生活事件：smoke_exposure。
🤖 AI 預測表現：活動度 MAE = 0.31，接近 cohort 平均（0.26）。
🔍 Flare 預測：實際有 3 個 flare 但模型未預警 — 可能因為亞型/反應者組合在此 cohort 中較罕見。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### Asthma_0080 — MAE 0.315
- 76 歲 F, subtype=neutrophilic, responder=typical
```
📋 患者畫像：76 歲 女性，診斷為 氣喘（neutrophilic 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 10 項，自動疊加共病：hypertension, diabetes_t2, osteoarthritis。
💊 治療：laba（強度 0.56）, saba_rescue（強度 0.61），並在第 71 天停藥。
🤖 AI 預測表現：活動度 MAE = 0.32，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### Asthma_0002 — MAE 0.329
- 74 歲 M, subtype=neutrophilic, responder=typical
```
📋 患者畫像：74 歲 男性，診斷為 氣喘（neutrophilic 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 3 項，自動疊加共病：diabetes_t2, osteoarthritis。
💊 治療：saba_rescue（強度 0.67），並在第 76 天停藥。
🎲 生活事件：viral_uri, thunderstorm。
🤖 AI 預測表現：活動度 MAE = 0.33，接近 cohort 平均（0.26）。
🔍 Flare 預測：實際 7 個 flare 窗口，模型預警 3 個，召回率 14%、準確率 33%。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

## Behçet's Disease (`behcet_disease`)


### Behcet_0115 — MAE 0.097
- 49 歲 F, subtype=mucocutaneous, responder=partial
```
📋 患者畫像：49 歲 女性，診斷為 behcet_disease（mucocutaneous 亞型），被分類為 部分反應者。
💊 治療：colchicine（強度 0.25）, prednisone（強度 0.37），共漏吃 55 天。
🎲 生活事件：oral_trauma, viral_infection。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### Behcet_0013 — MAE 0.097
- 53 歲 F, subtype=ocular, responder=partial
```
📋 患者畫像：53 歲 女性，診斷為 behcet_disease（ocular 亞型），被分類為 部分反應者。
💊 治療：colchicine（強度 0.25）, azathioprine（強度 0.29），共漏吃 50 天。
🎲 生活事件：oral_trauma, oral_trauma。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### Behcet_0111 — MAE 0.100
- 47 歲 F, subtype=ocular, responder=partial
```
📋 患者畫像：47 歲 女性，診斷為 behcet_disease（ocular 亞型），被分類為 部分反應者。
💊 治療：colchicine（強度 0.28），並在第 89 天停藥。
🎲 生活事件：oral_trauma, oral_trauma, oral_trauma, oral_trauma, oral_trauma 等共 7 件。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Chronic Spontaneous Urticaria (`chronic_urticaria`)


### CSU_0106 — MAE 0.186
- 87 歲 F, subtype=spontaneous, responder=partial
```
📋 患者畫像：87 歲 女性，診斷為 chronic_urticaria（spontaneous 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：cataract。
💊 治療：h1_antihistamine（強度 0.35），共漏吃 34 天。
🎲 生活事件：nsaid_use, nsaid_use, nsaid_use, nsaid_use。
🤖 AI 預測表現：活動度 MAE = 0.19，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### CSU_0052 — MAE 0.194
- 84 歲 F, subtype=spontaneous, responder=non_responder
```
📋 患者畫像：84 歲 女性，診斷為 chronic_urticaria（spontaneous 亞型），被分類為 無反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 5 項，自動疊加共病：hypertension, diabetes_t2, osteoarthritis, cataract。
💊 治療：h1_antihistamine（強度 0.13），共漏吃 36 天。
🎲 生活事件：nsaid_use, viral_infection, nsaid_use, nsaid_use。
🤖 AI 預測表現：活動度 MAE = 0.19，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

### CSU_0003 — MAE 0.225
- 53 歲 F, subtype=inducible, responder=super
```
📋 患者畫像：53 歲 女性，診斷為 chronic_urticaria（inducible 亞型），被分類為 超級反應者。
💊 治療：h1_antihistamine（強度 1.14），並在第 132 天停藥。
🎲 生活事件：nsaid_use, nsaid_use, emotional_stress_major, nsaid_use, viral_infection。
🤖 AI 預測表現：活動度 MAE = 0.22，接近 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：超級反應者，當前治療可維持。
```

## Gout (`gout`)


### Gout_0187 — MAE 0.166
- 83 歲 F, subtype=chronic_tophaceous, responder=typical
```
📋 患者畫像：83 歲 女性，診斷為 gout（chronic_tophaceous 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 5 項，自動疊加共病：diabetes_t2, cataract。
💊 治療：colchicine（強度 0.52）, nsaid（強度 0.51），共漏吃 71 天。
🎲 生活事件：dehydration, purine_meal, dehydration, purine_meal, purine_meal 等共 13 件。
🤖 AI 預測表現：活動度 MAE = 0.17，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### Gout_0037 — MAE 0.166
- 81 歲 M, subtype=intermittent, responder=typical
```
📋 患者畫像：81 歲 男性，診斷為 gout（intermittent 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：hypertension, osteoarthritis。
💊 治療：febuxostat（強度 0.38）, nsaid（強度 0.52），並在第 165 天停藥。
🎲 生活事件：purine_meal, purine_meal, alcohol_binge, purine_meal, dehydration 等共 13 件。
🤖 AI 預測表現：活動度 MAE = 0.17，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### Gout_0181 — MAE 0.173
- 88 歲 M, subtype=intermittent, responder=partial
```
📋 患者畫像：88 歲 男性，診斷為 gout（intermittent 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 7 項，自動疊加共病：hypertension, cataract。
💊 治療：allopurinol（強度 0.31）, colchicine（強度 0.46）, nsaid（強度 0.32），共漏吃 103 天。
🎲 生活事件：purine_meal, dehydration, purine_meal, surgery, alcohol_binge 等共 17 件。
🤖 AI 預測表現：活動度 MAE = 0.17，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際有 7 個 flare 但模型未預警 — 可能因為亞型/反應者組合在此 cohort 中較罕見。
📌 可能觸發因子：實際 flare 附近出現 surgery(d52), alcohol_binge(d54)。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

## Idiopathic Pulmonary Fibrosis (`idiopathic_pulmonary_fibrosis`)


### IPF_0056 — MAE 0.051
- 65 歲 F, subtype=rapid_progressor, responder=typical
```
📋 患者畫像：65 歲 女性，診斷為 idiopathic_pulmonary_fibrosis（rapid_progressor 亞型），被分類為 典型反應者。
💊 治療：未接受任何處方治療。
🎲 生活事件：infection, hospitalization。
🤖 AI 預測表現：活動度 MAE = 0.05，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### IPF_0172 — MAE 0.053
- 86 歲 M, subtype=slow_progressor, responder=typical
```
📋 患者畫像：86 歲 男性，診斷為 idiopathic_pulmonary_fibrosis（slow_progressor 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 3 項，自動疊加共病：hypertension, osteoarthritis, cataract。
💊 治療：nintedanib（強度 0.42）, pirfenidone（強度 0.37），共漏吃 30 天。
🎲 生活事件：infection。
🤖 AI 預測表現：活動度 MAE = 0.05，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### IPF_0142 — MAE 0.053
- 77 歲 M, subtype=slow_progressor, responder=non_responder
```
📋 患者畫像：77 歲 男性，診斷為 idiopathic_pulmonary_fibrosis（slow_progressor 亞型），被分類為 無反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 5 項，自動疊加共病：ckd。
💊 治療：nintedanib（強度 0.09），共漏吃 16 天。
🤖 AI 預測表現：活動度 MAE = 0.05，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：作為 non-responder，建議考慮替代治療策略。
```

## IgG4-Related Disease (`igg4_related_disease`)


### IgG4RD_0084 — MAE 0.070
- 69 歲 M, subtype=systemic, responder=typical
```
📋 患者畫像：69 歲 男性，診斷為 igg4_related_disease（systemic 亞型），被分類為 典型反應者。
💊 治療：prednisone（強度 0.85）, azathioprine（強度 0.45），共漏吃 28 天。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### IgG4RD_0003 — MAE 0.071
- 88 歲 M, subtype=systemic, responder=typical
```
📋 患者畫像：88 歲 男性，診斷為 igg4_related_disease（systemic 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：ckd。
💊 治療：未接受任何處方治療。
🎲 生活事件：imaging_finding。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### IgG4RD_0153 — MAE 0.073
- 67 歲 M, subtype=retroperitoneal, responder=partial
```
📋 患者畫像：67 歲 男性，診斷為 igg4_related_disease（retroperitoneal 亞型），被分類為 部分反應者。
💊 治療：prednisone（強度 0.44）, rituximab（強度 0.43），共漏吃 33 天。
🎲 生活事件：infection, infection。
🤖 AI 預測表現：活動度 MAE = 0.07，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Inflammatory Bowel Disease (`inflammatory_bowel_disease`)


### IBD_0127 — MAE 0.110
- 52 歲 F, subtype=crohn, responder=typical
```
📋 患者畫像：52 歲 女性，診斷為 inflammatory_bowel_disease（crohn 亞型），被分類為 典型反應者。
💊 治療：mesalazine（強度 0.63）, prednisone（強度 0.79），共漏吃 51 天。
🎲 生活事件：nsaid_use, dietary_indiscretion, dietary_indiscretion, dietary_indiscretion, dietary_indiscretion 等共 11 件。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際有 2 個 flare 但模型未預警 — 可能因為亞型/反應者組合在此 cohort 中較罕見。
📌 可能觸發因子：實際 flare 附近出現 dietary_indiscretion(d168), dietary_indiscretion(d169), infection(d176)。
📝 結論：典型病程，持續追蹤即可。
```

### IBD_0148 — MAE 0.111
- 77 歲 F, subtype=uc, responder=typical
```
📋 患者畫像：77 歲 女性，診斷為 inflammatory_bowel_disease（uc 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 10 項，自動疊加共病：hypertension, ckd, cataract。
💊 治療：anti_tnf（強度 0.62），共漏吃 24 天。
🎲 生活事件：nsaid_use, dietary_indiscretion, nsaid_use, dietary_indiscretion。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### IBD_0174 — MAE 0.112
- 83 歲 F, subtype=crohn, responder=super
```
📋 患者畫像：83 歲 女性，診斷為 inflammatory_bowel_disease（crohn 亞型），被分類為 超級反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 6 項，自動疊加共病：hypertension, cataract。
💊 治療：mesalazine（強度 0.74），共漏吃 22 天。
🎲 生活事件：dietary_indiscretion, nsaid_use, dietary_indiscretion, dietary_indiscretion, dietary_indiscretion 等共 6 件。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：超級反應者，當前治療可維持。
```

## Multiple Sclerosis (`multiple_sclerosis`)


### MS_0130 — MAE 0.082
- 39 歲 M, subtype=rrms, responder=typical
```
📋 患者畫像：39 歲 男性，診斷為 multiple_sclerosis（rrms 亞型），被分類為 典型反應者。
💊 治療：未接受任何處方治療。
🎲 生活事件：viral_infection。
🤖 AI 預測表現：活動度 MAE = 0.08，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### MS_0019 — MAE 0.082
- 36 歲 M, subtype=rrms, responder=partial
```
📋 患者畫像：36 歲 男性，診斷為 multiple_sclerosis（rrms 亞型），被分類為 部分反應者。
💊 治療：未接受任何處方治療。
🎲 生活事件：heat_exposure, heat_exposure。
🤖 AI 預測表現：活動度 MAE = 0.08，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### MS_0024 — MAE 0.082
- 43 歲 M, subtype=rrms, responder=typical
```
📋 患者畫像：43 歲 男性，診斷為 multiple_sclerosis（rrms 亞型），被分類為 典型反應者。
💊 治療：ocrelizumab（強度 0.67），共漏吃 12 天。
🎲 生活事件：heat_exposure, heat_exposure, heat_exposure。
🤖 AI 預測表現：活動度 MAE = 0.08，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Osteoarthritis (`osteoarthritis`)


### OA_0092 — MAE 0.058
- 74 歲 M, subtype=knee, responder=partial
```
📋 患者畫像：74 歲 男性，診斷為 osteoarthritis（knee 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：hypertension, diabetes_t2, ckd, osteoarthritis。
💊 治療：acetaminophen（強度 0.14）, nsaid_topical（強度 0.15）, physiotherapy（強度 0.05），並在第 154 天停藥。
🎲 生活事件：cold_winter, injury_minor, physical_overuse, cold_winter。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### OA_0123 — MAE 0.061
- 84 歲 M, subtype=knee, responder=partial
```
📋 患者畫像：84 歲 男性，診斷為 osteoarthritis（knee 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 3 項，自動疊加共病：cataract。
💊 治療：acetaminophen（強度 0.15）, nsaid_topical（強度 0.11），共漏吃 51 天。
🎲 生活事件：physical_overuse, physical_overuse, physical_overuse。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### OA_0141 — MAE 0.061
- 89 歲 F, subtype=hip, responder=partial
```
📋 患者畫像：89 歲 女性，診斷為 osteoarthritis（hip 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：osteoarthritis。
💊 治療：acetaminophen（強度 0.17）, nsaid_oral（強度 0.20），共漏吃 55 天。
🎲 生活事件：physical_overuse, physical_overuse, physical_overuse。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

## Psoriatic Arthritis (`psoriatic_arthritis`)


### PsA_0025 — MAE 0.101
- 38 歲 M, subtype=oligo, responder=partial
```
📋 患者畫像：38 歲 男性，診斷為 psoriatic_arthritis（oligo 亞型），被分類為 部分反應者。
💊 治療：nsaid（強度 0.11），共漏吃 20 天。
🎲 生活事件：skin_flare, trauma_koebner, trauma_koebner。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### PsA_0109 — MAE 0.101
- 46 歲 M, subtype=poly, responder=partial
```
📋 患者畫像：46 歲 男性，診斷為 psoriatic_arthritis（poly 亞型），被分類為 部分反應者。
💊 治療：nsaid（強度 0.16），共漏吃 14 天。
🎲 生活事件：trauma_koebner, trauma_koebner。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### PsA_0147 — MAE 0.102
- 63 歲 F, subtype=axial, responder=partial
```
📋 患者畫像：63 歲 女性，診斷為 psoriatic_arthritis（axial 亞型），被分類為 部分反應者。
💊 治療：methotrexate（強度 0.19）, nsaid（強度 0.08），共漏吃 38 天。
🎲 生活事件：trauma_koebner, skin_flare。
🤖 AI 預測表現：活動度 MAE = 0.10，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Rheumatoid Arthritis (`rheumatoid_arthritis`)


### RA_0106 — MAE 0.109
- 87 歲 F, subtype=seropositive, responder=partial
```
📋 患者畫像：87 歲 女性，診斷為 類風濕關節炎（seropositive 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：cataract。
💊 治療：methotrexate（強度 0.21）, nsaid（強度 0.11）, prednisone（強度 0.08），共漏吃 67 天。
🎲 生活事件：seasonal_change, seasonal_change。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### RA_0171 — MAE 0.110
- 61 歲 F, subtype=seropositive, responder=typical
```
📋 患者畫像：61 歲 女性，診斷為 類風濕關節炎（seropositive 亞型），被分類為 典型反應者。
💊 治療：methotrexate（強度 0.94）, nsaid（強度 0.23），共漏吃 43 天。
🎲 生活事件：job_loss。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### RA_0040 — MAE 0.111
- 63 歲 F, subtype=seropositive, responder=super
```
📋 患者畫像：63 歲 女性，診斷為 類風濕關節炎（seropositive 亞型），被分類為 超級反應者。
💊 治療：nsaid（強度 0.24），共漏吃 21 天。
🎲 生活事件：viral_infection, seasonal_change, seasonal_change, seasonal_change。
🤖 AI 預測表現：活動度 MAE = 0.11，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 33 個 flare 窗口，模型預警 18 個，召回率 55%、準確率 100%。
📌 可能觸發因子：實際 flare 附近出現 viral_infection(d132), seasonal_change(d148), seasonal_change(d169)。
📝 結論：超級反應者，當前治療可維持。
```

## Sjögren's Syndrome (`sjogren_syndrome`)


### Sjogren_0131 — MAE 0.085
- 63 歲 F, subtype=secondary, responder=typical
```
📋 患者畫像：63 歲 女性，診斷為 sjogren_syndrome（secondary 亞型），被分類為 典型反應者。
💊 治療：artificial_tears（強度 0.08）, hydroxychloroquine（強度 0.39），共漏吃 37 天。
🎲 生活事件：dry_environment, viral_infection, dry_environment, dry_environment, dry_environment 等共 7 件。
🤖 AI 預測表現：活動度 MAE = 0.09，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### Sjogren_0139 — MAE 0.086
- 45 歲 F, subtype=secondary, responder=partial
```
📋 患者畫像：45 歲 女性，診斷為 sjogren_syndrome（secondary 亞型），被分類為 部分反應者。
💊 治療：hydroxychloroquine（強度 0.19），共漏吃 12 天。
🎲 生活事件：dry_environment, dry_environment, dry_environment, dry_environment, dry_environment 等共 6 件。
🤖 AI 預測表現：活動度 MAE = 0.09，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### Sjogren_0078 — MAE 0.086
- 68 歲 F, subtype=primary, responder=partial
```
📋 患者畫像：68 歲 女性，診斷為 sjogren_syndrome（primary 亞型），被分類為 部分反應者。
💊 治療：未接受任何處方治療。
🎲 生活事件：dry_environment, dry_environment, dry_environment, viral_infection, dry_environment 等共 9 件。
🤖 AI 預測表現：活動度 MAE = 0.09，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

## Systemic Lupus Erythematosus (`systemic_lupus_erythematosus`)


### SLE_0081 — MAE 0.124
- 73 歲 F, subtype=renal, responder=typical
```
📋 患者畫像：73 歲 女性，診斷為 systemic_lupus_erythematosus（renal 亞型），被分類為 典型反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 5 項，自動疊加共病：hypertension。
💊 治療：hydroxychloroquine（強度 0.41）, prednisone（強度 0.44），共漏吃 42 天。
🎲 生活事件：uv_exposure, stress_major。
🤖 AI 預測表現：活動度 MAE = 0.12，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### SLE_0106 — MAE 0.133
- 87 歲 F, subtype=cutaneous, responder=partial
```
📋 患者畫像：87 歲 女性，診斷為 systemic_lupus_erythematosus（cutaneous 亞型），被分類為 部分反應者。
👴 老年機制觸發：CRP 反應遲鈍至 0.6×、治療反應修正 0.6×、伴隨用藥 4 項，自動疊加共病：cataract。
💊 治療：hydroxychloroquine（強度 0.26）, prednisone（強度 0.33），共漏吃 41 天。
🎲 生活事件：uv_exposure, uv_exposure, uv_exposure, uv_exposure。
🤖 AI 預測表現：活動度 MAE = 0.13，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：老年患者，建議監測共病與藥物交互作用。
```

### SLE_0197 — MAE 0.133
- 41 歲 F, subtype=neuro, responder=super
```
📋 患者畫像：41 歲 女性，診斷為 systemic_lupus_erythematosus（neuro 亞型），被分類為 超級反應者。
💊 治療：hydroxychloroquine（強度 0.55），共漏吃 18 天。
🎲 生活事件：uv_exposure, menstruation, stress_major, viral_infection, menstruation 等共 10 件。
🤖 AI 預測表現：活動度 MAE = 0.13，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：實際 62 個 flare 窗口，模型預警 44 個，召回率 61%、準確率 86%。
📌 可能觸發因子：實際 flare 附近出現 menstruation(d16), stress_major(d20), viral_infection(d28)。
📝 結論：超級反應者，當前治療可維持。
```

## Systemic Sclerosis (`systemic_sclerosis`)


### SSc_0114 — MAE 0.059
- 35 歲 M, subtype=limited, responder=typical
```
📋 患者畫像：35 歲 男性，診斷為 全身性硬化症（limited 亞型），被分類為 典型反應者。
💊 治療：未接受任何處方治療。
🎲 生活事件：infection。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### SSc_0119 — MAE 0.059
- 42 歲 F, subtype=diffuse, responder=partial
```
📋 患者畫像：42 歲 女性，診斷為 全身性硬化症（diffuse 亞型），被分類為 部分反應者。
💊 治療：mycophenolate（強度 0.55），共漏吃 9 天。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：典型病程，持續追蹤即可。
```

### SSc_0087 — MAE 0.059
- 51 歲 M, subtype=diffuse, responder=super
```
📋 患者畫像：51 歲 男性，診斷為 全身性硬化症（diffuse 亞型），被分類為 超級反應者。
💊 治療：mycophenolate（強度 1.02）, nintedanib（強度 0.45），共漏吃 30 天。
🎲 生活事件：infection。
🤖 AI 預測表現：活動度 MAE = 0.06，顯著優於 cohort 平均（0.26）。
🔍 Flare 預測：模型預測 90 天內無 flare，與實際一致。
📝 結論：超級反應者，當前治療可維持。
```