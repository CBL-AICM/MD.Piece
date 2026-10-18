# -*- coding: utf-8 -*-
"""獨立重算 immune_geo 修正二（不 import immune_geo／immune_geo_amendment2）：
自行解析 series matrix、自行由來源名稱取批次、自行對應診斷與基因，重算 C1–C3 與腎小管重現之 20 次平均 AUROC、
第 0 次重複 95% CI（bootstrap 2,000）、各路徑單獨 AUROC，與結果檔逐項比較。用法：python recompute_c.py <kidney_cause_dir>"""
import gzip
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

KC = sys.argv[1]
RAW = os.path.join(KC, "data", "raw", "geo")
RES = json.load(open(os.path.join(KC, "results", "immune_geo_amendment2.json"), encoding="utf-8"))
PLAN = json.load(open(os.path.join(KC, "params", "immune_geo_plan.json"), encoding="utf-8"))
SEED = 20261017


def parse(fn):
    hdr = {}
    with gzip.open(os.path.join(RAW, fn), "rt", encoding="utf-8") as f:
        lines = f.read().split("\n")
    for ln in lines:
        if ln.startswith("!Sample_"):
            k, *v = ln.split("\t")
            hdr.setdefault(k, []).append([x.strip('"') for x in v])
    b = lines.index("!series_matrix_table_begin")
    e = lines.index("!series_matrix_table_end")
    rows = [ln.split("\t") for ln in lines[b + 1:e]]
    cols = [c.strip('"') for c in rows[0][1:]]
    X = pd.DataFrame([[float(x) for x in r[1:]] for r in rows[1:]], index=[r[0].strip('"') for r in rows[1:]], columns=cols).T
    src = hdr["!Sample_source_name_ch1"][0]
    dxrow = [r for r in hdr["!Sample_characteristics_ch1"] if any("diagnosis" in x for x in r) or not any("tissue" in x for x in r)][0]
    dx = [x.split(":", 1)[1].strip().lower() if ":" in x else "" for x in dxrow]
    return X, pd.DataFrame({"src": src, "dx": dx, "batch": [re.search(r"(H\d+)-", s).group(1) for s in src]}, index=cols)


def code(s):
    if s == "":
        return "LD"
    table = {"diabetic nephropathy": "DN", "minimal change disease": "MCD", "thin membrande disease": "TMD",
             "membranous glomerulonephropathy": "MN", "systemic lupus erythematosus": "SLE",
             "focal segmental glomerular sclerosis": "FSGS", "focal segmental glomerulosclerosis": "FSGS",
             "focal segmental glomerular sclerosis/minimal change disease": "FSGS_MCD",
             "focal segmental glomerulosclerosis and minimal change disease": "FSGS_MCD",
             "anca associated vasculitis": "ANCA", "anca-associated vasculitis": "ANCA",
             "iga nephropathy": "IgAN", "hypertensive nephropathy": "HT", "tumor nephrectomy": "TN"}
    return table[s]


gi = pd.read_csv(os.path.join(RAW, "Homo_sapiens.gene_info.gz"), sep="\t", usecols=["GeneID", "Symbol"])
s2id = dict(zip(gi.Symbol, gi.GeneID))
PAN = {k: [f"{s2id[g]}_at" for g in v] for k, v in PLAN["features"]["panels"].items()}


def panel_scores(Xtr, Xte):
    out = []
    for genes in PAN.values():
        mu, sd = Xtr[genes].mean(), Xtr[genes].std(ddof=0).replace(0, 1)
        out.append(((Xte[genes] - mu) / sd).mean(axis=1).values)
    return np.column_stack(out)


def fit_pred(kind, Xtr, ytr, Xte):
    if kind == "PANEL":
        Ptr, Pte = panel_scores(Xtr, Xtr), panel_scores(Xtr, Xte)
        sc = StandardScaler().fit(Ptr)
        m = LogisticRegression(C=1.0, max_iter=5000).fit(sc.transform(Ptr), ytr)
        return m.predict_proba(sc.transform(Pte))[:, 1]
    sc = StandardScaler().fit(Xtr)
    m = LogisticRegression(C=0.01, max_iter=5000).fit(sc.transform(Xtr), ytr)
    return m.predict_proba(sc.transform(Xte))[:, 1]


def cv(kind, X, y, reps=20):
    aucs, p0 = [], None
    for r in range(reps):
        p = np.zeros(len(y))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED + r).split(X, y):
            p[te] = fit_pred(kind, X.iloc[tr], y[tr], X.iloc[te])
        aucs.append(roc_auc_score(y, p))
        if r == 0:
            p0 = p
    rng, a = np.random.default_rng(SEED), []
    while len(a) < 2000:
        b = rng.choice(len(y), len(y))
        if 0 < y[b].sum() < len(b):
            a.append(roc_auc_score(y[b], p0[b]))
    return float(np.mean(aucs)), [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def perpanel(X, y):
    sc = panel_scores(X, X)
    return {k: float(roc_auc_score(y, sc[:, i])) for i, k in enumerate(PAN)}


data = {}
for s in ["GSE104948", "GSE104954"]:
    for p in ["GPL22945", "GPL24120"]:
        X, M = parse(f"{s}-{p}.txt.gz")
        M["dx"] = M["dx"].map(code)
        data[(s, p)] = (X, M)


def task(series, plat, batch, pos, neg):
    X, M = data[(series, plat)]
    sel = (M.batch == batch) & M.dx.isin(pos | neg)
    return X[sel.values], M.dx[sel].isin(pos).astype(int).values


TASKS = {"C1_metabolic_H7": ("GPL22945", "H7", {"DN"}, {"FSGS", "FSGS_MCD", "MCD"}),
         "C2_metabolic_H1": ("GPL24120", "H1", {"DN"}, {"MCD", "TMD"}),
         "C3_SLE_vs_MN": ("GPL24120", "H5", {"SLE"}, {"MN"})}
rows = []
for key, (plat, bt, pos, neg) in TASKS.items():
    for comp, series, ref in [("glom", "GSE104948", RES[key]), ("tub", "GSE104954", RES["C4_replication"][key[:2]])]:
        X, y = task(series, plat, bt, pos, neg)
        assert int(y.sum()) == ref.get("n_pos", y.sum()) or comp == "tub", (key, comp)
        for kind, mk in [("PANEL", "PANEL_LR"), ("GENE", "GENE_LR")]:
            m, c = cv(kind, X, y)
            r_m = ref[mk]["auroc_mean"]
            rows.append((key, comp, kind, "auroc_mean", m, r_m))
            if "auroc_ci_rep0" in ref[mk]:
                rows.append((key, comp, kind, "ci_lo", c[0], ref[mk]["auroc_ci_rep0"][0]))
                rows.append((key, comp, kind, "ci_hi", c[1], ref[mk]["auroc_ci_rep0"][1]))
        pp = perpanel(X, y)
        for k, v in pp.items():
            if "per_panel" in ref:
                rows.append((key, comp, "panel", k, v, ref["per_panel"][k]["auroc"]))
        print(key, comp, "n", len(y), "pos", int(y.sum()))
it = RES["interferon_test"]
bad = [r for r in rows if abs(r[4] - r[5]) > 1e-3]
print(f"比對 {len(rows)} 項；差距 >0.001 者 {len(bad)} 項；最大差距 {max(abs(r[4] - r[5]) for r in rows):.2e}")
for r in bad:
    print("  不符:", r)
print("干擾素單獨（結果檔）glom", round(it["glom"]["auroc"], 4), "tub", round(it["tubint"]["auroc"], 4))
json.dump([list(r) for r in rows], open("recompute_c_out.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
