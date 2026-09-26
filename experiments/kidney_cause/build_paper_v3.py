# -*- coding: utf-8 -*-
"""v3 研究論文與審查回應表——所有數字由結果檔讀出（不手打）。  python build_paper_v3.py
輸出：Obsidian 主稿（研究計畫書/研究論文_v3重分析.md、審查意見回應_v3.md，圖在 figure/v3/）
      repo 副本（experiments/docs/ 同名兩檔）。"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")
VAULT = r"C:\Users\tpc10\Desktop\01_研究專案\MD_Piece_腎臟研究\AIMD\腎炎模型\研究計畫書"
REPO_DOCS = os.path.join(os.path.dirname(ROOT), "docs")
J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))
A, EV, X, CK, PR = (J("results", "v3_audit.json"), J("results", "v3_eval.json"), J("results", "exwas_v3.json"),
                    J("results", "exwas_v3_checks.json"), J("params", "external_validation_protocol.json"))
E = EV["axes"]
XV, XPH, XAM = (J("results", "external_2021_2023.json"), J("results", "external_2021_2023_posthoc.json"),
                J("params", "external_validation_amendment_1.json"))
XC = J("results", "external_2021_2023_precheck.json")["versions"]["調和（修正一）"]["features"]
RC = J("results", "direction_v3_1_recalibration.json")["axes"]
DV = J("results", "design_variance.json")
DV_COMMITS = dict(plan="9edd968", results="e7d16e4")
EXT_COMMITS = dict(amend="44b0ace", results="a7c4af8")
FIGS = ["圖1_分析樣本與三值標籤.png", "圖2_判別力與基準.png", "圖3_校準與分區.png", "圖4_回溯時間評估.png",
        "圖5_決策曲線.png", "圖6_暴露血尿比較.png", "圖7_外部確認.png", "圖S1_示範輸出.png"]


def n(x):
    return f"{x:,}"


def p3(x):
    return f"{x:.3f}"


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def num(x, d=3):
    t = f"{x:.{d}f}"
    return ("−" + t[1:]) if t.startswith("-") and float(t) != 0 else t.lstrip("-")


def ci(c):
    return f"{num(c[0])} 至 {num(c[1])}" if min(c) < 0 else f"{c[0]:.3f}–{c[1]:.3f}"


def sgn(x):
    t = num(x)
    return t if t.startswith("−") else "+" + t


def axis_vals(key):
    a, t = E[key], E[key]["tool"]
    m, lo, hi, c95 = t["repeats"]["mean"], t["repeats"]["min"], t["repeats"]["max"], t["ci95_repeat0"]
    cal, bB, bA = t["calibration_repeat0"], t["bands_repeat0"]["B"], t["bands_repeat0"]["A"]
    cmp_, ab, tm = a["comparisons"], a["ablation_adjacent"], a["temporal"]["early_to_late"]
    ew = a["temporal"]["expanding_window"]
    ew_auc = {c: v["auroc"] for c, v in ew.items()}
    d = lambda k: cmp_[k]["delta_vs_M3_repeat0"]
    return dict(
        n=n(t["n"]), pos=n(t["n_pos"]), prev=pct(t["prevalence"]), prev3=p3(t["prevalence"]),
        auc=p3(m["auroc_cal"]), auc_ci=ci(c95["auroc_cal"]), auc_rng=f"{lo['auroc_cal']:.3f}–{hi['auroc_cal']:.3f}",
        auc_raw=p3(m["auroc_raw"]), ap=p3(m["ap_cal"]), ap_ci=ci(c95["ap_cal"]), ap_raw=p3(m["ap_raw"]),
        ap_lift=f"{m['ap_cal'] / t['prevalence']:.1f}", prauc=p3(m["prauc_trapz_cal"]),
        cint=num(cal["intercept"], 2), cslope=f"{cal['slope']:.2f}", brier=f"{cal['brier']:.4f}",
        bss=f"{cal['brier_skill']:.3f}", meanpred=pct(cal["mean_pred"]), obs=pct(cal["observed"]),
        covA=pct(bA["coverage"]), covB=pct(bB["coverage"]),
        sensB=p3(bB["answered_sensitivity"]), specB=p3(bB["answered_specificity"]),
        sensA=p3(bA["answered_sensitivity"]), specA=p3(bA["answered_specificity"]),
        lowposA=n(bA["positives_in_low"]), lowposB=n(bB["positives_in_low"]),
        six=bB["six_cell"], bandB=bB["band"], bandA=bA["band"],
        t1000=f"{bB['per_1000_if_skip_low']['tested']:.0f}", m1000=f"{bB['per_1000_if_skip_low']['missed']:.1f}",
        mshare=pct(bB["per_1000_if_skip_low"]["missed_share_of_pos"], 0),
        insuff=n(t["insufficient_data_n"]),
        thrB=[pct(x, 2) if key == "肝炎" else pct(x) for x in t["thresholds_full_sample"]["B"]],
        thrA=[pct(x, 2) if key == "肝炎" else pct(x) for x in t["thresholds_full_sample"]["A"]],
        m1=p3(cmp_["M1_demographics"]["auroc_mean"]), m1ap=p3(cmp_["M1_demographics"]["ap_mean"]),
        m2=p3(cmp_["M2_basic_panel"]["auroc_mean"]), m2ap=p3(cmp_["M2_basic_panel"]["ap_mean"]),
        m3=p3(cmp_["M3_full"]["auroc_mean"]), m3ap=p3(cmp_["M3_full"]["ap_mean"]),
        m4=p3(cmp_["M4_full_HGB"]["auroc_mean"]), m4ap=p3(cmp_["M4_full_HGB"]["ap_mean"]),
        d1=sgn(d("M1_demographics")["d_auroc"]), d1ci=ci(d("M1_demographics")["ci95"]["d_auroc"]),
        d2=sgn(d("M2_basic_panel")["d_auroc"]), d2ci=ci(d("M2_basic_panel")["ci95"]["d_auroc"]),
        d2ap=sgn(d("M2_basic_panel")["d_ap"]), d2apci=ci(d("M2_basic_panel")["ci95"]["d_ap"]),
        d4=sgn(d("M4_full_HGB")["d_auroc"]), d4ci=ci(d("M4_full_HGB")["ci95"]["d_auroc"]),
        d4ap=sgn(d("M4_full_HGB")["d_ap"]), d4apci=ci(d("M4_full_HGB")["ci95"]["d_ap"]),
        ab_with=p3(ab["auroc_with"]), ab_without=p3(ab["auroc_without"]),
        ab_d=sgn(ab["auroc_with"] - ab["auroc_without"]), ab_ci=ci(ab["delta_ci95"]["d_auroc"]),
        ab_apw=p3(ab["ap_with"]), ab_apwo=p3(ab["ap_without"]), ab_apci=ci(ab["delta_ci95"]["d_ap"]),
        ab_removed="、".join({"LBXSATSI": "ALT", "LBXSASSI": "AST", "LBXSGTSI": "GGT", "LBXSTB": "總膽紅素",
                              "LBXSGL": "血糖", "LBXSOSSI": "滲透壓"}[x] for x in ab["removed"]),
        tl=p3(tm["auroc"]), tl_ci=ci(tm["ci95"]["auroc"]), tl_n=n(tm["n"]), tl_pos=n(tm["n_pos"]), tl_ap=p3(tm["ap"]),
        tl_ptr=pct(tm["prevalence_train"]), tl_pte=pct(tm["prevalence_test"]), tl_mp=pct(tm["mean_pred"]),
        tl_cint=num(tm["calibration"]["intercept"], 2), tl_cslope=f"{tm['calibration']['slope']:.2f}",
        ew_min=p3(min(ew_auc.values())), ew_min_c=min(ew_auc, key=ew_auc.get),
        ew_max=p3(max(ew_auc.values())), ew_max_c=max(ew_auc, key=ew_auc.get),
        ls=a["label_sensitivity"], dca={round(r["pt"], 3): r for r in a["decision_curve"]})


H, D = axis_vals("肝炎"), axis_vals("糖尿病")


def ext_vals(part, key):
    """外部確認一軸之數值（results/external_2021_2023.json）。"""
    r = XV[part]["axes"][key]
    ms = r["models"]
    m, b, g = ms["v3_full_LR（部署）"], ms["v3_basic_LR（常規套組候選）"], ms["v3_full_HGB（比較，僅判別）"]
    c, bb = m["calibration"], m["bands_B"]
    d = 2 if key == "肝炎" else 1
    return dict(
        n=n(r["n"]), pos=r["n_pos"], prev=pct(r["prevalence"], d),
        auc=p3(m["auroc"]), auc_ci=ci(m["ci95"]["auroc"]), ap=p3(m["ap"]), ap_ci=ci(m["ci95"]["ap"]),
        ap_lift=f"{m['ap'] / r['prevalence']:.1f}", cint=num(c["intercept"], 2), cslope=f"{c['slope']:.2f}",
        brier=f"{c['brier']:.4f}", bss=num(c["brier_skill"], 3), meanpred=pct(c["mean_pred"], d), obs=pct(c["observed"], d),
        ratio_pred=f"{c['mean_pred'] / c['observed']:.1f}", insuff=n(m["insufficient_data_n"]),
        covB=pct(bb["coverage"]), covA=pct(m["bands_A"]["coverage"]),
        rates="／".join(pct(bb["band"][k]["observed_rate"]) for k in ("傾向", "不確定", "不傾向")),
        low_n=n(bb["band"]["不傾向"]["n"]), low_pos=bb["six_cell"]["陽性_不傾向"],
        bauc=p3(b["auroc"]), bauc_ci=ci(b["ci95"]["auroc"]), dbf=sgn(b["auroc"] - m["auroc"]),
        dbf_ci=ci(r["basic_minus_full"]["d_auroc"]), bcint=num(b["calibration"]["intercept"], 2),
        bcslope=f"{b['calibration']['slope']:.2f}", gauc=p3(g["auroc"]), gap=p3(g["ap"]))


XH, XD = ext_vals("primary", "肝炎"), ext_vals("primary", "糖尿病")
SH, SD = ext_vals("sensitivity_as_frozen", "肝炎"), ext_vals("sensitivity_as_frozen", "糖尿病")
XK, SK = XV["primary"]["kidney"], XV["sensitivity_as_frozen"]["kidney"]
PHH, PHD, HC = XPH["axes"]["肝炎"], XPH["axes"]["糖尿病"], XPH["hep_positive_composition"]
ph = lambda r: (f"{p3(r['auroc_all_inputs'])} {'升' if r['delta_masked_minus_all'] >= 0 else '降'}為 {p3(r['auroc_masked'])}"
                f"（差 {sgn(r['delta_masked_minus_all'])}，95% CI {ci(r['delta_ci95'])}）")
xr = lambda f: f"{XC[f]['ratio']:.2f}"


def dv(r):
    """設計變異結果之格式化（盛行率為百分比，校準差為百分點）。"""
    w, d = r["weighted"], 2 if r["weighted"]["prevalence"]["est"] < 0.05 else 1
    pp = lambda x: num(100 * x, 2)
    return dict(
        prev=pct(w["prevalence"]["est"], d), prev_ci="–".join(pct(x, d) for x in w["prevalence"]["ci95"]),
        deff=f"{w['prevalence']['deff']:.2f}", uw_prev=pct(r["unweighted"]["prevalence"], d),
        auc=p3(w["auroc"]["est"]), auc_ci=ci(w["auroc"]["ci95"]), ap=p3(w["ap"]["est"]), ap_ci=ci(w["ap"]["ci95"]),
        cd=pp(w["calib_diff"]["est"]), cd_ci=f"{pp(w['calib_diff']['ci95'][0])} 至 {pp(w['calib_diff']['ci95'][1])}",
        cd_has0=w["calib_diff"]["ci95"][0] <= 0 <= w["calib_diff"]["ci95"][1], df=r["df"], n_rep=r["n_replicates"])


DH, DD = dv(DV["internal"]["肝炎"]), dv(DV["internal"]["糖尿病"])
FULL, BASIC_M = "v3_full_LR（部署）", "v3_basic_LR（常規套組候選）"
XDH, XDD = dv(DV["external"]["肝炎"][FULL]), dv(DV["external"]["糖尿病"][FULL])
max_se_gap = 100 * max(abs(x - 1) for x in DV["checks"]["jkn_taylor_se_ratio"])
MK = J("results", "v3_markers.json")


def _hcv_rows():
    import markers_v3
    from binary_tasks import LABEL_ADJACENT
    from nhanes_cohort import build_v3
    V = build_v3(J("params", "design.json"), verbose=False)
    ff = [f for f in V["features"] if f not in LABEL_ADJACENT["infection"]]
    return {r["marker"]: r for r in markers_v3.scan(V["cohort"][V["cohort"]["hcv3"].notna()], "hcv3", ff)}


HCV_ALL = _hcv_rows()
mk = lambda grp, m: p3(next(r["auc"] for r in MK[grp]["top"] if r["marker"] == m))
mk_all = lambda m: p3(HCV_ALL[m]["auc"])
mk_n = lambda m: HCV_ALL[m]["n_pos"]
T, R = A["total"], A["reclassification"]
old = A["old_rebuild"]
ls_h, ls_d = H["ls"], D["ls"]
hbv, hcv = ls_h["僅B肝_HBsAg"], ls_h["僅C肝_RNA"]
dmq, dma, dmb = ls_d["僅問卷_DIQ010"], ls_d["僅HbA1c"], ls_d["排除邊緣_DIQ010=3"]
Xr = {r["exposure"]: r for r in X["results"]}
xo = lambda e: Xr[e]["headline"]
Pb, Cd = CK["metals"]["鉛"], CK["metals"]["鎘"]
mo = lambda M, o, k: M["models"][o][k]
orr = lambda m: f"{m['OR_per_doubling']:.2f}（{m['ci'][0]:.2f}–{m['ci'][1]:.2f}）"
sig = sorted([r for r in X["results"] if r["significant_fdr05"]], key=lambda r: r["q_bh"])
kd_known = old["n_adults"] - T["kidney"]["unknown"]
fm = PR["frozen_models"]
plan_sha = EV["plan_sha256"]


def per_cycle_table():
    rows = ["| 週期 | 成人 | 腎臟 陽／陰／未知 | 肝炎 陽／陰／未知 | 糖尿病 陽／陰／未知 | 備註 |", "|---|---|---|---|---|---|"]
    for r in A["per_cycle"]:
        note = "無 HCV RNA 變數：HCV 抗體陽性者只能判未知" if r["cycle"] == "2003-2004" else (
            "HCV RNA 碼 3＝抗體篩檢陰性" if r["cycle"] >= "2013-2014" else "")
        k, h, dm = r["kidney"], r["hep_in_kidney"], r["dm_in_kidney"]
        rows.append(f"| {r['cycle']} | {n(r['adults'])} | {n(k['pos'])}／{n(k['neg'])}／{n(k['unknown'])} | "
                    f"{h['pos']}／{n(h['neg'])}／{h['unknown']} | {n(dm['pos'])}／{n(dm['neg'])}／{dm['unknown']} | {note} |")
    return "\n".join(rows)


def six_table(v):
    s = v["six"]
    return (f"| 實際標籤 | 傾向 | 不確定 | 不傾向 |\n|---|---|---|---|\n"
            f"| 陽性 | {n(s['陽性_傾向'])} | {n(s['陽性_不確定'])} | {n(s['陽性_不傾向'])} |\n"
            f"| 陰性 | {n(s['陰性_傾向'])} | {n(s['陰性_不確定'])} | {n(s['陰性_不傾向'])} |\n"
            f"| 該區實際陽性率 | {pct(v['bandB']['傾向']['observed_rate'])} | {pct(v['bandB']['不確定']['observed_rate'])} | "
            f"{pct(v['bandB']['不傾向']['observed_rate'])} |")


def dca_row(v, pt):
    r = v["dca"][pt]
    return f"{pct(pt, 1)}：模型 {r['nb_model']:.4f}、全數送驗 {r['nb_test_all']:.4f}"


def conv_table():
    from nhanes_cohort import FEATURE_LABELS
    rows = ["| 變數 | 檢驗 | 回推式（舊＝） | 來源 |", "|---|---|---|---|"]
    for v, c in XAM["conversions"].items():
        a, b = map(float, re.match(r"舊 = (\S+) \+ (\S+) × 新", c["equation"]).groups())
        src = os.path.basename(c["source"]).replace(".htm", "")
        fa = ("−" + f"{-a:g}") if a < 0 else f"{a:g}"          # 照官方文件之有效位數，不再四捨五入
        rows.append(f"| {v} | {FEATURE_LABELS.get(v, v)} | {fa} ＋ {b:g} × 新值 | {src} |")
    return "\n".join(rows)


sha_amend = __import__("hashlib").sha256(open(os.path.join(ROOT, "params", "external_validation_amendment_1.json"), "rb").read()).hexdigest()


def sig_table():
    rows = ["| 暴露 | OR（95% CI） | 量尺 | q 值 | n |", "|---|---|---|---|---|"]
    name = {"藥_利尿劑": "利尿劑", "藥_胰島素": "胰島素", "藥_別嘌醇": "別嘌醇", "LBXBCD": "血鎘", "LBXBPB": "血鉛",
            "藥_ACEI_ARB": "ACEI／ARB", "藥_雙胍": "雙胍類", "藥_鈣調磷酸酶": "鈣調磷酸酶抑制劑", "藥_PPI": "質子幫浦抑制劑",
            "藥_磺醯脲": "磺醯脲類", "藥_他汀": "他汀類", "LBXTHG": "血汞", "LBXBSE": "血硒",
            "URXUTL": "尿鉈", "URXUCS": "尿銫", "URXUSR": "尿鍶", "URXUBA": "尿鋇", "URXUSB": "尿銻",
            "LBXPFHS": "血清 PFHxS", "LBXPFOA": "血清 PFOA", "LBXNFOA": "血清 n-PFOA"}
    label = lambda e: name.get(e.replace("_percr", ""), e) + ("（肌酸酐比值）" if e.endswith("_percr") else "")
    for r in sig[:12]:
        h = r["headline"]
        rows.append(f"| {label(r['exposure'])} | {h['OR']:.3f}（{h['ci'][0]:.3f}–{h['ci'][1]:.3f}） | "
                    f"{h['scale']} | {r['q_bh']:.1e} | {n(h['n'])} |")
    return "\n".join(rows)


PAPER = f"""# 常規檢驗能否提供腎臟指標異常的病因線索？

## ——肝炎病毒感染與糖尿病兩個共存標籤：NHANES 1999–2018 重分析與 2021–2023 外部確認（v3）

作者　＿＿＿＿＿＿　　所屬單位　＿＿＿＿＿＿　　版本　v3（2026-09-27）

---

## 摘要

**背景與目的**　本研究的起點是一個臨床問題：腎臟指標異常時，能否只用已有的常規血液與尿液檢驗，指出病因的大概方向。公開健康調查沒有病理診斷，只能提供共存疾病標籤；共存疾病是候選病因，不等於病因。本研究評估兩個共存標籤（肝炎病毒感染、糖尿病）能被常規檢驗辨識到什麼程度，作為病因線索，並依 2026 年 9 月 26 日之外部方法學審查，以真實資料重建標籤與評估流程。

**方法**　NHANES 1999–2018 十個週期成人 {n(old['n_adults'])} 人。更正 1999–2000 年血清肌酸酐校正式、依官方式轉換 2007 年前尿肌酸酐；腎臟指標與兩個標籤改採三值（陽性、陰性、未知），各軸排除未知者。部署模型為五折交叉配適邏輯迴歸集成加保序校準，以分層五折重複五次之巢狀外層評估（校準器與分區門檻只用外層訓練資料），並在同一切分比較人口學、常規套組與梯度提升模型；另做回溯時間評估、調查權重、標籤定義敏感度與決策曲線。分析計畫於執行前提交版本控制。外部確認以從未參與開發的 NHANES 2021–2023 一次評估；取用後、評估前發現檢驗儀器與方法變更，依 CDC 官方回推式把數值換回開發時的量尺，並於評估前提交此修正。

**結果**　腎臟指標異常 {n(T['kidney']['pos'])} 人（原稿 {n(old['kidney'])} 人），另有 {n(T['kidney']['unknown'])} 人無法判定。肝炎標籤陽性 {H['pos']} 人、糖尿病標籤陽性 {D['pos']} 人。肝炎軸 AUROC {H['auc']}（95% CI {H['auc_ci']}）、平均精確率（AP）{H['ap']}（盛行率 {H['prev3']}），校準斜率 {H['cslope']}；糖尿病軸 AUROC {D['auc']}（{D['auc_ci']}）、AP {D['ap']}（盛行率 {D['prev3']}），校準斜率 {D['cslope']}。只用年齡與性別時為 {H['m1']} 與 {D['m1']}。以 1999–2008 年訓練、2009–2018 年評估，兩軸為 {H['tl']} 與 {D['tl']}。肝炎軸的訊號幾乎全來自 C 型肝炎：僅 C 肝標籤 AUROC {p3(hcv['auroc'])}，僅 B 肝標籤 {p3(hbv['auroc'])}。糖尿病軸的梯度提升模型比邏輯迴歸高 {D['d4'][1:]}（95% CI {D['d4ci']}）。在 2021–2023 年外部資料中，糖尿病軸 AUROC {XD['auc']}（{XD['auc_ci']}），只用常規套組的模型為 {XD['bauc']}、梯度提升為 {XD['gauc']}；肝炎軸只有 {XH['pos']} 名陽性，AUROC {XH['auc']}（{XH['auc_ci']}），區間過寬而無法確認，且平均預測為實際的 {XH['ratio_pred']} 倍。

**結論**　常規檢驗對 C 型肝炎相關的肝炎標籤與糖尿病標籤有中等且校準良好的辨識力，可作為病因線索；對 B 型肝炎幾乎沒有訊號。在未參與開發的新資料中，糖尿病軸大致維持判別力，只用常規套組的模型不輸全特徵模型；肝炎軸的外部事件太少，仍待確認，使用前須重新校準。辨識共存疾病不等於確定腎損傷病因，且在普遍篩檢的建議下，本工具不宜用來決定誰不必驗肝炎。

**關鍵詞**：NHANES；腎臟指標異常；病因線索；C 型肝炎；糖尿病；預測模型；校準；外部確認

---

## Abstract

**Background** We asked whether routine blood and urine tests can point toward the cause of abnormal kidney markers. Public survey data provide comorbidity labels, not etiology, so we evaluated how well routine tests identify two candidate-cause labels (hepatitis virus infection and diabetes) and rebuilt the analysis after an external methodological review.

**Methods** Adults in NHANES 1999–2018 (n = {n(old['n_adults'])}). We corrected the 1999–2000 serum creatinine calibration, harmonized pre-2007 urine creatinine, and used three-valued labels (positive, negative, unknown). The deployed model (cross-fitted logistic ensemble with isotonic calibration) was evaluated by nested 5-fold cross-validation repeated five times, with calibration and thresholds learned only in outer training folds, and compared on identical splits with demographic, routine-panel and gradient-boosting models. External confirmation used NHANES 2021–2023, evaluated once after a pre-evaluation amendment that applied the CDC's official backward equations for laboratory instrument and method changes.

**Results** Kidney-marker abnormality was present in {n(T['kidney']['pos'])} adults. The hepatitis axis had an AUROC of {H['auc']} (95% CI {H['auc_ci']}) and an average precision of {H['ap']} at a prevalence of {H['prev3']}; the diabetes axis had {D['auc']} ({D['auc_ci']}) and {D['ap']} at {D['prev3']}. Calibration slopes were {H['cslope']} and {D['cslope']}. Training on 1999–2008 and testing on 2009–2018 gave {H['tl']} and {D['tl']}. The hepatitis signal came from hepatitis C (AUROC {p3(hcv['auroc'])}) rather than hepatitis B ({p3(hbv['auroc'])}). In NHANES 2021–2023, the diabetes axis had an AUROC of {XD['auc']} ({XD['auc_ci']}); a routine-panel model reached {XD['bauc']} and gradient boosting {XD['gauc']}. The hepatitis axis had only {XH['pos']} events (AUROC {XH['auc']}, 95% CI {XH['auc_ci']}) and over-predicted risk by a factor of {XH['ratio_pred']}.

**Conclusions** Routine tests carry calibrated, moderate signal for hepatitis C–related and diabetes labels, usable as etiologic clues but not as diagnoses. New data supported the diabetes axis and favored the routine-panel model; the hepatitis axis remains unconfirmed and needs recalibration.

---

## 1　前言

腎臟病的病因評估需要整合病史、共存疾病、用藥、身體檢查、實驗室數據、影像，以及適當情境下的病理或基因檢查；單次 eGFR 下降或白蛋白尿升高，也不足以確認異常已持續三個月以上[@kdigo]。臨床上多數人每年都有抽血與驗尿，這些數值早已存在，卻很少被拿來回答「腎臟為什麼出問題」。本研究的核心問題正是這一點：**只用常規檢驗，能不能指出病因的大概方向？**

公開健康調查能回答的範圍有限。美國國家健康與營養調查（NHANES）沒有腎臟病理，只能提供共存疾病的操作型標籤，例如 B 型或 C 型肝炎病毒感染、糖尿病。這些疾病是腎損傷的候選病因，但標籤成立不代表腎損傷由它造成。因此本研究把問題界定為：**常規檢驗能否辨識這兩個候選病因的共存標籤**——辨識得出來，才有資格被稱為「病因線索」；要確認病因，仍需病理或臨床參考標準。

本研究前一版（v2）於 2026 年 9 月 26 日接受外部方法學審查。審查者沒有取得資料與程式，因此將標籤缺失、跨週期校正、校準流程、抽樣權重與時間驗證列為「待執行」。本版以原始資料執行這些重分析，並在過程中發現數項審查者無法看見的資料錯誤。研究目的為：

1. 依 NHANES 官方文件重建腎臟指標與兩個共存標籤，未知不再當作陰性；
2. 以校準與門檻完全留在訓練資料內的巢狀外層評估，報告兩軸工具的判別、校準與三段分區表現[@tripod,probast]；
3. 以同一切分比較簡單基準、檢驗時間外推、調查權重與標籤定義的影響；
4. 重新檢視上游暴露關聯，改在同一批受試者比較血中與尿中金屬；
5. 在取用任何新資料之前凍結外部確認的協定與模型，再以 NHANES 2021–2023 一次評估。

## 2　材料與方法

### 2.1　研究設計與資料來源

本研究為 NHANES 1999–2018 年十個週期的重複橫斷面次級資料分析，納入年齡至少 20 歲者。各週期為不同受試者，本設計不追蹤個人發病時序，故稱「分析樣本」而非世代。資料檔的來源網址與 SHA256 雜湊記錄於出處帳本，用於確認檔案未被更動；雜湊不能證明資料的單位、合併或標籤正確——本版發現的數項錯誤都能通過雜湊檢查。分析計畫（`params/v3_analysis_plan.json`，SHA256 前 16 碼 {plan_sha[:16]}）在執行評估程式之前提交版本控制（提交 bf269c5）。1999–2018 年資料已於先前版本反覆檢視，本版重分析屬探索性修訂，不是確認性驗證。

### 2.2　腎臟指標與檢驗校正

腎臟指標異常定義為單次 eGFR < 60 mL/min/1.73 m² 或尿白蛋白／肌酸酐比（ACR）≧ 30 mg/g。eGFR 以 CKD-EPI 2021 無種族係數公式計算[@egfr]。血清肌酸酐依官方文件校正：1999–2000 年為 1.013 × 原值 ＋ 0.147[@selvin,lab18]，2005–2006 年為 −0.016 ＋ 0.978 × 原值[@biopro_d]；2001–2004 年不需校正[@selvin]。**前一版在 1999–2000 年誤用了 NHANES III（1988–1994）的公式 −0.184 ＋ 0.960 × 原值**，使該週期原值 1.0 mg/dL 被換算為 0.776 而非 1.160，eGFR 因此被高估。2007 年起尿肌酸酐改用酵素法，依官方分段式轉換 2007 年前之值[@albcr]：原值 X < 75 mg/dL 時為 (1.02√X − 0.36)²，75–250 時為 (1.05√X − 0.74)²，≧ 250 時為 (1.01√X − 0.10)²。

腎臟結果採三值：任一已測指標達門檻為陽性；兩項皆有值且正常為陰性；一項正常而另一項缺失、或兩項皆缺失為未知。

### 2.3　共存標籤

**肝炎病毒感染標籤**：B 型肝炎表面抗原（HBsAg）陽性或 C 型肝炎病毒 RNA 陽性[@hbv]。HBsAg 在各週期凡有肝炎血清結果者皆為陽性或陰性碼，缺值即未檢測。HCV RNA 依檢驗流程只在抗體陽性或不確定者檢測，故 RNA 缺值且抗體陰性者判為 HCV 陰性；2013 年起 RNA 變數以碼 3 表示「抗體篩檢陰性」[@hepc]；抗體陽性或不確定而無 RNA 者為未知。**2003–2004 年的公開檔沒有 HCV RNA 變數**，該週期抗體陽性者只能判為未知——前一版將他們一律判為陰性。

**糖尿病標籤**：自述曾被醫師診斷糖尿病（問卷 DIQ010＝1，題目已排除妊娠期間）或 HbA1c ≧ 6.5%[@a1c]。DIQ010＝2（否）或 3（邊緣）為問卷陰性，7（拒答）、9（不知道）或缺值為問卷未知；兩項組成任一陽性即陽性，兩項皆陰性才判陰性，其餘為未知。

兩個標籤各自判定、可同時成立，各軸只排除該軸未知者。

### 2.4　特徵

特徵為各週期共有的常規血液與尿液檢驗 62 項（含 ACR、eGFR、嗜中性球／淋巴球比、年齡、性別）。定義標籤的檢驗（HBsAg、HCV 抗體與 RNA、HbA1c、糖尿病問卷）一律不作特徵；前一版以變數字首封存，誤將血比容與同半胱胺酸一併排除，本版改為明列。各軸再移除生理上緊鄰標籤的「近端特徵」：肝炎軸移除 ALT、AST、GGT、總膽紅素（餘 58 項），糖尿病軸移除血糖與滲透壓（餘 60 項）。這些近端特徵在預測時合法可得，移除它們是更嚴格的消融，並不表示保留就是資料洩漏。

「常規套組」依可得性而非表現事先定義：全血球計數、標準生化、血脂、尿白蛋白與肌酸酐，加上衍生指標與年齡性別（肝炎軸 44 項、糖尿病軸 46 項）；鐵蛋白、葉酸、維生素 B12、同半胱胺酸、甲基丙二酸、維生素 D、副甲狀腺素、骨鹼性磷酸酶、可丁尼、血中金屬與 CRP 不屬常規套組。

### 2.5　部署模型與巢狀評估

部署模型為中位數插補、標準化與類別平衡權重邏輯迴歸，以五折交叉配適得到五個模型並平均其機率，再以保序迴歸校準；校準器只用訓練資料之內層折外分數配適。評估採分層五折、重複五次（隨機種子 20260926）：每一外層折都在外層訓練資料內重新完成插補、標準化、集成、校準與門檻計算，外層受試者只用於評估；每次重複中每人恰有一個外層預測。指標逐次重複計算後取平均並列出最小至最大；95% 信賴區間取第一次重複之受試者層重抽 1,000 次，不含重新配適的變異。

判別以 AUROC 與平均精確率（AP，scikit-learn `average_precision_score` 之不內插階梯和[@ap]）並列該軸盛行率；肝炎軸盛行率低，以 AP 為主要判別摘要。校準報告校準截距（以預測機率之 logit 為 offset）、校準斜率、Brier 分數與相對僅用盛行率之 Brier skill[@vancalster]。逐人外層預測存於 `results/v3_oof.csv.gz`，可重算所有指標。

### 2.6　三段分區

輸出分為「傾向」「不確定」「不傾向」。前一版規則為預測機率 ≧ 2 倍盛行率為傾向、≦ 0.5 倍為不傾向；此規則在盛行率超過 50% 時無法達成，且兩軸代表的證據強度不同。本版在看到結果之前改為**勝算倍數**：預測勝算 ≧ 事前勝算 2 倍為傾向、≦ 0.5 倍為不傾向，相當於概似比 2 與 0.5；低盛行率時與舊規則幾乎相同。兩規則皆報告六格表（實際陽性／陰性 × 三區）、涵蓋率與各區實際陽性率。常規套組有值不足一半者標示「資料不足」，不給分區；超出開發資料範圍的輸入值另行標示。

### 2.7　同切分比較、時間、權重與標籤敏感度

在與部署模型相同的外層切分上比較：僅截距、僅年齡性別、常規套組、全特徵邏輯迴歸（單一模型）與全特徵梯度提升（深度 3、學習率 0.08、300 回合、L2 1.0）。與全特徵邏輯迴歸之差以同一批受試者重抽估計配對信賴區間。近端特徵消融亦以同一切分比較。

時間外推以 1999–2008 年開發、2009–2018 年評估，並以擴展視窗逐週期評估（每週期只用更早週期訓練）；較晚週期先前已被檢視，屬回溯時間評估。調查權重以合併 20 年 MEC 權重（1999–2002 年四年權重 × 4/20，其後兩年權重 × 2/20）[@weight] 計算加權盛行率、平均預測、AUROC 與 AP。設計變異依抽樣設計的分層（SDMVSTRA，各週期編號互不重複）與 PSU（SDMVPSU）估計：以刪一 PSU 摺刀法建立複製權重[@rustrao]，複製權重依全樣本設計建立，分析範圍以指示變數處理；比例之 95% CI 採 NCHS 比例呈現標準之 Korn–Graubard 法[@parker]，其他指標為估計值 ± t × 標準誤，自由度為分析範圍內 PSU 數減層數；加權盛行率另以泰勒線性化核對。此計畫於計算前提交（{DV_COMMITS['plan']}）；預測視為固定，不含模型重新配適的變異。標籤定義敏感度分別以僅 HBsAg、僅 HCV RNA、僅糖尿病問卷、僅 HbA1c、排除邊緣回答重跑。

### 2.8　決策曲線與每千人情境

決策曲線以淨效益 NB ＝ TP/N − FP/N × pt/(1 − pt) 比較「依模型送驗」「全數送驗」「全不送驗」[@vickers]。閾值機率 pt 應反映實際檢驗的利弊；肝炎檢驗便宜、無創，且美國建議成人至少篩檢一次 C 型肝炎[@hcvscreen] 與 B 型肝炎[@hbv]，相當於極低的 pt。每千人情境直接取外層預測之分區結果，不再使用前一版的開發集作業點假設。

### 2.9　暴露關聯（探索性）

以全體成人（不對腎臟結果條件化）掃描 {X['n_scanned']} 個暴露與三值腎臟結果之關聯。五層調整為 M0 未調整；M1 年齡、性別、種族；M2 再加 BMI 與吸菸；M3 再加糖尿病與高血壓；M4（僅藥物）再加總用藥數。多重比較的檢定家族定義為 M3 之 {X['n_scanned']} 個雙尾 p 值，以 Benjamini–Hochberg 法控制偽發現率[@bh]；其他層級只作敏感度。0/1 藥物暴露報告「使用 vs 未使用」之勝算比（前一版誤將其標準化為每 SD），連續暴露為每 1 SD。

前一版比較血中與尿中金屬時，血中值只來自 1999–2004 年、尿中值只來自 2005–2018 年，兩者沒有任何共同受試者（合併時欄位撞名，2005 年後的血中值被忽略）。本版修正合併，並在同時有血、尿值的同一批受試者中，以相同 M3 調整、log2 量尺（勝算比為濃度加倍），比較血中、尿中原濃度、原濃度加尿肌酸酐共變數[@barr]、肌酸酐比值四種寫法，對三種結果定義：腎臟指標異常、僅 eGFR < 60（與尿肌酸酐無共同分母）、僅 ACR ≧ 30。

### 2.10　外部確認協定

NHANES 2021–2023 年（週期 L）於 2024 年釋出，從未參與本研究任何決策。本版在取用前凍結三個模型（部署之全特徵邏輯迴歸、常規套組邏輯迴歸、全特徵梯度提升）與評估規則，記錄其 SHA256 與 17 個待取用檔案（約 {PR['total_bytes'] / 1e6:.1f} MB）；程式只允許評估一次，且不重新配適、不重新校準、不調整門檻（`params/external_validation_protocol.json`，提交 9ca4e9f）。

經使用者同意，17 個檔案於 2026 年 9 月 27 日取用，大小與凍結紀錄一致。取用後、計算任何預測之前，逐檔核對 CDC 文件發現：生化儀器由 Cobas 6000 換為 Cobas 8000[@biopro_l]；尿白蛋白由螢光免疫法改為液相層析串聯質譜[@albcr_l]；空腹三酸甘油酯改為非甘油空白法並更名[@trigly_l]；維生素 D 亦更名。凍結時只核對了血清與尿肌酸酐（兩者官方皆不需轉換）。若照凍結程式原樣執行，兩個更名的特徵會整欄以中位數補入，尿白蛋白（因此 ACR 與腎臟標籤）與十餘項生化值也不在開發時的量尺上。

因此於評估前提交修正一（`params/external_validation_amendment_1.json`，提交 {EXT_COMMITS['amend']}）。規則是：凡 CDC 文件建議用於與 2017–2020 年比較的回推式，對模型或標籤用到的變數一律套用（{len(XAM['conversions'])} 項，補充表 S3）；儀器計算的滲透壓、Friedewald LDL 與 ACR 由調整後的組成重算；同一分析物更名者對應回原名；其餘不動。肌酸酐、尿肌酸酐、HbA1c、總膽固醇、HDL、全血球計數與肝炎血清學，CDC 皆判定不需調整；血中金屬的方法有變但未提供換算式，依凍結協定使用原值。模型、校準、門檻與指標皆不變。評估前的資料核對只含標籤計數與特徵分布（`results/external_2021_2023_precheck.json`），評估程式先在開發資料上測試可執行。依凍結程式原樣、不調和的結果列為事前指定的敏感度分析。

## 3　結果

### 3.1　資料更正與分析樣本

{{FIG1}}

**圖1　分析樣本與三值標籤。** 兩個標籤在腎臟指標異常者中各自判定；底部為與原稿相比的資料更正。

依舊定義重建之計數與原稿完全一致（成人 {n(old['n_adults'])}、可判定 {n(old['outcome_known_old_rule'])}、腎臟異常 {n(old['kidney'])}、肝炎 {old['hep']}、糖尿病 {n(old['dm'])}），確認比較基準正確。更正後：

**表1　資料更正前後的樣本與標籤**

| 項目 | 原稿（v2） | 本版（v3） | 說明 |
|---|---|---|---|
| 成人 | {n(old['n_adults'])} | {n(old['n_adults'])} | — |
| 腎臟結果可判定 | {n(old['outcome_known_old_rule'])} | {n(kd_known)} | 一項正常另一項缺失之 {n(T['kidney_unknown_one_normal_one_missing'])} 人改列未知 |
| 腎臟指標異常 | {n(old['kidney'])} | {n(T['kidney']['pos'])} | 新增 {R['combined']['gained']}、移出 {R['combined']['lost']} |
| 1999–2000 年 eGFR < 60 | {R['scr_fix_1999_2000']['egfr_lt60_old']} | {R['scr_fix_1999_2000']['egfr_lt60_new']} | 血清肌酸酐公式更正 |
| ACR 跨越 30 mg/g | — | 增 {R['ucr_fix_pre2007']['acr_cross30_up']}、減 {R['ucr_fix_pre2007']['acr_cross30_down']} | 2007 年前尿肌酸酐轉換 |
| 肝炎標籤 陽／陰／未知 | {old['hep']}／{n(old['kidney'] - old['hep'])}／— | {T['hep_in_kidney']['pos']}／{n(T['hep_in_kidney']['neg'])}／{T['hep_in_kidney']['unknown']} | HBsAg 陽性 {T['hbv_in_kidney']['pos']}、HCV RNA 陽性 {T['hcv_in_kidney']['pos']}（兩者皆陽 {T['both_hbv_and_hcv']}） |
| 糖尿病標籤 陽／陰／未知 | {n(old['dm'])}／{n(old['kidney'] - old['dm'])}／— | {n(T['dm_in_kidney']['pos'])}／{n(T['dm_in_kidney']['neg'])}／{T['dm_in_kidney']['unknown']} | 問卷陽性 {n(T['dmq_in_kidney']['pos'])}、HbA1c 陽性 {n(T['dma_in_kidney']['pos'])} |
| 兩標籤皆陽性 | 70（推算） | {A['two_label_crosstab_in_kidney']['陽性']['陽性']}（實數） | — |

註：{n(T['kidney']['pos'])} ／ {n(kd_known)} ＝ {pct(T['kidney']['pos'] / kd_known, 2)} 為未加權樣本比例，不是人口盛行率。逐週期計數見補充表 S1。

### 3.2　判別力與同切分基準

{{FIG2}}

**圖2　判別力。** 點為五次重複平均，線為五次重複之最小至最大；(c) 為標籤定義敏感度。

**表2　兩軸判別力（巢狀外層評估）**

| 項目 | 肝炎病毒感染標籤 | 糖尿病標籤 |
|---|---|---|
| n（陽性；盛行率） | {H['n']}（{H['pos']}；{H['prev']}） | {D['n']}（{D['pos']}；{D['prev']}） |
| 部署工具 AUROC（95% CI） | **{H['auc']}**（{H['auc_ci']}） | **{D['auc']}**（{D['auc_ci']}） |
| 部署工具 AP（95% CI） | **{H['ap']}**（{H['ap_ci']}） | **{D['ap']}**（{D['ap_ci']}） |
| AP ÷ 盛行率 | {H['ap_lift']} | {D['ap_lift']} |
| 梯形 PR-AUC | {H['prauc']} | {D['prauc']} |
| 五次重複 AUROC 範圍 | {H['auc_rng']} | {D['auc_rng']} |
| 僅年齡、性別 AUROC／AP | {H['m1']}／{H['m1ap']} | {D['m1']}／{D['m1ap']} |
| 常規套組 LR AUROC／AP | {H['m2']}／{H['m2ap']} | {D['m2']}／{D['m2ap']} |
| 全特徵 LR（單一模型）AUROC／AP | {H['m3']}／{H['m3ap']} | {D['m3']}／{D['m3ap']} |
| 全特徵梯度提升 AUROC／AP | {H['m4']}／{H['m4ap']} | {D['m4']}／{D['m4ap']} |
| 常規套組 − 全特徵 LR：ΔAUROC（95% CI） | {H['d2']}（{H['d2ci']}） | {D['d2']}（{D['d2ci']}） |
| 常規套組 − 全特徵 LR：ΔAP（95% CI） | {H['d2ap']}（{H['d2apci']}） | {D['d2ap']}（{D['d2apci']}） |
| 梯度提升 − 全特徵 LR：ΔAUROC（95% CI） | {H['d4']}（{H['d4ci']}） | {D['d4']}（{D['d4ci']}） |
| 梯度提升 − 全特徵 LR：ΔAP（95% CI） | {H['d4ap']}（{H['d4apci']}） | {D['d4ap']}（{D['d4apci']}） |

註：差值由未四捨五入之值計算，配對信賴區間為同一批受試者重抽，不含重新配適變異。

兩軸的判別力都主要來自檢驗而非人口學：只用年齡與性別時 AUROC 僅 {H['m1']} 與 {D['m1']}。肝炎軸以常規套組即可達到全特徵的判別力（ΔAUROC {H['d2']}，95% CI {H['d2ci']}），AP 甚至略高；梯度提升沒有優勢。糖尿病軸則相反：梯度提升明顯高於邏輯迴歸（ΔAUROC {D['d4']}，{D['d4ci']}），顯示線性模型未能捕捉糖尿病訊號的非線性結構。前一版將糖尿病比較模型 0.816 與原型 0.763 並列，兩者同時更換了模型與分析人群；本版在同一樣本上顯示差距主要來自模型。

近端特徵消融（邏輯迴歸，同一切分）：肝炎軸移除{H['ab_removed']}後，AUROC 由 {H['ab_with']} 降為 {H['ab_without']}（差 {H['ab_d'][1:]}，95% CI {H['ab_ci']}）；糖尿病軸移除{D['ab_removed']}後，由 {D['ab_with']} 降為 {D['ab_without']}（差 {D['ab_d'][1:]}，{D['ab_ci']}）。這些差值表示模型依賴被移除的資訊，不代表先前較高的分數是洩漏。

**標籤定義敏感度。** 僅以 HCV RNA 為標籤時（陽性 {hcv['n_pos']} 人）AUROC {p3(hcv['auroc'])}、AP {p3(hcv['ap'])}；僅以 HBsAg 為標籤時（陽性 {hbv['n_pos']} 人）AUROC {p3(hbv['auroc'])}、AP {p3(hbv['ap'])}，AP 與盛行率 {pct(hbv['prevalence'], 2)} 幾乎相同。**肝炎軸的訊號幾乎全部來自 C 型肝炎。** 糖尿病軸對標籤定義不敏感：僅問卷 {p3(dmq['auroc'])}、僅 HbA1c {p3(dma['auroc'])}、排除邊緣回答 {p3(dmb['auroc'])}。

### 3.3　校準與三段分區

{{FIG3}}

**圖3　校準與分區。** 校準曲線以分位數分箱；右欄比較兩種分區規則之各區實際陽性比例。

兩軸校準良好：肝炎軸校準截距 {H['cint']}、斜率 {H['cslope']}、Brier {H['brier']}（skill {H['bss']}）；糖尿病軸截距 {D['cint']}、斜率 {D['cslope']}、Brier {D['brier']}（skill {D['bss']}）。肝炎軸 Brier skill 很低，反映低盛行率下個別機率的區辨仍有限。

**表3　肝炎病毒感染標籤之六格表（勝算規則；第一次重複之外層預測）**

{six_table(H)}

**表4　糖尿病標籤之六格表（勝算規則）**

{six_table(D)}

肝炎軸兩規則幾乎相同（涵蓋率 {H['covA']} 與 {H['covB']}），落在「不傾向」區的陽性 {H['lowposB']} 人，占全部陽性 {H['mshare']}。糖尿病軸改用勝算規則後涵蓋率由 {D['covA']} 升至 {D['covB']}；代價是作答者特異度由 {D['specA']} 降至 {D['specB']}、落在不傾向區的陽性由 {D['lowposA']} 增至 {D['lowposB']} 人。常規套組有值不足一半而標示資料不足者，肝炎軸 {H['insuff']} 人、糖尿病軸 {D['insuff']} 人。以全體開發資料重新訓練之部署門檻：肝炎軸傾向 ≧ {H['thrB'][0]}、不傾向 ≦ {H['thrB'][1]}；糖尿病軸傾向 ≧ {D['thrB'][0]}、不傾向 ≦ {D['thrB'][1]}。

### 3.4　回溯時間評估與調查權重

{{FIG4}}

**圖4　回溯時間評估。** 每一評估週期只用更早的週期訓練；虛線為巢狀外層評估值。

以 1999–2008 年開發、2009–2018 年評估，肝炎軸 AUROC {H['tl']}（95% CI {H['tl_ci']}；n {H['tl_n']}、陽性 {H['tl_pos']}），AP {H['tl_ap']}；糖尿病軸 {D['tl']}（{D['tl_ci']}），AP {D['tl_ap']}。兩軸都略低於巢狀外層估計。盛行率隨年代上升（肝炎 {H['tl_ptr']} → {H['tl_pte']}，糖尿病 {D['tl_ptr']} → {D['tl_pte']}），使較晚週期的平均預測偏低（校準截距 {H['tl_cint']} 與 {D['tl_cint']}）。擴展視窗中，肝炎軸逐週期 AUROC 由 {H['ew_min']}（{H['ew_min_c']}）到 {H['ew_max']}（{H['ew_max_c']}），單一週期陽性僅 15–29 人，區間很寬；糖尿病軸 {D['ew_min']}–{D['ew_max']}，相當穩定。

以 MEC 權重加權，並依抽樣設計估計變異（{DV['design']['internal']['strata']} 層、{DV['design']['internal']['psu']} 個 PSU，自由度 {DH['df']}）：肝炎軸加權盛行率 {DH['prev']}（95% CI {DH['prev_ci']}；未加權 {DH['uw_prev']}；設計效應 {DH['deff']}），加權 AUROC {DH['auc']}（{DH['auc_ci']}），AP {DH['ap']}（{DH['ap_ci']}）；糖尿病軸加權盛行率 {DD['prev']}（{DD['prev_ci']}；未加權 {DD['uw_prev']}；設計效應 {DD['deff']}），加權 AUROC {DD['auc']}（{DD['auc_ci']}），AP {DD['ap']}（{DD['ap_ci']}）。糖尿病軸的加權平均預測高於加權盛行率 {DD['cd']} 個百分點（95% CI {DD['cd_ci']}），區間不含 0，顯示機率不能直接移植到抽樣組成不同的人群；肝炎軸的加權校準差為 {DH['cd']} 個百分點（{DH['cd_ci']}），區間包含 0。肝炎軸加權 AUROC 的設計區間（{DH['auc_ci']}）比未加權之受試者層重抽區間（{H['auc_ci']}）寬，反映抽樣設計的叢集與權重不均。加權盛行率之摺刀法與泰勒線性化標準誤相差不到 {max_se_gap:.2f}%。

### 3.5　決策曲線與每千人情境

{{FIG5}}

**圖5　決策曲線。** 閾值機率須由實際檢驗之利弊決定。

肝炎軸在 pt ＝ 0.5% 時，依模型送驗與全數送驗的淨效益幾乎相同（{dca_row(H, 0.005)}）；pt 為 1% 以上模型才較高（{dca_row(H, 0.01)}）。由於肝炎血清檢驗便宜、無創，且指引建議成人普遍篩檢[@hbv,hcvscreen]，合理的 pt 很低，**本工具不宜用來決定誰可以不驗肝炎**。若只略過「不傾向」區，每千人送驗 {H['t1000']} 人、漏掉 {H['m1000']} 名陽性（占陽性 {H['mshare']}）。糖尿病軸在 pt ≧ 15% 起淨效益高於全數送驗（{dca_row(D, 0.15)}）；若只略過不傾向區，每千人送驗 {D['t1000']} 人、漏 {D['m1000']} 名陽性（占 {D['mshare']}）。這些數字取自外層預測，不再使用前一版開發集作業點的假設換算。

### 3.6　暴露關聯（探索性）

更正後結果可判定之成人 {n(X['cohort']['n_outcome_known'])} 人、腎臟指標異常 {n(X['cohort']['n_kidney_damage'])} 人。{X['n_scanned']} 個暴露中 {X['n_significant_fdr05']} 個於 M3 通過偽發現率 0.05；陽性對照命中 {len(X['control_check']['positive_hits'])}/{X['control_check']['n_positive_scanned']}（鈣調磷酸酶抑制劑、質子幫浦抑制劑），陰性對照 {len(X['control_check']['negative_hits'])}/{X['control_check']['n_negative_scanned']}；砷的毒性形式與砷貝他因皆未達顯著。前一版被判讀為「保護」的毒性砷，在更正結果變項後已不顯著。

**表5　偽發現率最低的 12 項暴露（M3）**

{sig_table()}

藥物關聯與處方常規一致：用於腎病或其共病的藥（利尿劑、胰島素、別嘌醇、ACEI／ARB）與腎臟異常正相關，腎功能差時應停用的雙胍類呈負相關（OR {xo('藥_雙胍')['OR']:.3f}）；教科書腎毒物 NSAID 不顯著（OR {xo('藥_NSAID')['OR']:.3f}，q ＝ {Xr['藥_NSAID']['q_bh']:.2f}）。這些方向可由適應症混雜與反向因果解釋，不能作為藥物致病或護腎的證據。

{{FIG6}}

**圖6　同一批受試者之血中與尿中鉛、鎘。** 勝算比為濃度加倍，M3 調整。

**表6　同一批受試者（n ＝ {n(Pb['n_both'])}）之血中與尿中金屬（OR 為濃度加倍，95% CI）**

| 金屬／量測 | 腎臟指標異常 | 僅 eGFR < 60 | 僅 ACR ≧ 30 |
|---|---|---|---|
| 鉛：血中 | {orr(mo(Pb, 'kidney_damage', '血中'))} | {orr(mo(Pb, 'egfr_lt60', '血中'))} | {orr(mo(Pb, 'acr_ge30', '血中'))} |
| 鉛：尿中原濃度 | {orr(mo(Pb, 'kidney_damage', '尿中_原濃度'))} | {orr(mo(Pb, 'egfr_lt60', '尿中_原濃度'))} | {orr(mo(Pb, 'acr_ge30', '尿中_原濃度'))} |
| 鉛：尿中＋尿肌酸酐共變數 | {orr(mo(Pb, 'kidney_damage', '尿中_原濃度＋尿肌酸酐共變數'))} | {orr(mo(Pb, 'egfr_lt60', '尿中_原濃度＋尿肌酸酐共變數'))} | {orr(mo(Pb, 'acr_ge30', '尿中_原濃度＋尿肌酸酐共變數'))} |
| 鉛：尿中肌酸酐比值 | {orr(mo(Pb, 'kidney_damage', '尿中_肌酸酐比值'))} | {orr(mo(Pb, 'egfr_lt60', '尿中_肌酸酐比值'))} | {orr(mo(Pb, 'acr_ge30', '尿中_肌酸酐比值'))} |
| 鎘：血中 | {orr(mo(Cd, 'kidney_damage', '血中'))} | {orr(mo(Cd, 'egfr_lt60', '血中'))} | {orr(mo(Cd, 'acr_ge30', '血中'))} |
| 鎘：尿中原濃度 | {orr(mo(Cd, 'kidney_damage', '尿中_原濃度'))} | {orr(mo(Cd, 'egfr_lt60', '尿中_原濃度'))} | {orr(mo(Cd, 'acr_ge30', '尿中_原濃度'))} |
| 鎘：尿中＋尿肌酸酐共變數 | {orr(mo(Cd, 'kidney_damage', '尿中_原濃度＋尿肌酸酐共變數'))} | {orr(mo(Cd, 'egfr_lt60', '尿中_原濃度＋尿肌酸酐共變數'))} | {orr(mo(Cd, 'acr_ge30', '尿中_原濃度＋尿肌酸酐共變數'))} |
| 鎘：尿中肌酸酐比值 | {orr(mo(Cd, 'kidney_damage', '尿中_肌酸酐比值'))} | {orr(mo(Cd, 'egfr_lt60', '尿中_肌酸酐比值'))} | {orr(mo(Cd, 'acr_ge30', '尿中_肌酸酐比值'))} |

註：低於檢出極限比例，血鉛 {pct(Pb['below_lod_share']['LBDBPBLC'], 2)}、尿鉛 {pct(Pb['below_lod_share']['URDUPBLC'], 1)}、血鎘 {pct(Cd['below_lod_share']['LBDBCDLC'], 1)}、尿鎘 {pct(Cd['below_lod_share']['URDUCDLC'], 1)}；NHANES 以檢出極限除以 √2 填補，本表未另作處理。

在同一批人中，血鉛與血鎘對三種結果定義都呈正相關；尿中金屬的方向則取決於結果定義與寫法。對與尿肌酸酐無共同分母的 eGFR < 60，尿鉛原濃度即呈負相關（{orr(mo(Pb, 'egfr_lt60', '尿中_原濃度'))}），加入尿肌酸酐後更明顯——與「腎絲球過濾下降使尿中排出減少」相符。對 ACR ≧ 30，肌酸酐比值寫法的尿鎘明顯高於原濃度（{orr(mo(Cd, 'acr_ge30', '尿中_肌酸酐比值'))} vs {orr(mo(Cd, 'acr_ge30', '尿中_原濃度'))}），部分來自與 ACR 共用的尿肌酸酐分母。這些模式支持排泄與分母機制值得檢查，但單次橫斷面資料不能排除真實暴露效應、殘餘混雜或測量誤差，也不能把 {X['n_significant_fdr05']} 個關聯一律歸為反向因果。

### 3.7　外部確認（NHANES 2021–2023）

{{FIG7}}

**圖7　外部確認。** (a) 內部（巢狀外層）與外部 AUROC；(b) 部署模型三段分區之實際陽性比例，外部標註陽性數／該區人數。

2021–2023 年成人中，腎臟指標異常 {n(XK['pos'])} 人（依凍結程式原樣為 {n(SK['pos'])} 人，差異來自尿白蛋白回推），無法判定 {n(XK['unknown'])} 人。肝炎軸可判定 {XH['n']} 人、陽性 {XH['pos']} 人（HBsAg 陽性 {HC['hbsag_pos']}、HCV RNA 陽性 {HC['hcv_rna_pos']}）；糖尿病軸可判定 {XD['n']} 人、陽性 {XD['pos']} 人。

**表7　外部確認結果（主要分析：修正一調和後）**

| 項目 | 肝炎病毒感染標籤 | 糖尿病標籤 |
|---|---|---|
| n（陽性；盛行率） | {XH['n']}（{XH['pos']}；{XH['prev']}） | {XD['n']}（{XD['pos']}；{XD['prev']}） |
| 部署模型 AUROC（95% CI） | **{XH['auc']}**（{XH['auc_ci']}） | **{XD['auc']}**（{XD['auc_ci']}） |
| 內部參考 AUROC（巢狀外層） | {H['auc']} | {D['auc']} |
| 部署模型 AP（95% CI） | {XH['ap']}（{XH['ap_ci']}） | {XD['ap']}（{XD['ap_ci']}） |
| AP ÷ 盛行率 | {XH['ap_lift']} | {XD['ap_lift']} |
| 校準截距／斜率 | {XH['cint']}／{XH['cslope']} | {XD['cint']}／{XD['cslope']} |
| 平均預測／實際陽性比例 | {XH['meanpred']}／{XH['obs']} | {XD['meanpred']}／{XD['obs']} |
| Brier（skill） | {XH['brier']}（{XH['bss']}） | {XD['brier']}（{XD['bss']}） |
| 涵蓋率（勝算規則；舊規則） | {XH['covB']}；{XH['covA']} | {XD['covB']}；{XD['covA']} |
| 各區實際陽性率：傾向／不確定／不傾向 | {XH['rates']} | {XD['rates']} |
| 資料不足 | {XH['insuff']} | {XD['insuff']} |
| 常規套組 LR AUROC（95% CI） | {XH['bauc']}（{XH['bauc_ci']}） | {XD['bauc']}（{XD['bauc_ci']}） |
| 常規套組 − 部署：ΔAUROC（配對 95% CI） | {XH['dbf']}（{XH['dbf_ci']}） | {XD['dbf']}（{XD['dbf_ci']}） |
| 常規套組 LR 校準截距／斜率 | {XH['bcint']}／{XH['bcslope']} | {XD['bcint']}／{XD['bcslope']} |
| 全特徵梯度提升 AUROC／AP | {XH['gauc']}／{XH['gap']} | {XD['gauc']}／{XD['gap']} |
| MEC 加權盛行率（Korn–Graubard 95% CI） | {XDH['prev']}（{XDH['prev_ci']}） | {XDD['prev']}（{XDD['prev_ci']}） |
| MEC 加權 AUROC（設計 95% CI） | {XDH['auc']}（{XDH['auc_ci']}） | {XDD['auc']}（{XDD['auc_ci']}） |
| MEC 加權校準差，百分點（設計 95% CI） | {XDH['cd']}（{XDH['cd_ci']}） | {XDD['cd']}（{XDD['cd_ci']}） |
| 敏感度：依凍結程式原樣 AUROC（95% CI） | {SH['auc']}（{SH['auc_ci']}） | {SD['auc']}（{SD['auc_ci']}） |
| 敏感度：依凍結程式原樣 校準截距／斜率 | {SH['cint']}／{SH['cslope']} | {SD['cint']}／{SD['cslope']} |

註：梯度提升依協定只評判別；差值由未四捨五入之值計算，配對信賴區間為同一批受試者重抽 1,000 次。加權指標之信賴區間依 2021–2023 年抽樣設計（{DV['design']['external']['strata']} 層、{DV['design']['external']['psu']} 個 PSU，自由度 {XDH['df']}）以刪一 PSU 摺刀法估計，於一次性評估之後補算，預測與評估時相同。

**糖尿病軸**　部署模型 AUROC {XD['auc']}（{XD['auc_ci']}），略低於內部估計 {D['auc']}，但內部估計仍在外部區間內；各區實際陽性率（{XD['rates']}）與內部相近，涵蓋率 {XD['covB']}。平均預測 {XD['meanpred']} 低於實際 {XD['obs']}（校準截距 {XD['cint']}、斜率 {XD['cslope']}），與回溯時間評估中盛行率上升造成的低估方向一致（3.4）。常規套組模型 AUROC {XD['bauc']}，比部署模型高 {XD['dbf'][1:]}（配對 95% CI {XD['dbf_ci']}）；梯度提升 {XD['gauc']}，非線性的優勢在新資料上仍然存在。

**肝炎軸**　陽性只有 {XH['pos']} 人，遠低於外部驗證建議的至少 100 個事件[@collins_ev]；AUROC {XH['auc']} 的 95% CI 為 {XH['auc_ci']}，既不能確認也不能否定內部估計 {H['auc']}。平均預測 {XH['meanpred']} 是實際 {XH['obs']} 的 {XH['ratio_pred']} 倍（校準截距 {XH['cint']}、斜率 {XH['cslope']}），Brier skill 為負值（{XH['bss']}），未經重新校準的機率不應使用。陽性組成也改變了：HCV RNA 陽性占肝炎軸可判定者的比例，開發資料為 {pct(T['hcv_in_kidney']['pos'] / E['肝炎']['tool']['n'], 2)}，2021–2023 年只有 {pct(HC['hcv_rna_pos'] / XV['primary']['axes']['肝炎']['n'], 2)}；HBsAg 陽性則為 {pct(T['hbv_in_kidney']['pos'] / E['肝炎']['tool']['n'], 2)} 與 {pct(HC['hbsag_pos'] / XV['primary']['axes']['肝炎']['n'], 2)}。本工具的訊號幾乎全部來自 C 型肝炎（3.2），陽性組成偏向 B 型肝炎會直接壓低判別力。不傾向區 {XH['low_n']} 人中沒有陽性，但以 {XH['pos']} 個事件無法據此推論漏失率。

**敏感度與事後探索**　依凍結程式原樣、不調和時，糖尿病軸 AUROC {SD['auc']}（{SD['auc_ci']}），校準截距 {SD['cint']}、斜率 {SD['cslope']}；肝炎軸 {SH['auc']}（{SH['auc_ci']}）。兩版的腎臟標籤與樣本不同（{n(SK['pos'])} 與 {n(XK['pos'])} 人），判別差異不大，但糖尿病軸的校準方向相反（原樣高估、調和後低估），顯示量尺調和主要影響機率的絕對值。以下為一次評估之後才進行的事後探索，不取代主要結果：部署模型含六項在開發資料中只有 1999–2004 年有值的非常規特徵（血鉛、血鎘、血汞、可丁尼、鐵蛋白、維生素 D），2021–2023 年腎臟指標異常者的中位數分別為開發時的 {xr('LBXBPB')}、{xr('LBXBCD')}、{xr('LBXTHG')}、{xr('LBXCOT')}、{xr('LBXFER')}、{xr('LBDVIDMS')} 倍。把這六項改為缺值（即開發資料中 2005–2018 年受試者的處理方式）後，糖尿病軸 AUROC 由 {ph(PHD)}，與常規套組模型相當；肝炎軸由 {ph(PHH)}。這支持一個解釋：開發資料中覆蓋不全、又隨年代大幅變動的特徵，在新資料上會拖累判別。

## 4　討論

### 4.1　主要發現

常規檢驗能辨識兩個候選病因的共存標籤，程度中等且校準良好：肝炎軸 AUROC {H['auc']}、AP 為盛行率的 {H['ap_lift']} 倍；糖尿病軸 AUROC {D['auc']}。三項結果改變了對這個工具的理解。第一，肝炎軸實際上是 C 型肝炎軸：B 型肝炎表面抗原陽性者幾乎無法由常規檢驗辨識（AUROC {p3(hbv['auroc'])}），可能因多數慢性 B 型肝炎帶原者肝功能與血液檢驗接近正常（單變量掃描 {MK['僅B肝']['n_markers']} 個標記僅 {MK['僅B肝']['n_fdr05']} 個通過偽發現率校正）。C 型肝炎標籤者的型態則一致：球蛋白較高（單變量 AUROC {mk('僅C肝', 'LBXSGB')}）、白蛋白較低（{mk('僅C肝', 'LBXSAL')}）、血小板與總膽固醇較低（{mk_all('LBXPLTSI')}、{mk_all('LBXSCH')}），與慢性病毒性肝炎之血脂研究方向一致[@bashir]；可丁尼亦較高（{mk('僅C肝', 'LBXCOT')}，僅 {mk_n('LBXCOT')} 名陽性有值），提示部分訊號來自與感染風險相關的吸菸暴露，而不只是肝臟生理。第二，糖尿病軸的線性模型不足，梯度提升的優勢在同一樣本上重現，下一版應考慮非線性模型或加入交互項。第三，精簡為常規套組並未降低肝炎軸判別力，對實際使用有利；在外部資料上，常規套組模型兩軸皆不低於部署模型，糖尿病軸更高（3.7）。

外部確認的結果分成兩半。糖尿病軸在從未參與開發的 2021–2023 年資料上維持中等判別力，三段分區的實際陽性率也與內部相近，可視為初步確認。肝炎軸則因事件太少而無法確認，機率明顯高估，陽性組成也由以 C 型肝炎為主轉為 B、C 型各半；在以 C 型肝炎訊號為主的工具上，這個轉變本身就會降低判別力。

### 4.2　與前一版的差異

本版修正了三類審查者無法看見的錯誤：1999–2000 年血清肌酸酐公式錯用、2003–2004 年缺 HCV RNA 卻判陰性、暴露分析中血中金屬欄位撞名。這三項都能通過 SHA256 檢查，說明出處帳本只保證檔案未被更動，不保證分析正確——這正是審查意見的重點。修正後兩軸判別力與前一版相近（前一版原型 0.788／0.763，本版 {H['auc']}／{D['auc']}），但分區統計改由巢狀外層預測計算，校準器不再與評估共用同一批資料。前一版的「血尿方向相反＝反向因果直接證據」建立在沒有共同受試者的比較上，本版已撤回，改以同一批人的分析取代。

### 4.3　作為病因線索的意義與界線

本研究的核心問題是「找原因」。現有資料能支持的結論是：當常規檢驗呈現與 C 型肝炎或糖尿病相符的型態時，這組數值提供了「值得優先查證這兩個候選病因」的線索，而且這個線索附有可追溯的依據（推動因子）與經校準的機率。它不能回答腎損傷是否由該病造成；免疫性病因在 NHANES 缺乏補體、自體抗體與病理，仍無法評估[@yang]。在臨床行動上，肝炎檢驗應依普遍篩檢建議進行，本工具的角色是解釋與排序，而不是省略檢驗。

### 4.4　研究限制

1. 標籤為共存疾病的操作型定義，不是腎臟病理；單次檢驗不確認慢性性[@kdigo]。
2. 1999–2018 年資料已在前一版反覆使用，本版為探索性重分析；保留集曾被評估兩次，本版不再宣稱一次性確認集（詳見版本紀錄）。確認性證據改由 2021–2023 年外部資料提供（3.7）。
3. 肝炎陽性僅 {H['pos']} 人，逐週期評估的區間很寬；穩定性取決於事件數與候選參數，而非總樣本數[@riley]。外部確認只有 {XH['pos']} 個事件，肝炎軸的外部表現仍未確認。
4. 設計變異已依 PSU 與分層估計，但預測視為固定，不含模型重新配適的變異；2021–2023 年依協定使用 MEC 權重，未使用 NCHS 為抽血項目另設的抽血權重。美國調查的機率不能直接移植至臺灣就醫族群。
5. 預測特徵中的血中金屬只來自 1999–2004 年檢驗檔，2015 年後的高敏感度 CRP 未與舊 CRP 合併，這些特徵在其他週期以中位數補入；事後探索顯示這類特徵在新資料上會拖累判別（3.7）。另外，開發時 HDL 膽固醇因肝炎 D 抗體的變數字首規則被一併排除於特徵之外，屬過度排除、不造成洩漏，將於下一版修正。
6. 暴露分析為單次橫斷面，無法建立時序。
7. 外部資料的檢驗儀器與方法已變更，本研究於評估前以 CDC 官方回推式調和；回推式本身有估計誤差，且血中金屬與可丁尼沒有官方換算式。

### 4.5　下一步

1. **部署改用常規套組模型並重新校準**：外部資料顯示常規套組模型兩軸皆不低於全特徵模型，肝炎軸在新資料上高估約 {XH['ratio_pred']} 倍。已於 2026-09-27 完成（網頁工具 v3.1，`params/direction_model_v3_1.json`）：依由簡到繁的更新原則[@vergouwe]，肝炎軸只有 {RC['肝炎']['n_pos']} 個事件，只更新截距（{num(RC['肝炎']['recalibration']['a'], 3)}）；糖尿病軸之斜率檢定 p ＝ {RC['糖尿病']['candidates']['slope_lr_test_p']:.3f}，更新截距與斜率（{num(RC['糖尿病']['recalibration']['a'], 3)}、{RC['糖尿病']['recalibration']['b']:.3f}）。事前機率改為 2021–2023 年之比例（肝炎 {pct(RC['肝炎']['after_apparent']['calibration']['observed'], 2)}、糖尿病 {pct(RC['糖尿病']['after_apparent']['calibration']['observed'])}），分區門檻依同一勝算規則重算。這批資料已用於更新，更新後的校準仍需另一批獨立資料驗證。
2. **糖尿病軸改用非線性模型**：梯度提升在外部資料上仍達 {XD['gauc']}；下一步評估其校準，並限制於常規套組特徵。
3. **肝炎軸的外部確認**：需要更多事件（例如合併之後的 NHANES 週期或醫院資料），並分開呈現 B 型與 C 型肝炎。
4. **病因研究**：取得具病理或臨床參考標準、診斷前檢驗與免疫檢驗之醫院資料，並處理只接受切片者的選擇偏差[@yang]。

## 5　結論

常規血液與尿液檢驗對腎臟指標異常成人中的 C 型肝炎相關肝炎標籤與糖尿病標籤，具有中等且校準良好的辨識力，可作為病因線索；對 B 型肝炎幾乎沒有訊號。在未參與開發的 2021–2023 年資料中，糖尿病軸維持中等判別力，只用常規套組的模型不輸全特徵模型；肝炎軸外部事件太少而無法確認，機率也須重新校準。這不等於病因診斷，也不支持用來省略肝炎篩檢。資料層級的錯誤已依官方文件更正，所有結果由同版結果檔生成。

---

## 研究聲明

**資料與程式可得性**　資料為 NHANES 公開檔，來源網址見 `params/manifest.json`，逐檔 SHA256 與位元組數見 `results/provenance.json`。程式與結果位於 https://github.com/CBL-AICM/MD.Piece （分支 claude/disease-trajectory-model-prompts-ad24d8，目錄 experiments/kidney_cause）：分析計畫 bf269c5、結果 d5140a9、外部確認協定 9ca4e9f、圖 397c204、外部確認修正一 {EXT_COMMITS['amend']}、外部確認結果 {EXT_COMMITS['results']}、設計變異計畫 {DV_COMMITS['plan']} 與結果 {DV_COMMITS['results']}。執行環境見 `requirements-lock.txt`（Python 3.14.3、scikit-learn 1.8.0、pandas 3.0.1、NumPy 2.4.3）。重現入口：`audit_v3.py` → `evaluate_v3.py` → `markers_v3.py` → `run_exwas.py` → `exwas_v3_checks.py` → `make_figures_v3.py` → `build_paper_v3.py`；外部確認為 `external_validation_2021.py`（`--precheck` → `--amend` → `--evaluate`，只允許評估一次），事後探索為 `external_posthoc_2021.py`；網頁工具 v3.1 之重新校準為 `recalibrate_v3_1.py`，網頁與 Python 之一致性以 `verify_direction_html.py` 檢查；設計變異為 `design_variance.py`。

**研究倫理**　本研究使用公開去識別化資料；次級分析之倫理審查或免審認定，須由作者依所屬機構規定補列，本文不預先宣稱。

**作者貢獻、資助與利益衝突**　須由作者確認後填列。

---

## 參考文獻

依首次引用順序編號；網路資料查閱日期 2026-09-26／27。

@@REFLIST@@

---

## 補充資料

### 表 S1　逐週期三值計數（腎臟為全體成人；兩標籤為腎臟指標異常者）

{per_cycle_table()}

### 表 S2　凍結之外部確認模型

| 模型 | 檔案 | SHA256（前 16 碼） |
|---|---|---|
""" + "\n".join(f"| {k} | `{v['path'].replace(chr(92), '/')}` | {v['sha256'][:16]} |" for k, v in fm.items()) + f"""

### 表 S3　外部確認修正一之官方回推式（2021–2023 年數值換回 2017–2020 年量尺）

{conv_table()}

註：另將 LBXTLG 對應為 LBXTR、LBXVIDMS 對應為 LBDVIDMS；滲透壓、Friedewald LDL 與 ACR 由調整後組成重算；回推值小於 0 者設為 0。修正一於評估前提交（{EXT_COMMITS['amend']}），檔案 SHA256 前 16 碼 {sha_amend[:16]}。

### 圖 S1　單一受試者輸出示範

{{FIGS1}}

**圖 S1　單一受試者輸出示範。** 僅展示工具的輸出形式；單例不代表準確率。推動因子為標準化值乘係數，共線特徵（如兩種總膽固醇）的貢獻可互相抵銷，不能逐項解讀為致病因子。

### 可重算之結果檔

`results/v3_audit.json`（稽核）、`results/v3_eval.json`（評估）、`results/v3_markers.json`（單變量標記）、`results/v3_oof.csv.gz`（逐人外層預測）、`results/exwas_v3.json`、`results/exwas_v3_checks.json`、`params/external_validation_amendment_1.json`（外部確認修正一）、`results/external_2021_2023_precheck.json`（評估前資料核對）、`results/external_2021_2023.json`（外部確認）、`results/external_2021_2023_posthoc.json`（事後探索）、`params/direction_model_v3_1.json` 與 `results/direction_v3_1_recalibration.json`（網頁工具 v3.1 及其更新校準之表面值）、`params/design_variance_plan.json` 與 `results/design_variance.json`（設計變異）、`docs/VERSION_LOG.md`（版本紀錄）。
"""

RESPONSE = f"""# 審查意見回應表（v3，2026-09-27）

> 對應《深度審查與補強方案》（2026-09-26）。審查者沒有取得資料與程式，將重分析列為「待執行」；本表逐項說明以真實資料執行的內容與結果。數字皆出自 `results/v3_*.json`、`results/exwas_v3*.json` 與 `results/external_2021_2023*.json`。
> 主稿：[[研究論文_v3重分析]]｜版本紀錄：`experiments/kidney_cause/docs/VERSION_LOG.md`

## 一、概念與主張（審查 §三）

| 審查意見 | 處理 | 結果或位置 |
|---|---|---|
| 病因和共病不可互換 | 標籤改稱「肝炎病毒感染／糖尿病共存標籤」；研究問題保留「找原因」，但界定為「病因線索」，結論不宣稱病因 | 論文題目、前言、4.3 |
| 單次異常與慢性疾病分開 | 改稱「單次腎臟指標異常」「分析樣本」 | 2.1、2.2、限制 1 |
| 切片與臨床效益不可預設 | 刪除減少切片之主張；以決策曲線與普遍篩檢比較 | 3.5：肝炎軸 pt ＝ 0.5% 時與全數送驗相同 |
| 資料出處不保證模型準確 | 改稱可追溯性與完整性檢查；並實際發現三項能通過 SHA256 的資料錯誤 | 2.1、4.2 |
| 資料洩漏與疾病訊號分開 | 改稱「近端特徵消融」，刪除「0.904 是虛假判別力」；改報同切分配對差 | 肝炎 {H['ab_with']}→{H['ab_without']}（{H['ab_ci']}）；糖尿病 {D['ab_with']}→{D['ab_without']}（{D['ab_ci']}） |
| 不顯著與無訊號分開 | 刪除「若軸不成立應無單標記通過 FDR」之必要推論；FDR 解讀改為控制錯誤發現比例 | 2.9 |

## 二、樣本分母與數字（審查 §四）

| 審查意見 | 處理 | 結果 |
|---|---|---|
| 3,289 是否涵蓋所有無法判定者 | 三值重建 | 未知 {n(T['kidney']['unknown'])} ＝ 一正常一缺 {n(T['kidney_unknown_one_normal_one_missing'])} ＋ 兩項皆缺 {n(T['kidney_unknown_both_missing'])}；可判定 {n(old['outcome_known_old_rule'])} → {n(kd_known)} |
| 17.34% 非人口盛行率 | 標明未加權；另報加權結果 | 3.1 註、3.4 |
| 標籤比例需排除未知 | 兩標籤三值 | 肝炎 {T['hep_in_kidney']['pos']}／{n(T['hep_in_kidney']['neg'])}／{T['hep_in_kidney']['unknown']}；糖尿病 {n(T['dm_in_kidney']['pos'])}／{n(T['dm_in_kidney']['neg'])}／{T['dm_in_kidney']['unknown']} |
| 共陽性 70 為條件推算 | 逐人交叉表 | 實數 {A['two_label_crosstab_in_kidney']['陽性']['陽性']}（舊定義重建為 70） |
| 0.816 與 0.763 不可相減 | 同一樣本、同一切分比較 | 糖尿病軸 LR {D['m3']} vs 梯度提升 {D['m4']}，差 {D['d4']}（{D['d4ci']}） |
| −0.002 與 −0.001、0.050 與 0.051 | 一律以未四捨五入值計算並附配對 CI | 表 2 |
| 0.904 與 0.913；圖四 0.087／0.088 | 0.913 為三週期早期版本，0.904 為十週期；舊圖四已刪除 | 版本紀錄第二節 |

## 三、圖表（審查 §五）

| 原稿 | 處理 |
|---|---|
| 圖一（世代、病因、未顯示未知） | 新圖 1：三值流程、各軸分析 n、交叉表、資料更正 |
| 圖二（混合三任務與工具；6.7／7.0） | 新圖 2：部署工具與同切分基準分開呈現；6.7 與 7.0 原為兩個不同任務（感染 vs 其餘、感染 vs 代謝），新圖只報絕對 AP |
| 圖二、圖四之「原始目標 0.90」 | 全部移除；0.90 之來源見版本紀錄第一節 |
| 圖三（反向因果直接證據） | 撤回；新圖 6 改為同一批 {n(Pb['n_both'])} 人之探索性比較 |
| 圖四（六項陷阱，表僅五項） | 刪除圖；改列版本紀錄之更正表，並刪除「每一次修正都使結果變差」 |
| 圖五（單例；糖尿病倍數超過 100%） | 圖 S1 改用概似比對數量尺（0.25–4 倍），不會超出機率範圍；標明僅展示 |
| 圖六（開發集作業點與保留集 AUROC 並列） | 刪除；每千人情境改由外層預測之分區結果計算 |

## 四、資料與標籤重跑規格（審查 §六）

| 審查意見 | 執行結果 |
|---|---|
| 每週期稽核表 | 表 S1；`results/v3_audit.json`（成人、SEQN 重複 0、肌酸酐與 ACR 可用數、三值計數、未知原因） |
| 四種缺失分開 | 三值規則；2003–2004 無 HCV RNA 屬「全週期未測」，列為未知 |
| 尿肌酸酐校正（優先項目） | 已依 ALB_CR_E 執行；ACR 跨 30 mg/g 增 {R['ucr_fix_pre2007']['acr_cross30_up']}、減 {R['ucr_fix_pre2007']['acr_cross30_down']}；跨 300 增 {R['ucr_fix_pre2007']['acr_cross300_up']}、減 {R['ucr_fix_pre2007']['acr_cross300_down']} |
| 血清肌酸酐校正核查 | **發現錯誤**：1999–2000 誤用 NHANES III 公式；更正後該週期 eGFR<60 由 {R['scr_fix_1999_2000']['egfr_lt60_old']} 增為 {R['scr_fix_1999_2000']['egfr_lt60_new']} 人 |
| HBV、HCV 分開 | 已分開；HBsAg 陽性 {T['hbv_in_kidney']['pos']}、HCV RNA 陽性 {T['hcv_in_kidney']['pos']}；僅 HBV AUROC {p3(hbv['auroc'])}、僅 HCV {p3(hcv['auroc'])} |
| 糖尿病問卷邊緣、拒答、不知道 | 邊緣歸問卷陰性並做排除敏感度（{p3(dmb['auroc'])}）；拒答／不知道為未知；問卷與 HbA1c 分別定義 {p3(dmq['auroc'])}／{p3(dma['auroc'])} |

## 五、模型評估（審查 §七）

| 審查意見 | 執行結果 |
|---|---|
| 分清探索與確認 | 1999–2018 重分析標為探索性；兩個保留集三次評估之日期與後續修改見版本紀錄；確認性評估改用 2021–2023 新資料，已一次評估（論文 3.7、表 7，本表第九節）：糖尿病軸 AUROC {XD['auc']}（{XD['auc_ci']}）；肝炎軸僅 {XH['pos']} 個事件，無法確認 |
| 全流程外層隔離 | 插補、標準化、集成、保序校準、門檻皆在外層訓練資料內完成（提交 bf269c5 之計畫） |
| 事件／特徵比 | 肝炎 {H['pos']} 事件對 58 特徵，約 {E['肝炎']['tool']['n_pos'] / 58:.1f}；已列限制，並顯示常規套組（44 項）不降判別 |
| 基準比較與配對差 | 僅截距、年齡性別、常規套組、全特徵 LR、梯度提升；配對 CI 見表 2 |
| 重複 CV 之彙整 | 每次重複每人一個外層預測，指標逐次計算後摘要；CI 取第一次重複並註明不含重新配適變異 |
| 向前時間驗證 | 1999–2008 → 2009–2018：肝炎 {H['tl']}（{H['tl_ci']}）、糖尿病 {D['tl']}（{D['tl_ci']}）；逐週期擴展視窗見圖 4 |
| 最低報告集 | 分母與陽性數、AUROC、絕對 AP（定義）、梯形 PR-AUC、校準截距與斜率、Brier、六格表、涵蓋率、全體漏失、每千人結果：表 2–4、圖 3、3.5 |

## 六、抽樣與暴露分析（審查 §八）

| 審查意見 | 執行結果 |
|---|---|
| 調查權重 | 20 年 MEC 權重（1999–2002 × 4/20、其後 × 2/20）；設計變異已依 {DV['design']['internal']['strata']} 層、{DV['design']['internal']['psu']} 個 PSU 以刪一 PSU 摺刀法估計（計畫 {DV_COMMITS['plan']} 先提交），比例採 Korn–Graubard 區間：肝炎軸加權 AUROC {DH['auc']}（{DH['auc_ci']}）、糖尿病軸 {DD['auc']}（{DD['auc_ci']}），糖尿病軸加權校準差 {DD['cd']} 個百分點（{DD['cd_ci']}）；外部 2021–2023 同法補算（表 7） |
| 五層調整之完整共變數 | M0–M4 已逐層列出（2.9） |
| 檢定家族 | M3 之 {X['n_scanned']} 個暴露共同校正；其他層級為敏感度，不跨層挑最小 p |
| 檢出極限、偏態、有效樣本、量尺 | 鉛、鎘列出低於檢出極限比例；改用 log2；藥物 OR 改為使用 vs 未使用 |
| 血尿非同一批人 | **發現錯誤**：舊版血中金屬只含 1999–2004、尿中只含 2005–2018，無共同受試者；修正合併後以同一批 {n(Pb['n_both'])} 人比較（表 6） |
| 尿液共同分母 | 比較原濃度、加尿肌酸酐共變數、比值三種寫法與三種結果定義（表 6、圖 6） |
| 陰性／陽性對照之解讀 | 改為「可檢查特定流程錯誤與部分偏差」，不宣稱對照證明無混雜 |

## 七、文獻（審查 §九）

依審查意見修正用途：Yang 2024 僅作未來病理標籤設計背景；Lai 2025、Zhang 2026 不再作為本研究之重現證據而移除；Cao 2026 不再引用；Bashir 2026 修正 DOI 並限於背景機轉；PLA2R 與抗 GBM 文獻移除。另新增經 PubMed 查證之 Selvin 2007（肌酸酐校正）、Van Calster 2019（校準）、Vickers 2006（決策曲線）、Schillie 2020（HCV 普遍篩檢）、Barr 2005（尿肌酸酐調整）；外部確認再新增經 PubMed 查證之 Collins 2016（外部驗證樣本數）與 Vergouwe 2017（模型更新方法），以及 CDC 2021–2023 年資料文件三份（BIOPRO_L、ALB_CR_L、TRIGLY_L）；設計變異新增經 PubMed 查證之 Rust & Rao 1996（複製權重變異估計）與 NCHS 比例呈現標準（Parker 2017）。

## 八、可交付成果（審查 §十）

| 產物 | 狀態 |
|---|---|
| 樣本核對表 | 完成：`results/v3_audit.json`、表 S1 |
| 資料字典 | 部分：特徵與封存清單已更新；舊附錄三（352 項）尚未改寫 |
| 逐人預測表 | 完成：`results/v3_oof.csv.gz`（SEQN、週期、軸、重複、折、標籤、原始與校準分數、分區、權重） |
| 評估摘要 | 完成：`results/v3_eval.json`、外部確認 `results/external_2021_2023.json`；表圖皆由同版結果檔生成 |
| 實驗歷史 | 完成：`docs/VERSION_LOG.md` |
| 軟體一致性 | 完成：網頁與 Python 對示範受試者逐軸一致（`verify_direction_html.py`）；新增資料不足與超出範圍旗標 |

## 九、外部確認（2026-09-27 新增）

| 步驟 | 內容 |
|---|---|
| 取用 | 使用者同意後下載 17 檔（約 {PR['total_bytes'] / 1e6:.1f} MB），大小與凍結紀錄一致，SHA256 入帳（`results/provenance.json`） |
| 評估前發現 | CDC 更換生化儀器、尿白蛋白與空腹三酸甘油酯之方法，兩個特徵更名；凍結程式只核對了肌酸酐 |
| 修正一（評估前提交 {EXT_COMMITS['amend']}） | 依 CDC 官方回推式把 {len(XAM['conversions'])} 項換回開發量尺，更名者對應回原名；模型、校準、門檻不變（論文 2.10、表 S3） |
| 主要結果 | 糖尿病軸 AUROC {XD['auc']}（{XD['auc_ci']}），內部 {D['auc']}；肝炎軸 {XH['pos']} 個事件，AUROC {XH['auc']}（{XH['auc_ci']}），平均預測為實際的 {XH['ratio_pred']} 倍 |
| 事前指定之比較 | 常規套組模型：糖尿病 {XD['bauc']}（較部署高 {XD['dbf'][1:]}，配對 CI {XD['dbf_ci']}）、肝炎 {XH['bauc']}；梯度提升：糖尿病 {XD['gauc']} |
| 敏感度（依凍結程式原樣） | 糖尿病 {SD['auc']}、肝炎 {SH['auc']}；糖尿病軸校準方向相反（原樣高估、調和後低估） |
| 事後探索（不取代主要結果） | 遮蔽六項開發時只有 1999–2004 年有值之非常規特徵：糖尿病軸 {p3(PHD['auroc_all_inputs'])} → {p3(PHD['auroc_masked'])}（{ci(PHD['delta_ci95'])}） |
| 對部署的意涵 | 改用常規套組模型並以新資料重新校準；肝炎軸不作確認性結論 |
| 部署更新（2026-09-27，使用者決定） | 網頁工具 v3.1 改用常規套組模型：肝炎軸只更新截距（{RC['肝炎']['n_pos']} 個事件），糖尿病軸更新截距與斜率（斜率檢定 p ＝ {RC['糖尿病']['candidates']['slope_lr_test_p']:.3f}）；事前機率改為 2021–2023 年比例；網頁與 Python 對示範受試者逐軸一致 |

## 十、尚未完成

1. 以另一批獨立資料驗證網頁工具 v3.1 更新後的校準（2021–2023 年資料已用於更新，不能再當驗證）；常規套組不含血中金屬與 CRP，原列之跨週期合併因此不再必要。
2. 糖尿病軸非線性模型之校準評估與部署。
3. 肝炎軸需更多事件之外部確認，B、C 型分開呈現。
4. HDL 膽固醇被肝炎 D 抗體字首規則誤排除，下一版重訓時修正。
5. 附錄三變數字典改寫。
6. 倫理審查或免審之機構認定。
"""


REFS = dict(
    kdigo="KDIGO CKD Work Group. KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease. Kidney Int. 2024;105(4S):S117–S314. https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf",
    tripod="Collins GS, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378. https://doi.org/10.1136/bmj-2023-078378",
    probast="Moons KGM, et al. PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. BMJ. 2025;388:e082505. https://doi.org/10.1136/bmj-2024-082505",
    egfr="National Kidney Foundation. CKD-EPI Creatinine Equation (2021). https://www.kidney.org/ckd-epi-creatinine-equation-2021",
    selvin="Selvin E, Manzi J, Stevens LA, et al. Calibration of serum creatinine in the National Health and Nutrition Examination Surveys (NHANES) 1988–1994, 1999–2004. Am J Kidney Dis. 2007;50(6):918–926. https://doi.org/10.1053/j.ajkd.2007.08.020",
    lab18="NCHS. NHANES 1999–2000 Standard Biochemistry Profile (LAB18): serum creatinine correction. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/1999/DataFiles/LAB18.htm",
    biopro_d="NCHS. NHANES 2005–2006 Standard Biochemistry Profile (BIOPRO_D): serum creatinine correction. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2005/DataFiles/BIOPRO_D.htm",
    albcr="NCHS. NHANES 2007–2008 Albumin & Creatinine – Urine (ALB_CR_E): urine creatinine method change. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/ALB_CR_E.htm",
    hbv="Conners EE, Panagiotakopoulos L, Hofmeister MG, et al. Screening and Testing for Hepatitis B Virus Infection: CDC Recommendations — United States, 2023. MMWR Recomm Rep. 2023;72(1):1–25. https://doi.org/10.15585/mmwr.rr7201a1",
    hepc="NCHS. NHANES 2013–2014 Hepatitis C (HEPC_H). https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/HEPC_H.htm",
    a1c="National Institute of Diabetes and Digestive and Kidney Diseases. The A1C Test & Diabetes. https://www.niddk.nih.gov/health-information/diagnostic-tests/a1c-test",
    ap="scikit-learn. sklearn.metrics.average_precision_score. https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html",
    vancalster="Van Calster B, McLernon DJ, van Smeden M, Wynants L, Steyerberg EW. Calibration: the Achilles heel of predictive analytics. BMC Med. 2019;17(1):230. https://doi.org/10.1186/s12916-019-1466-7",
    weight="NCHS. NHANES Tutorials: Weighting Module. https://wwwn.cdc.gov/nchs/nhanes/tutorials/weighting.aspx",
    vickers="Vickers AJ, Elkin EB. Decision curve analysis: a novel method for evaluating prediction models. Med Decis Making. 2006;26(6):565–574. https://doi.org/10.1177/0272989X06295361",
    hcvscreen="Schillie S, Wester C, Osborne M, Wesolowski L, Ryerson AB. CDC Recommendations for Hepatitis C Screening Among Adults — United States, 2020. MMWR Recomm Rep. 2020;69(2):1–17. https://doi.org/10.15585/mmwr.rr6902a1",
    bh="Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and powerful approach to multiple testing. J R Stat Soc Series B. 1995;57(1):289–300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x",
    barr="Barr DB, Wilder LC, Caudill SP, et al. Urinary creatinine concentrations in the U.S. population: implications for urinary biologic monitoring measurements. Environ Health Perspect. 2005;113(2):192–200. https://doi.org/10.1289/ehp.7337",
    bashir="Bashir A, et al. Lipid abnormalities in chronic viral hepatitis: associations and machine learning-enhanced prediction. BMC Gastroenterol. 2026;26:365. https://doi.org/10.1186/s12876-026-04861-y",
    yang="Yang P, et al. Machine learning models predicts risk of proliferative lupus nephritis. Front Immunol. 2024;15:1413569. https://doi.org/10.3389/fimmu.2024.1413569",
    riley="Riley RD, et al. Calculating the sample size required for developing a clinical prediction model. BMJ. 2020;368:m441. https://doi.org/10.1136/bmj.m441",
    biopro_l="NCHS. NHANES August 2021–August 2023 Standard Biochemistry Profile (BIOPRO_L): regression equations for the Cobas 6000 to Cobas 8000 change. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BIOPRO_L.htm",
    albcr_l="NCHS. NHANES August 2021–August 2023 Albumin & Creatinine – Urine (ALB_CR_L): urine albumin method change. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/ALB_CR_L.htm",
    trigly_l="NCHS. NHANES August 2021–August 2023 Cholesterol – LDL & Triglycerides (TRIGLY_L): triglyceride method change. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/TRIGLY_L.htm",
    collins_ev="Collins GS, Ogundimu EO, Altman DG. Sample size considerations for the external validation of a multivariable prognostic model: a resampling study. Stat Med. 2016;35(2):214–226. https://doi.org/10.1002/sim.6787",
    vergouwe="Vergouwe Y, Nieboer D, Oostenbrink R, et al. A closed testing procedure to select an appropriate method for updating prediction models. Stat Med. 2017;36(28):4529–4539. https://doi.org/10.1002/sim.7179",
    rustrao="Rust KF, Rao JNK. Variance estimation for complex surveys using replication techniques. Stat Methods Med Res. 1996;5(3):283–310. https://doi.org/10.1177/096228029600500305",
    parker="Parker JD, Talih M, Malec DJ, et al. National Center for Health Statistics Data Presentation Standards for Proportions. Vital Health Stat 2. 2017;(175):1–22. PMID: 30248016",
)


def number_refs(text):
    """[@a,b] → [n,m]，依首次出現編號；@@REFLIST@@ 換成對應清單。"""
    order = []

    def f(m):
        nums = []
        for k in m.group(1).split(","):
            assert k in REFS, k
            if k not in order:
                order.append(k)
            nums.append(str(order.index(k) + 1))
        return "[" + ",".join(nums) + "]"
    text = re.sub(r"\[@([a-z0-9_,]+)\]", f, text)
    unused = [k for k in REFS if k not in order]
    assert not unused, f"未引用之文獻：{unused}"
    return text.replace("@@REFLIST@@", "\n".join(f"{i + 1}. {REFS[k]}" for i, k in enumerate(order)))


def emit(text, figdir, fmt):
    for f in FIGS:
        key = "{FIGS1}" if f.startswith("圖S1") else "{FIG" + f[1] + "}"
        text = text.replace(key, fmt(f))
    return text


def main():
    obs_fig = os.path.join(VAULT, "figure", "v3")
    os.makedirs(obs_fig, exist_ok=True)
    for f in FIGS:
        shutil.copy(os.path.join(ROOT, "figures", "v3", f), os.path.join(obs_fig, f))
    fm_ = "---\ntitle: 常規檢驗能否提供腎臟指標異常的病因線索？（v3 重分析）\ntype: 研究論文\nversion: 3\ncreated: 2026-09-27\ntags: [腎病病因, NHANES, 重分析]\n---\n\n"
    nav = "> [!info] v3 重分析：依 2026-09-26《深度審查與補強方案》以真實資料執行。配套 [[審查意見回應_v3]]｜前版 [[研究計劃書V_2]]\n\n"
    paper = number_refs(PAPER)
    paper_obs = fm_ + nav + emit(paper, obs_fig, lambda f: f"![[figure/v3/{f}]]")
    paper_repo = emit(paper, None, lambda f: f"![](../kidney_cause/figures/v3/{f})")
    for path, txt in ((os.path.join(VAULT, "研究論文_v3重分析.md"), paper_obs),
                      (os.path.join(REPO_DOCS, "研究論文_v3重分析.md"), paper_repo),
                      (os.path.join(VAULT, "審查意見回應_v3.md"), RESPONSE),
                      (os.path.join(REPO_DOCS, "審查意見回應_v3.md"), RESPONSE.replace("[[研究論文_v3重分析]]", "研究論文_v3重分析.md"))):
        assert "{FIG" not in txt, path
        open(path, "w", encoding="utf-8").write(txt)
        print(f"[寫出] {path}（{len(txt):,} 字元）")


if __name__ == "__main__":
    main()
