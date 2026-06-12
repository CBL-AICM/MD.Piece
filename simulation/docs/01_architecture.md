# MD.Piece Real-World Digital Twin Simulation Platform
## Phase 1 — Research-Grade System Architecture

**Status:** Phase 1 of 7 (Architecture). No engine code written yet — by design.
**Document owner role:** Principal Healthcare Data Scientist / Digital Twin Architect
**Version:** 0.1 (Design)
**Audience:** clinical informatics reviewers, methodologists, engineers who will implement Phases 5–7.

> **Read this first — the honest framing.** This platform is a *behavioral microsimulation*, not a proof. Its conclusion about whether MD.Piece reduces information friction is **a function of the friction and capture parameters we choose**. The scientific value is therefore **not** a single point estimate ("MD.Piece is 34% better"). The value is the **response surface**: under *which* regimes of patient behavior, disease severity, and adoption does a Health-Event record beat unaided recall, and where does it fail? A platform that can only produce a positive result is worthless. This one is explicitly built to be able to produce a *negative* result. See §11 (Threats to Validity) before trusting any output.

---

## 0. Document map

| § | Section | Phase handoff |
|---|---------|---------------|
| 1 | Research framing, estimands, hypotheses | — |
| 2 | Conceptual model & causal structure | — |
| 3 | Architecture overview & data flow | → Phase 5 |
| 4 | Layer specifications (L1–L8) | → Phase 5 |
| 5 | The three-record paradigm & ground truth | — |
| 6 | Data model / schema preview | → Phase 2 |
| 7 | Probability-model strategy | → Phase 3 |
| 8 | Evaluation framework (metric definitions) | → Phase 7 |
| 9 | Registries (assumption / probability / persona / disease) | → Phase 2–3 |
| 10 | Validation, sensitivity & bias frameworks | → Phase 7 |
| 11 | **Threats to validity & known weaknesses** | — |
| 12 | Open decisions requiring clinical sign-off | — |
| 13 | Execution roadmap & determinism contract | → Phase 4–6 |

---

## 1. Research framing

### 1.1 Research question (restated precisely)

> Does a **Health-Event–based prospective record** (MD.Piece) reconstruct a chronic-disease patient's 12-month health story with **lower information loss** than **unaided retrospective recall**, when both are compared against a hidden ground truth, across a realistic distribution of patient behavior and disease trajectories?

### 1.2 Estimand (what number are we actually after)

We frame this with the ICH E9(R1) estimand framework to avoid a vague "accuracy" claim.

- **Population:** 3,200 simulated chronic-disease patients (6 index diseases + "other"), 12-month horizon, daily resolution.
- **Treatment / conditions compared (3 arms, within-subject):** `GROUND_TRUTH` (reference), `PATIENT_RECALL`, `MDPIECE`.
- **Endpoint family:** per-patient information-fidelity metrics (§8) computed against ground truth.
- **Population-level summary:** paired difference `MDPIECE − PATIENT_RECALL` per metric, summarized as mean + 95% interval over patients, **and** stratified by persona, disease, severity, health/tech literacy, and caregiver status.
- **Intercurrent events:** app **dropout** and **non-adoption** are *part of the MD.Piece arm*, not censored away. A patient who installs the app and abandons it in week 2 is a real MD.Piece outcome and must drag the MD.Piece arm down. Handling them as "missing" would be the single biggest way to cheat.

### 1.3 Hypotheses (pre-registered, including the null and the failure modes)

- **H1 (primary):** Mean Event Recall Rate is higher for `MDPIECE` than `PATIENT_RECALL`.
- **H0 (null, taken seriously):** No difference, or MD.Piece is *worse* for low-engagement / technology-avoidant personas because prospective logging burden + dropout exceeds the recall decay it prevents.
- **H2 (effect heterogeneity — the real story):** The MD.Piece advantage is **conditional**: large for symptom-driven and caregiver-managed personas, near-zero or negative for low-engagement and technology-avoidant personas. We expect a *crossover* interaction, not a uniform lift.
- **H3 (clinical, downstream):** Higher record fidelity raises the simulated **Doctor Understanding / Actionability** score — but with diminishing returns and a saturation ceiling (a clinician does not need 100% of events to understand the case).

> A result where MD.Piece helps everyone uniformly would be **a red flag that the friction model is too kind to the app** (see §11.3).

### 1.4 What this simulation can and cannot claim

| Can support | Cannot support |
|---|---|
| Internal consistency of the information-friction theory | That MD.Piece works for *real* patients |
| Direction & relative magnitude of effects under stated assumptions | Absolute effect sizes usable for a clinical claim |
| Which patient segments benefit / are harmed | Regulatory or marketing claims |
| Sensitivity of conclusions to each assumption | Anything not encoded in the parameters |
| Power / sample-size intuition for a *real* future study | Causal proof of mechanism in humans |

This table goes verbatim into any output report. (Rule 12: fail loud about scope.)

---

## 2. Conceptual model

### 2.1 The three-record paradigm

Everything flows from one hidden generator and two lossy observers:

```
                       ┌─────────────────────────────┐
                       │   GROUND TRUTH GENERATOR     │
                       │  (disease + utilization)     │   ← hidden, lossless
                       │  every event, dose, symptom  │
                       └──────────────┬──────────────┘
                                      │  the same lived reality
                 ┌────────────────────┴────────────────────┐
                 ▼                                          ▼
   ┌──────────────────────────┐              ┌──────────────────────────────┐
   │  PATIENT RECALL OBSERVER  │              │     MD.PIECE OBSERVER         │
   │  retrospective, at-visit  │              │  prospective, day-of logging  │
   │  memory decay + salience  │              │  engagement + dropout + recall│
   │  bias + telescoping       │              │  -at-logging + caregiver help │
   └────────────┬─────────────┘              └───────────────┬──────────────┘
                ▼                                             ▼
       PATIENT_RECALL dataset                          MDPIECE dataset
                └────────────────────┬────────────────────────┘
                                     ▼
                         EVALUATION vs GROUND TRUTH
```

**Critical design principle (the anti-strawman rule):** MD.Piece is **not** a perfect recorder. It is a *second lossy observer with a different loss profile*. Recall loses information **at the visit** (weeks/months after events, all at once, via memory). MD.Piece loses information **at the moment of each event** (via non-logging, dropout, mis-entry) but then **preserves what was logged without further decay**. The whole research question is whether prospective-but-incomplete beats complete-but-decayed. If we model MD.Piece as lossless, we have answered nothing.

### 2.2 Causal DAG of information loss

```
 health_literacy ─┐         ┌─► logging_probability ─┐
 tech_literacy ───┼─► persona┤                        ├─► MDPIECE completeness
 caregiver ───────┘         └─► dropout_hazard ──────┘
        │                                   ▲
        │                                   │ flare-driven re-engagement
 age, SES, access ─► disease severity ─► event_rate ─► (more events = more to lose)
        │                                   │
        └──────► recall_decay_rate ◄────────┘ salience(event_type) modulates decay
```

Confounders we must model explicitly so the MD.Piece "benefit" is not an artifact:
- **Adoption selection:** more literate / supported patients both adopt MD.Piece *and* recall better. If we don't model this, MD.Piece looks good partly because good rememberers use it. The persona layer must couple adoption to literacy so we can *adjust for it* in evaluation (stratified + a marginal estimate).
- **Severity ↔ salience:** sicker patients have more events (more to forget) but also more *salient* events (better remembered). Net effect is ambiguous — must emerge from the model, not be assumed.

### 2.3 Operational definition of "Information Friction"

"Information friction" is otherwise a slogan. We define it as a measurable construct:

> **Information Friction (IF)** = the fraction of clinically-relevant ground-truth information that fails to reach the clinician's working understanding at the point of care, weighted by clinical salience.

Decomposed into additive, separately-measurable components (§8.6):
`IF = w₁·EventOmission + w₂·MedicationError + w₃·TemporalError + w₄·SeverityError + w₅·UnreviewedFraction`
where the last term is contributed by the **doctor engine** (information captured but not read is still friction). Weights `w` are in the assumption registry and are a primary sensitivity-analysis target.

---

## 3. Architecture overview

### 3.1 Module map (matches the prescribed `simulation/` tree)

```
simulation/
├── config/              # YAML configs: population, disease params, persona table, friction, weights, seeds
├── patients/            # L1 Patient Generator → patients.csv
├── disease_engine/      # L3 Disease Progression + L2 Utilization (tightly coupled; see §3.3)
├── persona_engine/      # L4 Persona assignment + L6 App Usage/retention
├── friction_engine/     # L5 Information Friction: the two observers (recall + mdpiece capture)
├── usage_engine/        # L6 engagement/retention curves feeding the mdpiece observer
├── doctor_engine/       # L8 Doctor interaction + snapshot review
├── evaluation/          # metrics, comparison, sensitivity, bias, validation
├── outputs/             # all CSV/Parquet artifacts
└── docs/                # this document + registries
```

> **Design note / deviation flagged (Rule 7 — surface conflicts):** the prescribed tree lists L2 (utilization) and L3 (disease) as conceptually separate but **they cannot be independently simulated** — an ED visit is *caused by* a flare; a refill gap *causes* a flare. We therefore implement them as one coupled **`disease_engine`** with two sub-modules sharing state, rather than two engines that would need a fragile event bus between them. This is a deliberate, documented departure from a naive 1-folder-per-layer mapping. Layer 7 (Health-Event formatting) is **not an engine** — it is a *serialization view* over ground truth + the two observers, so it lives in `evaluation/` / `outputs/` as a transform, not a generator.

### 3.2 Data flow (generative pipeline, strict order)

```
seed → L1 patients ─► L4 persona assignment ─► L2+L3 disease/utilization timeline (GROUND TRUTH)
                                                        │
                                                        ├─► L5a recall observer  ──► PATIENT_RECALL
                                                        ├─► L6 usage ─► L5b mdpiece observer ──► MDPIECE
                                                        │
                                              L7 health-event view (all three) ─► L8 doctor engine
                                                        │
                                                        └─► evaluation ─► metrics, friction, comparison
```

Each arrow is a pure, seeded transform. No step mutates an upstream artifact. This makes the pipeline **resumable and auditable**: every CSV can be regenerated from `(config, seed, upstream CSV)`.

### 3.3 Determinism & reproducibility contract (non-negotiable)

- **One master seed** in `config/seeds.yaml`. Per-patient RNG is `np.random.default_rng(master_seed)` **spawned** via `SeedSequence(master_seed).spawn(n_patients)` so patient *i*'s stream is independent of *n* and of execution order (parallel-safe, reproducible regardless of worker count).
- **No wall-clock, no `Math.random`, no global `np.random.seed`.** All randomness threads through the spawned generators.
- **Config is the only knob.** No research constant is hard-coded in engine code. Every probability lives in `config/*.yaml` and is mirrored into the Probability Registry (§9.2). Rule: *if a number influences a result, it is in config and in the registry.*
- **Artifacts are content-addressed by config hash.** `outputs/<config_hash>/...` so a result is never silently produced by a different parameter set.

---

## 4. Layer specifications

Each layer below states: **Responsibility · Inputs · Outputs · Key parameters · Assumptions to challenge.**

### L1 — Patient Generator (`patients/`)

- **Responsibility:** sample 3,200 patients with internally-consistent attributes (literacy correlates with education correlates with SES, etc.) — *not* 15 independent marginal draws.
- **Inputs:** `config/population.yaml`, per-disease prevalence & demographics.
- **Outputs:** `patients.csv` (schema §6.1).
- **Key parameters:** disease mix, age/sex distributions per disease, joint distribution of {SES, education, health_literacy, tech_literacy}, caregiver-support prevalence by age, clinic-access distribution.
- **Method:** sample disease → sample disease-conditioned demographics → draw a **latent "advantage" factor** `z ~ N(0,1)` per patient that loads onto SES, education, both literacies, and access (a single-factor copula). This is what creates the **adoption-selection confound on purpose** so evaluation can adjust for it. Baseline adherence drawn conditional on literacy + caregiver.
- **Assumptions to challenge:** Is a single latent factor too crude? (It collapses health literacy and tech literacy, which dissociate in elderly patients — an elder may be health-literate but tech-avoidant. We allow a per-axis residual so they can diverge. Flagged for validation.) Disease prevalences are **not** general-population (this is a specialty/clinic-recruited cohort) — see §9.4 disease registry for sourcing and the over-representation of rare diseases (NMOSD, MG) typical of a specialty platform.

### L2 — Healthcare Utilization Engine (within `disease_engine/`)

- **Responsibility:** generate scheduled + unscheduled encounters: outpatient, specialist, ED, admission, infusion, labs, imaging, refills.
- **Inputs:** patient attributes, disease state (from L3, same tick), access/insurance.
- **Outputs:** encounter events into the ground-truth event stream.
- **Key parameters:** baseline outpatient interval per disease (e.g. infusion every 4 wk for NMOSD on rituximab vs 6-monthly), ED-propensity multiplier per persona/severity, admission probability given flare severity, refill schedule per medication.
- **Method:** two clocks — a **scheduled clock** (periodic visits, infusions, refills) and a **hazard-driven clock** (ED/admission as a function of current disease activity). Access & insurance gate whether a *needed* visit actually happens (a low-access patient's flare → delayed care → worse trajectory: this is where social determinants enter).
- **Assumptions to challenge:** ED propensity is one of the least literature-anchored numbers; flagged high-priority for sensitivity analysis.

### L3 — Disease Progression Engine (`disease_engine/`)

- **Responsibility:** the latent disease-activity process and its event chains (infection → worsening → escalation → recovery).
- **Inputs:** patient (disease, severity, duration, comorbidities), medication state, utilization (treatment received).
- **Outputs:** symptom events, flares, remissions, infections, treatment changes into ground truth.
- **Method:** a per-patient **latent disease-activity** continuous state `a(t) ∈ [0,1]` evolving daily as a mean-reverting process (OU-like) with disease-specific drift toward a severity-set baseline, **plus discrete shocks**: infections (seasonal hazard), flares (self-exciting / Hawkes-like — a flare raises near-term flare risk), and treatment effects (escalation pushes `a` down with a lag). Crossing thresholds emits discrete clinical events. Relapsing-remitting diseases (MS, NMOSD) get an explicit relapse hazard; progressive components get slow drift.
- **Disease event chain (canonical example, encoded as a guarded transition, not an LLM):**
  `infection(t) → +Δactivity over [t, t+7] → symptom threshold crossed → unscheduled visit pulled earlier → steroid escalation → −Δactivity with 3–5d lag → recovery`. This is deterministic conditional logic (Rule 5: no model in the loop; status/threshold logic is plain code).
- **Assumptions to challenge:** Hawkes self-excitation parameter, infection seasonality amplitude, and steroid-response lag are disease-specific and weakly sourced — all in the registry with `validation_required: true`.

### L4 — Persona Engine (`persona_engine/`)

- **Responsibility:** assign each patient one of 8 behavioral personas and the behavioral parameter vector that drives both observers.
- **Inputs:** patient attributes (esp. literacies, age, caregiver, anxiety proxy).
- **Outputs:** `persona`, behavioral params: `logging_prob`, `retention_hazard`, `recall_accuracy`, `med_recall_accuracy`, `symptom_report_accuracy`, `notification_response`, `engagement_level`.
- **Personas:** Perfect Logger, Normal User, Symptom-Driven, Anxious, Low-Engagement, Technology-Avoidant, Caregiver-Managed, Elderly Low-Literacy.
- **Method:** persona assignment is **probabilistic conditional on attributes**, not random — an 80-year-old with low tech literacy and a caregiver is *likely* Caregiver-Managed or Elderly Low-Literacy. This is what wires the adoption-selection confound. Each persona is a *distribution* of behavioral params (mean + spread), not fixed constants, so within-persona heterogeneity exists.
- **Assumptions to challenge:** the entire persona→parameter table is expert-judgment, not measured. This is the **single largest source of "researcher degrees of freedom"** and the #1 sensitivity-analysis and external-validation target (§9.3, §11.2).

### L5 — Information Friction Engine (`friction_engine/`) — *the core*

Two observers, one shared loss vocabulary.

- **Responsibility:** transform ground truth into each lossy dataset.
- **Loss primitives (apply to both observers with different rates):**
  - event **omission** (event never makes it into the record)
  - medication **omission / wrong dose / wrong frequency**
  - **temporal error** (wrong date; *telescoping* — recalled as more recent than actual)
  - **severity misreport** (regression toward "mild")
  - **false logging** (event recorded that did not happen — rare, recall-only mostly)
  - **incompleteness** (whole episodes dropped)
- **5a Recall observer:** applies a **memory model** at the moment of each clinic visit. Retention of event *e* recalled at visit time `t_v` ≈ `S(e) · exp(−(t_v − t_e)/τ(persona))` (salience-weighted Ebbinghaus forgetting), where salience `S` is high for hospitalizations/ED/new diagnoses, low for a single mild symptom day or one missed dose. Telescoping shifts surviving events' dates toward `t_v`. Severity regresses toward the mean.
- **5b MD.Piece observer:** applies a **logging model** at the moment of each event: event logged with `logging_prob × engagement(t) × (1 + caregiver_boost)`, gated by whether the patient is still **retained** (L6 dropout). Once logged, **no further decay** (the app's core value), but mis-entry at logging time still applies at a low rate. Notification response can *recover* some would-be-omitted events (a reminder prompts a late log) — with a realism cap and a `delayed_logging` timestamp penalty.
- **Information Friction Score:** computed per patient per arm (§8.6) and emitted to `information_friction.csv`.
- **Assumptions to challenge:** the forgetting time-constant `τ`, the salience weights, and the "no decay after logging" idealization (real apps have data-entry fatigue → quality decay even among loggers; we add a mild logged-quality decay term so MD.Piece isn't unfairly perfect).

### L6 — App Usage Engine (`usage_engine/`)

- **Responsibility:** realistic adoption → engagement → dropout trajectory feeding 5b.
- **Outputs:** `app_usage.csv` (daily/weekly engagement), `retention.csv` (cohort retention at D1/W1/M1/M3/M6/M12).
- **Method:** survival model for retention with a **declining hazard** (most dropout is early — classic app retention is steep then flattens), persona-specific median lifetime, **flare-driven re-engagement** (a flare transiently spikes engagement — sick patients log more), and caregiver-assisted engagement (caregiver keeps an otherwise-dropped patient active). Retention curves should reproduce the well-known shape where M1 retention for health apps is low (often <30%) — we deliberately make the *average* user unimpressive so MD.Piece has to earn any benefit.
- **Assumptions to challenge:** real digital-health retention is notoriously poor; if our curves are too optimistic, every MD.Piece result is inflated. Retention is therefore a headline sensitivity axis. (§11.3)

### L7 — Health Event view (transform in `outputs/`/`evaluation/`)

- **Responsibility:** serialize each arm into the MD.Piece Health-Event schema (Symptom, MedicationChange, Infection, Appointment, Laboratory, Hospitalization, EmergencyVisit, Procedure, Treatment, Infusion) and assemble **Timeline → Episode → Health Story → Doctor Snapshot**.
- **Note:** this is a pure view, applied identically to all three arms so differences come only from upstream loss, never from formatting.

### L8 — Doctor Interaction Engine (`doctor_engine/`)

- **Responsibility:** model the *last mile* of friction — information that reached the record but not the clinician's understanding.
- **Physician personas:** Highly/Moderately Engaged, Time-Constrained, Skeptical, Data-Oriented, Traditional × specialties {Neuro, Rheum, GI, Rehab, Primary}.
- **Outputs:** `doctor_snapshot.csv`, `doctor_interaction.csv` with `review_probability`, `reading_time`, `trust_score`, `actionability_score`, `snapshot_engagement`, and a derived **Doctor Understanding score**.
- **Method:** understanding = f(record completeness, snapshot signal-to-noise, physician reading-time budget, trust). A time-constrained skeptical clinician may extract *less* understanding from a *more* complete record if it's noisy — so completeness has diminishing/又possibly negative returns past a point. This lets MD.Piece *lose* on the clinical endpoint even when it wins on the data endpoint (a genuinely possible, important negative result).

---

## 5. The three-record system & ground truth

- **GROUND_TRUTH:** lossless, hidden, never exposed to recall/mdpiece/doctor generation — only to evaluation. Enforced by module boundaries: the friction and doctor engines receive ground truth *read-only* and the evaluation module is the only consumer of all three.
- **PATIENT_RECALL:** the L5a output.
- **MDPIECE:** the L5b output.
- **Leakage guard:** a test asserts the recall/mdpiece generators never read evaluation outputs and that ground truth is identical across runs with the same seed (a determinism + isolation test).

---

## 6. Data model / schema preview (Phase 2 handoff)

Long format, one row per event; arm identified by a column so all three coexist in `health_events.csv` for joins. Patient-level wide table separate.

### 6.1 `patients.csv` (one row/patient)
`patient_id, age, sex, disease, severity, disease_duration_yrs, comorbidity_count, comorbidities, ses_quintile, education_level, health_literacy, tech_literacy, caregiver_support, clinic_access, insurance, baseline_adherence, latent_advantage_z, persona`

### 6.2 Event schema (ground truth, recall, mdpiece share it)
`event_id, patient_id, arm{GROUND_TRUTH|PATIENT_RECALL|MDPIECE}, true_event_id(nullable→links recalled/logged back to truth), event_type, event_date_true, event_date_recorded, severity_true, severity_recorded, medication, dose, frequency, source{scheduled|hazard|infection|flare|...}, is_omitted, is_false, temporal_error_days, logged_lag_days, salience`
- `true_event_id` is the **linkage key** that makes recall/precision computable: a recall/mdpiece row maps to a ground-truth row (true positive), to nothing (false logging / hallucinated), and a ground-truth row with no match is an omission (false negative).

### 6.3 Other tables (columns finalized in Phase 2)
`ground_truth_events.csv, patient_recall.csv, health_events.csv, timeline.csv, doctor_snapshot.csv, doctor_interaction.csv, app_usage.csv, retention.csv, information_friction.csv, evaluation_metrics.csv`

Storage: Parquet (PyArrow) as the canonical artifact for the 50k–1M-event scale; CSV mirrors for the deliverables list. Polars optional for the join-heavy evaluation step.

---

## 7. Probability-model strategy (Phase 3 handoff)

| Phenomenon | Family | Why this family |
|---|---|---|
| Latent disease activity | Ornstein–Uhlenbeck (mean-reverting) | continuous, stationary-around-baseline, tractable |
| Flares | Hawkes / self-exciting point process | clustering: a flare begets flares |
| Infections | Non-homogeneous Poisson (seasonal λ(t)) | seasonality, rate varies over year |
| Inter-visit / inter-event times | Gamma / Weibull | flexible hazards, non-exponential |
| App retention | Discrete-time survival, declining hazard (e.g. log-logistic) | early-heavy dropout |
| Memory retention | Exponential/power forgetting × salience | Ebbinghaus form |
| Counts (events/patient) | Negative binomial | overdispersion vs Poisson |
| Binary behaviors (log? respond?) | Bernoulli w/ logit link to covariates | couples behavior to attributes |
| Attribute copula | Gaussian copula (latent z) | induces realistic correlation |

All parameters → Probability Registry (§9.2). Every distribution must be **adjustable from config** (architecture requirement).

---

## 8. Evaluation framework (metric definitions — Phase 7)

All metrics computed per patient per arm vs ground truth, then aggregated + stratified. **Linkage** via `true_event_id` (§6.2).

1. **Information Completeness** = recorded clinically-relevant info / total ground-truth clinically-relevant info (salience-weighted). [0–1]
2. **Event Recall Rate (sensitivity/recall)** = TP / (TP + FN) over events.
3. **Medication Recall Accuracy** = fraction of ground-truth med-events correctly captured with correct drug+dose+frequency (graded partial credit: drug > dose > frequency).
4. **Timeline Accuracy** = 1 − normalized temporal error; reported as median |date error| (days) and an ordering-preservation score (Kendall's τ on event sequence) — *order* often matters more clinically than exact dates.
5. **Clinical Reconstruction Score** = composite of (1)–(4) weighted by clinical salience; the headline data-fidelity number.
6. **Information Friction Score** = the §2.3 weighted loss; **lower is better** (the inverse-coded sibling of #5, but includes the doctor-side unreviewed term).
7. **False-logging / Precision** = TP / (TP + FP) — guards against an arm "winning" recall by inventing events. Report F1 too.
8. **Doctor Understanding Score** (L8) and **Doctor Engagement Score**.
9. **Time-to-Clinical-Understanding** = simulated reading time to reach an understanding threshold; a Health-Event snapshot should lower this **if** it's well-organized — and not if it's noisy.

**Comparison design:** within-subject paired differences (`MDPIECE − RECALL`), bootstrap CIs over patients, **stratified** by every L1/L4 factor, plus a **marginal (adoption-adjusted)** estimate that reweights to remove the selection confound — so we can report both "benefit among adopters" and "benefit if adoption were random," which usually differ a lot.

---

## 9. Registries

Four machine-readable registries (YAML, version-controlled, each row carries `source`, `value`, `plausible_range`, `validation_required`, `rationale`):

- **9.1 Assumption Registry** — every structural assumption (e.g. "no decay after logging", "single latent advantage factor"), its direction of bias, and how to test it.
- **9.2 Probability Registry** — every numeric parameter, its distribution, default, range, and citation status. The sensitivity analysis iterates over this file.
- **9.3 Persona Registry** — the 8 personas × 7 behavioral parameters table, marked expert-judgment, top validation priority.
- **9.4 Disease Registry** — per disease: typical age/sex, severity distribution, flare/relapse rates, standard treatments, infusion schedules, ICD-10 anchors (via ICD-10 MCP for coding fidelity). Diseases: NMOSD, MS, Lupus (SLE), RA, Crohn's, MG, Other.

> **Every registry entry defaults to `validation_required: true` until a citation is attached.** The platform must be able to print "N of M parameters are expert-judgment, not literature-anchored" — honesty about evidence base (Rule 12).

---

## 10. Validation, sensitivity & bias frameworks

- **Validation (face/internal):** (a) **face validity** — generated retention curves, flare frequencies, visit rates fall in clinically plausible ranges (checked against registry `plausible_range`); (b) **internal consistency** — e.g. sicker patients have more events; adopters skew higher-literacy; recall decays with time-since-event; (c) **determinism/leakage tests** (§5).
- **Sensitivity analysis:** one-at-a-time + a Latin-Hypercube / Sobol global sweep over the Probability Registry. Headline question: *which parameters flip the sign of the MD.Piece effect?* Those are the ones a real study must measure.
- **Bias analysis:** quantify (a) adoption-selection bias (compare crude vs adoption-adjusted estimate), (b) salience-weighting bias (results under uniform vs clinical weights), (c) the "kind-app" bias (results as MD.Piece loss rates → recall loss rates; at parity the effect must vanish — a sanity assertion).

---

## 11. Threats to validity & known weaknesses (read this before trusting output)

1. **Tautology risk (the big one).** We author both the recall-loss model and the mdpiece-capture model. The sign of the result is, in the limit, *chosen by us*. Mitigation: report the **response surface**, not a point estimate; include the parity sanity check (§10); pre-register hypotheses incl. the null (§1.3); make every loss parameter a sensitivity axis.
2. **Persona table is expert judgment.** Largest researcher-degrees-of-freedom. Mitigation: wide within-persona spreads, global sensitivity, explicit "expert-judgment" labeling, and a roadmap to calibrate against any real engagement data.
3. **"Kind-app" optimism.** Modeling MD.Piece capture as too complete, retention as too high, or post-logging decay as zero would manufacture a positive result. Mitigation: deliberately pessimistic default retention, a logged-quality decay term, dropout counted as MD.Piece outcomes (not censored).
4. **Ground truth is *too* perfect.** Real validation has no lossless reference; real EHR is itself incomplete. So absolute fidelity numbers will be optimistic vs a real study. We only claim *relative* comparisons.
5. **Independence we may be faking.** Recall errors and logging errors may be correlated within a patient (a disengaged patient both forgets and doesn't log). We model the shared `engagement/literacy` driver so the *correlation* is present, but the residual structure is assumed.
6. **No model of clinician's prior knowledge / continuity.** A regular clinician already knows the patient; our L8 treats each snapshot near-cold. This *overstates* the value of any record. Flagged.
7. **12-month horizon / no mortality, no loss-to-follow-up beyond app dropout.** Competing risks omitted in v0.1.
8. **Aggregation hides crossover.** A positive mean can hide a harmed subgroup. Mitigation: stratified reporting is mandatory, not optional.

This section is reproduced at the top of every generated evaluation report.

---

## 12. Open decisions requiring clinical / methodological sign-off

These are genuine forks where I will **not** silently pick for you (Rule 1):

- **D1 — Disease mix & prevalence:** specialty-platform skew (rare diseases over-represented) vs population-representative. Affects external validity of any aggregate. *Default proposal: specialty-clinic mix, documented.*
- **D2 — Salience weights** for the clinical-relevance weighting (who decides a "missed mild-symptom day" is worth 0.1 of a hospitalization?). Needs a clinician. *Default: a documented starting table, flagged for validation.*
- **D3 — Retention pessimism level:** which empirical retention benchmark anchors the curves. Headline sensitivity driver.
- **D4 — Whether MD.Piece in the model includes caregiver-proxy logging and OCR upload** (these exist in the real product per the product constitution). Including them *helps* MD.Piece; excluding them is conservative. *Default: include caregiver proxy, exclude OCR in v0.1, both flagged.*
- **D5 — Single latent advantage factor vs richer correlation structure** for patient attributes.

I will proceed to Phase 2 with the **defaults above** unless redirected, and every default is logged in the Assumption Registry so it can be revisited.

---

## 13. Execution roadmap & status

| Phase | Deliverable | Status |
|---|---|---|
| **1. Architecture** | this document | ✅ this turn |
| 2. Schemas | finalize every CSV/Parquet schema + the 4 registries as YAML | next |
| 3. Probability models | fill Probability Registry with distributions + defaults + ranges | |
| 4. Workflow | the seeded pipeline orchestrator + determinism harness | |
| 5. Implement | engines L1–L8 + evaluation | |
| 6. Generate | 3,200-patient / 12-month run → all CSVs | |
| 7. Evaluate | metrics + sensitivity + bias report (incl. §11 caveats) | |

**Checkpoint (Rule 10):**
- **Done & verified:** directory skeleton created; architecture, layer specs, schema preview, metric definitions, registry plan, and a critical threats-to-validity analysis written.
- **Not yet done:** no engine code, no schemas-as-YAML, no parameters chosen. Nothing has been run; no result exists.
- **Decision needed from you:** confirm D1–D5 defaults (or override), then I proceed to Phase 2 (schemas + registries).
