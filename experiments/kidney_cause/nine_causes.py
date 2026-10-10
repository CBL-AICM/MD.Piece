# -*- coding: utf-8 -*-
"""已知腎損傷，可能是哪一種病？——九種病因中 NHANES 量得到者之公開資料檢驗
（計畫 params/nine_causes_plan.json 已先提交；結果檔記錄計畫 SHA256）。
    python nine_causes.py      → results/nine_causes_nhanes.json

每病：腎損傷者與無腎損傷者之加權盛行率、粗盛行率比、調整盛行率比（年齡、性別、種族；邊際標準化）與調整勝算比；
次要：依腎臟型態（只有白蛋白尿／只有 eGFR<60／兩者）之盛行率與調整盛行率比。
變異：刪一 PSU 摺刀法，模型逐組重新配適（同 design_variance.py）。HIV 檔未下載時該病標記「未下載」。"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                    # noqa: E402
import pandas as pd                                   # noqa: E402
from scipy.stats import t as tdist                    # noqa: E402

from design_variance import design_of, korn_graubard  # noqa: E402
from nhanes_cohort import RAW, _read, build_v3        # noqa: E402

PLAN = os.path.join(ROOT, "params", "nine_causes_plan.json")
OUT = os.path.join(ROOT, "results", "nine_causes_nhanes.json")
SUF = ["", "_B", "_C", "_D", "_E", "_F", "_G", "_H", "_I", "_J"]          # 1999–2018
HIV_FILES = {"1999-2000": "LAB03.xpt", "2001-2002": "L03_B.xpt", "2003-2004": "L03_C.xpt",
             "2005-2006": "HIV_D.xpt", "2007-2008": "HIV_E.xpt", "2009-2010": "HIV_F.xpt",
             "2011-2012": "HIV_G.xpt", "2013-2014": "HIV_H.xpt", "2015-2016": "HIV_I.xpt", "2017-2018": "HIV_J.xpt"}
HIV_COMBO = {"2015-2016", "2017-2018"}                                   # 篩檢→分型→核酸
HIV_AGE_MAX = {c: (49 if c < "2009" else 59) for c in HIV_FILES}         # 各週期受檢年齡上限
AGE_BINS = [20, 30, 40, 50, 60, 70, 80, np.inf]
AGE_LAB = ["20–29", "30–39", "40–49", "50–59", "60–69", "70–79", "≥80"]
PHENO = ["無異常", "只有白蛋白尿", "只有eGFR<60", "兩者皆有"]
DISEASES = ["糖尿病", "肥胖", "高尿酸血症", "痛風", "B型肝炎", "C型肝炎", "HIV"]
COL = {"糖尿病": "dm3", "肥胖": "obese3", "高尿酸血症": "hua3", "痛風": "gout3",
       "B型肝炎": "hbv3", "C型肝炎": "hcv3", "HIV": "hiv3"}


def _stack(prefix, cols):
    frames = []
    for s in SUF:
        f = _read(f"{prefix}{s}.xpt")
        frames.append(f[["SEQN"] + [c for c in cols if c in f.columns]])
    return pd.concat(frames, ignore_index=True)


def hiv_label(df):
    """三值 HIV 標籤（計畫 diseases.HIV）。受檢年齡以外一律未知。"""
    col = lambda c: df[c] if c in df.columns else pd.Series(np.nan, index=df.index)
    lbdhi, c, h1, h2, nat = col("LBDHI"), col("LBXHIVC"), col("LBXHIV1"), col("LBXHIV2"), col("LBXHNAT")
    old = np.select([lbdhi == 1, lbdhi == 2], [1.0, 0.0], np.nan)
    new = np.select([c == 2, (c == 1) & ((h1 == 1) | (h2 == 1)), (c == 1) & (nat == 1), (c == 1) & (nat == 2)],
                    [0.0, 1.0, 1.0, 0.0], np.nan)
    lab = np.where(df["cycle"].isin(HIV_COMBO), new, old)
    tested_age = df["age"].le(df["cycle"].map(HIV_AGE_MAX))
    return np.where(tested_age, lab, np.nan)


def load():
    A = build_v3(json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8")),
                 verbose=False, fixes=True)["adults"]
    for prefix, cols in (("DEMO", ["RIDRETH1", "RIDEXPRG"]), ("BMX", ["BMXBMI"]), ("MCQ", ["MCQ160N"])):
        A = A.merge(_stack(prefix, cols), on="SEQN", how="left", validate="1:1")
    bmi, ua, female = A["BMXBMI"], A["LBXSUA"], A["sex"] == 2
    A["obese3"] = np.where(A["RIDEXPRG"] == 1, np.nan, np.select([bmi >= 30, bmi < 30], [1.0, 0.0], np.nan))
    A["hua3"] = np.select([ua > np.where(female, 5.7, 7.0), ua.notna()], [1.0, 0.0], np.nan)
    A["gout3"] = np.select([A["MCQ160N"] == 1, A["MCQ160N"] == 2], [1.0, 0.0], np.nan)
    have_hiv = all(os.path.exists(os.path.join(RAW, f)) for f in HIV_FILES.values())
    if have_hiv:
        hiv = pd.concat([_read(f) for f in HIV_FILES.values()], ignore_index=True)
        A = A.merge(hiv[["SEQN"] + [c for c in ("LBDHI", "LBXHIVC", "LBXHIV1", "LBXHIV2", "LBXHNAT") if c in hiv.columns]],
                    on="SEQN", how="left", validate="1:1")
        A["hiv3"] = hiv_label(A)
    else:
        A["hiv3"] = np.nan
    e, a = A["eGFR"], A["ACR"]
    A["pheno"] = np.select([(e >= 60) & (a < 30), (e >= 60) & (a >= 30), (e < 60) & (a < 30), (e < 60) & (a >= 30)],
                           [0, 1, 2, 3], -1)
    A["age_cat"] = pd.cut(A["age"], AGE_BINS, right=False, labels=False).astype(int)
    A["race"] = A["RIDRETH1"].astype(int)
    return A, have_hiv


def logit_fit(X, y, w, b=None, ridge=1e-6, tol=1e-9, max_iter=200):
    """加權邏輯斯迴歸（IRLS）；ridge 只為數值穩定（截距不罰），權重先標準化為平均 1。"""
    w = w / w.mean()
    b = np.zeros(X.shape[1]) if b is None else b.copy()
    pen = np.full(X.shape[1], ridge)
    pen[0] = 0.0
    for _ in range(max_iter):
        p = 1.0 / (1.0 + np.exp(-(X @ b)))
        g = X.T @ (w * (y - p)) - pen * b
        H = (X * (w * p * (1 - p))[:, None]).T @ X + np.diag(pen)
        step = np.linalg.solve(H, g)
        b = b + step
        if np.max(np.abs(step)) < tol:
            return b
    raise RuntimeError("IRLS 未收斂")


def merge_sparse(d, y):
    """計畫 sparse_rule：事件數 0 之年齡類別併入相鄰較低一類、種族類別併入第 5 類。回傳 (d, 紀錄)。"""
    d, log = d.copy(), []
    for k in sorted(d["age_cat"].unique(), reverse=True):
        if y[(d["age_cat"] == k).to_numpy()].sum() == 0 and k > d["age_cat"].min():
            lower = max(j for j in d["age_cat"].unique() if j < k)
            d.loc[d["age_cat"] == k, "age_cat"] = lower
            log.append(f"年齡 {AGE_LAB[k]} 併入 {AGE_LAB[lower]}")
    for r in sorted(d["race"].unique()):
        if r != 5 and y[(d["race"] == r).to_numpy()].sum() == 0:
            d.loc[d["race"] == r, "race"] = 5
            log.append(f"種族 {r} 併入 5")
    return d, log


def design_matrix(d, groups):
    """截距＋腎臟組別虛擬變數（groups 第一個為參照）＋年齡、種族（第一類為參照）＋女性。"""
    g = d["grp"].to_numpy()
    cols = [np.ones(len(d))] + [(g == k).astype(float) for k in groups[1:]]
    for c in ("age_cat", "race"):
        lev = sorted(d[c].unique())
        cols += [(d[c] == k).to_numpy(float) for k in lev[1:]]
    cols.append((d["sex"] == 2).to_numpy(float))
    return np.column_stack(cols)


def theta(X, y, g, w, groups, b0=None):
    """回傳 (統計量向量, 係數)。統計量：各組加權盛行率、各組對參照組之 log 粗盛行率比、log 調整盛行率比、log 調整勝算比。"""
    b = logit_fit(X, y, w, b0)
    prev = [np.average(y[g == k], weights=w[g == k]) for k in groups]
    std = []
    for j in range(len(groups)):                     # 邊際標準化：全體設為組別 j
        Xj = X.copy()
        Xj[:, 1:len(groups)] = 0.0
        if j:
            Xj[:, j] = 1.0
        std.append(np.average(1.0 / (1.0 + np.exp(-(Xj @ b))), weights=w))
    out = prev + [np.log(prev[j] / prev[0]) for j in range(1, len(groups))] \
        + [np.log(std[j] / std[0]) for j in range(1, len(groups))] + list(b[1:len(groups)])
    return np.array(out), b


def analyse(d, ycol, groups, labels, design):
    """d 為分析範圍（腎臟組別 grp、疾病標籤 ycol 皆可判定）。刪一 PSU 摺刀法。"""
    y = d[ycol].to_numpy(float)
    d, merged = merge_sparse(d, y)
    X, g, w = design_matrix(d, groups), d["grp"].to_numpy(), d["w_mec20"].to_numpy(float)
    h, j = d["SDMVSTRA"].to_numpy(int), d["SDMVPSU"].to_numpy(int)
    est, b = theta(X, y, g, w, groups)
    var, n_rep = np.zeros_like(est), 0
    for hh, psus in design.items():
        nh, in_h = len(psus), h == hh
        for jj in psus:
            wr = w.copy()
            drop = in_h & (j == jj)
            wr[drop] = 0.0
            wr[in_h & ~drop] *= nh / (nh - 1)
            keep = wr > 0
            r, _ = theta(X[keep], y[keep], g[keep], wr[keep], groups, b)
            var += (nh - 1) / nh * (r - est) ** 2
            n_rep += 1
    se = np.sqrt(var)
    df = len(set(zip(h.tolist(), j.tolist()))) - len(set(h.tolist()))
    tq = tdist.ppf(0.975, df)
    k = len(groups)
    res = dict(n=int(len(d)), n_events=int(y.sum()), df=int(df), n_replicates=n_rep, merged_categories=merged, groups={})
    for i, lab in enumerate(labels):
        m = g == groups[i]
        lo, hi, n_eff = korn_graubard(est[i], se[i], int(m.sum()), df)
        res["groups"][lab] = dict(n=int(m.sum()), n_events=int(y[m].sum()), prevalence=float(est[i]),
                                  se=float(se[i]), ci95=[lo, hi], ci_method="Korn–Graubard")
    ratio = lambda i: dict(est=float(np.exp(est[i])), ci95=[float(np.exp(est[i] - tq * se[i])), float(np.exp(est[i] + tq * se[i]))],
                           se_log=float(se[i]))
    res["contrasts"] = {labels[i]: dict(PR_crude=ratio(k + i - 1), aPR=ratio(2 * k + i - 2), aOR=ratio(3 * k + i - 3))
                        for i in range(1, k)}
    return res


def verdict(apr):
    lo, hi = apr["ci95"]
    return "腎損傷者較常見" if lo > 1 else "腎損傷者較少見" if hi < 1 else "無法區分"


def main():
    plan_sha = hashlib.sha256(open(PLAN, "rb").read()).hexdigest()
    A, have_hiv = load()
    design = design_of(A)
    K = A[A["kidney3"].notna()].copy()
    out = dict(plan="params/nine_causes_plan.json", plan_sha256=plan_sha,
               cohort=dict(adults=int(len(A)), kidney_known=int(len(K)),
                           kidney_damage=int((K["kidney3"] == 1).sum()), no_kidney_damage=int((K["kidney3"] == 0).sum()),
                           strata=len(design), psu=sum(len(v) for v in design.values())),
               hiv_files="已下載" if have_hiv else "未下載（待使用者同意）", primary={}, phenotype={}, sensitivity={})
    for dis in DISEASES:
        c = COL[dis]
        if dis == "HIV" and not have_hiv:
            out["primary"][dis] = out["phenotype"][dis] = dict(status="未下載")
            continue
        d = K[K[c].notna()].copy()
        d["grp"] = d["kidney3"].astype(int)
        r = analyse(d, c, [0, 1], ["無腎損傷", "腎損傷"], design)
        r["label_known"] = int(A[c].notna().sum())
        r["verdict"] = verdict(r["contrasts"]["腎損傷"]["aPR"])
        out["primary"][dis] = r
        p = d[d["pheno"] >= 0].copy()
        p["grp"] = p["pheno"]
        out["phenotype"][dis] = analyse(p, c, [0, 1, 2, 3], PHENO, design)
        print(f"[{dis}] n={r['n']:,}｜腎損傷 {r['groups']['腎損傷']['prevalence']:.3f} vs "
              f"{r['groups']['無腎損傷']['prevalence']:.3f}｜aPR {r['contrasts']['腎損傷']['aPR']['est']:.2f} "
              f"{r['contrasts']['腎損傷']['aPR']['ci95']}｜{r['verdict']}", flush=True)
    if have_hiv:
        d = K[K["hiv3"].notna() & (K["age"] <= 49)].copy()
        d["grp"] = d["kidney3"].astype(int)
        r = analyse(d, "hiv3", [0, 1], ["無腎損傷", "腎損傷"], design)
        r["verdict"] = verdict(r["contrasts"]["腎損傷"]["aPR"])
        out["sensitivity"]["HIV_20至49歲"] = r
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[完成] {OUT}")


if __name__ == "__main__":
    main()
