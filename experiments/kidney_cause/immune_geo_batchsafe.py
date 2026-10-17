# -*- coding: utf-8 -*-
"""immune_geo 修正一：同處理批次內比較（params/immune_geo_amendment_1.json，先提交、後執行）。
輸出 results/immune_geo_batchsafe.json。用法：python immune_geo_batchsafe.py"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

import immune_geo as ig

AMEND = os.path.join(ig.ROOT, "params", "immune_geo_amendment_1.json")
OUT = os.path.join(ig.ROOT, "results", "immune_geo_batchsafe.json")
NONIMMUNE = {"DN", "FSGS", "FSGS_MCD", "MCD"}


def load_batch(series, platform, batch):
    m, X = ig.load(series, platform)
    m["batch"] = m.source.str.extract(r"(H\d+)")[0].values
    keep = (m.batch == batch).values
    return m[keep], X[keep]


def cv_oof_prev(make, X, y, n_rep=20, seed=ig.SEED):
    """折外機率與「訓練折陽性比例」門檻（n_rep × n）。"""
    p, thr = np.zeros((n_rep, len(y))), np.zeros((n_rep, len(y)))
    for r in range(n_rep):
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed + r).split(X, y):
            p[r, te] = make().fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[te])[:, 1]
            thr[r, te] = y[tr].mean()
    return p, thr


def at(y, p, t):
    yhat = (p >= t).astype(int)
    return dict(accuracy=float(accuracy_score(y, yhat)), balanced_accuracy=float(balanced_accuracy_score(y, yhat)),
                sensitivity=float(yhat[y == 1].mean()), specificity=float(1 - yhat[y == 0].mean()))


def evaluate(make, X, y, perm):
    p, thr = cv_oof_prev(make, X, y)
    aucs = [roc_auc_score(y, o) for o in p]
    res = dict(auroc_mean=float(np.mean(aucs)), auroc_min_max=[float(min(aucs)), float(max(aucs))],
               auroc_ci_rep0=ig.boot_auc(y, p[0]),
               threshold_prevalence_rep0=at(y, p[0], thr[0]), threshold_05_rep0=at(y, p[0], 0.5),
               threshold_prevalence_mean20={k: float(np.mean([at(y, p[r], thr[r])[k] for r in range(len(p))]))
                                            for k in ["accuracy", "balanced_accuracy", "sensitivity", "specificity"]},
               brier_rep0=float(np.mean((p[0] - y) ** 2)))
    res["flag_below_040"] = res["auroc_mean"] < 0.40
    if perm:
        res["permutation_p"] = ig.permutation_p(make, X, y, res["auroc_mean"])
    return res


def task(m, X, pos, neg, panels, perm=False, rand=False):
    sel = m.dx.isin(pos | neg).values
    Xs, y = X[sel], m.dx[sel].isin(pos).astype(int).values
    out = dict(groups=m.dx[sel].value_counts().to_dict(), n=int(len(y)), n_pos=int(y.sum()))
    out["PANEL_LR"] = evaluate(lambda: ig.panel_lr(panels), Xs, y, perm)
    out["GENE_LR"] = evaluate(ig.gene_lr, Xs, y, perm)
    out["per_panel"] = ig.per_panel(Xs, y, panels)
    if rand:
        rs = ig.random_sets(Xs, y, panels)
        obs0 = roc_auc_score(y, ig.cv_oof(lambda: ig.panel_lr(panels), Xs, y, n_rep=1)[0])
        out["random_gene_sets"] = dict(n=len(rs), panel_auroc_rep0=float(obs0), median=float(np.median(rs)),
                                       p95=float(np.percentile(rs, 95)), percentile_of_panel=float((rs < obs0).mean() * 100))
    return out


def decide(t, rep):
    ok = {}
    for k in ["PANEL_LR", "GENE_LR"]:
        r = t[k]
        ok[k] = bool(r["auroc_ci_rep0"][0] > 0.5 and r["permutation_p"] < 0.025 and rep[k]["auroc_mean"] > 0.5
                     and not r["flag_below_040"])
    return dict(**ok, 回推成立=any(ok.values()))


def main():
    if os.path.exists(OUT) and "--force" not in sys.argv:
        sys.exit(f"{OUT} 已存在（結果只產生一次）；確定要重跑請加 --force")
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    gH7, XgH7 = load_batch("GSE104948", "GPL22945", "H7")
    gH5, XgH5 = load_batch("GSE104948", "GPL24120", "H5")
    tH7, XtH7 = load_batch("GSE104954", "GPL22945", "H7")
    tH5, XtH5 = load_batch("GSE104954", "GPL24120", "H5")
    panels = ig.panel_probes(XgH7.columns)
    R = dict(amendment_sha256=sha(AMEND), plan_sha256=sha(ig.PLAN_PATH),
             batch_table={f"{s}-{p}": pd.crosstab(m.dx, m.source.str.extract(r"(H\d+)")[0]).to_dict()
                          for s in ["GSE104948", "GSE104954"] for p in ["GPL22945", "GPL24120"]
                          for m in [ig.load(s, p)[0]]})
    R["B1_primary"] = task(gH7, XgH7, {"ANCA"}, NONIMMUNE, panels, perm=True, rand=True)
    R["B2_immune_vs_metabolic"] = task(gH7, XgH7, {"ANCA"}, {"DN"}, panels, perm=True)
    R["B3_SLE"] = task(gH5, XgH5, {"SLE"}, {"FSGS"}, panels, perm=True, rand=True)
    R["B4_replication"] = dict(B1=task(tH7, XtH7, {"ANCA"}, NONIMMUNE, panels),
                               B2=task(tH7, XtH7, {"ANCA"}, {"DN"}, panels),
                               B3=task(tH5, XtH5, {"SLE"}, {"FSGS"}, panels))
    # B5 多類別：H7 四類（FSGS_MCD 併入 FSGS）、H5 三類
    gH7_4 = gH7.copy()
    gH7_4["dx"] = gH7_4.dx.replace({"FSGS_MCD": "FSGS"})
    R["B5_multiclass"] = dict(H7=ig.multiclass(gH7_4, XgH7, panels, classes=("ANCA", "DN", "FSGS", "MCD")),
                              H5=ig.multiclass(gH5, XgH5, panels, classes=("SLE", "MN", "FSGS")))
    R["B6_exploratory_MN_vs_FSGS"] = task(gH5, XgH5, {"MN"}, {"FSGS"}, panels)
    R["not_evaluable"] = "IgAN 只在 H4、HT 只在 H2，同批次內無對照，本資料無法評估"
    R["decision"] = {k: decide(R[k], R["B4_replication"][b])
                     for k, b in [("B1_primary", "B1"), ("B2_immune_vs_metabolic", "B2"), ("B3_SLE", "B3")]}
    R["decision"]["免疫路徑專屬"] = {k: bool(R[k]["random_gene_sets"]["panel_auroc_rep0"] > R[k]["random_gene_sets"]["p95"])
                                for k in ["B1_primary", "B3_SLE"]}
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(R["decision"], ensure_ascii=False))


if __name__ == "__main__":
    main()
