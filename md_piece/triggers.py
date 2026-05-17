"""Trigger sampling, treatment assignment, comorbidity sampling.

v2: treatment parameters can be scalars or {mean, std, min, max} distributions,
and responder class + subtype + age modulate the realised effect_magnitude.
"""

from __future__ import annotations

import numpy as np

from md_piece.unpredictability import sample_param


def sample_triggers(
    disease_cfg,
    dt_days: float,
    rng: np.random.Generator,
) -> list[tuple[str, float, float]]:
    """Sample which trigger events fire in this timestep.

    Returns
    -------
    list of (trigger_id, duration_days, magnitude)
    """
    fired = []
    for trig in disease_cfg.triggers:
        p_step = trig["prob_per_day"] * dt_days
        if rng.random() < p_step:
            mag = float(rng.normal(trig["effect_mean"], trig["effect_sigma"]))
            mag = max(mag, 0.0)
            dur_lo, dur_hi = trig["duration_days"]
            dur = float(rng.uniform(dur_lo, dur_hi))
            fired.append((trig["id"], dur, mag))
    return fired


def assign_treatments(
    disease_cfg,
    sim_days: int,
    rng: np.random.Generator,
    *,
    effect_multiplier: float = 1.0,
    treatment_response_modifier: float = 1.0,
) -> list[dict]:
    """Decide which treatments a patient receives and realise distribution params.

    Parameters
    ----------
    effect_multiplier : float
        Responder-class multiplier on `effect_magnitude`.
    treatment_response_modifier : float
        Subtype × age modifier (multiplicative).
    """
    assigned: list[dict] = []
    max_start = max(1, int(sim_days * 0.2))
    for tx in disease_cfg.treatments:
        if rng.random() < tx["assignment_prob"]:
            record = dict(tx)
            # realise distribution-based params
            record["onset_days"] = sample_param(tx["onset_days"], rng)
            record["half_life_days"] = sample_param(tx["half_life_days"], rng)
            base_mag = sample_param(tx["effect_magnitude"], rng)
            record["effect_magnitude"] = max(
                0.0, base_mag * effect_multiplier * treatment_response_modifier
            )
            record["start_day"] = float(rng.uniform(0, max_start))
            assigned.append(record)
    return assigned


def assign_comorbidities(
    disease_cfg,
    rng: np.random.Generator,
) -> list[str]:
    """Sample comorbidity ids based on conditional probabilities."""
    return [
        c["id"]
        for c in disease_cfg.comorbidity
        if rng.random() < c["conditional_prob"]
    ]
