# MD.Piece — 3200 虛擬患者註冊與 12 個月使用模擬

*產生時間：2026-06-11T06:12:01.208433+00:00　模擬天數：365 天（12 個月）*

本報告把先前的 3200 位虛擬患者（16 種疾病 × 200，seed=2024）放進虛擬世界，為每人建立社經/家庭/地區/性別/共病背景，讓其中 **1600** 位註冊 MD.Piece 並真實使用 12 個月，模擬包含留存流失、逐功能記錄、忘記吃藥/沒紀錄/中途棄用等真實情境。

## 一、總覽

- 候選患者：**3200** 位；註冊：**1600** 位（註冊率 50.0%）；未註冊：1600 位
- 具至少一項共病：2332 位（72.9%）；其餘為單一慢性病
- 12 個月後仍活躍（engaged@12m）：**981** 位（61.3%）
- 幽靈使用者（註冊卻幾乎不用）：66 位（4.1%）
- 每位註冊者：中位活躍天數 74 天、中位總紀錄 150 筆、中位活躍月數 11 個月
- 平均資料完整度（活躍天/觀察天）：0.236；平均用藥記錄完成率：0.254

## 二、留存曲線（流失定律）

符合數位健康的『流失定律』：多數使用者在前幾週後逐漸流失，只剩穩定核心。
『實質活躍』定義為：該里程碑前後 30 天視窗內 **≥2 次**開啟 App（單次因 flare 偶爾回訪不算）。

- 48 小時內首次開啟 App（onboarding 回訪）：**72.1%**

| 里程碑 | D7 | D30 | D90 | D180 | D365(12個月) |
|---|---|---|---|---|---|
| 仍實質活躍 % | 97.1 | 96.6 | 82.6 | 79.1 | 61.3 |

> 註：註冊者為傾向分數前 50% 的族群（自我選擇效應），故 12 個月留存（61.3%）高於一般自助型 app；反應型使用者會因 flare 反覆回訪亦推升留存。

> 依據(PubMed)：Eysenbach G. *The law of attrition*. J Med Internet Res 2005. [DOI](https://doi.org/10.2196/jmir.7.1.e11)

## 三、使用者原型分布

| 原型 | 人數 | 說明 |
|---|---|---|
| power_user | 188 | 重度使用者：幾乎每天記錄、流失極慢、功能採用廣 |
| steady | 430 | 穩定使用者：每週數次、緩慢衰退 |
| reactive | 426 | 反應型：平時少記，症狀/flare 一來才猛記 |
| casual | 240 | 隨意型：零星使用、衰退較快 |
| early_churner | 250 | 早退型：前幾週用一用就停（真實世界最大宗） |
| ghost | 66 | 幽靈：註冊後幾乎不用 |

## 四、功能採用率（註冊者中曾用過該功能的比例）

| 功能 | 採用率 % |
|---|---|
| 症狀紀錄 (symptoms) | 96.5 |
| 用藥紀錄 (medications) | 66.7 |
| 衛教閱讀 (education) | 66.1 |
| 智慧提醒 (reminders) | 62.3 |
| 回診追蹤 (follow_ups) | 58.7 |
| 情緒追蹤 (emotions) | 58.2 |
| 生理量測 (vitals) | 46.9 |
| 檢驗上傳 (labs) | 42.4 |
| 就診前報告 (reports) | 40.2 |
| 飲食/拍照 (diet) | 39.3 |
| 睡眠紀錄 (sleep) | 37.4 |
| 健康memo (memos) | 35.0 |
| 月經週期 (menstrual) | 22.8 |

## 五、註冊率 × 族群（誰會註冊使用）

**依疾病罕見度**（罕見病患者也照樣使用）：

| 罕見度 | 候選 | 註冊 | 註冊率 % |
|---|---|---|---|
| 常見 | 1200 | 582 | 48.5 |
| 較不常見 | 1000 | 565 | 56.5 |
| 罕見 | 1000 | 453 | 45.3 |

**依好發年齡層**：

| 好發層 | 候選 | 註冊 | 註冊率 % |
|---|---|---|---|
| 年輕 | 1200 | 700 | 58.3 |
| 中年 | 1000 | 535 | 53.5 |
| 老年 | 1000 | 365 | 36.5 |

**依實際年齡層**（高齡註冊率較低，呼應數位落差；部分由家屬代理救回）：

| 年齡層 | 候選 | 註冊 | 註冊率 % |
|---|---|---|---|
| 年輕(<40) | 1063 | 692 | 65.1 |
| 中年(40-59) | 1133 | 618 | 54.5 |
| 老年(≥60) | 1004 | 290 | 28.9 |

**依地區（區域）**：

| 區域 | 候選 | 註冊 | 註冊率 % |
|---|---|---|---|
| 北部 | 1240 | 656 | 52.9 |
| 中部 | 939 | 457 | 48.7 |
| 南部 | 694 | 371 | 53.5 |
| 東部 | 248 | 91 | 36.7 |
| 離島 | 79 | 25 | 31.6 |

**依性別**：

| 性別 | 候選 | 註冊 | 註冊率 % |
|---|---|---|---|
| F | 1840 | 971 | 52.8 |
| M | 1360 | 629 | 46.2 |

## 六、各疾病使用深度（連結 PubMed 實證）

| 疾病 | 罕見度 | 好發層 | 註冊數 | @12m活躍 | 中位紀錄 | 主原型 | PubMed |
|---|---|---|---|---|---|---|---|
| Global epidemiology of rheum | 常見 | 中年 | 92 | 56(60.9%) | 159 | reactive | [36068354](https://doi.org/10.1038/s41584-022-00827-y) |
| Epidemiology of severe asthm | 常見 | 年輕 | 90 | 51(56.7%) | 152 | reactive | [39384302](https://doi.org/10.1183/16000617.0095-2024) |
| Systemic sclerosis | 罕見 | 中年 | 113 | 66(58.4%) | 123 | reactive | [28413064](https://doi.org/10.1016/S0140-6736(17)30933-9) |
| Global epidemiology of syste | 較不常見 | 年輕 | 122 | 78(63.9%) | 163 | steady | [36241363](https://doi.org/10.1136/ard-2022-223035) |
| Worldwide incidence and prev | 常見 | 年輕 | 121 | 75(62.0%) | 150 | reactive | [29050646](https://doi.org/10.1016/S0140-6736(17)32448-0) |
| Epidemiology and Pathophysio | 較不常見 | 年輕 | 113 | 68(60.2%) | 138 | steady | [35938654](https://doi.org/10.1212/CON.0000000000001136) |
| Global epidemiology of gout | 常見 | 老年 | 88 | 51(58.0%) | 162 | reactive | [32541923](https://doi.org/10.1038/s41584-020-0441-1) |
| Ankylosing spondylitis risk  | 較不常見 | 年輕 | 125 | 71(56.8%) | 138 | steady | [33754220](https://doi.org/10.1007/s10067-021-05679-7) |
| Psoriatic arthritis | 較不常見 | 中年 | 109 | 65(59.6%) | 146 | steady | [38857765](https://doi.org/10.1016/j.jaad.2024.03.058) |
| Epidemiology of Sjögren synd | 較不常見 | 中年 | 96 | 58(60.4%) | 154 | steady | [38110617](https://doi.org/10.1038/s41584-023-01057-6) |
| Behçet's Disease, Pathogenes | 罕見 | 年輕 | 129 | 73(56.6%) | 147 | steady | [38674208](https://doi.org/10.3390/medicina60040562) |
| EULAR recommendations for th | 罕見 | 老年 | 83 | 55(66.3%) | 155 | reactive | [36927642](https://doi.org/10.1136/ard-2022-223764) |
| Update on Autoimmune Pancrea | 罕見 | 老年 | 73 | 51(69.9%) | 156 | reactive | [39707927](https://doi.org/10.1002/ueg2.12738) |
| Chronic spontaneous urticari | 常見 | 中年 | 125 | 83(66.4%) | 182 | steady | [40451490](https://doi.org/10.1016/j.jaci.2025.05.019) |
| Osteoarthritis year in revie | 常見 | 老年 | 66 | 41(62.1%) | 154 | steady | [39103081](https://doi.org/10.1016/j.joca.2024.07.014) |
| Idiopathic pulmonary fibrosi | 罕見 | 老年 | 55 | 39(70.9%) | 191 | steady | [37156412](https://doi.org/10.1016/j.lpm.2023.104166) |

## 七、疾病流行病學分類與 PubMed 來源

依下列 PubMed 文獻把 16 種疾病分為罕見/常見、典型/不典型、好發年齡層（資料來源：PubMed）：

### rheumatoid_arthritis（常見・好發中年）
- 盛行率：全球盛行率約 0.5–1%，女性為主。
- 典型：對稱性小關節多發炎、晨僵 >1 小時、RF/anti-CCP 陽性。
- 不典型：血清陰性、老年發病(EORA)以大關節/類風濕多肌痛表現、回紋型風濕症。
- 來源(PubMed)：Global epidemiology of rheumatoid arthritis. *Nat Rev Rheumatol* 2022. PMID 36068354. [DOI](https://doi.org/10.1038/s41584-022-00827-y)

### asthma（常見・好發年輕）
- 盛行率：兒童約 14%、成人數%，全球逾 3 億人；最常見慢性呼吸道病。
- 典型：陣發性喘鳴、夜咳、可逆性呼氣氣流受限。
- 不典型：咳嗽變異型、成人晚發嗜伊紅性、運動誘發、職業型。
- 來源(PubMed)：Epidemiology of severe asthma in children: a systematic review and meta-analysis. *Eur Respir Rev* 2024. PMID 39384302. [DOI](https://doi.org/10.1183/16000617.0095-2024)

### systemic_sclerosis（罕見・好發中年）
- 盛行率：盛行率約 1–2/萬，屬罕見自體免疫病，女性為主。
- 典型：雷諾現象起始、皮膚硬化、ANA/抗 Scl-70/抗著絲點陽性。
- 不典型：無皮膚硬化型(sine scleroderma)、快速進展型、以間質肺病/肺高壓首發。
- 來源(PubMed)：Systemic sclerosis. *Lancet* 2017. PMID 28413064. [DOI](https://doi.org/10.1016/S0140-6736(17)30933-9)

### systemic_lupus_erythematosus（較不常見・好發年輕）
- 盛行率：盛行率約 43–100/10萬；好發育齡女性(女:男 ~9:1)。
- 典型：頰部紅斑、關節炎、腎炎、ANA/抗 dsDNA 陽性、多系統侵犯。
- 不典型：晚發型、男性、單一系統(僅血液/僅腎)、藥物誘發型。
- 來源(PubMed)：Global epidemiology of systemic lupus erythematosus: a comprehensive systematic analysis. *Ann Rheum Dis* 2023. PMID 36241363. [DOI](https://doi.org/10.1136/ard-2022-223035)

### inflammatory_bowel_disease（常見・好發年輕）
- 盛行率：西方盛行率達 0.3–0.7% 並全球上升；好發 15–35 歲，次峰 50–70。
- 典型：慢性腹瀉/血便、腹痛、體重下降、內視鏡黏膜發炎。
- 不典型：以腸外表現(關節/皮膚/眼)首發、老年發病、無症狀型。
- 來源(PubMed)：Worldwide incidence and prevalence of inflammatory bowel disease in the 21st century. *Lancet* 2017. PMID 29050646. [DOI](https://doi.org/10.1016/S0140-6736(17)32448-0)

### multiple_sclerosis（較不常見・好發年輕）
- 盛行率：盛行率約 30–300/10萬，隨緯度上升；好發 20–40 歲女性。
- 典型：復發緩解型、視神經炎/感覺異常、MRI 多發脫髓鞘病灶。
- 不典型：原發進展型(PPMS)、腫瘤樣脫髓鞘、晚發型、脊髓為主。
- 來源(PubMed)：Epidemiology and Pathophysiology of Multiple Sclerosis. *Continuum (Minneap Minn)* 2022. PMID 35938654. [DOI](https://doi.org/10.1212/CON.0000000000001136)

### gout（常見・好發老年）
- 盛行率：盛行率約 1–4%(年長男性可達 5%+)；最常見發炎性關節炎。
- 典型：急性單關節炎(足拇趾)、高尿酸血症、尿酸結晶。
- 不典型：多關節痛風石型、早發型(有家族/腎病)、停經後女性。
- 來源(PubMed)：Global epidemiology of gout: prevalence, incidence, treatment patterns and risk factors. *Nat Rev Rheumatol* 2020. PMID 32541923. [DOI](https://doi.org/10.1038/s41584-020-0441-1)

### ankylosing_spondylitis（較不常見・好發年輕）
- 盛行率：盛行率約 0.1–0.5%；好發 <45 歲(常 20 多歲)男性、HLA-B27。
- 典型：發炎性下背痛、晨僵、薦腸關節炎、活動後改善。
- 不典型：非放射學軸性脊椎關節炎、女性、以周邊關節/葡萄膜炎首發。
- 來源(PubMed)：Ankylosing spondylitis risk factors: a systematic literature review. *Clin Rheumatol* 2021. PMID 33754220. [DOI](https://doi.org/10.1007/s10067-021-05679-7)

### psoriatic_arthritis（較不常見・好發中年）
- 盛行率：盛行率約 0.1–0.25%；乾癬患者約 20–30% 併發，好發 30–50 歲。
- 典型：不對稱寡關節炎、指/趾炎、附著點炎、乾癬病灶。
- 不典型：關節炎早於皮膚、軸性為主、毀損性(arthritis mutilans)。
- 來源(PubMed)：Psoriatic arthritis: A comprehensive review for the dermatologist part I. *J Am Acad Dermatol* 2024. PMID 38857765. [DOI](https://doi.org/10.1016/j.jaad.2024.03.058)

### sjogren_syndrome（較不常見・好發中年）
- 盛行率：原發型盛行率約 0.01–0.6%(依準則)；強烈女性偏向、好發 40–60。
- 典型：乾眼乾口、抗 SSA/SSB 陽性、唾液腺腫。
- 不典型：以全身/腺體外(關節、肺、神經)首發、年輕發病、淋巴瘤轉化。
- 來源(PubMed)：Epidemiology of Sjögren syndrome. *Nat Rev Rheumatol* 2023. PMID 38110617. [DOI](https://doi.org/10.1038/s41584-023-01057-6)

### behcet_disease（罕見・好發年輕）
- 盛行率：整體罕見，惟絲路沿線(土耳其)達 0.1–0.4%；好發 20–40 歲。
- 典型：反覆口腔+生殖器潰瘍、葡萄膜炎、皮膚病灶、針刺反應。
- 不典型：血管型(動脈瘤/血栓)、神經型、腸道型。
- 來源(PubMed)：Behçet's Disease, Pathogenesis, Clinical Features, and Treatment Approaches. *Medicina (Kaunas)* 2024. PMID 38674208. [DOI](https://doi.org/10.3390/medicina60040562)

### anca_vasculitis（罕見・好發老年）
- 盛行率：罕見，盛行率約 13–20/10萬、年發生率 1–2/10萬；好發 50–70 歲。
- 典型：肺-腎症候群、ENT 侵犯、ANCA(PR3/MPO)陽性、壞死性小血管炎。
- 不典型：侷限型(僅 ENT)、單一器官、ANCA 陰性。
- 來源(PubMed)：EULAR recommendations for the management of ANCA-associated vasculitis: 2022 update. *Ann Rheum Dis* 2023. PMID 36927642. [DOI](https://doi.org/10.1136/ard-2022-223764)

### igg4_related_disease（罕見・好發老年）
- 盛行率：罕見且近年才被定義；好發 50–70 歲男性。
- 典型：多器官腫瘤樣腫大(胰、唾液腺、後腹膜)、血清 IgG4 升高、席紋狀纖維化。
- 不典型：單一器官型、血清 IgG4 正常、以過敏/淋巴結腫表現。
- 來源(PubMed)：Update on Autoimmune Pancreatitis and IgG4-Related Disease. *United European Gastroenterol J* 2024. PMID 39707927. [DOI](https://doi.org/10.1002/ueg2.12738)

### chronic_urticaria（常見・好發中年）
- 盛行率：點盛行率約 0.5–1%、終生約 1.4%；好發 20–40 歲女性。
- 典型：反覆風疹塊 >6 週、可伴血管性水腫、抗組織胺反應。
- 不典型：誘發型(冷/壓力/膽鹼性)、自體免疫型、難治型。
- 來源(PubMed)：Chronic spontaneous urticaria and chronic inducible urticaria. *J Allergy Clin Immunol* 2025. PMID 40451490. [DOI](https://doi.org/10.1016/j.jaci.2025.05.019)

### osteoarthritis（常見・好發老年）
- 盛行率：極常見，成人達 7–15%+；老年人失能首因。
- 典型：膝/髖/手關節活動痛、休息改善、骨刺、關節間隙變窄。
- 不典型：侵蝕性手部 OA、快速破壞型髖 OA、年輕創傷後續發型。
- 來源(PubMed)：Osteoarthritis year in review 2024: Epidemiology and therapy. *Osteoarthritis Cartilage* 2024. PMID 39103081. [DOI](https://doi.org/10.1016/j.joca.2024.07.014)

### idiopathic_pulmonary_fibrosis（罕見・好發老年）
- 盛行率：罕見，盛行率約 10–60/10萬；好發 >60 歲男性、吸菸者。
- 典型：進行性呼吸困難、乾咳、爆裂音、HRCT 呈 UIP 型。
- 不典型：併肺氣腫型(CPFE)、以急性惡化首發、家族型。
- 來源(PubMed)：Idiopathic pulmonary fibrosis. *Presse Med* 2023. PMID 37156412. [DOI](https://doi.org/10.1016/j.lpm.2023.104166)

---

*所有疾病流行病學分類引用自 PubMed 檢索之文獻（PMID/DOI 如上）；本模擬為 in silico（虛擬）資料，未寫入任何正式環境或真實使用者資料。*