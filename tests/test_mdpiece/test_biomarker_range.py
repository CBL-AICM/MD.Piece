"""Test 4 — biomarkers stay inside YAML-specified ranges."""

from __future__ import annotations

from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import list_diseases, load_disease


def test_all_biomarkers_within_range():
    """For every disease, no biomarker value should leave [range_min, range_max]."""
    for did in list_diseases():
        cfg = load_disease(did)
        cohort = generate_cohort(cfg, n_patients=30, sim_days=90, base_seed=7)
        df = cohort.to_dataframe()
        for name, spec in cfg.biomarkers.items():
            lo, hi = spec["range"]
            col = df[name]
            assert col.min() >= lo - 1e-6, (
                f"{did}.{name} below range: min={col.min()} < {lo}"
            )
            assert col.max() <= hi + 1e-6, (
                f"{did}.{name} above range: max={col.max()} > {hi}"
            )
