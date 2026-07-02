"""L6 usage/retention tests. Verify the mechanisms that make MD.Piece lossy (Rule 9)."""
from __future__ import annotations

import numpy as np
import pytest

from simulation.common import load_config, patient_seed_sequences, patient_rngs
from simulation.patients import generate_patient
from simulation.persona_engine import assign_persona, persona_params
from simulation.disease_engine import simulate_ground_truth
from simulation.usage_engine import usage_trajectory


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _trajectories(cfg, n=1200):
    seeds = patient_seed_sequences(cfg.master_seed, n)
    rows = []
    for i in range(n):
        rngs = patient_rngs(seeds[i], cfg.substreams)
        p = generate_patient(i, rngs["demographics"], cfg)
        p.persona = assign_persona(p, rngs["persona"], cfg)
        pp = persona_params(p.persona, cfg)
        ev = simulate_ground_truth(p, rngs, cfg)
        u = usage_trajectory(p, pp, ev, rngs["usage"], cfg)
        rows.append((p.persona, u.onboarded, float(u.engagement_gate.mean()), u.median_lifetime))
    return rows


def test_usage_deterministic(cfg):
    a = _trajectories(cfg, n=80)
    b = _trajectories(cfg, n=80)
    assert a == b


def test_onboarding_scales_with_engagement(cfg):
    """Non-adoption is persona-dependent: power users almost always onboard; low-engagement
    personas often never adopt. If onboarding were uniform (the bug we fixed), this fails."""
    rows = _trajectories(cfg)
    import pandas as pd
    df = pd.DataFrame(rows, columns=["persona", "onboarded", "mean_gate", "median_life"])
    onb = df.groupby("persona")["onboarded"].mean()
    assert onb["PERFECT_LOGGER"] > onb["TECH_AVOIDANT"] + 0.2
    assert onb["PERFECT_LOGGER"] > onb["LOW_ENGAGEMENT"] + 0.2


def test_retention_orders_by_kappa(cfg):
    """Higher retention_kappa => longer realized engagement (mean gate over the year)."""
    rows = _trajectories(cfg)
    import pandas as pd
    df = pd.DataFrame(rows, columns=["persona", "onboarded", "mean_gate", "median_life"])
    adopters = df[df["onboarded"]]
    g = adopters.groupby("persona")["mean_gate"].mean()
    assert g["PERFECT_LOGGER"] > g["NORMAL"] > g["TECH_AVOIDANT"]


def test_flare_reengages_dropped_user(cfg):
    """A flare/ED/admission transiently re-activates a user who has otherwise dropped out."""
    seeds = patient_seed_sequences(cfg.master_seed, 400)
    found = False
    for i in range(400):
        rngs = patient_rngs(seeds[i], cfg.substreams)
        p = generate_patient(i, rngs["demographics"], cfg)
        p.persona = assign_persona(p, rngs["persona"], cfg)
        pp = persona_params(p.persona, cfg)
        ev = simulate_ground_truth(p, rngs, cfg)
        u = usage_trajectory(p, pp, ev, rngs["usage"], cfg)
        if not u.onboarded:
            continue
        # find a flare-like event occurring after the user's gate first hit zero
        zero_days = np.where(u.engagement_gate == 0.0)[0]
        if len(zero_days) == 0:
            continue
        first_zero = zero_days[0]
        for e in ev:
            if e.event_type in ("FLARE", "EMERGENCY_VISIT", "HOSPITALIZATION") and e.event_date_true > first_zero:
                if u.gate(e.event_date_true) > 0.0:
                    found = True
                    break
        if found:
            break
    assert found, "expected at least one flare to re-engage a dropped-out user"
