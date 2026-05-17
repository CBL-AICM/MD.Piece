"""Evaluation metrics + 95% bootstrap CIs."""

from __future__ import annotations

import numpy as np
import torch
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader


def _bootstrap_ci(
    y_true: np.ndarray, y_pred: np.ndarray, metric_fn, n_iter: int = 500, seed: int = 0,
) -> tuple[float, float, float]:
    """Return (point_estimate, ci_low, ci_high)."""
    rng = np.random.default_rng(seed)
    point = float(metric_fn(y_true, y_pred))
    n = len(y_true)
    vals = []
    for _ in range(n_iter):
        idx = rng.integers(0, n, n)
        try:
            vals.append(float(metric_fn(y_true[idx], y_pred[idx])))
        except ValueError:
            continue
    if not vals:
        return point, float("nan"), float("nan")
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


@torch.no_grad()
def predict(model, loader: DataLoader, device: torch.device) -> dict[str, np.ndarray]:
    """Run model over a DataLoader, return concatenated predictions and targets."""
    model.eval()
    yr_true, yr_pred, yc_true, yc_prob = [], [], [], []
    for X, yr, yc in loader:
        X = X.to(device)
        reg, cls = model(X)
        yr_true.append(yr.numpy())
        yr_pred.append(reg.cpu().numpy())
        yc_true.append(yc.numpy())
        yc_prob.append(torch.sigmoid(cls).cpu().numpy())
    return {
        "yr_true": np.concatenate(yr_true),
        "yr_pred": np.concatenate(yr_pred),
        "yc_true": np.concatenate(yc_true),
        "yc_prob": np.concatenate(yc_prob),
    }


def regression_report(yt: np.ndarray, yp: np.ndarray) -> dict:
    """MAE, RMSE, R^2 with 95% CI."""
    mae, mae_lo, mae_hi = _bootstrap_ci(yt, yp, mean_absolute_error)
    rmse_fn = lambda a, b: float(np.sqrt(mean_squared_error(a, b)))
    rmse, rmse_lo, rmse_hi = _bootstrap_ci(yt, yp, rmse_fn)
    r2, r2_lo, r2_hi = _bootstrap_ci(yt, yp, r2_score)
    # naive baseline: predict last observed value would need raw seq;
    # here use mean predictor as a sanity baseline
    base_mae = float(np.mean(np.abs(yt - yt.mean())))
    return {
        "mae": {"point": mae, "ci95": [mae_lo, mae_hi]},
        "rmse": {"point": rmse, "ci95": [rmse_lo, rmse_hi]},
        "r2": {"point": r2, "ci95": [r2_lo, r2_hi]},
        "baseline_mean_predictor_mae": base_mae,
    }


def classification_report(yt: np.ndarray, yp: np.ndarray) -> dict:
    """AUROC, AUPRC, F1@0.5 with 95% CI."""
    pos = int(yt.sum())
    neg = len(yt) - pos
    if pos == 0 or neg == 0:
        return {
            "auroc": None, "auprc": None, "f1@0.5": None,
            "positive_rate": float(yt.mean()),
            "note": "single-class split, metrics undefined",
        }
    auroc, ar_lo, ar_hi = _bootstrap_ci(yt, yp, roc_auc_score)
    auprc, ap_lo, ap_hi = _bootstrap_ci(yt, yp, average_precision_score)
    f1_fn = lambda a, b: f1_score(a, (b >= 0.5).astype(int), zero_division=0)
    f1, f1_lo, f1_hi = _bootstrap_ci(yt, yp, f1_fn)
    return {
        "auroc": {"point": auroc, "ci95": [ar_lo, ar_hi]},
        "auprc": {"point": auprc, "ci95": [ap_lo, ap_hi]},
        "f1@0.5": {"point": f1, "ci95": [f1_lo, f1_hi]},
        "positive_rate": float(yt.mean()),
    }
