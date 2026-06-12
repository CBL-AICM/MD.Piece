"""Per-patient fidelity metrics for one record arm vs ground truth (arch §8).

Linkage via true_event_id (arch §6.2): a ground-truth event is a true-positive if some arm row
links to it; a ground-truth event with no link is an omission (FN); an arm row with no link is a
fabrication (FP). Everything is vectorized over patients; only Kendall's τ loops (small groups).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from simulation.common import Config


def arm_metrics(patients: pd.DataFrame, truth: pd.DataFrame, arm: pd.DataFrame,
                cfg: Config) -> pd.DataFrame:
    pid = patients["patient_id"]
    grading = cfg.probability_registry["friction"]["recall"]["med_recall_grading"]

    # one arm row per captured truth event (a true event is matched at most once)
    am = (arm.dropna(subset=["true_event_id"])
          .sort_values("event_id")
          .drop_duplicates(["patient_id", "true_event_id"])
          [["patient_id", "true_event_id", "severity_recorded",
            "medication", "dose", "frequency", "temporal_error_days"]]
          .rename(columns={"severity_recorded": "sev_rec", "medication": "med_rec",
                           "dose": "dose_rec", "frequency": "freq_rec",
                           "temporal_error_days": "terr"}))

    m = truth.merge(am, left_on=["patient_id", "event_id"],
                    right_on=["patient_id", "true_event_id"], how="left",
                    suffixes=("", "_am"))
    m["captured"] = m["true_event_id_am"].notna() if "true_event_id_am" in m else m["true_event_id"].notna()

    m["sal_cap"] = m["salience"] * m["captured"]
    m["tl"] = np.where(m["captured"], np.clip(1.0 - m["terr"].abs() / 30.0, 0.0, 1.0), np.nan)
    has_sev = m["severity_true"].notna()
    m["sev_err"] = np.where(m["captured"] & has_sev, (m["sev_rec"] != m["severity_true"]), np.nan)

    g = m.groupby("patient_id")
    n_truth = g.size()
    tp = g["captured"].sum()
    out = pd.DataFrame(index=pid)
    out["event_recall_rate"] = (tp / n_truth).reindex(pid).fillna(0.0).values
    out["information_completeness"] = (g["sal_cap"].sum() / g["salience"].sum()).reindex(pid).fillna(0.0).values
    out["timeline_accuracy"] = g["tl"].mean().reindex(pid).fillna(0.0).values
    out["severity_error_rate"] = g["sev_err"].mean().reindex(pid).fillna(0.0).values

    # medication accuracy (graded: drug > dose > frequency), over truth med-events
    mt = m[m["medication"].notna()].copy()
    if len(mt):
        drug_ok = (mt["med_rec"] == mt["medication"]) & mt["captured"]
        dose_ok = (mt["dose_rec"] == mt["dose"]) & mt["dose"].notna() & mt["captured"]
        freq_ok = (mt["freq_rec"] == mt["frequency"]) & mt["frequency"].notna() & mt["captured"]
        mt["mscore"] = (grading["drug"] * drug_ok + grading["dose"] * dose_ok
                        + grading["frequency"] * freq_ok)
        med_acc = mt.groupby("patient_id")["mscore"].mean()
    else:
        med_acc = pd.Series(dtype=float)
    out["medication_recall_accuracy"] = med_acc.reindex(pid).fillna(1.0).values  # no med events => no med loss

    # precision / F1 (fabrications guard against false-logging "wins")
    fp = arm[arm["is_false"]].groupby("patient_id").size().reindex(pid).fillna(0.0)
    tp_p = tp.reindex(pid).fillna(0.0)
    denom = (tp_p + fp).replace(0, np.nan)
    out["precision"] = (tp_p / denom).fillna(0.0).values
    rsum = out["event_recall_rate"] + out["precision"]
    out["f1"] = np.where(rsum > 0, 2 * out["event_recall_rate"] * out["precision"] / np.where(rsum > 0, rsum, 1), 0.0)

    # Kendall τ on event ordering among captured events (clinical sequence preservation)
    taus = {}
    for p, gg in m[m["captured"]].groupby("patient_id"):
        if len(gg) >= 3 and gg["terr"].abs().sum() > 0:
            t = kendalltau(gg["event_date_true"], gg["event_date_true"] + gg["terr"]).correlation
            taus[p] = 1.0 if np.isnan(t) else t
        else:
            taus[p] = 1.0
    out["ordering_tau"] = pd.Series(taus).reindex(pid).fillna(1.0).values

    # composite data-fidelity headline
    out["clinical_reconstruction_score"] = out[[
        "information_completeness", "event_recall_rate",
        "medication_recall_accuracy", "timeline_accuracy"]].mean(axis=1).values

    # signal-to-noise of the arm's record (salience-weighted) — fed to the doctor engine
    snr = arm.groupby("patient_id")["salience"].mean().reindex(pid).fillna(0.0)
    out["snr"] = snr.values
    out["n_arm_events"] = arm.groupby("patient_id").size().reindex(pid).fillna(0).astype(int).values

    out.insert(0, "patient_id", pid.values)
    return out.reset_index(drop=True)
