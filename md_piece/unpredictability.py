"""Central orchestrator for the eight unpredictability sources.

(1) Individual variability     — parameter distributions in YAML.
(2) Responder classes          — multiplier on treatment effect.
(3) Hidden subtypes            — offset on flare threshold + treatment response.
(4) Adherence                  — see md_piece.adherence.
(5) Stochastic life events     — see md_piece.life_events.
(6) Placebo / nocebo           — applied to subjective biomarkers.
(7) Long-tail rare events      — sampled via a low-probability hidden trigger.
(8) Age stratification         — see md_piece.age_stratification.

Reference: Senn (2016), Fulop et al. (2018), Walonoski et al. (2018).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# ---------- (1) parameter distribution sampling --------------------------------

def sample_param(param, rng: np.random.Generator) -> float:
    """Sample a YAML parameter that may be a scalar or a {mean, std, min, max} dict.

    Examples
    --------
    >>> sample_param(1.2, rng)              # → 1.2
    >>> sample_param({"mean":1.2,"std":0.3,"min":0.1,"max":2.0}, rng)
    """
    if isinstance(param, (int, float)):
        return float(param)
    if isinstance(param, dict):
        mu = float(param["mean"])
        sd = float(param.get("std", 0.0))
        if sd <= 0:
            return mu
        val = float(rng.normal(mu, sd))
        lo = float(param.get("min", -np.inf))
        hi = float(param.get("max",  np.inf))
        return float(np.clip(val, lo, hi))
    raise TypeError(f"unsupported param type: {type(param)}")


# ---------- (2) responder class -----------------------------------------------

def sample_responder_class(
    classes_cfg: dict | None, rng: np.random.Generator
) -> tuple[str, float]:
    """Pick (class_name, effect_multiplier) using YAML probabilities."""
    if not classes_cfg:
        return "typical", 1.0
    names = list(classes_cfg.keys())
    probs = np.array([classes_cfg[n]["probability"] for n in names], dtype=float)
    probs = probs / probs.sum()
    name = rng.choice(names, p=probs)
    return name, float(classes_cfg[name]["effect_multiplier"])


# ---------- (3) hidden disease subtype ----------------------------------------

@dataclass
class SubtypeProfile:
    name: str = "unspecified"
    flare_threshold_offset: float = 0.0
    treatment_response_multiplier: float = 1.0
    accumulation_rate_multiplier: float = 1.0


def sample_subtype(
    subtypes_cfg: dict | None, rng: np.random.Generator
) -> SubtypeProfile:
    if not subtypes_cfg:
        return SubtypeProfile()
    names = list(subtypes_cfg.keys())
    probs = np.array([subtypes_cfg[n]["probability"] for n in names], dtype=float)
    probs = probs / probs.sum()
    name = rng.choice(names, p=probs)
    s = subtypes_cfg[name]
    return SubtypeProfile(
        name=name,
        flare_threshold_offset=float(s.get("flare_threshold_offset", 0.0)),
        treatment_response_multiplier=float(s.get("treatment_response_multiplier", 1.0)),
        accumulation_rate_multiplier=float(s.get("accumulation_rate_multiplier", 1.0)),
    )


# ---------- (6) placebo / nocebo ----------------------------------------------

def sample_placebo_effect(
    placebo_cfg: dict | None, rng: np.random.Generator
) -> float:
    """Return a placebo multiplier shift applied to subjective biomarkers.

    YAML format:
        placebo:
          probabilities: [0.70, 0.20, 0.10]    # none / positive / nocebo
          effects:       [0.00, 0.15, -0.05]
    """
    if not placebo_cfg:
        return 0.0
    probs = np.array(placebo_cfg["probabilities"], dtype=float)
    probs = probs / probs.sum()
    effects = np.array(placebo_cfg["effects"], dtype=float)
    idx = int(rng.choice(len(probs), p=probs))
    return float(effects[idx])


# ---------- (7) long-tail rare events -----------------------------------------

def sample_long_tail_event(
    sim_days: int, rng: np.random.Generator,
) -> tuple[float, float, float] | None:
    """With ~3% probability, schedule one atypical severe flare lasting 7-21 days.

    Returns (onset_day, duration_days, activity_bump) or None.
    """
    if rng.random() > 0.03:
        return None
    onset = float(rng.uniform(0, sim_days))
    dur = float(rng.uniform(7, 21))
    bump = float(rng.uniform(3.0, 5.0))   # severe
    return onset, dur, bump


# ---------- bundle ------------------------------------------------------------

@dataclass
class UnpredictabilityBundle:
    """Aggregated per-patient unpredictability state."""
    responder_class: str = "typical"
    effect_multiplier: float = 1.0
    subtype: SubtypeProfile = field(default_factory=SubtypeProfile)
    placebo_shift: float = 0.0
    long_tail_event: tuple[float, float, float] | None = None


def build_unpredictability(
    disease_cfg, rng: np.random.Generator, sim_days: int,
) -> UnpredictabilityBundle:
    """Sample responder class + subtype + placebo + long-tail event for one patient."""
    rc_name, rc_mult = sample_responder_class(
        disease_cfg.raw.get("responder_classes"), rng
    )
    subtype = sample_subtype(disease_cfg.raw.get("subtypes"), rng)
    placebo = sample_placebo_effect(disease_cfg.raw.get("placebo"), rng)
    long_tail = sample_long_tail_event(sim_days, rng)
    return UnpredictabilityBundle(
        responder_class=rc_name,
        effect_multiplier=rc_mult,
        subtype=subtype,
        placebo_shift=placebo,
        long_tail_event=long_tail,
    )
