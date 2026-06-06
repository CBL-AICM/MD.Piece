"""L6 App Usage / Retention (arch §4 L6).

Produces a per-day ENGAGEMENT GATE e(t) in [0,1] that the MD.Piece observer (L5b) uses to
decide whether each event gets logged. The gate captures the realities that make MD.Piece
LOSSY (and therefore make the research question non-trivial):

  * Non-adoption: a fraction never get past onboarding -> gate == 0 all year (a real MD.Piece
    outcome, counted against the app, NOT censored — assumption A02).
  * Dropout: a hard dropout DAY is sampled from a log-logistic distribution (declining hazard,
    early-heavy dropout — the classic health-app retention shape). The patient logs at full
    propensity while retained, then stops. Sampling a day (rather than smoothly multiplying by
    the survival curve every day) avoids compounding that would penalize even high-retention
    users. Median lifetime is deliberately pessimistic (A09/D3) and scaled by retention_kappa.
  * Flare re-engagement: a flare/ED/admission transiently re-activates even a dropped user.
  * Caregiver floor: caregiver-managed patients can't fall below a retention floor.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulation.common import Config, Event, PatientRow, pval


@dataclass
class UsageTrajectory:
    onboarded: bool
    engagement_gate: np.ndarray  # [0,1] per day — the L5b logging gate
    median_lifetime: float

    def gate(self, day: int) -> float:
        return float(self.engagement_gate[day])

    def active_mask(self, threshold: float = 0.15) -> np.ndarray:
        return self.engagement_gate > threshold


def usage_trajectory(patient: PatientRow, persona: dict, truth_events: list[Event],
                     rng: np.random.Generator, cfg: Config) -> UsageTrajectory:
    horizon = cfg.horizon_days
    ret = cfg.probability_registry["usage"]["retention"]
    base_median = float(pval(ret["median_lifetime_days"]))
    shape = float(pval(ret["shape"]))
    spike_mult = float(pval(ret["flare_reengagement"]["spike_multiplier"]))
    spike_decay = float(pval(ret["flare_reengagement"]["decay_days"]))
    cg_floor = float(pval(ret["caregiver_retention_floor"]))
    onboard_base = float(pval(ret["onboarding_completion"]))
    onboard_spread = float(pval(ret["onboarding_engagement_spread"]))

    kappa = float(persona.get("retention_kappa", 1.0))
    median = max(7.0, base_median * kappa)

    # onboarding scales with engagement propensity: power users almost always adopt; low-engagement
    # personas often never get past Day-1 (non-adoption is a real MD.Piece outcome, A02).
    eng = float(persona.get("engagement_level", 0.5))
    onboard_p = float(np.clip(onboard_base + (eng - 0.5) * onboard_spread, 0.05, 0.99))

    gate = np.zeros(horizon, dtype=float)
    if rng.random() >= onboard_p:
        return UsageTrajectory(onboarded=False, engagement_gate=gate, median_lifetime=0.0)

    days = np.arange(horizon)
    # sample a hard dropout day from the log-logistic: S(D)=u  =>  D = median*((1-u)/u)^(1/shape)
    u = float(rng.random())
    u = min(max(u, 1e-6), 1.0 - 1e-6)
    dropout_day = median * ((1.0 - u) / u) ** (1.0 / shape)
    gate = (days < dropout_day).astype(float)  # full engagement while retained, then 0

    # flare-driven re-engagement (additive transient boost; can lift a dropped user)
    boost_amp = min(1.0, 0.25 * spike_mult)
    for ev in truth_events:
        if ev.event_type in ("FLARE", "EMERGENCY_VISIT", "HOSPITALIZATION"):
            tk = ev.event_date_true
            d = days - tk
            m = d >= 0
            gate[m] = gate[m] + boost_amp * np.exp(-d[m] / spike_decay)

    # caregiver floor keeps otherwise-dropped patients minimally active
    if persona.get("caregiver_required", False) or patient.caregiver_support >= 1.0:
        gate = np.maximum(gate, cg_floor)

    np.clip(gate, 0.0, 1.0, out=gate)
    return UsageTrajectory(onboarded=True, engagement_gate=gate,
                           median_lifetime=min(float(dropout_day), float(horizon)))
