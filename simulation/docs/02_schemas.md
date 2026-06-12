# Phase 2 — Data Schemas

**Status:** Phase 2 of 7. Defines every artifact's columns, dtypes, enums, and keys.
Canonical storage = Parquet (PyArrow); CSV mirrors for the deliverables list.
Authoritative machine-readable copy lives alongside this doc; implementation (Phase 5)
validates every emitted frame against these specs (fail-loud on schema drift).

## Conventions

- `event_date_*` are **integer day indices** `0..364` relative to each patient's enrolment day 0 (not wall-clock; reproducibility — see arch §3.3). A separate `calendar_date` is derived only at export so seasonality is interpretable.
- Categorical columns use closed enums (below). Unknown values are a fail-loud error, never silently coerced.
- `*_true` = ground-truth value; `*_recorded` = value as it appears in a lossy arm. In `GROUND_TRUTH` rows the two are equal by construction.
- Nullable columns are marked `?`. Floats in `[0,1]` unless noted.

---

## Enums

| Enum | Values |
|---|---|
| `disease` | `NMOSD, MS, SLE, RA, CROHN, MG, OTHER` |
| `arm` | `GROUND_TRUTH, PATIENT_RECALL, MDPIECE` |
| `event_type` | `SYMPTOM, MEDICATION_CHANGE, INFECTION, APPOINTMENT, LAB, IMAGING, HOSPITALIZATION, EMERGENCY_VISIT, PROCEDURE, TREATMENT, INFUSION, REFILL, FLARE, REMISSION` |
| `source` | `scheduled, hazard, infection, flare, treatment_response, refill, relapse` |
| `severity` | `0=none,1=mild,2=moderate,3=severe,4=critical` (ordinal int) |
| `sex` | `F, M` |
| `persona` | `PERFECT_LOGGER, NORMAL, SYMPTOM_DRIVEN, ANXIOUS, LOW_ENGAGEMENT, TECH_AVOIDANT, CAREGIVER_MANAGED, ELDERLY_LOW_LITERACY` |
| `education_level` | `0=primary,1=secondary,2=tertiary,3=postgrad` (ordinal) |
| `ses_quintile` | `1..5` (1=lowest) |
| `clinic_access` | `0=poor,1=moderate,2=good` |
| `insurance` | `NHI, NHI_PLUS_PRIVATE, UNINSURED` (Taiwan-context default; configurable) |
| `physician_persona` | `HIGHLY_ENGAGED, MODERATELY_ENGAGED, TIME_CONSTRAINED, SKEPTICAL, DATA_ORIENTED, TRADITIONAL` |
| `specialty` | `NEUROLOGY, RHEUMATOLOGY, GASTROENTEROLOGY, REHABILITATION, PRIMARY_CARE` |

---

## 1. `patients.csv` — one row / patient (PK `patient_id`)

| column | dtype | notes |
|---|---|---|
| patient_id | str | `P00001`..`P03200` |
| age | int | years |
| sex | enum sex | |
| disease | enum disease | |
| severity | int 0–4 | baseline disease severity at enrolment |
| disease_duration_yrs | float | years since diagnosis |
| comorbidity_count | int | |
| comorbidities | str | `;`-joined ICD-10 codes (via ICD-10 MCP), `?` |
| ses_quintile | int 1–5 | |
| education_level | int 0–3 | |
| health_literacy | float 0–1 | |
| tech_literacy | float 0–1 | |
| caregiver_support | float 0–1 | 0=none, 1=full-time proxy |
| clinic_access | int 0–2 | |
| insurance | enum insurance | |
| baseline_adherence | float 0–1 | |
| latent_advantage_z | float | standard-normal latent factor (arch §4 L1) — kept for adoption-adjustment in eval |
| persona | enum persona | |
| assigned_physician_id | str | FK → doctor table |

## 2. Event schema (shared by ground-truth / recall / mdpiece) — PK `event_id`

| column | dtype | notes |
|---|---|---|
| event_id | str | unique per (arm,row) |
| patient_id | str | FK |
| arm | enum arm | |
| true_event_id | str? | **linkage key**: maps a recalled/logged row back to its ground-truth event. NULL ⇒ false logging (FP). A ground-truth `event_id` absent from an arm ⇒ omission (FN). |
| event_type | enum event_type | |
| event_date_true | int | day index 0–364 |
| event_date_recorded | int? | as recorded in this arm (telescoping/temporal error applied) |
| severity_true | int 0–4? | for symptom/flare events |
| severity_recorded | int 0–4? | regression-to-mild applied in lossy arms |
| medication | str? | drug name / code |
| dose | str? | |
| frequency | str? | |
| source | enum source | causal origin in the generator |
| salience | float 0–1 | clinical-relevance weight (drives forgetting + eval weighting) |
| is_omitted | bool | true only in lossy arms where event dropped (row may be absent instead; see note) |
| is_false | bool | true ⇒ fabricated (recall-only mostly) |
| temporal_error_days | int | `event_date_recorded − event_date_true` (signed; neg = telescoped earlier) |
| logged_lag_days | int? | mdpiece only: delay between event and log |

> **Representation rule:** omissions are represented by **absence** of the row in the lossy arm (the natural FN), *plus* a mirror in `information_friction.csv`. `is_omitted` is retained only in a diagnostic long-form export for auditing the loss process. This avoids ambiguity in recall/precision computation.

## 3. `ground_truth_events.csv`
Event schema filtered to `arm=GROUND_TRUTH`. Lossless. The evaluation reference.

## 4. `patient_recall.csv`
Event schema filtered to `arm=PATIENT_RECALL`.

## 5. `health_events.csv`
All three arms in event schema (the union; the join surface for evaluation).

## 6. `timeline.csv` — Health-Event view (L7), one row / (patient, arm, episode)

| column | dtype | notes |
|---|---|---|
| patient_id, arm | | |
| episode_id | str | contiguous clinical episode (e.g. flare→escalation→recovery) |
| episode_start_day, episode_end_day | int | |
| episode_type | str | dominant driver (flare/infection/relapse/stable) |
| event_ids | str | `;`-joined member events |
| n_events | int | |
| completeness_vs_truth | float 0–1 | episode-level fidelity (eval-filled) |

## 7. `doctor_snapshot.csv` — one row / (patient, arm, visit)

| column | dtype | notes |
|---|---|---|
| patient_id, arm, physician_id | | |
| visit_day | int | |
| n_events_presented | int | events available in this arm up to visit |
| snapshot_signal_to_noise | float | salience-weighted / total presented |
| summary_length_tokens | int | simulated snapshot size |

## 8. `doctor_interaction.csv` — one row / (patient, arm, visit)

| column | dtype | notes |
|---|---|---|
| patient_id, arm, physician_id, visit_day | | |
| physician_persona, specialty | enums | |
| review_probability | float 0–1 | |
| reviewed | bool | |
| reading_time_sec | int | |
| trust_score | float 0–1 | |
| actionability_score | float 0–1 | |
| snapshot_engagement | float 0–1 | |
| doctor_understanding | float 0–1 | derived (arch L8) |
| time_to_understanding_sec | int? | NULL if threshold never reached |

## 9. `app_usage.csv` — one row / (patient, week) [mdpiece arm only]

| column | dtype | notes |
|---|---|---|
| patient_id | str | |
| week | int 0–51 | |
| active | bool | engaged this week |
| n_logs | int | events logged this week |
| notifications_sent, notifications_responded | int | |
| caregiver_assisted | bool | |
| reengaged_by_flare | bool | |

## 10. `retention.csv` — cohort retention summary

| column | dtype | notes |
|---|---|---|
| persona | enum persona | + an `ALL` row |
| retained_d1, retained_w1, retained_m1, retained_m3, retained_m6, retained_m12 | float 0–1 | fraction still active |
| median_lifetime_days | float | |

## 11. `information_friction.csv` — one row / (patient, arm)

| column | dtype | notes |
|---|---|---|
| patient_id, arm | | |
| event_omission_rate | float 0–1 | |
| medication_error_rate | float 0–1 | |
| temporal_error_mean_days | float | |
| severity_error_rate | float 0–1 | |
| unreviewed_fraction | float 0–1 | doctor-side (L8) |
| information_friction_score | float 0–1 | weighted composite (arch §2.3); **lower = better** |

## 12. `evaluation_metrics.csv` — one row / (patient, arm)

| column | dtype | notes |
|---|---|---|
| patient_id, arm | | |
| information_completeness | float 0–1 | |
| event_recall_rate | float 0–1 | sensitivity |
| precision | float 0–1 | guards against false-logging wins |
| f1 | float 0–1 | |
| medication_recall_accuracy | float 0–1 | graded drug>dose>freq |
| timeline_accuracy | float 0–1 | 1 − normalized temporal error |
| ordering_tau | float −1..1 | Kendall τ on event sequence |
| clinical_reconstruction_score | float 0–1 | headline composite |
| doctor_understanding | float 0–1 | |
| time_to_understanding_sec | int? | |

> A companion **wide** export `evaluation_paired.csv` pivots arm to columns and adds
> `mdpiece_minus_recall_*` paired differences per metric (the primary estimand, arch §1.2).
