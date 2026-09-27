# -*- coding: utf-8 -*-
"""全國中小學科學展覽會作品說明書（v3.2）——數字全部由結果檔產生，不手打。
    python build_fair_v3_2.py
格式依中華民國第 64 屆中小學科學展覽會作品說明書附件五至七：封面只寫科別、組別、作品名稱、關鍵詞（最多 3 個）；
內文依序為作品名稱、摘要（300 字以內含標點符號）、壹前言（動機、目的、文獻回顧）、貳研究設備與器材、參研究過程與方法、
肆研究結果、伍討論、陸結論、柒參考文獻資料（APA）；標題次序壹、一、（一）、1、（1）；不得出現校名與姓名。
輸出：Obsidian 主稿（研究計畫書/科展作品說明書_v3.2.md，圖在 figure/v3_2/）與 repo 副本（experiments/docs/）。
Word：python -X utf8 md2docx.py <主稿.md> --fair"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8")
VAULT = r"C:\Users\tpc10\Desktop\01_研究專案\MD_Piece_腎臟研究\AIMD\腎炎模型\研究計畫書"
REPO_DOCS = os.path.join(os.path.dirname(ROOT), "docs")
NAME = "科展作品說明書_v3.2"
J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))
AU, EV, XX = J("results", "v3_2_cohort_audit.json"), J("results", "v3_2_eval.json"), J("results", "v3_2_external.json")
E, X = EV["axes"], XX["axes"]
R, TOOL, EX = J("results", "direction_v3_2_recalibration.json")["axes"], J("params", "direction_model_v3_2.json")["axes"], \
    J("params", "direction_demo_expected.json")
X3 = J("results", "external_2021_2023.json")["primary"]["axes"]
A3 = J("results", "v3_audit.json")
EXW, CK = J("results", "exwas_v3.json"), J("results", "exwas_v3_checks.json")
PROV = J("results", "provenance.json")["files"]
N_EXT = sum(k.endswith("_L.xpt") for k in PROV)
N_ALL, N_DEV = len(PROV), len(PROV) - N_EXT
MB = sum(v["bytes"] for v in PROV.values()) / 1e6
LOCK_TXT = open(os.path.join(ROOT, "requirements-lock.txt"), encoding="utf-8").read()
LOCK = dict(l.split("==") for l in LOCK_TXT.splitlines() if "==" in l)
PY = re.search(r"Python ([\d.]+)", LOCK_TXT).group(1)
PKGS = "、".join(f"{k} {LOCK[k].strip()}" for k in ("scikit-learn", "pandas", "numpy", "scipy", "matplotlib", "python-docx"))
NODE = "v24.14.0"   # 2026-09-27 `node --version`；網頁計算核對用
COMMITS = dict(plan_v3="bf269c5", proto="9ca4e9f", amend="44b0ace", ext="a7c4af8", dv="9edd968", plan_v32="f6abc91")
TITLE = "血液會說話嗎？以常規檢驗尋找腎臟指標異常的病因線索"
KEYWORDS = "病因線索、腎臟指標異常、預測模型校準"
FIGS = ["圖1_分析樣本與資料修正.png", "圖2_判別力.png", "圖3_校準_線性與非線性.png", "圖4_穩健性.png", "圖5_決策曲線.png",
        "圖6_暴露血尿比較.png", "圖7_外部資料.png", "圖8_重新校準交叉驗證.png"]
LR, HG = "LR_routine", "HGB_routine"


def n(x):
    return f"{x:,}"


def num(x, d=3):
    t = f"{x:.{d}f}"
    return ("−" + t[1:]) if t.startswith("-") and float(t) != 0 else t.lstrip("-")


def sgn(x, d=3):
    t = num(x, d)
    return t if t.startswith("−") else "+" + t


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def ci(c, d=3):
    return f"{num(c[0], d)} 至 {num(c[1], d)}" if min(c) < 0 else f"{c[0]:.{d}f}–{c[1]:.{d}f}"


# ── 常用數字（全部來自結果檔）
tot = lambda key: {k: sum(c[key][k] for c in AU["per_cycle"].values()) for k in ("pos", "neg", "unknown")}
HEP_T, DM_T, KID = tot("hep_v3_2"), tot("dm_v3_2"), AU["kidney"]["v3_2"]
m = lambda ax, s: E[ax]["models"][s]
auc = lambda ax, s: m(ax, s)["repeats"]["mean"]["auroc"]
ap = lambda ax, s: m(ax, s)["repeats"]["mean"]["ap"]
cal = lambda ax, s: m(ax, s)["calibration_repeat0"]
band = lambda ax, s: m(ax, s)["bands_tool_repeat0"]     # 工具實際輸出：資料不足者不給方向（Codex 稽核後改用）
pair = lambda ax, k: E[ax]["paired_repeat0"][k]
dauc = lambda ax, k: f"{sgn(pair(ax, k)['d_auroc'])}（95% CI {ci(pair(ax, k)['ci95']['d_auroc'])}）"
dvd = lambda ax, s: (lambda p: f"{sgn(p['d_auroc'])}（95% CI {ci(p['ci95']['d_auroc'])}）")(E[ax]["paired_vs_demographics_repeat0"][f"{s}−M1_demographics"])
xd = lambda ax, k: f"{sgn(X[ax]['paired'][k]['d_auroc'])}（95% CI {ci(X[ax]['paired'][k]['ci95']['d_auroc'])}）"
tmp = lambda ax, s: E[ax]["temporal"][s]
wt = lambda ax, s: E[ax]["design_weighted"][s]["weighted"]
xm = lambda ax, s: X[ax]["models"][s]
x3 = lambda ax, s: X3[ax]["models"][s]
cvq = lambda ax, k: XX["recalibration_cv"]["v3.2"][ax]["random_summary"][k]
qf = lambda d: f"{d['median']:.2f}（{d['p2_5']:.2f}–{d['p97_5']:.2f}）"
ST = E["肝炎"]["subtypes_LR_routine"]
SL = E["肝炎"]["single_label_LR_routine"]
XS = XX["hepatitis_subtypes_tool_v3_2"]
CH = AU["kidney_2017_2018_reported_vs_DxC"]
AV = AU["feature_availability_in_kidney"]
Pb = CK["metals"]["鉛"]
hdl_i = TOOL["肝炎"]["features"].index("LBDHDL")
HDL_MED = sum(fp["medians"][hdl_i] for fp in TOOL["肝炎"]["ensemble"]) / len(TOOL["肝炎"]["ensemble"])
DEMO_HDL = json.load(open(os.path.join(ROOT, "params", "direction_demo_patient.json"), encoding="utf-8"))["LBDHDL"]
skip = lambda ax, s: band(ax, s)["per_1000_if_skip_low"]
dca0 = lambda ax, s: E[ax]["decision_curve"][s][0]
_dl, _dh = E["糖尿病"]["decision_curve"][LR], E["糖尿病"]["decision_curve"][HG]
assert all(a["pt"] == b["pt"] and min(a["nb_model"], b["nb_model"]) > max(a["nb_test_all"], 0) and b["nb_model"] > a["nb_model"]
           for a, b in zip(_dl, _dh)), "糖尿病決策曲線之文字敘述不成立"
DM_DCA = (_dl[0]["pt"], _dl[-1]["pt"])
x3h, x3d = X3["肝炎"], X3["糖尿病"]
rc = lambda ax: R[ax]["recalibration"]
thr = lambda ax: R[ax]["after_apparent"]["thresholds"]

# ── APA 參考文獻（期刊文章之作者、卷期、頁碼已以 PubMed 與 Crossref 核對，2026-09-27）
RET = "Retrieved September 27, 2026, from"
REF = {
    "benjamini": dict(au="Benjamini & Hochberg", date="1995", sort="Benjamini", apa="Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society: Series B (Methodological), 57*(1), 289–300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x"),
    "bashir": dict(au="Bashir et al.", date="2026", sort="Bashir", apa="Bashir, A., Arora, R., Mehrotra, D., Bala, M., Parry, A. H., & Iqball, A. (2026). Lipid abnormalities in chronic viral hepatitis: Associations and machine learning-enhanced prediction. *BMC Gastroenterology, 26*, 365. https://doi.org/10.1186/s12876-026-04861-y"),
    "christodoulou": dict(au="Christodoulou et al.", date="2019", sort="Christodoulou", apa="Christodoulou, E., Ma, J., Collins, G. S., Steyerberg, E. W., Verbakel, J. Y., & Van Calster, B. (2019). A systematic review shows no performance benefit of machine learning over logistic regression for clinical prediction models. *Journal of Clinical Epidemiology, 110*, 12–22. https://doi.org/10.1016/j.jclinepi.2019.02.004"),
    "tripod": dict(au="Collins et al.", date="2024", sort="Collins Moons", apa="Collins, G. S., Moons, K. G. M., Dhiman, P., Riley, R. D., Beam, A. L., Van Calster, B., Ghassemi, M., Liu, X., Reitsma, J. B., van Smeden, M., Boulesteix, A.-L., Camaradou, J. C., Celi, L. A., Denaxas, S., Denniston, A. K., Glocker, B., Golub, R. M., Harvey, H., Heinze, G., … Logullo, P. (2024). TRIPOD+AI statement: Updated guidance for reporting clinical prediction models that use regression or machine learning methods. *BMJ, 385*, e078378. https://doi.org/10.1136/bmj-2023-078378"),
    "collins_ev": dict(au="Collins et al.", date="2016", sort="Collins Ogundimu", apa="Collins, G. S., Ogundimu, E. O., & Altman, D. G. (2016). Sample size considerations for the external validation of a multivariable prognostic model: A resampling study. *Statistics in Medicine, 35*(2), 214–226. https://doi.org/10.1002/sim.6787"),
    "conners": dict(au="Conners et al.", date="2023", sort="Conners", apa="Conners, E. E., Panagiotakopoulos, L., Hofmeister, M. G., Spradling, P. R., Hagan, L. M., Harris, A. M., Rogers-Brown, J. S., Wester, C., & Nelson, N. P. (2023). Screening and testing for hepatitis B virus infection: CDC recommendations—United States, 2023. *MMWR Recommendations and Reports, 72*(1), 1–25. https://doi.org/10.15585/mmwr.rr7201a1"),
    "kdigo": dict(au="KDIGO CKD Work Group", long="Kidney Disease: Improving Global Outcomes [KDIGO] CKD Work Group", date="2024", sort="Kidney Disease", apa="Kidney Disease: Improving Global Outcomes (KDIGO) CKD Work Group. (2024). KDIGO 2024 clinical practice guideline for the evaluation and management of chronic kidney disease. *Kidney International, 105*(4S), S117–S314. https://doi.org/10.1016/j.kint.2023.10.018"),
    "probast": dict(au="Moons et al.", date="2025", sort="Moons", apa="Moons, K. G. M., Damen, J. A. A., Kaul, T., Hooft, L., Andaur Navarro, C., Dhiman, P., Beam, A. L., Van Calster, B., Celi, L. A., Denaxas, S., Denniston, A. K., Ghassemi, M., Heinze, G., Kengne, A. P., Maier-Hein, L., Liu, X., Logullo, P., McCradden, M. D., Liu, N., … van Smeden, M. (2025). PROBAST+AI: An updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. *BMJ, 388*, e082505. https://doi.org/10.1136/bmj-2024-082505"),
    "erb": dict(au="NCHS", long="National Center for Health Statistics [NCHS]", date="2026", sort="National Center for Health Statistics", apa="National Center for Health Statistics. (2026, March 24). *Ethics review board approval*. https://www.cdc.gov/nchs/nhanes/about/erb.html"),
    "nidd": dict(au="NIDDK", long="National Institute of Diabetes and Digestive and Kidney Diseases [NIDDK]", date="2018", sort="National Institute of Diabetes", apa="National Institute of Diabetes and Digestive and Kidney Diseases. (2018, April). *The A1C test & diabetes*. https://www.niddk.nih.gov/health-information/diagnostic-tests/a1c-test"),
    "nkf": dict(au="National Kidney Foundation", date="n.d.", sort="National Kidney Foundation", apa=f"National Kidney Foundation. (n.d.). *CKD-EPI creatinine equation (2021)*. {RET} https://www.kidney.org/ckd-epi-creatinine-equation-2021"),
    "parker": dict(au="Parker et al.", date="2017", sort="Parker", apa="Parker, J. D., Talih, M., Malec, D. J., Beresovsky, V., Carroll, M., Gonzalez, J. F., Hamilton, B. E., Ingram, D. D., Kochanek, K., McCarty, F., Moriarity, C., Shimizu, I., Strashny, A., & Ward, B. W. (2017). *National Center for Health Statistics data presentation standards for proportions* (Vital and Health Statistics, Series 2, No. 175). National Center for Health Statistics."),
    "rustrao": dict(au="Rust & Rao", date="1996", sort="Rust", apa="Rust, K. F., & Rao, J. N. K. (1996). Variance estimation for complex surveys using replication techniques. *Statistical Methods in Medical Research, 5*(3), 283–310. https://doi.org/10.1177/096228029600500305"),
    "schillie": dict(au="Schillie et al.", date="2020", sort="Schillie", apa="Schillie, S., Wester, C., Osborne, M., Wesolowski, L., & Ryerson, A. B. (2020). CDC recommendations for hepatitis C screening among adults—United States, 2020. *MMWR Recommendations and Reports, 69*(2), 1–17. https://doi.org/10.15585/mmwr.rr6902a1"),
    "selvin": dict(au="Selvin et al.", date="2007", sort="Selvin", apa="Selvin, E., Manzi, J., Stevens, L. A., Van Lente, F., Lacher, D. A., Levey, A. S., & Coresh, J. (2007). Calibration of serum creatinine in the National Health and Nutrition Examination Surveys (NHANES) 1988–1994, 1999–2004. *American Journal of Kidney Diseases, 50*(6), 918–926. https://doi.org/10.1053/j.ajkd.2007.08.020"),
    "vancalster": dict(au="Van Calster et al.", date="2019", sort="Van Calster", apa="Van Calster, B., McLernon, D. J., van Smeden, M., Wynants, L., & Steyerberg, E. W. (2019). Calibration: The Achilles heel of predictive analytics. *BMC Medicine, 17*(1), 230. https://doi.org/10.1186/s12916-019-1466-7"),
    "vergouwe": dict(au="Vergouwe et al.", date="2017", sort="Vergouwe", apa="Vergouwe, Y., Nieboer, D., Oostenbrink, R., Debray, T. P. A., Murray, G. D., Kattan, M. W., Koffijberg, H., Moons, K. G. M., & Steyerberg, E. W. (2017). A closed testing procedure to select an appropriate method for updating prediction models. *Statistics in Medicine, 36*(28), 4529–4539. https://doi.org/10.1002/sim.7179"),
    "vickers": dict(au="Vickers & Elkin", date="2006", sort="Vickers", apa="Vickers, A. J., & Elkin, E. B. (2006). Decision curve analysis: A novel method for evaluating prediction models. *Medical Decision Making, 26*(6), 565–574. https://doi.org/10.1177/0272989X06295361"),
    "yang": dict(au="Yang et al.", date="2024", sort="Yang", apa="Yang, P., Liu, Z., Lu, F., Sha, Y., Li, P., Zheng, Q., Wang, K., Zhou, X., Zeng, X., & Wu, Y. (2024). Machine learning models predicts risk of proliferative lupus nephritis. *Frontiers in Immunology, 15*, 1413569. https://doi.org/10.3389/fimmu.2024.1413569"),
}
NCHS_DOCS = {   # key: (標題, 說明, 網址, 年, 月)——頁面所示之最後修訂日，未修訂則用首次發布日（2026-09-27 逐頁核對）
    "lab18": ("Standard biochemistry profile & hormones (LAB18)", "NHANES 1999–2000 data documentation", "1999/DataFiles/LAB18.htm", 2006, "August"),
    "lab13": ("Cholesterol – total & HDL (Lab13)", "NHANES 1999–2000 data documentation", "1999/DataFiles/LAB13.htm", 2010, "April"),
    "l40b": ("Standard biochemistry profile (L40_B)", "NHANES 2001–2002 data documentation", "2001/DataFiles/L40_B.htm", 2006, "September"),
    "biopro_d": ("Standard biochemistry profile (BIOPRO_D)", "NHANES 2005–2006 data documentation", "2005/DataFiles/BIOPRO_D.htm", 2008, "March"),
    "albcr_e": ("Albumin & creatinine – urine (ALB_CR_E)", "NHANES 2007–2008 data documentation", "2007/DataFiles/ALB_CR_E.htm", 2009, "September"),
    "ghb_f": ("Glycohemoglobin (GHB_F)", "NHANES 2009–2010 data documentation", "2009/DataFiles/GHB_F.htm", 2012, "March"),
    "cbc_h": ("Complete blood count with 5-part differential – whole blood (CBC_H)", "NHANES 2013–2014 data documentation", "2013/DataFiles/CBC_H.htm", 2016, "July"),
    "hepc_h": ("Hepatitis C: RNA (HCV-RNA) and hepatitis C genotype (HEPC_H)", "NHANES 2013–2014 data documentation", "2013/DataFiles/HEPC_H.htm", 2017, "September"),
    "biopro_j": ("Standard biochemistry profile (BIOPRO_J)", "NHANES 2017–2018 data documentation", "2017/DataFiles/BIOPRO_J.htm", 2020, "February"),
    "biopro_l": ("Standard biochemistry profile (BIOPRO_L)", "NHANES August 2021–August 2023 data documentation", "2021/DataFiles/BIOPRO_L.htm", 2025, "September"),
    "albcr_l": ("Albumin & creatinine – urine (ALB_CR_L)", "NHANES August 2021–August 2023 data documentation", "2021/DataFiles/ALB_CR_L.htm", 2025, "September"),
    "trigly_l": ("Cholesterol – low-density lipoproteins (LDL) & triglycerides (TRIGLY_L)", "NHANES August 2021–August 2023 data documentation", "2021/DataFiles/TRIGLY_L.htm", 2025, "September"),
}
for k, (t, dsc, path, yr, mo) in NCHS_DOCS.items():
    REF[k] = dict(au="NCHS", long="National Center for Health Statistics [NCHS]", date=str(yr), month=mo, sort="National Center for Health Statistics",
                  title=t, desc=dsc, url=f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{path}")
REF["weighting"] = dict(au="NCHS", long="National Center for Health Statistics [NCHS]", date="n.d.", sort="National Center for Health Statistics",
                        title="Weighting", desc="NHANES tutorials", url="https://wwwn.cdc.gov/nchs/nhanes/tutorials/weighting.aspx")   # 頁面無日期
CITE = re.compile(r"\[@([a-z0-9_,]+)\]")


def render_citations(text):
    """[@a,b] → （作者, 年; 作者, 年）。同作者同年依標題排序加 a、b…（n.d. 為 n.d.-a）；同一括號內依作者字母、年份排序；
    團體作者引用兩次以上時首次用「全名 [縮寫]」，只引用一次則用全名。回傳 (文字, 參考文獻清單)。"""
    used, n_cite = [], {}
    for mt in CITE.finditer(text):
        for k in mt.group(1).split(","):
            assert k in REF, f"未定義之文獻鍵 {k}"
            if k not in used:
                used.append(k)
            n_cite[REF[k]["au"]] = n_cite.get(REF[k]["au"], 0) + 1
    same = {}
    for k in used:
        same.setdefault((REF[k]["au"], REF[k]["date"]), []).append(k)
    for (_, d), ks in same.items():
        ks.sort(key=lambda k: (REF[k].get("title") or REF[k]["apa"]).casefold())
        for i, k in enumerate(ks):
            REF[k]["date_full"] = d + (("-" if d == "n.d." else "") + chr(97 + i) if len(ks) > 1 else "")
    seen = set()
    dkey = lambda x: (not x.startswith("n.d."), x)

    def rep(mt):
        groups = {}
        for k in sorted(mt.group(1).split(","), key=lambda k: REF[k]["sort"].casefold()):
            r = REF[k]
            au = r["au"]
            disp = au
            if r.get("long") and au not in seen:
                disp = r["long"] if n_cite[au] > 1 else r["long"].split(" [")[0]
            seen.add(au)
            groups.setdefault(au, [disp, []])[1].append(r["date_full"])
        return "（" + "; ".join(f"{d}, {', '.join(sorted(ds, key=dkey))}" for d, ds in groups.values()) + "）"
    out = CITE.sub(rep, text)

    def entry(k):
        r = REF[k]
        if r.get("apa"):
            assert r["date_full"] == r["date"], f"{k}：自帶 APA 字串之文獻不可同作者同年"
            return r["apa"]
        when = r["date_full"] + (f", {r['month']}" if r.get("month") else "")
        return (f"National Center for Health Statistics. ({when}). *{r['title']}* [{r['desc']}]. "
                f"{RET + ' ' if r['date'] == 'n.d.' else ''}{r['url']}")
    order = sorted(used, key=lambda k: (REF[k]["sort"].casefold(), 0 if REF[k]["date"] == "n.d." else 1, REF[k]["date_full"]))
    return out, [entry(k) for k in order]


def routine_dictionary():
    """附錄一：常規套組變數字典（代號、中文名、單位、各軸是否納入）。"""
    sys.path.insert(0, ROOT)
    from make_direction_html import LABEL, UNIT
    hep, dm = set(E["肝炎"]["routine_panel"]), set(E["糖尿病"]["routine_panel"])
    allf = [f for f in E["糖尿病"]["routine_panel"]] + [f for f in E["肝炎"]["routine_panel"] if f not in dm]
    rows = []
    for f in allf:
        mark = lambda s, ax: "✓" if f in s else "近端排除"
        rows.append(f"| {f} | {LABEL.get(f, f)} | {UNIT.get(f, '')} | {mark(hep, '肝炎')} | {mark(dm, '糖尿病')} |")
    return "\n".join(rows), len(allf)


def conversion_table():
    """附錄二：官方回推式（2017–2018：BIOPRO_J；2021–2023：修正一）。"""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    sys.path.insert(0, ROOT)
    from external_validation_2021 import BACKWARD
    from make_direction_html import LABEL
    from nhanes_cohort import BRIDGE_J, BRIDGE_J_LOG10
    keys = list(dict.fromkeys(list(BRIDGE_J) + list(BRIDGE_J_LOG10) + list(BACKWARD)))
    eq = lambda a, b: f"{num(a, 5).rstrip('0').rstrip('.')} ＋ {b:g} × Y" if a >= 0 else f"{b:g} × Y − {num(-a, 5).rstrip('0').rstrip('.')}"
    rows = []
    for k in keys:
        j = f"X ＝ {eq(*BRIDGE_J[k])}" if k in BRIDGE_J else (
            f"log₁₀X ＝ {BRIDGE_J_LOG10[k][1]:g} × log₁₀Y − {num(-BRIDGE_J_LOG10[k][0], 5)}" if k in BRIDGE_J_LOG10 else "不需調整")
        l_ = f"X ＝ {eq(BACKWARD[k][0], BACKWARD[k][1])}（{BACKWARD[k][2]}）" if k in BACKWARD else "不需調整"
        rows.append(f"| {k} | {LABEL.get(k, k)} | {j} | {l_} |")
    return "\n".join(rows)


DICT_ROWS, N_ROUTINE_ALL = routine_dictionary()
CONV_ROWS = conversion_table()
ABSTRACT = (f"腎臟指標異常時需要找出病因。本研究檢驗一般健檢已有的常規血液與尿液數值能否提供病因線索。使用美國 NHANES 1999–2018 年 "
            f"{n(AU['n_adults'])} 名成人，依官方文件修正跨週期檢驗量尺與多項資料錯誤，在腎臟指標異常者中以巢狀交叉驗證建立模型。"
            f"糖尿病標籤之邏輯迴歸 AUROC {auc('糖尿病', LR):.3f}，梯度提升 {auc('糖尿病', HG):.3f} 且校準良好；肝炎標籤 {auc('肝炎', LR):.3f}，"
            f"訊號主要來自 C 型肝炎。在 2021–2023 年資料上，糖尿病標籤維持 {xm('糖尿病', LR)['auroc']:.3f} 與 {xm('糖尿病', HG)['auroc']:.3f}；"
            f"肝炎標籤只有 {X['肝炎']['n_pos']} 名陽性，無法確認。常規檢驗能提供病因線索，但不能取代診斷，也不能用來省略肝炎篩檢。")
assert len(ABSTRACT) <= 300, f"摘要 {len(ABSTRACT)} 字，超過 300 字"

BODY = f"""**科　　別**：動物與醫學學科

**組　　別**：高級中等學校組

**作品名稱**：{TITLE}

**關 鍵 詞**：{KEYWORDS}

**編　　號**：

<!-- 分頁 -->

# {TITLE}

## 摘要

{ABSTRACT}

## 壹、前言

### 一、研究動機

腎臟病的病因評估需要整合病史、共存疾病、用藥、身體檢查、實驗室數據與影像，必要時還需要病理或基因檢查；單次 eGFR 下降或白蛋白尿升高，也不足以確認異常已持續三個月以上[@kdigo]。另一方面，多數人每年健康檢查都會抽血、驗尿，這些數值早已存在，卻很少被拿來回答「腎臟為什麼出問題」。本研究的核心問題是：常規數值能不能在其他檢查之前，指出值得優先查證的病因方向？

> ⚠️ **待填寫**：研究者本人的真實動機（接觸的個案、課堂、新聞或閱讀所見）。本說明書不代寫這一段。

### 二、研究目的

**H₁**：在腎臟指標異常的成人中，常規血液與尿液檢驗辨識肝炎病毒感染與糖尿病兩個共存標籤的能力，明顯優於只用年齡與性別，且在未參與開發的新資料上仍然成立。判定方式事先寫定，不以任何固定分數作為通過門檻。

1. 依 NHANES 官方文件建立跨週期一致的檢驗量尺與三值標籤。
2. 以巢狀交叉驗證評估常規檢驗的判別與校準，並與只用年齡、性別的基準比較。
3. 比較線性模型（邏輯迴歸）與非線性模型（梯度提升）的判別與校準，特別是糖尿病標籤。
4. 檢驗時間外推、人口加權與抽樣設計下的穩健性，並分開呈現 B 型與 C 型肝炎。
5. 以未參與開發的 NHANES 2021–2023 評估外部表現。
6. 建立離線網頁工具，並估計「以新資料重新校準」這一步的可靠程度。

### 三、文獻回顧

#### （一）病因評估與病因線索

KDIGO 2024 指引把腎臟病的病因評估視為需要整合多種資訊的工作[@kdigo]。慢性病毒性肝炎會改變血脂與肝臟的合成功能，已有研究以常規肝功能與血脂檢驗建立預測模型[@bashir]；狼瘡腎炎的研究則以腎臟切片為參考標準，說明免疫性病因需要病理與免疫檢驗[@yang]。本研究的標籤是共存疾病，共存不等於腎損傷的原因，因此只宣稱「病因線索」。

#### （二）預測模型的報告與評估

TRIPOD+AI 與 PROBAST+AI 要求完整報告資料來源、標籤、缺值處理、校準與外部驗證[@tripod,probast]。校準常被忽略，但錯誤的機率會誤導決策[@vancalster]；外部驗證一般建議至少約 100 個事件[@collins_ev]；模型移到新族群時，可依由簡到繁的原則只更新截距或同時更新斜率[@vergouwe]。系統性回顧發現機器學習在臨床預測上常不優於邏輯迴歸[@christodoulou]，因此非線性模型的增益必須在同一批切分上直接比較，並同時檢查校準。

#### （三）調查資料與跨週期檢驗

NHANES 採複雜抽樣[@weighting]，加權估計與變異估計都必須考慮分層與地區單位（PSU），變異可用複製法估計[@rustrao]；比例的信賴區間採 NCHS 的呈現標準[@parker]。NHANES 各週期的檢驗儀器與方法不同，CDC 在資料文件中提供校正式與回推式，例如 1999–2004 年血清肌酸酐的校正[@selvin]與 2017–2018 年生化儀器更換的回推式[@biopro_j]。

#### （四）本作品的延續與新增

本作品延續研究者先前的版本：v1、v2 以同一資料建立三類與兩類病因模型；v3 依外部方法學審查重建三值標籤、校準流程，並完成一次事前凍結的外部確認。本版（v3.2）新增：(1) 逐週期核對 CDC 文件，找出並修正三類新的資料錯誤；(2) 評估非線性模型的校準；(3) 補回 HDL 並以修正後資料重建網頁工具；(4) 分開呈現 B 型與 C 型肝炎；(5) 以抽樣設計切半的交叉驗證估計重新校準的可靠度。

> ⚠️ **待確認**：若本主題曾參加其他競賽或前一屆科展，依實施要點須填寫延續性研究作品說明表並附前次資料；研究者本人之參與比重請依實際情形填寫。

## 貳、研究設備與器材

### 一、資料來源

美國國家健康與營養調查（NHANES）由美國疾病管制與預防中心（CDC）轄下的國家衛生統計中心（NCHS）執行，是具全國代表性的調查，公開檔案可自由下載。

| 資料 | 週期 | 檔案數 | 用途 |
|---|---|---|---|
| 開發資料 | 1999–2018 年十個週期 | {N_DEV} | 建立與評估模型 |
| 外部資料 | 2021–2023 年 | {N_EXT} | 外部評估 |

合計 {N_ALL} 個檔案、約 {MB:.0f} MB，每個檔案的來源網址、SHA256 雜湊與位元組數都記錄在出處帳本。NHANES 的調查協定由 NCHS 倫理審查委員會核准；本研究使用的週期分屬協定 #98-12（1999–2004）、#2005-06（2005–2010）、#2011-17 與 #2018-01（2011–2018），2021–2023 年一期在該頁列為「NHANES 2021-2022」、協定 #2021-05[@erb]；本研究只使用公開、已去識別的檔案，不接觸任何受試者。

> ⚠️ **待確認**：是否需要校內或主辦單位的倫理審查，請依比賽規定與指導老師確認。

### 二、軟硬體

| 項目 | 規格 |
|---|---|
| 電腦 | 一般個人電腦（Windows 11） |
| 分析語言 | Python {PY} |
| 主要套件 | {PKGS} |
| 網頁計算核對 | Node.js {NODE} |
| 撰寫與版本控制 | Obsidian、Git（GitHub） |
| AI 輔助工具 | Claude（Anthropic）：程式撰寫、資料核對與文件草擬之輔助；Codex（OpenAI）：唯讀之獨立稽核 ⚠️ 請依實際使用情形與比賽規定確認 |

### 三、防自欺機制（本研究自行設計）

| 機制 | 做法 | 防止什麼 |
|---|---|---|
| 出處帳本 | 每個檔案記錄網址與 SHA256，未登錄的檔案程式拒絕讀取 | 使用來路不明或被改動的資料 |
| 先提交、後執行 | 分析計畫在看到結果前提交版本控制（v3 {COMMITS['plan_v3']}、外部協定 {COMMITS['proto']}、設計變異 {COMMITS['dv']}、v3.2 {COMMITS['plan_v32']}） | 看到結果後才改方法 |
| 外部資料只評一次 | 事前指定的外部評估程式在結果檔存在時拒絕再跑 | 反覆嘗試到結果好看為止 |
| 逐週期核對官方文件 | 每個特徵逐週期檢查有值比例，並逐一閱讀 CDC 文件的換算說明 | 雜湊檢查抓不到的變數改名與量尺差異 |
| 網頁與 Python 核對 | 以 Node.js 執行網頁中的計算，與 Python 逐軸比對 | 網頁工具算錯 |
| 獨立稽核 | 另以不同的 AI 工具唯讀檢查程式與文件數字的對應，發現的問題逐項查證後才修改 | 同一個作者（或工具）重複同樣的盲點 |

## 參、研究過程與方法

### 一、研究架構

1. 下載 NHANES 公開檔，登錄出處帳本。
2. 依官方文件換算檢驗量尺，建立腎臟指標與兩個共存標籤的三值判定。
3. 在腎臟指標異常者中，以常規檢驗建立線性與非線性模型。
4. 以巢狀交叉驗證評估判別、校準與三段分區，並與基準比較。
5. 檢驗時間外推、人口加權、抽樣設計與標籤定義的穩健性。
6. 掃描上游暴露關聯（探索性）。
7. 以 NHANES 2021–2023 評估外部表現。
8. 建立網頁工具，重新校準並以交叉驗證估計其可靠度。

### 二、分析樣本與三值標籤

納入年齡至少 20 歲者。腎臟指標異常定義為單次 eGFR < 60 mL/min/1.73 m² 或尿白蛋白／肌酸酐比（ACR）≧ 30 mg/g[@kdigo]；eGFR 以 CKD-EPI 2021 無種族係數公式計算[@nkf]。每一項判定都分成三種結果：

| 判定 | 陽性 | 陰性 | 未知 |
|---|---|---|---|
| 腎臟指標 | 任一已測指標達門檻 | 兩項皆測且正常 | 一項正常而另一項缺，或兩項皆缺 |
| 肝炎病毒感染 | HBsAg 陽性或 HCV RNA 陽性 | 兩者皆可排除 | 其餘，例如抗體陽性但沒有 RNA |
| 糖尿病 | 醫師診斷或 HbA1c ≧ 6.5% | 問卷與 HbA1c 皆為陰性 | 拒答、不知道或缺值 |

肝炎之判定依 CDC 篩檢建議與 NHANES 檢驗流程[@conners,hepc_h]，糖尿病依 HbA1c 診斷切點[@nidd]。各軸只排除該軸的未知者，兩個標籤可以同時成立。

### 三、檢驗量尺與資料修正

NHANES 各週期的檢驗儀器與方法不同。本研究逐週期檢查每個特徵的有值比例，並逐一閱讀 CDC 資料文件，依官方建議處理：

| 週期 | 項目 | 官方文件 | 本研究的處理 |
|---|---|---|---|
| 1999–2000 | 血清肌酸酐 | 建議校正至標準方法[@lab18,selvin] | 1.013 × 原值 ＋ 0.147 |
| 2001–2002 | 鹼性磷酸酶、LDH、磷、總膽紅素 | 兩家實驗室交叉比對後以另一變數名發布調和值[@l40b] | 改名對應（v3.2 新增） |
| 2005–2006 | 血清肌酸酐 | 建議校正[@biopro_d] | −0.016 ＋ 0.978 × 原值 |
| 1999–2006 | 尿肌酸酐 | 2007 年換方法，提供分段轉換[@albcr_e] | 依官方分段式轉換 |
| 1999–2018 | HDL 膽固醇 | 1999–2002、2005–2006 年之方法偏差已於發布資料中修正；2005 年起變數改名[@lab13] | 改名對應並解除誤封存（v3.2 新增） |
| 2017–2018 | 12 項生化（含肌酸酐） | 儀器改為 Cobas 6000，提供回推式[@biopro_j] | 換回 1999–2016 年之量尺（v3.2 新增，附錄二） |
| 2021–2023 | 13 項生化、尿白蛋白、空腹三酸甘油酯 | 儀器與方法更換，提供回推式[@biopro_l,albcr_l,trigly_l] | 先換回 2017–2020 年量尺，再依上一列換回（附錄二） |
| 1999–2010 | HbA1c | 分布右移原因不明，建議使用原始值[@ghb_f] | 使用原始值（列為限制） |

### 四、特徵

候選特徵共 {EV['n_features']} 項：常規血液與尿液檢驗 {N_ROUTINE_ALL} 項（含 ACR、eGFR、嗜中性球／淋巴球比、年齡與性別），每個週期都有測量；另 {EV['n_features'] - N_ROUTINE_ALL} 項非常規檢驗（如 C 反應蛋白、血鉛、鐵蛋白、副甲狀腺素）在本研究資料中只有部分週期有值，只用於「全特徵」模型。定義標籤的檢驗一律不作特徵。各軸再移除生理上緊鄰標籤的「近端特徵」：肝炎軸移除 ALT、AST、GGT、總膽紅素，糖尿病軸移除血糖與滲透壓。「常規套組」依是否為一般健檢項目事先定義，不看表現挑選（肝炎軸 {len(E['肝炎']['routine_panel'])} 項、糖尿病軸 {len(E['糖尿病']['routine_panel'])} 項；附錄一）。

### 五、模型與巢狀評估

比較兩種模型：邏輯迴歸（線性）與梯度提升樹（HistGradientBoosting，最大深度 3、學習率 0.08、300 次迭代，沿用 v3 設定、不調參；非線性）。兩者都採網頁工具的結構：先以五折交叉配適得到五個模型並取平均，再用內層折外分數做保序校準。評估採分層五折、重複五次的巢狀外層評估：補值、標準化、配適、校準與門檻都只用外層訓練資料，被評估的人從未參與任何一步[@tripod,probast]。

判別以 AUROC 與平均精確率（AP）報告，並列五次重複之平均；校準以校準截距、校準斜率與 Brier 分數報告[@vancalster]，校準曲線與三段分區取第一次重複。模型間差異以同一批受試者 bootstrap 1,000 次估計 95% 信賴區間。

### 六、三段分區

工具輸出「傾向」「不確定」「不傾向」三區，規則在看到結果前寫定：預測勝算達事前勝算 2 倍以上為傾向，0.5 倍以下為不傾向，相當於概似比 2 與 0.5。常規套組有值不足一半時標示「資料不足」、不給方向；報告「能給出方向的比例」時以全部受試者為分母。

### 七、穩健性與分型

1. 時間外推：以 1999–2008 年開發、2009–2018 年評估。
2. 人口加權與抽樣設計：以合併 20 年的 MEC 權重計算加權指標[@weighting]，變異以刪一 PSU 摺刀法估計[@rustrao]，比例採 Korn–Graubard 區間[@parker]。
3. 腎臟標籤定義：2017–2018 年改用原發布的肌酸酐判定腎臟指標，重做主要分析。
4. 肝炎分型：以常規套組邏輯迴歸的外層預測，分別計算 C 型與 B 型陽性者對陰性者的 AUROC。

### 八、決策曲線與暴露探索

決策曲線比較「依模型送驗」「全數送驗」「全不送驗」三種做法的淨效益[@vickers]；肝炎檢驗便宜、無創，且指引建議成人普遍篩檢[@conners,schillie]，合理的閾值機率很低。暴露探索沿用 v3：以全體成人掃描 {EXW['n_scanned']} 個暴露，以 Benjamini–Hochberg 法控制偽發現率[@benjamini]，並在同時有血、尿值的同一批受試者中比較血中與尿中金屬。

### 九、外部資料：NHANES 2021–2023

2021–2023 年資料自 2024 年 9 月起分批釋出，本研究使用的生化檔於 2025 年 9 月釋出[@biopro_l]，未參與任何開發決策。v3 在取用前凍結模型與評估規則（{COMMITS['proto']}），取用後、評估前發現儀器與方法更換，先提交量尺調和的修正（{COMMITS['amend']}），再依協定只評一次（{COMMITS['ext']}），此為事前指定的確認結果。本版模型在修正後資料上重新訓練，並把 2021–2023 年數值兩段換算到開發資料的量尺後評估；這批資料已用過，所以列為事後分析。另以抽血權重（WTPH2YR）與 MEC 權重分別加權。

### 十、網頁工具 v3.2 與重新校準的交叉驗證

網頁工具採常規套組邏輯迴歸。模型種類在看到結果前決定：工具必須逐項顯示推動因子，邏輯迴歸可由係數直接說明，梯度提升只作為比較基準。以 2021–2023 年資料依由簡到繁的規則重新校準：陽性至少 100 個且斜率檢定 p < 0.05 才更新斜率，否則只更新截距[@vergouwe]；事前機率改為 2021–2023 年的比例。為估計這一步的可靠度，依抽樣設計把 2021–2023 年資料切半 200 次（每層兩個 PSU 各分一半），在一半重新校準、在另一半評估。網頁為單一離線檔案，計算以 Node.js 與 Python 逐軸核對。

## 肆、研究結果

### 一、資料修正與分析樣本

{{FIG1}}

**圖1　分析樣本、三值標籤與 v3.2 資料修正**

逐週期核對後，v3 另有三類資料錯誤：2001–2002 年四項常規生化整週期缺值（對應後有值 {pct(AV['LBXSAPSI']['2001-2002'], 0)}），2017–2018 年 12 項生化不在共同量尺上，HDL 未讀入。修正後腎臟指標異常 {n(KID['pos'])} 人（2017–2018 年 {CH.get('1→0', 0)} 人改為兩項皆正常、{CH.get('1→-1', 0)} 人改為未知），肝炎軸 {n(E['肝炎']['n'])} 人（陽性 {E['肝炎']['n_pos']}）、糖尿病軸 {n(E['糖尿病']['n'])} 人（陽性 {n(E['糖尿病']['n_pos'])}）。

### 二、判別力

{{FIG2}}

**圖2　判別力（點＝五次重複平均，線＝最小至最大）**

**表1　各模型之判別力（巢狀外層，五次重複平均）**

| 模型 | 肝炎 AUROC | 肝炎 AP | 糖尿病 AUROC | 糖尿病 AP |
|---|---|---|---|---|
| 只用年齡、性別 | {E['肝炎']['M1_demographics']['auroc_mean']:.3f} | {E['肝炎']['M1_demographics']['ap_mean']:.3f} | {E['糖尿病']['M1_demographics']['auroc_mean']:.3f} | {E['糖尿病']['M1_demographics']['ap_mean']:.3f} |
| 常規套組・邏輯迴歸 | **{auc('肝炎', LR):.3f}** | {ap('肝炎', LR):.3f} | **{auc('糖尿病', LR):.3f}** | {ap('糖尿病', LR):.3f} |
| 常規套組・邏輯迴歸（不含 HDL） | {auc('肝炎', 'LR_routine_noHDL'):.3f} | {ap('肝炎', 'LR_routine_noHDL'):.3f} | {auc('糖尿病', 'LR_routine_noHDL'):.3f} | {ap('糖尿病', 'LR_routine_noHDL'):.3f} |
| 常規套組・梯度提升 | {auc('肝炎', HG):.3f} | {ap('肝炎', HG):.3f} | **{auc('糖尿病', HG):.3f}** | {ap('糖尿病', HG):.3f} |
| 全特徵・邏輯迴歸 | {auc('肝炎', 'LR_full'):.3f} | {ap('肝炎', 'LR_full'):.3f} | {auc('糖尿病', 'LR_full'):.3f} | {ap('糖尿病', 'LR_full'):.3f} |
| 全特徵・梯度提升 | {auc('肝炎', 'HGB_full'):.3f} | {ap('肝炎', 'HGB_full'):.3f} | {auc('糖尿病', 'HGB_full'):.3f} | {ap('糖尿病', 'HGB_full'):.3f} |

1. 常規檢驗的判別明顯優於年齡、性別；肝炎軸 AP {ap('肝炎', LR):.3f} 是盛行率 {pct(E['肝炎']['prevalence'])} 的 {ap('肝炎', LR) / E['肝炎']['prevalence']:.1f} 倍。
2. 糖尿病軸的梯度提升明顯較高：ΔAUROC {dauc('糖尿病', 'HGB_routine−LR_routine')}；肝炎軸則沒有差異：{dauc('肝炎', 'HGB_routine−LR_routine')}。
3. 補回 HDL 的影響很小：糖尿病 {dauc('糖尿病', 'LR_routine−LR_routine_noHDL')}，肝炎 {dauc('肝炎', 'LR_routine−LR_routine_noHDL')}。

### 三、校準：線性與非線性模型

{{FIG3}}

**圖3　校準曲線與三段分區之實際陽性比例**

**表2　校準與分區（第一次重複之外層預測）**

| 指標 | 肝炎・邏輯迴歸 | 肝炎・梯度提升 | 糖尿病・邏輯迴歸 | 糖尿病・梯度提升 |
|---|---|---|---|---|
| 校準截距 | {sgn(cal('肝炎', LR)['intercept'], 2)} | {sgn(cal('肝炎', HG)['intercept'], 2)} | {sgn(cal('糖尿病', LR)['intercept'], 2)} | {sgn(cal('糖尿病', HG)['intercept'], 2)} |
| 校準斜率 | {cal('肝炎', LR)['slope']:.2f} | {cal('肝炎', HG)['slope']:.2f} | {cal('糖尿病', LR)['slope']:.2f} | {cal('糖尿病', HG)['slope']:.2f} |
| Brier 分數 | {cal('肝炎', LR)['brier']:.4f} | {cal('肝炎', HG)['brier']:.4f} | {cal('糖尿病', LR)['brier']:.4f} | {cal('糖尿病', HG)['brier']:.4f} |
| 傾向區實際陽性率 | {pct(band('肝炎', LR)['band']['傾向']['observed_rate'])} | {pct(band('肝炎', HG)['band']['傾向']['observed_rate'])} | {pct(band('糖尿病', LR)['band']['傾向']['observed_rate'])} | {pct(band('糖尿病', HG)['band']['傾向']['observed_rate'])} |
| 不傾向區實際陽性率 | {pct(band('肝炎', LR)['band']['不傾向']['observed_rate'])} | {pct(band('肝炎', HG)['band']['不傾向']['observed_rate'])} | {pct(band('糖尿病', LR)['band']['不傾向']['observed_rate'])} | {pct(band('糖尿病', HG)['band']['不傾向']['observed_rate'])} |
| 資料不足（不給方向）人數 | {band('肝炎', LR)['band']['資料不足']['n']} | {band('肝炎', HG)['band']['資料不足']['n']} | {band('糖尿病', LR)['band']['資料不足']['n']} | {band('糖尿病', HG)['band']['資料不足']['n']} |
| 能給出方向的比例 | {pct(band('肝炎', LR)['coverage'])} | {pct(band('肝炎', HG)['coverage'])} | {pct(band('糖尿病', LR)['coverage'])} | {pct(band('糖尿病', HG)['coverage'])} |

註：能給出方向的比例＝（傾向＋不傾向）人數／全部人數；各區實際陽性率只計入資料足夠者。

兩種模型經同樣的保序校準後都接近理想（截距接近 0、斜率接近 1）。糖尿病軸的梯度提升 Brier 分數較低，能給出方向的比例由 {pct(band('糖尿病', LR)['coverage'])} 升至 {pct(band('糖尿病', HG)['coverage'])}，且傾向區與不傾向區分得更開。肝炎軸的梯度提升斜率 {cal('肝炎', HG)['slope']:.2f}、能給出方向的比例降為 {pct(band('肝炎', HG)['coverage'])}，沒有優於邏輯迴歸。

### 四、穩健性

{{FIG4}}

**圖4　穩健性：時間外推、人口加權與腎臟標籤定義**

**表3　穩健性分析**

| 分析 | 肝炎・邏輯迴歸 | 肝炎・梯度提升 | 糖尿病・邏輯迴歸 | 糖尿病・梯度提升 |
|---|---|---|---|---|
| 時間外推 AUROC | {tmp('肝炎', LR)['auroc']:.3f} | {tmp('肝炎', HG)['auroc']:.3f} | {tmp('糖尿病', LR)['auroc']:.3f} | {tmp('糖尿病', HG)['auroc']:.3f} |
| 時間外推校準截距 | {sgn(tmp('肝炎', LR)['calibration']['intercept'], 2)} | {sgn(tmp('肝炎', HG)['calibration']['intercept'], 2)} | {sgn(tmp('糖尿病', LR)['calibration']['intercept'], 2)} | {sgn(tmp('糖尿病', HG)['calibration']['intercept'], 2)} |
| 人口加權 AUROC | {wt('肝炎', LR)['auroc']['est']:.3f} | {wt('肝炎', HG)['auroc']['est']:.3f} | {wt('糖尿病', LR)['auroc']['est']:.3f} | {wt('糖尿病', HG)['auroc']['est']:.3f} |
| 加權平均預測減盛行率（百分點，設計 95% CI） | {sgn(100 * wt('肝炎', LR)['calib_diff']['est'], 2)}（{ci([100 * v for v in wt('肝炎', LR)['calib_diff']['ci95']], 2)}） | {sgn(100 * wt('肝炎', HG)['calib_diff']['est'], 2)}（{ci([100 * v for v in wt('肝炎', HG)['calib_diff']['ci95']], 2)}） | {sgn(100 * wt('糖尿病', LR)['calib_diff']['est'], 2)}（{ci([100 * v for v in wt('糖尿病', LR)['calib_diff']['ci95']], 2)}） | {sgn(100 * wt('糖尿病', HG)['calib_diff']['est'], 2)}（{ci([100 * v for v in wt('糖尿病', HG)['calib_diff']['ci95']], 2)}） |
| 腎臟標籤用原發布肌酸酐 AUROC | {E['肝炎']['kidney_label_as_reported'][LR]['auroc']:.3f} | {E['肝炎']['kidney_label_as_reported'][HG]['auroc']:.3f} | {E['糖尿病']['kidney_label_as_reported'][LR]['auroc']:.3f} | {E['糖尿病']['kidney_label_as_reported'][HG]['auroc']:.3f} |

時間外推時，評估週期的糖尿病比例（{pct(tmp('糖尿病', LR)['prevalence_test'])}）高於開發週期（{pct(tmp('糖尿病', LR)['prevalence_train'])}），兩種模型都低估（截距為正），梯度提升較輕。人口加權後，糖尿病軸平均預測比母體盛行率高約 2 至 3 個百分點（設計效應 {wt('糖尿病', LR)['prevalence']['deff']:.2f}）：機率不能直接移植到組成不同的人群。改用原發布肌酸酐判定腎臟標籤，結果幾乎不變。

### 五、肝炎軸：C 型與 B 型

**表4　肝炎軸分型（常規套組邏輯迴歸之外層預測）**

| 分型 | 陽性人數 | AUROC（95% CI） | 傾向 | 不確定 | 不傾向 | 資料不足 |
|---|---|---|---|---|---|---|
| C 型（HCV RNA 陽性） | {ST['C型_HCV_RNA']['n_pos']} | {ST['C型_HCV_RNA']['auroc']:.3f}（{ci(ST['C型_HCV_RNA']['ci95']['auroc'])}） | {ST['C型_HCV_RNA']['bands_tool']['傾向']} | {ST['C型_HCV_RNA']['bands_tool']['不確定']} | {ST['C型_HCV_RNA']['bands_tool']['不傾向']} | {ST['C型_HCV_RNA']['bands_tool']['資料不足']} |
| B 型（HBsAg 陽性） | {ST['B型_HBsAg']['n_pos']} | {ST['B型_HBsAg']['auroc']:.3f}（{ci(ST['B型_HBsAg']['ci95']['auroc'])}） | {ST['B型_HBsAg']['bands_tool']['傾向']} | {ST['B型_HBsAg']['bands_tool']['不確定']} | {ST['B型_HBsAg']['bands_tool']['不傾向']} | {ST['B型_HBsAg']['bands_tool']['資料不足']} |

以 C 型或 B 型單獨作標籤重新建模，AUROC 分別為 {SL['僅C型_HCV_RNA']['auroc']:.3f} 與 {SL['僅B型_HBsAg']['auroc']:.3f}（合併感染 {ST['coinfected']} 人）。肝炎軸實際上是 C 型肝炎軸。

### 六、決策曲線

{{FIG5}}

**圖5　決策曲線**

肝炎軸在閾值 0.5% 時，依模型送驗與全數送驗的淨效益幾乎相同（{dca0('肝炎', LR)['nb_model']:.4f} 對 {dca0('肝炎', LR)['nb_test_all']:.4f}）。若只略過「不傾向」區（資料不足者照常送驗），每千人送驗 {skip('肝炎', LR)['tested']:.0f} 人，但漏掉 {skip('肝炎', LR)['missed']:.1f} 名陽性，占陽性的 {pct(skip('肝炎', LR)['missed_share_of_pos'], 0)}。**因此本工具不能用來決定誰可以不驗肝炎。**糖尿病軸在閾值 {DM_DCA[0]:.0%}–{DM_DCA[1]:.0%} 的每個點，兩種模型的淨效益都高於全數送驗與全不送驗（{DM_DCA[0]:.0%} 時與全數送驗差距很小），且梯度提升都高於邏輯迴歸；以上為點估計。

### 七、暴露關聯（探索性，沿用 v3）

{{FIG6}}

**圖6　同一批受試者之血中與尿中鉛、鎘（勝算比為濃度加倍）**

{EXW['n_scanned']} 個暴露中 {EXW['n_significant_fdr05']} 個通過偽發現率 0.05。藥物關聯與處方常規一致，例如腎功能差時應停用的雙胍類呈負相關，可由適應症與反向因果解釋，不能當作致病證據。前一版「血中升、尿中降就是反向因果的直接證據」建立在沒有共同受試者的比較上，已撤回；在同一批 {n(Pb['n_both'])} 人中，尿中金屬的方向取決於結果定義與寫法。

### 八、2021–2023 年外部資料

{{FIG7}}

**圖7　NHANES 2021–2023：v3 事前指定之一次評估與 v3.2 事後評估**

**表5　2021–2023 年外部資料之判別與校準**

| 項目 | 肝炎軸 | 糖尿病軸 |
|---|---|---|
| **v3 事前指定一次評估**：陽性／人數 | {x3h['n_pos']}／{n(x3h['n'])} | {x3d['n_pos']}／{n(x3d['n'])} |
| 　全特徵邏輯迴歸（當時之部署模型） | {x3('肝炎', 'v3_full_LR（部署）')['auroc']:.3f}（{ci(x3('肝炎', 'v3_full_LR（部署）')['ci95']['auroc'])}） | {x3('糖尿病', 'v3_full_LR（部署）')['auroc']:.3f}（{ci(x3('糖尿病', 'v3_full_LR（部署）')['ci95']['auroc'])}） |
| 　常規套組邏輯迴歸 | {x3('肝炎', 'v3_basic_LR（常規套組候選）')['auroc']:.3f} | {x3('糖尿病', 'v3_basic_LR（常規套組候選）')['auroc']:.3f} |
| **v3.2 事後評估**：陽性／人數 | {X['肝炎']['n_pos']}／{n(X['肝炎']['n'])} | {X['糖尿病']['n_pos']}／{n(X['糖尿病']['n'])} |
| 　只用年齡、性別（稽核後補做） | {X['肝炎']['M1_demographics']['auroc']:.3f}（{ci(X['肝炎']['M1_demographics']['ci95']['auroc'])}） | {X['糖尿病']['M1_demographics']['auroc']:.3f}（{ci(X['糖尿病']['M1_demographics']['ci95']['auroc'])}） |
| 　常規套組邏輯迴歸 | {xm('肝炎', LR)['auroc']:.3f}（{ci(xm('肝炎', LR)['ci95']['auroc'])}） | {xm('糖尿病', LR)['auroc']:.3f}（{ci(xm('糖尿病', LR)['ci95']['auroc'])}） |
| 　常規套組梯度提升 | {xm('肝炎', HG)['auroc']:.3f}（{ci(xm('肝炎', HG)['ci95']['auroc'])}） | {xm('糖尿病', HG)['auroc']:.3f}（{ci(xm('糖尿病', HG)['ci95']['auroc'])}） |
| 　校準截距／斜率：邏輯迴歸（重新校準前） | {sgn(xm('肝炎', LR)['calibration']['intercept'], 2)}／{xm('肝炎', LR)['calibration']['slope']:.2f} | {sgn(xm('糖尿病', LR)['calibration']['intercept'], 2)}／{xm('糖尿病', LR)['calibration']['slope']:.2f} |
| 　校準截距／斜率：梯度提升 | {sgn(xm('肝炎', HG)['calibration']['intercept'], 2)}／{xm('肝炎', HG)['calibration']['slope']:.2f} | {sgn(xm('糖尿病', HG)['calibration']['intercept'], 2)}／{xm('糖尿病', HG)['calibration']['slope']:.2f} |

1. 糖尿病軸在新資料上大致維持，並明顯高於同一批人只用年齡、性別的 {X['糖尿病']['M1_demographics']['auroc']:.3f}：ΔAUROC 邏輯迴歸 {xd('糖尿病', 'LR_routine−M1_demographics')}、梯度提升 {xd('糖尿病', 'HGB_routine−M1_demographics')}。梯度提升比邏輯迴歸高 {xd('糖尿病', 'HGB_routine−LR_routine')}，校準也較接近理想。
2. 肝炎軸只有 {X['肝炎']['n_pos']} 名陽性，遠低於建議的約 100 個事件[@collins_ev]。只用年齡、性別的 AUROC 為 {X['肝炎']['M1_demographics']['auroc']:.3f}，常規套組邏輯迴歸並未高於它，ΔAUROC {xd('肝炎', 'LR_routine−M1_demographics')}，信賴區間極寬而無法判讀；陽性組成由開發時以 C 型為主，變為 B 型 {XS['B型_HBsAg']['n_pos']} 人、C 型 {XS['C型_HCV_RNA']['n_pos']} 人。
3. 與年齡、性別模型的外部比較，是獨立稽核發現原稿拿外部結果和內部基準比較之後才補做的，屬事後分析。
4. 以抽血權重加權，糖尿病軸邏輯迴歸 AUROC {X['糖尿病']['weighted'][LR]['WTPH2YR']['weighted']['auroc']['est']:.3f}，與 MEC 權重的 {X['糖尿病']['weighted'][LR]['WTMEC2YR']['weighted']['auroc']['est']:.3f} 相近。

### 九、網頁工具 v3.2 與重新校準的交叉驗證

{{FIG8}}

**圖8　重新校準之交叉驗證（依抽樣設計切半 200 次）**

**表6　網頁工具 v3.2**

| 項目 | 肝炎軸 | 糖尿病軸 |
|---|---|---|
| 重新校準 | 只更新截距（事件 {rc('肝炎')['n_pos']} 個，不足 100） | 截距與斜率（斜率檢定 p ＝ {R['糖尿病']['candidates']['slope_lr_test_p']:.4f}） |
| 事前機率（2021–2023） | {pct(TOOL['肝炎']['prevalence'], 2)} | {pct(TOOL['糖尿病']['prevalence'])} |
| 傾向／不傾向門檻 | ≧ {pct(thr('肝炎')['t_high'], 2)}／≦ {pct(thr('肝炎')['t_low'], 2)} | ≧ {pct(thr('糖尿病')['t_high'])}／≦ {pct(thr('糖尿病')['t_low'])} |
| 交叉驗證：測試半平均預測／實際 | {qf(cvq('肝炎', 'oe_recal'))} | {qf(cvq('糖尿病', 'oe_recal'))} |
| 　不重新校準 | {qf(cvq('肝炎', 'oe_none'))} | {qf(cvq('糖尿病', 'oe_none'))} |

糖尿病軸在另一半資料上，重新校準後平均預測仍對準實際（中位數 {cvq('糖尿病', 'oe_recal')['median']:.2f}），不重新校準則略為低估（{cvq('糖尿病', 'oe_none')['median']:.2f}）；肝炎軸每半只有約 {cvq('肝炎', 'n_pos_test')['median']:.0f} 個事件，範圍極寬而無法判斷。示範受試者為 NHANES {EX['cycle'].replace('-', '–')} 的一名真實成人（C 型肝炎 RNA 陽性、無糖尿病）：肝炎軸「{EX['axes']['肝炎']['band']}」（機率 {pct(EX['axes']['肝炎']['cal'], 2)}，相對事前勝算 ×{EX['axes']['肝炎']['odds_ratio']:.2f}），最大推動因子為 HDL {DEMO_HDL:.0f} mg/dL（開發資料中位數 {HDL_MED:.0f} mg/dL）；糖尿病軸「{EX['axes']['糖尿病']['band']}」（{pct(EX['axes']['糖尿病']['cal'], 2)}）。網頁與 Python 的輸出逐軸一致。單一示範只展示輸出形式，不代表準確率。

## 伍、討論

### 一、假設的成立範圍

H₁ 在糖尿病軸成立。內部 AUROC 邏輯迴歸 {auc('糖尿病', LR):.3f}、梯度提升 {auc('糖尿病', HG):.3f}，只用年齡、性別為 {E['糖尿病']['M1_demographics']['auroc_mean']:.3f}；同一批切分的配對差 ΔAUROC：邏輯迴歸 {dvd('糖尿病', LR)}、梯度提升 {dvd('糖尿病', HG)}。外部 AUROC 為 {xm('糖尿病', LR)['auroc']:.3f} 與 {xm('糖尿病', HG)['auroc']:.3f}，同一批人只用年齡、性別為 {X['糖尿病']['M1_demographics']['auroc']:.3f}；ΔAUROC：邏輯迴歸 {xd('糖尿病', 'LR_routine−M1_demographics')}、梯度提升 {xd('糖尿病', 'HGB_routine−M1_demographics')}，此外部比較為事後分析。肝炎軸的內部結果支持 H₁：{auc('肝炎', LR):.3f} 對 {E['肝炎']['M1_demographics']['auroc_mean']:.3f}，ΔAUROC {dvd('肝炎', LR)}。外部則沒有高於年齡、性別，ΔAUROC {xd('肝炎', 'LR_routine−M1_demographics')}，但只有 {X['肝炎']['n_pos']} 名陽性，無法確認或否定。因此 H₁ **部分成立**。

### 二、非線性模型帶來什麼

糖尿病軸的梯度提升在內部、時間外推與外部資料上都比邏輯迴歸高；經同樣的保序校準後，內部與 2021–2023 年的校準接近理想，時間外推與人口加權時的偏移也比邏輯迴歸小（表3）。這與「機器學習常不優於邏輯迴歸」的系統性回顧不同[@christodoulou]，表示糖尿病標籤與常規檢驗之間存在線性模型沒有抓到的關係；本研究尚未分析是哪些特徵或交互作用造成增益。代價是可解釋性：網頁工具必須逐項說明「為什麼」，邏輯迴歸的推動因子可由係數直接算出。本研究事前決定工具維持邏輯迴歸，梯度提升的增益留待可解釋的非線性方法與獨立資料驗證。

### 三、肝炎軸其實是 C 型肝炎軸

C 型肝炎的常規檢驗型態清楚（AUROC {ST['C型_HCV_RNA']['auroc']:.3f}），與慢性病毒性肝炎改變血脂與肝臟合成功能的描述一致[@bashir]；B 型肝炎帶原者的常規檢驗大多接近正常（{ST['B型_HBsAg']['auroc']:.3f}）。2021–2023 年的陽性組成偏向 B 型，正好落在工具的弱點上。

### 四、雜湊抓不到的錯誤

本研究最重要的方法學教訓是：資料來源正確，不等於分析正確。下列問題都能通過 SHA256 檢查：

| 版本 | 問題 | 後果 | 更正 |
|---|---|---|---|
| v3 | 1999–2000 年肌酸酐套錯校正公式 | 該週期腎功能被高估 | eGFR < 60 由 {A3['reclassification']['scr_fix_1999_2000']['egfr_lt60_old']} 人增為 {A3['reclassification']['scr_fix_1999_2000']['egfr_lt60_new']} 人 |
| v3 | 2003–2004 年沒有 HCV RNA 變數 | 抗體陽性者被判為陰性 | 改判為未知 |
| v3 | 沒做檢驗的人被當成陰性 | 陰性組混入未受檢者 | 三值判定；腎臟可判定 {n(A3['old_rebuild']['outcome_known_old_rule'])} → {n(A3['old_rebuild']['n_adults'] - A3['total']['kidney']['unknown'])} 人 |
| v3 | 血中、尿中金屬合併時欄位撞名 | 血尿比較不是同一批人 | 在同一批 {n(Pb['n_both'])} 人中重新比較 |
| v3 外部 | 2021–2023 年儀器與方法更換 | 兩個特徵整欄缺值、十餘項不在同一量尺 | 評估前提交修正 |
| v3.2 | 2001–2002 年四項常規生化改名 | 整週期缺值 | 改名對應 |
| v3.2 | 2017–2018 年生化儀器更換 | 開發資料混用兩種量尺 | 12 項換回共同量尺 |
| v3.2 | HDL 未讀入且被誤封存 | 常規套組少一項 | 讀入並解除封存 |

這些錯誤都不會讓程式當掉，只會安靜地產生看似合理的數字。v3.2 的三項錯誤是在「逐週期檢查每個特徵的有值比例」與「逐一閱讀 CDC 文件」時發現的；它們對整體判別的影響很小，卻會改變個人的輸出，例如示範受試者的肝炎軸機率因補回 HDL 而明顯上升。

### 五、作為病因線索的意義與界線

本研究的核心問題是「找原因」。現有資料能支持的結論是：當常規檢驗呈現與 C 型肝炎或糖尿病相符的型態時，這組數值提供「值得優先查證這兩個候選病因」的線索，並附有推動因子與經校準的機率。它不能回答腎損傷是否由該病造成；免疫性病因在 NHANES 缺乏補體、自體抗體與病理，仍無法評估[@yang]。在臨床行動上，肝炎檢驗應依普遍篩檢建議進行，本工具的角色是解釋與排序，不是省略檢驗。

### 六、研究限制

1. 標籤是共存疾病的操作型定義，不是腎臟病理；單次檢驗不能確認慢性。
2. 1999–2018 年資料已在前幾版反覆使用，內部結果屬探索性；2021–2023 年資料也已用於 v3 外部確認與重新校準，v3.2 的外部數字是事後分析，網頁工具更新後的校準仍無獨立資料驗證。
3. 肝炎軸外部只有 {X['肝炎']['n_pos']} 個事件，對 B 型肝炎幾乎沒有訊號。
4. 2007–2010 年 HbA1c 分布右移原因不明而依 CDC 建議使用原值[@ghb_f]；2013–2014 週期起血球分析儀更換，CDC 無法回溯比對、沒有換算式[@cbc_h]；非常規特徵的跨週期方法差異未換算。
5. 預測視為固定，設計變異不含模型重新配適的變異。
6. 暴露分析為單次橫斷面資料；美國調查的機率不能直接移植到臺灣的就醫族群，輸入值也必須與開發資料的檢驗量尺一致。

### 七、未來展望

| 階段 | 目標 | 資料 | 狀態 |
|---|---|---|---|
| 一 | 界定常規檢驗提供病因線索的能力與邊界 | NHANES 公開資料 | 完成（本作品） |
| 二 | 以病理或臨床參考標準驗證，並重建免疫軸 | 醫院資料，含診斷前檢驗與免疫檢驗 | 待資料與倫理審查 |
| 三 | 從關聯推進到因果方向 | 縱貫追蹤或基因工具變數 | 視第二階段結果 |

近期工作：(1) 以獨立資料驗證網頁工具的校準；(2) 以可解釋的非線性方法保留糖尿病軸的增益；(3) 累積肝炎事件，另建 B 型肝炎的模型；(4) 建立臺灣常用檢驗方法與 NHANES 量尺的對照。

## 陸、結論

1. 常規血液與尿液檢驗對腎臟指標異常成人中的糖尿病標籤有中等辨識力，內部校準良好，並在內部與 2021–2023 年資料上都明顯優於只用年齡、性別；非線性模型更高（內部 {auc('糖尿病', HG):.3f}、2021–2023 年 {xm('糖尿病', HG)['auroc']:.3f}），校準也接近理想。
2. 肝炎軸的訊號主要來自 C 型肝炎；對 B 型肝炎幾乎沒有訊號。外部事件太少，且未高於只用年齡、性別，無法確認。
3. 網頁工具 v3.2 採修正後資料訓練的常規套組邏輯迴歸，保留逐項解釋；重新校準在交叉驗證中大致維持，但仍需獨立資料驗證。
4. 本工具提供的是病因線索，不是診斷，也不能用來省略肝炎篩檢。
5. 資料來源正確不等於分析正確：本研究共找到並更正八項能通過雜湊檢查的資料問題。

## 柒、參考文獻資料

{{REFERENCES}}

## 附錄

### 附錄一　常規套組變數字典

「近端排除」表示該軸因生理上緊鄰標籤而移除。

| 代號 | 名稱 | 單位 | 肝炎軸 | 糖尿病軸 |
|---|---|---|---|---|
{DICT_ROWS}

### 附錄二　CDC 官方回推式（X 為換算後、Y 為原值）

| 變數 | 名稱 | 2017–2018 → 1999–2016 量尺（BIOPRO_J） | 2021–2023 → 2017–2020 量尺（修正一） |
|---|---|---|---|
{CONV_ROWS}

### 附錄三　資料與程式可得性

程式與結果存放於 Git 儲存庫（目錄 experiments/kidney_cause），每一步都有提交代碼可供查核。

> ⚠️ **待確認**：是否附上儲存庫網址。網址與提交紀錄可能透露作者或學校，請依比賽規定決定。

重要提交：v3 分析計畫 {COMMITS['plan_v3']}、外部確認協定 {COMMITS['proto']}、修正一 {COMMITS['amend']}、外部確認結果 {COMMITS['ext']}、設計變異計畫 {COMMITS['dv']}、v3.2 計畫 {COMMITS['plan_v32']}。v3.2 重現入口：`evaluate_v3_2.py` → `external_v3_2.py` → `make_figures_v3_2.py` → `verify_direction_html.py` → `build_fair_v3_2.py`；版本沿革見 `docs/VERSION_LOG.md`。
"""


def emit(fmt):
    text, refs = render_citations(BODY)
    text = text.replace("{REFERENCES}", "\n\n".join(refs))    # 每筆文獻自成一段
    for i, f in enumerate(FIGS, 1):
        text = text.replace(f"{{FIG{i}}}", f"![[figure/v3_2/{f}]]" if fmt == "vault" else f"![](../kidney_cause/figures/v3_2/{f})")
    assert "{" not in text and "[@" not in text, "仍有未處理之欄位或引用"
    return text, refs


def main():
    vault_txt, refs = emit("vault")
    repo_txt, _ = emit("repo")
    fm = ("---\ntitle: 科展作品說明書 v3.2\ndate: 2026-09-27\ntags: [腎臟研究, 科展, 說明書]\n"
          "待辦:\n  - 研究動機（壹之一）請填真實經驗\n  - 組別與科別請依參賽身分確認\n  - 延續性研究說明表與參與比重\n"
          "  - AI 輔助工具之使用聲明依比賽規定確認\n  - 倫理審查需求與指導老師確認\n  - 附錄三是否附儲存庫網址（匿名規定）\n---\n\n")
    note = ("> [!info] 由 `experiments/kidney_cause/build_fair_v3_2.py` 自結果檔產生（數字不手打）。改內容請改產生程式後重跑；"
            "Word 以 `md2docx.py <本檔> --fair` 轉出。封面只寫科別、組別、作品名稱與關鍵詞；全文不得出現校名與姓名。\n\n")
    dst_fig = os.path.join(VAULT, "figure", "v3_2")
    os.makedirs(dst_fig, exist_ok=True)
    for f in FIGS:
        shutil.copy2(os.path.join(ROOT, "figures", "v3_2", f), os.path.join(dst_fig, f))
    open(os.path.join(VAULT, f"{NAME}.md"), "w", encoding="utf-8").write(fm + note + vault_txt)
    os.makedirs(REPO_DOCS, exist_ok=True)
    open(os.path.join(REPO_DOCS, f"{NAME}.md"), "w", encoding="utf-8").write(repo_txt)
    body = vault_txt.split("## 摘要", 1)[1]
    print(f"[完成] {os.path.join(VAULT, NAME + '.md')}（{len(fm + note + vault_txt):,} 字元）")
    print(f"[完成] {os.path.join(REPO_DOCS, NAME + '.md')}")
    print(f"摘要 {len(ABSTRACT)} 字（上限 300）｜關鍵詞 {len(KEYWORDS.split('、'))} 個｜參考文獻 {len(refs)} 筆｜圖 {len(FIGS)}｜內文約 {len(body):,} 字元")


if __name__ == "__main__":
    main()
