"""Medication adherence modelling.

Three failure modes per patient per simulation:
  - daily miss      (random pill skip)
  - discontinuation (permanent stop sometime during sim)
  - dose self-adjust (random sub-/supra-therapeutic dose)
Implements unpredictability source #4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AdherenceState:
    """Per-treatment per-patient adherence record."""
    treatment_id: str
    daily_miss_prob: float
    discontinuation_day: float | None = None   # None = never discontinued
    dose_multiplier_today: float = 1.0
    daily_skips: list[int] = field(default_factory=list)
    self_adjustments: list[tuple[int, float]] = field(default_factory=list)


def build_adherence_states(
    treatments: list[dict],
    adherence_cfg: dict,
    sim_days: int,
    rng: np.random.Generator,
) -> dict[str, AdherenceState]:
    """One AdherenceState per assigned treatment.

    Parameters
    ----------
    treatments : list of dict
        Already-assigned treatments for one patient.
    adherence_cfg : dict
        YAML 'adherence' block (daily_miss_probability, discontinuation_probability_per_year,
        dose_self_adjustment_probability).
    sim_days : int
    rng : np.random.Generator
    """
    states = {}
    miss_p = float(adherence_cfg.get("daily_miss_probability", 0.0))
    disc_p_year = float(adherence_cfg.get("discontinuation_probability_per_year", 0.0))
    p_discont_in_sim = 1.0 - (1.0 - disc_p_year) ** (sim_days / 365.0)

    for tx in treatments:
        disc_day = None
        if rng.random() < p_discont_in_sim:
            # uniformly distributed within sim
            start = float(tx.get("start_day", 0))
            disc_day = float(rng.uniform(start, sim_days))
        states[tx["id"]] = AdherenceState(
            treatment_id=tx["id"],
            daily_miss_prob=miss_p,
            discontinuation_day=disc_day,
        )
    return states


def dose_multiplier(
    state: AdherenceState,
    t_days: float,
    adherence_cfg: dict,
    rng: np.random.Generator,
) -> float:
    """Return today's effective dose multiplier in [0, 1.5].

    Cases (independent per day):
      - past discontinuation_day  -> 0.0
      - random miss               -> 0.0
      - random self-adjustment    -> uniform(0.5, 1.5)
      - otherwise                 -> 1.0
    """
    if state.discontinuation_day is not None and t_days >= state.discontinuation_day:
        return 0.0
    if rng.random() < state.daily_miss_prob:
        state.daily_skips.append(int(t_days))
        return 0.0
    if rng.random() < float(adherence_cfg.get("dose_self_adjustment_probability", 0.0)):
        mult = float(rng.uniform(0.5, 1.5))
        state.self_adjustments.append((int(t_days), mult))
        return mult
    return 1.0
