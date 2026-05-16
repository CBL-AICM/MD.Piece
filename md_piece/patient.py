"""Patient class — combines dynamics + triggers + biomarker mapping."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from md_piece.disease_loader import DiseaseConfig
from md_piece.dynamics import DynamicsState, step_dynamics
from md_piece.triggers import assign_comorbidities, assign_treatments, sample_triggers


@dataclass
class Patient:
    """One virtual patient with demographics, treatment plan and time-series."""

    patient_id: str
    disease_id: str
    age: int
    sex: str  # 'F' | 'M'
    comorbidities: list[str] = field(default_factory=list)
    treatments: list[dict] = field(default_factory=list)
    timeseries: pd.DataFrame | None = None  # populated after simulation
    flare_count: int = 0
    seed: int = 0


def _eval_biomarker(formula: str, activity: float, burden: float, noise: float) -> float:
    """Evaluate biomarker formula with limited safe namespace.

    YAML formulas use vars: activity, burden, noise, and functions: max, min, clip.
    """
    safe_globals = {
        "__builtins__": {},
        "max": max,
        "min": min,
        "clip": lambda x, lo, hi: max(lo, min(hi, x)),
    }
    safe_locals = {"activity": activity, "burden": burden, "noise": noise}
    return float(eval(formula, safe_globals, safe_locals))  # noqa: S307


def _compute_biomarkers(
    activity: float,
    burden: float,
    disease_cfg: DiseaseConfig,
    rng: np.random.Generator,
) -> dict[str, float]:
    """Map (activity, burden) → all biomarkers defined in YAML, clipped to range."""
    out = {}
    for name, spec in disease_cfg.biomarkers.items():
        noise = rng.normal(0.0, 1.0)
        try:
            val = _eval_biomarker(spec["formula"], activity, burden, noise)
        except Exception as e:
            raise ValueError(f"Biomarker formula failed for '{name}': {e}") from e
        lo, hi = spec["range"]
        out[name] = float(np.clip(val, lo, hi))
    return out


def _sample_demographics(
    disease_cfg: DiseaseConfig, rng: np.random.Generator
) -> tuple[int, str]:
    """Sample age and sex from disease demographics block."""
    demo = disease_cfg.demographics
    age_spec = demo.get("age", {"mean": 50, "sd": 15, "range": [18, 80]})
    age_lo, age_hi = age_spec["range"]
    age = int(np.clip(rng.normal(age_spec["mean"], age_spec["sd"]), age_lo, age_hi))
    female_ratio = demo.get("female_ratio", 0.5)
    sex = "F" if rng.random() < female_ratio else "M"
    return age, sex


def simulate_patient(
    patient_id: str,
    disease_cfg: DiseaseConfig,
    sim_days: int,
    seed: int,
    *,
    dt_days: float | None = None,
) -> Patient:
    """Run a full simulation for one patient and return populated Patient.

    Parameters
    ----------
    patient_id : str
    disease_cfg : DiseaseConfig
    sim_days : int
    seed : int
        Per-patient seed for full reproducibility.
    dt_days : float | None
        Override timestep. Default: 1.0 for day-based, 1/24 for hour-based.

    Returns
    -------
    Patient
        With .timeseries DataFrame populated.
    """
    rng = np.random.default_rng(seed)

    if dt_days is None:
        dt_days = 1.0 / 24.0 if disease_cfg.time_unit == "hour" else 1.0

    age, sex = _sample_demographics(disease_cfg, rng)
    treatments = assign_treatments(disease_cfg, sim_days, rng)
    comorbidities = assign_comorbidities(disease_cfg, rng)

    patient = Patient(
        patient_id=patient_id,
        disease_id=disease_cfg.id,
        age=age,
        sex=sex,
        comorbidities=comorbidities,
        treatments=treatments,
        seed=seed,
    )

    state = DynamicsState(
        activity=float(disease_cfg.baseline["activity"]),
        active_treatments=treatments,
    )

    n_steps = int(math.ceil(sim_days / dt_days))
    rows: list[dict[str, Any]] = []

    flare_thr = disease_cfg.flare["threshold"]
    refractory = disease_cfg.flare["refractory_days"]
    last_flare_t = -1e9
    flare_count = 0

    for i in range(n_steps):
        t = i * dt_days

        # sample new triggers, append to active list
        new_triggers = sample_triggers(disease_cfg, dt_days, rng)
        if new_triggers:
            state.active_triggers.extend(new_triggers)

        # advance
        state = step_dynamics(
            state, disease_cfg=disease_cfg, t_days=t, dt_days=dt_days, rng=rng
        )
        # treatments persist on patient but state instance was rebuilt
        state.active_treatments = treatments

        # flare detection
        if state.activity > flare_thr and (t - last_flare_t) > refractory:
            flare_count += 1
            last_flare_t = t

        # record once per day to keep df manageable
        record_now = (i % max(1, int(round(1.0 / dt_days))) == 0)
        if record_now:
            bms = _compute_biomarkers(
                state.activity, state.irreversible_burden, disease_cfg, rng
            )
            row = {
                "patient_id": patient_id,
                "day": int(round(t)),
                "activity": state.activity,
                "irreversible_burden": state.irreversible_burden,
                "n_active_triggers": len(state.active_triggers),
                "in_flare": int(state.activity > flare_thr),
            }
            row.update(bms)
            rows.append(row)

    patient.timeseries = pd.DataFrame(rows)
    patient.flare_count = flare_count
    return patient
