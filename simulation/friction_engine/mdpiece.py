"""L5b — MD.Piece observer (arch §4 L5b).

Models PROSPECTIVE day-of logging. Loss profile is the MIRROR of recall's:

  * Completeness is gated by engagement: each event is logged with
        p_log = logging_prob * gate(t) * coupling (+ caregiver_boost)
    where gate(t) comes from the usage engine (dropout, non-adoption, flare re-engagement).
    A dropped-out or never-adopted patient logs almost nothing — counted against MD.Piece.
  * BUT what gets logged is DATE-ACCURATE (logged the day it happened: temporal_error ≈ 0).
    This is the app's core value and the asymmetry with recall's telescoping.
  * Logged entries undergo only a small mis-entry rate, drifting up slightly over time
    (data-entry fatigue — assumption A03; set logged_quality_decay=0 to test the optimistic
    'logged == permanently perfect' assumption).
  * Notifications can RECOVER a would-be-omitted event as a delayed log (memory-sourced, so it
    carries a small temporal error and a logged_lag penalty).
  * MD.Piece does NOT fabricate events (no false logging) — prospective capture, not memory.

parity=True short-circuits to the recall model (V-SANITY, arch §10): with MD.Piece reduced to
the recall process, the MDPIECE−RECALL effect must vanish — proving the evaluation/bookkeeping
is unbiased and any real effect comes from the observer models, not the metric machinery.
"""
from __future__ import annotations

import numpy as np

from simulation.common import Config, Event, PatientRow, pval
from simulation.friction_engine.recall import recall_observer
from simulation.usage_engine import UsageTrajectory

_FLARE_LIKE = ("FLARE", "SYMPTOM", "EMERGENCY_VISIT")
# Document-backed event types recoverable via OCR upload (passive capture, design pillar B)
_OCR_TYPES = ("LAB", "IMAGING", "HOSPITALIZATION", "EMERGENCY_VISIT",
              "MEDICATION_CHANGE", "INFUSION", "PROCEDURE", "INFECTION")


def mdpiece_observer(truth_events: list[Event], patient: PatientRow, persona: dict,
                     usage: UsageTrajectory, rng: np.random.Generator, cfg: Config,
                     parity: bool = False) -> list[Event]:
    if parity:
        # V-SANITY: MD.Piece reduced to the recall process -> effect must vanish.
        return recall_observer(truth_events, patient, persona, rng, cfg,
                               arm="MDPIECE", id_prefix="M")

    mp = cfg.probability_registry["friction"]["mdpiece"]
    coupling = float(pval(mp["engagement_coupling"]))
    cg_boost = float(pval(mp["caregiver_boost"]))
    flare_cap = float(pval(mp["flare_logging_multiplier_cap"]))
    q_decay = float(pval(mp["logged_quality_decay"]))
    mis_rate = float(pval(mp["mis_entry_rate"]))
    nr = mp["notification_recovery"]
    max_recover = float(pval(nr["max_recovered_frac"]))
    lag_penalty = int(pval(nr["delayed_log_penalty_days"]))
    ocr = mp.get("ocr_capture", {})
    ocr_on = bool(ocr.get("enabled", False))
    ocr_frac = float(pval(ocr.get("recovered_frac", 0.0)))

    logging_prob = float(persona.get("logging_prob", 0.3))
    notif = float(persona.get("notif_response", 0.4))
    flare_mult = float(persona.get("flare_logging_multiplier", 1.0))
    has_caregiver = persona.get("caregiver_required", False) or patient.caregiver_support >= 1.0
    boost = cg_boost if has_caregiver else 0.0

    horizon = cfg.horizon_days
    out: list[Event] = []
    counter = 0

    def new_id() -> str:
        nonlocal counter
        counter += 1
        return f"{patient.patient_id}-M{counter:04d}"

    def perturb_severity(sev: int | None, scale: float) -> int | None:
        if sev is None:
            return None
        return int(np.clip(sev + rng.integers(-1, 2), 0, 4)) if rng.random() < scale else sev

    for e in truth_events:
        t = e.event_date_true
        gate = usage.gate(t)
        p_log = logging_prob * gate * coupling + boost
        if e.event_type in _FLARE_LIKE:
            p_log *= min(flare_cap, flare_mult)
        p_log = float(np.clip(p_log, 0.0, 1.0))

        if rng.random() < p_log:
            # logged the day it happened: date-accurate. Mis-entry rises slightly over time.
            eff_mis = float(np.clip(mis_rate + q_decay * (t / 365.0), 0.0, 1.0))
            sev_rec = perturb_severity(e.severity_true, eff_mis)
            med, dose, freq = e.medication, e.dose, e.frequency
            if e.medication is not None and rng.random() < eff_mis:
                dose = None  # minor entry slip
            out.append(Event(
                event_id=new_id(), patient_id=patient.patient_id, arm="MDPIECE",
                event_type=e.event_type, event_date_true=t, source=e.source, salience=e.salience,
                true_event_id=e.event_id, event_date_recorded=t,
                severity_true=e.severity_true, severity_recorded=sev_rec,
                medication=med, dose=dose, frequency=freq,
                temporal_error_days=0, logged_lag_days=0,
            ))
        elif rng.random() < notif * max_recover:
            # notification-recovered: late log from memory -> small temporal + severity error
            terr = lag_penalty + int(round(rng.normal(0.0, 2.0)))
            date_rec = int(np.clip(t + terr, 0, horizon - 1))
            out.append(Event(
                event_id=new_id(), patient_id=patient.patient_id, arm="MDPIECE",
                event_type=e.event_type, event_date_true=t, source=e.source, salience=e.salience,
                true_event_id=e.event_id, event_date_recorded=date_rec,
                severity_true=e.severity_true, severity_recorded=perturb_severity(e.severity_true, 0.5),
                medication=e.medication, dose=e.dose, frequency=e.frequency,
                temporal_error_days=date_rec - t, logged_lag_days=max(1, terr),
            ))
        elif ocr_on and e.event_type in _OCR_TYPES and rng.random() < ocr_frac:
            # OCR from uploaded documents (lab reports, discharge summaries, prescriptions):
            # passive, engagement-INDEPENDENT capture; date-accurate from the document itself.
            # (When ocr_on is False this branch short-circuits before drawing, preserving determinism.)
            out.append(Event(
                event_id=new_id(), patient_id=patient.patient_id, arm="MDPIECE",
                event_type=e.event_type, event_date_true=t, source=e.source, salience=e.salience,
                true_event_id=e.event_id, event_date_recorded=t,
                severity_true=e.severity_true, severity_recorded=e.severity_true,
                medication=e.medication, dose=e.dose, frequency=e.frequency,
                temporal_error_days=0, logged_lag_days=0,
            ))
        # else: omitted (absence of row)

    return out
