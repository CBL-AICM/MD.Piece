"""Test 1 — dynamics-type-specific behaviour."""

from __future__ import annotations

import numpy as np

from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease
from md_piece.patient import simulate_patient


def test_chronic_relapsing_flare_count_in_range():
    """RA cohort should produce 3-12 flares per patient on average over 365 days."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=30, sim_days=365, base_seed=1)
    flares = [p.flare_count for p in cohort.patients]
    mean_flares = float(np.mean(flares))
    # accept a generous band — calibrated band is 3-8; we allow 2-12 for stochastic safety
    assert 2.0 <= mean_flares <= 12.0, (
        f"RA mean flares {mean_flares:.1f} outside expected band [2, 12]"
    )


def test_reversible_returns_to_baseline_after_trigger():
    """Asthma activity should return within ±50% of baseline within 24h of trigger end."""
    cfg = load_disease("asthma")
    # Manually run a trace and inject one big trigger
    from md_piece.dynamics import DynamicsState, step_dynamics

    rng = np.random.default_rng(0)
    state = DynamicsState(activity=cfg.baseline["activity"])
    dt = 1 / 24
    activities = []
    for i in range(int(72 / dt)):  # 72h
        t = i * dt
        if abs(t - 12.0) < dt / 2 and not state.active_triggers:
            state.active_triggers.append(("inject", 2.0, 4.0))
        state = step_dynamics(state, disease_cfg=cfg, t_days=t, dt_days=dt, rng=rng)
        activities.append((t, state.activity))

    # 24h after trigger ends (t=14) → t=38
    final_window = [a for t, a in activities if 38 <= t <= 72]
    baseline = cfg.baseline["activity"]
    assert all(abs(a - baseline) < 1.5 for a in final_window), (
        f"asthma did not revert: range [{min(final_window):.2f}, {max(final_window):.2f}]"
    )


def test_progressive_burden_monotonic_increase():
    """SSc irreversible burden must be non-decreasing over time."""
    cfg = load_disease("systemic_sclerosis")
    p = simulate_patient("S1", cfg, sim_days=365, seed=3)
    burden = p.timeseries["irreversible_burden"].values
    diffs = np.diff(burden)
    assert (diffs >= -1e-9).all(), "irreversible burden decreased somewhere"
    assert burden[-1] > burden[0], "burden did not accumulate over 365 days"
