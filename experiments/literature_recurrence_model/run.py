"""文獻錨定的慢性病復發模型 × 3,200 位虛擬患者（不使用任何公開資料庫的個人層級資料）。

研究目的沿用前一份研究（claude/chronic-disease-recurrence-prediction 分支，假說二）：
「長期紀錄能不能預測復發和復發時間」。前一份用 NHEFS／Framingham 公開資料驗證；
本研究依要求改為：只用 PubMed 文獻摘要中的族群層級數字（literature.py），
搭配過去合成的 3,200 位虛擬患者（simulate_cohort.py）。

分析計畫在跑資料前寫死於此，跑完不回頭改門檻：

1. 文獻縱向統整
   - 各病一年復發機率：各研究換算後取中位數當目標（literature.disease_targets）。
   - H1（過去／近期疾病活動紀錄 → 未來復發）與 H2（未按時用藥或停藥 → 未來復發）：
     log 效果量以 DerSimonian–Laird 隨機效應統合；OR／HR／RR 視為近似同一尺度（限制）。
   - H3（時間型態）：各研究累積復發曲線以 Weibull 擬合，形狀參數 k < 1 表示越早期越容易復發。
2. 原始虛擬世代（模擬器原設定）量測同樣的量，與文獻對照。
3. 文獻校準：每病只調一個參數（復發判定門檻位移 δ），讓「第 2 年」一年復發機率等於文獻目標；
   沒有文獻錨的 3 病（OA、SSc、乾燥症）δ = 0。H1、H2、H3 與第 3 年復發率都不參與校準，留作獨立檢查。
4. 模型（校準後世代＝本研究的新數據；原始世代並列對照）
   - 預測時點 landmark = 第 730 天；排除當天正在復發者。
   - 結果：未來 90 天內是否有新一次復發（二元）；到下一次復發的天數（最多追 365 天）。
   - App 紀錄層：症狀日記 70% 的天數有填、填寫值加入 0.3 SD 的誤差；檢驗每 30 天一次；
     漏服與誘發因子只在有填日記的天數看得到；復發史完整可見。
   - 模型：只用年齡性別病別、只用文獻（不訓練）、文獻分數＋紀錄、logistic（紀錄長度 30/90/180/365/730 天）、
     梯度提升樹（730 天）、Cox（730 天，預測復發時間）。依患者 5 折分層交叉驗證；AUROC 以 1,000 次 bootstrap 給 95% CI；
     標籤隨機置換 50 次作為「沒有混入答案」的對照。
   - 預警：風險前 20% 視為警示，算敏感度、陽性預測值、提升倍數與提前天數。
5. 交叉對比：文獻 vs 原始虛擬 vs 校準後新數據 vs 模型預測（逐病一年復發率、三個機制、模型表現），
   並與前一份研究（NHEFS AUROC 0.71、數位雙生 0.77）及文獻中的模型表現對照。

跑法：
  python experiments/literature_recurrence_model/run.py <simulate_cohort.py 的輸出資料夾>
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import literature as LIT  # noqa: E402

SIMDATA = sys.argv[1]
OUT = os.path.join(HERE, "outputs")
os.makedirs(os.path.join(OUT, "plot_data"), exist_ok=True)
SEED = 2026
YEAR, LANDMARK, HORIZON, FOLLOW = 365, 730, 90, 365
WINDOWS = [30, 90, 180, 365, 730]
LOG_RATE, DIARY_NOISE, LAB_EVERY = 0.70, 0.30, 30
ZH = {
    "systemic_lupus_erythematosus": "紅斑性狼瘡", "rheumatoid_arthritis": "類風濕性關節炎", "asthma": "氣喘",
    "chronic_urticaria": "慢性蕁麻疹", "psoriatic_arthritis": "乾癬性關節炎", "ankylosing_spondylitis": "僵直性脊椎炎",
    "osteoarthritis": "退化性關節炎", "anca_vasculitis": "ANCA 血管炎", "behcet_disease": "貝賽特氏症",
    "multiple_sclerosis": "多發性硬化症", "inflammatory_bowel_disease": "發炎性腸道疾病", "gout": "痛風",
    "idiopathic_pulmonary_fibrosis": "特發性肺纖維化", "systemic_sclerosis": "全身性硬化症",
    "sjogren_syndrome": "乾燥症", "igg4_related_disease": "IgG4 相關疾病",
}
EN = {
    "systemic_lupus_erythematosus": "SLE", "rheumatoid_arthritis": "Rheumatoid arthritis", "asthma": "Asthma",
    "chronic_urticaria": "Chronic urticaria", "psoriatic_arthritis": "Psoriatic arthritis",
    "ankylosing_spondylitis": "Ankylosing spondylitis", "osteoarthritis": "Osteoarthritis",
    "anca_vasculitis": "ANCA vasculitis", "behcet_disease": "Behçet's disease", "multiple_sclerosis": "Multiple sclerosis",
    "inflammatory_bowel_disease": "IBD", "gout": "Gout", "idiopathic_pulmonary_fibrosis": "IPF",
    "systemic_sclerosis": "Systemic sclerosis", "sjogren_syndrome": "Sjögren's", "igg4_related_disease": "IgG4-RD",
}


def save(name, df):
    df.to_csv(os.path.join(OUT, "plot_data", name + ".csv"), index=False, encoding="utf-8-sig")


# ═════════════ 1. 文獻統整 ═════════════
def dl_pool(est, lo, hi):
    """DerSimonian–Laird 隨機效應（log 尺度）；SE 由 95% CI 反推。"""
    y = np.log(est)
    se = (np.log(hi) - np.log(lo)) / (2 * 1.96)
    w = 1 / se ** 2
    fixed = np.sum(w * y) / np.sum(w)
    q = np.sum(w * (y - fixed) ** 2)
    df = len(y) - 1
    tau2 = max(0.0, (q - df) / (np.sum(w) - np.sum(w ** 2) / np.sum(w))) if df > 0 else 0.0
    wr = 1 / (se ** 2 + tau2)
    mu = np.sum(wr * y) / np.sum(wr)
    s = math.sqrt(1 / np.sum(wr))
    i2 = max(0.0, (q - df) / q) if q > 0 else 0.0
    return {"pooled": math.exp(mu), "lo": math.exp(mu - 1.96 * s), "hi": math.exp(mu + 1.96 * s),
            "I2": i2, "tau2": tau2, "k": len(y), "Q_p": float(1 - stats.chi2.cdf(q, df)) if df > 0 else None}


def weibull_k(t, cum):
    """log(−log S) = k·log t − k·log λ 的最小平方擬合；只用 0.02 < S < 0.98 的點。"""
    t, s = np.asarray(t, float), 1 - np.asarray(cum, float)
    m = (s > 0.02) & (s < 0.98)
    if m.sum() < 2:
        return np.nan, np.nan
    k, c = np.polyfit(np.log(t[m]), np.log(-np.log(s[m])), 1)
    return float(k), float(math.exp(-c / k))


def literature_synthesis():
    tg = LIT.disease_targets()
    rows = []
    for d, pmid, kind, v, y, note in LIT.RATES:
        rows.append({"disease": d, "疾病": ZH[d], "pmid": pmid, "type": kind, "value": v, "years": y,
                     "annual_p": LIT.annual_p(kind, v, y), "note": note})
    save("文獻_各研究一年復發機率", pd.DataFrame(rows))
    eff = pd.DataFrame(LIT.EFFECTS, columns=["hyp", "疾病", "pmid", "measure", "est", "lo", "hi", "note"])
    pooled = {h: dl_pool(g.est.values, g.lo.values, g.hi.values) for h, g in eff.groupby("hyp")}
    curves = []
    for name, pmid, t, c in LIT.CURVES:
        k, lam = weibull_k(t, c)
        curves.append({"curve": name, "pmid": pmid, "k": k, "lambda_years": lam, "t": t, "cum": c})
    return tg, eff, pooled, curves


# ═════════════ 2. 虛擬世代與復發判定 ═════════════
def load_cohort():
    data = {}
    for f in sorted(os.listdir(SIMDATA)):
        if f.endswith(".npz"):
            z = np.load(os.path.join(SIMDATA, f), allow_pickle=True)
            data[f[:-4]] = {k: z[k] for k in z.files}
    assert len(data) == 16 and all(v["activity"].shape == (200, 1095) for v in data.values()), "需 16 病 × 200 人 × 1095 天"
    return data


def episodes(act, thr, gap):
    """in_flare = 活動度 > 個人門檻；新一次復發 = 由非復發轉為復發，且距上次復發結束 ≥ gap 天（否則併為同一次）。"""
    infl = act > thr[:, None]
    n, T = act.shape
    onset = np.zeros_like(infl)
    last_end = np.full(n, -10 ** 6)
    prev = np.zeros(n, bool)
    for t in range(T):
        cur = infl[:, t]
        start = cur & ~prev
        new = start & (t - last_end >= gap)
        onset[:, t] = new
        ended = prev & ~cur
        last_end = np.where(ended, t - 1, last_end)
        prev = cur
    return infl, onset


def gap_of(d):
    return max(int(math.ceil(float(d["refractory"]))), 7)


def p_window(onset, a, b):
    return float(onset[:, a:b].any(axis=1).mean())


def calibrate(d, target):
    """從 δ=0 往「讓復發率靠近目標」的方向每次移 0.05，取第一次跨過目標時較接近的一點。

    只往單一方向找：復發率太高就提高門檻、太低就降低門檻。復發率對 δ 並非單調——
    門檻壓得很低時患者整年處在復發中、「新一次復發」反而變少；若在整條 δ 軸上找最接近值，
    會落到這種不合理的解（第一版即如此，見說明書「過程中修正的問題」）。
    """
    base = float(d["threshold"]) + d["offset"].astype(float)

    def p_at(delta):
        _, on = episodes(d["activity"], base + delta, gap_of(d))
        return p_window(on, YEAR, 2 * YEAR)

    p0 = p_at(0.0)
    step = 0.05 if p0 > target else -0.05
    prev_d, prev_p = 0.0, p0
    for k in range(1, 241):
        delta = round(k * step, 4)
        p = p_at(delta)
        if (p - target) * (prev_p - target) <= 0:
            lo, hi, plo = prev_d, delta, prev_p  # 跨點區間內再二分 12 次
            for _ in range(12):
                mid = (lo + hi) / 2
                pm = p_at(mid)
                if (pm - target) * (plo - target) <= 0:
                    hi = mid
                else:
                    lo, plo = mid, pm
            cands = [(lo, plo), (hi, p_at(hi))]
            return min(cands, key=lambda c: abs(c[1] - target))
        prev_d, prev_p = delta, p
    return prev_d, prev_p


# ═════════════ 3. App 紀錄層與特徵 ═════════════
def records(d, disease, log_rate=LOG_RATE, noise=DIARY_NOISE):
    rng = np.random.default_rng(SEED + sorted(ZH).index(disease))
    n, T = d["activity"].shape
    logged = rng.random((n, T)) < log_rate
    sym = d["symptom"].astype(float)
    mu, sd = sym[:, :YEAR].mean(), sym[:, :YEAR].std() + 1e-9
    diary = np.where(logged, (sym - mu) / sd + rng.normal(0, noise, (n, T)), np.nan)
    lab = d["lab"].astype(float) * (1 if bool(d["lab_higher_worse"]) else -1)
    lmu, lsd = lab[:, :YEAR].mean(), lab[:, :YEAR].std() + 1e-9
    phase = rng.integers(0, LAB_EVERY, n)
    labmask = ((np.arange(T)[None, :] - phase[:, None]) % LAB_EVERY) == 0
    labz = np.where(labmask, (lab - lmu) / lsd, np.nan)
    skip = np.where(logged, d["skip"].astype(float), np.nan)
    trig = np.where(logged, (d["trig"] > 0).astype(float), np.nan)
    return diary, labz, skip, trig


def _nanslope(x):
    t = np.arange(x.shape[1], dtype=float)
    m = ~np.isnan(x)
    cnt = m.sum(1)
    tm = np.where(m, t, 0).sum(1) / np.maximum(cnt, 1)
    xm = np.nanmean(np.where(m, x, np.nan), 1)
    num = np.nansum(np.where(m, (t - tm[:, None]) * (x - xm[:, None]), 0), 1)
    den = np.sum(np.where(m, (t - tm[:, None]) ** 2, 0), 1)
    return np.where(den > 0, num / np.maximum(den, 1e-9), 0.0)


def features(rec, onset, W):
    diary, labz, skip, trig = rec
    a, b = LANDMARK - W, LANDMARK
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        dw = diary[:, a:b]
        f = {
            f"sym_mean": np.nanmean(dw, 1), "sym_max": np.nanmax(dw, 1), "sym_sd": np.nanstd(dw, 1),
            "sym_last14": np.nanmean(diary[:, b - 14:b], 1), "sym_slope": _nanslope(dw) * 30,
            "skip_frac": np.nanmean(skip[:, a:b], 1), "trig_frac": np.nanmean(trig[:, a:b], 1),
            "lab_last": _last(labz[:, a:b]), "lab_mean": np.nanmean(labz[:, a:b], 1),
            "n_onsets": onset[:, a:b].sum(1).astype(float),
            "days_since_onset": _days_since(onset[:, a:b], W),
        }
    out = pd.DataFrame(f)
    return out.fillna(out.mean()).fillna(0.0)


def _last(x):
    m = ~np.isnan(x)
    idx = np.where(m.any(1), x.shape[1] - 1 - np.argmax(m[:, ::-1], 1), -1)
    return np.where(idx >= 0, x[np.arange(len(x)), np.maximum(idx, 0)], np.nan)


def _days_since(on, W):
    has = on.any(1)
    last = W - 1 - np.argmax(on[:, ::-1], 1)
    return np.where(has, W - last, W).astype(float)


def build_table(data, deltas, log_rate=LOG_RATE, noise=DIARY_NOISE, oracle=False):
    """組成 3,200 人的患者表（每病依 deltas 判定復發）。"""
    rows, feats = [], {W: [] for W in WINDOWS}
    for d in sorted(data):
        z = data[d]
        thr = float(z["threshold"]) + z["offset"].astype(float) + deltas[d]
        infl, on = episodes(z["activity"], thr, gap_of(z))
        rec = records(z, d, log_rate, noise)
        for W in WINDOWS:
            f = features(rec, on, W)
            if oracle:  # 上限：直接看到潛在活動度與個人門檻的距離（現實中不可能取得）
                a = z["activity"][:, LANDMARK - W:LANDMARK] - thr[:, None]
                f = f.assign(or_last=a[:, -1], or_mean14=a[:, -14:].mean(1), or_max=a.max(1), or_mean=a.mean(1))
            feats[W].append(f)
        after = on[:, LANDMARK:LANDMARK + FOLLOW]
        has = after.any(1)
        first = np.where(has, np.argmax(after, 1) + 1, FOLLOW)
        yr = [on[:, k * YEAR:(k + 1) * YEAR] for k in range(3)]
        skip1 = z["skip"][:, :YEAR].mean(1)
        sym1 = z["symptom"][:, :YEAR].mean(1)
        for i in range(len(thr)):
            rows.append({
                "patient_id": f"{z['short']}_{i:04d}", "disease": d, "疾病": ZH[d], "age": int(z["age"][i]),
                "female": int(z["sex"][i]), "subtype": str(z["subtype"][i]), "delta": deltas[d],
                "n_onset_y1": int(yr[0][i].sum()), "n_onset_y2": int(yr[1][i].sum()), "n_onset_y3": int(yr[2][i].sum()),
                "skip_frac_y1": float(skip1[i]), "sym_mean_y1": float(sym1[i]),
                "in_flare_at_landmark": bool(infl[i, LANDMARK - 1]),
                "flare_frac": float(infl[i, YEAR:2 * YEAR].mean()),
                "flare_days_y2": int(infl[i, YEAR:2 * YEAR].sum()),
                "y90": int(on[i, LANDMARK:LANDMARK + HORIZON].any()), "time": int(first[i]), "event": int(has[i]),
                "in_flare_y2_start": bool(infl[i, YEAR - 1]),
                "first_after_y1": _first_after(on[i], infl[i], YEAR),
            })
    tab = pd.DataFrame(rows)
    feats = {W: pd.concat(v, ignore_index=True).add_prefix(f"w{W}_") for W, v in feats.items()}
    return tab, feats


def _first_after(on, infl, start):
    """第 365 天起到第 1094 天的第一次新復發天數（從第 365 天算）；無則 −1。"""
    idx = np.flatnonzero(on[start:])
    return int(idx[0]) + 1 if len(idx) else -1


# ═════════════ 4. 虛擬世代的機制量測 ═════════════
def mh_rr(tab, expo_col, out_col="any_y2"):
    """依疾病分層的 Mantel–Haenszel RR 與 Greenland–Robins 95% CI。"""
    num = den = var_num = 0.0
    R = S = 0.0
    for _, g in tab.groupby("disease"):
        e = g[expo_col].astype(bool)
        y = g[out_col].astype(bool)
        a, n1 = (y & e).sum(), e.sum()
        c, n0 = (y & ~e).sum(), (~e).sum()
        N = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        num += a * n0 / N
        den += c * n1 / N
        var_num += (n1 * n0 * (a + c) - a * c * N) / N ** 2
    if num == 0 or den == 0:
        return {"rr": np.nan, "lo": np.nan, "hi": np.nan}
    rr = num / den
    se = math.sqrt(var_num / (num * den))
    return {"rr": rr, "lo": rr * math.exp(-1.96 * se), "hi": rr * math.exp(1.96 * se)}


def mechanisms(tab):
    t = tab.copy()
    t["any_y2"] = t.n_onset_y2 > 0
    t["prior_y1"] = t.n_onset_y1 > 0
    out = {"H1_prior_flare": mh_rr(t, "prior_y1")}
    t["sym_hi"] = t.groupby("disease").sym_mean_y1.transform(lambda s: s >= s.quantile(2 / 3))
    t["sym_lo"] = t.groupby("disease").sym_mean_y1.transform(lambda s: s <= s.quantile(1 / 3))
    out["H1_symptom_tertile"] = mh_rr(t[t.sym_hi | t.sym_lo], "sym_hi")
    q = t.groupby("disease").skip_frac_y1
    t["skip_hi"] = q.transform(lambda s: s >= s.quantile(0.75))
    t["skip_lo"] = q.transform(lambda s: s <= s.quantile(0.25))
    out["H2_missed_dose_quartile"] = mh_rr(t[t.skip_hi | t.skip_lo], "skip_hi")
    # 劑量反應（對照 Held 2005）：第 1 年復發次數 0/1/2/≥3 → 第 2 年復發次數的比值
    dr = []
    for k in range(4):
        m = (t.n_onset_y1 == k) if k < 3 else (t.n_onset_y1 >= 3)
        dr.append(float(t.loc[m, "n_onset_y2"].mean()) if m.any() else np.nan)
    out["dose_response_rate_y2"] = dr
    # H3：每病第 365 天未在復發者，到下一次復發的 Weibull k
    ks = {}
    for d, g in t.groupby("disease"):
        g = g[~g.in_flare_y2_start]
        tt = np.where(g.first_after_y1 > 0, g.first_after_y1, 10 ** 6) / YEAR
        pts = [0.25, 0.5, 1.0, 1.5, 2.0]
        cum = [float((tt <= p).mean()) for p in pts]
        ks[d] = {"k": weibull_k(pts, cum)[0], "cum": cum}
    out["H3_weibull_k"] = ks
    return out


# ═════════════ 5. 模型 ═════════════
def boot_auc(y, s, n=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    y, s = np.asarray(y), np.asarray(s)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            vals.append(roc_auc_score(y[i], s[i]))
    return [float(roc_auc_score(y, s)), float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def calib(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    lp = np.log(p / (1 - p)).reshape(-1, 1)
    m = LogisticRegression(C=1e6, max_iter=5000).fit(lp, y)
    return {"slope": float(m.coef_[0][0]), "intercept": float(m.intercept_[0]), "brier": float(brier_score_loss(y, p)),
            "mean_pred": float(p.mean()), "obs": float(np.mean(y))}


def cv_predict(X, y, kind="lr", seed=SEED):
    pred = np.zeros(len(y))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(X, y):
        if kind == "lr":
            m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
        else:
            m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, random_state=seed)
        m.fit(X.iloc[tr], y[tr])
        pred[te] = m.predict_proba(X.iloc[te])[:, 1]
    return pred


def harrell_c(time, event, risk):
    time, event, risk = map(np.asarray, (time, event, risk))
    order = np.argsort(time)
    time, event, risk = time[order], event[order], risk[order]
    conc = tot = 0.0
    for i in np.flatnonzero(event):
        later = time > time[i]
        tot += later.sum()
        conc += (risk[i] > risk[later]).sum() + 0.5 * (risk[i] == risk[later]).sum()
    return conc / tot


def cox_fit(X, time, event, l2=0.01, iters=50):
    """Breslow 偏概似 + 小量 L2（λ=0.01，標準化後），Newton–Raphson；避免無事件病別造成係數發散。"""
    o = np.argsort(-time)
    X, time, event = X[o], time[o], event[o]
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        r = np.exp(np.clip(X @ b, -30, 30))
        s0 = np.cumsum(r)
        s1 = np.cumsum(r[:, None] * X, 0)
        s2 = np.cumsum(r[:, None, None] * X[:, :, None] * X[:, None, :], 0)
        # 同一時間（ties）取該時間點最後一列的風險集合
        last = np.r_[time[1:] != time[:-1], True]
        pos = np.flatnonzero(last)
        idx = pos[np.searchsorted(pos, np.arange(len(time)))]
        e = event.astype(bool)
        S0, S1, S2 = s0[idx][e], s1[idx][e], s2[idx][e]
        g = (X[e] - S1 / S0[:, None]).sum(0) - l2 * b
        Hm = (S2 / S0[:, None, None] - (S1[:, :, None] * S1[:, None, :]) / S0[:, None, None] ** 2).sum(0) + l2 * np.eye(len(b))
        step = np.linalg.solve(Hm, g)
        b = b + step
        if np.max(np.abs(step)) < 1e-7:
            break
    r = np.exp(np.clip(X @ b, -30, 30))
    ut = np.unique(time[event == 1])
    h = np.array([event[time == t].sum() / r[time >= t].sum() for t in ut])
    return b, ut, np.cumsum(h)


def cox_cv(X, time, event, ts=(90, 180, 365), seed=SEED):
    """5 折 Cox：回傳折外線性預測值與各時間點預測累積復發機率（Breslow 基線）。"""
    lp = np.zeros(len(time))
    risk = {t: np.zeros(len(time)) for t in ts}
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(X, event):
        sc = StandardScaler().fit(X.iloc[tr])
        Xtr, Xte = sc.transform(X.iloc[tr]), sc.transform(X.iloc[te])
        b, bt, ch = cox_fit(Xtr, time[tr], event[tr])
        lp[te] = Xte @ b
        for t in ts:
            H0 = float(np.interp(t, bt, ch, left=0.0))
            risk[t][te] = 1 - np.exp(-H0 * np.exp(Xte @ b))
    return lp, risk


def td_auc(time, event, risk, t):
    case = (event == 1) & (time <= t)
    ctrl = (time > t) | ((time >= t) & (event == 0))
    y = np.r_[np.ones(case.sum()), np.zeros(ctrl.sum())]
    s = np.r_[risk[case], risk[ctrl]]
    return float(roc_auc_score(y, s)) if case.any() and ctrl.any() else np.nan


def literature_score(tab, feats, tg, pooled, h=HORIZON):
    """不訓練：文獻一年復發率 × 文獻統合的 H1、H2 倍數（在病別內做平均歸一，使族群平均＝文獻值）。"""
    rr1, rr2 = pooled["H1"]["pooled"], pooled["H2"]["pooled"]
    fallback = float(np.median([v["target"] for v in tg.values()]))
    x1 = (feats[365]["w365_n_onsets"].values > 0).astype(float)
    x2 = (feats[90]["w90_skip_frac"].values >= 0.20).astype(float)
    mult = rr1 ** x1 * rr2 ** x2
    out = np.zeros(len(tab))
    for d in tab.disease.unique():
        m = (tab.disease == d).values
        p = tg[d]["target"] if d in tg else fallback
        h0 = -math.log(1 - p) / YEAR
        out[m] = 1 - np.exp(-h0 * mult[m] / mult[m].mean() * h)
    return out


def static_X(tab):
    X = pd.get_dummies(tab.disease, prefix="d", dtype=float)
    X["age"] = tab.age.values
    X["female"] = tab.female.values
    return X


def model_suite(tab, feats, tg, pooled, label):
    keep = ~tab.in_flare_at_landmark.values
    T = tab[keep].reset_index(drop=True)
    F = {W: f[keep].reset_index(drop=True) for W, f in feats.items()}
    y = T.y90.values
    S = static_X(T)
    res = {"n": int(len(T)), "excluded_in_flare": int((~keep).sum()), "event_rate_90d": float(y.mean()),
           "event_rate_365d": float(T.event.mean())}
    preds = {}
    preds["只用年齡性別病別"] = cv_predict(S, y)
    preds["只用文獻（未訓練）"] = literature_score(T, F, tg, pooled)
    for W in WINDOWS:
        preds[f"紀錄 {W} 天"] = cv_predict(pd.concat([S, F[W]], axis=1), y)
    lit_logit = np.log(preds["只用文獻（未訓練）"] / (1 - preds["只用文獻（未訓練）"]))
    preds["文獻分數＋紀錄 730 天"] = cv_predict(pd.concat([S, F[730]], axis=1).assign(lit=lit_logit), y)
    preds["梯度提升樹 730 天"] = cv_predict(pd.concat([S, F[730]], axis=1), y, "gb")
    res["auroc"] = {k: boot_auc(y, v) for k, v in preds.items()}
    res["calibration"] = {k: calib(y, v) for k, v in preds.items()}
    # 逐病 AUROC（紀錄 730 天 vs 只用文獻）
    per = []
    for d in sorted(T.disease.unique()):
        m = (T.disease == d).values
        if y[m].min() != y[m].max():
            per.append({"disease": d, "疾病": ZH[d], "n": int(m.sum()), "events": int(y[m].sum()),
                        "auc_rec730": float(roc_auc_score(y[m], preds["紀錄 730 天"][m])),
                        "auc_lit": float(roc_auc_score(y[m], preds["只用文獻（未訓練）"][m])),
                        "auc_static": float(roc_auc_score(y[m], preds["只用年齡性別病別"][m]))})
    res["per_disease"] = per
    # 置換檢定
    rng = np.random.default_rng(SEED)
    Xfull = pd.concat([S, F[730]], axis=1)
    res["permutation_auc"] = [float(roc_auc_score(yp, cv_predict(Xfull, yp, seed=SEED + i)))
                              for i, yp in enumerate(rng.permutation(y) for _ in range(50))]
    # 係數（全體資料擬合，只作解釋）
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(F[730], y)
    res["coef_730"] = dict(zip(F[730].columns, map(float, m[-1].coef_[0])))
    # Cox：復發時間
    Xc = pd.concat([S.drop(columns=[c for c in S if c.startswith("d_")][:1]), F[730]], axis=1)
    lp, crisk = cox_cv(Xc, T.time.values.astype(float), T.event.values)
    res["cox_c_index"] = float(harrell_c(T.time.values, T.event.values, lp))
    res["cox_td_auc"] = {t: td_auc(T.time.values, T.event.values, crisk[t], t) for t in (90, 180, 365)}
    lp_s, crisk_s = cox_cv(S.drop(columns=[c for c in S if c.startswith("d_")][:1]),
                           T.time.values.astype(float), T.event.values)
    res["cox_static_c_index"] = float(harrell_c(T.time.values, T.event.values, lp_s))
    # 預警：前 20%
    res["early_warning"] = {}
    for k in ["紀錄 730 天", "只用文獻（未訓練）", "只用年齡性別病別"]:
        s = preds[k]
        flag = s >= np.quantile(s, 0.80)
        tp = flag & (y == 1)
        lead = T.time.values[tp]
        res["early_warning"][k] = {"flagged": int(flag.sum()), "sensitivity": float(tp.sum() / y.sum()),
                                   "ppv": float(tp.sum() / flag.sum()), "lift": float(tp.sum() / flag.sum() / y.mean()),
                                   "lead_days_median": float(np.median(lead)), "lead_days_iqr": [float(np.percentile(lead, 25)), float(np.percentile(lead, 75))]}
    T = T.assign(**{f"pred_{k}": v for k, v in preds.items()}, cox_lp=lp,
                 cox_risk90=crisk[90], cox_risk180=crisk[180], cox_risk365=crisk[365])
    T.to_csv(os.path.join(OUT, f"landmark_predictions_{label}.csv"), index=False, encoding="utf-8-sig")
    return res, T, preds, y


# ═════════════ 主程式 ═════════════
def main():
    tg, eff, pooled, curves = literature_synthesis()
    data = load_cohort()

    # 原始世代
    deltas0 = {d: 0.0 for d in data}
    tab0, feats0 = build_table(data, deltas0)
    # 文獻校準
    deltas, achieved = {}, {}
    for d in sorted(data):
        if d in tg:
            deltas[d], achieved[d] = calibrate(data[d], tg[d]["target"])
        else:
            deltas[d], achieved[d] = 0.0, None
    tab1, feats1 = build_table(data, deltas)

    mech0, mech1 = mechanisms(tab0), mechanisms(tab1)
    sens = sensitivity(data, deltas, tab1)

    # 逐病交叉對比表
    rows = []
    for d in sorted(data):
        g0, g1 = tab0[tab0.disease == d], tab1[tab1.disease == d]
        rows.append({
            "disease": d, "疾病": ZH[d], "en": EN[d], "lit_target": tg[d]["target"] if d in tg else np.nan,
            "lit_lo": tg[d]["lo"] if d in tg else np.nan, "lit_hi": tg[d]["hi"] if d in tg else np.nan,
            "lit_k": tg[d]["k"] if d in tg else 0, "delta": deltas[d],
            "orig_p_y2": float((g0.n_onset_y2 > 0).mean()), "orig_p_y3": float((g0.n_onset_y3 > 0).mean()),
            "calib_p_y2": float((g1.n_onset_y2 > 0).mean()), "calib_p_y3": float((g1.n_onset_y3 > 0).mean()),
            "orig_rate_y2": float(g0.n_onset_y2.mean()), "calib_rate_y2": float(g1.n_onset_y2.mean()),
            "orig_flare_time_frac": float(g0.flare_frac.mean()), "calib_flare_time_frac": float(g1.flare_frac.mean()),
            "orig_episode_days": float(g0.flare_days_y2.sum() / max(g0.n_onset_y2.sum(), 1)),
            "calib_episode_days": float(g1.flare_days_y2.sum() / max(g1.n_onset_y2.sum(), 1)),
            "orig_in_flare_landmark": float(g0.in_flare_at_landmark.mean()), "calib_in_flare_landmark": float(g1.in_flare_at_landmark.mean()),
            "weibull_k_orig": mech0["H3_weibull_k"][d]["k"], "weibull_k_calib": mech1["H3_weibull_k"][d]["k"],
        })
    cross = pd.DataFrame(rows)

    res0, T0, preds0, y0 = model_suite(tab0, feats0, tg, pooled, "original")
    res1, T1, preds1, y1 = model_suite(tab1, feats1, tg, pooled, "calibrated")

    # 模型預測的一年復發率（Cox 365 天，折外）對照文獻與第 3 年實際
    pm = T1.groupby("disease").agg(model_pred_365=("cox_risk365", "mean"), obs_365_landmark=("event", "mean")).reset_index()
    cross = cross.merge(pm, on="disease", how="left")
    save("交叉對比_逐病一年復發率", cross)
    anchored = cross.dropna(subset=["lit_target"])
    agreement = {
        "spearman_lit_vs_orig": float(stats.spearmanr(anchored.lit_target, anchored.orig_p_y2)[0]),
        "spearman_lit_vs_calib_y3": float(stats.spearmanr(anchored.lit_target, anchored.calib_p_y3)[0]),
        "spearman_lit_vs_model": float(stats.spearmanr(anchored.lit_target, anchored.model_pred_365)[0]),
        "mae_lit_vs_orig": float((anchored.lit_target - anchored.orig_p_y2).abs().mean()),
        "mae_lit_vs_calib_y3": float((anchored.lit_target - anchored.calib_p_y3).abs().mean()),
        "mae_lit_vs_model": float((anchored.lit_target - anchored.model_pred_365).abs().mean()),
        "within_lit_range_orig": int(((anchored.orig_p_y2 >= anchored.lit_lo) & (anchored.orig_p_y2 <= anchored.lit_hi)).sum()),
        "within_lit_range_calib_y3": int(((anchored.calib_p_y3 >= anchored.lit_lo) & (anchored.calib_p_y3 <= anchored.lit_hi)).sum()),
        "within_lit_range_model": int(((anchored.model_pred_365 >= anchored.lit_lo) & (anchored.model_pred_365 <= anchored.lit_hi)).sum()),
        "n_anchored": int(len(anchored)),
    }

    # 繪圖資料
    save("文獻_效果量", eff)
    save("文獻_累積曲線Weibull", pd.DataFrame(curves))
    for lab, preds, y in (("calibrated", preds1, y1), ("original", preds0, y0)):
        from sklearn.metrics import roc_curve
        roc = []
        for k in ["只用年齡性別病別", "只用文獻（未訓練）", "紀錄 730 天", "梯度提升樹 730 天"]:
            fpr, tpr, _ = roc_curve(y, preds[k])
            idx = np.linspace(0, len(fpr) - 1, min(len(fpr), 200)).astype(int)
            roc.append(pd.DataFrame({"模型": k, "fpr": fpr[idx], "tpr": tpr[idx]}))
        save(f"ROC_{lab}", pd.concat(roc))
        cal = pd.DataFrame({"p": preds["紀錄 730 天"], "y": y})
        cal["bin"] = pd.qcut(cal.p.rank(method="first"), 10, labels=False)
        save(f"校準_{lab}", cal.groupby("bin").agg(pred=("p", "mean"), obs=("y", "mean"), n=("y", "size")).reset_index())
    # 時間線：Cox 365 天風險三分組，實際 KM vs 預測
    T1["tertile"] = pd.qcut(T1.cox_lp.rank(method="first"), 3, labels=["低", "中", "高"])
    tl = []
    for g, gg in T1.groupby("tertile", observed=True):
        for t in range(0, FOLLOW + 1, 15):
            tl.append({"組別": g, "day": t, "observed": float(((gg.event == 1) & (gg.time <= t)).mean()),
                       "predicted": float(np.mean(_interp_risk(gg, t)))})
    save("時間線_風險三分組", pd.DataFrame(tl))

    results = {
        "literature": {"targets": tg, "pooled": pooled, "curves": curves,
                       "ms_prior_relapse_rr": LIT.MS_PRIOR_RELAPSE["rr"], "gout_adherence": LIT.GOUT_ADHERENCE},
        "calibration": {"deltas": deltas, "achieved_y2": achieved},
        "mechanisms": {"original": mech0, "calibrated": mech1},
        "agreement": agreement,
        "sensitivity": sens,
        "models": {"original": res0, "calibrated": res1},
        "previous_study": {"nhefs_no_record_auc": 0.525, "nhefs_long_record_auc": 0.71, "twin_full_lr_auc": 0.773, "twin_mdpiece_lr_auc": 0.771,
                           "usage_years_auc_1y": 0.678, "usage_years_auc_10y": 0.718},
        "settings": {"landmark": LANDMARK, "horizon": HORIZON, "follow": FOLLOW, "windows": WINDOWS,
                     "log_rate": LOG_RATE, "diary_noise_sd": DIARY_NOISE, "lab_every": LAB_EVERY, "seed": SEED},
    }
    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=_js)
    tab1.to_csv(os.path.join(OUT, "新數據_校準後3200人患者表.csv"), index=False, encoding="utf-8-sig")
    tab0.to_csv(os.path.join(OUT, "原始虛擬3200人患者表.csv"), index=False, encoding="utf-8-sig")
    _print_summary(results, cross)


def sensitivity(data, deltas, tab):
    """紀錄品質的影響（校準後世代，logistic 730 天）：回憶式紀錄、本研究設定、完整紀錄、潛在活動度上限。"""
    out = {}
    arms = {"回憶式（30% 天數、誤差 0.8 SD）": (0.30, 0.8, False), "本研究設定（70%、0.3 SD）": (LOG_RATE, DIARY_NOISE, False),
            "完整紀錄（100%、無誤差）": (1.0, 0.0, False), "上限：直接看到潛在活動度": (1.0, 0.0, True)}
    for name, (lr, nz, orc) in arms.items():
        t, f = build_table(data, deltas, lr, nz, orc)
        keep = ~t.in_flare_at_landmark.values
        y = t.y90.values[keep]
        X = pd.concat([static_X(t[keep].reset_index(drop=True)), f[730][keep].reset_index(drop=True)], axis=1)
        p = cv_predict(X, y)
        within = []
        for dd in sorted(t.disease.unique()):
            m = (t[keep].disease == dd).values
            if y[m].min() != y[m].max():
                within.append((roc_auc_score(y[m], p[m]), y[m].sum()))
        w = np.array(within)
        out[name] = {"auc": boot_auc(y, p, 300), "within_disease_auc_weighted": float(np.average(w[:, 0], weights=w[:, 1]))}
    return out


def _interp_risk(g, t):
    pts = np.array([0, 90, 180, 365])
    vals = np.c_[np.zeros(len(g)), g.cox_risk90, g.cox_risk180, g.cox_risk365]
    return np.array([np.interp(t, pts, v) for v in vals])


def _js(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def _print_summary(r, cross):
    p = r["literature"]["pooled"]
    print("文獻統合 H1", {k: round(v, 3) if isinstance(v, float) else v for k, v in p["H1"].items()})
    print("文獻統合 H2", {k: round(v, 3) if isinstance(v, float) else v for k, v in p["H2"].items()})
    print("Weibull k（文獻）", [(c["curve"], round(c["k"], 2)) for c in r["literature"]["curves"]])
    for lab in ("original", "calibrated"):
        m = r["mechanisms"][lab]
        print(lab, "H1", m["H1_prior_flare"], "H1sym", m["H1_symptom_tertile"], "H2", m["H2_missed_dose_quartile"])
        print(lab, "dose-response", m["dose_response_rate_y2"])
        mm = r["models"][lab]
        print(lab, "n", mm["n"], "excl", mm["excluded_in_flare"], "rate90", round(mm["event_rate_90d"], 3))
        for k, v in mm["auroc"].items():
            print(f"   {k}: {v[0]:.3f} ({v[1]:.3f}-{v[2]:.3f})  cal slope {mm['calibration'][k]['slope']:.2f}")
        print("   perm AUC mean", round(float(np.mean(mm["permutation_auc"])), 3), "cox C", round(mm["cox_c_index"], 3),
              "static C", round(mm["cox_static_c_index"], 3), "tdAUC", mm["cox_td_auc"])
        print("   EW", mm["early_warning"])
    print(r["agreement"])
    print(r["sensitivity"])
    print(cross[["疾病", "lit_target", "lit_lo", "lit_hi", "delta", "orig_p_y2", "calib_p_y2", "calib_p_y3", "model_pred_365",
                 "weibull_k_orig", "weibull_k_calib"]].round(3).to_string())


if __name__ == "__main__":
    main()
