"""Test 2 — comorbidity sampling consistency."""

from __future__ import annotations

from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease


def test_ra_comorbidity_rates_within_tolerance():
    """Empirical comorbidity rates in a large RA cohort should match YAML ± 10 pp."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=300, sim_days=30, base_seed=99)
    target = {c["id"]: c["conditional_prob"] for c in cfg.comorbidity}

    counts = {cid: 0 for cid in target}
    for p in cohort.patients:
        for cid in p.comorbidities:
            counts[cid] = counts.get(cid, 0) + 1
    rates = {cid: counts[cid] / len(cohort.patients) for cid in target}

    for cid, expected in target.items():
        delta = abs(rates[cid] - expected)
        assert delta <= 0.10, (
            f"comorbidity '{cid}' empirical={rates[cid]:.2f} expected={expected:.2f} delta={delta:.2f}"
        )
