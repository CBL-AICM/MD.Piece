# 參考文獻總表（References）— MD.Piece 數位雙生模擬研究

本研究所有文獻皆取自 **PubMed**，共 **18 篇**，依用途分組。每篇附 PMID 與可點擊 DOI。
數值用於參數化模擬模型（非臨床結論）；各 cohort 背景（治療/未治療、成人/兒童、停藥後等）見內文與 registry 註記。

---

## A. 疾病流行病學：復發率與人口學（disease_registry 錨定）

1. **Jarius S, Ruprecht K, Kleiter I, et al.** MOG-IgG in NMO and related disorders: a multicenter study of 50 patients. Part 2: Epidemiology, clinical presentation, radiological and laboratory features, treatment responses, and long-term outcome. *J Neuroinflammation.* 2016;13(1):280. PMID 27793206. [DOI](https://doi.org/10.1186/s12974-016-0718-0)
   - 用途：**NMOSD** 年化復發率 ARR 0.92（MOG-IgG）。

2. **Bilodeau PA, Wruble Clark M, Ganguly A, et al.** Real-World Efficacy and Safety of Neuromyelitis Optica Spectrum Disorder Disease-Modifying Treatments. *Neurol Neuroimmunol Neuroinflamm.* 2026;13(2):e200536. PMID 41494145. [DOI](https://doi.org/10.1212/NXI.0000000000200536)
   - 用途：**NMOSD** 治療後 ARR 0.0–0.34；中位年齡 42、83% 女性。

3. **Kappos L, Fox RJ, Burcklen M, et al.** Ponesimod Compared With Teriflunomide in Patients With Relapsing Multiple Sclerosis (OPTIMUM): A Randomized Clinical Trial. *JAMA Neurol.* 2021;78(5):558-567. PMID 33779698. [DOI](https://doi.org/10.1001/jamaneurol.2021.0405)
   - 用途：**MS（RRMS）** ARR 0.202/0.290；中位年齡 37、64.9% 女性。

4. **Hao Y, Ji L, Gao D, et al.** Flare rates and factors determining flare occurrence in patients with SLE who achieved low disease activity or remission: a prospective cohort study. *Lupus Sci Med.* 2022;9(1):e000553. PMID 35241499. [DOI](https://doi.org/10.1136/lupus-2021-000553)
   - 用途：**SLE** SELENA-SLEDAI flare 0.10–0.49/人年。

5. **Mori S, Okada A, Koga T, Ueki Y.** Long-term outcomes after discontinuing biological drugs and tofacitinib in patients with rheumatoid arthritis: A prospective cohort study. *PLoS One.* 2022;17(6):e0270391. PMID 35737642. [DOI](https://doi.org/10.1371/journal.pone.0270391)
   - 用途：**RA** flare 0.36/人年（停藥後；1 年累積 45%）。

6. **Chauhan N, Khan HH, Kumar S, Lyons H.** Clinical Variables as Predictors of First Relapse in Pediatric Crohn's Disease. *Cureus.* 2019;11(6):e4980. PMID 31467814. [DOI](https://doi.org/10.7759/cureus.4980)
   - 用途：**Crohn's** 1 年內復發 32%（3 年 50%）。

7. **Such-Díaz A, Díaz-Marín C, Sánchez-Pérez R, Iglesias-Peinado I.** Drug exposure associated with exacerbation of symptoms in patients with myasthenia gravis. *Rev Neurol.* 2020;71(4):143-150. PMID 32700310. [DOI](https://doi.org/10.33588/rn.7104.2020198)
   - 用途：**MG** 年化惡化率 0.35/年（嚴重 0.12/年）。

## B. 病患回憶與記憶偏誤（friction_engine 回憶觀察者錨定）

8. **Brown JB, Adams ME.** Patients as reliable reporters of medical care process: recall of ambulatory encounter events. *Med Care.* 1992;30(5):400-411. PMID 1583918. [DOI](https://doi.org/10.1097/00005650-199205000-00003)
   - 用途：回憶假陰性 0.10（顯著事件）→ 0.53（瑣碎事件）；年齡效應；2–3 個月內無衰退 → 顯著性加權遺忘模型。

9. **Fellhölter G, Stuckenschneider T, Himmelmann L, Zieschang T.** Emergency department visits due to severe falls: comparing patient self-reports and general practitioner records: A cross-sectional study. *BMC Geriatr.* 2025;25(1):757. PMID 41053639. [DOI](https://doi.org/10.1186/s12877-025-06411-9)
   - 用途：自述 vs GP 病歷一致性 κ 0.41–1.0（依病況顯著性）；年齡/認知/教育影響 → 顯著性/識讀/年齡調節。

## C. App 留存、參與與通知效果（usage_engine / friction 通知補登錨定）

10. **Schmitz H, Howe CL, Armstrong DG, Subbian V.** Leveraging mobile health applications for biomedical research and citizen science: a scoping review. *J Am Med Inform Assoc.* 2018;25(12):1685-1695. PMID 30445467. [DOI](https://doi.org/10.1093/jamia/ocy130)
    - 用途：mHealth 低留存為定義性挑戰（質性）→ 悲觀留存預設。

11. **Greer JA, Jacobs JM, Pensak N, et al.** Randomized Trial of a Smartphone Mobile App to Improve Symptoms and Adherence to Oral Therapy for Cancer. *J Natl Compr Canc Netw.* 2020;18(2):133-141. PMID 32023526. [DOI](https://doi.org/10.6004/jnccn.2019.7354)
    - 用途：提醒僅對 baseline 非依從(+22.3%)/焦慮(+16.1%)次群有效、整體無效 → 通知補登（最關鍵翻轉參數）為「適度、分眾」。

12. **Mande A, Moore SL, Banaei-Kashani F, Echalier B, Bull S, Rosenberg MA.** Assessment of a Mobile Health iPhone App for Semiautomated Self-management of Chronic Recurrent Medical Conditions Using an N-of-1 Trial Framework. *JMIR Form Res.* 2022;6(4):e34827. PMID 35412460. [DOI](https://doi.org/10.2196/34827)
    - 用途：3 個月完成率 70.9%；**主要 barrier 為 app 設計與技術功能**；網路招募流失高 → 流失/可用性問題。

## D. 可用性、滿意度與接受度（PRO / MAUQ 錨定）

13. **Mustafa N, Safii NS, Jaffar A, et al.** Malay Version of the mHealth App Usability Questionnaire (M-MAUQ): Translation, Adaptation, and Validation Study. *JMIR Mhealth Uhealth.* 2021;9(2):e24457. PMID 33538704. [DOI](https://doi.org/10.2196/24457)
    - 用途：**MAUQ** 可用性三構面（易用性、介面與滿意度、實用性；α=0.946）→ 使用心聲（滿意度）模型結構。

14. **Dou K, Yu P, Deng N, et al.** Patients' Acceptance of Smartphone Health Technology for Chronic Disease Management: A Theoretical Model and Empirical Test. *JMIR Mhealth Uhealth.* 2017;5(12):e177. PMID 29212629. [DOI](https://doi.org/10.2196/mhealth.7886)
    - 用途：抗拒改變為顯著 barrier；醫病關係、自我效能、感知威脅影響接受度；意圖→實際使用僅弱相關 → 問題⑤⑥⑨。

## E. 醫病溝通、入口網、互通性與隱私（doctor_engine / 設計支柱錨定）

15. **Kruse CS, Argueta DA, Lopez L, Nair A.** Patient and provider attitudes toward the use of patient portals for the management of chronic disease: a systematic review. *J Med Internet Res.* 2015;17(2):e40. PMID 25707035. [DOI](https://doi.org/10.2196/jmir.3703)
    - 用途：**最大正向主題＝醫病溝通(37%)**；最大負向＝安全/可用性(41%)，不熟科技者尤甚 → 使用心聲主題、問題③⑦⑨。

16. **Sheikh A, Anderson M, Albala S, et al.** Health information technology and digital innovation for national learning health and care systems. *Lancet Digit Health.* 2021;3(6):e383-e396. PMID 33967002. [DOI](https://doi.org/10.1016/S2589-7500(21)00005-4)
    - 用途：可用性、**互通性**、隱私/安全、數位包容列為優先 → 問題⑦⑧。

## F. 數位落差與長者識讀；慢病遠距監測障礙

17. **Hoogland AI, Mansfield J, Lafranchise EA, Bulls HW, Johnstone PA, Jim HSL.** eHealth literacy in older adults with cancer. *J Geriatr Oncol.* 2020;11(6):1020-1022. PMID 31917114. [DOI](https://doi.org/10.1016/j.jgo.2019.12.015)
    - 用途：長者 eHealth 識讀顯著較低、裝置/入口網使用率低 → 問題②數位落差。

18. **Bui KL, Purtell L, Hyun A, Bonner A.** eHealth Solutions for Symptom Assessment and Monitoring in Adults With Chronic Kidney Disease: A Systematic Review. *J Clin Nurs.* 2025;34(9):3560-3591. PMID 40369651. [DOI](https://doi.org/10.1111/jocn.17827)
    - 用途：使用者滿意度高，但數位識讀為主要 barrier；效益證據有限 → 問題②⑩。

---

## 各文件引用對照

| 文件 | 主要引用（編號）|
|---|---|
| `09_literature_calibration.md` | 1–11 |
| `10_usage_sentiment_research.md` | 10, 11, 13, 15 |
| `11_patient_usage_problems.md` | 10, 12–18, 15 |
| `12_design_response_arms.md` | （承上之設計支柱，無新增）|

> 共 18 篇，全部取自 **PubMed**。如需匯出 RIS/BibTeX 或補進提案 `03_文獻與證據` 的驗證表，可再行整理。
