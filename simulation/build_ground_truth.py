"""Driver: build patients (L1+L4) and simulate the GROUND_TRUTH event stream (L2+L3).

Usage:
    python -m simulation.build_ground_truth --n 300      # smoke run with summary
    python -m simulation.build_ground_truth              # full 3,200-patient run
"""
from __future__ import annotations

import argparse

import pandas as pd

from simulation.common import (
    Config, OUTPUT_DIR, load_config, patient_seed_sequences, patient_rngs,
)
from simulation.patients import generate_patient
from simulation.persona_engine import assign_persona
from simulation.disease_engine import simulate_ground_truth


def build_ground_truth(cfg: Config, n: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_patients = n if n is not None else cfg.n_patients
    seed_seqs = patient_seed_sequences(cfg.master_seed, n_patients)
    patient_rows, all_events = [], []
    for i in range(n_patients):
        rngs = patient_rngs(seed_seqs[i], cfg.substreams)
        patient = generate_patient(i, rngs["demographics"], cfg)
        patient.persona = assign_persona(patient, rngs["persona"], cfg)
        patient_rows.append(patient.to_dict())
        all_events.extend(ev.to_dict() for ev in simulate_ground_truth(patient, rngs, cfg))
    return pd.DataFrame(patient_rows), pd.DataFrame(all_events)


def _summary(patients: pd.DataFrame, events: pd.DataFrame, cfg: Config) -> None:
    n = len(patients)
    yrs = cfg.horizon_days / 365.0
    print(f"patients={n}  events={len(events)}  events/patient={len(events)/n:.1f}")

    print("\nevents by type:")
    print(events["event_type"].value_counts().to_string())

    # Face validity (V-FACE-1): simulated flare rate vs registry relapse_rate_yr
    flares = events[events["event_type"] == "FLARE"]
    per_pt = flares.groupby("patient_id").size().reindex(patients["patient_id"], fill_value=0)
    fr = patients.assign(flares=per_pt.values).groupby("disease")["flares"].mean() / yrs
    print("\nflares/patient-year  (simulated vs registry relapse_rate_yr):")
    for d in fr.index:
        target = cfg.disease_registry[d]["relapse_rate_yr"]
        print(f"  {d:6s} sim={fr[d]:.2f}  registry={target:.2f}")

    # Internal validity (V-INT-1): event load rises with baseline severity
    ec = events.groupby("patient_id").size().reindex(patients["patient_id"], fill_value=0)
    by_sev = patients.assign(n_events=ec.values).groupby("severity")["n_events"].mean()
    print("\nmean events by baseline severity (should increase monotonically):")
    print(by_sev.round(1).to_string())

    # ED utilization by clinic access (poor access -> more ED substitution)
    ed = events[events["event_type"] == "EMERGENCY_VISIT"]
    ed_pt = ed.groupby("patient_id").size().reindex(patients["patient_id"], fill_value=0)
    by_acc = patients.assign(ed=ed_pt.values).groupby("clinic_access")["ed"].mean()
    print("\nmean ED visits by clinic_access (0=poor..2=good):")
    print(by_acc.round(3).to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    patients, events = build_ground_truth(cfg, n=args.n)
    print(f"config_hash={cfg.config_hash}")
    _summary(patients, events, cfg)

    if not args.no_write:
        out = OUTPUT_DIR / cfg.config_hash
        out.mkdir(parents=True, exist_ok=True)
        patients.to_csv(out / "patients.csv", index=False)
        events.to_parquet(out / "ground_truth_events.parquet", index=False)
        events.to_csv(out / "ground_truth_events.csv", index=False)
        print(f"\nwrote {out}/ground_truth_events.parquet ({len(events)} rows)")


if __name__ == "__main__":
    main()
