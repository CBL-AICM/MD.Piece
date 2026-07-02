"""L4 Persona Engine (arch §4 L4).

Persona is sampled CONDITIONAL on patient attributes via a softmax over feature scores,
NOT uniformly. High tech-literacy pushes toward PERFECT_LOGGER/NORMAL; advanced age +
caregiver toward CAREGIVER_MANAGED / ELDERLY_LOW_LITERACY. This is what wires the adoption-
selection confound (assumption A05): more able patients both adopt the app AND recall better,
so MD.Piece's apparent benefit is partly selection — which evaluation must adjust for.
"""
from __future__ import annotations

import numpy as np

from simulation.common import Config, PatientRow, PERSONAS


def _feature_activations(p: PatientRow) -> dict[str, float]:
    """Map raw attributes to bounded feature activations consumed by the softmax."""
    return {
        "tech_literacy": (p.tech_literacy - 0.5) * 2.0,        # -1..1
        "age_over_70": 1.0 if p.age > 70 else 0.0,
        "caregiver_support": p.caregiver_support,               # 0..1
        "low_health_literacy": max(0.0, 0.5 - p.health_literacy) * 2.0,  # 0..1
    }


def assign_persona(p: PatientRow, rng: np.random.Generator, cfg: Config) -> str:
    asn = cfg.persona_registry["assignment"]
    base = asn["base_rates"]
    fweights = asn["feature_weights"]
    acts = _feature_activations(p)

    logits = np.array([np.log(base[name]) for name in PERSONAS], dtype=float)
    for feat, act in acts.items():
        contrib = fweights.get(feat, {})
        for j, name in enumerate(PERSONAS):
            logits[j] += act * contrib.get(name, 0.0)

    logits -= logits.max()
    probs = np.exp(logits)
    probs /= probs.sum()
    return PERSONAS[rng.choice(len(PERSONAS), p=probs)]


def persona_params(persona: str, cfg: Config) -> dict:
    """Behavioral parameter vector for a persona (means; spread applied at draw time downstream)."""
    return dict(cfg.persona_registry["personas"][persona])
