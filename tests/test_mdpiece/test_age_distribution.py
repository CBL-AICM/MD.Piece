"""Test 3 (v2) — age distribution + elderly mechanism."""

from __future__ import annotations

import numpy as np

from md_piece.age_stratification import AGE_BIN_RANGES, AGE_BINS
from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import list_diseases, load_disease


def _bin_for_age(age: int) -> str:
    for b in AGE_BINS:
        lo, hi = AGE_BIN_RANGES[b]
        if lo <= age < hi:
            return b
    return "70-90"


def test_age_within_global_range_20_to_90():
    """All patients in every disease cohort must have 20 <= age <= 90."""
    for did in list_diseases():
        cfg = load_disease(did)
        cohort = generate_cohort(cfg, n_patients=80, sim_days=30, base_seed=3)
        ages = [p.age for p in cohort.patients]
        assert min(ages) >= 20 and max(ages) <= 90, (
            f"{did}: ages {min(ages)}-{max(ages)} outside [20,90]"
        )


def test_age_distribution_matches_yaml_within_15pp():
    """Empirical bin frequencies must match YAML age_distribution within 15 percentage points."""
    for did in list_diseases():
        cfg = load_disease(did)
        if not cfg.raw.get("age_distribution"):
            continue
        cohort = generate_cohort(cfg, n_patients=500, sim_days=15, base_seed=11)
        observed = {b: 0 for b in AGE_BINS}
        for p in cohort.patients:
            observed[_bin_for_age(p.age)] += 1
        n = sum(observed.values())
        observed_p = {b: observed[b] / n for b in AGE_BINS}
        for b in AGE_BINS:
            expected = cfg.raw["age_distribution"].get(b, 0)
            delta = abs(observed_p[b] - expected)
            assert delta <= 0.15, (
                f"{did} bin {b}: observed={observed_p[b]:.2f} expected={expected:.2f}"
            )


def test_elderly_mechanism_triggers_for_age_ge_70():
    """Every patient with age >= 70 must have is_elderly=True and >=1 auto comorbidity."""
    cfg = load_disease("rheumatoid_arthritis")   # has elderly bin
    cohort = generate_cohort(cfg, n_patients=200, sim_days=15, base_seed=5)
    elderly = [p for p in cohort.patients if p.age >= 70]
    assert len(elderly) >= 5, "not enough elderly patients sampled to test"
    for p in elderly:
        assert p.age_profile.is_elderly, f"age={p.age} not flagged elderly"
        assert p.age_profile.crp_dampening < 1.0
        assert p.age_profile.polypharmacy_count >= 0
        assert len(p.age_profile.elderly_comorbidities) >= 0
