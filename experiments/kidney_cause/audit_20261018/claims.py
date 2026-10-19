# -*- coding: utf-8 -*-
"""新寫段落之逐項數字核對：每一項＝（文件中應出現的字串，由結果檔重算的值）。
文件字串要在指定文件全文中找得到，且等於重算值；不符即列出。用法：python claims.py <results_dir>"""
import json
import os
import sys

R = sys.argv[1]
J = lambda n: json.load(open(os.path.join(R, n), encoding="utf-8"))
G0, B, C, N, PV = J("immune_geo.json"), J("immune_geo_batchsafe.json"), J("immune_geo_amendment2.json"), J("nine_causes_nhanes.json"), J("provenance.json")["files"]
f2 = lambda x: f"{x:.2f}"
f3 = lambda x: f"{x:.3f}"
pc = lambda x, d=1: f"{x * 100:.{d}f}%"
ci2 = lambda c: f"{c[0]:.2f}–{c[1]:.2f}"
pv = lambda p: "< 0.001" if p < 0.001 else f"＝ {p:.3f}"
n = lambda x: f"{x:,}"

claims = []
add = lambda label, s: claims.append((label, s))

# 前置：舊版（跨批次）
add("跨批次全基因 CV", f"AUROC 只有 {f3(G0['T1_primary']['GENE_LR']['auroc_mean'])}")
add("跨批次保留測試集", f"保留測試集 {f3(G0['T1_primary']['holdout']['GENE_LR']['auroc'])}")
add("路徑基因數", f"共 {sum(G0['panels'].values())} 個基因")
# 修正一
b1, b2, b3, r = B["B1_primary"], B["B2_immune_vs_metabolic"], B["B3_SLE"], B["B4_replication"]
add("B1 全基因", f"全基因模型 AUROC {f3(b1['GENE_LR']['auroc_mean'])}（置換 p {pv(b1['GENE_LR']['permutation_p'])}）")
add("B1 路徑", f"免疫路徑模型 {f3(b1['PANEL_LR']['auroc_mean'])}（置換 p {pv(b1['PANEL_LR']['permutation_p'])}）")
add("B1 隨機中位數", f"中位數已有 {f3(b1['random_gene_sets']['median'])}")
add("B1 百分位", f"第 {b1['random_gene_sets']['percentile_of_panel']:.1f} 百分位")
add("B3 路徑", f"免疫路徑模型 {f3(b3['PANEL_LR']['auroc_mean'])}（置換 p {pv(b3['PANEL_LR']['permutation_p'])}）")
assert b3["random_gene_sets"]["percentile_of_panel"] == 100.0
add("B3 全基因", f"全基因模型 {f3(b3['GENE_LR']['auroc_mean'])}（置換 p {pv(b3['GENE_LR']['permutation_p'])}）")
add("B1/B3 重現", f"{f2(r['B1']['PANEL_LR']['auroc_mean'])}／{f2(r['B1']['GENE_LR']['auroc_mean'])} 與 {f2(r['B3']['PANEL_LR']['auroc_mean'])}／{f2(r['B3']['GENE_LR']['auroc_mean'])}")
add("B2 例數", f"（{b2['n_pos']} 對 {b2['n'] - b2['n_pos']} 例）")
add("B2 全基因", f"全基因模型 AUROC {f3(b2['GENE_LR']['auroc_mean'])}（置換 p {pv(b2['GENE_LR']['permutation_p'])}）")
add("B2 路徑", f"免疫路徑模型只有 {f3(b2['PANEL_LR']['auroc_mean'])}（置換 p {pv(b2['PANEL_LR']['permutation_p'])}）")
# 修正二
c1, c2, c3, c4, it = C["C1_metabolic_H7"], C["C2_metabolic_H1"], C["C3_SLE_vs_MN"], C["C4_replication"], C["interferon_test"]
add("C1 例數", f"（H7，{c1['n_pos']} 對 {c1['n'] - c1['n_pos']} 例）")
add("C1 路徑", f"免疫路徑模型 AUROC {f3(c1['PANEL_LR']['auroc_mean'])}（置換 p {pv(c1['PANEL_LR']['permutation_p'])}）")
add("C1 全基因", f"全基因模型 {f3(c1['GENE_LR']['auroc_mean'])}（置換 p {pv(c1['GENE_LR']['permutation_p'])}）")
add("C2 例數", f"（H1，{c2['n_pos']} 對 {c2['n'] - c2['n_pos']} 例）")
add("C2 兩模型", f"分別為 {f3(c2['PANEL_LR']['auroc_mean'])}（置換 p {pv(c2['PANEL_LR']['permutation_p'])}）與 {f3(c2['GENE_LR']['auroc_mean'])}（置換 p {pv(c2['GENE_LR']['permutation_p'])}）")
pts = [c1[m]["auroc_mean"] for m in ("PANEL_LR", "GENE_LR")] + [c2[m]["auroc_mean"] for m in ("PANEL_LR", "GENE_LR")]
add("C1C2 點估計範圍", f"點估計介於 {f2(min(pts))} 至 {f2(max(pts))}")
tub = [c4[k][m]["auroc_mean"] for k in ("C1", "C2") for m in ("PANEL_LR", "GENE_LR")]
add("C1C2 腎小管範圍", f"腎小管間質重做為 {f2(min(tub))} 至 {f2(max(tub))}")
add("C3 例數", f"（{c3['n_pos']} 對 {c3['n'] - c3['n_pos']} 例）")
add("C3 路徑", f"免疫路徑模型 AUROC {f3(c3['PANEL_LR']['auroc_mean'])}（置換 p {pv(c3['PANEL_LR']['permutation_p'])}）")
add("C3 全基因", f"全基因模型 {f3(c3['GENE_LR']['auroc_mean'])}（置換 p {pv(c3['GENE_LR']['permutation_p'])}）")
add("C3 腎小管", f"腎小管間質為 {f3(c4['C3']['PANEL_LR']['auroc_mean'])}／{f3(c4['C3']['GENE_LR']['auroc_mean'])}")
print("interferon_test keys:", json.dumps(it, ensure_ascii=False)[:600])
pp = c3["per_panel"]
add("C3 巨噬細胞/補體", f"單核巨噬細胞（{f3(pp['myeloid']['auroc'])}）與補體（{f3(pp['complement']['auroc'])}）")
pb1 = b1["per_panel"]
add("B1 單路徑", f"單核巨噬細胞（{f2(pb1['myeloid']['auroc'])}）、補體（{f2(pb1['complement']['auroc'])}）與嗜中性球（{f2(pb1['neutrophil']['auroc'])}）")
p1 = c1["per_panel"]
add("C1 單路徑", f"AUROC {f2(p1['complement']['auroc'])}、{f2(p1['myeloid']['auroc'])}、{f2(p1['t_cell']['auroc'])}")
add("DN 干擾素腎絲球", f"偏低（{f2(c1['per_panel']['interferon']['auroc'])}、{f2(c2['per_panel']['interferon']['auroc'])}）")
add("DN 干擾素腎小管", f"（{f2(c4['C1']['per_panel']['interferon']['auroc'])}、{f2(c4['C2']['per_panel']['interferon']['auroc'])}）")
# 表十三
for lab, t, rr in [("T B1", b1, r["B1"]), ("T B3", b3, r["B3"]), ("T B2", b2, r["B2"]), ("T C1", c1, c4["C1"]), ("T C2", c2, c4["C2"]), ("T C3", c3, c4["C3"])]:
    add(lab, f"{f3(t['PANEL_LR']['auroc_mean'])}（{ci2(t['PANEL_LR']['auroc_ci_rep0'])}） | {f3(t['GENE_LR']['auroc_mean'])}（{ci2(t['GENE_LR']['auroc_ci_rep0'])}） | {f2(rr['PANEL_LR']['auroc_mean'])}／{f2(rr['GENE_LR']['auroc_mean'])}")
# 九種病因
P = N["primary"]
for dz in ["糖尿病", "肥胖", "高尿酸血症", "痛風", "B型肝炎", "C型肝炎", "HIV"]:
    g, a = P[dz]["groups"], P[dz]["contrasts"]["腎損傷"]["aPR"]
    pd = 2 if g["腎損傷"]["prevalence"] < 0.02 else 1
    add(f"表 {dz}", f"{n(g['腎損傷']['n_events'])}／{n(g['腎損傷']['n'])}；{pc(g['腎損傷']['prevalence'], pd)} | {n(g['無腎損傷']['n_events'])}／{n(g['無腎損傷']['n'])}；{pc(g['無腎損傷']['prevalence'], pd)} | {f2(a['est'])}（{ci2(a['ci95'])}）")
s = N["sensitivity"]["HIV_20至49歲"]["contrasts"]["腎損傷"]["aPR"]
add("HIV 敏感度", f"（{f2(s['est'])}，95% CI {ci2(s['ci95'])}）")
ph = N["phenotype"]
u = ph["高尿酸血症"]["contrasts"]
add("尿酸 eGFR", f"只有 eGFR < 60 為 {f2(u['只有eGFR<60']['aPR']['est'])}，95% CI {ci2(u['只有eGFR<60']['aPR']['ci95'])}；只有白蛋白尿為 {f2(u['只有白蛋白尿']['aPR']['est'])}")
for dz, lab in [("糖尿病", "糖尿病"), ("C型肝炎", "C 型肝炎"), ("HIV", "HIV")]:
    a = ph[dz]["contrasts"]["只有白蛋白尿"]["aPR"]
    add(f"白蛋白尿 {dz}", f"{lab} {f2(a['est'])}，95% CI {ci2(a['ci95'])}")
# 檔案數與容量
nh = {k: v for k, v in PV.items() if k.lower().endswith(".xpt")}
geo = {k: v for k, v in PV.items() if not k.lower().endswith(".xpt")}
mb = lambda d: sum(v["bytes"] for v in d.values()) / 1e6
add("檔案總數容量", f"合計 {len(PV)} 個檔案、約 {mb(PV):.0f} MB（NHANES {len(nh)} 個、約 {mb(nh):.0f} MB；切片轉錄體 {len(geo)} 個、約 {mb(geo):.0f} MB）")
add("腎絲球例數", "GSE104948 為腎絲球 196 例")
add("腎小管例數", "GSE104954 為腎小管間質 195 例")

for doc in ["B_fair", "A_tisf"]:
    Jd = json.load(open(f"{doc}.json", encoding="utf-8"))
    txt = "\n".join(i["text"] for i in Jd["items"] if i["kind"] == "para") + "\n" + "\n".join(
        " | ".join(row) for i in Jd["items"] if i["kind"] == "table" for row in i["rows"])
    txt = txt.replace("−", "-")
    ok, bad = 0, []
    for lab, s in claims:
        if s.replace("−", "-") in txt:
            ok += 1
        else:
            bad.append((lab, s))
    print(f"== {doc}: {ok} 項在文中找到與重算一致；{len(bad)} 項找不到（可能是寫法不同或數字不符，需人工看）")
    for lab, s in bad:
        print("   -", lab, "::", s)
