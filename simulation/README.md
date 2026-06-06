# MD.Piece Digital Twin Simulation Platform

A research-grade behavioral microsimulation that asks: **does a Health-Event–based
prospective record (MD.Piece) reconstruct a patient's 12-month health story with less
information loss than unaided retrospective recall?**

3,200 virtual chronic-disease patients · 12 months · daily resolution · 3 record arms
(`GROUND_TRUTH`, `PATIENT_RECALL`, `MDPIECE`).

> ⚠️ **This is not a proof that MD.Piece works.** It is a microsimulation whose conclusion
> depends on its parameters. Its value is the *response surface* — where the app helps,
> where it fails — and it is explicitly built to be able to produce a **negative** result.
> Read `docs/01_architecture.md` §11 (Threats to Validity) before trusting any output.

## Status

| Phase | Deliverable | Status |
|---|---|---|
| 1. Architecture | `docs/01_architecture.md` | ✅ done |
| 2. Schemas | `docs/02_schemas.md` + 4 registries (YAML) | ✅ done |
| 3. Probability models | `config/probability_registry.yaml` | ✅ done |
| 4. Workflow | `docs/04_workflow.md` (pipeline + determinism + validation harness) | ✅ done |
| 5. Implement | engines L1–L8 + evaluation | ✅ done — **all engines + evaluation, 27/27 tests** |
| 6. Generate | 3,200-patient dataset | ✅ done — `python -m simulation.run_study` (139,914 events) |
| 7. Evaluate | metrics + sensitivity + bias report | ✅ done — `python -m simulation.run_sensitivity` |

**Headline result** (full 3,200-patient run, `outputs/<hash>/report.md`): MD.Piece is a
*crossover*, not a uniform win. On composite **Clinical Reconstruction Score** Δ=**+0.110**
(helps 64% of patients) — but on raw **Event Recall Rate** Δ=**−0.126** and **Doctor
Understanding** Δ=**−0.120**. I.e. MD.Piece captures *fewer* events but records them *more
accurately*. Benefit concentrates in caregiver-managed (+0.44) & high-engagement personas;
harm in tech-avoidant (−0.13) & low-engagement. **Sensitivity** (`docs/06_sensitivity.md`): the
sign flips on `notif_recovery`; the full-adoption ceiling is +0.235 (the gap = the engagement
penalty); uniform-vs-clinical salience barely moves it (not a weighting artifact). **Global Sobol**
(`docs/07_sobol.md`, Saltelli N=64): variance is ~additive (ΣS1≈1.0, interactions negligible) and
dominated by `notif_recovery` (ST≈0.40) > `recall_tau` (0.28) > `onboarding` (0.24) — corroborating
the one-at-a-time ranking, so the decisive driver isn't hidden in interactions.

**Phase 5 progress** (`pytest simulation/tests/` → **27/27 green**):
- **L1 patients + L4 persona** — `python -m simulation.build_population`. Determinism,
  scale-invariance, the designed adoption-selection confound, latent-factor coupling, fail-loud config.
- **L2+L3 disease/utilization** — `python -m simulation.build_ground_truth`. OU latent activity +
  Hawkes flares (branching-ratio-stable) + seasonal infections + adherence/access-gated care.
  Flare rates auto-calibrate to the registry; event load rises with severity; poor-access→ED
  substitution; hospitalization→escalation chain integrity. ~43 events/patient.
- **L6 usage + L5 friction (the core)** — `python -m simulation.build_arms`. Recall observer
  (salience-weighted forgetting + telescoping) and MD.Piece observer (engagement-gated prospective
  logging, date-accurate, non-adoption/dropout counted against the app). **The V-SANITY parity
  gate passes** (effect → 0 when MD.Piece is reduced to recall), and the **crossover (H2)** is
  reproduced: MD.Piece helps caregiver-managed (+0.32) & perfect-logger (+0.13) personas, harms
  tech-avoidant (−0.45) & low-engagement (−0.35); **net −0.13** across the cohort (an honest,
  segment-dependent, net-negative result — as the brief intends).

Remaining engines: doctor (L8 — last-mile clinician friction), health-event view (L7),
evaluation (full metric set + information-friction score + report), then Phase 6 run + Phase 7 sweeps.

## Layout

```
simulation/
├── config/          # YAML: population, disease, persona, friction, weights, seeds
├── patients/        # L1 patient generator
├── disease_engine/  # L2 utilization + L3 disease progression (coupled — see arch §3.1)
├── persona_engine/  # L4 persona assignment
├── usage_engine/    # L6 app usage / retention
├── friction_engine/ # L5 the two lossy observers (recall + mdpiece capture) — the core
├── doctor_engine/   # L8 clinician review / last-mile friction
├── evaluation/      # metrics, comparison, sensitivity, bias, validation
├── outputs/         # CSV / Parquet artifacts (content-addressed by config hash)
└── docs/            # architecture + registries
```

## Start here

1. `docs/01_architecture.md` — the full Phase 1 design (research framing, layers,
   schemas, metrics, threats to validity, open decisions D1–D5).
