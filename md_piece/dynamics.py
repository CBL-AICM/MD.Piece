"""Generic ODE engine for three dynamics types — v2.

Master equation:
    dI/dt = -k * (I - target(t))
    target(t) = baseline
              + sum(trigger_magnitudes)             # transient
              - sum(treatment_effects * dose)       # adherence-aware
              + sum(life_event_bumps)               # stochastic life events
              + long_tail_bump(t)                   # rare severe flare
              + circadian(t)
              + age_modifier * (I - baseline)       # young = amplified
    dI += noise * sqrt(dt)
    [ dB/dt = rate * max(I-baseline,0) * subtype_mult * antifibrotic_slow ]
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class DynamicsState:
    """Per-timestep state."""
    activity: float
    irreversible_burden: float = 0.0
    active_triggers: list[tuple[str, float, float]] = field(default_factory=list)
    active_treatments: list[dict] = field(default_factory=list)


def _circadian(t_hours: float, amplitude: float, phase_hours: float) -> float:
    return amplitude * np.sin(2.0 * np.pi * (t_hours - phase_hours) / 24.0)


def _treatment_effect(tx: dict, t_days: float) -> float:
    """Ramp + exponential decay, modulated by today's dose_multiplier."""
    start = tx["start_day"]
    if t_days < start:
        return 0.0
    elapsed = t_days - start
    onset = max(tx["onset_days"], 1e-3)
    ramp = min(1.0, elapsed / onset)
    half_life = max(tx["half_life_days"], 1e-3)
    decay = 0.5 ** ((elapsed - onset) / half_life) if elapsed > onset else 1.0
    dose = float(tx.get("dose_multiplier_today", 1.0))
    return tx["effect_magnitude"] * ramp * decay * dose


def step_dynamics(
    state: DynamicsState,
    *,
    disease_cfg,
    t_days: float,
    dt_days: float,
    rng: np.random.Generator,
    life_event_bump: float = 0.0,
    long_tail_bump: float = 0.0,
    age_severity_multiplier: float = 1.0,
) -> DynamicsState:
    """Advance state by one integration step (v2 — age + life events aware)."""
    baseline = disease_cfg.baseline["activity"]
    lo, hi = disease_cfg.baseline["range"]
    k = disease_cfg.decay["k"]
    k_per_day = k * 24.0 if disease_cfg.time_unit == "hour" else k

    trigger_sum = sum(mag for _id, _t, mag in state.active_triggers)
    tx_sum = sum(_treatment_effect(tx, t_days) for tx in state.active_treatments)

    t_hours = (t_days * 24.0) % 24.0
    circ = _circadian(
        t_hours,
        disease_cfg.circadian["amplitude"],
        disease_cfg.circadian["phase_hours"],
    )

    target = (
        baseline
        + trigger_sum
        - tx_sum
        + life_event_bump
        + long_tail_bump
        + circ
    )
    # age severity: young patients amplify deviation from baseline
    if age_severity_multiplier != 1.0:
        target = baseline + (target - baseline) * age_severity_multiplier

    noise = rng.normal(0.0, disease_cfg.noise["sigma"]) * np.sqrt(max(dt_days, 1e-6))
    dI = -k_per_day * (state.activity - target) * dt_days + noise
    new_activity = float(np.clip(state.activity + dI, lo, hi))

    new_burden = state.irreversible_burden
    if disease_cfg.dynamics_type == "progressive" and disease_cfg.accumulation:
        acc_rate = disease_cfg.accumulation["rate_per_unit_activity"]
        sat = disease_cfg.accumulation.get("saturation", float("inf"))
        slowdown = 1.0
        for tx in state.active_treatments:
            if tx.get("accumulation_slowdown") and t_days >= tx["start_day"]:
                slowdown *= (1.0 - tx["accumulation_slowdown"])
        # patient-specific subtype rate multiplier (set on patient)
        subtype_mult = float(state.__dict__.get("_acc_subtype_mult", 1.0))
        dB = (
            acc_rate
            * max(state.activity - baseline, 0.0)
            * dt_days * slowdown * subtype_mult
        )
        new_burden = float(min(state.irreversible_burden + dB, sat))

    updated_triggers = [
        (tid, t_left - dt_days, mag)
        for (tid, t_left, mag) in state.active_triggers
        if (t_left - dt_days) > 0
    ]

    new_state = DynamicsState(
        activity=new_activity,
        irreversible_burden=new_burden,
        active_triggers=updated_triggers,
        active_treatments=state.active_treatments,
    )
    # propagate subtype mult through new state for the next step
    if "_acc_subtype_mult" in state.__dict__:
        new_state._acc_subtype_mult = state._acc_subtype_mult
    return new_state
