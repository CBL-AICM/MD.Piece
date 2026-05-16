"""Dataset assembly: cohort -> patient-aware train/val/test windows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from md_piece.cohort_generator import Cohort, generate_cohort
from md_piece.disease_loader import load_disease

from ml.features import build_patient_frame, feature_columns, make_windows


@dataclass
class WindowSplit:
    """A split (train/val/test) of windowed samples."""

    X: np.ndarray            # (N, T, F)
    y_reg: np.ndarray        # (N,)
    y_cls: np.ndarray        # (N,)
    patient_ids: list[str]


@dataclass
class DataBundle:
    """Everything the training loop needs."""

    train: WindowSplit
    val: WindowSplit
    test: WindowSplit
    feature_names: list[str]
    scaler_mean: np.ndarray
    scaler_std: np.ndarray
    disease_ids: list[str]


def _split_patients(
    patient_ids: list[str], ratios: tuple[float, float, float], seed: int
) -> dict[str, set[str]]:
    """Partition unique patient ids into train/val/test sets."""
    uniq = sorted(set(patient_ids))
    rng = np.random.default_rng(seed)
    rng.shuffle(uniq)
    n = len(uniq)
    n_tr = int(n * ratios[0])
    n_val = int(n * ratios[1])
    return {
        "train": set(uniq[:n_tr]),
        "val": set(uniq[n_tr : n_tr + n_val]),
        "test": set(uniq[n_tr + n_val :]),
    }


def build_databundle(
    diseases: list[str],
    n_patients_per_disease: int,
    sim_days: int,
    window_size: int,
    horizon_days: int,
    flare_horizon_days: int,
    base_seed: int,
    split_ratios: tuple[float, float, float],
    split_seed: int,
    cache_dir: Path | None = None,
) -> DataBundle:
    """Generate cohorts, window them, split by patient, fit scaler on train only."""
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1: build per-disease frames and collect union schema + per-disease one-hot
    per_disease_frames: list[tuple[str, "object"]] = []  # (disease_id, DataFrame)
    union_feats: list[str] = []
    seen = set()

    for did in diseases:
        cfg = load_disease(did)
        cohort: Cohort = generate_cohort(
            cfg, n_patients_per_disease, sim_days, base_seed=base_seed
        )
        df = build_patient_frame(cohort, cfg)
        per_disease_frames.append((did, df))
        for c in feature_columns(df):
            if c not in seen:
                seen.add(c)
                union_feats.append(c)

    # add a disease-id one-hot so the model knows which disease this window is from
    disease_onehot_cols = [f"is_{d}" for d in diseases]
    for col in disease_onehot_cols:
        if col not in seen:
            seen.add(col)
            union_feats.append(col)

    # Pass 2: pad each frame to union schema and window
    all_X, all_yr, all_yc, all_pid = [], [], [], []
    for did, df in per_disease_frames:
        for col in union_feats:
            if col not in df.columns:
                df[col] = 0.0
        df[f"is_{did}"] = 1.0
        df = df[["patient_id", "day", "in_flare", "disease_id"] + union_feats]

        X, yr, yc, pids = make_windows(
            df, window_size, horizon_days, flare_horizon_days
        )
        pids = [f"{did}::{p}" for p in pids]
        all_X.append(X)
        all_yr.append(yr)
        all_yc.append(yc)
        all_pid.extend(pids)

    feature_names = union_feats
    X = np.concatenate(all_X, axis=0)
    y_reg = np.concatenate(all_yr, axis=0)
    y_cls = np.concatenate(all_yc, axis=0)

    splits = _split_patients(all_pid, split_ratios, split_seed)

    masks = {
        name: np.array([pid in pset for pid in all_pid])
        for name, pset in splits.items()
    }

    # fit standardizer on TRAIN ONLY (per feature, over N*T)
    Xtr = X[masks["train"]]
    flat = Xtr.reshape(-1, Xtr.shape[-1])
    mu = flat.mean(axis=0)
    sigma = flat.std(axis=0)
    sigma[sigma < 1e-6] = 1.0  # avoid div-by-zero on constant cols

    def _apply(arr: np.ndarray) -> np.ndarray:
        return ((arr - mu) / sigma).astype(np.float32)

    def _split(name: str) -> WindowSplit:
        idx = masks[name]
        return WindowSplit(
            X=_apply(X[idx]),
            y_reg=y_reg[idx],
            y_cls=y_cls[idx],
            patient_ids=[p for p, keep in zip(all_pid, idx) if keep],
        )

    bundle = DataBundle(
        train=_split("train"),
        val=_split("val"),
        test=_split("test"),
        feature_names=list(feature_names),
        scaler_mean=mu.astype(np.float32),
        scaler_std=sigma.astype(np.float32),
        disease_ids=list(diseases),
    )

    if cache_dir is not None:
        np.savez_compressed(
            cache_dir / "bundle.npz",
            Xtr=bundle.train.X, yrtr=bundle.train.y_reg, yctr=bundle.train.y_cls,
            Xva=bundle.val.X, yrva=bundle.val.y_reg, ycva=bundle.val.y_cls,
            Xte=bundle.test.X, yrte=bundle.test.y_reg, ycte=bundle.test.y_cls,
            mu=bundle.scaler_mean, sigma=bundle.scaler_std,
            feature_names=np.array(bundle.feature_names),
        )

    return bundle


class WindowDataset(Dataset):
    """PyTorch Dataset over a WindowSplit."""

    def __init__(self, split: WindowSplit):
        self.X = torch.from_numpy(split.X)
        self.yr = torch.from_numpy(split.y_reg).float()
        self.yc = torch.from_numpy(split.y_cls).float()

    def __len__(self) -> int:
        return self.X.shape[0]

    def __getitem__(self, i: int):
        return self.X[i], self.yr[i], self.yc[i]
