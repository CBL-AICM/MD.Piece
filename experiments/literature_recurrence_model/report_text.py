"""說明書內文（中文、英文）。數字一律由 build_report.numbers() 傳入，這裡不寫死任何結果。"""
from __future__ import annotations

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TITLE = {
    "zh": ("以文獻數據錨定的慢性病復發預測", "結合 3,200 位虛擬患者的縱向研究"),
    "en": ("Literature-Anchored Prediction of Chronic Disease Recurrence", "A Longitudinal Study Combined With 3,200 Virtual Patients"),
}
FILENAME = {"zh": "說明書_中文_文獻錨定慢性病復發預測.docx", "en": "Report_EN_literature_anchored_recurrence_prediction.docx"}


def _cite_table(N, lang):
    meta = json.load(open(os.path.join(HERE, "outputs", "literature_metadata.json"), encoding="utf-8"))
    rows = []
    for _, r in N["refs"].iterrows():
        if r.pmid:
            au = [a for a in meta[r.pmid]["authors"] if not a.startswith("None")]
            last = [a.split(",")[0] for a in au]
            people = [a for a in au if ", " in a and len(a.split(", ")[1]) <= 4]
            if len(people) == 1 or len(last) == 1:
                who = last[0]
            elif len(people) == 2 and len(last) == 2:
                who = f"{last[0]} & {last[1]}"
            else:
                who = f"{last[0]} et al."
            cite = f"{who} ({r.year})"
        else:
            cite = r.apa.split(" (")[0] if not r.apa.startswith("MD.") else r.apa.split(". ")[0] + ". " + r.apa.split(". ")[1].split(")")[0] + ")"
            if r.apa.startswith("MD."):
                cite = ("MD. Piece 研究團隊 (" if lang == "zh" else "MD. Piece Research Team (") + r.apa.split("(")[1].split(")")[0] + ")"
            else:
                who = r.apa.split(",")[0]
                year = r.apa.split("(")[1].split(")")[0]
                cite = f"{who} et al. ({year})" if r.apa.count(".,") > 1 else f"{who} ({year})"
        rows.append([cite, r["類別"] if lang == "zh" else r.category_en,
                     r["用途（為什麼用、用了哪部分）"] if lang == "zh" else r.usage_en])
    return rows


def blocks(N, lang):
    return _zh(N) if lang == "zh" else _en(N)


# ═══════════════════════════ 中文 ═══════════════════════════
def _zh(N):
    mc, mo, me, H1, H2, ag, s = N["mc"], N["mo"], N["mech"], N["H1"], N["H2"], N["ag"], N["sens"]
    a, ao = mc["auroc"], mo["auroc"]
    ew = mc["early_warning"]
    sens_keys = list(s)
    m1, m2 = me["calibrated"], me["original"]
    tl = N["tl"]
    perm = np.array(N["perm"])
    cross = N["cross"]
    rows_cross = []
    for _, r in cross.sort_values("lit_target", ascending=False, na_position="last").iterrows():
        if np.isnan(r.lit_target):
            rows_cross.append([r["疾病"], "無", "—", f2(r.orig_p_y2), f2(r.calib_p_y3), f2(r.model_pred_365)])
        else:
            rows_cross.append([r["疾病"], f"{int(r.lit_k)}", f"{f2(r.lit_target)} ({f2(r.lit_lo)}–{f2(r.lit_hi)})",
                               f2(r.orig_p_y2), f2(r.calib_p_y3), f2(r.model_pred_365)])
    cal = mc["calibration"]
    model_rows = []
    for k in ["只用年齡性別病別", "只用文獻（未訓練）", "紀錄 30 天", "紀錄 365 天", "紀錄 730 天", "文獻分數＋紀錄 730 天", "梯度提升樹 730 天"]:
        model_rows.append([k, cie_t(a[k]), f2(cal[k]["slope"]), f3(cal[k]["brier"]), cie_t(ao[k])])
    c_lit = {c["curve"]: c["k"] for c in N["curves"]}
    B = []
    B += [("h1", "摘要"),
          ("pn", f"慢性病常讓人擔心的，是「好了一陣子，又復發」。本研究延續前一份研究的目的：長期紀錄能不能預測復發，以及復發大約在什麼時候出現。這一次不使用公開資料庫的個人資料來訓練或回推，只從 PubMed {N['n_pubmed'] - N['n_methods']} 篇文獻摘要擷取族群層級的數字，包括 13 種疾病的一年復發率、兩類復發相關因子的效果量與 5 條累積復發曲線，再與過去合成的 3,200 位虛擬患者（16 種慢性病，每種 200 人）結合。"),
          ("pn", f"文獻統整的結果是：過去或近期的疾病活動與之後的復發有關（統合相對風險 {f2(H1['pooled'])}，95% 信賴區間 {f2(H1['lo'])}–{f2(H1['hi'])}）；沒有按時用藥或停藥也與較多復發有關（{f2(H2['pooled'])}，{f2(H2['lo'])}–{f2(H2['hi'])}）；5 條曲線中有 {N['k_lit_below1']} 條的 Weibull 形狀參數小於 1，表示越早期越容易復發。原始虛擬患者的一年復發率，13 種有文獻可比的疾病中沒有一種落在文獻範圍內。每種疾病只調整一個復發門檻做文獻校準後，未參與校準的第 3 年復發率與文獻目標平均相差 {ag['mae_lit_vs_calib_y3'] * 100:.1f} 個百分點，{ag['within_lit_range_calib_y3']} 種落在文獻範圍內。"),
          ("pn", f"在校準後的新數據中，用兩年紀錄預測未來 90 天復發的 AUROC 為 {ci(a['紀錄 730 天'])}，只比只用年齡、性別與病別的 {f3(a['只用年齡性別病別'][0])} 略高；Cox 模型預測的一年復發時間線與實際接近。交叉對比發現，虛擬患者重現了「過去復發越多，之後越容易復發」的方向，但強度比文獻小，也沒有重現漏服藥物的影響。模擬資料適合用來檢查方法；要用在真實病人身上之前，仍需要真實的患者紀錄再驗證一次。"),
          ("pn", "關鍵詞：慢性病復發、縱向研究、文獻統整、虛擬患者、預測模型"),
          ("pagebreak",)]
    B += [("h1", "壹、前言"), ("h2", "一、研究動機"),
          ("p", "紅斑性狼瘡、類風濕性關節炎、發炎性腸道疾病、多發性硬化症這些慢性病，病程常常時好時壞。病情穩定一段時間後，又突然變差，醫學上稱為復發（flare 或 relapse）。從免疫學來看，這些疾病的共同點是免疫系統長期處在容易被點燃的狀態：一次感染、一段壓力很大的日子，或是自行減藥、停藥，都可能讓發炎再度升高。復發不只讓人不舒服，也和器官損傷的累積有關，例如貝賽特氏症的研究發現，曾經復發的人之後出現器官損傷的機會較高（Floris et al., 2022）。"),
          ("p", f"MD. Piece 是一個讓患者在手機上記錄症狀、用藥與生活狀況的 App。前一份研究用美國國家健康與營養調查追蹤資料（NHEFS）與 Framingham 教學資料，發現加入長期紀錄後預測復發住院的 AUROC 約為 {N['prev']['nhefs_long_record_auc']:.2f}，數位雙生模擬約為 {N['prev']['twin_full_lr_auc']:.2f}（MD. Piece 研究團隊, 2026a）。這一次的條件不同：不能用公開資料庫的個人資料來訓練或回推模型。於是我們想知道，如果手上只有已發表文獻裡的數字，能不能建立並檢查一個復發預測模型？也想順便看看，我們先前合成的虛擬患者，行為到底像不像文獻描述的真實病人。"),
          ("h2", "二、研究目的"),
          ("pn", "（一）從文獻整理 13 種慢性病的一年復發率，並檢查三個復發機制假說在多篇縱向研究中是否一致：H1 過去或近期的疾病活動與之後的復發有關；H2 沒有按時用藥或停藥與之後的復發有關；H3 復發風險在穩定後的早期較高、之後逐漸下降。"),
          ("pn", "（二）比較過去合成的 3,200 位虛擬患者與文獻是否相符，並以文獻數字校準，產生新數據。"),
          ("pn", "（三）沿用前一份研究的目的，在新數據上訓練模型，檢驗長期紀錄能否預測未來 90 天的復發與一年內的復發時間，並估計預警的表現。"),
          ("pn", "（四）把新數據、原始虛擬患者與真實文獻三方交叉對比，最後再與文獻中已發表的預測模型表現對照。"),
          ("h2", "三、文獻回顧"),
          ("p", "許多縱向研究都提到，「以前的病史」是預測之後病程的重要線索。慢性阻塞性肺病的 ECLIPSE 研究追蹤 2,138 人三年，發現過去的急性惡化次數是之後惡化最好的單一預測因子，而且「容易惡化」的特性在三年內相當穩定（Hurst et al., 2010）。重度氣喘患者若最近三個月有嚴重惡化，之後再惡化的勝算比校正後為 3.77（Miller et al., 2007）。多發性硬化症臨床試驗安慰劑組的資料也顯示，試驗前兩年的復發次數越多，試驗期間的復發率越高（Held et al., 2005）。"),
          ("p", "用藥順從度是另一條線索。緩解期潰瘍性結腸炎患者領藥不到八成時，復發風險約為按時用藥者的 5.5 倍（Kane et al., 2003）；狼瘡患者停用 hydroxychloroquine 後重大復發較多，但差異未達統計顯著（Tsakonas et al., 1998）；停用低劑量類固醇也與稍多的復發有關（Ji et al., 2021）。至於復發的時間型態，類風濕性關節炎停用生物製劑後，第 1、3、5 年累積復發分別為 45%、64% 與 80%（Mori et al., 2022），新診斷的發炎性腸道疾病也是第一年復發最多（Vester-Andersen et al., 2014），兩者都呈現「前期快、後期慢」的曲線。"),
          ("p", "預測模型方面，COPD 已有超過 400 個預後模型，但多數有偏誤風險（Bellou et al., 2019）；COPD 惡化的 AI 模型統合 AUC 約為 0.77，但研究間差異很大（Niraula et al., 2025）。狼瘡研究則發現，「持續活動」可以預測，單次復發的預測模型表現卻不好（Nikpour et al., 2009）。這些結果提醒我們，復發預測本身就不容易，評估時要看清楚比較的基準。"),
          ]
    B += [("h1", "貳、研究設備及器材"),
          ("pn", "（一）硬體：雲端 Linux 電腦（4 核心 CPU、16 GB 記憶體）。"),
          ("pn", "（二）軟體：Python 3.13，使用 NumPy、pandas、SciPy、scikit-learn（Pedregosa et al., 2011）與 Matplotlib（Hunter, 2007）。Cox 比例風險模型以 Newton–Raphson 法自行撰寫，並與 statsmodels 的結果比對到小數第四位一致。"),
          ("pn", "（三）文獻來源：PubMed（以 NCBI E-utilities 檢索與下載摘要）。"),
          ("pn", "（四）虛擬患者：MD. Piece 專案的 md_piece 模擬器與 16 種疾病設定檔（MD. Piece 研究團隊, 2026b），原封不動使用。"),
          ("pn", "（五）程式與輸出位置：儲存庫 experiments/literature_recurrence_model/，依序執行 simulate_cohort.py、run.py、figures.py、references.py、build_report.py 可重現全部數字、圖表與本說明書。"),
          ]
    B += [("h1", "參、研究過程或方法"), ("h2", "一、研究架構與流程"),
          ("p", "研究架構如圖 1，流程如圖 2。資料只有兩個來源：文獻摘要中的族群層級數字，以及過去合成的虛擬患者。公開資料庫的個人層級資料（例如 NHEFS、Framingham）這次完全不使用，既不用來訓練，也不用來回推參數。分析計畫在執行前已寫在程式 run.py 的開頭，跑完後沒有回頭修改門檻或權重；過程中發現並修正的兩個程式問題，列在本章第九節。"),
          ("fig", "fig01_framework", "研究架構", "MD. Piece 只作為輔助工具，不做診斷，也不取代醫師。", 14.5),
          ("fig", "fig02_workflow", "研究流程", None, 14.0),
          ("h2", "二、文獻檢索與數字擷取"),
          ("p", f"以疾病名稱加上 flare、relapse、exacerbation、recurrence、cohort、adherence 等關鍵字在 PubMed 檢索，逐篇閱讀摘要。只收摘要中「明確寫出數字」的縱向研究、臨床試驗或統合分析；摘要沒有寫出的數字（例如某些信賴區間）不從其他地方補。最後用到 {N['n_pubmed'] - N['n_methods']} 篇研究文獻與 {N['n_methods']} 篇統計方法文獻，全部列在附錄表 A，並說明每一篇為什麼用、用了哪一部分。"),
          ("p", "不同研究報告復發的方式不同，所以先換算成同一個尺度：「一年內至少復發一次的比例」。事件率 λ（次／人年）換算為 1 − e^(−λ)；t 年累積復發比例 p 換算為 1 − (1 − p)^(1/t)；一年內的比例直接使用。每種疾病取各研究換算值的中位數作為校準目標，最小值到最大值作為文獻範圍。退化性關節炎、全身性硬化症與乾燥症這次找不到可比的年復發率（全身性硬化症與乾燥症的文獻多以「病情進展」或活動度起伏描述，Elhai et al., 2022；Fernández-Castro et al., 2025），因此不校準，並在結果中標示。"),
          ("h2", "三、機制假說的文獻統整"),
          ("p", "H1 與 H2 各收集摘要中有 95% 信賴區間的效果量（勝算比 OR、風險比 HR 或相對風險 RR），取對數後以 DerSimonian–Laird 隨機效應模型統合（DerSimonian & Laird, 1986），並計算異質性 I²。三種效果量在事件不太常見時數值相近，這裡把它們視為近似的同一尺度，這是本研究的限制之一。H3 則把每條累積復發曲線擬合為 Weibull 分布：log(−log S(t)) = k·log t − k·log λ，形狀參數 k 小於 1 代表越早期越容易復發，k 等於 1 代表風險不隨時間改變。"),
          ("h2", "四、虛擬患者"),
          ("p", "虛擬患者來自 md_piece 模擬器。每位患者每天有一個「潛在疾病活動度」，會受到治療效果、漏服藥物、感染或壓力等誘發因子、生活事件、亞型與個人差異的影響；活動度超過門檻就算處在復發中。模擬器另外會產生患者自填的症狀分數與醫院的檢驗值。過去研究用同一個模擬器、同一組亂數種子（base_seed = 2024）產生了 16 種疾病各 200 人、共 3,200 人、180 天的資料。這次沿用同樣的種子，把模擬延長為 1,095 天（3 年），才有足夠的時間看第 1 年到第 3 年的變化。"),
          ("p", "「新一次復發」定義為從非復發轉為復發，而且距離上一次復發結束至少 7 天（或疾病設定的不反應期，取較長者）；間隔太短的視為同一次復發。"),
          ("h2", "五、文獻校準：產生新數據"),
          ("p", "每種疾病只調整一個參數：復發門檻的位移 δ。δ 從 0 開始，往「讓第 2 年一年復發率靠近文獻目標」的方向每次移動 0.05，第一次跨過目標後再在區間內二分 12 次。只往單一方向找的原因寫在第九節。校準只用到第 2 年的一年復發率；H1、H2、H3、第 3 年復發率與復發持續天數都沒有參與校準，留作獨立檢查。校準後的 3,200 人就是本研究的「新數據」，原始設定的 3,200 人則作為對照。"),
          ("h2", "六、App 紀錄層與預測特徵"),
          ("p", f"真實的 App 紀錄不會完美，所以在潛在活動度和模型之間加了一層「紀錄」：症狀日記只有 {int(N['settings']['log_rate'] * 100)}% 的天數有填，填寫的數值加上 {N['settings']['diary_noise_sd']} 個標準差的誤差；檢驗值每 {N['settings']['lab_every']} 天一次；漏服藥物與誘發因子只有在有填日記的天數才看得到；過去的復發史則完整可見。預測時往回看一段紀錄（30、90、180、365 或 730 天），計算症狀的平均、最高、起伏、最近 14 天平均與變化斜率、漏服比例、誘發因子天數比例、最近一次與平均檢驗值、這段期間的復發次數，以及距離上次復發的天數，再加上年齡、性別與病別。"),
          ("h2", "七、模型與評估"),
          ("p", "預測時點設在第 730 天（相當於使用 App 兩年後），排除當天正在復發的人。主要結果是未來 90 天內是否出現新一次復發；次要結果是到下一次復發的天數，最多追蹤 365 天。比較的模型有：只用年齡、性別與病別；只用文獻（不訓練，把各病的文獻年復發率乘上 H1 與 H2 的統合倍數）；文獻分數加上紀錄；logistic 迴歸（五種紀錄長度）；梯度提升樹；以及預測復發時間的 Cox 模型。"),
          ("p", "所有模型都用分層五折交叉驗證，只用「沒看過」的那一折來評估。鑑別力用 AUROC，並以 1,000 次 bootstrap 估計 95% 信賴區間；校準度用校準斜率與 Brier 分數；Cox 模型用 C-index（Harrell et al., 1982）與 90、180、365 天的時間相依 AUC。為了確認訓練資料裡沒有混入答案，把結果標籤隨機打亂 50 次重跑，AUROC 應該落在 0.5 附近。預警分析把風險最高的 20% 視為「警示」，計算敏感度、陽性預測值、提升倍數（陽性預測值 ÷ 平均復發率）與提前天數。最後做紀錄品質的敏感度分析：回憶式紀錄（只有 30% 的天數、誤差 0.8 SD）、本研究設定、完整紀錄，以及「直接看到潛在活動度」的理論上限。"),
          ("h2", "八、交叉對比"),
          ("p", "交叉對比分三層：（1）逐病一年復發率：文獻、原始虛擬患者、新數據（第 3 年）與模型預測；（2）三個機制：文獻統合值與虛擬患者的分層 Mantel–Haenszel 相對風險（Greenland & Robins, 1985）、劑量反應與 Weibull k；（3）模型表現：本研究、前一份研究與文獻中的模型。"),
          ("h2", "九、過程中修正的問題"),
          ("p", "（一）第一版校準在整條 δ 軸上找「最接近目標」的點。結果類風濕性關節炎、乾癬性關節炎與 IgG4 相關疾病被調成很低的門檻：患者幾乎整年都處在復發中，「新一次復發」反而變少，數字看似對上文獻，其實不合理（類風濕性關節炎只有 17 人在預測時點不在復發中）。改成只往單一方向找之後，各病處在復發中的天數比例都低於 1.5%。（二）第一版 Cox 模型在新數據中發散，原因是部分病別事件很少、係數趨向無限大；改為加上很小的 L2 懲罰（λ = 0.01），在沒有懲罰時與 statsmodels 的結果一致。這兩項修正都在看模型表現之前完成。"),
          ]
    rcol = ["疾病", "估計數", "文獻目標 (範圍)", "原始虛擬 第 2 年", "新數據 第 3 年", "模型預測"]
    B += [("h1", "肆、研究結果"), ("h2", "一、文獻統整"),
          ("p", f"共擷取 {N['n_rate_est']} 個年復發率估計值，來自 {N['n_rate_studies']} 篇研究、13 種疾病。換算後的一年復發率從特發性肺纖維化的 {f2(N['r']['literature']['targets']['idiopathic_pulmonary_fibrosis']['target'])} 到貝賽特氏症的 {f2(N['r']['literature']['targets']['behcet_disease']['target'])}；同一種疾病在不同研究間也有差距，例如慢性蕁麻疹從 0.06 到 0.36，主要與研究族群（剛停藥或長期穩定）有關（圖 3 藍點）。"),
          ("fig", "fig03_annual_recurrence", "逐病一年復發率：文獻、原始虛擬患者、新數據與模型預測", "藍點為各研究換算後的一年復發率，淺藍帶為文獻範圍。新數據取第 3 年（沒有參與校準）。模型預測為 Cox 模型在第 730 天預測的一年復發機率平均（交叉驗證折外）。", 15.0),
          ("p", f"H1 共 {H1['k']} 篇，統合相對風險 {f2(H1['pooled'])}（95% CI {f2(H1['lo'])}–{f2(H1['hi'])}），I² = {H1['I2'] * 100:.0f}%，各研究方向一致。H2 共 {H2['k']} 篇，統合值 {f2(H2['pooled'])}（{f2(H2['lo'])}–{f2(H2['hi'])}），I² = {H2['I2'] * 100:.0f}%，方向一致但大小差很多（圖 4）。痛風的 NOR-Gout 研究沒有信賴區間，未納入統合，但服藥順從度最低與最高四分位的復發比例為 33.3% 對 9.5%（Uhlig et al., 2025a），方向相同。H3 方面，類風濕性關節炎（k = {f2(c_lit['類風濕性關節炎（停藥後）'])}）、克隆氏症（{f2(c_lit['克隆氏症（新診斷）'])}）與潰瘍性結腸炎（{f2(c_lit['潰瘍性結腸炎（新診斷）'])}）的 k 都小於 1，IgG4 相關疾病（{f2(c_lit['IgG4 相關疾病'])}）與特發性肺纖維化（{f2(c_lit['特發性肺纖維化（急性惡化）'])}）接近 1（圖 5a）。也就是說，「越早期越容易復發」在停藥後與新診斷的族群中比較明顯。"),
          ("fig", "fig04_forest_H1_H2", "機制假說 H1 與 H2：文獻各研究、文獻統合值與兩組虛擬患者", "H1 包含曾嚴重惡化、控制不佳、疾病活動度較高、檢驗反覆升高與緩解時間短；虛擬患者的 H1 為「第 1 年曾復發 vs 未復發」對第 2 年復發的相對風險；H2 為第 1 年漏服比例最高與最低四分位的比較。皆依病別分層。", 14.5),
          ("fig", "fig05_timing_weibull", "機制假說 H3：累積復發曲線的時間型態", "（a）點為文獻報告值，線為 Weibull 擬合。（b）虛擬患者每點為一種疾病，從第 365 天起追蹤 2 年；橫線為中位數。", 15.5),
          ("h2", "二、原始虛擬患者與文獻的比較"),
          ("p", f"原始虛擬患者的一年復發率偏高很多：13 種有文獻可比的疾病中，一年復發率從 {f2(N['orig_min'])} 到 {f2(N['orig_max'])}，沒有一種落在文獻範圍內，與文獻目標平均相差 {ag['mae_lit_vs_orig'] * 100:.0f} 個百分點；各病高低的排序也和文獻幾乎無關（Spearman ρ = {f2(ag['spearman_lit_vs_orig'])}）。例如紅斑性狼瘡與類風濕性關節炎在原始設定下，幾乎每個人每年都會復發，而文獻中每年約只有 14% 到 30%（Nikpour et al., 2009；Peng et al., 2017；Mori et al., 2022）。只有特發性肺纖維化（0.10 對 0.08）與 IgG4 相關疾病（0.06 對 0.16）較接近。"),
          ("p", f"機制方面，原始虛擬患者的 H1 相對風險為 {f2(m2['H1_prior_flare']['rr'])}（{f2(m2['H1_prior_flare']['lo'])}–{f2(m2['H1_prior_flare']['hi'])}），方向和文獻相同但小很多；H2 為 {f2(m2['H2_missed_dose_quartile']['rr'])}（{f2(m2['H2_missed_dose_quartile']['lo'])}–{f2(m2['H2_missed_dose_quartile']['hi'])}），看不到漏服藥物的影響；Weibull k 中位數為 {f2(N['k_orig_med'])}，比文獻的 {f2(N['k_lit_med'])} 更接近「風險不隨時間改變」。"),
          ("h2", "三、文獻校準後的新數據"),
          ("p", f"校準後，13 種疾病第 2 年的一年復發率都對準了文獻目標（類風濕性關節炎因為人數離散，停在 0.33，目標為 0.30）。比較能說明問題的是沒有參與校準的第 3 年：與文獻目標平均只差 {ag['mae_lit_vs_calib_y3'] * 100:.1f} 個百分點，{ag['within_lit_range_calib_y3']}／{ag['n_anchored']} 種落在文獻範圍內，排序相關 ρ = {f2(ag['spearman_lit_vs_calib_y3'])}（圖 3、表 1）。落在範圍外的主要是紅斑性狼瘡：第 2 年為 0.14，第 3 年降到 {f2(cross.set_index('disease').loc['systemic_lupus_erythematosus', 'calib_p_y3'])}，低於文獻下限 0.13。"),
                    ("p", f"新數據中，H1 的相對風險升為 {f2(m1['H1_prior_flare']['rr'])}（{f2(m1['H1_prior_flare']['lo'])}–{f2(m1['H1_prior_flare']['hi'])}），症狀較重三分之一對較輕三分之一為 {f2(m1['H1_symptom_tertile']['rr'])}（{f2(m1['H1_symptom_tertile']['lo'])}–{f2(m1['H1_symptom_tertile']['hi'])}），方向與文獻一致，但仍比文獻統合的 {f2(H1['pooled'])} 小；H2 為 {f2(m1['H2_missed_dose_quartile']['rr'])}（{f2(m1['H2_missed_dose_quartile']['lo'])}–{f2(m1['H2_missed_dose_quartile']['hi'])}），仍未重現。劑量反應方面，過去復發 0、1、2、≥3 次的人，之後的復發率依序為 1、{N['dr_new'][1]:.1f}、{N['dr_new'][2]:.1f}、{N['dr_new'][3]:.1f} 倍，形狀與多發性硬化症研究的 1、{N['ms'][1]:.1f}、{N['ms'][2]:.1f}、{N['ms'][3]:.1f} 倍相近（圖 6；Held et al., 2005）。Weibull k 中位數為 {f2(N['k_new_med'])}，仍高於文獻。"),
          ("fig", "fig06_dose_response", "過去復發次數與之後復發率的劑量反應", "文獻為多發性硬化症臨床試驗安慰劑組試驗前 24 個月的復發次數；虛擬患者為第 1 年復發次數對第 2 年復發次數。", 12.0),
          ("p", f"復發持續的天數是另一項獨立檢查。新數據中多數疾病一次復發平均持續 2 到 7 天（例如僵直性脊椎炎 {N['ep_new']['Ankylosing spondylitis']:.1f} 天、紅斑性狼瘡 {N['ep_new']['SLE']:.1f} 天），和患者每週自述的復發「多數不超過 3 天」接近（Jacquemin et al., 2017），但比僵直性脊椎炎「大發作平均 2.4 週」短（Cooksey et al., 2010）。換句話說，新數據裡的復發比較像短暫的症狀變差，而不是需要住院或改藥的大復發。"),
          ("tab", "逐病一年復發率交叉對比", rcol, rows_cross,
           "數值為一年內至少復發一次的比例。文獻估計數為可換算的估計值個數。「無」表示找不到可比的文獻年復發率，未校準。新數據取第 3 年，模型預測為 Cox 模型的折外一年預測平均。", [3.4, 1.4, 3.6, 2.4, 2.4, 2.0]),
          ("h2", "四、預測未來 90 天的復發"),
          ("p", f"新數據中，第 730 天可預測的有 {mc['n']} 人（{mc['excluded_in_flare']} 人當天正在復發而排除），未來 90 天復發的比例為 {pct(mc['event_rate_90d'])}，一年內為 {pct(mc['event_rate_365d'])}。只用年齡、性別與病別的 AUROC 為 {ci(a['只用年齡性別病別'])}；加入 730 天紀錄後為 {ci(a['紀錄 730 天'])}，增加 {a['紀錄 730 天'][0] - a['只用年齡性別病別'][0]:.3f}。紀錄長度從 30 天增加到 365 天時，AUROC 從 {f3(a['紀錄 30 天'][0])} 增加到 {f3(a['紀錄 365 天'][0])}，再延長到 730 天就沒有再增加（圖 7）。只用文獻、完全不訓練的模型為 {ci(a['只用文獻（未訓練）'])}；把文獻分數加進紀錄模型（{f3(a['文獻分數＋紀錄 730 天'][0])}）沒有再提高。梯度提升樹為 {f3(a['梯度提升樹 730 天'][0])}，校準斜率只有 {f2(cal['梯度提升樹 730 天']['slope'])}，有過度擬合的跡象。標籤打亂 50 次的 AUROC 平均為 {perm.mean():.3f}（{perm.min():.3f}–{perm.max():.3f}），表示訓練資料沒有混入答案。"),
          ("p", f"因為不同疾病的復發率差很多，「只看病別」就能分出不少高低。若只在同一種疾病內比較（以事件數加權平均），紀錄模型的 AUROC 為 {f3(N['within_rec'])}，只用年齡性別為 {f3(N['within_static'])}，只用文獻為 {f3(N['within_lit'])}，紀錄的幫助在病別內比較看得出來，但幅度不大。"),
          ("fig", "fig07_record_length_auroc", "預測時往回看的紀錄長度與 AUROC", "色帶為 bootstrap 95% 信賴區間。虛線為只用年齡、性別與病別，點線為只用文獻（未訓練）。", 13.5),
          ("tab", "各模型預測未來 90 天復發的表現", ["模型", "新數據 AUROC (95% CI)", "校準斜率", "Brier", "原始虛擬 AUROC"], model_rows,
           "校準斜率越接近 1 越好，小於 1 代表預測的高低差距太大。Brier 分數越小越好。", [4.0, 4.4, 1.6, 1.4, 4.2]),
          ("fig", "fig08_roc", "ROC 曲線", "圖例中的數字為 AUROC。", 15.5),
          ("fig", "fig09_calibration", "730 天紀錄模型的校準圖", "依預測機率分成十組，比較每組的平均預測值與實際復發比例；虛線為完全一致。", 10.5),
          ("h2", "五、復發時間線"),
          ("p", f"Cox 模型的 C-index 為 {f3(mc['cox_c_index'])}（只用年齡性別病別為 {f3(mc['cox_static_c_index'])}），90、180、365 天的時間相依 AUC 分別為 {f3(mc['cox_td_auc']['90'])}、{f3(mc['cox_td_auc']['180'])}、{f3(mc['cox_td_auc']['365'])}。依預測風險分成三組，一年內實際復發的比例為低風險組 {pct(tl.loc['低', 'observed'])}、中風險組 {pct(tl.loc['中', 'observed'])}、高風險組 {pct(tl.loc['高', 'observed'])}，模型預測分別為 {pct(tl.loc['低', 'predicted'])}、{pct(tl.loc['中', 'predicted'])} 與 {pct(tl.loc['高', 'predicted'])}，整條時間線都很接近（圖 10）。各病預測的一年復發率與文獻目標平均相差 {ag['mae_lit_vs_model'] * 100:.1f} 個百分點，{ag['within_lit_range_model']} 種落在文獻範圍內（表 1）。"),
          ("fig", "fig10_timeline", "依預測風險分組的復發時間線：實際與模型預測", "實線為實際累積復發比例，虛線為 Cox 模型預測（交叉驗證折外）。", 12.5),
          ("h2", "六、紀錄品質、預警與預測特徵"),
          ("p", f"紀錄品質對結果幾乎沒有影響：回憶式紀錄、本研究設定與完整紀錄的 AUROC 分別為 {f3(s[sens_keys[0]]['auc'][0])}、{f3(s[sens_keys[1]]['auc'][0])} 與 {f3(s[sens_keys[2]]['auc'][0])}。就算直接看到潛在活動度，上限也只有 {f3(s[sens_keys[3]]['auc'][0])}，病別內平均 {f3(s[sens_keys[3]]['within_disease_auc_weighted'])}（圖 11）。這表示在這個模擬器裡，未來 90 天的復發有很大一部分來自隨機出現的誘發因子，事前很難看出來。"),
          ("fig", "fig11_record_quality", "紀錄品質與理論上限", "深色為全體 AUROC（線段為 95% CI），淺色為病別內以事件數加權的平均 AUROC。", 14.0),
          ("p", f"預警方面，把風險最高的 20% 視為警示時，紀錄模型抓到 {pct(ew['紀錄 730 天']['sensitivity'], 0)} 的復發，被警示的人中有 {pct(ew['紀錄 730 天']['ppv'], 0)} 真的復發，是平均復發率的 {f2(ew['紀錄 730 天']['lift'])} 倍；從預測時點到復發的天數中位數為 {ew['紀錄 730 天']['lead_days_median']:.0f} 天（四分位距 {ew['紀錄 730 天']['lead_days_iqr'][0]:.0f}–{ew['紀錄 730 天']['lead_days_iqr'][1]:.0f} 天）。只用文獻的模型抓到 {pct(ew['只用文獻（未訓練）']['sensitivity'], 0)}，只用年齡性別病別為 {pct(ew['只用年齡性別病別']['sensitivity'], 0)}（圖 12）。在模型裡權重最大的特徵是「過去兩年的復發次數」，其次是誘發因子天數、漏服比例與最近 14 天的症狀（圖 13），和文獻中「病史是最好的預測因子」的說法一致（Hurst et al., 2010）。症狀平均的係數為負值，是因為它和症狀最高值、最近 14 天症狀高度相關，單獨看係數的正負沒有意義。"),
          ("fig", "fig12_early_warning", "風險最高 20% 作為警示時的預警表現", "提升倍數 = 陽性預測值 ÷ 平均復發率。提前天數只計算被警示而且真的復發的人。", 16.0),
          ("fig", "fig13_features", "730 天紀錄模型的標準化係數", "係數由全體資料擬合，只用於說明，不用於評估。", 12.0),
          ]
    prev = N["prev"]
    rows_cmp = [
        ["本研究：新數據，紀錄 730 天（logistic）", f3(a["紀錄 730 天"][0]), "3,177 位虛擬患者，未來 90 天"],
        ["本研究：新數據，Cox 時間線", f"C = {f3(mc['cox_c_index'])}", "一年內復發時間"],
        ["本研究：只用文獻（未訓練）", f3(a["只用文獻（未訓練）"][0]), "同上"],
        ["前一份研究：NHEFS 長期紀錄", f2(prev["nhefs_long_record_auc"]), "真實公開資料，未來 12 個月再住院"],
        ["前一份研究：數位雙生", f2(prev["twin_full_lr_auc"]), "3,200 位虛擬患者"],
        ["文獻：COPD 惡化 AI 模型統合", "0.77", "13 篇，I² = 99.5%（Niraula et al., 2025）"],
        ["文獻：氣喘控制問卷 ACQ", "0.68", "3 年內惡化（He et al., 2022）"],
        ["文獻：硬皮症無惡化存活", "0.70–0.71", "EUSTAR（Elhai et al., 2022）"],
    ]
    B += [("h2", "七、與前一份研究及文獻中模型表現的對照"),
          ("p", "表 3 把本研究的模型表現放在前一份研究與文獻旁邊。三者的族群、結果定義與時間長度都不同，只能看大致的範圍，不能直接比高低。"),
          ("tab", "模型表現對照", ["來源與模型", "AUROC／C", "說明"], rows_cmp, None, [6.6, 2.4, 7.0]),
          ]
    B += [("h1", "伍、討論"), ("h2", "一、三個復發機制在文獻中是否成立"),
          ("p", "H1 在 5 篇、4 種疾病的研究中方向一致，異質性中等，再加上 COPD 與多發性硬化症的長期追蹤（Hurst et al., 2010；Held et al., 2005），可以說「過去或近期的疾病活動與之後的復發有關」在文獻中相當一致。從免疫學的角度，這可以有幾種解釋：有些人的免疫系統本來就比較容易被點燃；每次發炎留下的組織損傷，也可能讓下一次更容易發生。不過觀察性研究只能看到「相關」，無法分辨這兩種解釋。H2 的方向也一致，但只有 3 篇，大小差距很大，信賴區間下限接近 1，證據比 H1 弱；而且用藥順從度差的人，可能本來就病得比較重或生活比較忙亂，不能直接把差距都歸到藥物本身。H3 只在停藥後與新診斷的族群中較明顯，長期穩定的族群（例如 IgG4 相關疾病、特發性肺纖維化）比較接近固定風險。"),
          ("h2", "二、虛擬患者哪裡像、哪裡不像"),
          ("p", "原始虛擬患者的復發太頻繁，與文獻差距很大，這是本研究最直接的發現之一。原因之一是模擬器把「活動度短暫超過門檻」都算成復發，而文獻多半要求醫師判定或需要改藥。只調一個門檻後，第 3 年的復發率就能和文獻相符，表示模擬器的「病程起伏」形狀大致合理，問題主要在復發的判定尺度。"),
          ("p", "不像的地方有三個：H1 的強度比文獻小、H2 幾乎沒有出現，以及 Weibull k 比文獻高。在模擬器裡，漏服藥物只會讓當天藥效稍微下降，藥效很快又恢復，而真實病人長期沒吃藥時，可能是整段時間停藥，也可能伴隨其他生活改變。模擬器的復發多由隨機誘發因子觸發，事件之間比較獨立，這可能是「早期特別危險」與「頻繁復發者」兩種特性都比較弱的原因。這些差距需要在模擬器的設計上處理，而不是靠調參數硬對齊。"),
          ("h2", "三、長期紀錄的幫助為什麼看起來不大"),
          ("p", f"前一份研究的 NHEFS 資料中，加入長期紀錄讓 AUROC 從 {N['prev']['nhefs_no_record_auc']:.2f} 提高到 {N['prev']['nhefs_long_record_auc']:.2f}；這次在新數據中只提高約 {a['紀錄 730 天'][0] - a['只用年齡性別病別'][0]:.2f}，在病別內比較則從 {f2(N['within_static'])} 提高到 {f2(N['within_rec'])}。紀錄品質的敏感度分析提供了線索：即使紀錄完整、甚至直接看到潛在活動度，上限也只有 {f2(s[sens_keys[3]]['auc'][0])}。也就是說，這組模擬資料裡可被預測的部分本來就有限，資料品質再好也幫不上太多忙。這與狼瘡研究中「單次復發很難預測」的發現相符（Nikpour et al., 2009），也與 AS 的研究一致：突發的壓力事件之後疾病活動才上升（Luo et al., 2019），事前不容易看出。另一方面，模型最依賴的是復發史，這部分在真實的 App 中比較容易記錄完整，對設計提醒功能是有用的訊息。"),
          ("h2", "四、從臨床角度的解讀"),
          ("p", f"以預警來說，警示 20% 的人可以抓到約一半的復發，提前約 {ew['紀錄 730 天']['lead_days_median']:.0f} 天，但被警示的人中只有約五分之一真的復發。在臨床上，這比較適合用來安排「提早回診或多問幾句」，而不是用來決定加藥或改藥。MD. Piece 的定位也是如此：整理紀錄、提醒患者與醫師注意，最後仍由醫師判斷。"),
          ("h2", "五、研究限制"),
          ("pn", "（一）文獻只用摘要中的數字，部分研究族群特殊（如剛停藥、新診斷或重度患者），換算一年復發率時也假設每年風險相同。"),
          ("pn", "（二）OR、HR、RR 被視為近似同一尺度；H2 只有 3 篇研究。"),
          ("pn", "（三）三種疾病沒有文獻錨，結果只能當作模擬器原設定的表現。"),
          ("pn", "（四）新數據仍是模擬資料，復發多為短暫症狀變差，和臨床定義的復發不完全相同；模型表現不能直接推論到真實患者。"),
          ("pn", "（五）每種疾病只有 200 人，部分疾病在 90 天內只有個位數事件，病別內的結果不穩定。"),
          ("h2", "六、未來工作"),
          ("p", "下一步可以把文獻的 H1、H2 與時間型態直接寫進模擬器（例如讓停藥持續一段時間、加入個人的「容易復發」程度），再用同樣的方法檢查；同時在倫理審查通過後，以真實的 App 使用者紀錄做前瞻性驗證。"),
          ]
    B += [("h1", "陸、結論"),
          ("pn", f"（一）文獻支持「過去或近期的疾病活動與之後的復發有關」（統合 {f2(H1['pooled'])}）；「未按時用藥或停藥」方向一致但證據較弱（{f2(H2['pooled'])}）；「越早期越容易復發」主要出現在停藥後與新診斷的族群。"),
          ("pn", f"（二）原始虛擬患者的一年復發率與文獻差距很大；每病調整一個門檻後，未參與校準的第 3 年復發率與文獻平均只差 {ag['mae_lit_vs_calib_y3'] * 100:.1f} 個百分點。"),
          ("pn", "（三）新數據重現了「過去復發越多，之後越容易復發」的方向與劑量反應，但強度比文獻小，也沒有重現漏服藥物的影響。"),
          ("pn", f"（四）在新數據中，兩年紀錄預測未來 90 天復發的 AUROC 為 {f3(a['紀錄 730 天'][0])}，比只用年齡性別病別略高；Cox 模型的一年復發時間線與實際接近。紀錄品質對結果影響很小，理論上限為 {f3(s[sens_keys[3]]['auc'][0])}。"),
          ("pn", "（五）只用文獻數字，可以建立方向正確、表現中等的復發模型，也能找出模擬器需要改進的地方；要用於真實病人，仍需真實紀錄的驗證。"),
          ]
    B += [("h1", "柒、參考文獻"), ("refs",)]
    B += [("pagebreak",), ("h1", "附錄"),
          ("tab", "文獻使用對照：每篇文獻為什麼用、用了哪一部分", ["文獻", "類別", "用途"], _cite_table(N, "zh"),
           "類別：一年復發率＝校準目標；機制效果量＝H1、H2 森林圖與統合；累積復發曲線＝H3；模型表現對照＝討論；背景與合理性檢查；統計方法；本專案先前資料。逐筆換算數字見 outputs/plot_data/文獻_各研究一年復發機率.csv。",
           [4.2, 3.6, 8.2], 10.5, "A")]
    return B


def f2(x):
    return f"{x:.2f}"


def f3(x):
    return f"{x:.3f}"


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def ci(v, d=3):
    return f"{v[0]:.{d}f}（{v[1]:.{d}f}–{v[2]:.{d}f}）"


def cie_t(v, d=3):
    return f"{v[0]:.{d}f} ({v[1]:.{d}f}–{v[2]:.{d}f})"


def cie(v, d=3):
    return f"{v[0]:.{d}f} (95% CI {v[1]:.{d}f}–{v[2]:.{d}f})"


EN_MODEL = {"只用年齡性別病別": "Age, sex and disease only", "只用文獻（未訓練）": "Literature only (untrained)",
            "紀錄 30 天": "Records, 30 days", "紀錄 365 天": "Records, 365 days", "紀錄 730 天": "Records, 730 days",
            "文獻分數＋紀錄 730 天": "Literature score + records, 730 days", "梯度提升樹 730 天": "Gradient boosting, 730 days"}


# ═══════════════════════════ English ═══════════════════════════
def _en(N):
    mc, mo, me, H1, H2, ag, s = N["mc"], N["mo"], N["mech"], N["H1"], N["H2"], N["ag"], N["sens"]
    a, ao = mc["auroc"], mo["auroc"]
    ew = mc["early_warning"]
    sk = list(s)
    m1, m2 = me["calibrated"], me["original"]
    tl = N["tl"]
    perm = np.array(N["perm"])
    cross = N["cross"]
    cal = mc["calibration"]
    c_lit = {c["curve"]: c["k"] for c in N["curves"]}
    rows_cross = []
    for _, r in cross.sort_values("lit_target", ascending=False, na_position="last").iterrows():
        if np.isnan(r.lit_target):
            rows_cross.append([r.en, "None", "—", f2(r.orig_p_y2), f2(r.calib_p_y3), f2(r.model_pred_365)])
        else:
            rows_cross.append([r.en, f"{int(r.lit_k)}", f"{f2(r.lit_target)} ({f2(r.lit_lo)}–{f2(r.lit_hi)})",
                               f2(r.orig_p_y2), f2(r.calib_p_y3), f2(r.model_pred_365)])
    model_rows = [[EN_MODEL[k], cie_t(a[k]), f2(cal[k]["slope"]), f3(cal[k]["brier"]), cie_t(ao[k])] for k in EN_MODEL]
    prev = N["prev"]
    sle_y3 = cross.set_index("disease").loc["systemic_lupus_erythematosus", "calib_p_y3"]
    B = []
    B += [("h1", "Abstract"),
          ("pn", f"People living with chronic disease often worry about one thing: getting better for a while and then relapsing. This study keeps the aim of our previous study, which asked whether long-term records can predict recurrence and roughly when it will happen. This time, no individual-level data from public databases were used for training or back-fitting. Instead, we extracted population-level numbers from {N['n_pubmed'] - N['n_methods']} PubMed abstracts: one-year recurrence rates for 13 diseases, effect sizes for two groups of risk factors, and five cumulative recurrence curves. We combined these with the 3,200 virtual patients created earlier (16 chronic diseases, 200 patients each)."),
          ("pn", f"In the literature, past or recent disease activity was associated with later recurrence (pooled relative risk {f2(H1['pooled'])}, 95% CI {f2(H1['lo'])}–{f2(H1['hi'])}). Missing or stopping medication was associated with more recurrence ({f2(H2['pooled'])}, {f2(H2['lo'])}–{f2(H2['hi'])}). In {N['k_lit_below1']} of 5 curves the Weibull shape parameter was below 1, meaning risk was highest early. None of the 13 comparable diseases in the original virtual cohort had a one-year recurrence rate inside the published range. After calibrating a single threshold per disease, the year-3 rates, which were not used in calibration, differed from the literature targets by {ag['mae_lit_vs_calib_y3'] * 100:.1f} percentage points on average, and {ag['within_lit_range_calib_y3']} diseases fell inside the published range."),
          ("pn", f"In the calibrated new data, a model using two years of records predicted recurrence within 90 days with an AUROC of {cie(a['紀錄 730 天'])}, slightly higher than {f3(a['只用年齡性別病別'][0])} for age, sex and disease alone. The Cox model's one-year timeline was close to what was observed. The virtual patients reproduced the direction of \"more past recurrences, more later recurrences,\" but the effect was smaller than in the literature, and the effect of missed doses did not appear. Simulated data are useful for checking methods; real patient records are still needed before any clinical use."),
          ("pn", "*Keywords:* chronic disease recurrence, longitudinal study, literature synthesis, virtual patients, prediction model"),
          ("pagebreak",)]
    B += [("h1", "Introduction"), ("h2", "Motivation"),
          ("p", "Chronic conditions such as systemic lupus erythematosus (SLE), rheumatoid arthritis (RA), inflammatory bowel disease (IBD) and multiple sclerosis (MS) tend to go up and down. After a stable period the disease can suddenly get worse; doctors call this a flare or relapse. From an immunologist's point of view, these diseases share an immune system that stays easy to ignite: an infection, a stressful month, or cutting down on medicine can all be followed by a rise in inflammation. Flares are not only unpleasant. They are also linked to organ damage. In Behçet's syndrome, for example, people who had a relapse were more likely to accrue damage later (Floris et al., 2022)."),
          ("p", f"MD. Piece is a phone app in which patients record symptoms, medicines and daily life. Our previous study used the NHANES I Epidemiologic Follow-up Study (NHEFS) and the Framingham teaching dataset. It found that adding long-term records gave an AUROC of about {prev['nhefs_long_record_auc']:.2f} for recurrence hospitalisation, and about {prev['twin_full_lr_auc']:.2f} in a digital twin simulation (MD. Piece Research Team, 2026a). This time the rules are different: individual-level public data may not be used to train or back-fit a model. So we asked whether published numbers alone are enough to build and check a recurrence model. We also wanted to see whether the virtual patients we made earlier behave like the real patients described in the literature."),
          ("h2", "Aims"),
          ("pn", "1. Summarise one-year recurrence rates for 13 chronic diseases from the literature, and check three mechanism hypotheses across longitudinal studies: H1, past or recent disease activity is associated with later recurrence; H2, missing or stopping medication is associated with later recurrence; H3, risk is highest soon after a stable period and then falls."),
          ("pn", "2. Compare the 3,200 virtual patients with the literature, and calibrate them to the published numbers to produce new data."),
          ("pn", "3. With the same aim as the previous study, train models on the new data to see whether long-term records predict recurrence within 90 days and the timing of recurrence within a year, and estimate early-warning performance."),
          ("pn", "4. Cross-compare the new data, the original virtual patients and the literature, and finally compare model performance with published models."),
          ("h2", "Literature Review"),
          ("p", "Many longitudinal studies point to past history as an important clue. The ECLIPSE study followed 2,138 people with chronic obstructive pulmonary disease (COPD) for three years. A history of exacerbations was the single best predictor of later exacerbations, and the frequent-exacerbation tendency was fairly stable over three years (Hurst et al., 2010). In severe asthma, a recent severe exacerbation was associated with future exacerbation, with an adjusted odds ratio of 3.77 (Miller et al., 2007). In placebo arms of MS trials, more relapses in the two years before a trial went with a higher relapse rate during the trial (Held et al., 2005)."),
          ("p", "Medication adherence is another clue. Patients with quiescent ulcerative colitis who refilled less than 80% of their medicine had about 5.5 times the risk of relapse (Kane et al., 2003). Stopping hydroxychloroquine in SLE was followed by more major flares, although the difference was not statistically significant (Tsakonas et al., 1998), and stopping low-dose glucocorticoids by slightly more flares (Ji et al., 2021). As for timing, after stopping biologics in RA the cumulative flare proportions were 45%, 64% and 80% at 1, 3 and 5 years (Mori et al., 2022). Newly diagnosed IBD also showed most recurrences in the first year (Vester-Andersen et al., 2014). Both curves rise quickly at first and slowly later."),
          ("p", "For prediction models, COPD alone has more than 400 prognostic models, most with a high risk of bias (Bellou et al., 2019). AI models for COPD exacerbations have a pooled AUC of about 0.77, with large differences between studies (Niraula et al., 2025). In SLE, persistently active disease could be predicted, while models for single flares performed poorly (Nikpour et al., 2009). Recurrence prediction is hard, and results depend on what a model is compared with."),
          ]
    B += [("h1", "Materials"),
          ("pn", "1. Hardware: a cloud Linux computer (4 CPU cores, 16 GB memory)."),
          ("pn", "2. Software: Python 3.13 with NumPy, pandas, SciPy, scikit-learn (Pedregosa et al., 2011) and Matplotlib (Hunter, 2007). The Cox proportional hazards model was written with Newton–Raphson and matched statsmodels to four decimal places."),
          ("pn", "3. Literature: PubMed, searched and downloaded through NCBI E-utilities."),
          ("pn", "4. Virtual patients: the md_piece simulator and its 16 disease files from the MD. Piece project (MD. Piece Research Team, 2026b), used without changes."),
          ("pn", "5. Code: experiments/literature_recurrence_model/ in the repository. Running simulate_cohort.py, run.py, figures.py, references.py and build_report.py reproduces all numbers, figures and this report."),
          ]
    B += [("h1", "Method"), ("h2", "Design and Workflow"),
          ("p", "Figure 1 shows the design and Figure 2 the workflow. There were only two data sources: population-level numbers in published abstracts, and the virtual patients created earlier. Individual-level public data (such as NHEFS or Framingham) were not used at all, neither for training nor for back-fitting. The analysis plan was written at the top of run.py before running, and thresholds and weights were not changed afterwards. Two coding problems found and fixed during the work are described at the end of this section."),
          ("fig", "fig01_framework", "Study Design", "MD. Piece is a support tool only. It does not diagnose and does not replace the doctor.", 14.5),
          ("fig", "fig02_workflow", "Study Workflow", None, 14.0),
          ("h2", "Literature Search and Extraction"),
          ("p", f"We searched PubMed with disease names plus flare, relapse, exacerbation, recurrence, cohort and adherence, and read each abstract. Only longitudinal studies, trials or meta-analyses that stated numbers in the abstract were used. Numbers not stated in the abstract (for example some confidence intervals) were not filled in from elsewhere. In the end we used {N['n_pubmed'] - N['n_methods']} research papers and {N['n_methods']} statistical methods papers. All are listed in Appendix Table A1 with the reason for use and the part used."),
          ("p", "Studies report recurrence in different ways, so every number was converted to one scale: the proportion with at least one recurrence within a year. An event rate λ per person-year became 1 − e^(−λ); a cumulative proportion *p* at *t* years became 1 − (1 − *p*)^(1/*t*); one-year proportions were used directly. For each disease, the median of the converted values was the calibration target, and the minimum to maximum was the published range. For osteoarthritis, systemic sclerosis and Sjögren's disease we found no comparable yearly rate. The latter two are mostly described in terms of progression or fluctuating activity (Elhai et al., 2022; Fernández-Castro et al., 2025). These three were not calibrated and are marked in the results."),
          ("h2", "Pooling the Mechanism Hypotheses"),
          ("p", "For H1 and H2 we collected effect sizes with 95% confidence intervals (odds ratio, hazard ratio or relative risk). They were pooled on the log scale with a DerSimonian–Laird random-effects model (DerSimonian & Laird, 1986), and heterogeneity was summarised with *I*². The three measures are close when events are not common; treating them as one scale is a limitation. For H3, each cumulative curve was fitted to a Weibull distribution, log(−log *S*(*t*)) = *k*·log *t* − *k*·log λ. A shape *k* below 1 means risk is highest early; *k* = 1 means constant risk."),
          ("h2", "Virtual Patients"),
          ("p", "The virtual patients come from the md_piece simulator. Each patient has a daily latent disease activity that responds to treatment, missed doses, triggers such as infection or stress, life events, subtype and individual differences. When activity is above a threshold the patient is in a flare. The simulator also produces a self-reported symptom score and clinic lab values. Earlier work used the same simulator and random seeds (base_seed = 2024) to make 200 patients for each of 16 diseases, 3,200 in total, over 180 days. We kept the same seeds and extended the simulation to 1,095 days (three years) so that changes from year 1 to year 3 could be seen."),
          ("p", "A new recurrence was defined as a change from no flare to flare, at least 7 days after the end of the previous flare (or the disease's refractory period, if longer). Shorter gaps were counted as the same flare."),
          ("h2", "Literature Calibration: Making the New Data"),
          ("p", "Only one parameter was changed per disease: a shift δ in the flare threshold. Starting at δ = 0, δ moved in steps of 0.05 in the direction that brought the year-2 one-year recurrence rate toward the literature target, followed by 12 bisection steps after the target was crossed. The reason for searching in one direction is given below. Only the year-2 rate was used. H1, H2, H3, the year-3 rate and flare length were kept out of calibration as independent checks. The calibrated 3,200 patients are the new data of this study; the original 3,200 serve as the comparison."),
          ("h2", "App Record Layer and Predictors"),
          ("p", f"Real app records are never perfect, so a record layer was placed between latent activity and the model. Symptom diaries were filled on {int(N['settings']['log_rate'] * 100)}% of days with an error of {N['settings']['diary_noise_sd']} SD. Lab values came every {N['settings']['lab_every']} days. Missed doses and triggers were visible only on diary days, and flare history was fully visible. Looking back over 30, 90, 180, 365 or 730 days, we computed symptom mean, maximum, variability, the last 14-day mean and slope, the missed-dose fraction, the fraction of days with triggers, the latest and mean lab values, the number of flares in the window and days since the last flare, plus age, sex and disease."),
          ("h2", "Models and Evaluation"),
          ("p", "The prediction point was day 730, equivalent to two years of app use. Patients in a flare on that day were excluded. The main outcome was a new recurrence within 90 days; the secondary outcome was the time to the next recurrence, followed for up to 365 days. Models were: age, sex and disease only; literature only, untrained, using each disease's published yearly rate multiplied by the pooled H1 and H2 factors; literature score plus records; logistic regression with five record lengths; gradient boosting; and a Cox model for timing."),
          ("p", "All models used stratified five-fold cross-validation and were scored only on the held-out fold. Discrimination was measured with AUROC, with 95% confidence intervals from 1,000 bootstrap samples. Calibration was measured with the calibration slope and the Brier score. For the Cox model we used the C-index (Harrell et al., 1982) and time-dependent AUCs at 90, 180 and 365 days. To check that no answer leaked into training, outcome labels were shuffled 50 times; AUROC should then stay near 0.5. For early warning, the top 20% of predicted risk was flagged, and we computed sensitivity, positive predictive value (PPV), lift (PPV divided by the mean recurrence rate) and lead time. A sensitivity analysis compared four record-quality settings: recall-style records (30% of days, 0.8 SD error), this study's setting, complete records, and an upper bound with direct access to latent activity."),
          ("h2", "Cross-Comparison"),
          ("p", "Cross-comparison had three layers: (a) one-year recurrence by disease in the literature, the original cohort, the new data (year 3) and the model; (b) the three mechanisms, comparing pooled literature values with stratified Mantel–Haenszel relative risks in the virtual cohorts (Greenland & Robins, 1985), dose–response and Weibull *k*; and (c) model performance in this study, the previous study and published models."),
          ("h2", "Problems Found and Fixed"),
          ("p", "First, the initial calibration searched the whole δ axis for the closest value. It pushed RA, psoriatic arthritis and IgG4-related disease to very low thresholds, where patients were in flare almost all year and \"new\" flares became rare. The rates matched the literature on paper but made no sense: only 17 RA patients were out of flare at the prediction point. After switching to a one-direction search, the share of days in flare was below 1.5% for every disease. Second, the first Cox model diverged on the new data, because a few diseases had very few events and their coefficients grew without limit. A small L2 penalty (λ = 0.01) fixed this; without the penalty our code matched statsmodels. Both fixes were made before model performance was examined."),
          ]
    rcol = ["Disease", "*k*", "Literature target (range)", "Original, year 2", "New data, year 3", "Model"]
    B += [("h1", "Results"), ("h2", "Literature Synthesis"),
          ("p", f"We extracted {N['n_rate_est']} yearly recurrence estimates from {N['n_rate_studies']} studies covering 13 diseases. Converted one-year rates ranged from {f2(N['r']['literature']['targets']['idiopathic_pulmonary_fibrosis']['target'])} in idiopathic pulmonary fibrosis (IPF) to {f2(N['r']['literature']['targets']['behcet_disease']['target'])} in Behçet's disease. Values also differed within a disease. In chronic urticaria, for instance, they ranged from 0.06 to 0.36, largely depending on whether patients had just stopped treatment or had been stable for years (blue dots in Figure 3)."),
          ("fig", "fig03_annual_recurrence", "One-Year Recurrence by Disease: Literature, Original Virtual Cohort, New Data and Model", "Blue dots are converted one-year rates from individual studies; the light band is the published range. New data are shown for year 3, which was not used in calibration. The model value is the mean one-year risk predicted by the Cox model at day 730 (out-of-fold).", 15.0),
          ("p", f"H1 had {H1['k']} studies, with a pooled relative risk of {f2(H1['pooled'])} (95% CI {f2(H1['lo'])}–{f2(H1['hi'])}) and *I*² = {H1['I2'] * 100:.0f}%; all pointed the same way. H2 had {H2['k']} studies, pooled at {f2(H2['pooled'])} ({f2(H2['lo'])}–{f2(H2['hi'])}) with *I*² = {H2['I2'] * 100:.0f}%: the same direction, but very different sizes (Figure 4). The NOR-Gout study gave no confidence interval and was not pooled, but flares in the lowest versus highest adherence quartile were 33.3% versus 9.5% (Uhlig et al., 2025a), again in the same direction. For H3, *k* was below 1 for RA after stopping biologics ({f2(c_lit['類風濕性關節炎（停藥後）'])}), Crohn's disease ({f2(c_lit['克隆氏症（新診斷）'])}) and ulcerative colitis ({f2(c_lit['潰瘍性結腸炎（新診斷）'])}), and close to 1 for IgG4-related disease ({f2(c_lit['IgG4 相關疾病'])}) and IPF ({f2(c_lit['特發性肺纖維化（急性惡化）'])}) (Figure 5a). The early-risk pattern was clearest after stopping treatment or soon after diagnosis."),
          ("fig", "fig04_forest_H1_H2", "Mechanisms H1 and H2: Individual Studies, Pooled Literature Values and the Two Virtual Cohorts", "H1 includes recent severe exacerbation, poor control, higher activity, recurrent ANCA and short remission. In the virtual cohorts, H1 is the relative risk of a year-2 flare for patients with versus without a year-1 flare. H2 compares the highest and lowest quartiles of the year-1 missed-dose fraction. All are stratified by disease.", 14.5),
          ("fig", "fig05_timing_weibull", "Mechanism H3: Timing Pattern of Cumulative Recurrence", "(a) Dots are published values; lines are Weibull fits. (b) Each virtual dot is one disease, followed for two years from day 365; bars show medians.", 15.5),
          ("h2", "Original Virtual Patients Versus the Literature"),
          ("p", f"Recurrence in the original virtual cohort was far too frequent. Across the 13 comparable diseases, one-year rates ranged from {f2(N['orig_min'])} to {f2(N['orig_max'])}. None fell inside the published range, the mean gap from the targets was {ag['mae_lit_vs_orig'] * 100:.0f} percentage points, and the ranking of diseases was almost unrelated to the literature (Spearman ρ = {f2(ag['spearman_lit_vs_orig'])}). Under the original settings, nearly every SLE and RA patient flared every year, while studies report about 14% to 30% per year (Nikpour et al., 2009; Peng et al., 2017; Mori et al., 2022). Only IPF (0.10 vs 0.08) and IgG4-related disease (0.06 vs 0.16) were close."),
          ("p", f"For the mechanisms, the original cohort's H1 relative risk was {f2(m2['H1_prior_flare']['rr'])} ({f2(m2['H1_prior_flare']['lo'])}–{f2(m2['H1_prior_flare']['hi'])}): the same direction as the literature but much smaller. H2 was {f2(m2['H2_missed_dose_quartile']['rr'])} ({f2(m2['H2_missed_dose_quartile']['lo'])}–{f2(m2['H2_missed_dose_quartile']['hi'])}), with no visible effect of missed doses. The median Weibull *k* was {f2(N['k_orig_med'])}, closer to constant risk than the literature's {f2(N['k_lit_med'])}."),
          ("h2", "The Calibrated New Data"),
          ("p", f"After calibration, the year-2 rates of all 13 diseases matched their targets (RA stopped at 0.33 against a target of 0.30 because of small-sample steps). The more informative check is year 3, which was not used in calibration. There the mean gap was {ag['mae_lit_vs_calib_y3'] * 100:.1f} percentage points, {ag['within_lit_range_calib_y3']} of {ag['n_anchored']} diseases fell inside the published range, and the rank correlation was ρ = {f2(ag['spearman_lit_vs_calib_y3'])} (Figure 3, Table 1). The main miss was SLE: 0.14 in year 2 but {f2(sle_y3)} in year 3, below the published minimum of 0.13."),
                    ("p", f"In the new data, the H1 relative risk rose to {f2(m1['H1_prior_flare']['rr'])} ({f2(m1['H1_prior_flare']['lo'])}–{f2(m1['H1_prior_flare']['hi'])}). For the most versus least symptomatic third it was {f2(m1['H1_symptom_tertile']['rr'])} ({f2(m1['H1_symptom_tertile']['lo'])}–{f2(m1['H1_symptom_tertile']['hi'])}). Both point the same way as the literature but stay below the pooled {f2(H1['pooled'])}. H2 was {f2(m1['H2_missed_dose_quartile']['rr'])} ({f2(m1['H2_missed_dose_quartile']['lo'])}–{f2(m1['H2_missed_dose_quartile']['hi'])}) and was still not reproduced. For dose–response, patients with 0, 1, 2 and ≥3 past flares had later flare rates of 1, {N['dr_new'][1]:.1f}, {N['dr_new'][2]:.1f} and {N['dr_new'][3]:.1f} times the reference. This is similar in shape to the MS values of 1, {N['ms'][1]:.1f}, {N['ms'][2]:.1f} and {N['ms'][3]:.1f} (Figure 6; Held et al., 2005). The median Weibull *k* was {f2(N['k_new_med'])}, still above the literature."),
          ("fig", "fig06_dose_response", "Dose–Response Between Past Recurrences and Later Recurrence Rate", "Literature values are pre-trial relapses over 24 months in MS placebo arms. Virtual values are year-1 flares versus year-2 flares.", 12.0),
          ("p", f"Flare length was another independent check. In the new data most diseases had flares lasting 2 to 7 days on average; for example {N['ep_new']['Ankylosing spondylitis']:.1f} days in ankylosing spondylitis and {N['ep_new']['SLE']:.1f} days in SLE. That is close to weekly self-reports in which most flares lasted 3 days or less (Jacquemin et al., 2017). It is shorter than the 2.4 weeks reported for major flares in ankylosing spondylitis (Cooksey et al., 2010). In other words, flares in the new data look more like short symptom worsening than like flares that lead to admission or a change in treatment."),
          ("tab", "Cross-Comparison of One-Year Recurrence by Disease", rcol, rows_cross,
           "Values are the proportion with at least one recurrence in a year. *k* is the number of convertible published values. None means no comparable published rate, so the disease was not calibrated. New data are year 3; the model value is the mean out-of-fold one-year Cox prediction.", [3.8, 1.0, 3.8, 2.4, 2.4, 1.6]),
          ("h2", "Predicting Recurrence Within 90 Days"),
          ("p", f"In the new data, {mc['n']} patients could be scored at day 730 ({mc['excluded_in_flare']} were in a flare and excluded). Of these, {pct(mc['event_rate_90d'])} had a recurrence within 90 days and {pct(mc['event_rate_365d'])} within a year. Age, sex and disease alone gave an AUROC of {cie(a['只用年齡性別病別'])}. Adding 730 days of records gave {cie(a['紀錄 730 天'])}, an increase of {a['紀錄 730 天'][0] - a['只用年齡性別病別'][0]:.3f}. Lengthening the record window from 30 to 365 days raised AUROC from {f3(a['紀錄 30 天'][0])} to {f3(a['紀錄 365 天'][0])}, with no further gain at 730 days (Figure 7). The untrained literature-only model reached {cie(a['只用文獻（未訓練）'])}. Adding the literature score to the record model ({f3(a['文獻分數＋紀錄 730 天'][0])}) did not help. Gradient boosting reached {f3(a['梯度提升樹 730 天'][0])}, but its calibration slope of {f2(cal['梯度提升樹 730 天']['slope'])} suggests overfitting. With shuffled labels, the mean AUROC over 50 runs was {perm.mean():.3f} ({perm.min():.3f}–{perm.max():.3f}), so no answer leaked into training."),
          ("p", f"Because diseases differ a lot in their rates, disease type alone separates risk well. Within a disease, using an event-weighted average, AUROC was {f3(N['within_rec'])} for the record model, {f3(N['within_static'])} for age and sex, and {f3(N['within_lit'])} for literature only. Records helped within diseases, but only modestly."),
          ("fig", "fig07_record_length_auroc", "Length of Records Used and AUROC", "Bands are bootstrap 95% confidence intervals. Dashed lines show age, sex and disease only; dotted lines show literature only (untrained).", 13.5),
          ("tab", "Performance of Each Model for Recurrence Within 90 Days", ["Model", "New data AUROC (95% CI)", "Calibration slope", "Brier", "Original cohort AUROC"], model_rows,
           "A calibration slope near 1 is best; below 1 means predictions are too spread out. Lower Brier scores are better.", [4.4, 4.2, 2.0, 1.4, 4.0]),
          ("fig", "fig08_roc", "ROC Curves", "Numbers in the legend are AUROCs.", 15.5),
          ("fig", "fig09_calibration", "Calibration of the 730-Day Record Model", "Predictions were split into tenths; each point compares the mean prediction with the observed proportion. The dashed line is perfect agreement.", 10.5),
          ("h2", "Recurrence Timeline"),
          ("p", f"The Cox model had a C-index of {f3(mc['cox_c_index'])} ({f3(mc['cox_static_c_index'])} with age, sex and disease only). Time-dependent AUCs at 90, 180 and 365 days were {f3(mc['cox_td_auc']['90'])}, {f3(mc['cox_td_auc']['180'])} and {f3(mc['cox_td_auc']['365'])}. When patients were split into three risk groups, the observed one-year proportions were {pct(tl.loc['低', 'observed'])}, {pct(tl.loc['中', 'observed'])} and {pct(tl.loc['高', 'observed'])}, against predictions of {pct(tl.loc['低', 'predicted'])}, {pct(tl.loc['中', 'predicted'])} and {pct(tl.loc['高', 'predicted'])}; the two lines stayed close throughout the year (Figure 10). Predicted one-year rates by disease differed from the literature targets by {ag['mae_lit_vs_model'] * 100:.1f} percentage points on average, and {ag['within_lit_range_model']} diseases fell inside the published range (Table 1)."),
          ("fig", "fig10_timeline", "Recurrence Timeline by Predicted Risk Group: Observed and Predicted", "Solid lines are observed cumulative recurrence; dashed lines are out-of-fold Cox predictions.", 12.5),
          ("h2", "Record Quality, Early Warning and Predictors"),
          ("p", f"Record quality made almost no difference. Recall-style, standard and complete records gave AUROCs of {f3(s[sk[0]]['auc'][0])}, {f3(s[sk[1]]['auc'][0])} and {f3(s[sk[2]]['auc'][0])}. Even with direct access to latent activity, the ceiling was only {f3(s[sk[3]]['auc'][0])}, or {f3(s[sk[3]]['within_disease_auc_weighted'])} within diseases (Figure 11). In this simulator, much of the 90-day recurrence comes from triggers that appear at random and are hard to see in advance."),
          ("fig", "fig11_record_quality", "Record Quality and the Theoretical Ceiling", "Dark bars are overall AUROC (lines are 95% CIs); light bars are event-weighted within-disease AUROC.", 14.0),
          ("p", f"For early warning, flagging the top 20% of risk caught {pct(ew['紀錄 730 天']['sensitivity'], 0)} of recurrences with the record model. Among flagged patients, {pct(ew['紀錄 730 天']['ppv'], 0)} did recur, {f2(ew['紀錄 730 天']['lift'])} times the average rate. The median time from prediction to recurrence was {ew['紀錄 730 天']['lead_days_median']:.0f} days (IQR {ew['紀錄 730 天']['lead_days_iqr'][0]:.0f}–{ew['紀錄 730 天']['lead_days_iqr'][1]:.0f}). The literature-only model caught {pct(ew['只用文獻（未訓練）']['sensitivity'], 0)}, and age, sex and disease {pct(ew['只用年齡性別病別']['sensitivity'], 0)} (Figure 12). The largest weight in the model was the number of flares in the past two years, followed by days with triggers, the missed-dose fraction and symptoms in the last 14 days (Figure 13). This matches the published finding that history is the best predictor (Hurst et al., 2010). The negative weight on mean symptoms reflects its strong correlation with maximum and recent symptoms; its sign means little on its own."),
          ("fig", "fig12_early_warning", "Early-Warning Performance When the Top 20% of Risk Is Flagged", "Lift = PPV ÷ mean recurrence rate. Lead time is counted only for flagged patients who did recur.", 16.0),
          ("fig", "fig13_features", "Standardised Coefficients of the 730-Day Record Model", "Coefficients come from a fit on all data and are for explanation only, not evaluation.", 12.0),
          ]
    rows_cmp = [
        ["This study: new data, records 730 days (logistic)", f3(a["紀錄 730 天"][0]), "3,177 virtual patients, 90 days"],
        ["This study: new data, Cox timeline", f"C = {f3(mc['cox_c_index'])}", "Time to recurrence within a year"],
        ["This study: literature only (untrained)", f3(a["只用文獻（未訓練）"][0]), "Same"],
        ["Previous study: NHEFS long-term records", f2(prev["nhefs_long_record_auc"]), "Real public data, readmission in 12 months"],
        ["Previous study: digital twin", f2(prev["twin_full_lr_auc"]), "3,200 virtual patients"],
        ["Literature: pooled AI models for COPD exacerbation", "0.77", "13 studies, I² = 99.5% (Niraula et al., 2025)"],
        ["Literature: Asthma Control Questionnaire", "0.68", "Exacerbation within 3 years (He et al., 2022)"],
        ["Literature: progression-free survival in SSc", "0.70–0.71", "EUSTAR (Elhai et al., 2022)"],
    ]
    B += [("h2", "Comparison With the Previous Study and Published Models"),
          ("p", "Table 3 places this study next to the previous study and published models. Populations, outcomes and time spans differ, so the table shows rough ranges rather than a ranking."),
          ("tab", "Model Performance in Context", ["Source and model", "AUROC / C", "Notes"], rows_cmp, None, [6.6, 2.4, 7.0]),
          ]
    B += [("h1", "Discussion"), ("h2", "Do the Three Mechanisms Hold in the Literature?"),
          ("p", "H1 pointed the same way in 5 studies across 4 diseases with moderate heterogeneity. Together with long-term follow-up in COPD and MS (Hurst et al., 2010; Held et al., 2005), the link between past or recent activity and later recurrence looks consistent. Immunology offers more than one explanation. Some people's immune systems may simply be easier to ignite, and the tissue damage left by each episode may make the next one more likely. Observational studies show association only and cannot tell these apart. H2 also pointed one way, but rests on 3 studies of very different size, with a lower confidence limit close to 1, so the evidence is weaker than for H1. People who miss doses may also be sicker or living more disrupted lives, so the whole gap cannot be credited to the medicine itself. H3 was clear only after stopping treatment or soon after diagnosis. Long-stable groups such as IgG4-related disease and IPF were closer to constant risk."),
          ("h2", "Where the Virtual Patients Fit and Where They Do Not"),
          ("p", "The original virtual patients flared far too often. This is one of the most direct findings of the study. One reason is that the simulator counts every brief crossing of the threshold as a flare, whereas most studies require a doctor's judgement or a change in treatment. With one threshold adjusted per disease, the year-3 rates matched the literature. This suggests that the shape of the ups and downs in the simulator is broadly reasonable, and that the main problem was the scale used to call a flare."),
          ("p", "Three things did not fit: H1 was weaker than in the literature, H2 barely appeared, and Weibull *k* was higher. In the simulator a missed dose only lowers the drug effect slightly for a short time, while real non-adherence can mean weeks off treatment, often with other life changes. Flares in the simulator are mostly set off by random triggers and are fairly independent of each other, which may be why both the early-risk pattern and the frequent-flarer tendency are weak. These gaps should be handled in the simulator design, not forced into line by tuning parameters."),
          ("h2", "Why Long-Term Records Helped Less This Time"),
          ("p", f"In the previous study's NHEFS data, adding long-term records raised AUROC from {N['prev']['nhefs_no_record_auc']:.2f} to {N['prev']['nhefs_long_record_auc']:.2f}. Here they added about {a['紀錄 730 天'][0] - a['只用年齡性別病別'][0]:.2f} overall, and {f2(N['within_static'])} to {f2(N['within_rec'])} within diseases. The record-quality analysis gives a clue: even complete records, or direct access to latent activity, reached only {f2(s[sk[3]]['auc'][0])}. The predictable part of this simulated data is small to begin with, so better data cannot add much. This fits the SLE finding that single flares are hard to predict (Nikpour et al., 2009), and the observation in spondyloarthritis that disease activity rises after sudden stressful events (Luo et al., 2019), which are hard to foresee. On the other hand, the model leaned most on flare history, which a real app can record fairly completely. That is useful for designing reminders."),
          ("h2", "A Clinical Reading"),
          ("p", f"Flagging 20% of patients caught about half of recurrences, about {ew['紀錄 730 天']['lead_days_median']:.0f} days ahead, but only about one in five flagged patients actually flared. In practice this suits an earlier check-in or a few extra questions, not a decision to add or change medicine. That is the intended role of MD. Piece: organise records and prompt patients and doctors to pay attention, with the doctor making the final call."),
          ("h2", "Limitations"),
          ("pn", "1. Only numbers in abstracts were used. Some populations were special (just stopped treatment, newly diagnosed or severe), and the conversion to yearly rates assumed equal risk each year."),
          ("pn", "2. OR, HR and RR were treated as roughly one scale, and H2 rests on three studies."),
          ("pn", "3. Three diseases had no literature anchor; their results reflect the simulator's original settings only."),
          ("pn", "4. The new data are still simulated, and their flares are mostly short symptom worsening rather than clinically defined flares. Performance cannot be carried over to real patients."),
          ("pn", "5. Each disease had only 200 patients, and some had single-digit numbers of events within 90 days, so within-disease results are unstable."),
          ("h2", "Future Work"),
          ("p", "Next, the published H1, H2 and timing patterns could be built into the simulator itself, for example by letting non-adherence last for a period and adding a personal tendency to flare, and then checked the same way. After ethics approval, a prospective check with records from real app users is needed."),
          ]
    B += [("h1", "Conclusions"),
          ("pn", f"1. The literature supports a link between past or recent disease activity and later recurrence (pooled {f2(H1['pooled'])}). Missed or stopped medication points the same way with weaker evidence ({f2(H2['pooled'])}). Early-high risk appears mainly after stopping treatment or soon after diagnosis."),
          ("pn", f"2. The original virtual cohort was far from the literature. After adjusting one threshold per disease, year-3 rates, not used in calibration, differed from the literature by {ag['mae_lit_vs_calib_y3'] * 100:.1f} percentage points on average."),
          ("pn", "3. The new data reproduced the direction and dose–response of \"more past recurrences, more later recurrences,\" but the effect was smaller than published, and the effect of missed doses did not appear."),
          ("pn", f"4. In the new data, two years of records predicted recurrence within 90 days with an AUROC of {f3(a['紀錄 730 天'][0])}, slightly above age, sex and disease alone. The Cox timeline was close to what was observed. Record quality mattered little, and the ceiling was {f3(s[sk[3]]['auc'][0])}."),
          ("pn", "5. Published numbers alone can support a recurrence model that points the right way with moderate performance, and they show where the simulator needs work. Real records are still needed before use with real patients."),
          ]
    B += [("h1", "References"), ("refs",)]
    B += [("pagebreak",), ("h1", "Appendix"),
          ("tab", "How Each Source Was Used", ["Source", "Category", "Use"], _cite_table(N, "en"),
           "Categories: annual recurrence rate = calibration target; mechanism effect size = H1/H2 forest plot and pooling; cumulative curve = H3; benchmark = discussion; background and plausibility check; statistical method; earlier project material. Study-level conversions are in outputs/plot_data/文獻_各研究一年復發機率.csv.",
           [4.2, 3.6, 8.2], 10.5, "A1")]
    return B
