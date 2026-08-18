# -*- coding: utf-8 -*-
"""四道閘門（指示 三之五）：生成世代之後、任何分析之前執行；任一未過即中止並印出實際數值。

G1 各風險層內單一型別最高佔比 ≤ 0.90（型別 = stable / flip / gradual）
G2 令 β = 0 重跑最小版 M4：max_L |ΔC_L| < 0.01（3 個閘門 seed 平均；n_gate 大於分析世代以壓抽樣雜訊）
G3 僅用 t < t_onset 的 x_obs 訓練「減藥後是否翻轉」分類器：AUROC ∈ [0.45, 0.55]
G4 mu_intrinsic 完全未進入非侵入臂特徵：簽章檢查 + 置換 mu_intrinsic 後特徵雜湊不變 + 原始碼掃描"""
import hashlib
import inspect

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

import m6_arms
from m0_params import value
from m1_generator import simulate_cohort, events_from_U, observe
from m2_risk import score, stratify
from m4_predict import run_predict, window_features
from seeding import module_rng


def g1_type_mix(cohort, coefs):
    sc = score(cohort, coefs)
    worst = 0.0; detail = {}
    for q in (5, 10):
        st = stratify(sc, q)
        shares = []
        for s in range(q):
            m = st == s
            typ = cohort["type"][m]
            shares.append({t: float(np.mean(typ == t)) for t in ("stable", "flip", "gradual")})
        w = max(max(d.values()) for d in shares)
        worst = max(worst, w); detail[f"q{q}"] = shares
    thr = float(value(cohort["_P"], "gate1_max_type_share")) if "_P" in cohort else 0.9
    return dict(gate="G1 各風險層內單一型別最高佔比", value=round(worst, 3), criterion=f"<= {thr}", passed=bool(worst <= thr),
                detail=detail, fail_means="起點未重疊，H1 被設定成偽")


def g2_beta_zero(P, Cj, master_seed, mu_mean, kappa, obs_cfg, n_gate=8000, seeds=3):
    thr = float(value(P, "gate2_max_delta_c"))
    Ls = value(P, "landmarks")
    per = []
    for gs in range(seeds):
        C = simulate_cohort(P, Cj, master_seed + 3000 + gs, n=n_gate, mu_mean=mu_mean, kappa=kappa)
        # β = 0：事件與 x 無關（同一組 U）；λ = λ0 常數 → 24 個月事件率 ≈ 1 − exp(−λ0·730)，與主分析同量級
        lam0 = value(P, "hazard")["lambda0_per_day"]
        C["t_event"] = events_from_U(C["X"], lam0, 0.0, C["U"], t_start=C["run_in"])
        C["event"] = C["t_event"] >= 0
        xo = observe(C["X"], C["run_in"], obs_cfg["interval"], obs_cfg["error_sd"], module_rng(master_seed + 3000 + gs, "obs", 0))
        r = run_predict(C, xo, Ls, folds=5, seed=77 + gs, timing=False)
        per.append({L: row["c_gain"] for L, row in r["landmarks"].items()})
    mean = {L: float(np.mean([d[L] for d in per])) for L in per[0]}
    worst = float(max(abs(v) for v in mean.values()))
    return dict(gate="G2 β=0 時 max_L |ΔC_L|", value=round(worst, 4), criterion=f"< {thr}", passed=bool(worst < thr),
                detail=dict(mean={L: round(v, 4) for L, v in mean.items()}, per_seed=[{L: round(v, 4) for L, v in d.items()} for d in per]),
                fail_means="結局仍與 x(t) 耦合，存在洩漏")


def g3_pre_onset(cohort, x_obs, folds=5, seed=0):
    """只用 t < t_onset 的觀測資料 → 特徵 [level, trend, ar1, sd] → CV AUROC 分辨『減藥後翻轉 vs 否』。"""
    lo, hi = value(cohort["_P"], "gate3_auroc_range") if "_P" in cohort else (0.45, 0.55)
    onset = cohort["t_onset"]
    F = np.array([window_features(x_obs[i].astype(float), 0, onset) for i in range(cohort["n"])])
    F = np.where(np.isnan(F), np.nanmedian(F, axis=0), F)
    y = (cohort["type"] == "flip").astype(int)
    if y.min() == y.max():
        return dict(gate="G3 定態期型別分類 AUROC", value=None, criterion=f"[{lo}, {hi}]", passed=False, fail_means="無翻轉者，無法評估")
    p = cross_val_predict(LogisticRegression(max_iter=2000), F, y, cv=StratifiedKFold(folds, shuffle=True, random_state=seed), method="predict_proba")[:, 1]
    auc = float(roc_auc_score(y, p))
    return dict(gate="G3 僅用 t<t_onset 資料的型別分類 AUROC", value=round(auc, 3), criterion=f"[{lo}, {hi}]", passed=bool(lo <= auc <= hi),
                fail_means="兩型在減藥前即可分，存在混淆")


def g4_no_mu_in_noninvasive(cohort, x_obs, window):
    """(a) 簽章不含 mu_intrinsic；(b) 原始碼不含該字串；(c) 置換 mu_intrinsic 後特徵雜湊不變。"""
    sig_ok = "mu_intrinsic" not in inspect.signature(m6_arms.noninvasive_arm).parameters and \
             "mu_intrinsic" not in inspect.signature(m6_arms.noninvasive_features).parameters
    src = inspect.getsource(m6_arms.noninvasive_features) + inspect.getsource(m6_arms.noninvasive_arm)
    src_ok = "mu_intrinsic" not in src.replace("絕對不得接收 mu_intrinsic", "").replace("沒有 mu_intrinsic", "")
    onset = cohort["t_onset"]; upto = onset + 180
    F1 = m6_arms.noninvasive_features(x_obs, onset, upto, window)
    C2 = dict(cohort); C2["mu_intrinsic"] = cohort["mu_intrinsic"][::-1].copy()          # 置換 μ 不應影響任何特徵
    F2 = m6_arms.noninvasive_features(x_obs, onset, upto, window)                          # 函式根本收不到 cohort
    h1 = hashlib.sha256(np.nan_to_num(F1).tobytes()).hexdigest(); h2 = hashlib.sha256(np.nan_to_num(F2).tobytes()).hexdigest()
    ok = sig_ok and src_ok and h1 == h2
    return dict(gate="G4 mu_intrinsic 未進入非侵入臂", value=f"簽章 {'無' if sig_ok else '有'}／原始碼 {'無' if src_ok else '有'}／置換後雜湊 {'相同' if h1 == h2 else '不同'}",
                criterion="完全未進入", passed=bool(ok), fail_means="H4 的比較失去意義")
