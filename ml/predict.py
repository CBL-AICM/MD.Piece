"""Load a trained checkpoint and run inference.

Two entry points:
  1. predict_from_patient(patient) -> dict   # predict on a md_piece.Patient
  2. CLI: python -m ml.predict --disease rheumatoid_arthritis --seed 999
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch

from md_piece.cohort_generator import Cohort
from md_piece.disease_loader import load_disease
from md_piece.patient import Patient, simulate_patient

from ml.dataset import build_patient_frame
from ml.features import feature_columns, make_windows
from ml.model import MDPieceModel


def load_checkpoint(ckpt_path: Path, device: torch.device | None = None):
    """Load the saved best.pt and re-build the model.

    Returns
    -------
    (model, feature_names, mean, std, config)
    """
    device = device or torch.device("cpu")
    state = torch.load(ckpt_path, map_location=device, weights_only=False)
    cfg = state["config"]
    feature_names = state["feature_names"]
    mean = np.array(state["scaler_mean"], dtype=np.float32)
    std = np.array(state["scaler_std"], dtype=np.float32)

    model = MDPieceModel(
        n_features=len(feature_names),
        hidden=cfg["model"]["hidden"],
        n_layers=cfg["model"]["n_layers"],
        dropout=cfg["model"]["dropout"],
    ).to(device)
    model.load_state_dict(state["model_state"])
    model.eval()
    return model, feature_names, mean, std, cfg


def _patient_to_aligned_frame(patient: Patient, feature_names: list[str]):
    """Build a DataFrame matching the training schema (pad missing cols with 0)."""
    cfg = load_disease(patient.disease_id)
    one_cohort = Cohort(disease_id=cfg.id, patients=[patient])
    df = build_patient_frame(one_cohort, cfg)
    # add disease one-hot columns the trainer used
    for col in feature_names:
        if col not in df.columns:
            df[col] = 0.0
    df[f"is_{patient.disease_id}"] = 1.0
    df = df[["patient_id", "day", "in_flare", "disease_id"] + list(feature_names)]
    return df


def predict_from_patient(
    patient: Patient,
    ckpt_path: Path = Path("output/mdpiece/checkpoints/best.pt"),
) -> dict:
    """Run the trained model on every sliding window of one patient.

    Returns
    -------
    dict with arrays:
      day       — last day of each input window
      activity_pred / activity_true
      flare_prob / flare_true
    """
    model, feature_names, mean, std, cfg = load_checkpoint(ckpt_path)
    df = _patient_to_aligned_frame(patient, feature_names)

    X, yr, yc, _pids = make_windows(
        df,
        window_size=cfg["data"]["window_size"],
        horizon_days=cfg["data"]["horizon_days"],
        flare_horizon_days=cfg["data"]["flare_horizon_days"],
    )
    if len(X) == 0:
        raise ValueError("patient too short for one window+horizon")

    Xn = ((X - mean) / std).astype(np.float32)
    with torch.no_grad():
        reg, cls = model(torch.from_numpy(Xn))
        reg = reg.cpu().numpy()
        prob = torch.sigmoid(cls).cpu().numpy()

    win = cfg["data"]["window_size"]
    days = np.arange(win, win + len(reg))
    return {
        "day": days,
        "activity_pred": reg,
        "activity_true": yr,
        "flare_prob": prob,
        "flare_true": yc.astype(int),
    }


def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--disease", required=True,
                   choices=["rheumatoid_arthritis", "asthma", "systemic_sclerosis"])
    p.add_argument("--days", type=int, default=120)
    p.add_argument("--seed", type=int, default=999)
    p.add_argument("--ckpt", type=Path,
                   default=Path("output/mdpiece/checkpoints/best.pt"))
    args = p.parse_args()

    cfg = load_disease(args.disease)
    patient = simulate_patient("DEMO", cfg, sim_days=args.days, seed=args.seed)
    print(f"[predict] simulated {args.disease} patient (seed={args.seed})")
    print(f"          age={patient.age} sex={patient.sex} "
          f"treatments={[t['id'] for t in patient.treatments]}")

    res = predict_from_patient(patient, args.ckpt)
    mae = float(np.mean(np.abs(res["activity_pred"] - res["activity_true"])))
    if res["flare_true"].sum() > 0 and res["flare_true"].sum() < len(res["flare_true"]):
        from sklearn.metrics import roc_auc_score
        auroc = roc_auc_score(res["flare_true"], res["flare_prob"])
    else:
        auroc = float("nan")
    print(f"[predict] windows={len(res['day'])}  "
          f"activity MAE={mae:.3f}  flare AUROC={auroc:.3f}")
    print()
    print("first 10 predictions:")
    print(f"  {'day':>4s} {'act_pred':>10s} {'act_true':>10s} "
          f"{'flare_p':>9s} {'flare_t':>8s}")
    for i in range(min(10, len(res["day"]))):
        print(f"  {res['day'][i]:4d} {res['activity_pred'][i]:10.3f} "
              f"{res['activity_true'][i]:10.3f} {res['flare_prob'][i]:9.3f} "
              f"{res['flare_true'][i]:8d}")


if __name__ == "__main__":
    _cli()
