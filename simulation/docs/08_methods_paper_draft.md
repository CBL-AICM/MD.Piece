# Reducing Information Friction Between Patients and Clinicians with a Health-Event Record: An In-Silico Digital-Twin Evaluation

**Draft methods paper · v0.1** · generated from simulation `config_hash 6e5c84dbb48d`, seed 20260606.

> **Status:** working draft for internal review. All quantitative results are from a
> *microsimulation*, not human data, and support **no clinical claim**. Numbers are
> reproducible from the committed code + config (`python -m simulation.run_study`).

---

## Structured abstract

**Background.** Chronic-disease care depends on an accurate account of what has happened to the
patient between visits. Two failure modes degrade that account: patients *forget* (retrospective
recall decay) and prospective tools are *incompletely used* (logging burden, dropout, non-adoption).
Whether a Health-Event–based record (MD.Piece) reduces net "information friction" relative to
unaided recall is unknown and difficult to study directly.

**Objective.** To build a transparent, fully-parameterized behavioral microsimulation ("digital
twin") that contrasts, against a hidden ground truth, the health-story fidelity of (i) unaided
patient recall and (ii) a prospective Health-Event record — and to characterize *where* the record
helps or harms, and *which assumptions* the conclusion depends on.

**Methods.** We simulated 3,200 virtual patients with one of seven chronic diseases (specialty-clinic
case mix) at daily resolution over 12 months. A coupled disease/utilization engine (Ornstein–Uhlenbeck
latent activity, self-exciting Hawkes flares, seasonal infections, adherence/access-gated care)
produced a lossless ground-truth event stream. Two lossy "observers" transformed it: a *recall*
observer (salience-weighted forgetting, temporal telescoping, severity regression) and an *MD.Piece*
observer (engagement-gated prospective logging, date-accurate, subject to onboarding failure and
dropout). Eight behavioral personas governed both observers; non-adoption and dropout were treated
as MD.Piece outcomes, not censored. A clinician engine modeled last-mile friction, with understanding
discounted by record accuracy. Primary endpoint was a per-patient Clinical Reconstruction Score
(CRS); we report paired MD.Piece−recall differences with bootstrap intervals, stratified by persona
and disease, plus one-at-a-time and global (Sobol) sensitivity analyses and pre-specified bias checks.

**Results.** Across 139,914 ground-truth events, MD.Piece showed higher composite reconstruction
fidelity than recall (CRS 0.454 vs 0.344; Δ +0.110, 95% CI +0.103 to +0.117) but **lower raw event
completeness** (event-recall rate 0.341 vs 0.467; Δ −0.126). Simulated clinician understanding was
**equivalent** once accuracy was accounted for (0.218 vs 0.215; Δ +0.002, CI −0.010 to +0.014). The
effect was a **crossover**, not a uniform lift: MD.Piece strongly benefited caregiver-managed
(ΔCRS +0.44) and high-engagement personas and harmed technology-avoidant (−0.13) and low-engagement
patients; 64% of patients were helped. The aggregate sign was decided by notification-recovery
effectiveness (the only parameter whose plausible range flipped the sign); global Sobol indicated an
essentially additive response surface (ΣS1 ≈ 1.0) dominated by notification recovery (total-order
index 0.40), patient-memory strength (0.28), and onboarding completion (0.24). A full-adoption,
no-dropout upper bound reached ΔCRS +0.235, quantifying the engagement penalty.

**Conclusions.** In silico, a Health-Event record is **not a universal improvement** over patient
recall: it trades completeness for accuracy and yields comparable clinician understanding overall.
Its value is **conditional and targetable** — robust for caregiver-mediated and engaged patients,
adverse for the disengaged — and fragile to engagement parameters that a real study has not yet
measured. We provide the model as an open, adjustable platform for hypothesis generation and
power/targeting analysis prior to clinical evaluation.

---

## 1. Introduction

Between-visit information loss is a recognized driver of diagnostic delay and miscommunication in
chronic disease. Patients reconstruct months of symptoms, medication changes, and acute events from
memory, which is known to be incomplete and systematically biased (omission of low-salience events,
telescoping of dates, regression of remembered severity). Prospective patient-facing records promise
to capture events as they happen, but their real-world value is bounded by adoption and sustained
engagement — both historically poor for health applications.

These two loss processes operate at different times and in different directions, so the net effect of
a prospective record is genuinely uncertain and not resolvable by intuition. Direct clinical
comparison is expensive and confounded (patients who adopt apps differ systematically from those who
do not). We therefore built a transparent simulation in which the ground truth is known by
construction, every loss mechanism is explicit and adjustable, and the adoption confound is modeled
so it can be analytically removed. Our aim is **not** to estimate a clinical effect size but to (a)
test the internal logic of the information-friction theory, (b) identify the patient segments and
parameters that decide the outcome, and (c) generate falsifiable, pre-registered hypotheses for a
future human study.

## 2. Methods

### 2.1 Design and estimand
A three-arm, within-subject in-silico study: `GROUND_TRUTH` (hidden reference), `PATIENT_RECALL`, and
`MDPIECE`. Following the ICH E9(R1) framework, the estimand is the per-patient paired difference
(MD.Piece − recall) in information-fidelity endpoints versus ground truth, summarized over a 3,200-patient
target population (specialty-clinic case mix) and stratified by persona, disease, severity, literacy,
and caregiver status. Intercurrent events (app dropout, non-adoption) are part of the MD.Piece arm.

### 2.2 Virtual population (L1)
Patients were sampled with disease-conditioned demographics and a single latent "advantage" factor
loading (Gaussian copula) onto socioeconomic status, education, health and technology literacy,
clinic access, and adherence, with per-axis residuals so literacies could dissociate. This induces a
**deliberate adoption-selection confound** that downstream analysis adjusts for.

### 2.3 Disease and utilization (L2+L3, coupled)
Latent disease activity a(t)∈[0,1] followed an Ornstein–Uhlenbeck process reverting to a
severity-set baseline, with the reversion target modulated upward by active infections and missed
refills and downward by treatment escalation. Flares followed a self-exciting Hawkes process with
branching ratio < 1 (background rate auto-calibrated so the stationary flare rate equals each
disease's registry relapse rate); infections followed a seasonal Poisson hazard. Utilization combined
a scheduled clock (outpatient/infusion/refill, adherence- and access-gated) with an activity-driven
ED/admission hazard amplified by poor access (ED substitution). Disease parameters were specified per
condition (NMOSD, MS, SLE, RA, Crohn's, myasthenia gravis, other) in a versioned registry with
ICD-10 anchors.

### 2.4 Personas (L4)
Each patient received one of eight behavioral personas (Perfect Logger, Normal, Symptom-Driven,
Anxious, Low-Engagement, Technology-Avoidant, Caregiver-Managed, Elderly Low-Literacy), assigned by a
softmax conditional on attributes (not uniformly), wiring the adoption confound. Each persona defines
a distribution (not fixed constants) over logging probability, retention, recall accuracy,
medication-recall accuracy, symptom-report accuracy, notification response, and engagement.

### 2.5 Information-friction observers (L5) and usage (L6)
The **recall** observer reconstructs the year at the final visit; event retention follows
salience-weighted forgetting `p_keep = floor + (1−floor)·exp(−Δt/τ)` with `floor = salience·recall_accuracy`
and `τ = τ_base·(0.5+recall_accuracy)`; surviving events undergo telescoping and severity regression,
with graded medication loss and occasional false memories. The **MD.Piece** observer logs each event
the day it occurs with probability `logging_prob·engagement(t)·coupling (+caregiver_boost)`, where the
engagement gate from the usage engine (persona-dependent onboarding, log-logistic dropout, flare
re-engagement, caregiver floor) encodes non-adoption and dropout; logged events are date-accurate but
carry small mis-entry; notifications recover a fraction of would-be-omitted events as delayed,
memory-sourced logs.

### 2.6 Clinician interaction (L8)
Physicians (six personas × specialty by disease) reviewed each arm's snapshot with persona-specific
probability and attention budget. Understanding was a saturating function of usable signal
(completeness degraded by low signal-to-noise) capped by reading budget, and **discounted by record
accuracy** so that complete-but-misdated records yield false confidence rather than understanding.

### 2.7 Outcomes
Per-patient, per-arm versus ground truth: information completeness (salience-weighted), event-recall
rate (sensitivity), precision/F1 (guarding against fabrication), graded medication-recall accuracy,
timeline accuracy and ordering (Kendall's τ), a composite Clinical Reconstruction Score, an
Information Friction Score (weighted loss, lower better, including an unreviewed-fraction term), and
clinician understanding/time-to-understanding.

### 2.8 Analysis
Paired MD.Piece−recall differences with 1,000-sample bootstrap intervals over patients, stratified by
all design factors, plus an adoption-adjusted (reweighted) estimate. Sensitivity: one-at-a-time
sweeps over the probability registry (sign-flip detection) and a global variance-based Sobol analysis
(Saltelli estimator, scipy quasi-Monte-Carlo, N=64, 384 evaluations) reporting first- and total-order
indices. Pre-specified bias checks: uniform-versus-clinical salience weighting and a full-adoption
upper bound.

### 2.9 Reproducibility and validation
One master seed with a spawned per-patient RNG tree makes runs byte-reproducible and worker-invariant;
no research constant is hard-coded (all in four YAML registries). Validation comprised face checks
(registry-calibrated flare rates, monotone severity–event-load, pessimistic retention curves),
internal-consistency checks (the adoption confound present and measurable; recall decaying with event
age), and a **parity bias gate (V-SANITY)**: reducing MD.Piece to the recall process drives the
effect to ≈0, proving the metric machinery is unbiased. All checks are enforced as automated tests
(32 passing).

## 3. Results

### 3.1 Generation
3,200 patients produced 139,914 ground-truth events (≈43/patient). Simulated per-disease flare rates
matched registry targets; event load rose monotonically with baseline severity; poor clinic access
produced higher ED utilization; app retention was pessimistic (onboarded 66%; month-1 53%, month-3
41%, month-12 29%).

### 3.2 Primary estimand (paired, MD.Piece − recall)

| Endpoint | Recall | MD.Piece | Δ (95% CI) |
|---|---|---|---|
| Clinical Reconstruction Score | 0.344 | 0.454 | **+0.110** (+0.103, +0.117) |
| Event Recall Rate | 0.467 | 0.341 | **−0.126** (−0.137, −0.116) |
| Information Friction Score (↓ better) | 0.621 | 0.514 | **−0.107** (−0.113, −0.101) |
| Doctor Understanding | 0.215 | 0.218 | +0.002 (−0.010, +0.014) |

MD.Piece captured fewer events but recorded them more accurately (dates, medications); composite
fidelity and total information friction favored MD.Piece, while raw completeness favored recall, and
clinician understanding was equivalent.

### 3.3 Effect heterogeneity (crossover)

ΔCRS by persona: Caregiver-Managed **+0.44**, Perfect Logger +0.32, Anxious +0.25, Symptom-Driven
+0.10, Normal +0.07, Elderly-Low-Literacy +0.03, Low-Engagement **−0.05**, Technology-Avoidant
**−0.13**. MD.Piece improved the record for 64% of patients and degraded it for 36%. By disease the
effect was uniformly modest-positive (ΔCRS +0.09 to +0.13), i.e. the heterogeneity is behavioral, not
nosological.

### 3.4 Sensitivity and global Sobol
Only **notification-recovery** flipped the aggregate sign within its plausible range (ΔCRS −0.02 at 0
to +0.16 at 0.5). Stronger patient memory collapsed the advantage (ΔCRS +0.16 → +0.04 as recall τ
rose). Global Sobol indicated an essentially additive surface (ΣS1 ≈ 1.0; negligible interactions),
with total-order indices: notification recovery 0.40, recall-memory strength 0.28, onboarding
completion 0.24, retention median 0.03 — corroborating the one-at-a-time ranking.

### 3.5 Bias checks
Uniform salience weighting barely changed the result (ΔCRS +0.097 vs +0.110 clinical), indicating the
conclusion is not an artifact of the salience table. The full-adoption, no-dropout upper bound reached
ΔCRS +0.235 (and the only scenario where raw completeness favored MD.Piece), locating roughly half of
MD.Piece's potential value in the adoption/engagement gap.

## 4. Discussion

**Principal findings.** A Health-Event record is, in this model, a **completeness-for-accuracy trade**
rather than a strict improvement. It logs fewer events but with correct dates and medications;
patient recall captures more events but with telescoped dates and regressed severity. Once clinician
understanding is credited for accuracy rather than volume, the two records are equivalent in
understanding — a finding that only emerged after correcting an initial metric that rewarded recall's
misdated volume as false confidence.

**Who benefits.** The dominant axis of effect is behavioral, not disease-specific. The record helps
exactly where prospective logging is sustained — caregiver-mediated and high-engagement patients —
and harms the disengaged, for whom non-logging plus dropout exceeds the recall decay it would have
prevented. This argues for **targeted deployment** (caregiver-supported and engaged segments) rather
than universal rollout, and for caregiver-proxy logging as a first-class feature.

**What the conclusion hinges on.** The aggregate sign is governed by a single, currently-unmeasured
parameter — how effectively reminders recover events that would otherwise go unlogged — and
secondarily by patient-memory decay and onboarding. The Sobol additivity result is practically useful:
because interactions are negligible, a real study can estimate these drivers independently.

**Strengths.** Full transparency and adjustability (no hard-coded research constants); an explicit,
auditable assumption registry; honest treatment of non-adoption and dropout as outcomes; an unbiased
metric gate (parity check); and a deliberately conservative design (assumption-level bias is balanced,
four assumptions favoring each arm).

**Limitations.** (1) The result is, in the limit, a function of authored parameters; we mitigate with
sensitivity/Sobol analysis and report a response surface rather than a point estimate, but external
validity is unestablished. (2) Ground truth is lossless, unlike real EHR, so absolute fidelity is
optimistic and only relative comparisons are claimed. (3) The persona→behavior table is expert
judgment (the largest researcher degree of freedom) and the top validation priority. (4) Default app
retention, though labeled pessimistic, is on the optimistic side of real health-app benchmarks at
month 1, so MD.Piece's advantage is plausibly overstated. (5) The clinician model treats each
snapshot near-cold, ignoring continuity of care, which favors any structured record. (6) Twelve-month
horizon; no mortality or competing risks. Seven of fifteen structural assumptions remain
validation-required.

**Future work.** A prospective sub-study should measure notification-recovery rate and patient-recall
decay (the two sign-determining quantities), report completeness and accuracy as separate endpoints
rather than a composite, and evaluate within the caregiver/high-engagement segments where the signal
is unambiguous. The platform supports calibrating the persona and retention parameters to real
engagement logs as they become available.

## 5. Conclusion
In a transparent digital-twin simulation, a Health-Event record did not uniformly outperform patient
recall; it improved record accuracy and composite fidelity, matched clinician understanding, and
reduced completeness, with a strongly segment-dependent, engagement-driven, and parameter-fragile
aggregate effect. The actionable message is targeting and measurement: deploy where engagement is
sustained, and measure notification recovery and recall decay before any efficacy claim.

---

### Data and code availability
All engines, registries, and analysis scripts are in `simulation/`. Results regenerate deterministically
via `python -m simulation.run_study`, `run_sensitivity`, and `run_sobol`. Generated datasets are
reproducible from code + config and are not stored in version control.

### Assumptions and reproducibility statement
Fifteen structural assumptions are catalogued with direction-of-bias in
`config/assumption_registry.yaml` (seven validation-required; assumption-level bias balanced, four
favoring each arm). Every numeric parameter resides in `config/*.yaml` and is a sensitivity-analysis
axis. This is a simulation study; it makes no clinical claim.
