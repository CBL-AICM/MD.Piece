# -*- coding: utf-8 -*-
"""科展作品說明書（使用者修改版）圖二至圖九之數據——自結果檔取出每一個要畫的數字，交給繪圖者（Codex）。
    python export_fig_data_fair2.py   → figures/fair2/fig_data.json
取數邏輯與 make_figures_v3_2 相同（同一批結果檔、同一欄位），只拿掉版本標記：
圖六只留與表十五對應的五列（事前指定評估兩列、資料修正後之檢驗評估三列），圖九只留現行網頁工具（不重新校準／重新校準）。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import make_figures_v3_2 as M   # noqa: E402  （同一批結果檔：AU、E、X、X3）

OUT = os.path.join(ROOT, "figures", "fair2")
KEYS = ("肝炎", "糖尿病")
AXIS = {"肝炎": "肝炎軸（感染方向）", "糖尿病": "糖尿病軸（代謝方向）"}
LABEL = {"肝炎": "肝炎病毒感染標籤", "糖尿病": "糖尿病標籤"}
LR, HG = M.LR, M.HG
MODELS = [("LR_routine", "常規套組・邏輯迴歸", "axis"), ("LR_routine_noHDL", "常規套組・邏輯迴歸（不含 HDL）", "gray"),
          ("HGB_routine", "常規套組・梯度提升", "axis_dark"), ("LR_full", "全特徵・邏輯迴歸", "gray"),
          ("HGB_full", "全特徵・梯度提升", "gray")]
COLORS = {"肝炎": {"axis": "#2a78d6", "axis_dark": "#174a86"}, "糖尿病": {"axis": "#eb6834", "axis_dark": "#a4410f"},
          "gray": "#a3a29d", "ink": "#0b0b0b", "sub": "#52514e", "muted": "#8a8985"}
DISPLAY = {"圖二": (12.96, 9.41), "圖三": (17.0, 8.77), "圖四": (17.0, 11.55), "圖五": (17.0, 5.74), "圖六": (17.0, 6.44),
           "圖七": (17.0, 6.94), "圖八": (17.0, 7.81), "圖九": (17.0, 6.60)}    # 使用者 Word 中之現有寬×高（cm）


def ci(v):
    return [round(v[0], 4), round(v[1], 4)] if v else None


def fig2():
    AU = M.AU
    k = AU["kidney"]["v3_2"]
    tot = lambda tk: {s: sum(c[tk][s] for c in AU["per_cycle"].values()) for s in ("pos", "neg", "unknown")}
    ch = AU["kidney_2017_2018_reported_vs_DxC"]
    av = AU["feature_availability_in_kidney"]
    labels = []
    for key, tk in (("肝炎", "hep_v3_2"), ("糖尿病", "dm_v3_2")):
        t = tot(tk)
        labels.append({"axis": key, "title": LABEL[key], "pos": t["pos"], "neg": t["neg"], "unknown": t["unknown"],
                       "analysis_n": t["pos"] + t["neg"]})
    return {
        "top_box": f"NHANES 1999–2018 十個週期　成人（≧20 歲）\nn = {AU['n_adults']:,}",
        "kidney_box": f"腎臟指標（單次檢驗；eGFR<60 或 ACR≧30 mg/g）三值判定\n異常 {k['pos']:,}　｜　兩項皆測且正常 {k['neg']:,}　｜　未知 {k['unknown']:,}",
        "label_boxes": [{**b, "text": f"{b['title']}\n陽性 {b['pos']:,}　陰性 {b['neg']:,}　未知 {b['unknown']:,}\n→ 該軸分析 n = {b['analysis_n']:,}"}
                        for b in labels],
        "note": "兩個標籤各自判定、可同時成立；各軸只排除該軸未知者",
        "fix_box_title": "資料修正（逐週期核對 CDC 文件後發現，皆能通過檔案雜湊檢查）",
        "fix_box_items": [
            f"① 2001–2002 年鹼性磷酸酶、LDH、磷、總膽紅素以另一變數名發布，原被整週期當成缺值 → 對應後有值 {av['LBXSAPSI']['2001-2002']:.0%}",
            "② 2017–2018 年生化儀器更換，依 CDC 回推式把 12 項檢驗（含肌酸酐）換回 1999–2016 年之量尺",
            f"　 → 該週期原判腎臟指標異常者中 {sum(ch.values())} 人改判（{ch.get('1→0', 0)} 人改為兩項皆正常、{ch.get('1→-1', 0)} 人改為未知）",
            f"③ HDL 膽固醇 2005 年起未讀入、1999–2004 年被封存規則誤排除 → 恢復（各週期有值 ≧{min(av['LBDHDL'].values()):.0%}）"],
    }


def fig3():
    out = {}
    for key in KEYS:
        a = M.E[key]
        d = a["M1_demographics"]
        panels = {}
        for metric in ("auroc", "ap"):
            rows = [{"label": "只用年齡、性別", "role": "baseline", "mean": d[f"{metric}_mean"], "min": d[f"{metric}_range"][0],
                     "max": d[f"{metric}_range"][1]}]
            for m, lab, role in MODELS:
                r = a["models"][m]["repeats"]
                rows.append({"label": lab, "role": role, "mean": r["mean"][metric], "min": r["min"][metric], "max": r["max"][metric]})
            panels[metric] = rows
        out[key] = {"title": AXIS[key], "prevalence": a["prevalence"], **panels}
    return out


def fig4():
    out = {}
    for key in KEYS:
        a = M.E[key]
        models = []
        for m, lab, role in ((LR, "常規套組・邏輯迴歸", "axis"), (HG, "常規套組・梯度提升", "axis_dark")):
            s = a["models"][m]
            bt = s["bands_tool_repeat0"]
            models.append({"label": lab, "role": role, "intercept": s["calibration_repeat0"]["intercept"],
                           "slope": s["calibration_repeat0"]["slope"],
                           "curve": [{"mean_pred": p["mean_pred"], "observed": p["observed"]} for p in s["calibration_curve_repeat0"]],
                           "bands": {b: {"observed_rate": bt["band"][b]["observed_rate"], "n": bt["band"][b]["n"]} for b in ("傾向", "不確定", "不傾向")},
                           "coverage": bt["coverage"]})
        out[key] = {"title": AXIS[key], "prevalence": a["prevalence"], "insufficient_n": a["models"][LR]["bands_tool_repeat0"]["band"]["資料不足"]["n"],
                    "models": models}
    return out


def fig5():
    out = {}
    for key in KEYS:
        a = M.E[key]
        models = []
        for m, lab, role in ((LR, "常規套組・邏輯迴歸", "axis"), (HG, "常規套組・梯度提升", "axis_dark")):
            s = a["models"][m]
            w = a["design_weighted"][m]["weighted"]["auroc"]
            models.append({"label": lab, "role": role, "conditions": [
                {"label": "巢狀外層（主要分析）", "auroc": s["repeats"]["mean"]["auroc"], "ci95": ci(s["ci95_repeat0"]["auroc"])},
                {"label": "時間外推", "auroc": a["temporal"][m]["auroc"], "ci95": ci(a["temporal"][m]["ci95"]["auroc"])},
                {"label": "人口加權", "auroc": w["est"], "ci95": ci(w["ci95"])},
                {"label": "腎臟標籤用原發布肌酸酐", "auroc": a["kidney_label_as_reported"][m]["auroc"], "ci95": None}]})
        out[key] = {"title": AXIS[key], "models": models}
    return out


def fig6():
    out = {}
    for key in KEYS:
        m3, xa = M.X3[key]["models"], M.X["axes"][key]
        row = lambda lab, m, role: {"label": lab, "role": role, "auroc": m["auroc"], "ci95": ci(m["ci95"]["auroc"])}
        out[key] = {"title": AXIS[key], "groups": [
            {"name": "事前指定評估（資料修正前）", "n_pos": M.X3[key]["n_pos"], "n": M.X3[key]["n"],
             "rows": [row("全特徵邏輯迴歸", m3["v3_full_LR（部署）"], "gray"), row("常規套組邏輯迴歸", m3["v3_basic_LR（常規套組候選）"], "gray")]},
            {"name": "檢驗評估（資料修正後）", "n_pos": xa["n_pos"], "n": xa["n"],
             "rows": [row("只用年齡、性別", xa["M1_demographics"], "baseline"), row("常規套組邏輯迴歸", xa["models"][LR], "axis"),
                      row("常規套組梯度提升", xa["models"][HG], "axis_dark")]}]}
    return out


def fig7():
    out = {}
    for key in KEYS:
        dc = M.E[key]["decision_curve"]
        b = M.E[key]["models"][LR]["bands_tool_repeat0"]["per_1000_if_skip_low"]
        out[key] = {"title": AXIS[key], "pt": [r["pt"] for r in dc[LR]],
                    "curves": [{"label": "依常規套組・邏輯迴歸送驗", "role": "axis", "net_benefit": [r["nb_model"] for r in dc[LR]]},
                               {"label": "依常規套組・梯度提升送驗", "role": "axis_dark", "net_benefit": [r["nb_model"] for r in dc[HG]]},
                               {"label": "全數送驗", "role": "test_all_gray_dotted", "net_benefit": [r["nb_test_all"] for r in dc[LR]]},
                               {"label": "全不送驗", "role": "test_none_black_solid", "net_benefit": [0.0] * len(dc[LR])}],
                    "annotation": {"text": (f"若只略過「不傾向」區（邏輯迴歸）：\n每千人送驗 {b['tested']:.0f}、漏 {b['missed']:.1f} 名陽性\n"
                                            f"（占陽性 {b['missed_share_of_pos']:.0%}）"),
                                   "tested_per_1000": b["tested"], "missed_per_1000": b["missed"], "missed_share": b["missed_share_of_pos"]}}
        assert all(a["pt"] == c["pt"] for a, c in zip(dc[LR], dc[HG]))
    return out


def fig8():
    X = json.load(open(os.path.join(ROOT, "results", "exwas_v3_2_checks.json"), encoding="utf-8"))
    outs = [("kidney_damage", "腎臟指標異常（eGFR<60 或 ACR≧30）"), ("egfr_lt60", "僅 eGFR<60（與尿肌酸酐無共同分母）"), ("acr_ge30", "僅 ACR≧30")]
    meas = [("血中", "血中"), ("尿中_原濃度", "尿中（原濃度）"), ("尿中_原濃度＋尿肌酸酐共變數", "尿中（＋尿肌酸酐共變數）"), ("尿中_肌酸酐比值", "尿中（肌酸酐比值）")]
    out = {"x_label": "勝算比（濃度加倍；調整人口學、體位、抽菸、糖尿病與高血壓；95% CI，對數刻度）", "columns": [o[1] for o in outs],
           "rows": []}
    for metal in ("鉛", "鎘"):
        Mm = X["metals"][metal]
        out["rows"].append({"metal": metal, "n_both": Mm["n_both"], "panels": [
            [{"label": lab, "kind": "blood" if mk == "血中" else "urine", "or": Mm["models"][ok][mk]["OR_per_doubling"],
              "ci95": ci(Mm["models"][ok][mk]["ci"])} for mk, lab in meas] for ok, _ in outs]})
    return out


def fig9():
    cv = M.X["recalibration_cv"]["v3.2"]    # 現行網頁工具
    out = {}
    for key in KEYS:
        s = cv[key]["random_summary"]
        q = lambda d: {"median": d["median"], "p2_5": d["p2_5"], "p97_5": d["p97_5"]}
        out[key] = {"title": AXIS[key], "n_pos_test_median": s["n_pos_test"]["median"],
                    "rows": [{"label": "不重新校準", "role": "gray", **q(s["oe_none"])}, {"label": "重新校準", "role": "axis", **q(s["oe_recal"])}]}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    data = {"colors": COLORS, "display_cm": {k: {"width": w, "current_height": h} for k, (w, h) in DISPLAY.items()},
            "圖二": fig2(), "圖三": fig3(), "圖四": fig4(), "圖五": fig5(), "圖六": fig6(), "圖七": fig7(), "圖八": fig8(), "圖九": fig9()}
    txt = json.dumps(data, ensure_ascii=False, indent=1)
    assert "v3" not in txt.replace("v3_2", "") and "V3" not in txt, "數據檔仍含版本字樣"
    open(os.path.join(OUT, "fig_data.json"), "w", encoding="utf-8").write(txt)
    print(f"[完成] figures/fair2/fig_data.json（{len(txt):,} 字元）")


if __name__ == "__main__":
    main()
