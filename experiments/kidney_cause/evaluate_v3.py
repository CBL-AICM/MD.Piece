# -*- coding: utf-8 -*-
"""v3 重分析——完全依 params/v3_analysis_plan.json（先提交、後執行）。
    python evaluate_v3.py

每一外層折內完成：插補、標準化、5 折交叉配適集成、保序校準、盛行率（門檻）；外層受試者只用於評估。
輸出 results/v3_eval.json、results/v3_oof.csv.gz（逐人外層預測，可重算所有指標）。
"""
import hashlib
import json
import os
import sys
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np                                                          # noqa: E402
import pandas as pd                                                         # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier                 # noqa: E402
from sklearn.impute import SimpleImputer                                    # noqa: E402
from sklearn.isotonic import IsotonicRegression                             # noqa: E402
from sklearn.linear_model import LogisticRegression                         # noqa: E402
from sklearn.metrics import auc, average_precision_score, precision_recall_curve, roc_auc_score  # noqa: E402
from sklearn.model_selection import StratifiedKFold                         # noqa: E402
from sklearn.pipeline import make_pipeline                                  # noqa: E402
from sklearn.preprocessing import StandardScaler                            # noqa: E402

from binary_tasks import LABEL_ADJACENT                                     # noqa: E402
from nhanes_cohort import build_v3                                          # noqa: E402

SEED, REPEATS, FOLDS, NBOOT, EPS = 20260926, 5, 5, 1000, 1e-3
PLAN = os.path.join(ROOT, "params", "v3_analysis_plan.json")
OUT = os.path.join(ROOT, "results", "v3_eval.json")
OOF = os.path.join(ROOT, "results", "v3_oof.csv.gz")
AXES = {"肝炎": dict(label="hep3", adjacent=LABEL_ADJACENT["infection"]),
        "糖尿病": dict(label="dm3", adjacent=LABEL_ADJACENT["metabolic"])}
# 常規套組（計畫書定義，依可得性而非表現）：血球＋標準生化＋血脂＋尿液＋衍生＋人口學
BASIC = ["LBXWBCSI", "LBXLYPCT", "LBXMOPCT", "LBXNEPCT", "LBXEOPCT", "LBXBAPCT", "LBXRBCSI", "LBXHGB", "LBXHCT",
         "LBXMCVSI", "LBXMC", "LBXMCHSI", "LBXRDW", "LBXPLTSI", "LBXMPSI",
         "LBXSCR", "LBXSBU", "LBXSUA", "LBXSAL", "LBXSGL", "LBXSCH", "LBXSTR", "LBXSGTSI", "LBXSASSI", "LBXSATSI",
         "LBXSLDSI", "LBXSAPSI", "LBXSTB", "LBXSTP", "LBXSGB", "LBXSPH", "LBXSCA", "LBXSNASI", "LBXSKSI", "LBXSCLSI",
         "LBXSC3SI", "LBXSIR", "LBXSOSSI", "LBXTC", "LBDHDL", "LBDLDL", "LBXTR", "URXUMA", "URXUCR",
         "ACR", "eGFR", "NLR", "age", "sex"]
BAND_NAMES = {2: "傾向", 1: "不確定", 0: "不傾向"}


def lr(seed):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(class_weight="balanced", max_iter=4000, random_state=seed))


def hgb(seed):
    return HistGradientBoostingClassifier(random_state=seed, class_weight="balanced", max_depth=3,
                                          learning_rate=0.08, max_iter=300, l2_regularization=1.0)


def fit_tool(X, y, seed=SEED, make=lr):
    """部署模型：5 折交叉配適集成（預設 LR；v3.2 亦用於 HGB）→ 內層折外原始分數配適保序校準。"""
    oof, models = np.zeros(len(y)), []
    for tr, va in StratifiedKFold(FOLDS, shuffle=True, random_state=seed).split(X, y):
        m = make(seed).fit(X[tr], y[tr])
        oof[va] = m.predict_proba(X[va])[:, 1]
        models.append(m)
    return dict(models=models, iso=IsotonicRegression(out_of_bounds="clip").fit(oof, y), prev=float(y.mean()))


def tool_predict(T, X):
    raw = np.mean([m.predict_proba(X)[:, 1] for m in T["models"]], axis=0)
    return raw, T["iso"].predict(raw)


def thresholds(prev, rule):
    if rule == "A":
        return 2 * prev, 0.5 * prev
    o = prev / (1 - prev)
    return 2 * o / (1 + 2 * o), 0.5 * o / (1 + 0.5 * o)


def bands(p, prev, rule):
    hi, lo = thresholds(prev, rule)
    return np.where(p >= hi, 2, np.where(p <= lo, 0, 1))


def calib(y, p):
    """校準截距（logit p 為 offset）與斜率；Newton 法，p 以 EPS 截斷。"""
    o = np.log(np.clip(p, EPS, 1 - EPS) / (1 - np.clip(p, EPS, 1 - EPS)))
    a = 0.0
    for _ in range(100):
        mu = 1 / (1 + np.exp(-(a + o)))
        step = np.sum(y - mu) / -np.sum(mu * (1 - mu))
        a -= step
        if abs(step) < 1e-12:
            break
    Xd, b = np.column_stack([np.ones_like(o), o]), np.zeros(2)
    for _ in range(100):
        mu = 1 / (1 + np.exp(-(Xd @ b)))
        step = np.linalg.solve(-(Xd.T * (mu * (1 - mu))) @ Xd, Xd.T @ (y - mu))
        b -= step
        if np.max(np.abs(step)) < 1e-12:
            break
    brier = float(np.mean((p - y) ** 2))
    prev = float(y.mean())
    return dict(intercept=float(a), slope=float(b[1]), brier=brier, brier_skill=1 - brier / (prev * (1 - prev)),
                mean_pred=float(p.mean()), observed=prev)


def curve(y, p, bins=10):
    """分位數分箱之校準曲線（ties 時合併箱）。"""
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    return [dict(mean_pred=float(p[idx == k].mean()), observed=float(y[idx == k].mean()), n=int((idx == k).sum()))
            for k in range(len(edges) - 1) if (idx == k).any()]


def band_stats(y, b):
    six = {f"{'陽性' if t else '陰性'}_{BAND_NAMES[k]}": int(((y == t) & (b == k)).sum()) for t in (1, 0) for k in (2, 1, 0)}
    n, pos = len(y), int(y.sum())
    ans = b != 1
    per = {BAND_NAMES[k]: dict(n=int((b == k).sum()), observed_rate=float(y[b == k].mean()) if (b == k).any() else None)
           for k in (2, 1, 0)}
    return dict(six_cell=six, band=per, coverage=float(ans.mean()),
                answered_sensitivity=float(((b == 2) & (y == 1)).sum() / max((ans & (y == 1)).sum(), 1)),
                answered_specificity=float(((b == 0) & (y == 0)).sum() / max((ans & (y == 0)).sum(), 1)),
                positives_in_low=int(((b == 0) & (y == 1)).sum()),
                per_1000_if_skip_low=dict(tested=1000 * float((b != 0).mean()), missed=1000 * float(((b == 0) & (y == 1)).mean()),
                                          missed_share_of_pos=float(((b == 0) & (y == 1)).sum() / max(pos, 1))))


def boot(y, fns, n=NBOOT, seed=SEED):
    """受試者層 bootstrap；fns: dict name → f(idx)。回傳 95% 百分位 CI。"""
    rng = np.random.default_rng(seed)
    vals = {k: [] for k in fns}
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            for k, f in fns.items():
                vals[k].append(f(i))
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in vals.items()}


def prauc_trapz(y, p):
    pr, rc, _ = precision_recall_curve(y, p)
    return float(auc(rc, pr))


def axis_data(kd, feats, spec, label=None):
    lab = label or spec["label"]
    d = kd[kd[lab].notna()].reset_index(drop=True)
    ff = [f for f in feats if f not in spec["adjacent"]]
    basic = [f for f in BASIC if f in ff]
    return d, ff, basic, d[lab].to_numpy(int)


def nested(d, ff, basic, y, repeats=REPEATS, compare=True):
    """外層分層 5 折 × repeats。回傳逐人預測表與各比較模型之預測。"""
    X = d[ff].to_numpy(float)
    ib = [ff.index(f) for f in basic]
    ia = [ff.index(f) for f in ("age", "sex")]
    rows, comp = [], {k: np.full((repeats, len(y)), np.nan) for k in ("M1_demographics", "M2_basic_panel", "M3_full", "M4_full_HGB")}
    for r in range(repeats):
        for f, (tr, te) in enumerate(StratifiedKFold(FOLDS, shuffle=True, random_state=SEED + r).split(X, y)):
            T = fit_tool(X[tr], y[tr])
            raw, cal = tool_predict(T, X[te])
            rows.append(pd.DataFrame(dict(idx=te, repeat=r, fold=f, y=y[te], raw=raw, cal=cal,
                                          band_A=bands(cal, T["prev"], "A"), band_B=bands(cal, T["prev"], "B"),
                                          prev_train=T["prev"])))
            if compare:
                comp["M1_demographics"][r, te] = lr(SEED).fit(X[tr][:, ia], y[tr]).predict_proba(X[te][:, ia])[:, 1]
                comp["M2_basic_panel"][r, te] = lr(SEED).fit(X[tr][:, ib], y[tr]).predict_proba(X[te][:, ib])[:, 1]
                comp["M3_full"][r, te] = lr(SEED).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
                comp["M4_full_HGB"][r, te] = hgb(SEED).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    P = pd.concat(rows, ignore_index=True)
    P["insufficient"] = (d[basic].notna().mean(axis=1).to_numpy() < 0.5)[P["idx"]]
    return P, comp, X


def summarize(P, y):
    """逐重複計算指標 → 平均與範圍；CI 取第 0 次重複 bootstrap。"""
    per = []
    for r, g in P.groupby("repeat"):
        g = g.sort_values("idx")
        yy, raw, cal = g["y"].to_numpy(), g["raw"].to_numpy(), g["cal"].to_numpy()
        per.append(dict(auroc_cal=roc_auc_score(yy, cal), auroc_raw=roc_auc_score(yy, raw),
                        ap_cal=average_precision_score(yy, cal), ap_raw=average_precision_score(yy, raw),
                        prauc_trapz_cal=prauc_trapz(yy, cal), **{f"cal_{k}": v for k, v in calib(yy, cal).items()},
                        coverage_A=float((g["band_A"] != 1).mean()), coverage_B=float((g["band_B"] != 1).mean())))
    per = pd.DataFrame(per)
    g0 = P[P["repeat"] == 0].sort_values("idx")
    y0, cal0, raw0 = g0["y"].to_numpy(), g0["cal"].to_numpy(), g0["raw"].to_numpy()
    ci = boot(y0, dict(auroc_cal=lambda i: roc_auc_score(y0[i], cal0[i]), ap_cal=lambda i: average_precision_score(y0[i], cal0[i]),
                       auroc_raw=lambda i: roc_auc_score(y0[i], raw0[i]), ap_raw=lambda i: average_precision_score(y0[i], raw0[i]),
                       brier=lambda i: float(np.mean((cal0[i] - y0[i]) ** 2))))
    return dict(
        n=int(len(y)), n_pos=int(y.sum()), prevalence=float(y.mean()),
        repeats=dict(mean=per.mean().to_dict(), min=per.min().to_dict(), max=per.max().to_dict()),
        ci95_repeat0=ci, calibration_repeat0=calib(y0, cal0), calibration_curve_repeat0=curve(y0, cal0),
        bands_repeat0=dict(A=band_stats(y0, g0["band_A"].to_numpy()), B=band_stats(y0, g0["band_B"].to_numpy())),
        insufficient_data_n=int(g0["insufficient"].sum()),
        bands_B_excluding_insufficient=band_stats(y0[~g0["insufficient"].to_numpy()], g0["band_B"].to_numpy()[~g0["insufficient"].to_numpy()]),
        thresholds_full_sample=dict(A=thresholds(float(y.mean()), "A"), B=thresholds(float(y.mean()), "B")))


def compare_models(comp, P, y):
    g0 = P[P["repeat"] == 0].sort_values("idx")
    y0 = g0["y"].to_numpy()
    res = dict(M0_intercept=dict(auroc=0.5, ap=float(y.mean())))
    ref = comp["M3_full"][0]
    for k, v in comp.items():
        a = [roc_auc_score(y, v[r]) for r in range(v.shape[0])]
        ap = [average_precision_score(y, v[r]) for r in range(v.shape[0])]
        res[k] = dict(auroc_mean=float(np.mean(a)), auroc_range=[float(min(a)), float(max(a))],
                      ap_mean=float(np.mean(ap)), ap_range=[float(min(ap)), float(max(ap))])
        if k != "M3_full":
            p0 = v[0]
            res[k]["delta_vs_M3_repeat0"] = dict(
                d_auroc=float(roc_auc_score(y, p0) - roc_auc_score(y, ref)),
                d_ap=float(average_precision_score(y, p0) - average_precision_score(y, ref)),
                ci95=boot(y, dict(d_auroc=lambda i: roc_auc_score(y[i], p0[i]) - roc_auc_score(y[i], ref[i]),
                                  d_ap=lambda i: average_precision_score(y[i], p0[i]) - average_precision_score(y[i], ref[i]))))
    return res


def ablation_adjacent(kd, feats, spec, y_d, d):
    """近端特徵消融：全部特徵（含標籤鄰近）LR vs 不含，同一切分之配對差（第 0 次重複）。"""
    ff_all = [f for f in feats]
    ff_lf = [f for f in feats if f not in spec["adjacent"]]
    Xa, Xl = d[ff_all].to_numpy(float), d[ff_lf].to_numpy(float)
    pa, pl = np.zeros(len(y_d)), np.zeros(len(y_d))
    for tr, te in StratifiedKFold(FOLDS, shuffle=True, random_state=SEED).split(Xa, y_d):
        pa[te] = lr(SEED).fit(Xa[tr], y_d[tr]).predict_proba(Xa[te])[:, 1]
        pl[te] = lr(SEED).fit(Xl[tr], y_d[tr]).predict_proba(Xl[te])[:, 1]
    return dict(removed=spec["adjacent"], auroc_with=float(roc_auc_score(y_d, pa)), auroc_without=float(roc_auc_score(y_d, pl)),
                ap_with=float(average_precision_score(y_d, pa)), ap_without=float(average_precision_score(y_d, pl)),
                delta_ci95=boot(y_d, dict(d_auroc=lambda i: roc_auc_score(y_d[i], pa[i]) - roc_auc_score(y_d[i], pl[i]),
                                          d_ap=lambda i: average_precision_score(y_d[i], pa[i]) - average_precision_score(y_d[i], pl[i]))))


def temporal(d, ff, y):
    X = d[ff].to_numpy(float)
    cyc = d["cycle"].to_numpy()
    order = sorted(set(cyc))
    early = np.isin(cyc, order[:5])

    def ev(tr, te, nb=500):
        T = fit_tool(X[tr], y[tr])
        raw, cal = tool_predict(T, X[te])
        yy = y[te]
        out = dict(train_cycles=sorted(set(cyc[tr])), n=int(te.sum()), n_pos=int(yy.sum()),
                   prevalence_test=float(yy.mean()), prevalence_train=T["prev"], mean_pred=float(cal.mean()))
        if 0 < yy.sum() < len(yy):
            out.update(auroc=float(roc_auc_score(yy, cal)), ap=float(average_precision_score(yy, cal)),
                       ci95=boot(yy, dict(auroc=lambda i: roc_auc_score(yy[i], cal[i])), n=nb),
                       calibration=calib(yy, cal), bands_B=band_stats(yy, bands(cal, T["prev"], "B")))
        return out
    split = ev(early, ~early, nb=NBOOT)
    split["per_test_cycle"] = {}
    T = fit_tool(X[early], y[early])
    raw, cal = tool_predict(T, X[~early])
    for c in order[5:]:
        m = cyc[~early] == c
        yy, pp = y[~early][m], cal[m]
        split["per_test_cycle"][c] = dict(n=int(m.sum()), n_pos=int(yy.sum()),
                                          auroc=float(roc_auc_score(yy, pp)) if 0 < yy.sum() < len(yy) else None)
    expanding = {c: ev(np.isin(cyc, order[:k]), cyc == c) for k, c in enumerate(order) if k >= 3}
    return dict(early_to_late=split, expanding_window=expanding)


def weighted(d, P, y):
    g0 = P[P["repeat"] == 0].sort_values("idx")
    w = d["w_mec20"].to_numpy(float)[g0["idx"].to_numpy()]
    yy, cal = g0["y"].to_numpy(), g0["cal"].to_numpy()
    ok = np.isfinite(w) & (w > 0)
    return dict(n_with_weight=int(ok.sum()),
                unweighted=dict(prevalence=float(yy.mean()), mean_pred=float(cal.mean()), auroc=float(roc_auc_score(yy, cal)),
                                ap=float(average_precision_score(yy, cal)), brier=float(np.mean((cal - yy) ** 2))),
                weighted=dict(prevalence=float(np.average(yy[ok], weights=w[ok])), mean_pred=float(np.average(cal[ok], weights=w[ok])),
                              auroc=float(roc_auc_score(yy[ok], cal[ok], sample_weight=w[ok])),
                              ap=float(average_precision_score(yy[ok], cal[ok], sample_weight=w[ok])),
                              brier=float(np.average((cal[ok] - yy[ok]) ** 2, weights=w[ok]))),
                note="點估計；未以 PSU／分層估計設計變異")


def label_sensitivity(kd, feats, spec, labels):
    out = {}
    for name, lab, drop in labels:
        k = kd if drop is None else kd[~drop(kd)]
        d, ff, basic, y = axis_data(k, feats, spec, label=lab)
        P, _, _ = nested(d, ff, basic, y, repeats=1, compare=False)
        g = P.sort_values("idx")
        out[name] = dict(n=int(len(y)), n_pos=int(y.sum()), prevalence=float(y.mean()),
                         auroc=float(roc_auc_score(g["y"], g["cal"])), ap=float(average_precision_score(g["y"], g["cal"])),
                         calibration=calib(g["y"].to_numpy(), g["cal"].to_numpy()))
    return out


def dca(P, grid):
    g0 = P[P["repeat"] == 0]
    y, p = g0["y"].to_numpy(), g0["cal"].to_numpy()
    n, prev = len(y), float(y.mean())
    rows = []
    for pt in grid:
        tp, fp = ((p >= pt) & (y == 1)).sum(), ((p >= pt) & (y == 0)).sum()
        w = pt / (1 - pt)
        rows.append(dict(pt=float(pt), nb_model=float(tp / n - fp / n * w), nb_test_all=float(prev - (1 - prev) * w),
                         test_fraction=float((p >= pt).mean())))
    return rows


def main():
    t0 = time.time()
    plan_sha = hashlib.sha256(open(PLAN, "rb").read()).hexdigest()
    P0 = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = build_v3(P0, verbose=True)
    kd, feats = V["cohort"], V["features"]
    out = dict(created=pd.Timestamp.now().isoformat(timespec="seconds"), plan=os.path.relpath(PLAN, ROOT),
               plan_sha256=plan_sha, seed=SEED, n_kidney=int(len(kd)), n_features=len(feats), axes={})
    oof_all = []
    sens = {"肝炎": [("僅B肝_HBsAg", "hbv3", None), ("僅C肝_RNA", "hcv3", None)],
            "糖尿病": [("僅問卷_DIQ010", "dmq3", None), ("僅HbA1c", "dma3", None),
                    ("排除邊緣_DIQ010=3", "dm3", lambda k: k["DIQ010"] == 3)]}
    grids = {"肝炎": np.round(np.arange(0.005, 0.1001, 0.005), 4), "糖尿病": np.round(np.arange(0.10, 0.6001, 0.05), 3)}
    for name, spec in AXES.items():
        d, ff, basic, y = axis_data(kd, feats, spec)
        print(f"\n[{name}] n={len(y):,} 陽性 {y.sum():,}（{y.mean():.4f}）特徵 {len(ff)}（常規套組 {len(basic)}）", flush=True)
        P, comp, X = nested(d, ff, basic, y)
        s = summarize(P, y)
        print(f"  部署模型 AUROC {s['repeats']['mean']['auroc_cal']:.3f}（raw {s['repeats']['mean']['auroc_raw']:.3f}）"
              f"｜AP {s['repeats']['mean']['ap_cal']:.3f}（盛行率 {y.mean():.3f}）｜校準截距 {s['calibration_repeat0']['intercept']:.2f}"
              f" 斜率 {s['calibration_repeat0']['slope']:.2f}｜涵蓋率 A {s['bands_repeat0']['A']['coverage']:.1%}"
              f" B {s['bands_repeat0']['B']['coverage']:.1%}｜{time.time()-t0:.0f}s", flush=True)
        a = dict(label=spec["label"], features=ff, basic_panel=basic, removed_adjacent=spec["adjacent"], tool=s)
        a["comparisons"] = compare_models(comp, P, y)
        print("  比較：" + "｜".join(f"{k} {v.get('auroc_mean', v.get('auroc')):.3f}" for k, v in a["comparisons"].items()), flush=True)
        a["ablation_adjacent"] = ablation_adjacent(kd, feats, spec, y, d)
        a["temporal"] = temporal(d, ff, y)
        tl = a["temporal"]["early_to_late"]
        print(f"  時間：1999–2008 → 2009–2018 AUROC {tl.get('auroc', float('nan')):.3f}（n={tl['n']}、陽性 {tl['n_pos']}）", flush=True)
        a["survey_weighted"] = weighted(d, P, y)
        a["label_sensitivity"] = label_sensitivity(kd, feats, spec, sens[name])
        a["decision_curve"] = dca(P, grids[name])
        out["axes"][name] = a
        P = P.assign(axis=name, SEQN=d["SEQN"].to_numpy()[P["idx"]], cycle=d["cycle"].to_numpy()[P["idx"]],
                     w_mec20=d["w_mec20"].to_numpy()[P["idx"]])
        oof_all.append(P)
    pd.concat(oof_all, ignore_index=True).drop(columns=["idx"]).to_csv(OOF, index=False, compression="gzip")
    out["runtime_s"] = round(time.time() - t0, 1)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    with open(os.path.join(ROOT, "results", "runs_log.jsonl"), "a", encoding="utf-8") as f:
        for name, a in out["axes"].items():
            f.write(json.dumps(dict(kind="v3_eval", created=out["created"], axis=name, plan_sha256=plan_sha,
                                    n=a["tool"]["n"], n_pos=a["tool"]["n_pos"],
                                    auroc=a["tool"]["repeats"]["mean"]["auroc_cal"], ap=a["tool"]["repeats"]["mean"]["ap_cal"]),
                               ensure_ascii=False) + "\n")
    print(f"\n[存檔] {OUT}｜{OOF}｜{out['runtime_s']}s")


if __name__ == "__main__":
    main()
