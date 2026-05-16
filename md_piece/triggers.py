"""Trigger sampling and treatment assignment."""

from __future__ import annotations

import numpy as np


def sample_triggers(
    disease_cfg,
    dt_days: float,
    rng: np.random.Generator,
) -> list[tuple[str, float, float]]:
    """Sample which trigger events fire in this timestep.

    Parameters
    ----------
    disease_cfg : DiseaseConfig
    dt_days : float
        Step size in days. Probabilities in YAML are per day, so we scale.
    rng : np.random.Generator

    Returns
    -------
    list of (trigger_id, duration_days, magnitude)
        Newly fired triggers to append to active list.
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
) -> list[dict]:
    """Decide which treatments this patient receives and when they start.

    Parameters
    ----------
    disease_cfg : DiseaseConfig
    sim_days : int
        Total simulation horizon — treatments start in first 20%.
    rng : np.random.Generator

    Returns
    -------
    list of dict
        Each treatment record with start_day and inherited YAML fields.
    """
    assigned = []
    max_start = max(1, int(sim_days * 0.2))
    for tx in disease_cfg.treatments:
        if rng.random() < tx["assignment_prob"]:
            record = dict(tx)
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
