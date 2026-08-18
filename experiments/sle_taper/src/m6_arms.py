# -*- coding: utf-8 -*-
"""M6：切片臂與非侵入臂（本版新增；H4）。

切片臂：單次、低誤差、直接觀測 μ_intrinsic：mu_obs = mu_intrinsic + N(0, σ_biopsy²)，mu_obs > threshold → 判定會發作。
非侵入臂：高頻、高誤差、只看 x_obs：由 x_obs 在減藥後的窗內特徵（水準、斜率、AR(1)、SD、警報）
        以交叉驗證 logistic 給出發作機率。**函式簽章完全不接收 mu_intrinsic**（G4）。
compare_arms：兩臂各自的敏感度／特異度／AUC 與一致性；不得合成單一分數（第五部第 7 題）。
precision_frequency_grid：4×4（量測誤差 × 取樣間隔）→ 非侵入臂的偵測提前期與敏感度。"""
import numpy as np
from sklearn.metrics import roc_auc_score

from m4_predict import landmark_features, cv_pred


def biopsy_arm(mu_intrinsic, sigma_biopsy, threshold, rng):
    """回傳布林預測（會發作）。誤差由 rng 抽（模組 arms）。"""
    mu_obs = mu_intrinsic + (rng.normal(0.0, sigma_biopsy, len(mu_intrinsic)) if sigma_biopsy > 0 else 0.0)
    return mu_obs > threshold


def biopsy_observation(mu_intrinsic, sigma_biopsy, rng):
    return mu_intrinsic + (rng.normal(0.0, sigma_biopsy, len(mu_intrinsic)) if sigma_biopsy > 0 else 0.0)


def noninvasive_features(x_obs, onset, upto, window):
    """只由 x_obs[:, :upto] 建構特徵。簽章裡沒有 mu_intrinsic，也不接受 cohort dict——G4 以此為證。"""
    return landmark_features(x_obs, upto, window)


def noninvasive_arm(x_obs, window, params):
    """params: dict(onset, upto, y, folds, seed)。回傳 CV 發作機率（n,）。絕對不得接收 mu_intrinsic。"""
    F = noninvasive_features(x_obs, params["onset"], params["upto"], window)
    return cv_pred(F, params["y"], params.get("folds", 5), params.get("seed", 0))


def _sens_spec(pred, truth):
    pred = np.asarray(pred, bool); truth = np.asarray(truth, bool)
    sens = float(pred[truth].mean()) if truth.any() else np.nan
    spec = float((~pred[~truth]).mean()) if (~truth).any() else np.nan
    return sens, spec


def compare_arms(biopsy_pred, noninv_prob, events, top_share=None, threshold=None):
    """兩臂比較。非侵入臂以機率轉判定：threshold（絕對）或 top_share（相對）。不合成單一分數。"""
    events = np.asarray(events, bool)
    if threshold is None:
        k = max(1, int(round((top_share if top_share else events.mean()) * len(noninv_prob))))
        thr = np.sort(noninv_prob)[-k]
    else:
        thr = threshold
    nv_pred = noninv_prob >= thr
    sb, pb = _sens_spec(biopsy_pred, events)
    sn, pn = _sens_spec(nv_pred, events)
    out = dict(biopsy=dict(sensitivity=sb, specificity=pb, flagged=float(np.mean(biopsy_pred))),
               noninvasive=dict(sensitivity=sn, specificity=pn, flagged=float(np.mean(nv_pred)),
                                auc=float(roc_auc_score(events, noninv_prob)) if 0 < events.sum() < len(events) else np.nan),
               agreement=float(np.mean(nv_pred == biopsy_pred)),
               both_flag=float(np.mean(nv_pred & biopsy_pred)), only_biopsy=float(np.mean(biopsy_pred & ~nv_pred)),
               only_noninvasive=float(np.mean(nv_pred & ~biopsy_pred)),
               conflict_rate=float(np.mean(nv_pred != biopsy_pred)))
    return out
