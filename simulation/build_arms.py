"""Driver: build all three record arms (GROUND_TRUTH, PATIENT_RECALL, MDPIECE).

Surfaces the headline research signal — per-persona event recall rate, MDPIECE vs RECALL —
so the crossover (H2: app helps some personas, harms others) is visible before the full
evaluation engine exists.

Usage:
    python -m simulation.build_arms --n 600              # smoke run + signal table
    python -m simulation.build_arms --n 600 --parity     # V-SANITY: effect should vanish
"""
from __future__ import annotations

import argparse

import pandas as pd

from simulation.common import Config, load_config, patient_seed_sequences, patient_rngs
from simulation.patients import generate_patient
from simulation.persona_engine import assign_persona, persona_params
from simulation.disease_engine import simulate_ground_truth
from simulation.usage_engine import usage_trajectory
from simulation.friction_engine import recall_observer, mdpiece_observer


def build_arms(cfg: Config, n: int | None = None, parity: bool = False):
    n_patients = n if n is not None else cfg.n_patients
    seeds = patient_seed_sequences(cfg.master_seed, n_patients)
    prows, truth, recall, mdp = [], [], [], []
    for i in range(n_patients):
        rngs = patient_rngs(seeds[i], cfg.substreams)
        p = generate_patient(i, rngs["demographics"], cfg)
        p.persona = assign_persona(p, rngs["persona"], cfg)
        pp = persona_params(p.persona, cfg)
        ev = simulate_ground_truth(p, rngs, cfg)
        usage = usage_trajectory(p, pp, ev, rngs["usage"], cfg)
        rec = recall_observer(ev, p, pp, rngs["recall"], cfg)
        md = mdpiece_observer(ev, p, pp, usage, rngs["mdpiece"], cfg, parity=parity)
        prows.append(p.to_dict())
        truth.extend(e.to_dict() for e in ev)
        recall.extend(e.to_dict() for e in rec)
        mdp.extend(e.to_dict() for e in md)
    return (pd.DataFrame(prows), pd.DataFrame(truth),
            pd.DataFrame(recall), pd.DataFrame(mdp))


def event_recall_rate(patients: pd.DataFrame, truth: pd.DataFrame, arm: pd.DataFrame) -> pd.Series:
    """Per-patient sensitivity: distinct true events captured / total true events."""
    tc = truth.groupby("patient_id").size()
    matched = arm.dropna(subset=["true_event_id"]).groupby("patient_id")["true_event_id"].nunique()
    return (matched / tc).reindex(patients["patient_id"]).fillna(0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--parity", action="store_true", help="V-SANITY: mdpiece reduced to recall")
    args = ap.parse_args()

    cfg = load_config()
    patients, truth, recall, mdp = build_arms(cfg, n=args.n, parity=args.parity)

    rr_recall = event_recall_rate(patients, truth, recall)
    rr_mdp = event_recall_rate(patients, truth, mdp)
    df = patients.assign(recall=rr_recall.values, mdpiece=rr_mdp.values)
    df["delta"] = df["mdpiece"] - df["recall"]

    mode = "PARITY (mdpiece==recall; delta should be ~0)" if args.parity else "PROSPECTIVE"
    print(f"config_hash={cfg.config_hash}  n={len(patients)}  mode={mode}")
    print(f"truth_events={len(truth)} recall_events={len(recall)} mdpiece_events={len(mdp)}")
    print(f"\nOVERALL event recall rate:  recall={df['recall'].mean():.3f}  "
          f"mdpiece={df['mdpiece'].mean():.3f}  delta={df['delta'].mean():+.3f}")

    print("\nBy persona (the crossover — H2):")
    g = df.groupby("persona")[["recall", "mdpiece", "delta"]].mean().round(3)
    g["n"] = df.groupby("persona").size()
    print(g.sort_values("delta", ascending=False).to_string())


if __name__ == "__main__":
    main()
