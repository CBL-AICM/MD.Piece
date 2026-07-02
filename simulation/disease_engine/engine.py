"""L2 + L3 — coupled Disease Progression & Healthcare Utilization (arch §4 L2/L3).

A daily microsimulation over the horizon producing the GROUND_TRUTH event stream:

  * Latent disease activity a(t) in [0,1]: Ornstein-Uhlenbeck mean-reversion toward a
    severity-set baseline, with the reversion TARGET modulated up by active infections /
    missed refills and down by active treatment escalation.
  * Flares: Hawkes self-exciting process (a flare raises near-term flare risk). A flare
    jumps a(t) up and can pull care earlier -> steroid escalation -> a(t) falls after a lag.
  * Infections: non-homogeneous (seasonal) Poisson hazard; raise a(t) across a short window.
  * Utilization: scheduled care (outpatient / infusion / refill) gated by adherence & clinic
    access, plus hazard-driven ED / admission that scales with activity and is AMPLIFIED by
    poor access (ED substitution — a social-determinant effect, arch §4 L2).

This is the canonical event chain encoded as deterministic guarded transitions (Rule 5:
no model in the loop — thresholds and hazards are plain code).
"""
from __future__ import annotations

import math

import numpy as np

from simulation.common import Config, Event, PatientRow, salience_of


def _v(node):
    """Unwrap a {value:..., range:...} registry node, or pass a scalar through."""
    return node["value"] if isinstance(node, dict) and "value" in node else node


def _severity_from_activity(a: float, bins: list[float]) -> int:
    s = 0
    for b in bins:
        if a >= b:
            s += 1
    return s


def simulate_ground_truth(patient: PatientRow, rngs: dict[str, np.random.Generator],
                          cfg: Config) -> list[Event]:
    dr = rngs["disease"]
    ur = rngs["utilization"]
    horizon = cfg.horizon_days

    dreg = cfg.disease_registry[patient.disease]
    dflt = cfg.disease_registry["defaults"]
    util = cfg.probability_registry["utilization"]
    season = cfg.disease_registry["infection_seasonality"]

    # --- disease dynamics params ---
    baseline = float(dflt["ou_baseline_by_severity"][patient.severity])
    theta = float(dreg["ou_reversion"])
    sigma = float(dflt["ou_sigma"])
    bins = dflt["activity_severity_bins"]
    sym_thr = float(dflt["symptom_threshold"])
    sym_hyst = float(dflt["symptom_hysteresis"])
    sym_recur = int(dflt["symptom_recur_days"])
    flare_jump = float(dflt["flare_activity_jump"])
    hawkes_tau = float(dflt["hawkes_decay_days"])
    inf_bump = float(dflt["infection_activity_bump"])
    inf_window = int(dflt["infection_window_days"])
    refill_lapse_bump = float(dflt["missed_refill_activity_bump"])

    # Hawkes flares. hawkes_excitation is the BRANCHING RATIO (offspring flares per flare),
    # which MUST be < 1 for stationarity. The exponential kernel is normalized so its
    # integral equals the branching ratio: g(t) = (br/tau)*exp(-t/tau). The background rate
    # is then set so the stationary flare rate mu/(1-br) equals relapse_rate_yr (face validity).
    br = float(dreg["hawkes_excitation"])
    assert 0.0 <= br < 1.0, f"{patient.disease} hawkes_excitation must be in [0,1), got {br}"
    mu_flare = float(dreg["relapse_rate_yr"]) * (1.0 - br) / 365.0
    mu_inf = float(dreg["infection_rate_yr"]) / 365.0
    amp = float(season["amplitude"])
    peak_day = float(season["peak_day"])

    # --- utilization params ---
    maint_drug = dreg["standard_treatments"][0]
    infusion_interval = dreg["infusion_interval"]
    outpatient_interval = int(dreg["outpatient_interval"])
    refill_interval = int(_v(util["refill_interval_days"]))
    lab_p = float(_v(util["lab_on_appointment_prob"]))
    img_p = float(_v(util["imaging_on_appointment_prob"]))
    access_mult = float(util["access_multiplier"][patient.clinic_access])
    cs = util["care_seeking"]
    symptom_visit_p = float(_v(cs["symptom_visit_prob"]))
    flare_visit_p = float(_v(cs["flare_visit_prob"]))
    lit_w = float(_v(cs["literacy_weight"]))
    ed = util["ed"]
    ed_base = float(_v(ed["base_hazard_at_max_activity"]))
    ed_low_access = float(_v(ed["low_access_multiplier"]))
    admit_p = float(_v(ed["admission_prob_given_ed"]))
    icu_p = float(_v(ed["icu_prob_given_admission"]))
    esc = util["escalation"]
    esc_p = float(_v(esc["prob_given_flare_visit"]))
    steroid = esc["steroid"]
    esc_effect = float(_v(esc["effect_size"]))
    steroid_lag = int(dreg["steroid_response_lag"])

    lit = patient.health_literacy
    adher = patient.baseline_adherence
    # literacy modulates appropriate care-seeking (centered at 0.5)
    lit_factor = 1.0 + lit_w * (lit - 0.5)

    # phases so visit calendars are not synchronized across the population
    outpatient_phase = int(ur.integers(1, outpatient_interval + 1))
    refill_phase = int(ur.integers(1, refill_interval + 1))
    infusion_phase = int(ur.integers(1, int(infusion_interval) + 1)) if infusion_interval else None

    events: list[Event] = []
    counter = 0

    def emit(etype, day, source, severity=None, med=None, dose=None, freq=None):
        nonlocal counter
        counter += 1
        eid = f"{patient.patient_id}-G{counter:04d}"
        events.append(Event(
            event_id=eid, patient_id=patient.patient_id, arm="GROUND_TRUTH",
            event_type=etype, event_date_true=day, source=source,
            salience=salience_of(etype, cfg), true_event_id=eid,
            event_date_recorded=day, severity_true=severity, severity_recorded=severity,
            medication=med, dose=dose, frequency=freq,
        ))

    # baseline maintenance therapy anchored at enrolment
    emit("TREATMENT", 0, "scheduled", severity=patient.severity, med=maint_drug, freq="maintenance")

    a = baseline
    flare_times: list[int] = []
    infection_active_until = -1
    treat_effect_until = -1
    pending_escalations: list[tuple[int, float]] = []
    episode_open = False
    last_symptom_day = -10_000

    for day in range(horizon):
        # activate any escalation whose response lag has elapsed
        treat_effect = 0.0
        for apply_day, eff in pending_escalations:
            if apply_day <= day:
                treat_effect_until = max(treat_effect_until, apply_day + 45)
        if day <= treat_effect_until:
            treat_effect = esc_effect

        infect_on = day <= infection_active_until
        eff_target = baseline + (inf_bump if infect_on else 0.0) - treat_effect
        eff_target = min(1.0, max(0.0, eff_target))

        # OU step toward the (modulated) target
        a = a + theta * (eff_target - a) + sigma * float(dr.normal())
        a = min(1.0, max(0.0, a))

        # --- infections (seasonal Poisson) ---
        seasonal = 1.0 + amp * math.cos(2 * math.pi * (day - peak_day) / 365.0)
        lam_inf = mu_inf * max(0.0, seasonal)
        if dr.random() < 1.0 - math.exp(-lam_inf):
            emit("INFECTION", day, "infection", severity=_severity_from_activity(a, bins))
            infection_active_until = day + inf_window

        # --- flares (Hawkes self-exciting) ---
        lam = mu_flare + sum((br / hawkes_tau) * math.exp(-(day - tk) / hawkes_tau)
                             for tk in flare_times)
        if dr.random() < 1.0 - math.exp(-lam):
            a = min(1.0, a + flare_jump)
            flare_times.append(day)
            sev = _severity_from_activity(a, bins)
            src = "relapse" if patient.disease in ("MS", "NMOSD") else "flare"
            emit("FLARE", day, src, severity=sev)
            # care-seeking on a flare (access + literacy gated)
            if ur.random() < min(1.0, flare_visit_p * access_mult * lit_factor):
                emit("APPOINTMENT", day, "flare", severity=sev)
                if ur.random() < esc_p:
                    emit("MEDICATION_CHANGE", day, "treatment_response",
                         severity=sev, med=steroid, freq="taper")
                    pending_escalations.append((day + steroid_lag, esc_effect))

        # --- symptom episodes (activity crossing, with hysteresis to kill threshold chatter) ---
        if not episode_open and a >= sym_thr:
            episode_open = True
            sev = _severity_from_activity(a, bins)
            emit("SYMPTOM", day, "hazard", severity=sev)
            last_symptom_day = day
            if ur.random() < min(1.0, symptom_visit_p * access_mult * lit_factor):
                emit("APPOINTMENT", day, "hazard", severity=sev)
        elif episode_open:
            if a < sym_thr - sym_hyst:
                episode_open = False
                emit("REMISSION", day, "treatment_response", severity=_severity_from_activity(a, bins))
            elif day - last_symptom_day >= sym_recur:
                # sustained activity => ongoing symptom burden (ties symptom count to time-above-threshold)
                emit("SYMPTOM", day, "hazard", severity=_severity_from_activity(a, bins))
                last_symptom_day = day

        # --- ED / hospitalization hazard (ramps in above a=0.6; amplified by poor access) ---
        ed_ramp = max(0.0, (a - 0.6) / 0.4)
        ed_haz = ed_base * ed_ramp * (ed_low_access if patient.clinic_access == 0 else 1.0)
        if ed_ramp > 0 and ur.random() < ed_haz:
            sev = _severity_from_activity(a, bins)
            emit("EMERGENCY_VISIT", day, "hazard", severity=sev)
            if ur.random() < admit_p:
                emit("HOSPITALIZATION", day, "hazard", severity=max(3, sev))
                if ur.random() < icu_p:
                    emit("PROCEDURE", day, "hazard", severity=4)
                # admission usually triggers escalation
                emit("MEDICATION_CHANGE", day, "treatment_response", severity=sev,
                     med=steroid, freq="taper")
                pending_escalations.append((day + steroid_lag, esc_effect))

        # --- scheduled outpatient ---
        if day > 0 and (day - outpatient_phase) % outpatient_interval == 0:
            if ur.random() < min(1.0, access_mult * (0.5 + 0.5 * adher)):
                emit("APPOINTMENT", day, "scheduled", severity=_severity_from_activity(a, bins))
                if ur.random() < lab_p:
                    emit("LAB", day, "scheduled")
                if ur.random() < img_p:
                    emit("IMAGING", day, "scheduled")

        # --- maintenance infusion ---
        if infusion_interval and day > 0 and (day - infusion_phase) % int(infusion_interval) == 0:
            if ur.random() < min(1.0, access_mult * (0.6 + 0.4 * adher)):
                emit("INFUSION", day, "scheduled", med=maint_drug, freq="maintenance")

        # --- medication refill (adherence-gated; a miss is a treatment lapse) ---
        if day > 0 and (day - refill_phase) % refill_interval == 0:
            if ur.random() < adher * (0.7 + 0.3 * access_mult):
                emit("REFILL", day, "refill", med=maint_drug)
            else:
                a = min(1.0, a + refill_lapse_bump)  # lapse nudges activity up

    return events
