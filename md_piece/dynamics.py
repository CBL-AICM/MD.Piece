"""Generic ODE engine for three dynamics types.

Master equation:
    dI/dt = -k*(I - baseline)
            + sum(active_trigger_effects)
            - sum(active_treatment_effects)
            + circadian(t)
            + noise(t)
            [ + dB/dt = rate * I    # progressive only ]
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class DynamicsState:
    """Per-timestep state of one patient.

    Attributes
    ----------
    activity : float
        Current immune-activity score (clipped to disease range).
    irreversible_burden : float
        Monotonically non-decreasing burden (progressive type only).
    active_triggers : list of (id, remaining_time, magnitude)
    active_treatments : list of (id, days_since_start, effect_curve_value)
    """

    activity: float
    irreversible_burden: float = 0.0
    active_triggers: list[tuple[str, float, float]] = field(default_factory=list)
    active_treatments: list[dict] = field(default_factory=list)


def _circadian(t_hours: float, amplitude: float, phase_hours: float) -> float:
    """Sinusoidal circadian modulation."""
    return amplitude * np.sin(2.0 * np.pi * (t_hours - phase_hours) / 24.0)


def _treatment_effect(tx: dict, t_days: float) -> float:
    """Time-dependent treatment magnitude with onset ramp + exponential decay."""
    start = tx["start_day"]
    if t_days < start:
        return 0.0
    elapsed = t_days - start
    onset = max(tx["onset_days"], 1e-3)
    ramp = min(1.0, elapsed / onset)
    half_life = max(tx["half_life_days"], 1e-3)
    decay = 0.5 ** ((elapsed - onset) / half_life) if elapsed > onset else 1.0
    return tx["effect_magnitude"] * ramp * decay


def step_dynamics(
    state: DynamicsState,
    *,
    disease_cfg,
    t_days: float,
    dt_days: float,
    rng: np.random.Generator,
) -> DynamicsState:
    """Advance state by one integration step.

    Parameters
    ----------
    state : DynamicsState
        Current state.
    disease_cfg : DiseaseConfig
        Loaded disease configuration.
    t_days : float
        Absolute simulation time in days.
    dt_days : float
        Step size in days (e.g. 1/24 for hourly).
    rng : np.random.Generator
        Per-patient RNG for reproducibility.

    Returns
    -------
    DynamicsState
        Updated state (new instance).
    """
    baseline = disease_cfg.baseline["activity"]
    lo, hi = disease_cfg.baseline["range"]
    k = disease_cfg.decay["k"]

    # interpret k consistently in per-day units regardless of time_unit
    k_per_day = k * 24.0 if disease_cfg.time_unit == "hour" else k

    # additive shifts to the equilibrium target (in activity units)
    trigger_sum = sum(mag for _id, _t, mag in state.active_triggers)
    tx_sum = sum(_treatment_effect(tx, t_days) for tx in state.active_treatments)

    t_hours = (t_days * 24.0) % 24.0
    circ = _circadian(
        t_hours,
        disease_cfg.circadian["amplitude"],
        disease_cfg.circadian["phase_hours"],
    )

    target = baseline + trigger_sum - tx_sum + circ
    noise = rng.normal(0.0, disease_cfg.noise["sigma"]) * np.sqrt(max(dt_days, 1e-6))

    # target-tracking ODE: dI/dt = -k * (I - target)
    dI = -k_per_day * (state.activity - target) * dt_days + noise
    new_activity = float(np.clip(state.activity + dI, lo, hi))

    # progressive: accumulate irreversible burden
    new_burden = state.irreversible_burden
    if disease_cfg.dynamics_type == "progressive" and disease_cfg.accumulation:
        acc_rate = disease_cfg.accumulation["rate_per_unit_activity"]
        sat = disease_cfg.accumulation.get("saturation", float("inf"))

        slowdown = 1.0
        for tx in state.active_treatments:
            if tx.get("accumulation_slowdown") and t_days >= tx["start_day"]:
                slowdown *= (1.0 - tx["accumulation_slowdown"])

        dB = acc_rate * max(state.activity - baseline, 0.0) * dt_days * slowdown
        new_burden = float(min(state.irreversible_burden + dB, sat))

    # decay trigger timers
    updated_triggers = [
        (tid, t_left - dt_days, mag)
        for (tid, t_left, mag) in state.active_triggers
        if (t_left - dt_days) > 0
    ]

    return DynamicsState(
        activity=new_activity,
        irreversible_burden=new_burden,
        active_triggers=updated_triggers,
        active_treatments=state.active_treatments,  # treatments persist
    )
