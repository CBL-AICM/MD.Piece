"""產生參考文獻清單（APA 第 7 版）與「每篇文獻為什麼用、用了哪一部分」對照表。

書目資料取自 PubMed E-utilities（只存書目，不存摘要全文）：outputs/literature_metadata.json。
跑法：
  python experiments/literature_recurrence_model/references.py [PubMed 快取資料夾]   # 給快取時先更新 metadata
"""
from __future__ import annotations

import json
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(HERE, "outputs", "literature_metadata.json")

JOURNAL = {  # PubMed 期刊名 → APA 用的完整刊名（標題大小寫）
    "Arthritis Rheum": "Arthritis & Rheumatism", "Clin Rheumatol": "Clinical Rheumatology",
    "Lupus Sci Med": "Lupus Science & Medicine", "PLoS One": "PLOS ONE", "RMD Open": "RMD Open",
    "Pulm Pharmacol Ther": "Pulmonary Pharmacology & Therapeutics",
    "Asian Pac J Allergy Immunol": "Asian Pacific Journal of Allergy and Immunology", "Dermatol Ther": "Dermatologic Therapy",
    "Ann Rheum Dis": "Annals of the Rheumatic Diseases", "Arthritis Rheumatol": "Arthritis & Rheumatology",
    "N Engl J Med": "The New England Journal of Medicine", "J Crohns Colitis": "Journal of Crohn's and Colitis",
    "Am J Med": "The American Journal of Medicine", "Scand J Gastroenterol": "Scandinavian Journal of Gastroenterology",
    "Rheumatology (Oxford)": "Rheumatology", "Sarcoidosis Vasc Diffuse Lung Dis": "Sarcoidosis, Vasculitis, and Diffuse Lung Diseases",
    "Respir Investig": "Respiratory Investigation", "Respir Med": "Respiratory Medicine",
    "Ann Transl Med": "Annals of Translational Medicine", "Clin Exp Immunol": "Clinical and Experimental Immunology",
    "Lupus": "Lupus", "Neurology": "Neurology", "Front Digit Health": "Frontiers in Digital Health", "BMJ": "BMJ",
    "Lancet Rheumatol": "The Lancet Rheumatology", "Expert Rev Clin Immunol": "Expert Review of Clinical Immunology",
    "Semin Arthritis Rheum": "Seminars in Arthritis and Rheumatism", "J Rheumatol": "The Journal of Rheumatology",
    "J Med Econ": "Journal of Medical Economics", "Ann Neurol": "Annals of Neurology",
    "Arthritis Res Ther": "Arthritis Research & Therapy", "Joint Bone Spine": "Joint Bone Spine",
    "ERJ Open Res": "ERJ Open Research", "Rheumatol Int": "Rheumatology International",
    "Control Clin Trials": "Controlled Clinical Trials", "JAMA": "JAMA", "Biometrics": "Biometrics",
}

# PMID: (用途分類, 中文：為什麼用／用了哪部分, English: why / which part)
USAGE = {
    "19714602": ("A,D", "狼瘡年復發率（每年約 1/3 患者復發）；討論「單次復發難預測」", "SLE annual flare proportion (~1/3 per year); discussion of poor flare prediction"),
    "28929239": ("A", "狼瘡每年復發比例 13.0–15.7%", "SLE yearly flare proportion 13.0–15.7%"),
    "36631164": ("A", "狼瘡 14.8 個月內 16% 復發，換算年復發率", "SLE 16% flares in 14.8 months, converted to annual"),
    "35737642": ("A,C", "RA 停藥後 0.36 次/人年；1/3/5 年累積復發 45/64/80%（Weibull）", "RA 0.36 flares/person-year; cumulative 45/64/80% at 1/3/5 y (Weibull)"),
    "29862047": ("A,B", "RA 減量 12 個月 41/97 復發；DAS28 HR 1.96（H1）", "RA tapering 41/97 flares in 12 mo; DAS28 HR 1.96 (H1)"),
    "33864158": ("A", "RA、PsA、中軸型脊椎關節炎拉長給藥 12 個月持續率", "12-month persistence of bDMARD spacing in RA, PsA, axSpA"),
    "40774410": ("A", "氣喘年惡化 0.17 與 0.42 次", "Asthma annual exacerbation rates 0.17 and 0.42"),
    "40321140": ("A,B", "蕁麻疹緩解後再發 10.6%；緩解 < 3 年 OR 5.13（H1）", "CSU recurrence 10.6%; remission < 3 y OR 5.13 (H1)"),
    "34877757": ("A", "omalizumab 停藥後 45/124 再發", "CSU relapse after omalizumab: 45/124"),
    "29724729": ("A", "ANCA 血管炎 60 個月無重大復發 49.4%／71.9%", "AAV 60-month major relapse-free survival 49.4%/71.9%"),
    "40948107": ("A", "貝賽特氏症葡萄膜炎年化復發 0.28–0.95", "Behçet uveitis annualized relapse 0.28–0.95"),
    "20089952": ("A", "多發性硬化症年化復發率 0.40（安慰劑）與 0.18", "MS annualized relapse rate 0.40 (placebo) and 0.18"),
    "25154681": ("A,C", "IBD 第 1 年累積復發；CD 與 UC 1/5/7 年曲線（Weibull）", "IBD year-1 recurrence; CD and UC 1/5/7-y curves (Weibull)"),
    "12543288": ("A,B", "UC 12 個月 19/86 復發；未按時領藥 HR 5.5（H2）", "UC 19/86 relapses in 12 mo; nonadherence HR 5.5 (H2)"),
    "19101844": ("A", "UC 10 年內 83% 有復發病程", "UC: 83% relapsing course over 10 y"),
    "39292608": ("A,B", "痛風順從度高低四分位最近一年復發 9.5% vs 33.3%（H2 劑量對照）", "Gout flare 9.5% vs 33.3% by adherence quartile (H2 check)"),
    "21319592": ("A,C", "IPF 急性惡化 1/2/3 年 8.6/12.6/23.9%（Weibull）", "IPF acute exacerbation 8.6/12.6/23.9% at 1/2/3 y (Weibull)"),
    "32205147": ("A", "IPF 急性惡化 1 年 7.6%", "IPF acute exacerbation 7.6% at 1 y"),
    "32097488": ("A,C", "IgG4-RD 12/24/36 個月累積復發（Weibull）", "IgG4-RD cumulative relapse at 12/24/36 mo (Weibull)"),
    "33151477": ("A", "IgG4-RD 中位 21 個月 29.5% 難治或復發；停藥者較常復發", "IgG4-RD 29.5% refractory/relapsed in 21 mo; more after withdrawal"),
    "16914299": ("B", "氣喘近期嚴重惡化 → 未來惡化 OR 3.77（H1）", "Asthma recent severe exacerbation OR 3.77 (H1)"),
    "36660650": ("B,D", "氣喘控制不佳 OR 6.34（H1）；ACQ AUC 0.68 作模型表現對照", "Uncontrolled asthma OR 6.34 (H1); ACQ AUC 0.68 as benchmark"),
    "33020895": ("B", "ANCA 反覆升高型復發 HR 3.7（H1）", "Recurrent ANCA pattern relapse HR 3.7 (H1)"),
    "9541091": ("B", "停用 HCQ 復發 RR（0.43 取倒數）（H2）", "HCQ withdrawal RR (inverse of 0.43) (H2)"),
    "33576768": ("B", "停用低劑量類固醇復發 RR 1.38（H2）；17 篇統合", "Glucocorticoid withdrawal RR 1.38 (H2); 17-study meta-analysis"),
    "16344520": ("B", "MS 過去復發 0/1/2/≥3 次的劑量反應（圖 6）", "MS dose–response by prior relapses 0/1/2/≥3 (Figure 6)"),
    "41487303": ("D", "COPD AI 預測統合 AUC 0.77，作本研究 AUROC 對照", "COPD AI pooled AUC 0.77 as benchmark"),
    "31585960": ("D", "COPD 預後模型多數偏誤風險高，討論外部驗證的重要", "Most COPD prognostic models at high risk of bias"),
    "38265945": ("D,E", "硬皮症無惡化存活 AUC 0.70；說明 SSc 為進行型、無復發率", "SSc progression-free AUC 0.70; SSc is progressive, no flare rate"),
    "20843247": ("D", "COPD 過去惡化史是最強預測因子、表型 3 年穩定（H1 背景）", "COPD exacerbation history best predictor; phenotype stable 3 y (H1 background)"),
    "29463519": ("E", "狼瘡懷孕期復發 HR 1.59，HCQ 可減弱：說明誘發因子與用藥的交互", "SLE pregnancy flare HR 1.59, reduced with HCQ: triggers × treatment"),
    "40232132": ("E", "狼瘡停藥的復發危險因子回顧（H2 背景）", "Review of flare risk after withdrawal in SLE (H2 background)"),
    "33367569": ("E", "UC 一年黏膜癒合者之後復發 HR 0.5（早期狀態影響長期）", "UC mucosal healing at 1 y, later relapse HR 0.5"),
    "40056480": ("E", "痛風緩解率隨年數上升（時間型態背景）", "Gout remission rises over years (timing background)"),
    "31043541": ("E", "痛風無法達標的主因之一為服藥順從度差（H2 背景）", "Poor adherence as obstacle to gout remission (H2 background)"),
    "21138339": ("E", "難治型痛風每年 8.8 次：說明族群差異大，未納入目標", "Refractory gout 8.8 flares/y: subgroup, not used as target"),
    "31177284": ("E", "一般痛風患者每年 ≥3 次者少：支持不用難治型數字", "Few gout patients have ≥3 flares/y"),
    "16510744": ("E", "MS 藥物使復發率降 68%：說明治療狀態影響年復發率", "Natalizumab −68% relapse: treatment changes rates"),
    "8017890": ("E", "MS 自然病史：早期發作少者預後較好（H1 背景）", "MS natural history: few early attacks, better course"),
    "36397162": ("E", "貝賽特氏症復發與器官損傷相關（復發的臨床意義）", "Behçet relapse linked to damage accrual"),
    "40382308": ("E", "PsA 停藥後早期與晚期復發比例（時間型態背景）", "PsA early vs late flares after DMARD stop"),
    "20123954": ("E", "AS 自述復發頻繁且多為短暫：對照模擬中復發持續天數", "AS self-reported flares frequent and short; flare length check"),
    "28879046": ("E", "RA／axSpA 每週自述復發 28%、多數 ≤ 3 天：對照復發持續天數", "Weekly self-reported flares 28%, most ≤3 days; flare length check"),
    "29883766": ("E", "突發壓力事件後 SpA 活動度上升：支持模擬中的誘發因子設計", "Stressful events precede SpA activity rise: supports trigger design"),
    "38770009": ("E", "重度氣喘安慰劑組年惡化 1.31：說明族群嚴重度差異", "Severe asthma placebo 1.31/y: severity range"),
    "40526294": ("E", "乾燥症 9.5 年追蹤只描述活動度起伏，無復發率 → 不校準", "Sjögren's 9.5-y follow-up without flare rate → not calibrated"),
    "3802833": ("F", "隨機效應統合方法（DerSimonian–Laird）", "Random-effects pooling method"),
    "7069920": ("F", "C-index 計算方法", "C-index method"),
    "4005387": ("F", "分層 Mantel–Haenszel 相對風險的變異數", "Variance of stratified Mantel–Haenszel RR"),
}
CATEGORY = {"A": ("一年復發率（校準目標）", "Annual recurrence rate (calibration target)"),
            "B": ("機制效果量（H1／H2）", "Mechanism effect size (H1/H2)"),
            "C": ("累積復發曲線（H3）", "Cumulative curve (H3)"), "D": ("模型表現對照", "Benchmark for model performance"),
            "E": ("背景與合理性檢查", "Background and plausibility check"), "F": ("統計方法", "Statistical method")}

NON_PUBMED = [  # 不在 PubMed 的來源（軟體、本專案先前資料）
    ("Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. Computing in Science & Engineering, 9(3), 90–95. https://doi.org/10.1109/MCSE.2007.55",
     "F", "繪圖軟體", "Plotting software"),
    ("MD. Piece 研究團隊. (2026a). 慢性病縱向復發預測：MD. Piece 復發引擎 × 真實縱向資料與數位雙生 [未出版研究資料]. GitHub 儲存庫 cbl-aicm/md.piece，分支 claude/chronic-disease-recurrence-prediction-212dbc.",
     "G", "前一份研究：沿用其研究目的、評估方式（AUROC、預警、時間線）並對照其結果", "Previous study: same aim and metrics; results compared"),
    ("MD. Piece 研究團隊. (2026b). md_piece 虛擬患者模擬器與 16 種疾病設定 [電腦軟體]. GitHub 儲存庫 cbl-aicm/md.piece，分支 claude/train-ai-model-0NYvq.",
     "G", "3,200 位虛擬患者的來源（原封不動使用）", "Source of the 3,200 virtual patients (used unchanged)"),
    ("Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830.",
     "F", "logistic、梯度提升樹、交叉驗證", "Logistic regression, boosting, cross-validation"),
]
CATEGORY["G"] = ("本專案先前資料", "Earlier project material")


def _pages(p):
    if not p:
        return ""
    m = re.match(r"^([A-Za-z]*)(\d+)-([A-Za-z]*)(\d+)$", p)
    if m:
        a, b = m.group(2), m.group(4)
        if len(b) < len(a):
            b = a[: len(a) - len(b)] + b
        return f"{m.group(1)}{a}–{m.group(1)}{b}"
    return p


def _author(a):
    last, ini = a.split(", ") if ", " in a else (a, "")
    if last in ("None", ""):
        return None
    ini = " ".join(f"{c}." for c in ini.replace(" ", "")) if ini else ""
    return f"{last}, {ini}".strip().rstrip(",")


def apa(d):
    au = [x for x in (_author(a) for a in d["authors"]) if x]
    if len(au) >= 21:
        names = ", ".join(au[:19]) + ", ... " + au[-1]
    elif len(au) > 1:
        names = ", ".join(au[:-1]) + ", & " + au[-1]
    else:
        names = au[0] if au else ""
    title = d["title"].rstrip(".")
    j = JOURNAL.get(d["jabbr"], d["journal"])
    vol = d["vol"] or ""
    iss = f"({d['issue']})" if d["issue"] and d["issue"] != "None" else ""
    pg = _pages(d["pages"])
    src = f"{j}, {vol}{iss}" + (f", {pg}" if pg else "")
    doi = f" https://doi.org/{d['doi']}" if d["doi"] else ""
    names = names if names.endswith(".") else names + "."
    return f"{names} ({d.get('year_label', d['year'])}). {title}. {src}.{doi}"


def build(cache=None):
    if cache:
        meta = {}
        for pmid in USAGE:
            d = json.load(open(os.path.join(cache, f"{pmid}.json"), encoding="utf-8"))
            d.pop("abstract", None)
            meta[pmid] = d
        json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    meta = json.load(open(META, encoding="utf-8"))
    # 同一第一作者、同一年 → 依標題排序加 a、b（APA 7）
    keyed = {}
    for pmid in USAGE:
        d = meta[pmid]
        keyed.setdefault((d["authors"][0].split(",")[0], d["year"]), []).append(pmid)
    for (_, year), ids in keyed.items():
        if len(ids) > 1:
            for k, pmid in enumerate(sorted(ids, key=lambda i: meta[i]["title"].lower())):
                meta[pmid]["year_label"] = f"{year}{'abcdefgh'[k]}"
    rows = []
    for pmid, (cat, zh, en) in USAGE.items():
        d = meta[pmid]
        rows.append({"pmid": pmid, "apa": apa(d), "first_author": d["authors"][0].split(",")[0], "year": d.get("year_label", d["year"]),
                     "category": cat, "類別": "、".join(CATEGORY[c][0] for c in cat.split(",")),
                     "category_en": "; ".join(CATEGORY[c][1] for c in cat.split(",")),
                     "用途（為什麼用、用了哪部分）": zh, "usage_en": en})
    for ref, cat, zh, en in NON_PUBMED:
        rows.append({"pmid": "", "apa": ref, "first_author": ref.split(",")[0].split(".")[0], "year": "", "category": cat,
                     "類別": CATEGORY[cat][0], "category_en": CATEGORY[cat][1], "用途（為什麼用、用了哪部分）": zh, "usage_en": en})
    df = pd.DataFrame(rows).sort_values("apa", key=lambda s: s.str.lower()).reset_index(drop=True)
    df.to_csv(os.path.join(HERE, "outputs", "references_used.csv"), index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    df = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(len(df), "references;", (df.pmid != "").sum(), "from PubMed")
    print(df.apa.head(5).to_string())
