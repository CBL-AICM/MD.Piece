"""L5a — Patient Recall observer (arch §4 L5a).

Models RETROSPECTIVE reconstruction at the annual review (recall_day): the patient tries to
remember the year's events all at once, from memory. Loss profile:

  * Omission via salience-weighted forgetting. Retention of event e:
        p_keep = floor + (1 - floor) * exp(-Δt / τ)
        floor  = salience * recall_accuracy   (salient events + good rememberers retain a floor)
        τ      = tau_days * (0.5 + recall_accuracy)   (better rememberers forget slower)
    => a year-old mild symptom is usually gone; a recent hospitalization usually survives.
  * Telescoping: surviving events are recalled as MORE RECENT than they were (date shifts
    toward the recall day) — a classic, well-documented recall bias.
  * Severity regression toward 'mild' (anxious personas instead INFLATE severity).
  * Graded medication loss: drug > dose > frequency survive in that order.
  * A small rate of FALSE memories (fabricated events) — recall, unlike an app, invents.

Crucially, recall loss does NOT depend on app engagement — that is the whole asymmetry with
MD.Piece (which is engagement-gated but date-accurate). See mdpiece.py.
"""
from __future__ import annotations

import numpy as np

from simulation.common import Config, Event, PatientRow, pval, salience_of


def recall_observer(truth_events: list[Event], patient: PatientRow, persona: dict,
                    rng: np.random.Generator, cfg: Config, recall_day: int | None = None,
                    arm: str = "PATIENT_RECALL", id_prefix: str = "R") -> list[Event]:
    horizon = cfg.horizon_days
    recall_day = horizon - 1 if recall_day is None else recall_day
    rc = cfg.probability_registry["friction"]["recall"]
    tau_days = float(pval(rc["tau_days"]))
    telescoping_on = bool(rc["telescoping"]["enabled"])
    fwd = float(pval(rc["telescoping"]["forward_bias_frac"]))
    sev_strength = float(pval(rc["severity_regression"]["strength"]))
    false_rate = float(pval(rc["false_logging_rate"]))
    grading = rc["med_recall_grading"]

    rec = float(persona.get("recall_accuracy", 0.5))
    med_acc = float(persona.get("med_recall_accuracy", 0.5))
    sev_bias = float(persona.get("severity_bias", 0.0))  # anxious persona inflates severity

    tau = tau_days * (0.5 + rec)
    out: list[Event] = []
    counter = 0

    def new_id() -> str:
        nonlocal counter
        counter += 1
        return f"{patient.patient_id}-{id_prefix}{counter:04d}"

    kept = 0
    for e in truth_events:
        dt = recall_day - e.event_date_true
        if dt < 0:
            continue  # not yet happened at recall time
        floor = e.salience * rec
        p_keep = floor + (1.0 - floor) * np.exp(-dt / tau)
        if rng.random() >= p_keep:
            continue  # forgotten (omission = absence of row)
        kept += 1

        # telescoping: shift recorded date toward the recall day (recalled as more recent)
        if telescoping_on and dt > 0:
            shift = fwd * dt + rng.normal(0.0, 3.0)
            date_rec = int(np.clip(round(e.event_date_true + shift), 0, recall_day))
        else:
            date_rec = e.event_date_true

        # severity regression toward 'mild' (1); anxious personas inflate
        if e.severity_true is not None:
            regressed = e.severity_true - sev_strength * (e.severity_true - 1) + sev_bias
            sev_rec = int(np.clip(round(regressed), 0, 4))
        else:
            sev_rec = None

        # graded medication recall: drug, then dose, then frequency
        med, dose, freq = e.medication, e.dose, e.frequency
        if e.medication is not None:
            if rng.random() >= med_acc:
                med = None  # remembers a med change happened, not which drug
            if rng.random() >= med_acc * (grading["drug"] + grading["dose"]):
                dose = None
            if rng.random() >= med_acc * grading["frequency"]:
                freq = None

        out.append(Event(
            event_id=new_id(), patient_id=patient.patient_id, arm=arm,
            event_type=e.event_type, event_date_true=e.event_date_true,
            source=e.source, salience=e.salience, true_event_id=e.event_id,
            event_date_recorded=date_rec, severity_true=e.severity_true, severity_recorded=sev_rec,
            medication=med, dose=dose, frequency=freq,
            temporal_error_days=date_rec - e.event_date_true,
        ))

    # false memories: a few fabricated low-salience symptom events (true_event_id stays None)
    n_false = rng.poisson(false_rate * max(1, kept))
    for _ in range(int(n_false)):
        day = int(rng.integers(0, horizon))
        out.append(Event(
            event_id=new_id(), patient_id=patient.patient_id, arm=arm,
            event_type="SYMPTOM", event_date_true=day, source="hazard",
            salience=salience_of("SYMPTOM", cfg), true_event_id=None,
            event_date_recorded=day, severity_true=None,
            severity_recorded=int(rng.integers(1, 3)), is_false=True,
        ))
    return out
