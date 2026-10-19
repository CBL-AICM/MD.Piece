# -*- coding: utf-8 -*-
"""把研究報告圖二–圖十一的數據從結果檔匯出成 CSV，供 FigureLabs 重製（數字不手打）。
  python -X utf8 export_figurelabs_csv.py   → figures/figurelabs/data/*.csv（UTF-8 BOM）
B 版編號：圖三 判別力、圖四 校準與分區、圖五 GEO 切片、圖六 穩健性、圖七 外部資料、
          圖八 決策曲線、圖九 暴露、圖十 重新校準、圖十一 九種病因。"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures" / "figurelabs" / "data"
OUT.mkdir(parents=True, exist_ok=True)
J = lambda p: json.load(open(ROOT / p, encoding="utf-8"))
F = J("figures/fair2/fig_data.json")
AXES = {"肝炎": "肝炎軸（感染方向）", "糖尿病": "糖尿病軸（代謝方向）"}
r3 = lambda x: None if x is None else round(x, 6)  # 保留 6 位，避免畫圖時二次四捨五入（如 2.025047→2.025→2.02）


def write(name, header, rows):
    with open(OUT / name, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}\t{len(rows)} 列")


def ci(c):
    return (None, None) if c is None else (c[0], c[1])


# 圖三 判別力
rows = []
for a, t in AXES.items():
    d = F["圖三"][a]
    for metric in ("auroc", "ap"):
        for m in d[metric]:
            rows.append([t, metric.upper(), m["label"], r3(m["mean"]), r3(m["min"]), r3(m["max"]), r3(d["prevalence"])])
write("圖三_判別力.csv", ["方向軸", "指標", "模型", "五次重複平均", "最小", "最大", "盛行率"], rows)

# 圖四 校準曲線＋三段分區
rows, bands = [], []
for a, t in AXES.items():
    d = F["圖四"][a]
    for m in d["models"]:
        for i, p in enumerate(m["curve"], 1):
            rows.append([t, m["label"], r3(m["intercept"]), r3(m["slope"]), i, r3(p["mean_pred"]), r3(p["observed"])])
        for b, v in m["bands"].items():
            bands.append([t, m["label"], b, r3(v["observed_rate"]), v["n"], r3(d["prevalence"])])
write("圖四a_校準曲線.csv", ["方向軸", "模型", "校準截距", "校準斜率", "十分位組", "平均預測機率", "實際陽性比例"], rows)
write("圖四b_三段分區.csv", ["方向軸", "模型", "分區", "實際陽性比例", "人數", "盛行率"], bands)

# 圖五 GEO 切片（同 make_figures_report.fig10）
B, C = J("results/immune_geo_batchsafe.json"), J("results/immune_geo_amendment2.json")
rep = {**B["B4_replication"], **C["C4_replication"]}
dec = {**B["decision"], **C["decision"]}
GEO = [("免疫 對 非免疫", "ANCA 對 DN、FSGS、MCD", B["B1_primary"], rep["B1"], dec["B1_primary"]),
       ("免疫 對 非免疫", "SLE 對 FSGS", B["B3_SLE"], rep["B3"], dec["B3_SLE"]),
       ("免疫 對 代謝", "ANCA 對 DN", B["B2_immune_vs_metabolic"], rep["B2"], dec["B2_immune_vs_metabolic"]),
       ("代謝 對 兩者皆非", "DN 對 FSGS、MCD", C["C1_metabolic_H7"], rep["C1"], dec["C1_metabolic_H7"]),
       ("代謝 對 兩者皆非", "DN 對 MCD、TMD", C["C2_metabolic_H1"], rep["C2"], dec["C2_metabolic_H1"]),
       ("免疫 對 免疫", "SLE 對 MN", C["C3_SLE_vs_MN"], rep["C3"], dec["C3_SLE_vs_MN"])]
MOD = [("PANEL_LR", "免疫路徑模型"), ("GENE_LR", "全基因模型")]
ZH = dict(interferon="干擾素", complement="補體", b_plasma="B／漿細胞", t_cell="T 細胞", myeloid="單核巨噬", neutrophil="嗜中性球")
rows, heat = [], []
for grp, lab, r, t, d in GEO:
    for m, name in MOD:
        lo, hi = ci(r[m]["auroc_ci_rep0"])
        rows.append([grp, lab, r["n_pos"], r["n"] - r["n_pos"], name, r3(r[m]["auroc_mean"]), r3(lo), r3(hi),
                     r3(t[m]["auroc_mean"]), "成立" if d["回推成立"] else "不成立"])
    for p, v in r["per_panel"].items():
        heat.append([lab, ZH[p], r3(v["auroc"])])
write("圖五a_切片判別力.csv", ["比較方向", "比較", "陽性例數", "對照例數", "模型", "腎絲球AUROC（20次平均）",
                          "95%CI下限", "95%CI上限", "腎小管間質AUROC（重現）", "回推判定"], rows)
write("圖五b_各路徑AUROC.csv", ["比較", "免疫路徑", "腎絲球AUROC"], heat)

# 圖六 穩健性
rows = []
for a, t in AXES.items():
    for m in F["圖五"][a]["models"]:
        for c in m["conditions"]:
            lo, hi = ci(c["ci95"])
            rows.append([t, m["label"], c["label"], r3(c["auroc"]), r3(lo), r3(hi)])
write("圖六_穩健性.csv", ["方向軸", "模型", "條件", "AUROC", "95%CI下限", "95%CI上限"], rows)

# 圖七 外部資料
rows = []
for a, t in AXES.items():
    for g in F["圖六"][a]["groups"]:
        for x in g["rows"]:
            lo, hi = ci(x["ci95"])
            rows.append([t, g["name"], g["n_pos"], g["n"], x["label"], r3(x["auroc"]), r3(lo), r3(hi)])
write("圖七_外部資料.csv", ["方向軸", "評估", "陽性數", "總人數", "模型", "AUROC", "95%CI下限", "95%CI上限"], rows)

# 圖八 決策曲線（長格式）
rows = []
for a, t in AXES.items():
    d = F["圖七"][a]
    for c in d["curves"]:
        for pt, nb in zip(d["pt"], c["net_benefit"]):
            rows.append([t, pt, c["label"], round(nb, 5)])
write("圖八_決策曲線.csv", ["方向軸", "閾值機率", "策略", "淨效益"], rows)

# 圖九 暴露
d = F["圖八"]
rows = []
for r in d["rows"]:
    for col, panel in zip(d["columns"], r["panels"]):
        for x in panel:
            lo, hi = ci(x["ci95"])
            rows.append([r["metal"], r["n_both"], col, x["label"], "血中" if x["kind"] == "blood" else "尿中",
                         r3(x["or"]), r3(lo), r3(hi)])
write("圖九_暴露.csv", ["金屬", "人數", "腎臟結果", "測量方式", "檢體", "勝算比", "95%CI下限", "95%CI上限"], rows)

# 圖十 重新校準
rows = []
for a, t in AXES.items():
    d = F["圖九"][a]
    for x in d["rows"]:
        rows.append([t, d["n_pos_test_median"], x["label"], r3(x["median"]), r3(x["p2_5"]), r3(x["p97_5"])])
write("圖十_重新校準.csv", ["方向軸", "測試半陽性中位數", "做法", "平均預測／實際陽性比例（中位數）",
                         "2.5百分位", "97.5百分位"], rows)

# 圖十一 九種病因（同 make_figures_report.fig9）
R = J("results/nine_causes_nhanes.json")
P, PH = R["primary"], R["phenotype"]
DIR = {"糖尿病": "代謝", "肥胖": "代謝", "高尿酸血症": "代謝", "痛風": "代謝", "B型肝炎": "感染", "C型肝炎": "感染", "HIV": "感染"}
rows = []
for dz in [k for k in P if "status" not in P[k]]:
    c = P[dz]["contrasts"]["腎損傷"]["aPR"]
    rows.append([dz, DIR[dz], "腎損傷對無腎損傷", r3(c["est"]), r3(c["ci95"][0]), r3(c["ci95"][1])])
    for k in ("只有白蛋白尿", "只有eGFR<60", "兩者皆有"):
        c = PH[dz]["contrasts"][k]["aPR"]
        rows.append([dz, DIR[dz], f"{k}對兩項皆正常", r3(c["est"]), r3(c["ci95"][0]), r3(c["ci95"][1])])
write("圖十一_九種病因.csv", ["疾病", "方向", "比較", "調整盛行率比", "95%CI下限", "95%CI上限"], rows)
