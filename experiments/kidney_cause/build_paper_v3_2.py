# -*- coding: utf-8 -*-
"""研究論文 v3.2 與審查回應表 v3.2——所有數字由結果檔讀出（不手打）。  python build_paper_v3_2.py
輸出：Obsidian 主稿（研究計畫書/研究論文_v3.2.md、審查意見回應_v3.2.md，圖在 figure/v3_2/）＋ repo 副本（experiments/docs/）。
v3 版（build_paper_v3.py → 研究論文_v3重分析.md、審查意見回應_v3.md）照原樣保留；其勘誤見 docs/VERSION_LOG.md 第十節。"""
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")
from direction import odds_thresholds                                   # noqa: E402
from nhanes_cohort import BRIDGE_J, BRIDGE_J_LOG10, DERIVED, FEATURE_LABELS  # noqa: E402

VAULT = r"C:\Users\tpc10\Desktop\01_研究專案\MD_Piece_腎臟研究\AIMD\腎炎模型\研究計畫書"
REPO_DOCS = os.path.join(os.path.dirname(ROOT), "docs")
J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))

# ── v3.2 結果
AU, EV, SU, XX = (J("results", "v3_2_cohort_audit.json"), J("results", "v3_2_eval.json"),
                  J("results", "v3_2_supplement.json"), J("results", "v3_2_external.json"))
MK, R = J("results", "v3_2_markers.json"), J("results", "direction_v3_2_recalibration.json")["axes"]
TOOL, BASE = J("params", "direction_model_v3_2.json")["axes"], J("params", "direction_model_v3_2_basic.json")["axes"]
EXD, DEMO = J("params", "direction_demo_expected.json"), J("params", "direction_demo_patient.json")
E, X, C = EV["axes"], XX["axes"], SU["counts"]
# ── v3 結果（v2→v3 之更正、事前指定之外部確認、v3 設計變異——照原樣引用）
A3 = J("results", "v3_audit.json")
XV, XPH, XAM = (J("results", "external_2021_2023.json"), J("results", "external_2021_2023_posthoc.json"),
                J("params", "external_validation_amendment_1.json"))
XC = J("results", "external_2021_2023_precheck.json")["versions"]["調和（修正一）"]["features"]
DV, PR = J("results", "design_variance.json"), J("params", "external_validation_protocol.json")
# ── 暴露分析 v3.2（計畫 6737bf5）；v3 之 exwas_v3*.json＝2017–2018 年用原發布肌酸酐之敏感度分析（見 EXC）
EXW, CK, EXC = J("results", "exwas_v3_2.json"), J("results", "exwas_v3_2_checks.json"), J("results", "exwas_v3_2_compare.json")
# ── 免疫方向（計畫 29e1d3b、結果 9eb8cf6）：公開抗核抗體次樣本，v3.2 資料
IM = J("results", "immune_v3_2.json")
IML, IMH, IM1 = (IM["models"]["LR_routine"]["repeats"]["mean"]["auroc"], IM["models"]["HGB_routine"]["repeats"]["mean"]["auroc"],
                 IM["M1_demographics"]["auroc_mean"])
IMD = IM["paired_vs_demographics_repeat0"]["LR_routine−M1_demographics"]
IMS = IM["models"]["LR_routine"]["calibration_repeat0"]["slope"]
assert IM["decision"] == "無法可靠回推" and IML < IM1 and IMS < 0.5, "免疫方向之敘述不成立"
CM = dict(plan_v3="bf269c5", res_v3="d5140a9", proto="9ca4e9f", figs_v3="397c204", amend="44b0ace", ext="a7c4af8",
          tool_v31="59a2455", dv_plan="9edd968", dv_res="e7d16e4", plan_v32="f6abc91", res_v32="4d48842", audit="95e9db4",
          supp_plan="0826af6", supp_res="8c69f65", mk_plan="30b28d6", mk_res="b643c1f",
          exw_plan="6737bf5", exw_res="4cd396b", imm_plan="29e1d3b", imm_res="9eb8cf6")
LR, HG, LRN, LF, HF = "LR_routine", "HGB_routine", "LR_routine_noHDL", "LR_full", "HGB_full"
FIGS = {"FIG1": "圖1_分析樣本與資料修正.png", "FIG2": "圖2_判別力.png", "FIG3": "圖3_校準_線性與非線性.png", "FIG4": "圖4_穩健性.png",
        "FIG5": "圖5_決策曲線.png", "FIG6": "圖6_暴露血尿比較.png", "FIG7": "圖7_外部資料.png", "FIG8": "圖8_重新校準交叉驗證.png",
        "FIGS1": "圖S1_示範輸出.png"}
NAME = {**FEATURE_LABELS, **DERIVED, "age": "年齡", "sex": "性別"}
sha = lambda *p: hashlib.sha256(open(os.path.join(ROOT, *p), "rb").read()).hexdigest()


def n(x):
    return f"{x:,}"


def p3(x):
    return f"{x:.3f}"


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def num(x, d=3):
    t = f"{x:.{d}f}"
    return ("−" + t[1:]) if t.startswith("-") and float(t) != 0 else t.lstrip("-")


def ci(c, d=3):
    return f"{num(c[0], d)} 至 {num(c[1], d)}" if min(c) < 0 else f"{c[0]:.{d}f}–{c[1]:.{d}f}"


def sgn(x, d=3):
    t = num(x, d)
    return t if t.startswith("−") else "+" + t


def dfmt(p, f="d_auroc", d=3):
    """配對差：(帶號值, 95% CI 字串, CI 是否含 0)。"""
    c = p["ci95"][f]
    return sgn(p[f], d), ci(c, d), c[0] <= 0 <= c[1]


# ── 內部（v3.2）
def mstats(key, s):
    m = E[key]["models"][s]
    r, c, t = m["repeats"], m["calibration_repeat0"], m["bands_tool_repeat0"]
    b = t["band"]
    return dict(auc=p3(r["mean"]["auroc"]), auc_ci=ci(m["ci95_repeat0"]["auroc"]), rng=f"{r['min']['auroc']:.3f}–{r['max']['auroc']:.3f}",
                ap=p3(r["mean"]["ap"]), ap_ci=ci(m["ci95_repeat0"]["ap"]), prauc=p3(SU["axes"][key]["prauc_trapz"][s]["mean"]),
                cint=num(c["intercept"], 2), cslope=f"{c['slope']:.2f}", brier=f"{c['brier']:.4f}", bss=f"{c['brier_skill']:.3f}",
                cov=pct(t["coverage"]), hi=pct(b["傾向"]["observed_rate"]), mid=pct(b["不確定"]["observed_rate"]),
                lo=pct(b["不傾向"]["observed_rate"]), insuff=n(b["資料不足"]["n"]), insuff_rate=pct(b["資料不足"]["observed_rate"]),
                low_pos=b["不傾向"]["n_pos"], t1000=f"{t['per_1000_if_skip_low']['tested']:.0f}",
                m1000=f"{t['per_1000_if_skip_low']['missed']:.1f}", mshare=pct(t["per_1000_if_skip_low"]["missed_share_of_pos"], 0),
                band=b)


def tstats(key, s):
    t = E[key]["temporal"][s]
    return dict(auc=p3(t["auroc"]), auc_ci=ci(t["ci95"]["auroc"]), n=n(t["n"]), pos=n(t["n_pos"]), ap=p3(t["ap"]),
                ptr=pct(t["prevalence_train"]), pte=pct(t["prevalence_test"]), mp=pct(t["mean_pred"]),
                cint=num(t["calibration"]["intercept"], 2), cslope=f"{t['calibration']['slope']:.2f}")


def dv(r):
    """設計變異之格式化（盛行率為百分比，校準差為百分點）；結構同 results/design_variance.json。"""
    w, d = r["weighted"], 2 if r["weighted"]["prevalence"]["est"] < 0.05 else 1
    pp = lambda x: num(100 * x, 2)
    return dict(prev=pct(w["prevalence"]["est"], d), prev_ci="–".join(pct(x, d) for x in w["prevalence"]["ci95"]),
                deff=f"{w['prevalence']['deff']:.2f}", uw_prev=pct(r["unweighted"]["prevalence"], d),
                auc=p3(w["auroc"]["est"]), auc_ci=ci(w["auroc"]["ci95"]), ap=p3(w["ap"]["est"]), ap_ci=ci(w["ap"]["ci95"]),
                cd=pp(w["calib_diff"]["est"]), cd_ci=f"{pp(w['calib_diff']['ci95'][0])} 至 {pp(w['calib_diff']['ci95'][1])}",
                cd_has0=w["calib_diff"]["ci95"][0] <= 0 <= w["calib_diff"]["ci95"][1], df=r["df"])


def axis_vals(key):
    a, su = E[key], SU["axes"][key]
    pv = a["paired_repeat0"]
    rm = lambda s, k="auroc": a["models"][s]["repeats"]["mean"][k]
    m1 = a["M1_demographics"]["auroc_mean"]
    dg, dg_ci, dg0 = dfmt(pv["HGB_routine−LR_routine"])
    dgap, dgap_ci, _ = dfmt(pv["HGB_routine−LR_routine"], "d_ap")
    dgb, dgb_ci, dgb0 = dfmt(pv["HGB_routine−LR_routine"], "d_brier", 4)
    drf, drf_ci, drf0 = dfmt(pv["LR_routine−LR_full"])
    dh, dh_ci, dh0 = dfmt(pv["LR_routine−LR_routine_noHDL"])
    dhap, dhap_ci, _ = dfmt(pv["LR_routine−LR_routine_noHDL"], "d_ap")
    pm = a["paired_vs_demographics_repeat0"]
    d1, d1_ci, _ = dfmt(pm["LR_routine−M1_demographics"])
    d1g, d1g_ci, _ = dfmt(pm["HGB_routine−M1_demographics"])
    ab = su["ablation_adjacent"]
    ew = {c: r for c, r in su["expanding_window_LR_routine"].items() if "auroc" in r}
    ewa = {c: r["auroc"] for c, r in ew.items()}
    return dict(
        n=n(a["n"]), pos=n(a["n_pos"]), npos=a["n_pos"], prev=pct(a["prevalence"]), prev3=p3(a["prevalence"]),
        feats=len(a["features"]), routine=len(a["routine_panel"]),
        m={s: mstats(key, s) for s in a["models"]},
        m1=p3(a["M1_demographics"]["auroc_mean"]), m1ap=p3(a["M1_demographics"]["ap_mean"]),
        ap_lift=f"{a['models'][LR]['repeats']['mean']['ap'] / a['prevalence']:.1f}",
        dg=dg, dg_ci=dg_ci, dg0=dg0, dgap=dgap, dgap_ci=dgap_ci, dgb=dgb, dgb_ci=dgb_ci, dgb0=dgb0,
        drf=drf, drf_ci=drf_ci, drf0=drf0, dh=dh, dh_ci=dh_ci, dh0=dh0, dhap=dhap, dhap_ci=dhap_ci,
        d1=d1, d1_ci=d1_ci, d1g=d1g, d1g_ci=d1g_ci,
        # 五次重複平均之差（與表中平均值相減一致）；上列配對差與 CI 取第一次重複
        mdg=sgn(rm(HG) - rm(LR)), mdgap=sgn(rm(HG, "ap") - rm(LR, "ap")), mdrf=sgn(rm(LR) - rm(LF)),
        mdh=sgn(rm(LR) - rm(LRN)), md1=sgn(rm(LR) - m1), md1g=sgn(rm(HG) - m1),
        ab_removed="、".join({"LBXSATSI": "ALT", "LBXSASSI": "AST", "LBXSGTSI": "GGT", "LBXSTB": "總膽紅素",
                              "LBXSGL": "血糖", "LBXSOSSI": "滲透壓"}[x] for x in ab["removed"]),
        ab_with=p3(ab["auroc_with"]), ab_without=p3(ab["auroc_without"]), ab_d=sgn(ab["auroc_with"] - ab["auroc_without"]),
        ab_ci=ci(ab["delta_ci95"]["d_auroc"]), ab_apw=p3(ab["ap_with"]), ab_apwo=p3(ab["ap_without"]), ab_apci=ci(ab["delta_ci95"]["d_ap"]),
        t={s: tstats(key, s) for s in a["temporal"]},
        ew_rows="\n".join(f"| {c} | {n(r['n'])} | {r['n_pos']} | {p3(r['auroc'])}（{ci(r['ci95']['auroc'])}） |" for c, r in ew.items()),
        ew_min=p3(min(ewa.values())), ew_min_c=min(ewa, key=ewa.get), ew_max=p3(max(ewa.values())), ew_max_c=max(ewa, key=ewa.get),
        ew_pos=f"{min(r['n_pos'] for r in ew.values())}–{max(r['n_pos'] for r in ew.values())}",
        w={s: dv(r) for s, r in a["design_weighted"].items()},
        kr=a["kidney_label_as_reported"], dca={round(r["pt"], 3): r for r in a["decision_curve"][LR]},
        dca_g={round(r["pt"], 3): r for r in a["decision_curve"][HG]},
        thr=[odds_thresholds(BASE[key]["prevalence"])[i] for i in (0, 1)], base_prev=BASE[key]["prevalence"])


H, D = axis_vals("肝炎"), axis_vals("糖尿病")
# 文字中之方向性敘述，由結果檢查（結果改變時程式中止，不讓文字靜默失真）
assert not D["dg0"] and D["dg"].startswith("+") and H["dg0"], "HGB 與 LR 之比較敘述不成立"
assert not D["dgb0"] and D["dgb"].startswith("−"), "糖尿病 HGB Brier 較低之敘述不成立"
assert H["drf0"] and not D["drf0"] and D["drf"].startswith("−"), "常規套組 vs 全特徵之敘述不成立"
assert not D["dh0"] and H["dh0"], "HDL 之敘述不成立"
assert H["w"][LR]["cd_has0"] and not D["w"][LR]["cd_has0"] and not D["w"][HG]["cd_has0"], "加權校準差之敘述不成立"
_dl, _dh = E["糖尿病"]["decision_curve"][LR], E["糖尿病"]["decision_curve"][HG]
assert all(min(a["nb_model"], b["nb_model"]) > max(a["nb_test_all"], 0) and b["nb_model"] > a["nb_model"] for a, b in zip(_dl, _dh))
DM_DCA = (_dl[0]["pt"], _dl[-1]["pt"])
HCV1, HBV1 = E["肝炎"]["single_label_LR_routine"]["僅C型_HCV_RNA"], E["肝炎"]["single_label_LR_routine"]["僅B型_HBsAg"]
ST = E["肝炎"]["subtypes_LR_routine"]
LS = SU["axes"]["糖尿病"]["label_sensitivity_LR_routine"]
MKC = {r["marker"]: r for r in MK["僅C肝"]["all"]}
mkc = lambda m: p3(MKC[m]["auc"])


# ── 外部（v3 事前指定之一次評估；照原樣）
def ext_vals(part, key):
    r = XV[part]["axes"][key]
    ms = r["models"]
    m, b, g = ms["v3_full_LR（部署）"], ms["v3_basic_LR（常規套組候選）"], ms["v3_full_HGB（比較，僅判別）"]
    c, bb = m["calibration"], m["bands_B"]
    d = 2 if key == "肝炎" else 1
    return dict(
        n=n(r["n"]), pos=r["n_pos"], prev=pct(r["prevalence"], d), auc=p3(m["auroc"]), auc_ci=ci(m["ci95"]["auroc"]),
        ap=p3(m["ap"]), ap_ci=ci(m["ci95"]["ap"]), cint=num(c["intercept"], 2), cslope=f"{c['slope']:.2f}",
        meanpred=pct(c["mean_pred"], d), obs=pct(c["observed"], d), ratio_pred=f"{c['mean_pred'] / c['observed']:.1f}",
        brier=f"{c['brier']:.4f}", bss=num(c["brier_skill"], 3), insuff=n(m["insufficient_data_n"]), covB=pct(bb["coverage"]),
        rates="／".join(pct(bb["band"][k]["observed_rate"]) for k in ("傾向", "不確定", "不傾向")),
        bauc=p3(b["auroc"]), bauc_ci=ci(b["ci95"]["auroc"]), dbf=sgn(b["auroc"] - m["auroc"]),
        dbf_ci=ci(r["basic_minus_full"]["d_auroc"]), gauc=p3(g["auroc"]), gap=p3(g["ap"]))


XH, XD = ext_vals("primary", "肝炎"), ext_vals("primary", "糖尿病")
SH, SD = ext_vals("sensitivity_as_frozen", "肝炎"), ext_vals("sensitivity_as_frozen", "糖尿病")
XK, SK = XV["primary"]["kidney"], XV["sensitivity_as_frozen"]["kidney"]
PHH, PHD, HC = XPH["axes"]["肝炎"], XPH["axes"]["糖尿病"], XPH["hep_positive_composition"]
ph = lambda r: (f"{p3(r['auroc_all_inputs'])} {'升' if r['delta_masked_minus_all'] >= 0 else '降'}為 {p3(r['auroc_masked'])}"
                f"（差 {sgn(r['delta_masked_minus_all'])}，95% CI {ci(r['delta_ci95'])}）")
xr = lambda f: f"{XC[f]['ratio']:.2f}"
FULL = "v3_full_LR（部署）"
XDH, XDD = dv(DV["external"]["肝炎"][FULL]), dv(DV["external"]["糖尿病"][FULL])
DH3, DD3 = dv(DV["internal"]["肝炎"]), dv(DV["internal"]["糖尿病"])


# ── 外部（v3.2 事後評估）
def xstats(key, s):
    v = X[key]["models"][s]
    c, b = v["calibration"], v["bands_B"]["band"]
    ntot = X[key]["n"]
    return dict(auc=p3(v["auroc"]), auc_ci=ci(v["ci95"]["auroc"]), ap=p3(v["ap"]), ap_ci=ci(v["ci95"]["ap"]),
                cint=num(c["intercept"], 2), cslope=f"{c['slope']:.2f}", brier=f"{c['brier']:.4f}", bss=num(c["brier_skill"], 3),
                mp=pct(c["mean_pred"], 2 if key == "肝炎" else 1), insuff=v["insufficient_data_n"],
                cov=pct((b["傾向"]["n"] + b["不傾向"]["n"]) / ntot),
                rates="／".join("—" if b[k]["observed_rate"] is None else pct(b[k]["observed_rate"]) for k in ("傾向", "不確定", "不傾向")))


def xw(key, s, wk):
    return dv(X[key]["weighted"][s][wk])


XS2 = {key: {s: xstats(key, s) for s in X[key]["models"]} for key in ("肝炎", "糖尿病")}
xd = lambda key, k: dfmt(X[key]["paired"][k])
XM1 = {key: dict(auc=p3(X[key]["M1_demographics"]["auroc"]), auc_ci=ci(X[key]["M1_demographics"]["ci95"]["auroc"])) for key in X}
assert not xd("糖尿病", "HGB_routine−LR_routine")[2] and not xd("糖尿病", "LR_routine−LR_full")[2], "外部糖尿病比較之敘述不成立"
assert not xd("糖尿病", "LR_routine−M1_demographics")[2] and xd("肝炎", "LR_routine−M1_demographics")[2], "外部年齡性別比較之敘述不成立"
XS_SUB = XX["hepatitis_subtypes_tool_v3_2"]
XDATA = XX["data"]


# ── 網頁工具 v3.2 與重新校準之交叉驗證
def cvs(ver, key):
    s = XX["recalibration_cv"][ver][key]["random_summary"]
    q = lambda d, k="median": d[k]
    return dict(oe=f"{q(s['oe_recal']):.2f}", oe_rng=f"{s['oe_recal']['p2_5']:.2f}–{s['oe_recal']['p97_5']:.2f}",
                oen=f"{q(s['oe_none']):.2f}", oen_rng=f"{s['oe_none']['p2_5']:.2f}–{s['oe_none']['p97_5']:.2f}",
                share=pct(s["share_slope_update"], 0), npos=f"{q(s['n_pos_test']):.0f}",
                ci_r=num(q(s["calib_intercept_recal"]), 2), cs_r=f"{q(s['calib_slope_recal']):.2f}",
                ci_n=num(q(s["calib_intercept_none"]), 2), cs_n=f"{q(s['calib_slope_none']):.2f}",
                cs_r_rng=f"{s['calib_slope_recal']['p2_5']:.2f}–{s['calib_slope_recal']['p97_5']:.2f}",
                fixed_oe=f"{XX['recalibration_cv'][ver][key]['fixed_split']['mean_pred_recal'] / XX['recalibration_cv'][ver][key]['fixed_split']['observed_test']:.2f}")


CVH, CVD, CV31H, CV31D = cvs("v3.2", "肝炎"), cvs("v3.2", "糖尿病"), cvs("v3.1", "肝炎"), cvs("v3.1", "糖尿病")


def tool_vals(key):
    r = R[key]
    t = r["after_apparent"]["thresholds"]
    d = 2 if key == "肝炎" else 1
    return dict(method=r["recalibration"]["method"], a=num(r["recalibration"]["a"], 3), b=f"{r['recalibration']['b']:.3f}",
                p=f"{r['candidates']['slope_lr_test_p']:.4f}", npos=r["n_pos"], prior=pct(TOOL[key]["prevalence"], d),
                hi=pct(t["t_high"], d), lo=pct(t["t_low"], d))


TH, TD = tool_vals("肝炎"), tool_vals("糖尿病")
hdl_i = TOOL["肝炎"]["features"].index("LBDHDL")
HDL_MED = sum(fp["medians"][hdl_i] for fp in TOOL["肝炎"]["ensemble"]) / len(TOOL["肝炎"]["ensemble"])
EXH, EXDM = EXD["axes"]["肝炎"], EXD["axes"]["糖尿病"]
assert EXH["drivers"][0] == "LBDHDL", "示範受試者最大推動因子不是 HDL"

# ── 樣本與資料修正
old, T3, RC3 = A3["old_rebuild"], A3["total"], A3["reclassification"]
kd_known3 = old["n_adults"] - T3["kidney"]["unknown"]
kd_known32 = C["adults"] - C["kidney"]["unknown"]
CH1718 = AU["kidney_2017_2018_reported_vs_DxC"]
PC = AU["per_cycle"]
assert all(v["kidney_v3"] == v["kidney_v3_2"] and v["hep_v3"] == v["hep_v3_2"] and v["dm_v3"] == v["dm_v3_2"]
           for c, v in PC.items() if c != "2017-2018"), "v3 → v3.2 之計數在 2017–2018 以外有改變"
AV = AU["feature_availability_in_kidney"]
HDL_MIN = min(AV["LBDHDL"].values())
AV0102 = min(AV[f]["2001-2002"] for f in ("LBXSAPSI", "LBXSLDSI", "LBXSPH", "LBXSTB"))
NONROUTINE = [f for f in dict.fromkeys(E["肝炎"]["features"] + E["糖尿病"]["features"])
              if f not in set(E["肝炎"]["routine_panel"]) | set(E["糖尿病"]["routine_panel"])]
N_ROUTINE = len(set(E["肝炎"]["routine_panel"]) | set(E["糖尿病"]["routine_panel"]))
assert N_ROUTINE + len(NONROUTINE) == EV["n_features"]
BM = AU["bridged_medians_adults"]
closer = [k for k in list(BRIDGE_J) + list(BRIDGE_J_LOG10)
          if abs(BM["2017-2018_DxC"][k] - BM["2015-2016"][k]) < abs(BM["2017-2018_reported"][k] - BM["2015-2016"][k])]
X2 = C["two_label_crosstab_in_kidney"]

# ── 暴露（v3.2 重跑；與 v3 之比較見 EXC）
EC, ER = EXC["cohort_comparison"], EXC["results_comparison"]
LC = {(t["v3"], t["v3_2"]): t["n"] for t in EC["label_changes"]["transitions"]}
assert EC["v3_equals_v32_with_original_2017_2018_creatinine"], "v3 已不等於 2017–2018 原發布肌酸酐之敏感度分析"
assert EC["label_changes"]["by_cycle"] == {"2017-2018": EC["label_changes"]["n_changed"]}
assert set(LC) <= {("異常", "正常"), ("異常", "未知")}
assert LC.get(("異常", "正常"), 0) == CH1718.get("1→0", 0) and LC.get(("異常", "未知"), 0) == CH1718.get("1→-1", 0)
assert not ER["status_changed"] and EXW["plan_sha256"] == sha("params", "exwas_v3_2_plan.json")
assert ER["max_abs_dlogOR"]["exposure"] == "URXUAS3"      # 文中稱「尿中亞砷酸」（UAS 檔標籤 Urinary arsenous acid）
assert not any(m["cells_changing_p_below_05"] for m in EXC["checks_comparison"].values())
Xr = {r["exposure"]: r for r in EXW["results"]}
xo = lambda e: Xr[e]["headline"]
Pb, Cd = CK["metals"]["鉛"], CK["metals"]["鎘"]
mo = lambda M, o, k: M["models"][o][k]
# 3.6 敘述之方向
assert set(EXW["control_check"]["positive_hits"]) == {"藥_鈣調磷酸酶", "藥_PPI"} and not EXW["control_check"]["negative_hits"]
assert not EXW["arsenic_builtin_control"]["arsenobetaine_significant"] and not EXW["arsenic_builtin_control"]["toxic_species_significant"]
assert all(Xr[e]["significant_fdr05"] and xo(e)["OR"] > 1 for e in ("藥_利尿劑", "藥_胰島素", "藥_別嘌醇", "藥_ACEI_ARB"))
assert Xr["藥_雙胍"]["significant_fdr05"] and xo("藥_雙胍")["OR"] < 1 and not Xr["藥_NSAID"]["significant_fdr05"]
assert all(mo(M, o, "血中")["ci"][0] > 1 for M in (Pb, Cd) for o in ("kidney_damage", "egfr_lt60", "acr_ge30"))
assert mo(Pb, "egfr_lt60", "尿中_原濃度")["ci"][1] < 1
assert mo(Pb, "egfr_lt60", "尿中_原濃度＋尿肌酸酐共變數")["OR_per_doubling"] < mo(Pb, "egfr_lt60", "尿中_原濃度")["OR_per_doubling"]
assert mo(Cd, "acr_ge30", "尿中_肌酸酐比值")["OR_per_doubling"] > mo(Cd, "acr_ge30", "尿中_原濃度")["OR_per_doubling"]
orr = lambda m: f"{m['OR_per_doubling']:.2f}（{m['ci'][0]:.2f}–{m['ci'][1]:.2f}）"
sig = sorted([r for r in EXW["results"] if r["significant_fdr05"]], key=lambda r: r["q_bh"])


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


def per_cycle_table():
    rows = ["| 週期 | 成人 | 腎臟 陽／陰／未知 | 肝炎 陽／陰／未知 | 糖尿病 陽／陰／未知 | 備註 |", "|---|---|---|---|---|---|"]
    note = {"2001-2002": "四項生化改名對應（v3.2）", "2003-2004": "無 HCV RNA 變數：HCV 抗體陽性者只能判未知",
            "2017-2018": "生化依 BIOPRO_J 換回舊量尺（v3.2）；HCV RNA 碼 3＝抗體篩檢陰性"}
    for c, r in PC.items():
        k, h, d = r["kidney_v3_2"], r["hep_v3_2"], r["dm_v3_2"]
        nt = note.get(c, "HCV RNA 碼 3＝抗體篩檢陰性" if c >= "2013-2014" else "")
        rows.append(f"| {c} | {n(r['adults'])} | {n(k['pos'])}／{n(k['neg'])}／{n(k['unknown'])} | "
                    f"{h['pos']}／{n(h['neg'])}／{h['unknown']} | {n(d['pos'])}／{n(d['neg'])}／{d['unknown']} | {nt} |")
    return "\n".join(rows)


def six_table(v, key):
    b = v["m"][LR]["band"]
    cell = lambda k, pos: n(b[k]["n_pos"] if pos else b[k]["n"] - b[k]["n_pos"])
    return (f"| 實際標籤 | 傾向 | 不確定 | 不傾向 | 資料不足 |\n|---|---|---|---|---|\n"
            f"| 陽性 | {cell('傾向', 1)} | {cell('不確定', 1)} | {cell('不傾向', 1)} | {cell('資料不足', 1)} |\n"
            f"| 陰性 | {cell('傾向', 0)} | {cell('不確定', 0)} | {cell('不傾向', 0)} | {cell('資料不足', 0)} |\n"
            f"| 該區實際陽性率 | {v['m'][LR]['hi']} | {v['m'][LR]['mid']} | {v['m'][LR]['lo']} | {v['m'][LR]['insuff_rate']} |")


def conv_table_l():
    from nhanes_cohort import FEATURE_LABELS as FL
    rows = ["| 變數 | 檢驗 | 回推式（舊＝） | 來源 |", "|---|---|---|---|"]
    for v, c in XAM["conversions"].items():
        a, b = map(float, re.match(r"舊 = (\S+) \+ (\S+) × 新", c["equation"]).groups())
        src = os.path.basename(c["source"]).replace(".htm", "")
        fa = ("−" + f"{-a:g}") if a < 0 else f"{a:g}"
        rows.append(f"| {v} | {FL.get(v, v)} | {fa} ＋ {b:g} × 新值 | {src} |")
    return "\n".join(rows)


def conv_table_j():
    rows = ["| 變數 | 檢驗 | 回推式（X＝換算值，Y＝2017–2018 原值） | 2015–2016 中位數 | 2017–2018 原值中位數 | 換算後中位數 |",
            "|---|---|---|---|---|---|"]
    for k in list(BRIDGE_J) + list(BRIDGE_J_LOG10):
        if k in BRIDGE_J:
            a, b = BRIDGE_J[k]
            eq = f"X ＝ {b:g} × Y {'＋' if a >= 0 else '−'} {abs(a):g}"
        else:
            a, b = BRIDGE_J_LOG10[k]
            eq = f"log₁₀X ＝ {b:g} × log₁₀Y {'＋' if a >= 0 else '−'} {abs(a):g}"
        rows.append(f"| {k} | {NAME.get(k, k)} | {eq} | {BM['2015-2016'][k]:g} | {BM['2017-2018_reported'][k]:g} | {BM['2017-2018_DxC'][k]:.4g} |")
    return "\n".join(rows)


fm_models = PR["frozen_models"]
sha_amend = sha("params", "external_validation_amendment_1.json")
plan32_sha = EV["plan_sha256"]
nonroutine_names = "、".join(NAME.get(f, f).split("（")[0].replace(" BAP", "").replace(" PTH", "") for f in NONROUTINE)

PAPER = f"""# 常規檢驗能否回推腎炎（腎損傷）的病因方向？

## ——感染、代謝、免疫三個方向：NHANES 1999–2018 重分析、資料修正與 2021–2023 外部評估（v3.2）

作者　＿＿＿＿＿＿　　所屬單位　＿＿＿＿＿＿　　版本　v3.2（2026-09-27）

---

## 摘要

**背景與目的**　本研究的起點是一個臨床問題：腎炎（腎損傷）時，能否只用已有的常規血液與尿液檢驗，回推病因方向（感染、代謝、免疫）。公開健康調查沒有腎炎診斷與病理，腎炎（腎損傷）以腎臟指標異常為操作型定義，三個方向各以共存疾病標籤代表（肝炎病毒感染、糖尿病、抗核抗體陽性）；共存疾病是候選病因，不等於病因。v3 依 2026 年 9 月 26 日之外部方法學審查以真實資料重建標籤與評估流程；v3.2 再逐週期核對官方文件、修正三類資料錯誤，並評估非線性模型的校準。

**方法**　NHANES 1999–2018 十個週期成人 {n(C['adults'])} 人。依官方文件校正跨週期檢驗（1999–2000 與 2005–2006 年血清肌酸酐、2007 年前尿肌酸酐、2001–2002 年以另一變數名發布之四項生化、2017–2018 年生化儀器更換之回推式）；腎臟指標與各方向標籤採三值（陽性、陰性、未知），各方向排除未知者。候選模型為常規套組與全特徵之邏輯迴歸與梯度提升，皆採網頁工具的結構（五折交叉配適集成加保序校準），以分層五折重複五次之巢狀外層評估（校準器與分區門檻只用外層訓練資料），並在同一切分比較只用年齡、性別的基準；另做時間外推、調查權重與抽樣設計變異、標籤定義敏感度與決策曲線。免疫方向以 1999–2004 年剩餘血清之抗核抗體次樣本（1:80 稀釋 3+／4+）另行評估。分析計畫皆於執行前提交版本控制。外部資料為 NHANES 2021–2023：v3 事前凍結模型並一次評估；v3.2 模型於修正後資料重新訓練後再評估，屬事後分析。網頁工具以 2021–2023 年資料重新校準，並以依抽樣設計切半 200 次的交叉驗證估計此步驟之可靠度。

**結果**　腎臟指標異常 {n(C['kidney']['pos'])} 人，另有 {n(C['kidney']['unknown'])} 人無法判定；肝炎標籤陽性 {H['pos']} 人、糖尿病標籤陽性 {D['pos']} 人。網頁工具所用之常規套組邏輯迴歸：肝炎軸 AUROC {H['m'][LR]['auc']}（95% CI {H['m'][LR]['auc_ci']}）、平均精確率 {H['m'][LR]['ap']}（盛行率 {H['prev3']}）、校準斜率 {H['m'][LR]['cslope']}；糖尿病軸 AUROC {D['m'][LR]['auc']}（{D['m'][LR]['auc_ci']}）、校準斜率 {D['m'][LR]['cslope']}；只用年齡與性別時為 {H['m1']} 與 {D['m1']}。糖尿病軸的梯度提升 AUROC {D['m'][HG]['auc']}，比邏輯迴歸高（第一次重複之配對差 {D['dg']}，95% CI {D['dg_ci']}），經同樣保序校準後截距 {D['m'][HG]['cint']}、斜率 {D['m'][HG]['cslope']}，Brier 分數由 {D['m'][LR]['brier']} 降為 {D['m'][HG]['brier']}；肝炎軸則無優勢（配對差 {H['dg']}，95% CI {H['dg_ci']}）。肝炎軸的訊號幾乎全來自 C 型肝炎（僅 C 肝標籤 AUROC {p3(HCV1['auroc'])}，僅 B 肝 {p3(HBV1['auroc'])}）。在 2021–2023 年資料上，糖尿病軸之邏輯迴歸與梯度提升 AUROC 為 {XS2['糖尿病'][LR]['auc']} 與 {XS2['糖尿病'][HG]['auc']}，同一批人只用年齡、性別為 {XM1['糖尿病']['auc']}；肝炎軸只有 {X['肝炎']['n_pos']} 名陽性，無法確認。重新校準之交叉驗證中，糖尿病軸測試半平均預測與實際之比中位數 {CVD['oe']}（{CVD['oe_rng']}）。免疫方向（抗核抗體次樣本 {n(IM['n'])} 人、陽性 {IM['n_pos']} 人）常規套組邏輯迴歸 AUROC {IML:.3f}、梯度提升 {IMH:.3f}，只用年齡、性別為 {IM1:.3f}；邏輯迴歸減年齡性別之配對 ΔAUROC {sgn(IMD['d_auroc'])}（95% CI {ci(IMD['ci95']['d_auroc'])}）。

**結論**　常規檢驗可回推腎炎（腎損傷）的代謝方向（糖尿病標籤，中等辨識力、內部校準良好），感染方向只能部分回推（訊號主要來自 C 型肝炎，對 B 型肝炎幾乎沒有訊號），免疫方向回推不了（抗核抗體標籤未優於只用年齡、性別）。糖尿病軸的非線性模型判別更高、經保序校準後校準同樣接近理想，且在新資料上維持；網頁工具為保留逐項解釋而維持邏輯迴歸。肝炎軸的外部事件太少，仍待確認。回推的是病因方向，不等於確定腎損傷病因，且在普遍篩檢的建議下，本工具不宜用來決定誰不必驗肝炎。

**關鍵詞**：NHANES；腎炎（腎損傷）；病因方向；C 型肝炎；糖尿病；抗核抗體；預測模型；校準；外部評估

---

## Abstract

**Background** We asked whether routine blood and urine tests can point toward the cause of abnormal kidney markers. Public survey data provide comorbidity labels, not etiology, so we evaluated how well routine tests identify two candidate-cause labels (hepatitis virus infection and diabetes). Version 3 rebuilt the analysis after an external methodological review; version 3.2 corrected three further data errors found by cycle-by-cycle checks of the official documentation and evaluated the calibration of a non-linear model.

**Methods** Adults in NHANES 1999–2018 (n = {n(C['adults'])}). Laboratory values were harmonized across cycles following NCHS documentation, including renamed 2001–2002 biochemistry variables and backward equations for the 2017–2018 analyzer change; labels were three-valued (positive, negative, unknown). Logistic regression and gradient boosting on a routine panel and on all features were fitted with the deployed tool's structure (cross-fitted ensemble with isotonic calibration) and evaluated by nested 5-fold cross-validation repeated five times, with calibration and thresholds learned only in outer training folds, against an age–sex baseline on identical splits. NHANES 2021–2023 served as external data (a pre-specified single evaluation in version 3; post hoc in version 3.2). The web tool was recalibrated on these data, and the reliability of recalibration was estimated by 200 design-based half splits.

**Results** Kidney-marker abnormality was present in {n(C['kidney']['pos'])} adults. The routine-panel logistic model had an AUROC of {H['m'][LR]['auc']} (95% CI {H['m'][LR]['auc_ci']}) for hepatitis and {D['m'][LR]['auc']} ({D['m'][LR]['auc_ci']}) for diabetes, versus {H['m1']} and {D['m1']} for age and sex alone. For diabetes, gradient boosting reached {D['m'][HG]['auc']} (paired difference in the first repeat {D['dg']}, 95% CI {D['dg_ci']}) with a calibration intercept of {D['m'][HG]['cint']} and slope of {D['m'][HG]['cslope']} after the same isotonic calibration; for hepatitis it offered no gain. The hepatitis signal came from hepatitis C (AUROC {p3(HCV1['auroc'])}) rather than hepatitis B ({p3(HBV1['auroc'])}). In NHANES 2021–2023, the diabetes models reached {XS2['糖尿病'][LR]['auc']} (logistic) and {XS2['糖尿病'][HG]['auc']} (boosting) versus {XM1['糖尿病']['auc']} for age and sex; the hepatitis axis had only {X['肝炎']['n_pos']} events. After recalibration, the median ratio of mean predicted to observed risk in held-out halves was {CVD['oe']} for diabetes.

**Conclusions** Routine tests carry moderate, internally well-calibrated signal for hepatitis C–related and diabetes labels, usable as etiologic clues but not as diagnoses. A non-linear model improved discrimination for diabetes without loss of calibration; the web tool keeps logistic regression for item-level explanations. The hepatitis axis remains unconfirmed externally.

---

## 1　前言

腎臟病的病因評估需要整合病史、共存疾病、用藥、身體檢查、實驗室數據、影像，以及適當情境下的病理或基因檢查；單次 eGFR 下降或白蛋白尿升高，也不足以確認異常已持續三個月以上[@kdigo]。臨床上多數人每年都有抽血與驗尿，這些數值早已存在，卻很少被拿來回答「腎臟為什麼出問題」。本研究的核心問題正是這一點：**腎炎（腎損傷）時，只用常規檢驗，能不能回推病因方向——感染、代謝，還是免疫？**

公開健康調查能回答的範圍有限。美國國家健康與營養調查（NHANES）沒有腎炎診斷與腎臟病理，腎炎（腎損傷）只能以腎臟指標異常為操作型定義，三個病因方向也只能以共存疾病的操作型標籤代表：感染方向為 B 型或 C 型肝炎病毒感染、代謝方向為糖尿病、免疫方向為抗核抗體陽性（只有 1999–2004 年剩餘血清次樣本檢驗）。這些標籤是腎損傷的候選病因，但標籤成立不代表腎損傷由它造成。因此本研究把問題界定為：**常規檢驗能否回推這三個病因方向的標籤**——回推得出來，才有資格被稱為病因方向；要確認病因，仍需病理或臨床參考標準。

前一版（v2）於 2026 年 9 月 26 日接受外部方法學審查。審查者沒有取得資料與程式，因此將標籤缺失、跨週期校正、校準流程、抽樣權重與時間驗證列為「待執行」；v3 以原始資料執行這些重分析，並發現數項審查者無法看見的資料錯誤。v3 完成後，本研究逐週期檢查每個特徵的有值比例並逐一閱讀 CDC 資料文件，又找到三類能通過雜湊檢查的錯誤；v3 也留下兩個問題：糖尿病軸的梯度提升判別較高，但校準未知；網頁工具以 2021–2023 年資料重新校準，但這一步的可靠度未知。本版（v3.2）修正資料、重建模型並回答這兩個問題。研究目的為：

1. 依 NHANES 官方文件校正跨週期檢驗量尺，以腎臟指標異常定義腎炎（腎損傷），並為感染（病毒性肝炎）、代謝（糖尿病）、免疫（抗核抗體）三個病因方向建立三值標籤，未知不再當作陰性；
2. 以校準與門檻完全留在訓練資料內的巢狀外層評估[@tripod,probast]，評估常規檢驗回推代謝方向的判別與校準，並比較線性與非線性模型；
3. 評估常規檢驗回推感染方向的能力，並分開 B 型與 C 型肝炎；
4. 以公開的抗核抗體次樣本，評估常規檢驗能否回推免疫方向；
5. 與只用年齡、性別的基準比較，檢驗時間外推、調查權重與抽樣設計、標籤定義與 NHANES 2021–2023 新資料上的表現，並以決策曲線評估能否用來省略檢驗；
6. 以上游暴露掃描（同一批受試者比較血中與尿中金屬）檢驗單次橫斷面資料能否找到原因，並記錄能通過雜湊檢查的資料錯誤；
7. 建立網頁工具，逐項顯示推動因子，並估計以新資料重新校準的可靠程度。

## 2　材料與方法

### 2.1　研究設計與資料來源

本研究為 NHANES 1999–2018 年十個週期的重複橫斷面次級資料分析，納入年齡至少 20 歲者。各週期為不同受試者，本設計不追蹤個人發病時序，故稱「分析樣本」而非世代。資料檔的來源網址與 SHA256 雜湊記錄於出處帳本，用於確認檔案未被更動；雜湊不能證明資料的單位、合併或標籤正確——v3 與 v3.2 發現的資料錯誤都能通過雜湊檢查。分析計畫皆在執行評估程式之前提交版本控制：v3（`params/v3_analysis_plan.json`，提交 {CM['plan_v3']}）、設計變異（{CM['dv_plan']}）、v3.2（`params/v3_2_plan.json`，SHA256 前 16 碼 {plan32_sha[:16]}，提交 {CM['plan_v32']}）。為使本文與 v3 之報告項目一致，另有四項 v3 已有、v3.2 計畫未列之分析（描述性計數、近端特徵消融、擴展視窗、糖尿病標籤定義敏感度）與單變量標記描述，依 v3 之定義於 v3.2 資料重跑；程式亦先提交後執行（{CM['supp_plan']}、{CM['mk_plan']}），但執行於 v3.2 主要結果之後。1999–2018 年資料已於先前版本反覆檢視，本版屬探索性修訂，不是確認性驗證。

### 2.2　腎臟指標與檢驗校正

腎臟指標異常定義為單次 eGFR < 60 mL/min/1.73 m² 或尿白蛋白／肌酸酐比（ACR）≧ 30 mg/g。eGFR 以 CKD-EPI 2021 無種族係數公式計算[@egfr]。血清肌酸酐依官方文件校正：1999–2000 年為 1.013 × 原值 ＋ 0.147[@selvin,lab18]，2005–2006 年為 −0.016 ＋ 0.978 × 原值[@biopro_d]；2001–2004 年不需校正[@selvin]。v2 在 1999–2000 年誤用了 NHANES III（1988–1994）的公式 −0.184 ＋ 0.960 × 原值，使該週期原值 1.0 mg/dL 被換算為 0.776 而非 1.160，eGFR 因此被高估（v3 更正）。2007 年起尿肌酸酐改用酵素法，依官方分段式轉換 2007 年前之值[@albcr]：原值 X < 75 mg/dL 時為 (1.02√X − 0.36)²，75–250 時為 (1.05√X − 0.74)²，≧ 250 時為 (1.01√X − 0.10)²。

v3.2 另更正兩項跨週期問題。第一，2001–2002 年之鹼性磷酸酶、LDH、磷與總膽紅素，官方以 LBDSAPSI、LBDSLDSI、LBDSPH、LBDSTB 發布[@l40b]；前版只讀取其他週期的變數名，這四項在該週期整週期缺值而以中位數補入，本版改名對應（腎臟指標異常者中有值比例 {pct(AV0102, 0)}）。第二，2017–2018 年生化儀器由 Beckman Coulter DxC 660i 改為 Roche Cobas 6000，CDC 以 248 份檢體之橋接研究提供回推式，把數值換回舊儀器量尺[@biopro_j]；本研究特徵中有 {len(BRIDGE_J) + len(BRIDGE_J_LOG10)} 項適用（另有 9 項 CDC 判定不需調整，球蛋白與滲透壓為計算值）。前版未套用，開發資料因此混用兩種量尺。本版依官方式換算（補充表 S4；鹼性磷酸酶為 log₁₀ 尺度；回推值小於 0 設為 0；球蛋白為總蛋白減白蛋白、滲透壓與 eGFR 由換算後之組成重算）。主分析的 2017–2018 年腎臟指標使用換算後肌酸酐，另以原發布值做敏感度分析。HbA1c 在 2007–2010 年分布右移，CDC 找不到原因並建議使用原始值[@ghb_f]，本研究照辦。

腎臟結果採三值：任一已測指標達門檻為陽性；兩項皆有值且正常為陰性；一項正常而另一項缺失、或兩項皆缺失為未知。

### 2.3　病因方向標籤（共存疾病之操作型定義）

**肝炎病毒感染標籤**：B 型肝炎表面抗原（HBsAg）陽性或 C 型肝炎病毒 RNA 陽性[@hbv]。HBsAg 在各週期凡有肝炎血清結果者皆為陽性或陰性碼，缺值即未檢測。HCV RNA 依檢驗流程只在抗體陽性或不確定者檢測，故 RNA 缺值且抗體陰性者判為 HCV 陰性；2013 年起 RNA 變數以碼 3 表示「抗體篩檢陰性」[@hepc]；抗體陽性或不確定而無 RNA 者為未知。2003–2004 年的公開檔沒有 HCV RNA 變數，該週期抗體陽性者只能判為未知（v2 將他們判為陰性，v3 更正）。

**糖尿病標籤**：自述曾被醫師診斷糖尿病（問卷 DIQ010＝1，題目已排除妊娠期間）或 HbA1c ≧ 6.5%[@a1c]。DIQ010＝2（否）或 3（邊緣）為問卷陰性，7（拒答）、9（不知道）或缺值為問卷未知；兩項組成任一陽性即陽性，兩項皆陰性才判陰性，其餘為未知。

**抗核抗體標籤（免疫方向）**：1999–2004 年剩餘血清次樣本以間接免疫螢光檢測抗核抗體，1:80 稀釋下總強度 3+／4+（該檔之陽性規則）為陽性、未達 3+ 為陰性，不在次樣本者為未知。特異自體抗體只在 3+／4+ 者反射檢驗，故不另作標籤。

三個標籤各自判定、可同時成立，各方向只排除該方向未知者。

### 2.4　特徵

候選特徵 {EV['n_features']} 項：常規血液與尿液檢驗 {N_ROUTINE} 項（全血球計數、標準生化、血脂、尿白蛋白與肌酸酐，加上 ACR、eGFR、嗜中性球／淋巴球比、年齡、性別），每個週期都有測量；另 {len(NONROUTINE)} 項非常規檢驗（{nonroutine_names}）在本研究資料中只有部分週期有值，只用於「全特徵」模型。v3.2 新增 HDL 膽固醇：前版以變數字首封存 D 型肝炎抗體（LBDHD）時，把 HDL（LBDHDL、LBXHDD）一併排除，2005 年起的變數名 LBDHDD 也未讀取；這屬過度排除、不造成洩漏。本版以完整變數名封存 D 型肝炎抗體並讀入 HDL（各週期有值 ≧ {pct(HDL_MIN, 0)}）；1999–2002 與 2005–2006 年 HDL 的方法偏差 CDC 已於發布資料中修正[@lab13]。

定義標籤的檢驗（HBsAg、HCV 抗體與 RNA、HbA1c、糖尿病問卷）一律不作特徵。各軸再移除生理上緊鄰標籤的「近端特徵」：肝炎軸移除 ALT、AST、GGT、總膽紅素（餘 {H['feats']} 項），糖尿病軸移除血糖與滲透壓（餘 {D['feats']} 項）。這些近端特徵在預測時合法可得，移除它們是更嚴格的消融，並不表示保留就是資料洩漏。「常規套組」依可得性而非表現事先定義：肝炎軸 {H['routine']} 項、糖尿病軸 {D['routine']} 項。

### 2.5　模型與巢狀評估

候選模型五個：常規套組邏輯迴歸（網頁工具所用之模型族）、常規套組邏輯迴歸不含 HDL（估計補回 HDL 之影響）、常規套組梯度提升、全特徵邏輯迴歸、全特徵梯度提升。邏輯迴歸為中位數插補、標準化與類別平衡權重；梯度提升為 HistGradientBoosting（最大深度 3、學習率 0.08、300 回合、L2 1.0、類別平衡權重），沿用 v3 設定、不調參。五個模型都採網頁工具的結構：以五折交叉配適得到五個模型並平均其機率，再以內層折外分數配適保序迴歸校準。

評估採分層五折、重複五次（隨機種子 20260926），與 v3 相同之切分規則：每一外層折都在外層訓練資料內重新完成插補、標準化、集成、校準與門檻計算，外層受試者只用於評估；每次重複中每人恰有一個外層預測。指標逐次重複計算後取平均並列出最小至最大；95% 信賴區間取第一次重複之受試者層重抽 1,000 次，不含重新配適的變異。只用年齡與性別之邏輯迴歸在同一切分評估。模型間差異取第一次重複之外層預測計算配對差，並以同一批受試者重抽估計其 95% CI；配對差與表中五次重複平均之差可能不同，兩者並列。校準、分區、人口加權與決策曲線皆取第一次重複之外層預測。

判別以 AUROC 與平均精確率（AP，scikit-learn `average_precision_score` 之不內插階梯和[@ap]）並列該軸盛行率，另報梯形 PR-AUC；肝炎軸盛行率低，以 AP 為主要判別摘要。校準報告校準截距（以預測機率之 logit 為 offset）、校準斜率、Brier 分數與相對僅用盛行率之 Brier skill[@vancalster]。逐人外層預測存於 `results/v3_2_oof.csv.gz`，可重算所有指標。

### 2.6　三段分區

輸出分為「傾向」「不確定」「不傾向」：預測勝算 ≧ 事前勝算 2 倍為傾向、≦ 0.5 倍為不傾向，相當於概似比 2 與 0.5（v3 於看到結果前由盛行率倍數規則改為此規則）。常規套組有值不足一半者標示「資料不足」、不給方向；報告「能給出方向的比例」時以全部受試者為分母，各區實際陽性率只計入資料足夠者，「只略過不傾向區」之情境中資料不足者照常送驗。超出開發資料範圍的輸入值另行標示。

### 2.7　同切分比較、時間、權重與標籤敏感度

同切分比較：梯度提升與邏輯迴歸（常規套組）、常規套組與全特徵（邏輯迴歸）、含與不含 HDL、各模型與只用年齡性別。近端特徵消融沿用 v3 之定義：全特徵邏輯迴歸含與不含近端特徵，以同一切分比較。

時間外推以 1999–2008 年開發、2009–2018 年評估（常規套組之邏輯迴歸與梯度提升）；另以擴展視窗逐週期評估網頁工具模型族（每一評估週期只用更早週期訓練）。較晚週期先前已被檢視，屬回溯時間評估。調查權重以合併 20 年 MEC 權重（1999–2002 年四年權重 × 4/20，其後兩年權重 × 2/20）[@weight] 計算加權盛行率、平均預測、AUROC 與 AP；設計變異依分層（SDMVSTRA，各週期編號互不重複）與 PSU（SDMVPSU），以刪一 PSU 摺刀法建立複製權重[@rustrao]，比例之 95% CI 採 NCHS 比例呈現標準之 Korn–Graubard 法[@parker]，其他指標為估計值 ± t × 標準誤，自由度為 PSU 數減層數；預測視為固定，不含模型重新配適的變異（方法計畫 {CM['dv_plan']}）。腎臟指標判定之敏感度：2017–2018 年改用原發布肌酸酐判定腎臟指標，重做主要分析。標籤定義敏感度：僅 HBsAg、僅 HCV RNA、僅糖尿病問卷、僅 HbA1c、排除邊緣回答，皆以常規套組邏輯迴歸重建模。

### 2.8　決策曲線與每千人情境

決策曲線以淨效益 NB ＝ TP/N − FP/N × pt/(1 − pt) 比較「依模型送驗」「全數送驗」「全不送驗」[@vickers]。閾值機率 pt 應反映實際檢驗的利弊；肝炎檢驗便宜、無創，且美國建議成人至少篩檢一次 C 型肝炎[@hcvscreen] 與 B 型肝炎[@hbv]，相當於極低的 pt。每千人情境直接取外層預測之分區結果，並套用資料不足規則。

### 2.9　暴露關聯（探索性）

以全體成人（不對腎臟結果條件化）掃描 {EXW['n_scanned']} 個暴露與三值腎臟結果之關聯。五層調整為 M0 未調整；M1 年齡、性別、種族；M2 再加 BMI 與吸菸；M3 再加糖尿病與高血壓；M4（僅藥物）再加總用藥數。多重比較的檢定家族定義為 M3 之 {EXW['n_scanned']} 個雙尾 p 值，以 Benjamini–Hochberg 法控制偽發現率[@bh]；其他層級只作敏感度。0/1 藥物暴露報告「使用 vs 未使用」之勝算比，連續暴露為每 1 SD。v2 比較血中與尿中金屬時，血中值只來自 1999–2004 年、尿中值只來自 2005–2018 年，沒有任何共同受試者；v3 修正合併，並在同時有血、尿值的同一批受試者中，以相同 M3 調整、log2 量尺（勝算比為濃度加倍），比較血中、尿中原濃度、原濃度加尿肌酸酐共變數[@barr]、肌酸酐比值四種寫法，對三種結果定義：腎臟指標異常、僅 eGFR < 60、僅 ACR ≧ 30。

暴露分析以 v3.2 之資料修正重跑（計畫與程式先提交 {CM['exw_plan']}）：只把 2017–2018 年生化換成 DxC 660i 量尺，方法、暴露清單、調整層、偽發現率與對照皆與 v3 相同；C1 改名之變數與肝炎封存都不在暴露分析的暴露、共變項或結果定義內。換算使 2017–2018 年 {EC['label_changes']['n_changed']} 人的腎臟結果改變（{LC.get(('異常', '正常'), 0)} 人由異常改為正常、{LC.get(('異常', '未知'), 0)} 人改為未知）；兩版資料的暴露與共變項逐格相同，因此 v3 之結果即「2017–2018 年沿用原發布肌酸酐」之敏感度分析。

### 2.10　外部資料：NHANES 2021–2023

2021–2023 年資料自 2024 年 9 月起分批釋出，其中生化（BIOPRO_L）、尿白蛋白與肌酸酐（ALB_CR_L）與空腹三酸甘油酯（TRIGLY_L）三檔於 2025 年 9 月釋出[@biopro_l,albcr_l,trigly_l]，從未參與 v3 之開發決策。v3 在取用前凍結三個模型（部署之全特徵邏輯迴歸、常規套組邏輯迴歸、全特徵梯度提升）與評估規則，記錄其 SHA256 與 17 個待取用檔案（約 {PR['total_bytes'] / 1e6:.1f} MB）；程式只允許評估一次，且不重新配適、不重新校準、不調整門檻（`params/external_validation_protocol.json`，提交 {CM['proto']}）。取用後、計算任何預測之前，逐檔核對 CDC 文件發現：生化儀器由 Cobas 6000 換為 Cobas 8000[@biopro_l]；尿白蛋白由螢光免疫法改為液相層析串聯質譜[@albcr_l]；空腹三酸甘油酯改為非甘油空白法並更名[@trigly_l]；維生素 D 亦更名。因此於評估前提交修正一（`params/external_validation_amendment_1.json`，提交 {CM['amend']}）：凡 CDC 文件建議用於與 2017–2020 年比較的回推式，對模型或標籤用到的變數一律套用（{len(XAM['conversions'])} 項，補充表 S3）；更名者對應回原名；模型、校準、門檻與指標皆不變；依凍結程式原樣、不調和的結果列為事前指定的敏感度分析。一次評估之結果見提交 {CM['ext']}。

v3.2 事後評估：v3.2 模型在修正後之開發資料重新訓練；2021–2023 年數值先依修正一換回 Cobas 6000 量尺，再依 BIOPRO_J 換回 DxC 660i 量尺，與 v3.2 開發資料一致。這批資料已用於 v3 之一次評估與網頁工具 v3.1 的重新校準（{CM['tool_v31']}），v3.2 之外部數字皆屬事後分析。除 MEC 權重外，另以 NCHS 為抽血項目另設之抽血權重（WTPH2YR）加權作敏感度。與只用年齡、性別模型之外部比較，是獨立稽核（2.12）發現原稿以外部結果對照內部基準之後才補做，亦屬事後分析。

### 2.11　網頁工具 v3.2 與重新校準之交叉驗證

網頁工具採常規套組邏輯迴歸，在看到 v3.2 結果之前即決定：工具必須逐項顯示推動因子，邏輯迴歸可由係數直接說明；梯度提升只作比較。以全部 v3.2 開發資料訓練後，依與 v3.1 相同之規則以 2021–2023 年資料更新校準：陽性至少 100 個且斜率概似比檢定 p < 0.05 才同時更新截距與斜率，否則只更新截距[@vergouwe]；事前機率改為 2021–2023 年該軸比例，分區門檻依勝算規則重算。更新後之校準為表面值。為估計此步驟之可靠度，依抽樣設計把 2021–2023 年資料切半 200 次（每層兩個 PSU 隨機各分一半，隨機種子 20260927），在訓練半依同一規則（含是否更新斜率之判斷、事前機率與門檻）重新校準、在測試半評估，並與不重新校準比較；另報告一個固定切分（PSU 1 訓練、PSU 2 測試）。網頁為單一離線檔案，其計算以 Node.js 與 Python 逐軸核對。

### 2.12　獨立稽核

定稿前以另一個 AI 工具（Codex，唯讀）獨立檢查資料處理與評估程式、以及文件數字與結果檔欄位之對應。四支資料與評估程式未發現問題；文件對應發現三項問題（分區統計未套用資料不足規則、外部比較之年齡性別基準取自內部、特徵數描述不精確），逐項查證屬實後修正（4.3；提交 {CM['audit']}）。

### 2.13　免疫方向（抗核抗體次樣本）

計畫 {CM['imm_plan']} 先提交後執行。樣本為腎臟指標異常成人中屬 1999–2004 年剩餘血清次樣本者；模型、切分、種子與同切分基準均同 2.5 與 2.7。只有三個週期且為次樣本，事前寫定不做時間外推、調查權重與外部評估。判定規則事前寫定：常規套組邏輯迴歸相對只用年齡、性別之配對 ΔAUROC 95% CI 下界大於 0，才判為「可回推」。

## 3　結果

### 3.1　資料更正與分析樣本

{{FIG1}}

**圖1　分析樣本、三值標籤與 v3.2 資料修正。** 感染（肝炎）與代謝（糖尿病）兩個方向的標籤在腎臟指標異常者中各自判定（免疫方向為另一次樣本，見 3.9）。

依 v2 定義重建之計數與原稿完全一致（v3 稽核：成人 {n(old['n_adults'])}、可判定 {n(old['outcome_known_old_rule'])}、腎臟異常 {n(old['kidney'])}、肝炎 {old['hep']}、糖尿病 {n(old['dm'])}），確認比較基準正確。v3.2 之修正只改變 2017–2018 年的計數，其他九個週期的腎臟、肝炎與糖尿病三值計數與 v3 完全相同。

**表1　資料更正前後的樣本與標籤**

| 項目 | 原稿（v2） | v3 | v3.2 | 說明 |
|---|---|---|---|---|
| 成人 | {n(old['n_adults'])} | {n(T3['adults'])} | {n(C['adults'])} | — |
| 腎臟結果可判定 | {n(old['outcome_known_old_rule'])} | {n(kd_known3)} | {n(kd_known32)} | v3：一項正常另一項缺失者改列未知；v3.2：2017–2018 年 {CH1718.get('1→-1', 0)} 人改為未知 |
| 腎臟指標異常 | {n(old['kidney'])} | {n(T3['kidney']['pos'])} | {n(C['kidney']['pos'])} | v3：新增 {RC3['combined']['gained']}、移出 {RC3['combined']['lost']}；v3.2：2017–2018 年 {CH1718.get('1→0', 0)} 人改為正常、{CH1718.get('1→-1', 0)} 人改為未知 |
| 1999–2000 年 eGFR < 60 | {RC3['scr_fix_1999_2000']['egfr_lt60_old']} | {RC3['scr_fix_1999_2000']['egfr_lt60_new']} | 同 v3 | 血清肌酸酐公式更正 |
| ACR 跨越 30 mg/g | — | 增 {RC3['ucr_fix_pre2007']['acr_cross30_up']}、減 {RC3['ucr_fix_pre2007']['acr_cross30_down']} | 同 v3 | 2007 年前尿肌酸酐轉換 |
| 肝炎標籤 陽／陰／未知 | {old['hep']}／{n(old['kidney'] - old['hep'])}／— | {T3['hep_in_kidney']['pos']}／{n(T3['hep_in_kidney']['neg'])}／{T3['hep_in_kidney']['unknown']} | {C['hep_in_kidney']['pos']}／{n(C['hep_in_kidney']['neg'])}／{C['hep_in_kidney']['unknown']} | v3.2：HBsAg 陽性 {C['hbv_in_kidney']['pos']}、HCV RNA 陽性 {C['hcv_in_kidney']['pos']}（兩者皆陽 {C['both_hbv_and_hcv']}） |
| 糖尿病標籤 陽／陰／未知 | {n(old['dm'])}／{n(old['kidney'] - old['dm'])}／— | {n(T3['dm_in_kidney']['pos'])}／{n(T3['dm_in_kidney']['neg'])}／{T3['dm_in_kidney']['unknown']} | {n(C['dm_in_kidney']['pos'])}／{n(C['dm_in_kidney']['neg'])}／{C['dm_in_kidney']['unknown']} | v3.2：問卷陽性 {n(C['dmq_in_kidney']['pos'])}、HbA1c 陽性 {n(C['dma_in_kidney']['pos'])} |
| 兩標籤皆陽性 | 70（推算） | {A3['two_label_crosstab_in_kidney']['陽性']['陽性']} | {X2['陽性']['陽性']} | 逐人交叉表 |
| 候選特徵 | — | {A3['n_features_v3']} | {EV['n_features']} | v3.2 補回 HDL |
| 2001–2002 年四項常規生化 | — | 整週期缺值 | 有值 {pct(AV0102, 0)} | 改名對應 |
| 2017–2018 年生化量尺 | — | Cobas 6000 原值 | 換回 DxC 660i 量尺 | BIOPRO_J 回推式（補充表 S4） |

註：{n(C['kidney']['pos'])} ／ {n(kd_known32)} ＝ {pct(C['kidney']['pos'] / kd_known32, 2)} 為未加權樣本比例，不是人口盛行率。逐週期計數見補充表 S1。2017–2018 年換算後，12 項中有 {len(closer)} 項的中位數比換算前更接近 2015–2016 年（補充表 S4）。

### 3.2　判別力與同切分基準

{{FIG2}}

**圖2　判別力。** 點為五次重複平均，線為五次重複之最小至最大。

**表2　判別力（巢狀外層評估，五次重複平均；95% CI 為第一次重複）**

| 項目 | 肝炎病毒感染標籤 | 糖尿病標籤 |
|---|---|---|
| n（陽性；盛行率） | {H['n']}（{H['pos']}；{H['prev']}） | {D['n']}（{D['pos']}；{D['prev']}） |
| 常規套組 LR（網頁工具模型族）AUROC（95% CI） | **{H['m'][LR]['auc']}**（{H['m'][LR]['auc_ci']}） | **{D['m'][LR]['auc']}**（{D['m'][LR]['auc_ci']}） |
| 　AP（95% CI） | **{H['m'][LR]['ap']}**（{H['m'][LR]['ap_ci']}） | **{D['m'][LR]['ap']}**（{D['m'][LR]['ap_ci']}） |
| 　AP ÷ 盛行率；梯形 PR-AUC | {H['ap_lift']}；{H['m'][LR]['prauc']} | {D['ap_lift']}；{D['m'][LR]['prauc']} |
| 　五次重複 AUROC 範圍 | {H['m'][LR]['rng']} | {D['m'][LR]['rng']} |
| 常規套組 LR 不含 HDL AUROC／AP | {H['m'][LRN]['auc']}／{H['m'][LRN]['ap']} | {D['m'][LRN]['auc']}／{D['m'][LRN]['ap']} |
| 常規套組梯度提升 AUROC（95% CI）／AP | {H['m'][HG]['auc']}（{H['m'][HG]['auc_ci']}）／{H['m'][HG]['ap']} | **{D['m'][HG]['auc']}**（{D['m'][HG]['auc_ci']}）／{D['m'][HG]['ap']} |
| 全特徵 LR AUROC／AP | {H['m'][LF]['auc']}／{H['m'][LF]['ap']} | {D['m'][LF]['auc']}／{D['m'][LF]['ap']} |
| 全特徵梯度提升 AUROC／AP | {H['m'][HF]['auc']}／{H['m'][HF]['ap']} | {D['m'][HF]['auc']}／{D['m'][HF]['ap']} |
| 只用年齡、性別 AUROC／AP | {H['m1']}／{H['m1ap']} | {D['m1']}／{D['m1ap']} |
| 常規套組 LR − 年齡性別：ΔAUROC | {H['d1']}（{H['d1_ci']}）；平均 {H['md1']} | {D['d1']}（{D['d1_ci']}）；平均 {D['md1']} |
| 梯度提升 − LR（常規套組）：ΔAUROC | {H['dg']}（{H['dg_ci']}）；平均 {H['mdg']} | {D['dg']}（{D['dg_ci']}）；平均 {D['mdg']} |
| 　ΔAP | {H['dgap']}（{H['dgap_ci']}）；平均 {H['mdgap']} | {D['dgap']}（{D['dgap_ci']}）；平均 {D['mdgap']} |
| 常規套組 − 全特徵（LR）：ΔAUROC | {H['drf']}（{H['drf_ci']}）；平均 {H['mdrf']} | {D['drf']}（{D['drf_ci']}）；平均 {D['mdrf']} |
| 含 − 不含 HDL（常規套組 LR）：ΔAUROC | {H['dh']}（{H['dh_ci']}）；平均 {H['mdh']} | {D['dh']}（{D['dh_ci']}）；平均 {D['mdh']} |

註：Δ 各格前為第一次重複之配對差與其 95% CI（同一批受試者重抽，不含重新配適變異），「平均」為五次重複平均之差（與表中平均值相減一致）；差值皆由未四捨五入之值計算。

兩軸的判別力都主要來自檢驗而非人口學：只用年齡與性別時 AUROC 僅 {H['m1']} 與 {D['m1']}，常規套組邏輯迴歸平均高出 {H['md1'][1:]} 與 {D['md1'][1:]}。以下配對差皆取第一次重複。肝炎軸以常規套組即可達到全特徵的判別力（配對差 {H['drf']}，95% CI {H['drf_ci']}），梯度提升沒有優勢（配對差 {H['dg']}，{H['dg_ci']}；五次重複平均差 {H['mdg']}）。糖尿病軸則相反：梯度提升明顯高於邏輯迴歸（配對差 ΔAUROC {D['dg']}，{D['dg_ci']}；ΔAP {D['dgap']}，{D['dgap_ci']}），顯示線性模型未能捕捉糖尿病訊號的非線性結構；常規套組比全特徵低 {D['drf'][1:]}（{D['drf_ci']}），差距小。補回 HDL 對糖尿病軸 ΔAUROC {D['dh']}（{D['dh_ci']}），對肝炎軸 {H['dh']}（{H['dh_ci']}），影響都小。

近端特徵消融（全特徵邏輯迴歸，同一切分）：肝炎軸移除{H['ab_removed']}後，AUROC 由 {H['ab_with']} 降為 {H['ab_without']}（差 {H['ab_d'][1:]}，95% CI {H['ab_ci']}）；糖尿病軸移除{D['ab_removed']}後，由 {D['ab_with']} 降為 {D['ab_without']}（差 {D['ab_d'][1:]}，{D['ab_ci']}）。這些差值表示模型依賴被移除的資訊，不代表先前較高的分數是洩漏。

**標籤定義敏感度。** 僅以 HCV RNA 為標籤時（陽性 {HCV1['n_pos']} 人）AUROC {p3(HCV1['auroc'])}、AP {p3(HCV1['ap'])}；僅以 HBsAg 為標籤時（陽性 {HBV1['n_pos']} 人）AUROC {p3(HBV1['auroc'])}、AP {p3(HBV1['ap'])}，AP 與盛行率 {pct(HBV1['prevalence'], 2)} 幾乎相同。**肝炎軸的訊號幾乎全部來自 C 型肝炎。** 以肝炎軸第一次重複之外層預測分型：C 型陽性 {ST['C型_HCV_RNA']['n_pos']} 人對陰性者 AUROC {p3(ST['C型_HCV_RNA']['auroc'])}（{ci(ST['C型_HCV_RNA']['ci95']['auroc'])}），B 型陽性 {ST['B型_HBsAg']['n_pos']} 人 {p3(ST['B型_HBsAg']['auroc'])}（{ci(ST['B型_HBsAg']['ci95']['auroc'])}）。糖尿病軸對標籤定義不敏感：僅問卷 {p3(LS['僅問卷_DIQ010']['auroc'])}、僅 HbA1c {p3(LS['僅HbA1c']['auroc'])}、排除邊緣回答 {p3(LS['排除邊緣_DIQ010=3']['auroc'])}。

### 3.3　校準與三段分區：線性與非線性模型

{{FIG3}}

**圖3　校準與分區。** 校準曲線以分位數分箱；右欄為三段分區之實際陽性比例（依工具規則，資料不足者不給方向）。

**表3　校準與分區（第一次重複之外層預測）**

| 指標 | 肝炎・邏輯迴歸 | 肝炎・梯度提升 | 糖尿病・邏輯迴歸 | 糖尿病・梯度提升 |
|---|---|---|---|---|
| 校準截距 | {H['m'][LR]['cint']} | {H['m'][HG]['cint']} | {D['m'][LR]['cint']} | {D['m'][HG]['cint']} |
| 校準斜率 | {H['m'][LR]['cslope']} | {H['m'][HG]['cslope']} | {D['m'][LR]['cslope']} | {D['m'][HG]['cslope']} |
| Brier（skill） | {H['m'][LR]['brier']}（{H['m'][LR]['bss']}） | {H['m'][HG]['brier']}（{H['m'][HG]['bss']}） | {D['m'][LR]['brier']}（{D['m'][LR]['bss']}） | {D['m'][HG]['brier']}（{D['m'][HG]['bss']}） |
| 傾向區實際陽性率 | {H['m'][LR]['hi']} | {H['m'][HG]['hi']} | {D['m'][LR]['hi']} | {D['m'][HG]['hi']} |
| 不確定區實際陽性率 | {H['m'][LR]['mid']} | {H['m'][HG]['mid']} | {D['m'][LR]['mid']} | {D['m'][HG]['mid']} |
| 不傾向區實際陽性率 | {H['m'][LR]['lo']} | {H['m'][HG]['lo']} | {D['m'][LR]['lo']} | {D['m'][HG]['lo']} |
| 資料不足（不給方向） | {H['m'][LR]['insuff']} | {H['m'][HG]['insuff']} | {D['m'][LR]['insuff']} | {D['m'][HG]['insuff']} |
| 能給出方向的比例 | {H['m'][LR]['cov']} | {H['m'][HG]['cov']} | {D['m'][LR]['cov']} | {D['m'][HG]['cov']} |

註：能給出方向的比例＝（傾向＋不傾向）人數／全部人數。

兩種模型經同樣的保序校準後都接近理想。糖尿病軸的梯度提升校準截距 {D['m'][HG]['cint']}、斜率 {D['m'][HG]['cslope']}，Brier 較邏輯迴歸低（差 {D['dgb']}，95% CI {D['dgb_ci']}），能給出方向的比例由 {D['m'][LR]['cov']} 升至 {D['m'][HG]['cov']}，傾向區與不傾向區分得更開（{D['m'][HG]['hi']} 對 {D['m'][HG]['lo']}）。肝炎軸的梯度提升斜率 {H['m'][HG]['cslope']}、能給出方向的比例只有 {H['m'][HG]['cov']}，沒有優於邏輯迴歸。

**表4　肝炎病毒感染標籤之分區（常規套組邏輯迴歸；第一次重複之外層預測）**

{six_table(H, '肝炎')}

**表5　糖尿病標籤之分區（常規套組邏輯迴歸）**

{six_table(D, '糖尿病')}

肝炎軸落在「不傾向」區的陽性 {H['m'][LR]['low_pos']} 人，占全部陽性 {pct(H['m'][LR]['low_pos'] / H['npos'], 0)}。糖尿病軸資料不足者 {D['m'][LR]['insuff']} 人中糖尿病比例 {D['m'][LR]['insuff_rate']}，高於全體（{D['prev']}），提示部分沒有抽血資料者是由問卷判定為糖尿病。以全體開發資料之盛行率計算之勝算門檻：肝炎軸傾向 ≧ {pct(H['thr'][0], 2)}、不傾向 ≦ {pct(H['thr'][1], 2)}；糖尿病軸傾向 ≧ {pct(D['thr'][0])}、不傾向 ≦ {pct(D['thr'][1])}（網頁工具 v3.2 改用 2021–2023 年事前機率，見 3.8）。

### 3.4　時間外推、調查權重與標籤定義

{{FIG4}}

**圖4　穩健性：時間外推（1999–2008 訓練、2009–2018 評估）、人口加權（設計 CI）與腎臟標籤定義。**

以 1999–2008 年開發、2009–2018 年評估：肝炎軸邏輯迴歸 AUROC {H['t'][LR]['auc']}（95% CI {H['t'][LR]['auc_ci']}；n {H['t'][LR]['n']}、陽性 {H['t'][LR]['pos']}）、梯度提升 {H['t'][HG]['auc']}（{H['t'][HG]['auc_ci']}）；糖尿病軸邏輯迴歸 {D['t'][LR]['auc']}（{D['t'][LR]['auc_ci']}）、梯度提升 {D['t'][HG]['auc']}（{D['t'][HG]['auc_ci']}）。盛行率隨年代上升（肝炎 {H['t'][LR]['ptr']} → {H['t'][LR]['pte']}，糖尿病 {D['t'][LR]['ptr']} → {D['t'][LR]['pte']}），使較晚週期的平均預測偏低：校準截距肝炎軸 {H['t'][LR]['cint']}（梯度提升 {H['t'][HG]['cint']}），糖尿病軸 {D['t'][LR]['cint']}（梯度提升 {D['t'][HG]['cint']}）；梯度提升的偏移較小。

**表6　擴展視窗之逐週期 AUROC（常規套組邏輯迴歸；每一評估週期只用更早週期訓練）**

| 評估週期 | 肝炎：n | 肝炎：陽性 | 肝炎：AUROC（95% CI） |
|---|---|---|---|
{H['ew_rows']}

| 評估週期 | 糖尿病：n | 糖尿病：陽性 | 糖尿病：AUROC（95% CI） |
|---|---|---|---|
{D['ew_rows']}

肝炎軸逐週期 AUROC 由 {H['ew_min']}（{H['ew_min_c']}）到 {H['ew_max']}（{H['ew_max_c']}），單一週期陽性僅 {H['ew_pos']} 人，區間很寬；糖尿病軸 {D['ew_min']}–{D['ew_max']}，相當穩定。

以 MEC 權重加權，並依抽樣設計估計變異（{DV['design']['internal']['strata']} 層、{DV['design']['internal']['psu']} 個 PSU，自由度 {H['w'][LR]['df']}）：肝炎軸加權盛行率 {H['w'][LR]['prev']}（95% CI {H['w'][LR]['prev_ci']}；未加權 {H['w'][LR]['uw_prev']}；設計效應 {H['w'][LR]['deff']}），邏輯迴歸加權 AUROC {H['w'][LR]['auc']}（{H['w'][LR]['auc_ci']}）、梯度提升 {H['w'][HG]['auc']}（{H['w'][HG]['auc_ci']}）；糖尿病軸加權盛行率 {D['w'][LR]['prev']}（{D['w'][LR]['prev_ci']}；未加權 {D['w'][LR]['uw_prev']}；設計效應 {D['w'][LR]['deff']}），邏輯迴歸 {D['w'][LR]['auc']}（{D['w'][LR]['auc_ci']}）、梯度提升 {D['w'][HG]['auc']}（{D['w'][HG]['auc_ci']}）。糖尿病軸的加權平均預測高於加權盛行率：邏輯迴歸 {D['w'][LR]['cd']} 個百分點（95% CI {D['w'][LR]['cd_ci']}）、梯度提升 {D['w'][HG]['cd']}（{D['w'][HG]['cd_ci']}），區間都不含 0，顯示機率不能直接移植到抽樣組成不同的人群；肝炎軸為 {H['w'][LR]['cd']}（{H['w'][LR]['cd_ci']}），包含 0。

2017–2018 年改用原發布肌酸酐判定腎臟指標時（肝炎軸 n {n(H['kr']['n'])}、糖尿病軸 n {n(D['kr']['n'])}），邏輯迴歸 AUROC 為 {p3(H['kr'][LR]['auroc'])} 與 {p3(D['kr'][LR]['auroc'])}、梯度提升 {p3(H['kr'][HG]['auroc'])} 與 {p3(D['kr'][HG]['auroc'])}，與主分析幾乎相同。

### 3.5　決策曲線與每千人情境

{{FIG5}}

**圖5　決策曲線。** 閾值機率須由實際檢驗之利弊決定。

肝炎軸在 pt ＝ 0.5% 時，依模型送驗與全數送驗的淨效益幾乎相同（模型 {H['dca'][0.005]['nb_model']:.4f}、全數送驗 {H['dca'][0.005]['nb_test_all']:.4f}）；pt 為 1% 時模型較高（{H['dca'][0.01]['nb_model']:.4f} 對 {H['dca'][0.01]['nb_test_all']:.4f}）。由於肝炎血清檢驗便宜、無創，且指引建議成人普遍篩檢[@hbv,hcvscreen]，合理的 pt 很低，**本工具不宜用來決定誰可以不驗肝炎**。若只略過「不傾向」區（資料不足者照常送驗），每千人送驗 {H['m'][LR]['t1000']} 人、漏掉 {H['m'][LR]['m1000']} 名陽性（占陽性 {H['m'][LR]['mshare']}）。糖尿病軸在 pt {DM_DCA[0]:.0%}–{DM_DCA[1]:.0%} 的每個點，兩種模型的淨效益都高於全數送驗與全不送驗（{DM_DCA[0]:.0%} 時與全數送驗差距很小：{D['dca'][0.1]['nb_model']:.4f} 對 {D['dca'][0.1]['nb_test_all']:.4f}），且梯度提升都高於邏輯迴歸；若只略過不傾向區，每千人送驗 {D['m'][LR]['t1000']} 人、漏 {D['m'][LR]['m1000']} 名陽性（占 {D['m'][LR]['mshare']}）。以上為點估計。

### 3.6　暴露關聯（探索性）

結果可判定之成人 {n(EXW['cohort']['n_outcome_known'])} 人、腎臟指標異常 {n(EXW['cohort']['n_kidney_damage'])} 人。{EXW['n_scanned']} 個暴露中 {EXW['n_significant_fdr05']} 個於 M3 通過偽發現率 0.05；陽性對照命中 {len(EXW['control_check']['positive_hits'])}/{EXW['control_check']['n_positive_scanned']}（鈣調磷酸酶抑制劑、質子幫浦抑制劑），陰性對照 {len(EXW['control_check']['negative_hits'])}/{EXW['control_check']['n_negative_scanned']}；砷的毒性形式與砷貝他因皆未達顯著。與 v3（2017–2018 年用原發布之肌酸酐）相比，結果可判定者少 {ER['cohort']['v3']['n_outcome_known'] - ER['cohort']['v3_2']['n_outcome_known']} 人、腎臟指標異常少 {ER['cohort']['v3']['n_kidney_damage'] - ER['cohort']['v3_2']['n_kidney_damage']} 人；沒有任何暴露改變顯著與否，對數勝算比的最大變動為尿中亞砷酸之 {abs(ER['max_abs_dlogOR']['dlogOR']):.3f}（勝算比 {ER['max_abs_dlogOR']['OR_v3']:.3f} → {ER['max_abs_dlogOR']['OR_v3_2']:.3f}），對照與砷之判定、表 8 各格 p < 0.05 與否皆不變。

**表7　偽發現率最低的 12 項暴露（M3）**

{sig_table()}

藥物關聯與處方常規一致：用於腎病或其共病的藥（利尿劑、胰島素、別嘌醇、ACEI／ARB）與腎臟異常正相關，腎功能差時應停用的雙胍類呈負相關（OR {xo('藥_雙胍')['OR']:.3f}）；教科書腎毒物 NSAID 不顯著（OR {xo('藥_NSAID')['OR']:.3f}，q ＝ {Xr['藥_NSAID']['q_bh']:.2f}）。這些方向可由適應症混雜與反向因果解釋，不能作為藥物致病或護腎的證據。

{{FIG6}}

**圖6　同一批受試者之血中與尿中鉛、鎘。** 勝算比為濃度加倍，M3 調整。

**表8　同一批有血、尿值之受試者（n ＝ {n(Pb['n_both'])}；僅 eGFR < 60 之模型 n ＝ {n(min(v['n'] for v in Pb['models']['egfr_lt60'].values()))}）之血中與尿中金屬（OR 為濃度加倍，95% CI）**

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

在同一批人中，血鉛與血鎘對三種結果定義都呈正相關；尿中金屬的方向則取決於結果定義與寫法。對與尿肌酸酐無共同分母的 eGFR < 60，尿鉛原濃度即呈負相關，OR {orr(mo(Pb, 'egfr_lt60', '尿中_原濃度'))}，加入尿肌酸酐後更明顯——與「腎絲球過濾下降使尿中排出減少」相符。對 ACR ≧ 30，肌酸酐比值寫法的尿鎘 OR {orr(mo(Cd, 'acr_ge30', '尿中_肌酸酐比值'))}，明顯高於原濃度的 {orr(mo(Cd, 'acr_ge30', '尿中_原濃度'))}，部分來自與 ACR 共用的尿肌酸酐分母。這些模式支持排泄與分母機制值得檢查，但單次橫斷面資料不能排除真實暴露效應、殘餘混雜或測量誤差，也不能把 {EXW['n_significant_fdr05']} 個關聯一律歸為反向因果。

### 3.7　外部資料（NHANES 2021–2023）

{{FIG7}}

**圖7　NHANES 2021–2023：v3 事前指定之一次評估（灰）與 v3.2 事後評估（彩色）。**

#### 3.7.1　v3 事前指定之一次評估（照原樣保留）

2021–2023 年成人中，腎臟指標異常 {n(XK['pos'])} 人（依凍結程式原樣為 {n(SK['pos'])} 人，差異來自尿白蛋白回推），無法判定 {n(XK['unknown'])} 人。肝炎軸可判定 {XH['n']} 人、陽性 {XH['pos']} 人（HBsAg 陽性 {HC['hbsag_pos']}、HCV RNA 陽性 {HC['hcv_rna_pos']}）；糖尿病軸可判定 {XD['n']} 人、陽性 {XD['pos']} 人。

**表9　v3 事前指定之外部確認（主要分析：修正一調和後）**

| 項目 | 肝炎病毒感染標籤 | 糖尿病標籤 |
|---|---|---|
| n（陽性；盛行率） | {XH['n']}（{XH['pos']}；{XH['prev']}） | {XD['n']}（{XD['pos']}；{XD['prev']}） |
| 部署模型（全特徵 LR）AUROC（95% CI） | {XH['auc']}（{XH['auc_ci']}） | {XD['auc']}（{XD['auc_ci']}） |
| 部署模型 AP（95% CI） | {XH['ap']}（{XH['ap_ci']}） | {XD['ap']}（{XD['ap_ci']}） |
| 校準截距／斜率 | {XH['cint']}／{XH['cslope']} | {XD['cint']}／{XD['cslope']} |
| 平均預測／實際陽性比例 | {XH['meanpred']}／{XH['obs']} | {XD['meanpred']}／{XD['obs']} |
| 常規套組 LR AUROC（95% CI） | {XH['bauc']}（{XH['bauc_ci']}） | {XD['bauc']}（{XD['bauc_ci']}） |
| 常規套組 − 部署：ΔAUROC（配對 95% CI） | {XH['dbf']}（{XH['dbf_ci']}） | {XD['dbf']}（{XD['dbf_ci']}） |
| 全特徵梯度提升 AUROC／AP | {XH['gauc']}／{XH['gap']} | {XD['gauc']}／{XD['gap']} |
| MEC 加權 AUROC（設計 95% CI） | {XDH['auc']}（{XDH['auc_ci']}） | {XDD['auc']}（{XDD['auc_ci']}） |
| 敏感度：依凍結程式原樣 AUROC | {SH['auc']}（{SH['auc_ci']}） | {SD['auc']}（{SD['auc_ci']}） |

註：梯度提升依協定只評判別；加權指標之信賴區間依 2021–2023 年抽樣設計（{DV['design']['external']['strata']} 層、{DV['design']['external']['psu']} 個 PSU，自由度 {XDH['df']}）以刪一 PSU 摺刀法於一次評估之後補算（{CM['dv_res']}）。v3 模型以含前述資料錯誤之開發資料訓練；本表為當時事前指定之結果，照原樣保留。

糖尿病軸部署模型 AUROC {XD['auc']}，常規套組模型 {XD['bauc']}（較部署模型高 {XD['dbf'][1:]}，配對 95% CI {XD['dbf_ci']}）；肝炎軸只有 {XH['pos']} 名陽性，AUROC {XH['auc']}（{XH['auc_ci']}）無法確認，平均預測為實際的 {XH['ratio_pred']} 倍。一次評估之後的事後探索：部署模型含六項在開發資料中只有 1999–2004 年有值的非常規特徵，2021–2023 年腎臟指標異常者的中位數分別為開發時的 {xr('LBXBPB')}（血鉛）、{xr('LBXBCD')}（血鎘）、{xr('LBXTHG')}（血汞）、{xr('LBXCOT')}（可丁尼）、{xr('LBXFER')}（鐵蛋白）、{xr('LBDVIDMS')}（維生素 D）倍；把這六項改為缺值後，糖尿病軸 AUROC 由 {ph(PHD)}。此發現促成網頁工具 v3.1 改用常規套組模型。

#### 3.7.2　v3.2 事後評估

v3.2 評估資料：成人 {n(XDATA['n_adults'])} 人、腎臟指標異常 {n(XDATA['kidney']['pos'])} 人；肝炎軸 {n(X['肝炎']['n'])} 人（陽性 {X['肝炎']['n_pos']}）、糖尿病軸 {n(X['糖尿病']['n'])} 人（陽性 {X['糖尿病']['n_pos']}）。與 v3 之差異來自 2021–2023 年數值再經 BIOPRO_J 換回 DxC 660i 量尺（腎臟指標異常 {n(XK['pos'])} → {n(XDATA['kidney']['pos'])}）。

**表10　v3.2 事後評估（2021–2023）**

| 模型 | 肝炎：AUROC（95% CI） | 肝炎：校準截距／斜率 | 糖尿病：AUROC（95% CI） | 糖尿病：校準截距／斜率 |
|---|---|---|---|---|
| 只用年齡、性別（稽核後補做） | {XM1['肝炎']['auc']}（{XM1['肝炎']['auc_ci']}） | — | {XM1['糖尿病']['auc']}（{XM1['糖尿病']['auc_ci']}） | — |
| 常規套組 LR（重新校準前） | {XS2['肝炎'][LR]['auc']}（{XS2['肝炎'][LR]['auc_ci']}） | {XS2['肝炎'][LR]['cint']}／{XS2['肝炎'][LR]['cslope']} | {XS2['糖尿病'][LR]['auc']}（{XS2['糖尿病'][LR]['auc_ci']}） | {XS2['糖尿病'][LR]['cint']}／{XS2['糖尿病'][LR]['cslope']} |
| 常規套組 LR 不含 HDL | {XS2['肝炎'][LRN]['auc']}（{XS2['肝炎'][LRN]['auc_ci']}） | {XS2['肝炎'][LRN]['cint']}／{XS2['肝炎'][LRN]['cslope']} | {XS2['糖尿病'][LRN]['auc']}（{XS2['糖尿病'][LRN]['auc_ci']}） | {XS2['糖尿病'][LRN]['cint']}／{XS2['糖尿病'][LRN]['cslope']} |
| 常規套組梯度提升 | {XS2['肝炎'][HG]['auc']}（{XS2['肝炎'][HG]['auc_ci']}） | {XS2['肝炎'][HG]['cint']}／{XS2['肝炎'][HG]['cslope']} | {XS2['糖尿病'][HG]['auc']}（{XS2['糖尿病'][HG]['auc_ci']}） | {XS2['糖尿病'][HG]['cint']}／{XS2['糖尿病'][HG]['cslope']} |
| 全特徵 LR | {XS2['肝炎'][LF]['auc']}（{XS2['肝炎'][LF]['auc_ci']}） | {XS2['肝炎'][LF]['cint']}／{XS2['肝炎'][LF]['cslope']} | {XS2['糖尿病'][LF]['auc']}（{XS2['糖尿病'][LF]['auc_ci']}） | {XS2['糖尿病'][LF]['cint']}／{XS2['糖尿病'][LF]['cslope']} |
| 全特徵梯度提升 | {XS2['肝炎'][HF]['auc']}（{XS2['肝炎'][HF]['auc_ci']}） | {XS2['肝炎'][HF]['cint']}／{XS2['肝炎'][HF]['cslope']} | {XS2['糖尿病'][HF]['auc']}（{XS2['糖尿病'][HF]['auc_ci']}） | {XS2['糖尿病'][HF]['cint']}／{XS2['糖尿病'][HF]['cslope']} |
| v3 常規套組 LR（凍結，DxC 量尺） | {XS2['肝炎']['v3_basic_LR（凍結）']['auc']}（{XS2['肝炎']['v3_basic_LR（凍結）']['auc_ci']}） | {XS2['肝炎']['v3_basic_LR（凍結）']['cint']}／{XS2['肝炎']['v3_basic_LR（凍結）']['cslope']} | {XS2['糖尿病']['v3_basic_LR（凍結）']['auc']}（{XS2['糖尿病']['v3_basic_LR（凍結）']['auc_ci']}） | {XS2['糖尿病']['v3_basic_LR（凍結）']['cint']}／{XS2['糖尿病']['v3_basic_LR（凍結）']['cslope']} |

**表11　v3.2 事後評估之配對比較、加權與分區（2021–2023）**

| 項目 | 肝炎病毒感染標籤 | 糖尿病標籤 |
|---|---|---|
| 常規套組 LR − 年齡性別：ΔAUROC（95% CI） | {xd('肝炎', 'LR_routine−M1_demographics')[0]}（{xd('肝炎', 'LR_routine−M1_demographics')[1]}） | {xd('糖尿病', 'LR_routine−M1_demographics')[0]}（{xd('糖尿病', 'LR_routine−M1_demographics')[1]}） |
| 梯度提升 − 年齡性別 | {xd('肝炎', 'HGB_routine−M1_demographics')[0]}（{xd('肝炎', 'HGB_routine−M1_demographics')[1]}） | {xd('糖尿病', 'HGB_routine−M1_demographics')[0]}（{xd('糖尿病', 'HGB_routine−M1_demographics')[1]}） |
| 梯度提升 − LR（常規套組） | {xd('肝炎', 'HGB_routine−LR_routine')[0]}（{xd('肝炎', 'HGB_routine−LR_routine')[1]}） | {xd('糖尿病', 'HGB_routine−LR_routine')[0]}（{xd('糖尿病', 'HGB_routine−LR_routine')[1]}） |
| 常規套組 − 全特徵（LR） | {xd('肝炎', 'LR_routine−LR_full')[0]}（{xd('肝炎', 'LR_routine−LR_full')[1]}） | {xd('糖尿病', 'LR_routine−LR_full')[0]}（{xd('糖尿病', 'LR_routine−LR_full')[1]}） |
| 常規套組 LR：MEC 加權 AUROC（設計 95% CI） | {xw('肝炎', LR, 'WTMEC2YR')['auc']}（{xw('肝炎', LR, 'WTMEC2YR')['auc_ci']}） | {xw('糖尿病', LR, 'WTMEC2YR')['auc']}（{xw('糖尿病', LR, 'WTMEC2YR')['auc_ci']}） |
| 常規套組 LR：抽血權重加權 AUROC | {xw('肝炎', LR, 'WTPH2YR')['auc']}（{xw('肝炎', LR, 'WTPH2YR')['auc_ci']}） | {xw('糖尿病', LR, 'WTPH2YR')['auc']}（{xw('糖尿病', LR, 'WTPH2YR')['auc_ci']}） |
| 常規套組 LR：MEC 加權校準差，百分點 | {xw('肝炎', LR, 'WTMEC2YR')['cd']}（{xw('肝炎', LR, 'WTMEC2YR')['cd_ci']}） | {xw('糖尿病', LR, 'WTMEC2YR')['cd']}（{xw('糖尿病', LR, 'WTMEC2YR')['cd_ci']}） |
| 常規套組 LR：各區實際陽性率（傾向／不確定／不傾向） | {XS2['肝炎'][LR]['rates']} | {XS2['糖尿病'][LR]['rates']} |
| 　能給出方向的比例；資料不足 | {XS2['肝炎'][LR]['cov']}；{XS2['肝炎'][LR]['insuff']} | {XS2['糖尿病'][LR]['cov']}；{XS2['糖尿病'][LR]['insuff']} |

註：分區為重新校準前之基礎模型以開發資料盛行率計算之門檻；各區實際陽性率只計入資料足夠者，能給出方向的比例以全部為分母。抽血權重大於 0 者：肝炎軸 {n(X['肝炎']['weighted'][LR]['WTPH2YR']['n_weight_positive'])} 人、糖尿病軸 {n(X['糖尿病']['weighted'][LR]['WTPH2YR']['n_weight_positive'])} 人。

**糖尿病軸**　常規套組邏輯迴歸 AUROC {XS2['糖尿病'][LR]['auc']}、梯度提升 {XS2['糖尿病'][HG]['auc']}，都明顯高於同一批人只用年齡、性別的 {XM1['糖尿病']['auc']}；梯度提升比邏輯迴歸高 {xd('糖尿病', 'HGB_routine−LR_routine')[0][1:]}（95% CI {xd('糖尿病', 'HGB_routine−LR_routine')[1]}），校準截距 {XS2['糖尿病'][HG]['cint']}、斜率 {XS2['糖尿病'][HG]['cslope']}，比邏輯迴歸（{XS2['糖尿病'][LR]['cint']}／{XS2['糖尿病'][LR]['cslope']}）更接近理想。全特徵邏輯迴歸只有 {XS2['糖尿病'][LF]['auc']}，比常規套組低 {xd('糖尿病', 'LR_routine−LR_full')[0][1:]}（95% CI {xd('糖尿病', 'LR_routine−LR_full')[1]}）：2021–2023 年沒有測量或只在部分週期有值的非常規特徵在新資料上拖累判別，與 v3 之事後探索一致。以抽血權重加權，結論不變。

**肝炎軸**　只有 {X['肝炎']['n_pos']} 名陽性，遠低於外部驗證建議的至少 100 個事件[@collins_ev]。常規套組邏輯迴歸 AUROC {XS2['肝炎'][LR]['auc']}（{XS2['肝炎'][LR]['auc_ci']}），同一批人只用年齡、性別為 {XM1['肝炎']['auc']}，常規套組沒有高於它（ΔAUROC {xd('肝炎', 'LR_routine−M1_demographics')[0]}，95% CI {xd('肝炎', 'LR_routine−M1_demographics')[1]}）；所有區間都極寬，無法確認或否定內部結果。陽性組成也不同：開發資料的肝炎陽性以 C 型為主（{C['hcv_in_kidney']['pos']}／{C['hep_in_kidney']['pos']}），2021–2023 年為 B 型 {XS_SUB['B型_HBsAg']['n_pos']} 人、C 型 {XS_SUB['C型_HCV_RNA']['n_pos']} 人；重新校準後之網頁工具對 C 型陽性 AUROC {p3(XS_SUB['C型_HCV_RNA']['auroc'])}（{ci(XS_SUB['C型_HCV_RNA']['ci95']['auroc'])}）、B 型 {p3(XS_SUB['B型_HBsAg']['auroc'])}（{ci(XS_SUB['B型_HBsAg']['ci95']['auroc'])}）。

### 3.8　網頁工具 v3.2 與重新校準之交叉驗證

{{FIG8}}

**圖8　重新校準之交叉驗證。** 依抽樣設計把 2021–2023 年資料切半 200 次；點為中位數，線為 2.5–97.5 百分位。

**表12　網頁工具 v3.2 與重新校準之交叉驗證**

| 項目 | 肝炎病毒感染標籤 | 糖尿病標籤 |
|---|---|---|
| 重新校準方式 | {TH['method']}（陽性 {TH['npos']}，未達 100；斜率檢定 p ＝ {TH['p']}） | {TD['method']}（斜率檢定 p ＝ {TD['p']}） |
| 更新係數 a、b | {TH['a']}、{TH['b']} | {TD['a']}、{TD['b']} |
| 事前機率（2021–2023） | {TH['prior']} | {TD['prior']} |
| 傾向／不傾向門檻 | ≧ {TH['hi']}／≦ {TH['lo']} | ≧ {TD['hi']}／≦ {TD['lo']} |
| 交叉驗證：測試半陽性數（中位數） | {CVH['npos']} | {CVD['npos']} |
| 　平均預測／實際：重新校準 | {CVH['oe']}（{CVH['oe_rng']}） | {CVD['oe']}（{CVD['oe_rng']}） |
| 　平均預測／實際：不重新校準 | {CVH['oen']}（{CVH['oen_rng']}） | {CVD['oen']}（{CVD['oen_rng']}） |
| 　校準截距／斜率：重新校準（中位數） | {CVH['ci_r']}／{CVH['cs_r']} | {CVD['ci_r']}／{CVD['cs_r']} |
| 　校準截距／斜率：不重新校準（中位數） | {CVH['ci_n']}／{CVH['cs_n']} | {CVD['ci_n']}／{CVD['cs_n']} |
| 　訓練半更新斜率之比例 | {CVH['share']} | {CVD['share']} |
| 　固定切分（PSU 1 訓練、PSU 2 測試）平均預測／實際 | {CVH['fixed_oe']} | {CVD['fixed_oe']} |
| v3.1 同法之交叉驗證：平均預測／實際 | {CV31H['oe']}（{CV31H['oe_rng']}） | {CV31D['oe']}（{CV31D['oe_rng']}） |

糖尿病軸在測試半上，重新校準後平均預測與實際之比中位數 {CVD['oe']}，不重新校準為 {CVD['oen']}（略為低估）：整體高低的更新是可靠的。斜率則不然：以半數資料檢定時，只有 {CVD['share']} 的切分通過「陽性 ≧ 100 且 p < 0.05」而更新斜率，其餘只更新截距，測試半校準斜率中位數仍為 {CVD['cs_r']}（範圍 {CVD['cs_r_rng']}）；以全部資料更新之網頁工具已更新斜率（b ＝ {TD['b']}），但這一步的穩定性有限。肝炎軸每半只有約 {CVH['npos']} 個事件，平均預測與實際之比範圍 {CVH['oe_rng']}，無法判斷。

示範受試者（補充圖 S1）為 NHANES {EXD['cycle'].replace('-', '–')} 的一名真實成人（HCV RNA 陽性、無糖尿病）：網頁工具 v3.2 之肝炎軸機率 {pct(EXH['cal'], 2)}、相對事前勝算 ×{EXH['odds_ratio']:.2f}（「{EXH['band']}」），最大推動因子為 HDL {DEMO['LBDHDL']:.0f} mg/dL（開發資料中位數約 {HDL_MED:.0f} mg/dL）；糖尿病軸 {pct(EXDM['cal'], 2)}（「{EXDM['band']}」）。網頁與 Python 的輸出逐軸一致。在 C 型肝炎陽性者中，HDL 的單變量差異其實很小（AUROC {mkc('LBDHDL')}）；它在模型中的推動力是與總膽固醇等共線特徵一起調整後的條件效果，不能單獨解讀。單一示範只展示輸出形式，不代表準確率。

### 3.9　免疫方向（抗核抗體次樣本）

腎臟指標異常且在次樣本者 {n(IM['n'])} 人，其中 3+／4+ 陽性 {IM['n_pos']} 人（{pct(IM['prevalence'])}；女性 {IM['by_sex']['女']['n_pos']}／{IM['by_sex']['女']['n']}、男性 {IM['by_sex']['男']['n_pos']}／{IM['by_sex']['男']['n']}）。常規套組邏輯迴歸 AUROC {IML:.3f}、梯度提升 {IMH:.3f}，只用年齡、性別為 {IM1:.3f}；邏輯迴歸減年齡性別之配對 ΔAUROC {sgn(IMD['d_auroc'])}（95% CI {ci(IMD['ci95']['d_auroc'])}），依事前規則判為「{IM['decision']}」。校準斜率 {IMS:.2f}，模型學到的多半是雜訊。陽性者中與全身性紅斑狼瘡相關之特異抗體很少：Ro/SSA {IM['sle_antibodies_among_pos']['Ro/SSA']}、U1-RNP {IM['sle_antibodies_among_pos']['U1-RNP']}、La/SSB {IM['sle_antibodies_among_pos']['La/SSB']}、Sm {IM['sle_antibodies_among_pos']['Sm']} 人。

## 4　討論

### 4.1　主要發現

常規檢驗能回推代謝與感染兩個病因方向，程度中等、內部校準良好：常規套組邏輯迴歸肝炎軸 AUROC {H['m'][LR]['auc']}、AP 為盛行率的 {H['ap_lift']} 倍；糖尿病軸 AUROC {D['m'][LR]['auc']}；兩軸都比只用年齡、性別高約 0.2。肝炎軸實際上是 C 型肝炎軸：B 型肝炎表面抗原陽性者幾乎無法由常規檢驗辨識（僅 B 肝標籤 AUROC {p3(HBV1['auroc'])}；單變量掃描 {MK['僅B肝']['n_markers']} 個標記僅 {MK['僅B肝']['n_fdr05']} 個通過偽發現率校正），可能因多數慢性 B 型肝炎帶原者肝功能與血液檢驗接近正常。C 型肝炎標籤者的型態則一致：球蛋白較高（單變量 AUROC {mkc('LBXSGB')}）、白蛋白較低（{mkc('LBXSAL')}）、血小板與總膽固醇較低（{mkc('LBXPLTSI')}、{mkc('LBXSCH')}），與慢性病毒性肝炎之血脂研究方向一致[@bashir]；可丁尼亦較高（{mkc('LBXCOT')}，僅 {MKC['LBXCOT']['n_pos']} 名陽性有值），提示部分訊號來自與感染風險相關的吸菸暴露，而不只是肝臟生理。免疫方向則回推不了：抗核抗體次樣本中，常規套組 AUROC {IML:.3f} 未優於只用年齡、性別的 {IM1:.3f}（3.9）。

### 4.2　非線性模型與校準

糖尿病軸的梯度提升在內部（{D['m'][HG]['auc']} 對 {D['m'][LR]['auc']}）、時間外推（{D['t'][HG]['auc']} 對 {D['t'][LR]['auc']}）與 2021–2023 年資料（{XS2['糖尿病'][HG]['auc']} 對 {XS2['糖尿病'][LR]['auc']}）都比邏輯迴歸高。經同樣的保序校準後，它的內部校準截距 {D['m'][HG]['cint']}、斜率 {D['m'][HG]['cslope']}，Brier 較低；時間外推與人口加權時仍有偏移（截距 {D['t'][HG]['cint']}、加權校準差 {D['w'][HG]['cd']} 個百分點），但都比邏輯迴歸小；在 2021–2023 年資料上，重新校準前的截距與斜率（{XS2['糖尿病'][HG]['cint']}／{XS2['糖尿病'][HG]['cslope']}）也比邏輯迴歸接近理想。因此，非線性模型的增益不是以校準為代價換來的。這與「機器學習在臨床預測上常不優於邏輯迴歸」的系統性回顧不同[@christodoulou]，表示糖尿病標籤與常規檢驗之間存在線性模型沒有抓到的關係；本研究尚未分析是哪些特徵或交互作用造成增益。肝炎軸則沒有這種增益：事件數少，非線性模型的校準斜率偏離 1（{H['m'][HG]['cslope']}），能給出方向的比例也較低。

網頁工具仍維持邏輯迴歸。工具的目的是提供附有「為什麼」的病因方向，邏輯迴歸的推動因子可由係數直接算出；這個選擇在看到 v3.2 結果之前即寫定。代價是糖尿病軸少了約 {D['mdg'][1:]} 的 AUROC（五次重複平均差）。保留增益的方法（可解釋的非線性模型，或在邏輯迴歸中加入經事前指定的交互項）需以獨立資料驗證。

### 4.3　與前版的差異

v3 修正了三類審查者無法看見的錯誤：1999–2000 年血清肌酸酐公式錯用、2003–2004 年缺 HCV RNA 卻判陰性、暴露分析中血中金屬欄位撞名，並把未知從陰性中分出。v3.2 再修正三類：2001–2002 年四項生化以另一變數名發布而整週期缺值、2017–2018 年生化儀器更換之回推式未套用、HDL 未讀入且被誤封存。六項都能通過 SHA256 檢查，說明出處帳本只保證檔案未被更動，不保證分析正確。v3.2 的三項錯誤都是在「逐週期檢查每個特徵的有值比例」與「逐一閱讀 CDC 文件」時發現的；它們對整體判別的影響很小（例如補回 HDL 對糖尿病軸 ΔAUROC {D['dh']}），卻會改變個人的輸出——示範受試者的肝炎軸機率在補回 HDL 後明顯上升（3.8）。

獨立稽核另找到三項報告層級的問題並已更正：(1)「能給出方向的比例」原把資料不足者也算入分區（糖尿病梯度提升 {pct(E['糖尿病']['models'][HG]['bands_B_repeat0']['coverage'])} → {D['m'][HG]['cov']}）；(2) 假設的外部部分原以外部 AUROC 對照內部的年齡性別基準，補做同一批外部受試者的基準後，糖尿病軸成立、肝炎軸無法判斷；(3) 候選特徵原被描述為「全為各週期共有之常規檢驗」。v3 之研究說明書與研究論文亦有第 (1) 項問題，勘誤列於版本紀錄。

### 4.4　回推病因方向的意義與界線

本研究的核心問題是回推腎炎（腎損傷）的病因方向。現有公開資料能支持的結論是：代謝方向（糖尿病）可以回推；感染方向只有 C 型肝炎可以回推；免疫方向回推不了。當常規檢驗呈現與 C 型肝炎或糖尿病相符的型態時，這組數值指出值得優先查證的病因方向，並附有可追溯的依據（推動因子）與經校準的機率；它不能回答腎損傷是否由該病造成。免疫方向在公開資料中只有抗核抗體可用，缺乏補體與病理，常規檢驗沒有可學習的訊號[@yang]。在臨床行動上，肝炎檢驗應依普遍篩檢建議進行，本工具的角色是解釋與排序，而不是省略檢驗。

### 4.5　研究限制

1. 病因方向的標籤為共存疾病的操作型定義，不是腎臟病理；腎炎（腎損傷）以單次腎臟指標異常定義，不確認慢性性，也無法區分腎炎與其他腎損傷[@kdigo]。
2. 1999–2018 年資料已在前幾版反覆使用，本版為探索性重分析；2021–2023 年資料已用於 v3 之一次評估與 v3.1 重新校準，v3.2 之外部數字皆屬事後分析，網頁工具 v3.2 更新後的校準仍無獨立資料驗證。
3. 肝炎陽性僅 {H['pos']} 人，逐週期評估的區間很寬；穩定性取決於事件數與候選參數，而非總樣本數[@riley]。外部只有 {X['肝炎']['n_pos']} 個事件，肝炎軸的外部表現仍未確認，對 B 型肝炎幾乎沒有訊號。
4. HbA1c 在 2007–2010 年分布右移而依 CDC 建議使用原值[@ghb_f]；2013–2014 週期起血球分析儀更換，CDC 無法回溯比對、沒有換算式[@cbc_h]；非常規特徵的跨週期方法差異未換算（這些特徵只用於全特徵模型）。
5. 設計變異已依 PSU 與分層估計，但預測視為固定，不含模型重新配適的變異。美國調查的機率不能直接移植至臺灣就醫族群，輸入值也必須與開發資料的檢驗量尺一致。
6. 暴露分析為單次橫斷面，無法建立時序。
7. 外部資料的檢驗儀器與方法已變更，本研究以 CDC 官方回推式兩段換算；回推式本身有估計誤差，且血中金屬與可丁尼沒有官方換算式。
8. 免疫方向以抗核抗體 3+／4+ 為標籤，抗核抗體陽性不等於免疫性腎炎；只有 1999–2004 年剩餘血清次樣本、未加權，也沒有新資料可評估。

### 4.6　下一步

1. **以另一批獨立資料驗證網頁工具 v3.2 的校準**：2021–2023 年資料已用於更新，不能再當驗證；交叉驗證顯示整體高低可靠、斜率更新不穩定。
2. **保留糖尿病軸之非線性增益**：評估可解釋的非線性方法或事前指定的交互項，並以獨立資料驗證。
3. **肝炎軸**：需要更多事件（例如之後的 NHANES 週期），並另建 B 型肝炎的模型。

## 5　結論

常規血液與尿液檢驗可回推腎炎（腎損傷）成人的代謝方向（糖尿病標籤，中等辨識力、內部校準良好）；感染方向只能部分回推，訊號主要來自 C 型肝炎，對 B 型肝炎幾乎沒有訊號；免疫方向回推不了，抗核抗體標籤未優於只用年齡、性別。糖尿病軸的非線性模型判別更高，經保序校準後校準同樣接近理想，並在 2021–2023 年資料上維持；網頁工具為保留逐項解釋而維持邏輯迴歸，其重新校準在交叉驗證中整體高低可靠，但仍需獨立資料驗證。肝炎軸外部事件太少而無法確認。回推的是病因方向，不等於病因診斷，也不支持用來省略肝炎篩檢。資料層級的錯誤已依官方文件更正，所有結果由同版結果檔生成。

---

## 研究聲明

**資料與程式可得性**　資料為 NHANES 公開檔，來源網址見 `params/manifest.json`，逐檔 SHA256 與位元組數見 `results/provenance.json`。程式與結果位於 https://github.com/CBL-AICM/MD.Piece （分支 claude/disease-trajectory-model-prompts-ad24d8，目錄 experiments/kidney_cause）。v3：分析計畫 {CM['plan_v3']}、結果 {CM['res_v3']}、外部確認協定 {CM['proto']}、圖 {CM['figs_v3']}、修正一 {CM['amend']}、外部確認結果 {CM['ext']}、網頁工具 v3.1 {CM['tool_v31']}、設計變異計畫 {CM['dv_plan']} 與結果 {CM['dv_res']}。v3.2：計畫 {CM['plan_v32']}、結果 {CM['res_v32']}、稽核後更正 {CM['audit']}、補充分析 {CM['supp_plan']}（程式）與 {CM['supp_res']}（結果）、單變量標記 {CM['mk_plan']} 與 {CM['mk_res']}、暴露分析 {CM['exw_plan']}（計畫與程式）與 {CM['exw_res']}（結果）、免疫方向 {CM['imm_plan']} 與 {CM['imm_res']}。執行環境見 `requirements-lock.txt`。v3.2 重現入口：`evaluate_v3_2.py` → `external_v3_2.py` → `supplement_v3_2.py` → `markers_v3.py v3.2` → `run_exwas.py v3.2` → `exwas_v3_checks.py v3.2` → `exwas_v3_2_compare.py` → `immune_v3_2.py` → `make_figures_v3_2.py` → `verify_direction_html.py` → `build_paper_v3_2.py`；v3 外部確認之程式見 v3 版。

**研究倫理**　本研究只使用公開、去識別化之 NHANES 資料，未接觸可識別個人之資訊；NHANES 之調查協定由 NCHS 倫理審查委員會核准[@erb]。

**AI 工具使用**　程式撰寫、資料核對與文件草擬使用 Claude（Anthropic）輔助；獨立稽核使用 Codex（OpenAI，唯讀）。所有數字由結果檔以程式產生，作者須確認後負責。

**作者貢獻、資助與利益衝突**　須由作者確認後填列。

---

## 參考文獻

依首次引用順序編號；網路資料查閱日期 2026-09-26／27。

@@REFLIST@@

---

## 補充資料

### 表 S1　逐週期三值計數（v3.2；腎臟為全體成人，兩標籤為腎臟指標異常者）

{per_cycle_table()}

### 表 S2　v3 凍結之外部確認模型

| 模型 | 檔案 | SHA256（前 16 碼） |
|---|---|---|
""" + "\n".join(f"| {k} | `{v['path'].replace(chr(92), '/')}` | {v['sha256'][:16]} |" for k, v in fm_models.items()) + f"""

### 表 S3　外部資料修正一之官方回推式（2021–2023 年數值換回 2017–2020 年量尺）

{conv_table_l()}

註：另將 LBXTLG 對應為 LBXTR、LBXVIDMS 對應為 LBDVIDMS；滲透壓、Friedewald LDL 與 ACR 由調整後組成重算；回推值小於 0 者設為 0。修正一於評估前提交（{CM['amend']}），檔案 SHA256 前 16 碼 {sha_amend[:16]}。

### 表 S4　2017–2018 年生化之 BIOPRO_J 回推式與換算前後中位數（全體成人）

{conv_table_j()}

註：v3.2 對開發資料之 2017–2018 年與外部資料（修正一之後）皆套用此表；球蛋白（總蛋白減白蛋白）與滲透壓由換算後組成重算，重算後中位數分別為 {BM['2017-2018_DxC']['LBXSGB']:.4g} 與 {BM['2017-2018_DxC']['LBXSOSSI']:.4g}（2015–2016 年 {BM['2015-2016']['LBXSGB']:g} 與 {BM['2015-2016']['LBXSOSSI']:g}）。

### 圖 S1　單一受試者輸出示範

{{FIGS1}}

**圖 S1　單一受試者輸出示範（網頁工具 v3.2）。** 僅展示工具的輸出形式；單例不代表準確率。推動因子為標準化值乘係數，共線特徵（如 HDL 與兩種總膽固醇）的貢獻可互相抵銷，不能逐項解讀為致病因子。

### 可重算之結果檔

v3.2：`results/v3_2_cohort_audit.json`（資料修正之稽核）、`results/v3_2_eval.json`（內部評估）、`results/v3_2_oof.csv.gz`（逐人外層預測）、`results/v3_2_supplement.json`（補充分析）、`results/v3_2_markers.json`（單變量標記）、`results/v3_2_external.json`（2021–2023 事後評估與重新校準交叉驗證）、`params/direction_model_v3_2_basic.json` 與 `params/direction_model_v3_2.json`（網頁工具重新校準前、後）、`results/direction_v3_2_recalibration.json`（重新校準之表面值）、`results/exwas_v3_2.json` 與 `results/exwas_v3_2_checks.json`（暴露分析）、`results/exwas_v3_2_compare.json`（與 v3 暴露分析之比較）、`results/immune_v3_2.json`（免疫方向）。v3（照原樣）：`results/v3_audit.json`、`results/v3_eval.json`、`results/exwas_v3.json`、`results/exwas_v3_checks.json`（暴露分析；＝2017–2018 年用原發布肌酸酐之敏感度分析）、`params/external_validation_amendment_1.json`、`results/external_2021_2023_precheck.json`、`results/external_2021_2023.json`、`results/external_2021_2023_posthoc.json`、`results/design_variance.json`。版本紀錄：`docs/VERSION_LOG.md`。
"""

RESPONSE = f"""# 審查意見回應表（v3.2，2026-09-27）

> 對應《深度審查與補強方案》（2026-09-26）。審查者沒有取得資料與程式，將重分析列為「待執行」；本表逐項說明以真實資料執行的內容與結果。v3 已完成主要重分析；v3.2 再修正三類資料錯誤、評估非線性模型的校準並更新網頁工具（第十節）。數字皆出自 `results/v3_2_*.json`、`results/exwas_v3_2*.json`（v3.2）與 `results/v3_*.json`、`results/external_2021_2023*.json`（v3，照原樣）。
> 主稿：[[研究論文_v3.2]]｜前版：[[研究論文_v3重分析]]、[[審查意見回應_v3]]｜版本紀錄：`experiments/kidney_cause/docs/VERSION_LOG.md`

## 一、概念與主張（審查 §三）

| 審查意見 | 處理 | 結果或位置 |
|---|---|---|
| 病因和共病不可互換 | 標籤為共存疾病之操作型定義；研究問題界定為「回推腎炎（腎損傷）的病因方向」（感染、代謝、免疫），結論只宣稱方向、不宣稱病因 | 論文題目、前言、2.3、4.4 |
| 單次異常與慢性疾病分開 | 改稱「單次腎臟指標異常」「分析樣本」 | 2.1、2.2、限制 1 |
| 切片與臨床效益不可預設 | 刪除減少切片之主張；以決策曲線與普遍篩檢比較 | 3.5：肝炎軸 pt ＝ 0.5% 時與全數送驗幾乎相同 |
| 資料出處不保證模型準確 | 改稱可追溯性與完整性檢查；v3 與 v3.2 共找到六項能通過 SHA256 的資料錯誤 | 2.1、4.3 |
| 資料洩漏與疾病訊號分開 | 改稱「近端特徵消融」，刪除「0.904 是虛假判別力」；改報同切分配對差（v3.2 資料重跑） | 肝炎 {H['ab_with']}→{H['ab_without']}（差之 95% CI {H['ab_ci']}）；糖尿病 {D['ab_with']}→{D['ab_without']}（{D['ab_ci']}） |
| 不顯著與無訊號分開 | 刪除「若軸不成立應無單標記通過 FDR」之必要推論；FDR 解讀改為控制錯誤發現比例 | 2.9 |

## 二、樣本分母與數字（審查 §四）

| 審查意見 | 處理 | 結果（v3.2） |
|---|---|---|
| 3,289 是否涵蓋所有無法判定者 | 三值重建 | 未知 {n(C['kidney']['unknown'])} ＝ 一正常一缺 {n(C['kidney_unknown_one_normal_one_missing'])} ＋ 兩項皆缺 {n(C['kidney_unknown_both_missing'])}；可判定 {n(old['outcome_known_old_rule'])}（v2）→ {n(kd_known3)}（v3）→ {n(kd_known32)}（v3.2） |
| 17.34% 非人口盛行率 | 標明未加權；另報加權結果 | 論文 3.1 註、3.4 |
| 標籤比例需排除未知 | 兩標籤三值 | 肝炎 {C['hep_in_kidney']['pos']}／{n(C['hep_in_kidney']['neg'])}／{C['hep_in_kidney']['unknown']}；糖尿病 {n(C['dm_in_kidney']['pos'])}／{n(C['dm_in_kidney']['neg'])}／{C['dm_in_kidney']['unknown']} |
| 共陽性 70 為條件推算 | 逐人交叉表 | 實數 {X2['陽性']['陽性']}（舊定義重建為 70） |
| 0.816 與 0.763 不可相減 | 同一樣本、同一切分比較 | 糖尿病軸常規套組：邏輯迴歸 {D['m'][LR]['auc']} vs 梯度提升 {D['m'][HG]['auc']}（五次重複平均），平均差 {D['mdg']}；第一次重複配對差 {D['dg']}（95% CI {D['dg_ci']}） |
| −0.002 與 −0.001、0.050 與 0.051 | 一律以未四捨五入值計算並附配對 CI | 論文表 2 |
| 0.904 與 0.913；圖四 0.087／0.088 | 0.913 為三週期早期版本，0.904 為十週期；舊圖四已刪除 | 版本紀錄第二節 |

## 三、圖表（審查 §五）

| 原稿 | 處理（v3.2 圖） |
|---|---|
| 圖一（世代、病因、未顯示未知） | 圖 1：三值流程、各軸分析 n、資料更正 |
| 圖二（混合三任務與工具；6.7／7.0） | 圖 2：常規套組與全特徵 × 線性與非線性分開呈現；6.7 與 7.0 原為兩個不同任務，新圖只報絕對值 |
| 圖二、圖四之「原始目標 0.90」 | 全部移除；0.90 之來源見版本紀錄第一節 |
| 圖三（反向因果直接證據） | 撤回；圖 6 改為同一批 {n(Pb['n_both'])} 人之探索性比較 |
| 圖四（六項陷阱，表僅五項） | 刪除；改列版本紀錄之更正表，並刪除「每一次修正都使結果變差」 |
| 圖五（單例；糖尿病倍數超過 100%） | 圖 S1 改用概似比對數量尺（0.25–4 倍），不會超出機率範圍；標明僅展示 |
| 圖六（開發集作業點與保留集 AUROC 並列） | 刪除；每千人情境改由外層預測之分區結果計算（套用資料不足規則） |

## 四、資料與標籤重跑規格（審查 §六）

| 審查意見 | 執行結果 |
|---|---|
| 每週期稽核表 | 表 S1（v3.2）；`results/v3_audit.json`、`results/v3_2_cohort_audit.json`（逐週期三值計數、特徵有值比例、2017–2018 換算前後中位數） |
| 四種缺失分開 | 三值規則；2003–2004 無 HCV RNA 屬「全週期未測」，列為未知；v3.2 另發現 2001–2002 年四項生化為「變數改名」而非缺測 |
| 尿肌酸酐校正（優先項目） | 已依 ALB_CR_E 執行；ACR 跨 30 mg/g 增 {RC3['ucr_fix_pre2007']['acr_cross30_up']}、減 {RC3['ucr_fix_pre2007']['acr_cross30_down']}；跨 300 增 {RC3['ucr_fix_pre2007']['acr_cross300_up']}、減 {RC3['ucr_fix_pre2007']['acr_cross300_down']} |
| 血清肌酸酐校正核查 | v3 **發現錯誤**：1999–2000 誤用 NHANES III 公式，更正後該週期 eGFR<60 由 {RC3['scr_fix_1999_2000']['egfr_lt60_old']} 增為 {RC3['scr_fix_1999_2000']['egfr_lt60_new']} 人；v3.2 **再發現** 2017–2018 年儀器更換之回推式未套用，更正後該週期 {CH1718.get('1→0', 0)} 人由異常改為正常、{CH1718.get('1→-1', 0)} 人改為未知 |
| HBV、HCV 分開 | 已分開；HBsAg 陽性 {C['hbv_in_kidney']['pos']}、HCV RNA 陽性 {C['hcv_in_kidney']['pos']}；僅 HBV 標籤 AUROC {p3(HBV1['auroc'])}、僅 HCV {p3(HCV1['auroc'])} |
| 糖尿病問卷邊緣、拒答、不知道 | 邊緣歸問卷陰性並做排除敏感度（{p3(LS['排除邊緣_DIQ010=3']['auroc'])}）；拒答／不知道為未知；問卷與 HbA1c 分別定義 {p3(LS['僅問卷_DIQ010']['auroc'])}／{p3(LS['僅HbA1c']['auroc'])} |

## 五、模型評估（審查 §七）

| 審查意見 | 執行結果 |
|---|---|
| 分清探索與確認 | 1999–2018 重分析標為探索性；確認性評估為 v3 事前凍結之 2021–2023 一次評估（糖尿病軸部署模型 {XD['auc']}；肝炎軸僅 {XH['pos']} 個事件，無法確認）；v3.2 之外部數字標為事後分析 |
| 全流程外層隔離 | 插補、標準化、集成、保序校準、門檻皆在外層訓練資料內完成；v3.2 之梯度提升亦採同一結構 |
| 事件／特徵比 | 肝炎 {H['pos']} 事件對常規套組 {H['routine']} 項，約 {E['肝炎']['n_pos'] / H['routine']:.1f}；已列限制 |
| 基準比較與配對差 | 年齡性別、常規套組（含／不含 HDL）、全特徵、線性與非線性；配對 CI 見論文表 2 |
| 重複 CV 之彙整 | 每次重複每人一個外層預測，指標逐次計算後摘要；CI 取第一次重複並註明不含重新配適變異 |
| 向前時間驗證 | 1999–2008 → 2009–2018：肝炎 {H['t'][LR]['auc']}（{H['t'][LR]['auc_ci']}）、糖尿病 {D['t'][LR]['auc']}（{D['t'][LR]['auc_ci']}）；梯度提升 {H['t'][HG]['auc']}／{D['t'][HG]['auc']}；逐週期擴展視窗見論文表 6 |
| 最低報告集 | 分母與陽性數、AUROC、絕對 AP（定義）、梯形 PR-AUC、校準截距與斜率、Brier、分區表（含資料不足）、涵蓋率、全體漏失、每千人結果：論文表 2–5、圖 3、3.5 |

## 六、抽樣與暴露分析（審查 §八）

| 審查意見 | 執行結果 |
|---|---|
| 調查權重 | 20 年 MEC 權重；設計變異依 {DV['design']['internal']['strata']} 層、{DV['design']['internal']['psu']} 個 PSU 以刪一 PSU 摺刀法估計，比例採 Korn–Graubard 區間。v3.2：肝炎軸加權 AUROC {H['w'][LR]['auc']}（{H['w'][LR]['auc_ci']}）、糖尿病軸 {D['w'][LR]['auc']}（{D['w'][LR]['auc_ci']}），糖尿病軸加權校準差 {D['w'][LR]['cd']} 個百分點（{D['w'][LR]['cd_ci']}）；外部另以抽血權重作敏感度 |
| 五層調整之完整共變數 | M0–M4 已逐層列出（2.9） |
| 檢定家族 | M3 之 {EXW['n_scanned']} 個暴露共同校正；其他層級為敏感度，不跨層挑最小 p |
| 檢出極限、偏態、有效樣本、量尺 | 鉛、鎘列出低於檢出極限比例；改用 log2；藥物 OR 改為使用 vs 未使用 |
| 血尿非同一批人 | v3 **發現錯誤**：舊版血中金屬只含 1999–2004、尿中只含 2005–2018，無共同受試者；修正合併後以同一批 {n(Pb['n_both'])} 人比較（論文表 8） |
| 尿液共同分母 | 比較原濃度、加尿肌酸酐共變數、比值三種寫法與三種結果定義（論文表 8、圖 6） |
| 陰性／陽性對照之解讀 | 改為「可檢查特定流程錯誤與部分偏差」，不宣稱對照證明無混雜 |

註：暴露分析已以 v3.2 資料修正重跑（先提交 {CM['exw_plan']}、結果 {CM['exw_res']}）；2017–2018 年 {EC['label_changes']['n_changed']} 人腎臟結果改變，無任何暴露改變顯著與否（v3 結果即原發布肌酸酐之敏感度分析）。

## 七、文獻（審查 §九）

依審查意見修正用途：Yang 2024 僅作背景（免疫性病因需補體、自體抗體與病理，NHANES 無法評估）；Lai 2025、Zhang 2026 不再作為本研究之重現證據而移除；Cao 2026 不再引用；Bashir 2026 修正 DOI 並限於背景機轉；PLA2R 與抗 GBM 文獻移除。v3 新增經 PubMed 查證之 Selvin 2007、Van Calster 2019、Vickers 2006、Schillie 2020、Barr 2005、Collins 2016、Vergouwe 2017、Rust & Rao 1996 與 NCHS 比例呈現標準（Parker 2017），以及 CDC 2021–2023 年資料文件三份。v3.2 新增 Christodoulou 2019（機器學習與邏輯迴歸之系統性回顧）與 CDC 資料文件 L40_B、BIOPRO_J、Lab13、GHB_F、CBC_H 及 NHANES 倫理審查頁；並依 CDC 頁面更正 LAB18（Standard Biochemistry Profile & Hormones）、HEPC_H（Hepatitis C: RNA and Genotype）與 TRIGLY_L 之標題，NCHS 文件加註發布或修訂日期。

## 八、可交付成果（審查 §十）

| 產物 | 狀態 |
|---|---|
| 樣本核對表 | 完成：`results/v3_audit.json`、`results/v3_2_cohort_audit.json`、表 S1 |
| 資料字典 | 部分：常規套組 {N_ROUTINE} 項之變數字典已完成（科展作品說明書 v3.2 附錄一）；舊附錄三（352 項）尚未改寫 |
| 逐人預測表 | 完成：`results/v3_2_oof.csv.gz`（軸、模型、重複、SEQN、週期、標籤、校準後機率、分區） |
| 評估摘要 | 完成：`results/v3_2_eval.json`、`results/v3_2_external.json`、`results/v3_2_supplement.json`；表圖皆由同版結果檔生成 |
| 實驗歷史 | 完成：`docs/VERSION_LOG.md`（第九至十二節為 v3.2） |
| 軟體一致性 | 完成：網頁與 Python 對示範受試者逐軸一致（`verify_direction_html.py`）；資料不足與超出範圍旗標 |

## 九、外部確認（2026-09-27）

| 步驟 | 內容 |
|---|---|
| 取用 | 使用者同意後下載 17 檔（約 {PR['total_bytes'] / 1e6:.1f} MB），大小與凍結紀錄一致，SHA256 入帳（`results/provenance.json`） |
| 評估前發現 | CDC 更換生化儀器、尿白蛋白與空腹三酸甘油酯之方法，兩個特徵更名；凍結程式只核對了肌酸酐 |
| 修正一（評估前提交 {CM['amend']}） | 依 CDC 官方回推式把 {len(XAM['conversions'])} 項換回開發量尺，更名者對應回原名；模型、校準、門檻不變 |
| v3 事前指定結果（{CM['ext']}，照原樣） | 糖尿病軸 AUROC {XD['auc']}（{XD['auc_ci']}）；常規套組 {XD['bauc']}（較部署高 {XD['dbf'][1:]}，配對 CI {XD['dbf_ci']}）；肝炎軸 {XH['pos']} 個事件，AUROC {XH['auc']}（{XH['auc_ci']}），平均預測為實際的 {XH['ratio_pred']} 倍 |
| 敏感度（依凍結程式原樣） | 糖尿病 {SD['auc']}、肝炎 {SH['auc']} |
| 事後探索（v3） | 遮蔽六項開發時只有 1999–2004 年有值之非常規特徵：糖尿病軸 {p3(PHD['auroc_all_inputs'])} → {p3(PHD['auroc_masked'])}（差之 95% CI {ci(PHD['delta_ci95'])}） |
| 部署更新 v3.1（{CM['tool_v31']}） | 改用常規套組模型並以 2021–2023 年資料重新校準 |
| v3.2 事後評估 | 修正後資料重新訓練、兩段換算至 DxC 量尺：糖尿病軸常規套組 LR {XS2['糖尿病'][LR]['auc']}、梯度提升 {XS2['糖尿病'][HG]['auc']}，同批年齡性別 {XM1['糖尿病']['auc']}（ΔAUROC {xd('糖尿病', 'LR_routine−M1_demographics')[0]}，95% CI {xd('糖尿病', 'LR_routine−M1_demographics')[1]}）；肝炎軸 {XS2['肝炎'][LR]['auc']}，年齡性別 {XM1['肝炎']['auc']}，無法判斷 |

## 十、v3.2 更新（2026-09-27）

| 項目 | 內容 |
|---|---|
| 新發現之資料錯誤 | (1) 2001–2002 年 ALP、LDH、磷、總膽紅素以 LBDS* 發布，整週期缺值 → 改名對應（有值 {pct(AV0102, 0)}）；(2) 2017–2018 年 BIOPRO_J 回推式未套用 → 12 項換回舊量尺；(3) HDL 未讀入且被誤封存 → 讀入（有值 ≧ {pct(HDL_MIN, 0)}）。計畫先提交 {CM['plan_v32']} |
| 糖尿病軸非線性模型之校準 | 梯度提升 {D['m'][HG]['auc']}（LR {D['m'][LR]['auc']}；第一次重複配對差 {D['dg']}，95% CI {D['dg_ci']}），保序校準後截距 {D['m'][HG]['cint']}、斜率 {D['m'][HG]['cslope']}，Brier {D['m'][HG]['brier']}（LR {D['m'][LR]['brier']}）；時間外推截距 {D['t'][HG]['cint']}（LR {D['t'][LR]['cint']}）；2021–2023 年 {XS2['糖尿病'][HG]['auc']}，截距／斜率 {XS2['糖尿病'][HG]['cint']}／{XS2['糖尿病'][HG]['cslope']} |
| 網頁工具 v3.2 | 常規套組邏輯迴歸（事前決定，保留逐項推動因子）；肝炎軸{TH['method']}、糖尿病軸{TD['method']}；事前 {TH['prior']}／{TD['prior']}；網頁與 Python 一致 |
| 重新校準之交叉驗證 | 糖尿病軸測試半平均預測／實際 {CVD['oe']}（{CVD['oe_rng']}），不重新校準 {CVD['oen']}；斜率更新只在 {CVD['share']} 的切分發生，校準斜率中位數 {CVD['cs_r']}；肝炎軸 {CVH['oe']}（{CVH['oe_rng']}），無法判斷 |
| 補充分析（依 v3 定義重跑） | 描述性計數、近端消融、擴展視窗、糖尿病標籤敏感度、梯形 PR-AUC、單變量標記（先提交 {CM['supp_plan']}、{CM['mk_plan']}） |
| 免疫方向重跑 | 以公開抗核抗體次樣本在修正後資料上重跑（先提交 {CM['imm_plan']}、結果 {CM['imm_res']}）：{n(IM['n'])} 人、陽性 {IM['n_pos']} 人；常規套組 AUROC {IML:.3f}，只用年齡、性別 {IM1:.3f}，配對 ΔAUROC {sgn(IMD['d_auroc'])}（95% CI {ci(IMD['ci95']['d_auroc'])}）→ 無法可靠回推 |
| 暴露分析重跑 | 以 v3.2 資料修正重跑（先提交 {CM['exw_plan']}、結果 {CM['exw_res']}）：2017–2018 年 {EC['label_changes']['n_changed']} 人腎臟結果改變；{EXW['n_scanned']} 個暴露中通過偽發現率者 {EXW['n_significant_fdr05']} 個（v3 {ER['n_significant_fdr05']['v3']} 個），無任何暴露改變顯著與否，對數勝算比最大變動 {abs(ER['max_abs_dlogOR']['dlogOR']):.3f}；對照判定與血尿比較之結論不變 |
| 獨立稽核（Codex，唯讀） | 程式無問題；文件三項（資料不足規則、外部基準、特徵數描述）查證屬實後更正（{CM['audit']}）；v3 文件之勘誤記於版本紀錄第十節 |

## 十一、尚未完成

1. 以另一批獨立資料驗證網頁工具 v3.2 更新後的校準（2021–2023 年資料已用於更新）。
2. 保留糖尿病軸非線性增益之可解釋方法，並以獨立資料驗證。
3. 肝炎軸需更多事件之外部確認，並另建 B 型肝炎模型。
4. 舊附錄三變數字典（352 項）改寫。
5. 作者資訊、貢獻與利益衝突。
"""

REFS = dict(
    kdigo="KDIGO CKD Work Group. KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease. Kidney Int. 2024;105(4S):S117–S314. https://doi.org/10.1016/j.kint.2023.10.018",
    tripod="Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378. https://doi.org/10.1136/bmj-2023-078378",
    probast="Moons KGM, Damen JAA, Kaul T, et al. PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. BMJ. 2025;388:e082505. https://doi.org/10.1136/bmj-2024-082505",
    egfr="National Kidney Foundation. CKD-EPI Creatinine Equation (2021) [undated web page; accessed 2026 Sep 27]. https://www.kidney.org/ckd-epi-creatinine-equation-2021",
    selvin="Selvin E, Manzi J, Stevens LA, et al. Calibration of serum creatinine in the National Health and Nutrition Examination Surveys (NHANES) 1988–1994, 1999–2004. Am J Kidney Dis. 2007;50(6):918–926. https://doi.org/10.1053/j.ajkd.2007.08.020",
    lab18="NCHS. NHANES 1999–2000 Standard Biochemistry Profile & Hormones (LAB18): serum creatinine correction. First published June 2002; last revised August 2006. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/1999/DataFiles/LAB18.htm",
    biopro_d="NCHS. NHANES 2005–2006 Standard Biochemistry Profile (BIOPRO_D): serum creatinine correction. First published March 2008. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2005/DataFiles/BIOPRO_D.htm",
    albcr="NCHS. NHANES 2007–2008 Albumin & Creatinine – Urine (ALB_CR_E): urine creatinine method change. First published September 2009. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2007/DataFiles/ALB_CR_E.htm",
    l40b="NCHS. NHANES 2001–2002 Standard Biochemistry Profile (L40_B): variables LBDSAPSI, LBDSLDSI, LBDSPH, LBDSTB. First published September 2006. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2001/DataFiles/L40_B.htm",
    biopro_j="NCHS. NHANES 2017–2018 Standard Biochemistry Profile (BIOPRO_J): regression equations for the change from the DxC 660i to the Cobas 6000. First published February 2020. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BIOPRO_J.htm",
    ghb_f="NCHS. NHANES 2009–2010 Glycohemoglobin (GHB_F): shift in the 2007–2010 distribution; use of original values. First published September 2011; last revised March 2012. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2009/DataFiles/GHB_F.htm",
    hbv="Conners EE, Panagiotakopoulos L, Hofmeister MG, et al. Screening and Testing for Hepatitis B Virus Infection: CDC Recommendations — United States, 2023. MMWR Recomm Rep. 2023;72(1):1–25. https://doi.org/10.15585/mmwr.rr7201a1",
    hepc="NCHS. NHANES 2013–2014 Hepatitis C: RNA (HCV-RNA) and Hepatitis C Genotype (HEPC_H). First published October 2015; last revised September 2017. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/HEPC_H.htm",
    a1c="National Institute of Diabetes and Digestive and Kidney Diseases. The A1C Test & Diabetes. Last reviewed April 2018. https://www.niddk.nih.gov/health-information/diagnostic-tests/a1c-test",
    lab13="NCHS. NHANES 1999–2000 Cholesterol – Total & HDL (Lab13). First published June 2002; last revised April 2010. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/1999/DataFiles/LAB13.htm",
    ap="scikit-learn. sklearn.metrics.average_precision_score. https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html",
    vancalster="Van Calster B, McLernon DJ, van Smeden M, Wynants L, Steyerberg EW. Calibration: the Achilles heel of predictive analytics. BMC Med. 2019;17(1):230. https://doi.org/10.1186/s12916-019-1466-7",
    weight="NCHS. NHANES Tutorials: Weighting [undated web page; accessed 2026 Sep 27]. https://wwwn.cdc.gov/nchs/nhanes/tutorials/weighting.aspx",
    rustrao="Rust KF, Rao JNK. Variance estimation for complex surveys using replication techniques. Stat Methods Med Res. 1996;5(3):283–310. https://doi.org/10.1177/096228029600500305",
    parker="Parker JD, Talih M, Malec DJ, et al. National Center for Health Statistics Data Presentation Standards for Proportions. Vital Health Stat 2. 2017;(175):1–22. PMID: 30248016",
    vickers="Vickers AJ, Elkin EB. Decision curve analysis: a novel method for evaluating prediction models. Med Decis Making. 2006;26(6):565–574. https://doi.org/10.1177/0272989X06295361",
    hcvscreen="Schillie S, Wester C, Osborne M, Wesolowski L, Ryerson AB. CDC Recommendations for Hepatitis C Screening Among Adults — United States, 2020. MMWR Recomm Rep. 2020;69(2):1–17. https://doi.org/10.15585/mmwr.rr6902a1",
    bh="Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and powerful approach to multiple testing. J R Stat Soc Series B. 1995;57(1):289–300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x",
    barr="Barr DB, Wilder LC, Caudill SP, et al. Urinary creatinine concentrations in the U.S. population: implications for urinary biologic monitoring measurements. Environ Health Perspect. 2005;113(2):192–200. https://doi.org/10.1289/ehp.7337",
    biopro_l="NCHS. NHANES August 2021–August 2023 Standard Biochemistry Profile (BIOPRO_L): regression equations for the Cobas 6000 to Cobas 8000 change. First published September 2025. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/BIOPRO_L.htm",
    albcr_l="NCHS. NHANES August 2021–August 2023 Albumin & Creatinine – Urine (ALB_CR_L): urine albumin method change. First published September 2025. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/ALB_CR_L.htm",
    trigly_l="NCHS. NHANES August 2021–August 2023 Cholesterol – Low-Density Lipoproteins (LDL) & Triglycerides (TRIGLY_L): triglyceride method change. First published September 2025. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/TRIGLY_L.htm",
    vergouwe="Vergouwe Y, Nieboer D, Oostenbrink R, et al. A closed testing procedure to select an appropriate method for updating prediction models. Stat Med. 2017;36(28):4529–4539. https://doi.org/10.1002/sim.7179",
    collins_ev="Collins GS, Ogundimu EO, Altman DG. Sample size considerations for the external validation of a multivariable prognostic model: a resampling study. Stat Med. 2016;35(2):214–226. https://doi.org/10.1002/sim.6787",
    bashir="Bashir A, Arora R, Mehrotra D, et al. Lipid abnormalities in chronic viral hepatitis: associations and machine learning-enhanced prediction. BMC Gastroenterol. 2026;26:365. https://doi.org/10.1186/s12876-026-04861-y",
    christodoulou="Christodoulou E, Ma J, Collins GS, Steyerberg EW, Verbakel JY, Van Calster B. A systematic review shows no performance benefit of machine learning over logistic regression for clinical prediction models. J Clin Epidemiol. 2019;110:12–22. https://doi.org/10.1016/j.jclinepi.2019.02.004",
    yang="Yang P, Liu Z, Lu F, et al. Machine learning models predicts risk of proliferative lupus nephritis. Front Immunol. 2024;15:1413569. https://doi.org/10.3389/fimmu.2024.1413569",
    riley="Riley RD, Ensor J, Snell KIE, et al. Calculating the sample size required for developing a clinical prediction model. BMJ. 2020;368:m441. https://doi.org/10.1136/bmj.m441",
    cbc_h="NCHS. NHANES 2013–2014 Complete Blood Count with 5-Part Differential – Whole Blood (CBC_H): instrument change without retrospective method comparison. First published July 2016. https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/CBC_H.htm",
    erb="NCHS. NHANES Ethics Review Board Approval [page dated 2026 Mar 24]. https://www.cdc.gov/nchs/nhanes/about/erb.html",
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


def emit(text, fmt):
    for key, f in FIGS.items():
        text = text.replace("{" + key + "}", fmt(f))
    assert "{FIG" not in text and "[@" not in text, "仍有未處理之圖或引用"
    return text


def main():
    obs_fig = os.path.join(VAULT, "figure", "v3_2")
    os.makedirs(obs_fig, exist_ok=True)
    for f in FIGS.values():
        shutil.copy2(os.path.join(ROOT, "figures", "v3_2", f), os.path.join(obs_fig, f))
    fm_ = ("---\ntitle: 常規檢驗能否回推腎炎（腎損傷）的病因方向？（v3.2）\ntype: 研究論文\nversion: 3.2\ncreated: 2026-09-27\n"
           "tags: [腎病病因, NHANES, 重分析, v3.2]\n---\n\n")
    nav = ("> [!info] v3.2：資料修正後重建、非線性模型之校準、網頁工具 v3.2。由 `experiments/kidney_cause/build_paper_v3_2.py` 自結果檔產生"
           "（數字不手打；改內容請改產生程式後重跑）。配套 [[審查意見回應_v3.2]]｜前版 [[研究論文_v3重分析]]\n\n")
    paper = number_refs(PAPER)
    paper_obs = fm_ + nav + emit(paper, lambda f: f"![[figure/v3_2/{f}]]")
    paper_repo = emit(paper, lambda f: f"![](../kidney_cause/figures/v3_2/{f})")
    resp_repo = RESPONSE.replace("[[研究論文_v3.2]]", "研究論文_v3.2.md").replace("[[研究論文_v3重分析]]", "研究論文_v3重分析.md") \
                        .replace("[[審查意見回應_v3]]", "審查意見回應_v3.md")
    assert "{" not in RESPONSE and "[@" not in RESPONSE
    for path, txt in ((os.path.join(VAULT, "研究論文_v3.2.md"), paper_obs), (os.path.join(REPO_DOCS, "研究論文_v3.2.md"), paper_repo),
                      (os.path.join(VAULT, "審查意見回應_v3.2.md"), RESPONSE), (os.path.join(REPO_DOCS, "審查意見回應_v3.2.md"), resp_repo)):
        open(path, "w", encoding="utf-8").write(txt)
        print(f"[寫出] {path}（{len(txt):,} 字元）")


if __name__ == "__main__":
    main()
