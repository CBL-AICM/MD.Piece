# -*- coding: utf-8 -*-
"""校準三步（指示 三之四，照順序）。達成值須於啟動時列印並寫入 assumptions.md。

步驟一：調 μ_intrinsic 分布的平均，使「完全停藥後 24 個月」發作率 → 0.306（De Rosa 2018）；檢核 52 週 → 0.321（Gopal 2023）。
        兩者若不能同時滿足，以 24 個月為主，記錄偏差（第五部第 2 題）。
步驟二：反推 σ_biopsy 與門檻：切片臂觀測 μ_intrinsic + N(0, σ_biopsy²)，門檻取「發作者的第 1 百分位」（敏感度 → 接近 1.00），
        再二分 σ_biopsy 使特異度 → 0.88。σ 大 → 特異度低（單調）。
步驟三：靜態基線 C 落在 [0.65, 0.75]；不在區間時走 kappa 格點取最接近中點者。
pilot 世代用 master_seed+1000（與分析世代分開）。"""
import numpy as np

from m0_params import value
from m1_generator import simulate_cohort as _sim
from m2_risk import static_auc
from m6_arms import biopsy_observation
from seeding import module_rng


def step1_mu_mean(P, Cj, master_seed, n_pilot=1500, iters=14, verbose=True):
    target = float(value(P, "withdrawal_flare_rate_24m"))
    check52 = float(value(P, "withdrawal_flare_rate_52w"))
    lo, hi = -0.5, 2.5                                                # μ 平均的搜尋範圍（x 單位）

    def rate(m):
        C = _sim(P, Cj, master_seed + 1000, n=n_pilot, mu_mean=m, taper=dict(complete=True))
        return float(C["event_24m"].mean()), float(C["event_52w"].mean())

    r_lo, _ = rate(lo); r_hi, _ = rate(hi)
    clamped = None
    if r_lo > target:
        best, clamped = lo, "lower_bound"
    elif r_hi < target:
        best, clamped = hi, "upper_bound"
    else:
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            if rate(mid)[0] < target:
                lo = mid
            else:
                hi = mid
        best = 0.5 * (lo + hi)
    r24, r52 = rate(best)
    out = dict(step="一 μ_intrinsic 平均", target=f"24 個月發作率 {target:.3f}（檢核 52 週 {check52:.3f}）",
               achieved=f"24 個月 {r24:.3f}、52 週 {r52:.3f}", mu_mean=float(best), rate_24m=r24, rate_52w=r52,
               dev_52w=float(r52 - check52), clamped=clamped, note=("" if clamped is None else f"卡在{clamped}") + (f"；52 週偏差 {r52 - check52:+.3f}" ))
    if verbose:
        print(f"[校準一] μ_intrinsic 平均 = {best:.3f} → 24 個月發作率 {r24:.3f}（目標 {target:.3f}）、52 週 {r52:.3f}（檢核 {check52:.3f}）"
              + (f"  ※ {clamped}" if clamped else ""))
    return out


def step2_sigma_biopsy(P, Cj, master_seed, mu_mean, n_pilot=1500, iters=14, sens_q=0.01, verbose=True):
    """門檻 = 發作者 mu_obs 的第 (100·sens_q) 百分位（敏感度 = 1 − sens_q ≈ 1.00）；二分 σ 使特異度 → 0.88。"""
    tgt_sens, tgt_spec = float(value(P, "biopsy_rule_sensitivity")), float(value(P, "biopsy_rule_specificity"))
    C = _sim(P, Cj, master_seed + 1000, n=n_pilot, mu_mean=mu_mean, taper=dict(complete=True))
    y = C["event_24m"]
    rng = module_rng(master_seed + 1000, "arms", 0)
    eps = rng.normal(0.0, 1.0, len(y))                                # 固定的標準常態，σ 只縮放它

    def perf(sig):
        mu_obs = C["mu_intrinsic"] + sig * eps
        thr = float(np.quantile(mu_obs[y], sens_q))
        pred = mu_obs > thr
        sens = float(pred[y].mean()); spec = float((~pred[~y]).mean())
        return sens, spec, thr

    s0 = perf(0.0)
    if s0[1] < tgt_spec:                                              # 連無誤差都達不到特異度 → 不可達
        # 對照：De Rosa 11 位發作者中 1 位無殘餘活性（μ 規則不可能抓到）→ 敏感度目標若取 10/11，特異度可達多少
        cnt = value(P, "derosa_flare_counts"); q_alt = 1.0 - cnt["flared_with_residual_activity"] / cnt["flared"]
        mu_obs0 = C["mu_intrinsic"]; thr_alt = float(np.quantile(mu_obs0[y], q_alt)); pred_alt = mu_obs0 > thr_alt
        alt = dict(sens_target=1 - q_alt, sensitivity=float(pred_alt[y].mean()), specificity_at_sigma0=float((~pred_alt[~y]).mean()))
        # 低 μ 發作者（μ 低於非發作者中位）的比例：說明為何 μ 規則的敏感度到不了 1.00
        low_mu_flare = float(np.mean(mu_obs0[y] < np.median(mu_obs0[~y])))
        out = dict(step="二 σ_biopsy", target=f"敏感度 {tgt_sens:.2f}／特異度 {tgt_spec:.2f}", achieved=f"σ=0 時 敏感度 {s0[0]:.3f}／特異度 {s0[1]:.3f}",
                   sigma_biopsy=None, threshold=s0[2], sensitivity=s0[0], specificity=s0[1],
                   note=f"unreachable：無誤差時特異度已低於目標；發作者中 {low_mu_flare:.0%} 的 μ 低於非發作者中位（基線風險造成的低 μ 發作）。對照：敏感度目標取 10/11 時 σ=0 特異度 {alt['specificity_at_sigma0']:.3f}",
                   alt_sens_10_of_11=alt, low_mu_flarer_share=low_mu_flare)
        if verbose:
            print(f"[校準二] unreachable：σ_biopsy=0 時特異度 {s0[1]:.3f} < {tgt_spec}；{out['note']}")
        return out
    lo, hi = 0.0, 3.0 * float(np.std(C["mu_intrinsic"]))
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if perf(mid)[1] > tgt_spec:                                    # 特異度仍高 → σ 可再大
            lo = mid
        else:
            hi = mid
    sig = 0.5 * (lo + hi)
    sens, spec, thr = perf(sig)
    out = dict(step="二 σ_biopsy", target=f"敏感度 {tgt_sens:.2f}／特異度 {tgt_spec:.2f}", achieved=f"敏感度 {sens:.3f}／特異度 {spec:.3f}",
               sigma_biopsy=float(sig), threshold=float(thr), sensitivity=sens, specificity=spec,
               note=f"門檻＝發作者 mu_obs 第 {100 * sens_q:.0f} 百分位；σ_biopsy/SD(μ)={sig / float(np.std(C['mu_intrinsic'])):.2f}")
    if verbose:
        print(f"[校準二] σ_biopsy = {sig:.3f}（μ_intrinsic SD 的 {out['note'].split('=')[-1]}）、門檻 {thr:.3f} → 敏感度 {sens:.3f}／特異度 {spec:.3f}")
    return out


def step3_static_c(P, Cj, master_seed, mu_mean, n_pilot=1500, verbose=True):
    lo_t, hi_t = value(P, "static_c_target"); mid = 0.5 * (lo_t + hi_t)
    k0 = float(value(P, "kappa"))

    def auc_for(k):
        C = _sim(P, Cj, master_seed + 1000, n=n_pilot, mu_mean=mu_mean, kappa=k, taper=dict(complete=True))
        return float(static_auc(C))

    tried = [(k0, auc_for(k0))]
    best = tried[0]
    if not (lo_t <= best[1] <= hi_t):
        for k in P["kappa"]["grid"]:
            if k != k0:
                tried.append((k, auc_for(k)))
        best = min(tried, key=lambda kv: abs(kv[1] - mid))
    out = dict(step="三 靜態基線 C", target=f"[{lo_t}, {hi_t}]", achieved=f"C = {best[1]:.3f}（kappa={best[0]}）", kappa=float(best[0]),
               static_c=float(best[1]), in_target=bool(lo_t <= best[1] <= hi_t), tried=tried,
               note="" if lo_t <= best[1] <= hi_t else "未落在區間：kappa 格點皆不可達，取最接近中點者")
    if verbose:
        print(f"[校準三] kappa={best[0]} → 靜態 C {best[1]:.3f}（目標 {lo_t}–{hi_t}）" + ("" if out["in_target"] else "  ※ 未達"))
    return out
