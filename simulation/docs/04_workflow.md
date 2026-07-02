# Phase 4 — Simulation Workflow & Orchestration

**Status:** Phase 4 of 7. Defines execution order, module interfaces, the determinism
harness, and the validation/test plan. After this, Phases 5–7 are implementation + run.
No research constant appears in code — all flow through `config/` (arch §3.3).

## 1. Pipeline (strict DAG, every arrow a pure seeded transform)

```
config/*.yaml ─► [load+validate config] ─► [build RNG tree from master_seed]
      │
      ▼
 (per patient i, using spawned substreams)
 L1 generate_patient(i)                         → patient row
   └► L4 assign_persona(patient)                → persona + behavioral params
        └► L2+L3 simulate_ground_truth(patient) → ground-truth event stream  [disease_engine]
             ├► L5a recall_observer(truth, persona, visits)   → PATIENT_RECALL events
             └► L6 usage_trajectory(persona) ─► L5b mdpiece_observer(truth, usage, persona)
                                                              → MDPIECE events + app_usage
      ▼ (population-level, after all patients)
 L7 health_event_view(all arms)                 → timeline / episodes
 L8 doctor_engine(snapshots per arm)            → doctor_snapshot, doctor_interaction
 evaluation(all arms vs ground truth)           → evaluation_metrics, information_friction, retention
      ▼
 outputs/<config_hash>/*.parquet (+ csv mirrors)  +  report.md (with §11 caveats prepended)
```

**Parallelism:** patients are independent given their spawned RNG → embarrassingly parallel
across patients (multiprocessing / joblib). Population-level steps (L7/L8/eval) run after the
barrier. Determinism is preserved regardless of worker count (RNG spawned by patient index,
not draw order).

## 2. Module interfaces (Phase 5 contract)

Each engine is a pure function `f(inputs, rng, config) -> dataframe/records`. No engine
reads another engine's *output file*; they pass in-memory typed records. Only `evaluation`
reads all three arms. Ground truth passed **read-only** to observers (leakage guard, arch §5).

| Module | Signature (conceptual) |
|---|---|
| `patients.generate` | `(i, rng[demographics], cfg) -> PatientRow` |
| `persona.assign` | `(patient, rng[persona], cfg) -> PersonaParams` |
| `disease_engine.simulate` | `(patient, persona, rng[disease,utilization], cfg) -> list[Event]` (GROUND_TRUTH) |
| `friction_engine.recall` | `(truth_events, patient, persona, visit_days, rng[recall], cfg) -> list[Event]` |
| `usage_engine.trajectory` | `(patient, persona, truth_events, rng[usage], cfg) -> UsageWeeks` |
| `friction_engine.mdpiece` | `(truth_events, usage, patient, persona, rng[mdpiece], cfg) -> list[Event]` |
| `doctor_engine.review` | `(arm_events, physician, visit, rng[doctor], cfg) -> Interaction` |
| `evaluation.score` | `(truth, recall, mdpiece, doctor) -> MetricsRow, FrictionRow` |

## 3. Determinism harness (a first-class deliverable, not an afterthought)

Tests that MUST pass before any result is trusted (arch §5, §10):

- **T-DET-1 (reproducibility):** two full runs, same config → byte-identical Parquet (modulo
  unordered-row sort). Hash-compared in CI.
- **T-DET-2 (worker-invariance):** run with 1 vs N workers → identical output.
- **T-DET-3 (ground-truth isolation):** ground-truth events identical whether or not the
  recall/mdpiece/doctor engines run (observers cannot mutate truth).
- **T-DET-4 (config-hash binding):** changing any config value changes `<config_hash>` and
  the output directory (no silent parameter swap).

## 4. Validation harness (face / internal validity, arch §10)

Auto-checked after a run; failures are **loud** (Rule 12), not warnings:

- **V-FACE-1:** simulated per-disease relapse/flare rates fall within `disease_registry`
  plausible ranges (±tolerance).
- **V-FACE-2:** retention curve monotonically non-increasing; M1 retention within the
  pessimistic band declared in D3.
- **V-INT-1:** sicker patients (higher severity) have more ground-truth events (monotone).
- **V-INT-2:** adopters (high engagement) skew higher tech/health literacy (the intended
  confound is present and measurable).
- **V-INT-3:** recall fidelity decreases with time-since-event (forgetting actually bites).
- **V-SANITY (parity, arch §10):** with mdpiece loss params set equal to recall loss params,
  the `MDPIECE − RECALL` effect is ≈ 0 (within MC error). **If it isn't, the engine is
  biased and no result is valid.** This is the most important single test.

## 5. Sensitivity & bias harness (Phase 7, arch §10)

- **One-at-a-time:** sweep each `probability_registry` knob across its `range`; record effect
  on the primary estimand. Output a tornado plot of |Δeffect|.
- **Global (Sobol/LHS):** joint sweep; first- and total-order sensitivity indices. Headline
  output: **which parameters can flip the SIGN of the MD.Piece effect** — those are exactly
  what a real future study must measure.
- **Bias quantification:** crude vs adoption-adjusted effect (A05); clinical vs uniform
  salience weights (A07); with vs without dropouts (A02); MD.Piece loss → recall loss parity
  (A01). Each prints a number into the report.

## 6. Output contract

`outputs/<config_hash>/`:
- the 11 prescribed CSVs + Parquet canonicals
- `report.md` — **§11 Threats-to-Validity reproduced at the top**, then: assumption-registry
  roll-up (N unvalidated, net directional bias), primary estimand + 95% CI, the mandatory
  stratified tables (by persona/disease/severity/literacy/caregiver), the parity-check result,
  and the tornado/Sobol sensitivity summary.
- `manifest.json` — config hash, seed, package versions, git SHA, row counts, run timestamp
  (stamped *after* the run; never inside the seeded pipeline).

## 7. Stack & scale

Python 3.11 · NumPy (RNG, vectorized draws) · SciPy (distributions/survival) · pandas +
PyArrow (Parquet) · Polars optional for the join-heavy evaluation · Faker for cosmetic
identifiers only (never for anything that influences a result) · NetworkX for the disease
event-chain DAG / episode assembly. Target 3,200 patients × 365 days; expected 50k–1M events.
Patient-parallel; a full run should sit in minutes on a workstation.

## 8. Implementation order (Phase 5)

1. config loader + schema validators + RNG tree + **determinism harness** (tests first — Rule 4/9).
2. L1 patients → L4 persona (+ V-INT-2 confound test).
3. disease_engine L2+L3 (+ V-FACE-1, V-INT-1).
4. friction_engine L5a recall (+ V-INT-3) ; usage L6 (+ V-FACE-2) ; L5b mdpiece.
5. **parity sanity test (V-SANITY) — gate: nothing proceeds until it passes.**
6. L7 view, L8 doctor.
7. evaluation + report.
8. Phase 6 full run; Phase 7 sensitivity/bias.

Each step ships with its validation test green before the next (Rule 10 checkpoints).

## Checkpoint (end of design phases 1–4)

- **Done & verified:** complete design package — architecture, schemas, four registries
  (disease/persona/assumption/probability) as machine-readable YAML, and this workflow +
  determinism + validation + sensitivity plan. Every research number is in config and flagged
  for validation; the design can produce positive *or* negative results and has a built-in
  bias self-check (V-SANITY).
- **Not done:** zero engine code; nothing run; no dataset; no result.
- **Next:** Phase 5 implementation, starting with the determinism harness + L1/L4 — the
  first point at which code exists.
