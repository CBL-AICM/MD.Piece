# -*- coding: utf-8 -*-
"""PSU 與分層之設計變異估計（2026-09-27；計畫 params/design_variance_plan.json 已先提交 9edd968）。
    python design_variance.py      → results/design_variance.json

刪一 PSU 摺刀法（JKn）估計加權盛行率、平均預測、校準差、AUROC、AP 的標準誤；盛行率另以泰勒線性化核對。
複製權重依全樣本設計建立（含分析範圍內沒有受試者的 PSU），分析範圍以指示變數處理。
預測視為固定，不含模型重新配適的變異。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                                   # noqa: E402
import pandas as pd                                                  # noqa: E402
from scipy.stats import beta, t as tdist                             # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

OUT = os.path.join(ROOT, "results", "design_variance.json")
NAMES = ["prevalence", "mean_pred", "calib_diff", "auroc", "ap"]
J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))


def stats(y, p, w):
    """加權點估計向量；權重為 0 者不計。"""
    k = w > 0
    y, p, w = y[k], p[k], w[k]
    prev, mp = np.average(y, weights=w), np.average(p, weights=w)
    return np.array([prev, mp, mp - prev, roc_auc_score(y, p, sample_weight=w),
                     average_precision_score(y, p, sample_weight=w)])


def design_of(df):
    """全樣本設計：{層: [PSU…]}。"""
    return {int(h): sorted(int(j) for j in g.unique()) for h, g in df.groupby("SDMVSTRA")["SDMVPSU"]}


def jkn(y, p, w, h, j, design):
    """刪一 PSU 摺刀法。h, j 為分析範圍內每人之層與 PSU；design 為全樣本之層與 PSU。"""
    theta = stats(y, p, w)
    var, n_rep = np.zeros_like(theta), 0
    for hh, psus in design.items():
        nh, in_h = len(psus), h == hh
        for jj in psus:
            wr = w.copy()
            drop = in_h & (j == jj)
            wr[drop] = 0.0
            wr[in_h & ~drop] *= nh / (nh - 1)
            var += (nh - 1) / nh * (stats(y, p, wr) - theta) ** 2
            n_rep += 1
    return theta, np.sqrt(var), n_rep


def taylor_prev_se(y, w, h, j, design):
    """加權比例之泰勒線性化標準誤（PSU 以放回抽樣近似；無受試者之 PSU 總和為 0）。"""
    p = np.average(y, weights=w)
    z = w * (y - p) / w.sum()
    var = 0.0
    for hh, psus in design.items():
        tot = np.array([z[(h == hh) & (j == jj)].sum() for jj in psus])
        var += len(psus) / (len(psus) - 1) * np.sum((tot - tot.mean()) ** 2)
    return float(np.sqrt(var))


def korn_graubard(p, se, n, df):
    """NCHS 比例呈現標準之 Korn–Graubard 區間；回傳 (下界, 上界, 有效樣本數)。"""
    n_eff = min(n, p * (1 - p) / se ** 2) if se > 0 else n
    n_df = n_eff * (tdist.ppf(0.975, n - 1) / tdist.ppf(0.975, df)) ** 2
    x = p * n_df
    lo = 0.0 if x <= 0 else float(beta.ppf(0.025, x, n_df - x + 1))
    hi = 1.0 if x >= n_df else float(beta.ppf(0.975, x + 1, n_df - x))
    return lo, hi, float(n_eff)


def analyse(y, p, w, h, j, design):
    theta, se, n_rep = jkn(y, p, w, h, j, design)
    n = len(y)
    df = len(set(zip(h.tolist(), j.tolist()))) - len(set(h.tolist()))
    tq = tdist.ppf(0.975, df)
    res = {k: dict(est=float(theta[i]), se=float(se[i]), ci95=[float(theta[i] - tq * se[i]), float(theta[i] + tq * se[i])])
           for i, k in enumerate(NAMES)}
    lo, hi, n_eff = korn_graubard(theta[0], se[0], n, df)
    se_t = taylor_prev_se(y, w, h, j, design)
    res["prevalence"].update(ci95=[lo, hi], ci_method="Korn–Graubard", n_eff=n_eff,
                             deff=float(se[0] ** 2 / (theta[0] * (1 - theta[0]) / n)),
                             se_taylor=se_t, se_ratio_jkn_to_taylor=float(se[0] / se_t))
    return dict(n=n, n_pos=int(y.sum()), df=int(df), n_replicates=n_rep, weighted=res,
                unweighted=dict(zip(NAMES, map(float, stats(y, p, np.ones(n))))))


def internal():
    from nhanes_cohort import build_v3
    A = build_v3(J("params", "design.json"), verbose=False)["adults"]
    design = design_of(A)
    dz = A[["SEQN", "SDMVSTRA", "SDMVPSU"]].drop_duplicates("SEQN")
    oof = pd.read_csv(os.path.join(ROOT, "results", "v3_oof.csv.gz"))
    out = {}
    for ax in ("肝炎", "糖尿病"):
        d = oof[(oof["axis"] == ax) & (oof["repeat"] == 0)].merge(dz, on="SEQN", how="left", validate="one_to_one")
        assert d[["SDMVSTRA", "SDMVPSU"]].notna().all().all(), f"{ax}：有人缺設計變數"
        out[ax] = analyse(d["y"].to_numpy(float), d["cal"].to_numpy(float), d["w_mec20"].to_numpy(float),
                          d["SDMVSTRA"].to_numpy(int), d["SDMVPSU"].to_numpy(int), design)
    return out, design


def external():
    import external_validation_2021 as ev
    from direction import AXES, predict_matrix
    L = ev.load_2021(True)
    design = design_of(L)
    kd = L[L["kidney3"] == 1]
    Ms = {k: J(os.path.relpath(p, ROOT))["axes"] for k, p in ev.MODELS.items()}
    out = {}
    for ax, spec in AXES.items():
        d = kd[kd[spec["label"]].notna()]
        y = d[spec["label"]].astype(int).to_numpy(float)
        out[ax] = {}
        for mk, M in Ms.items():
            a = M[ax]
            X = np.column_stack([d[f].to_numpy(float) if f in d.columns else np.full(len(d), np.nan) for f in a["features"]])
            out[ax][mk] = analyse(y, predict_matrix(a, X)[1], d["WTMEC2YR"].to_numpy(float),
                                  d["SDMVSTRA"].to_numpy(int), d["SDMVPSU"].to_numpy(int), design)
    return out, design


def main():
    ins, d_in = internal()
    ext, d_ex = external()
    E, X = J("results", "v3_eval.json")["axes"], J("results", "external_2021_2023.json")["primary"]["axes"]
    checks = []
    for ax, r in ins.items():
        ref = E[ax]["survey_weighted"]["weighted"]
        checks += [(f"內部 {ax} {k}", r["weighted"][k]["est"], ref[k]) for k in ("prevalence", "mean_pred", "auroc", "ap")]
    for ax, r in ext.items():
        ref = X[ax]["weighted_full"]
        checks += [(f"外部 {ax} {k}", r["v3_full_LR（部署）"]["weighted"][k]["est"], ref[k]) for k in ("prevalence", "mean_pred", "auroc")]
    bad = [c for c in checks if abs(c[1] - c[2]) > 1e-9]
    assert not bad, f"點估計與既有結果不一致：{bad}"
    ratios = [r["weighted"]["prevalence"]["se_ratio_jkn_to_taylor"] for r in ins.values()] + \
             [m["weighted"]["prevalence"]["se_ratio_jkn_to_taylor"] for r in ext.values() for m in r.values()]
    assert all(0.9 <= x <= 1.1 for x in ratios), f"JKn 與泰勒標準誤差異超過 10%：{ratios}"
    res = dict(plan="params/design_variance_plan.json（提交 9edd968）",
               design=dict(internal=dict(strata=len(d_in), psu=sum(map(len, d_in.values()))),
                           external=dict(strata=len(d_ex), psu=sum(map(len, d_ex.values())))),
               checks=dict(point_estimates_match=len(checks), jkn_taylor_se_ratio=[round(x, 4) for x in ratios]),
               internal=ins, external=ext)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[核對] 點估計與既有結果一致 {len(checks)} 項；盛行率 JKn／泰勒標準誤比值 {[round(x, 3) for x in ratios]}")
    for ax, r in ins.items():
        w = r["weighted"]
        print(f"[內部 {ax}] n={r['n']:,} 陽性 {r['n_pos']}，df {r['df']}｜盛行率 {w['prevalence']['est']:.4f}"
              f"（{w['prevalence']['ci95'][0]:.4f}–{w['prevalence']['ci95'][1]:.4f}，DEFF {w['prevalence']['deff']:.2f}）"
              f"｜AUROC {w['auroc']['est']:.3f}（{w['auroc']['ci95'][0]:.3f}–{w['auroc']['ci95'][1]:.3f}）"
              f"｜AP {w['ap']['est']:.3f}（{w['ap']['ci95'][0]:.3f}–{w['ap']['ci95'][1]:.3f}）"
              f"｜校準差 {w['calib_diff']['est']:+.4f}（{w['calib_diff']['ci95'][0]:+.4f}–{w['calib_diff']['ci95'][1]:+.4f}）")
    for ax, r in ext.items():
        for mk, m in r.items():
            w = m["weighted"]
            print(f"[外部 {ax}｜{mk}] n={m['n']:,} 陽性 {m['n_pos']}，df {m['df']}｜盛行率 {w['prevalence']['est']:.4f}"
                  f"（{w['prevalence']['ci95'][0]:.4f}–{w['prevalence']['ci95'][1]:.4f}）｜AUROC {w['auroc']['est']:.3f}"
                  f"（{w['auroc']['ci95'][0]:.3f}–{w['auroc']['ci95'][1]:.3f}）｜校準差 {w['calib_diff']['est']:+.4f}"
                  f"（{w['calib_diff']['ci95'][0]:+.4f}–{w['calib_diff']['ci95'][1]:+.4f}）")
    print(f"[存檔] {OUT}")


if __name__ == "__main__":
    main()
