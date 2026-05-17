"""Feature engineering: cohort -> per-patient long DataFrame -> windowed samples."""

from __future__ import annotations

import numpy as np
import pandas as pd

from md_piece.cohort_generator import Cohort
from md_piece.disease_loader import DiseaseConfig


CORE_NUMERIC = ["activity", "irreversible_burden", "n_active_triggers"]


def build_patient_frame(cohort: Cohort, disease_cfg: DiseaseConfig) -> pd.DataFrame:
    """Concatenate cohort timeseries and attach static (per-patient) features.

    Output columns:
        patient_id, day,
        activity, irreversible_burden, n_active_triggers,
        biomarker_* (disease-specific, kept under common prefix),
        age, sex_F, on_<treatment_id>* (multi-hot),
        in_flare (target component),
        disease_id (string).
    """
    df = cohort.to_dataframe().copy()
    meta = cohort.metadata_dataframe().set_index("patient_id")

    # one-hot treatments — union of all YAML treatment ids
    tx_ids = [tx["id"] for tx in disease_cfg.treatments]
    for tx_id in tx_ids:
        df[f"on_{tx_id}"] = df["patient_id"].map(
            lambda pid: int(tx_id in meta.loc[pid, "treatments"].split(",")) if meta.loc[pid, "treatments"] else 0
        )

    # demographics
    df["age"] = df["patient_id"].map(lambda pid: int(meta.loc[pid, "age"]))
    df["sex_F"] = df["patient_id"].map(lambda pid: int(meta.loc[pid, "sex"] == "F"))

    # rename biomarkers with disease prefix to avoid collisions when stacking diseases
    bm_cols = list(disease_cfg.biomarkers.keys())
    rename_map = {c: f"bm_{c}" for c in bm_cols}
    df = df.rename(columns=rename_map)

    df["disease_id"] = disease_cfg.id
    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the list of feature column names (sequence inputs)."""
    drop = {"patient_id", "day", "disease_id", "in_flare"}
    return [c for c in df.columns if c not in drop]


def make_windows(
    df: pd.DataFrame,
    window_size: int,
    horizon_days: int,
    flare_horizon_days: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Slide a window over each patient and build (X, y_reg, y_cls).

    Parameters
    ----------
    df : DataFrame
        Output of build_patient_frame (one disease).
    window_size : int
        # past days as input.
    horizon_days : int
        # days ahead for activity regression target.
    flare_horizon_days : int
        # days ahead window for "any flare" binary target.

    Returns
    -------
    X : (N, window_size, F) float32
    y_reg : (N,) float32   — activity at t+horizon
    y_cls : (N,) int64     — 1 if any in_flare==1 in (t+1 .. t+flare_horizon_days)
    patient_ids : list[str] of length N
    """
    feats = feature_columns(df)
    X_list, yr_list, yc_list, pid_list = [], [], [], []

    for pid, sub in df.groupby("patient_id", sort=False):
        sub = sub.sort_values("day").reset_index(drop=True)
        arr = sub[feats].to_numpy(dtype=np.float32)
        act = sub["activity"].to_numpy(dtype=np.float32)
        fl = sub["in_flare"].to_numpy(dtype=np.int64)
        n = len(sub)
        t_end = n - max(horizon_days, flare_horizon_days)
        for t in range(window_size, t_end):
            X_list.append(arr[t - window_size : t])
            yr_list.append(act[t + horizon_days - 1])
            yc_list.append(int(fl[t : t + flare_horizon_days].max() > 0))
            pid_list.append(pid)

    if not X_list:
        return (
            np.zeros((0, window_size, len(feats)), dtype=np.float32),
            np.zeros((0,), dtype=np.float32),
            np.zeros((0,), dtype=np.int64),
            [],
        )
    return (
        np.stack(X_list),
        np.array(yr_list, dtype=np.float32),
        np.array(yc_list, dtype=np.int64),
        pid_list,
    )
