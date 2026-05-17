"""MD. Piece v2 — one-shot demo.

Simulates all available diseases and emits:
  - per-disease CSVs              (output/mdpiece/*.csv)
  - per-disease validation figures (output/mdpiece/*.png)
  - cohort.json for the PWA       (pwa/data/cohort.json)
"""

from __future__ import annotations

import argparse
import json
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
PWA_DATA = Path("pwa/data")


def _patient_to_json(p) -> dict:
    """Serialize one Patient to a json-friendly dict for the PWA."""
    df = p.timeseries
    return {
        "patient_id": p.patient_id,
        "disease_id": p.disease_id,
        "age": p.age,
        "sex": p.sex,
        "age_bin": p.age_profile.age_bin if p.age_profile else "",
        "is_elderly": bool(p.age_profile.is_elderly) if p.age_profile else False,
        "subtype": p.subtype,
        "responder_class": p.responder_class,
        "placebo_shift": p.placebo_shift,
        "comorbidities": p.comorbidities,
        "treatments": [
            {"id": t["id"], "start_day": t.get("start_day"),
             "effect_magnitude": t["effect_magnitude"]}
            for t in p.treatments
        ],
        "life_events": [
            {"id": e.id, "onset_day": e.onset_day,
             "duration_days": e.duration_days, "activity_bump": e.activity_bump}
            for e in p.life_events
        ],
        "long_tail_event": p.long_tail_event,
        "flare_count": p.flare_count,
        "timeseries": df.to_dict(orient="records"),
    }


def run(n_patients: int = 100, sim_days: int = 90, base_seed: int = 42) -> None:
    """Simulate every disease, write artifacts + PWA data."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PWA_DATA.mkdir(parents=True, exist_ok=True)

    diseases = list_diseases()
    print(f"[MD.Piece v2] generating {n_patients} patients x {sim_days} days "
          f"for {len(diseases)} disease(s): {diseases}")

    cohort_json = {
        "version": "2.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": {"n_patients": n_patients, "sim_days": sim_days, "seed": base_seed},
        "diseases": {},
    }

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

        cohort_json["diseases"][did] = {
            "name": cfg.name,
            "dynamics_type": cfg.dynamics_type,
            "patients": [_patient_to_json(p) for p in cohort.patients],
        }

        elderly = sum(1 for p in cohort.patients
                      if p.age_profile and p.age_profile.is_elderly)
        print(f"  {did:25s} | t={dt:5.1f}s | rows={len(ts):6d} | "
              f"flares mean={meta.flare_count.mean():.2f} | elderly={elderly}/{n_patients}")

    out_json = PWA_DATA / "cohort.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(cohort_json, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = out_json.stat().st_size / 1024 / 1024
    print(f"[MD.Piece v2] PWA data -> {out_json} ({size_mb:.1f} MB)")
    print(f"[MD.Piece v2] artifacts in {OUT_DIR.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100, help="patients per disease")
    parser.add_argument("--days", type=int, default=90, help="simulation days")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(n_patients=args.n, sim_days=args.days, base_seed=args.seed)
