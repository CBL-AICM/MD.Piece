"""MD. Piece one-shot demo.

Generates 100 patients * 90 days for all three reference diseases,
writes timeseries CSVs and validation figures into output/mdpiece/.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import list_diseases, load_disease
from md_piece.visualize import (
    plot_cohort_overlay,
    plot_flare_distribution,
    plot_single_patient,
)

OUT_DIR = Path("output/mdpiece")


def run(n_patients: int = 100, sim_days: int = 90, base_seed: int = 42) -> None:
    """Simulate all available diseases and dump artifacts."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    diseases = list_diseases()
    print(f"[MD.Piece] generating {n_patients} patients x {sim_days} days "
          f"for {len(diseases)} disease(s): {diseases}")

    for did in diseases:
        t0 = time.time()
        cfg = load_disease(did)
        cohort = generate_cohort(cfg, n_patients, sim_days, base_seed=base_seed)
        dt = time.time() - t0

        ts = cohort.to_dataframe()
        meta = cohort.metadata_dataframe()
        ts.to_csv(OUT_DIR / f"{did}_timeseries.csv", index=False)
        meta.to_csv(OUT_DIR / f"{did}_metadata.csv", index=False)

        plot_single_patient(cohort.patients[0], OUT_DIR / f"{did}_single.png")
        plot_cohort_overlay(cohort, OUT_DIR / f"{did}_cohort.png")
        plot_flare_distribution(cohort, OUT_DIR / f"{did}_flares.png")

        print(f"  {did:25s} | t={dt:5.1f}s | rows={len(ts):6d} | "
              f"flares mean={meta.flare_count.mean():.2f}")

    print(f"[MD.Piece] done. Artifacts in {OUT_DIR.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100, help="patients per disease")
    parser.add_argument("--days", type=int, default=90, help="simulation days")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(n_patients=args.n, sim_days=args.days, base_seed=args.seed)
