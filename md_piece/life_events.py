"""Stochastic life events (unpredictability source #5).

Generates a timeline of events for one patient: infection, surgery, pregnancy,
menstruation, travel, seasonal change, etc.  Each event maps to a transient
activity bump via the existing trigger machinery.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class LifeEvent:
    """A scheduled event for one patient.

    onset_day      : day the event begins.
    duration_days  : days until the bump ends.
    activity_bump  : signed shift added to target activity (negative = improves).
    id             : event identifier.
    """
    id: str
    onset_day: float
    duration_days: float
    activity_bump: float


def _eligible(event_cfg: dict, age: int, sex: str) -> bool:
    """Apply age_range / sex_filter gates from YAML."""
    if "age_range" in event_cfg:
        lo, hi = event_cfg["age_range"]
        if not (lo <= age <= hi):
            return False
    if "sex_filter" in event_cfg and event_cfg["sex_filter"] != sex:
        return False
    return True


def schedule_life_events(
    life_events_cfg: list[dict],
    sim_days: int,
    age: int,
    sex: str,
    rng: np.random.Generator,
) -> list[LifeEvent]:
    """Return a list of events that occur within [0, sim_days)."""
    out: list[LifeEvent] = []
    if not life_events_cfg:
        return out

    horizon_years = sim_days / 365.0
    for cfg in life_events_cfg:
        if not _eligible(cfg, age, sex):
            continue
        rate = float(cfg["prob_per_year"]) * horizon_years
        n = int(rng.poisson(rate))
        for _ in range(n):
            onset = float(rng.uniform(0, sim_days))
            d_lo, d_hi = cfg["duration_days"]
            dur = float(rng.uniform(d_lo, d_hi)) if d_hi > d_lo else float(d_lo)
            out.append(LifeEvent(
                id=cfg["id"],
                onset_day=onset,
                duration_days=dur,
                activity_bump=float(cfg["activity_bump"]),
            ))
    out.sort(key=lambda e: e.onset_day)
    return out


def active_events_at(events: list[LifeEvent], t_days: float) -> list[LifeEvent]:
    """Return events whose [onset, onset+duration) window contains t_days."""
    return [e for e in events
            if e.onset_day <= t_days < e.onset_day + e.duration_days]
