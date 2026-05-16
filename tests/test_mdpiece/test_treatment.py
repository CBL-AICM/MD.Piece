"""Test 3 — treatment effect direction."""

from __future__ import annotations

import numpy as np

from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease


def test_tnf_inhibitor_lowers_ra_das28():
    """Patients receiving TNF inhibitor should have lower mean DAS28 than non-receivers."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=120, sim_days=120, base_seed=5)

    with_tnf, without_tnf = [], []
    for p in cohort.patients:
        tx_ids = [t["id"] for t in p.treatments]
        mean_das = p.timeseries["das28"].mean()
        if "tnf_inhibitor" in tx_ids:
            with_tnf.append(mean_das)
        else:
            without_tnf.append(mean_das)

    # need at least a few patients in each arm
    assert len(with_tnf) >= 10 and len(without_tnf) >= 10, (
        f"insufficient arm sizes: tnf={len(with_tnf)} no={len(without_tnf)}"
    )
    diff = float(np.mean(without_tnf) - np.mean(with_tnf))
    assert diff > 0.05, (
        f"TNF inhibitor did not lower DAS28: with={np.mean(with_tnf):.2f} "
        f"without={np.mean(without_tnf):.2f}"
    )
