"""Patient class — v2: integrates eight unpredictability sources + age stratification."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from md_piece.adherence import (
    AdherenceState,
    build_adherence_states,
    dose_multiplier,
)
from md_piece.age_stratification import (
    AgeProfile,
    build_age_profile,
    sample_age_and_sex,
)
from md_piece.disease_loader import DiseaseConfig
from md_piece.dynamics import DynamicsState, step_dynamics
from md_piece.life_events import (
    LifeEvent,
    active_events_at,
    schedule_life_events,
)
from md_piece.triggers import (
    assign_comorbidities,
    assign_treatments,
    sample_triggers,
)
from md_piece.unpredictability import (
    UnpredictabilityBundle,
    build_unpredictability,
)


@dataclass
class Patient:
    """Virtual patient — full v2 record."""
    patient_id: str
    disease_id: str
    age: int
    sex: str
    age_profile: AgeProfile | None = None
    comorbidities: list[str] = field(default_factory=list)
    treatments: list[dict] = field(default_factory=list)
    subtype: str = "unspecified"
    responder_class: str = "typical"
    placebo_shift: float = 0.0
    long_tail_event: tuple[float, float, float] | None = None
    adherence_states: dict[str, AdherenceState] = field(default_factory=dict)
    life_events: list[LifeEvent] = field(default_factory=list)
    timeseries: pd.DataFrame | None = None
    flare_count: int = 0
    seed: int = 0


def _eval_biomarker(formula: str, activity: float, burden: float, noise: float) -> float:
    safe_globals = {
        "__builtins__": {},
        "max": max, "min": min,
        "clip": lambda x, lo, hi: max(lo, min(hi, x)),
    }
    safe_locals = {"activity": activity, "burden": burden, "noise": noise}
    return float(eval(formula, safe_globals, safe_locals))  # noqa: S307


def _compute_biomarkers(
    activity: float, burden: float, disease_cfg: DiseaseConfig,
    placebo_shift: float, rng: np.random.Generator,
) -> dict[str, float]:
    """v2: subjective biomarkers get the placebo multiplier."""
    out = {}
    for name, spec in disease_cfg.biomarkers.items():
        noise = rng.normal(0.0, 1.0)
        val = _eval_biomarker(spec["formula"], activity, burden, noise)
        if spec.get("subjective"):
            # placebo_shift in [-0.05, 0.15]; multiplicative against value
            val = val * (1.0 - placebo_shift)
        lo, hi = spec["range"]
        out[name] = float(np.clip(val, lo, hi))
    return out


def simulate_patient(
    patient_id: str,
    disease_cfg: DiseaseConfig,
    sim_days: int,
    seed: int,
    *,
    dt_days: float | None = None,
) -> Patient:
    """Run a full v2 simulation (age + 8 unpredictability sources)."""
    rng = np.random.default_rng(seed)
    if dt_days is None:
        dt_days = 1.0 / 24.0 if disease_cfg.time_unit == "hour" else 1.0

    # ---- age + sex ----
    if disease_cfg.raw.get("age_distribution"):
        age, sex, _bin = sample_age_and_sex(
            disease_cfg.raw["age_distribution"],
            disease_cfg.raw.get("sex_ratio_by_age", {}),
            rng,
        )
    else:
        # legacy fallback
        demo = disease_cfg.demographics
        age_lo, age_hi = demo["age"]["range"]
        age = int(np.clip(
            rng.normal(demo["age"]["mean"], demo["age"]["sd"]), age_lo, age_hi
        ))
        sex = "F" if rng.random() < demo.get("female_ratio", 0.5) else "M"
    age_profile = build_age_profile(age, sex, rng)

    # ---- unpredictability bundle ----
    bundle = build_unpredictability(disease_cfg, rng, sim_days)

    # treatment response modifier = subtype × age
    tx_response_mod = (
        bundle.subtype.treatment_response_multiplier
        * age_profile.treatment_response_modifier
    )

    # ---- treatments + adherence ----
    treatments = assign_treatments(
        disease_cfg, sim_days, rng,
        effect_multiplier=bundle.effect_multiplier,
        treatment_response_modifier=tx_response_mod,
    )
    adherence_cfg = disease_cfg.raw.get("adherence", {})
    adherence_states = build_adherence_states(treatments, adherence_cfg, sim_days, rng)

    # ---- comorbidities (regular + elderly auto-add) ----
    comorbidities = assign_comorbidities(disease_cfg, rng)
    for c in age_profile.elderly_comorbidities:
        if c not in comorbidities:
            comorbidities.append(c)

    # ---- life events ----
    events = schedule_life_events(
        disease_cfg.raw.get("life_events", []),
        sim_days, age, sex, rng,
    )

    patient = Patient(
        patient_id=patient_id,
        disease_id=disease_cfg.id,
        age=age,
        sex=sex,
        age_profile=age_profile,
        comorbidities=comorbidities,
        treatments=treatments,
        subtype=bundle.subtype.name,
        responder_class=bundle.responder_class,
        placebo_shift=bundle.placebo_shift,
        long_tail_event=bundle.long_tail_event,
        adherence_states=adherence_states,
        life_events=events,
        seed=seed,
    )

    # ---- run integration loop ----
    state = DynamicsState(
        activity=float(disease_cfg.baseline["activity"]),
        active_treatments=treatments,
    )
    state._acc_subtype_mult = bundle.subtype.accumulation_rate_multiplier

    n_steps = int(math.ceil(sim_days / dt_days))
    rows: list[dict[str, Any]] = []
    flare_thr = disease_cfg.flare["threshold"] + bundle.subtype.flare_threshold_offset
    refractory = disease_cfg.flare["refractory_days"]
    last_flare_t = -1e9
    flare_count = 0

    last_day_recorded = -1
    for i in range(n_steps):
        t = i * dt_days

        # update adherence — recompute today's dose_multiplier (once per day)
        if int(t) != last_day_recorded:
            for tx in treatments:
                st = adherence_states[tx["id"]]
                tx["dose_multiplier_today"] = dose_multiplier(
                    st, t, adherence_cfg, rng
                )

        # new triggers
        new_triggers = sample_triggers(disease_cfg, dt_days, rng)
        if new_triggers:
            state.active_triggers.extend(new_triggers)

        # active life event bump
        life_bump = sum(e.activity_bump for e in active_events_at(events, t))

        # long-tail bump
        long_tail_bump = 0.0
        if bundle.long_tail_event is not None:
            on, dur, mag = bundle.long_tail_event
            if on <= t < on + dur:
                long_tail_bump = mag

        state = step_dynamics(
            state,
            disease_cfg=disease_cfg, t_days=t, dt_days=dt_days, rng=rng,
            life_event_bump=life_bump,
            long_tail_bump=long_tail_bump,
            age_severity_multiplier=age_profile.severity_modifier,
        )
        state.active_treatments = treatments

        if state.activity > flare_thr and (t - last_flare_t) > refractory:
            flare_count += 1
            last_flare_t = t

        record_now = (i % max(1, int(round(1.0 / dt_days))) == 0)
        if record_now:
            bms = _compute_biomarkers(
                state.activity, state.irreversible_burden,
                disease_cfg, bundle.placebo_shift, rng,
            )
            row = {
                "patient_id": patient_id,
                "day": int(round(t)),
                "activity": state.activity,
                "irreversible_burden": state.irreversible_burden,
                "n_active_triggers": len(state.active_triggers),
                "in_flare": int(state.activity > flare_thr),
                "life_event_active": int(life_bump != 0),
                "long_tail_active": int(long_tail_bump > 0),
                "dose_any_skipped": int(any(
                    tx.get("dose_multiplier_today", 1.0) == 0.0 for tx in treatments
                )),
            }
            row.update(bms)
            rows.append(row)
            last_day_recorded = int(t)

    patient.timeseries = pd.DataFrame(rows)
    patient.flare_count = flare_count
    return patient
