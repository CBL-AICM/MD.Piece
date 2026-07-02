"""Driver: build the patient population (L1 + L4) → DataFrame / patients.csv.

This is the first runnable slice of Phase 5. Later phases bolt the disease, friction,
usage, doctor, and evaluation engines onto this same seeded, patient-parallel scaffold.

Usage:
    python -m simulation.build_population              # full run from config
    python -m simulation.build_population --n 200      # quick smoke run
"""
from __future__ import annotations

import argparse

import pandas as pd

from simulation.common import (
    Config, OUTPUT_DIR, load_config, patient_seed_sequences, patient_rngs,
)
from simulation.patients import generate_patient
from simulation.persona_engine import assign_persona


def build_population(cfg: Config, n: int | None = None) -> pd.DataFrame:
    n_patients = n if n is not None else cfg.n_patients
    seed_seqs = patient_seed_sequences(cfg.master_seed, n_patients)
    rows = []
    for i in range(n_patients):
        rngs = patient_rngs(seed_seqs[i], cfg.substreams)
        patient = generate_patient(i, rngs["demographics"], cfg)
        patient.persona = assign_persona(patient, rngs["persona"], cfg)
        rows.append(patient.to_dict())
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None, help="override patient count (smoke run)")
    ap.add_argument("--no-write", action="store_true", help="don't write files, just summarize")
    args = ap.parse_args()

    cfg = load_config()
    df = build_population(cfg, n=args.n)

    print(f"config_hash={cfg.config_hash}  patients={len(df)}")
    print("\ndisease mix (generated):")
    print((df["disease"].value_counts(normalize=True).round(3)).to_string())
    print("\npersona mix (generated):")
    print((df["persona"].value_counts(normalize=True).round(3)).to_string())
    # confound visibility: tech literacy by persona (adopter personas should skew high)
    print("\nmean tech_literacy by persona (confound check — adopters skew high):")
    print(df.groupby("persona")["tech_literacy"].mean().round(3).sort_values(ascending=False).to_string())

    if not args.no_write:
        out = OUTPUT_DIR / cfg.config_hash
        out.mkdir(parents=True, exist_ok=True)
        df.to_csv(out / "patients.csv", index=False)
        df.to_parquet(out / "patients.parquet", index=False)
        print(f"\nwrote {out / 'patients.csv'}")


if __name__ == "__main__":
    main()
