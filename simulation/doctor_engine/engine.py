"""L8 Doctor Interaction Engine (arch §4 L8).

Models the LAST MILE of information friction: data that reached the record but not the
clinician's working understanding. Understanding is a SATURATING function of usable signal,
capped by the physician's attention budget — so a more complete but NOISIER record can yield
LESS understanding for a time-constrained reader. This is what lets MD.Piece lose the clinical
endpoint even while winning the data endpoint (a genuinely possible negative result, arch §11).
"""
from __future__ import annotations

import math

import numpy as np

from simulation.common import Config, pval

# specialty routing by disease (face-valid)
_SPECIALTY = {
    "NMOSD": "NEUROLOGY", "MS": "NEUROLOGY", "MG": "NEUROLOGY",
    "SLE": "RHEUMATOLOGY", "RA": "RHEUMATOLOGY",
    "CROHN": "GASTROENTEROLOGY", "OTHER": "PRIMARY_CARE",
}


def assign_physician(disease: str, rng: np.random.Generator, cfg: Config) -> tuple[str, str]:
    mix = cfg.probability_registry["doctor"]["persona_mix"]
    personas = list(mix.keys())
    probs = np.array([mix[p] for p in personas], dtype=float)
    probs /= probs.sum()
    persona = personas[rng.choice(len(personas), p=probs)]
    return persona, _SPECIALTY.get(disease, "PRIMARY_CARE")


def review_record(physician_persona: str, completeness: float, snr: float, n_events: int,
                  rng: np.random.Generator, cfg: Config, accuracy: float = 1.0) -> dict:
    """One clinician's review of one arm's record. Returns interaction + understanding.

    `accuracy` (0-1) = fidelity of the captured data (date/severity correctness). TRUE
    understanding is discounted by it: a complete-but-misdated record (recall's telescoping)
    yields FALSE confidence, not real understanding — so volume alone does not buy understanding.
    """
    dc = cfg.probability_registry["doctor"]
    base_rev = float(pval(dc["review_probability"]["base"]))
    rev_off = dc["review_probability"]["persona_offset"].get(physician_persona, 0.0)
    review_p = float(np.clip(base_rev + rev_off, 0.02, 0.99))

    rt_base = float(pval(dc["reading_time_sec"]["base"]))
    rt_per = float(pval(dc["reading_time_sec"]["per_event"]))
    needed = rt_base + rt_per * n_events
    budget = float(pval(dc["reading_budget_base_sec"])) * float(dc["budget_multiplier"].get(physician_persona, 1.0))

    und = dc["understanding"]
    sat_k = float(pval(und["saturation_k"]))
    noise_pen = float(pval(und["noise_penalty"]))
    threshold = float(pval(und["threshold"]))
    acc_couple = float(pval(und["accuracy_coupling"]))
    trust_couple = float(pval(und["trust_completeness_coupling"]))

    reviewed = rng.random() < review_p
    if not reviewed:
        return dict(reviewed=False, reading_time_sec=0, trust_score=0.0,
                    actionability_score=0.0, snapshot_engagement=0.0,
                    doctor_understanding=0.0, time_to_understanding_sec=None,
                    unreviewed_fraction=1.0)

    fraction_read = float(np.clip(budget / max(needed, 1.0), 0.0, 1.0))
    # usable signal: completeness degraded by noise (low snr hurts), saturating returns
    signal = completeness * (1.0 - noise_pen * (1.0 - snr))
    signal = max(0.0, signal) * fraction_read
    understanding = (1.0 - math.exp(-sat_k * signal))
    # discount for inaccurate data: wrong dates/severities are false confidence, not understanding
    understanding *= (1.0 - acc_couple * (1.0 - float(np.clip(accuracy, 0.0, 1.0))))
    understanding = float(np.clip(understanding, 0.0, 1.0))

    # skeptical physicians discount completeness when forming trust
    trust = float(np.clip(0.4 + trust_couple * (completeness - 0.5)
                          - (0.15 if physician_persona == "SKEPTICAL" else 0.0), 0.0, 1.0))
    actionability = float(np.clip(understanding * (0.6 + 0.4 * snr), 0.0, 1.0))
    reading_time = int(min(needed, budget))
    ttu = reading_time if understanding >= threshold else None

    return dict(reviewed=True, reading_time_sec=reading_time, trust_score=round(trust, 3),
                actionability_score=round(actionability, 3),
                snapshot_engagement=round(fraction_read, 3),
                doctor_understanding=round(understanding, 3),
                time_to_understanding_sec=ttu,
                unreviewed_fraction=round(1.0 - fraction_read, 3))
