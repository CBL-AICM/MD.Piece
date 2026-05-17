"""Trigger sampling, treatment assignment, comorbidity sampling.

v2.5 — supports per-patient social-profile modifiers:
  - trigger_amplification:  multiplies a trigger's prob_per_day
  - treatment_access:       multiplies assignment_prob by drug class
  - effect_multiplier:      from responder class
  - treatment_response_modifier: subtype × age
"""

from __future__ import annotations

import numpy as np

from md_piece.unpredictability import sample_param


def sample_triggers(
    disease_cfg,
    dt_days: float,
    rng: np.random.Generator,
    *,
    trigger_amplification: dict | None = None,
) -> list[tuple[str, float, float]]:
    """Sample which trigger events fire this step.

    trigger_amplification: dict of {trigger_id: multiplier} from social profile.
    """
    fired = []
    amp_map = trigger_amplification or {}
    for trig in disease_cfg.triggers:
        amp = float(amp_map.get(trig["id"], 1.0))
        p_step = trig["prob_per_day"] * amp * dt_days
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
    treatment_access: dict | None = None,
) -> list[dict]:
    """Assign treatments, applying responder + subtype + social access modifiers.

    treatment_access: dict of {drug_class: multiplier} to throttle expensive
    or hard-to-access therapies for low-income / rural / low-literacy patients.
    """
    assigned: list[dict] = []
    access_map = treatment_access or {}
    max_start = max(1, int(sim_days * 0.2))
    for tx in disease_cfg.treatments:
        access_mult = float(access_map.get(tx.get("class", ""), 1.0))
        eff_p = tx["assignment_prob"] * access_mult
        if rng.random() < eff_p:
            record = dict(tx)
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
