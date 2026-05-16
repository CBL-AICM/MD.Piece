"""Test 5 — same seed = same result, byte-for-byte."""

from __future__ import annotations

import numpy as np

from md_piece.disease_loader import list_diseases, load_disease
from md_piece.patient import simulate_patient


def test_identical_seed_identical_trajectory():
    """Running the same patient twice with the same seed must produce identical timeseries."""
    for did in list_diseases():
        cfg = load_disease(did)
        p1 = simulate_patient("rep", cfg, sim_days=60, seed=2024)
        p2 = simulate_patient("rep", cfg, sim_days=60, seed=2024)
        a1 = p1.timeseries["activity"].values
        a2 = p2.timeseries["activity"].values
        assert np.array_equal(a1, a2), f"{did}: trajectories diverged"
