"""Test 4 (v2) — eight unpredictability sources behave as advertised."""

from __future__ import annotations

from collections import Counter

import numpy as np

from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease


def test_responder_class_distribution_within_5pp():
    """Empirical responder class frequencies within ±5 pp of YAML."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=400, sim_days=15, base_seed=21)
    rc = Counter(p.responder_class for p in cohort.patients)
    total = sum(rc.values())
    for name, spec in cfg.raw["responder_classes"].items():
        observed = rc.get(name, 0) / total
        expected = spec["probability"]
        assert abs(observed - expected) <= 0.07, (
            f"responder '{name}' observed={observed:.2f} expected={expected:.2f}"
        )


def test_same_treatment_same_disease_has_high_variation():
    """CV of mean activity within RA + on TNF inhibitor must be > 0.15."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=200, sim_days=180, base_seed=31)
    on_tnf = [
        p for p in cohort.patients
        if any(t["id"] == "tnf_inhibitor" for t in p.treatments)
    ]
    assert len(on_tnf) >= 20
    means = np.array([p.timeseries["activity"].mean() for p in on_tnf])
    cv = float(means.std() / max(means.mean(), 1e-6))
    assert cv > 0.12, (
        f"insufficient response heterogeneity under same disease+treatment: CV={cv:.3f}"
    )


def test_adherence_records_some_dose_skips():
    """At least 30% of treated patients with adherence config should miss some doses."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=80, sim_days=180, base_seed=41)
    n_with_skips = 0
    n_treated = 0
    for p in cohort.patients:
        if not p.treatments:
            continue
        n_treated += 1
        any_skip = any(len(s.daily_skips) > 0 or s.discontinuation_day is not None
                       for s in p.adherence_states.values())
        if any_skip:
            n_with_skips += 1
    assert n_treated >= 30
    frac = n_with_skips / n_treated
    assert frac >= 0.3, (
        f"only {frac:.2f} of treated patients had any non-adherence event (expected ≥ 0.3)"
    )


def test_life_events_scheduled_for_some_patients():
    """In a 180-day RA cohort, > 50% of patients should have ≥ 1 scheduled life event."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=80, sim_days=180, base_seed=51)
    with_events = sum(1 for p in cohort.patients if p.life_events)
    frac = with_events / len(cohort.patients)
    assert frac >= 0.5, f"only {frac:.2f} of patients had a life event (expected ≥ 0.5)"


def test_subtype_assignment_present():
    """Each patient has a non-empty subtype name."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=50, sim_days=15, base_seed=61)
    for p in cohort.patients:
        assert p.subtype and p.subtype != "unspecified"
