# -*- coding: utf-8 -*-
"""immune_geo 修正二：代謝方向本身＋SLE 對 MN（params/immune_geo_amendment_2.json，先提交、後執行）。
模型、交叉驗證、置換、門檻、判定規則全部沿用修正一（immune_geo_batchsafe）。
輸出 results/immune_geo_amendment2.json。用法：python immune_geo_amendment2.py"""
import hashlib
from concurrent.futures import ProcessPoolExecutor
import json
import os
import sys

import time

import numpy as np
from sklearn.metrics import roc_auc_score

import immune_geo as ig
import immune_geo_batchsafe as bs

AMEND = os.path.join(ig.ROOT, "params", "immune_geo_amendment_2.json")
OUT = os.path.join(ig.ROOT, "results", "immune_geo_amendment2.json")
NEITHER = {"FSGS", "FSGS_MCD", "MCD"}
T0 = time.time()


def log(msg):
    print(f"[{(time.time() - T0) / 60:5.1f} 分] {msg}", flush=True)


# 平行版：亂數序列與 ig.permutation_p／ig.random_sets 逐次相同（先依序抽完再平行計算），結果逐位元相同。
# joblib 1.3.2 在 Python 3.14 無法啟動子程序，改用標準庫 ProcessPoolExecutor；模型以 (種類, 路徑) 描述以便序列化。
_W = {}


def _init(X):
    _W["X"] = X


def _make(spec):
    return (lambda: ig.panel_lr(spec[1])) if spec[0] == "panel" else ig.gene_lr


def _auc(spec, y, seed):
    return roc_auc_score(y, ig.cv_oof(_make(spec), _W["X"], y, n_rep=1, seed=seed)[0])


def _pool_map(X, jobs):
    with ProcessPoolExecutor(12, initializer=_init, initargs=(X,)) as ex:
        return list(ex.map(_auc, *zip(*jobs), chunksize=8))


def _spec(make):
    m = make()
    return ("panel", m.steps[0][1].panels) if hasattr(m.steps[0][1], "panels") else ("gene", None)


def par_permutation_p(make, X, y, observed, n=1000, seed=ig.SEED):
    rng = np.random.default_rng(seed)
    perms = [rng.permutation(y) for _ in range(n)]
    sp = _spec(make)
    aucs = _pool_map(X, [(sp, yp, seed + 10_000 + i) for i, yp in enumerate(perms)])
    return (sum(a >= observed for a in aucs) + 1) / (n + 1)


def par_random_sets(Xs, y, panels, n=1000, seed=ig.SEED):
    rng = np.random.default_rng(seed)
    used = {p for v in panels.values() for p in v}
    pool = np.array([c for c in Xs.columns if c not in used])
    sets = [{k: list(rng.choice(pool, len(v), replace=False)) for k, v in panels.items()} for _ in range(n)]
    return np.array(_pool_map(Xs, [(("panel", rp), y, seed + 20_000 + i) for i, rp in enumerate(sets)]))


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
    ig.permutation_p, ig.random_sets = par_permutation_p, par_random_sets
    log("資料載入完成")
    R = dict(amendment_sha256=sha(AMEND), amendment_1_sha256=sha(bs.AMEND), plan_sha256=sha(ig.PLAN_PATH))
    R["C1_metabolic_H7"] = bs.task(g7, Xg7, {"DN"}, NEITHER, panels, perm=True)
    log("C1 完成")
    R["C2_metabolic_H1"] = bs.task(g1, Xg1, {"DN"}, {"MCD", "TMD"}, panels, perm=True)
    log("C2 完成")
    R["C3_SLE_vs_MN"] = bs.task(g5, Xg5, {"SLE"}, {"MN"}, panels, perm=True, rand=True)
    log("C3 完成")
    R["C4_replication"] = dict(C1=bs.task(t7, Xt7, {"DN"}, NEITHER, panels),
                               C2=bs.task(t1, Xt1, {"DN"}, {"MCD", "TMD"}, panels),
                               C3=bs.task(t5, Xt5, {"SLE"}, {"MN"}, panels))
    log("C4 腎小管間質重現完成")
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
