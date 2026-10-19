# -*- coding: utf-8 -*-
"""免疫方向補強：NIH NCBI GEO 腎臟切片轉錄體（ERCB，GSE104948／GSE104954）。

計畫：params/immune_geo_plan.json（先提交、後執行）。輸出：results/immune_geo.json。
用法：python immune_geo.py"""
import gzip
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
import provenance  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw", "geo")
PLAN_PATH = os.path.join(ROOT, "params", "immune_geo_plan.json")
OUT = os.path.join(ROOT, "results", "immune_geo.json")
PLAN = json.load(open(PLAN_PATH, encoding="utf-8"))
SEED = 20261017

# 診斷字串（兩系列大小寫不同）→ 代碼；空白＝活體捐贈者（來源名稱含 LD，見計畫 pre_run_facts）
DX = [("lupus", "SLE"), ("iga nephropathy", "IgAN"), ("anca", "ANCA"), ("diabetic", "DN"),
      ("hypertensive", "HT"), ("membranous", "MN"), ("segmental glomerular sclerosis/minimal", "FSGS_MCD"),
      ("glomerulosclerosis and minimal", "FSGS_MCD"), ("segmental", "FSGS"), ("minimal change", "MCD"),
      ("thin membran", "TMD"), ("tumor nephrectomy", "TN")]
SHARED = ["LD", "TN", "DN", "FSGS", "MCD", "FSGS_MCD"]  # 兩平台都有的類別＝平台校正參考
IMMUNE, METABOLIC = {"SLE", "IgAN", "ANCA"}, {"DN", "HT"}


def dx_code(s):
    s = s.lower().replace("diagnosis:", "").strip()
    if not s:
        return "LD"
    for key, code in DX:
        if key in s:
            return code
    raise ValueError(f"未知診斷：{s}")


def load(series, platform):
    path = os.path.join(RAW, f"{series}-{platform}.txt.gz")
    provenance.require_real(path)
    meta, rows = {}, []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("!series_matrix_table_begin"):
                break
            if line.startswith(("!Sample_geo_accession", "!Sample_source_name_ch1", "!Sample_characteristics_ch1")):
                k, *v = line.rstrip("\n").split("\t")
                v = [x.strip('"') for x in v]
                if k == "!Sample_characteristics_ch1":
                    k = "tissue" if v[0].startswith("tissue") else "diagnosis"
                meta[k] = v
        expr = pd.read_csv(f, sep="\t", index_col=0, comment="!", quotechar='"')
    m = pd.DataFrame({"gsm": meta["!Sample_geo_accession"], "source": meta["!Sample_source_name_ch1"],
                      "dx": [dx_code(d) for d in meta["diagnosis"]]})
    assert all(("LD" in s) == (d == "LD") for s, d in zip(m.source, m.dx)), "空白診斷應恰為 LD"
    m["platform"], m["series"] = platform, series
    expr = expr[m.gsm]
    assert expr.notna().all().all()
    return m.set_index("gsm"), expr.T  # 樣本 × 基因


def symbol_to_probe():
    path = os.path.join(RAW, "Homo_sapiens.gene_info.gz")
    provenance.require_real(path)
    gi = pd.read_csv(path, sep="\t", usecols=["GeneID", "Symbol"])
    return {s: f"{g}_at" for g, s in zip(gi.GeneID, gi.Symbol)}


def panel_probes(columns):
    s2p, cols = symbol_to_probe(), set(columns)
    out = {}
    for name, genes in PLAN["features"]["panels"].items():
        probes = [s2p[g] for g in genes if g in s2p and s2p[g] in cols]
        assert len(probes) == len(genes), f"{name} 有基因不在平台上（計畫已剔除缺者）"
        out[name] = probes
    return out


class PanelScore(BaseEstimator, TransformerMixin):
    """路徑分數＝該路徑基因（訓練折內標準化後）z 值平均；標準化參數只來自 fit 的資料。"""

    def __init__(self, panels):
        self.panels = panels

    def fit(self, X, y=None):
        cols = sorted({p for v in self.panels.values() for p in v})
        self.cols_ = cols
        self.mu_, self.sd_ = X[cols].mean(), X[cols].std(ddof=0).replace(0, 1)
        return self

    def transform(self, X):
        z = (X[self.cols_] - self.mu_) / self.sd_
        return np.column_stack([z[v].mean(axis=1) for v in self.panels.values()])


def panel_lr(panels):
    return make_pipeline(PanelScore(panels), StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))


def gene_lr():
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.01, max_iter=5000))


def cv_oof(make, X, y, n_rep=20, seed=SEED):
    """分層 5 折 × n_rep；回傳每次重複的折外機率（n_rep × n）。"""
    out = np.zeros((n_rep, len(y)))
    for r in range(n_rep):
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed + r).split(X, y):
            out[r, te] = make().fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[te])[:, 1]
    return out


def boot_auc(y, p, n=2000, seed=SEED):
    rng, idx, a = np.random.default_rng(seed), np.arange(len(y)), []
    while len(a) < n:
        b = rng.choice(idx, len(idx))
        if 0 < y[b].sum() < len(b):
            a.append(roc_auc_score(y[b], p[b]))
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


def binary_metrics(y, p):
    yhat = (p >= 0.5).astype(int)
    return dict(auroc=float(roc_auc_score(y, p)), accuracy=float(accuracy_score(y, yhat)),
                balanced_accuracy=float(balanced_accuracy_score(y, yhat)),
                sensitivity=float(yhat[y == 1].mean()), specificity=float(1 - yhat[y == 0].mean()),
                brier=float(brier_score_loss(y, p)))


def summarize(y, oof):
    aucs = [roc_auc_score(y, o) for o in oof]
    return dict(n=int(len(y)), n_pos=int(y.sum()), auroc_mean=float(np.mean(aucs)),
                auroc_min_max=[float(min(aucs)), float(max(aucs))], auroc_ci_rep0=boot_auc(y, oof[0]),
                rep0=binary_metrics(y, oof[0]))


def permutation_p(make, X, y, observed, n=1000, seed=SEED):
    rng, hits = np.random.default_rng(seed), 0
    for i in range(n):
        yp = rng.permutation(y)
        hits += roc_auc_score(yp, cv_oof(make, X, yp, n_rep=1, seed=seed + 10_000 + i)[0]) >= observed
    return (hits + 1) / (n + 1)


def binary_task(m, X, keep_pos, keep_neg, panels, perm=False):
    sel = m.dx.isin(keep_pos | keep_neg)
    Xs, y = X[sel.values], m.dx[sel].isin(keep_pos).astype(int).values
    res = dict(groups=m.dx[sel].value_counts().to_dict())
    for name, make in [("PANEL_LR", lambda: panel_lr(panels)), ("GENE_LR", gene_lr)]:
        res[name] = summarize(y, cv_oof(make, Xs, y))
    if perm:
        res["PANEL_LR"]["permutation_p"] = permutation_p(lambda: panel_lr(panels), Xs, y,
                                                         res["PANEL_LR"]["auroc_mean"])
    return res, Xs, y


def per_panel(Xs, y, panels):
    sc = PanelScore(panels).fit(Xs).transform(Xs)
    return {k: dict(auroc=float(roc_auc_score(y, sc[:, i])),
                    mean_diff_z=float(sc[y == 1, i].mean() - sc[y == 0, i].mean()))
            for i, k in enumerate(panels)}


def random_sets(Xs, y, panels, n=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    used = {p for v in panels.values() for p in v}
    pool = np.array([c for c in Xs.columns if c not in used])
    aucs = []
    for i in range(n):
        rp = {k: list(rng.choice(pool, len(v), replace=False)) for k, v in panels.items()}
        aucs.append(roc_auc_score(y, cv_oof(lambda: panel_lr(rp), Xs, y, n_rep=1, seed=seed + 20_000 + i)[0]))
    return np.array(aucs)


def batch_center(m, X):
    """每平台減去「共有類別各類平均之平均」；參考不含單一平台獨有疾病（計畫 batch）。"""
    Xc = X.copy()
    for plat in m.platform.unique():
        rows = (m.platform == plat).values
        ref = X[rows & m.dx.isin(SHARED).values].groupby(m.dx[rows & m.dx.isin(SHARED).values].values).mean().mean()
        Xc.loc[rows] = X[rows] - ref
    return Xc


def multiclass(m, X, panels, classes=("SLE", "IgAN", "DN", "HT"), n_rep=20):
    sel = m.dx.isin(classes).values
    Xs, y = X[sel], m.dx[sel].values
    out = dict(groups=pd.Series(y).value_counts().to_dict())
    for name, make in [("PANEL_LR", lambda: panel_lr(panels)), ("GENE_LR", gene_lr)]:
        acc, bacc, top2 = [], [], []
        conf = None
        for r in range(n_rep):
            proba = np.zeros((len(y), len(classes)))
            for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED + r).split(Xs, y):
                mdl = make().fit(Xs.iloc[tr], y[tr])
                order = [list(mdl.classes_).index(c) for c in classes]
                proba[te] = mdl.predict_proba(Xs.iloc[te])[:, order]
            pred = np.array(classes)[proba.argmax(1)]
            acc.append(accuracy_score(y, pred))
            bacc.append(balanced_accuracy_score(y, pred))
            top2.append(np.mean([y[i] in np.array(classes)[np.argsort(-proba[i])[:2]] for i in range(len(y))]))
            if r == 0:
                conf = pd.crosstab(pd.Series(y, name="true"), pd.Series(pred, name="pred")).reindex(
                    index=classes, columns=classes, fill_value=0)
        out[name] = dict(accuracy_mean=float(np.mean(acc)), balanced_accuracy_mean=float(np.mean(bacc)),
                         top2_mean=float(np.mean(top2)), chance_majority=float(pd.Series(y).value_counts(normalize=True).max()),
                         confusion_rep0={k: v for k, v in conf.to_dict(orient="index").items()})
    return out


def main():
    if os.path.exists(OUT) and "--force" not in sys.argv:
        sys.exit(f"{OUT} 已存在（結果只產生一次）；確定要重跑請加 --force")
    plan_sha = hashlib.sha256(open(PLAN_PATH, "rb").read()).hexdigest()
    d = {(s, p): load(s, p) for s in ["GSE104948", "GSE104954"] for p in ["GPL22945", "GPL24120"]}
    panels = panel_probes(d[("GSE104948", "GPL24120")][1].columns)
    R = dict(plan_sha256=plan_sha, panels={k: len(v) for k, v in panels.items()},
             sample_counts={f"{s}-{p}": v[0].dx.value_counts().to_dict() for (s, p), v in d.items()})

    # T1 主要：GPL24120 腎絲球，免疫（SLE＋IgAN）對代謝（DN＋HT）；先抽 25% 保留測試集
    m, X = d[("GSE104948", "GPL24120")]
    sel = m.dx.isin({"SLE", "IgAN"} | METABOLIC).values
    m1, X1 = m[sel], X[sel]
    y1 = m1.dx.isin({"SLE", "IgAN"}).astype(int).values
    dev, hold = train_test_split(np.arange(len(y1)), test_size=0.25, stratify=m1.dx.values, random_state=SEED)
    t1, Xd, yd = binary_task(m1.iloc[dev], X1.iloc[dev], {"SLE", "IgAN"}, METABOLIC, panels, perm=True)
    t1["per_panel"] = per_panel(Xd, yd, panels)
    rs = random_sets(Xd, yd, panels)
    obs0 = roc_auc_score(yd, cv_oof(lambda: panel_lr(panels), Xd, yd, n_rep=1)[0])
    t1["random_gene_sets"] = dict(n=len(rs), panel_auroc_rep0=float(obs0), median=float(np.median(rs)),
                                  p95=float(np.percentile(rs, 95)), percentile_of_panel=float((rs < obs0).mean() * 100))
    hold_res = {}
    for name, make in [("PANEL_LR", lambda: panel_lr(panels)), ("GENE_LR", gene_lr)]:
        p = make().fit(Xd, yd).predict_proba(X1.iloc[hold])[:, 1]
        hold_res[name] = dict(**binary_metrics(y1[hold], p), auroc_ci=boot_auc(y1[hold], p))
    t1["holdout"] = dict(n=int(len(hold)), n_pos=int(y1[hold].sum()),
                         groups=m1.dx.iloc[hold].value_counts().to_dict(), **hold_res)
    full = panel_lr(panels).fit(Xd, yd)
    t1["panel_coef_full_dev"] = dict(zip(panels, map(float, full[-1].coef_[0])))
    R["T1_primary"] = t1

    # T2：GPL22945 腎絲球 ANCA 對 DN
    m, X = d[("GSE104948", "GPL22945")]
    t2, Xs, ys = binary_task(m, X, {"ANCA"}, {"DN"}, panels, perm=True)
    t2["per_panel"] = per_panel(Xs, ys, panels)
    R["T2_ANCA"] = t2

    # T3：GPL24120 腎小管間質（同 T1 定義，全樣本交叉驗證）
    m, X = d[("GSE104954", "GPL24120")]
    t3, Xs, ys = binary_task(m, X, {"SLE", "IgAN"}, METABOLIC, panels)
    t3["per_panel"] = per_panel(Xs, ys, panels)
    R["T3_tubulointerstitium"] = t3

    # T4：兩平台腎絲球合併（平台校正＋陰性對照）
    ma, Xa = d[("GSE104948", "GPL22945")]
    mb, Xb = d[("GSE104948", "GPL24120")]
    mg, Xg = pd.concat([ma, mb]), pd.concat([Xa, Xb])
    Xc = batch_center(mg, Xg)
    sh = mg.dx.isin(SHARED).values
    yp = (mg.platform[sh] == "GPL22945").astype(int).values
    neg = summarize(yp, cv_oof(gene_lr, Xc[sh], yp))
    ok = neg["auroc_ci_rep0"][1] < 0.70
    t4 = dict(platform_negative_control=dict(**neg, passed=bool(ok)))
    if ok:
        r4, _, _ = binary_task(mg, Xc, IMMUNE, METABOLIC, panels)
        t4.update(r4)
        t4["multiclass_5"] = multiclass(mg, Xc, panels, classes=("SLE", "IgAN", "ANCA", "DN", "HT"))
    R["T4_pooled"] = t4

    # T5：回推可能病因（GPL24120 腎絲球四類）
    m, X = d[("GSE104948", "GPL24120")]
    R["T5_multiclass"] = multiclass(m, X, panels)

    # T6：探索——T1 模型套用於非主要類別
    pr = full.predict_proba(X)[:, 1]
    R["T6_exploratory"] = {k: dict(n=int(v.size), median=float(np.median(v)), q1_q3=[float(np.percentile(v, 25)), float(np.percentile(v, 75))])
                           for k, v in pd.Series(pr, index=m.dx.values).groupby(level=0) if k in {"MN", "FSGS", "MCD", "TMD", "TN", "LD"}
                           for v in [v.values]}

    # 計畫判定規則
    p1 = R["T1_primary"]["PANEL_LR"]
    R["decision"] = dict(
        回推成立=bool(p1["auroc_ci_rep0"][0] > 0.5 and p1["permutation_p"] < 0.05 and t1["holdout"]["PANEL_LR"]["auroc"] > 0.5),
        免疫路徑專屬=bool(obs0 > t1["random_gene_sets"]["p95"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(R["decision"], ensure_ascii=False))


if __name__ == "__main__":
    main()
