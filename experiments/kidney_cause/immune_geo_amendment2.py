# -*- coding: utf-8 -*-
"""immune_geo 修正二：代謝方向本身＋SLE 對 MN（params/immune_geo_amendment_2.json，先提交、後執行）。
模型、交叉驗證、置換、門檻、判定規則全部沿用修正一（immune_geo_batchsafe）。
輸出 results/immune_geo_amendment2.json。用法：python immune_geo_amendment2.py"""
import hashlib
import json
import os
import sys

import numpy as np
from sklearn.metrics import roc_auc_score

import immune_geo as ig
import immune_geo_batchsafe as bs

AMEND = os.path.join(ig.ROOT, "params", "immune_geo_amendment_2.json")
OUT = os.path.join(ig.ROOT, "results", "immune_geo_amendment2.json")
NEITHER = {"FSGS", "FSGS_MCD", "MCD"}


def interferon_test(m, X, pos, neg, panels, n_perm=10_000):
    """干擾素單路徑分數（非監督）AUROC、bootstrap CI、單側置換 p。"""
    sel = m.dx.isin(pos | neg).values
    y = m.dx[sel].isin(pos).astype(int).values
    s = ig.PanelScore({"interferon": panels["interferon"]}).fit(X[sel]).transform(X[sel])[:, 0]
    auc = roc_auc_score(y, s)
    rng = np.random.default_rng(ig.SEED)
    hits = sum(roc_auc_score(rng.permutation(y), s) >= auc for _ in range(n_perm))
    return dict(auroc=float(auc), ci=ig.boot_auc(y, s), permutation_p=(hits + 1) / (n_perm + 1))


def main():
    if os.path.exists(OUT) and "--force" not in sys.argv:
        sys.exit(f"{OUT} 已存在（結果只產生一次）；確定要重跑請加 --force")
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    g7, Xg7 = bs.load_batch("GSE104948", "GPL22945", "H7")
    g1, Xg1 = bs.load_batch("GSE104948", "GPL24120", "H1")
    g5, Xg5 = bs.load_batch("GSE104948", "GPL24120", "H5")
    t7, Xt7 = bs.load_batch("GSE104954", "GPL22945", "H7")
    t1, Xt1 = bs.load_batch("GSE104954", "GPL24120", "H1")
    t5, Xt5 = bs.load_batch("GSE104954", "GPL24120", "H5")
    panels = ig.panel_probes(Xg7.columns)  # 與修正一相同
    R = dict(amendment_sha256=sha(AMEND), amendment_1_sha256=sha(bs.AMEND), plan_sha256=sha(ig.PLAN_PATH))
    R["C1_metabolic_H7"] = bs.task(g7, Xg7, {"DN"}, NEITHER, panels, perm=True)
    R["C2_metabolic_H1"] = bs.task(g1, Xg1, {"DN"}, {"MCD", "TMD"}, panels, perm=True)
    R["C3_SLE_vs_MN"] = bs.task(g5, Xg5, {"SLE"}, {"MN"}, panels, perm=True, rand=True)
    R["C4_replication"] = dict(C1=bs.task(t7, Xt7, {"DN"}, NEITHER, panels),
                               C2=bs.task(t1, Xt1, {"DN"}, {"MCD", "TMD"}, panels),
                               C3=bs.task(t5, Xt5, {"SLE"}, {"MN"}, panels))
    R["interferon_test"] = dict(glom=interferon_test(g5, Xg5, {"SLE"}, {"MN"}, panels),
                                tubint=interferon_test(t5, Xt5, {"SLE"}, {"MN"}, panels))
    D = {k: bs.decide(R[k], R["C4_replication"][b])
         for k, b in [("C1_metabolic_H7", "C1"), ("C2_metabolic_H1", "C2"), ("C3_SLE_vs_MN", "C3")]}
    rs = R["C3_SLE_vs_MN"]["random_gene_sets"]
    D["免疫路徑專屬_C3"] = bool(rs["panel_auroc_rep0"] > rs["p95"])
    it = R["interferon_test"]
    D["干擾素專屬狼瘡_C3"] = bool(it["glom"]["ci"][0] > 0.5 and it["glom"]["permutation_p"] < 0.05
                              and it["tubint"]["auroc"] > 0.5)
    pp = R["C3_SLE_vs_MN"]["per_panel"]
    D["描述_干擾素為最高路徑_C3"] = max(pp, key=lambda k: pp[k]["auroc"]) == "interferon"
    D["批次記憶警示"] = {k: [m for m in ["PANEL_LR", "GENE_LR"] if R[k][m]["flag_below_040"]]
                    for k in ["C1_metabolic_H7", "C2_metabolic_H1", "C3_SLE_vs_MN"]}
    R["decision"] = D
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(D, ensure_ascii=False))


if __name__ == "__main__":
    main()
