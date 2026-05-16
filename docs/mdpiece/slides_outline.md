# MD. Piece — 10-Slide Science Fair Outline

> Talk length target: 8 minutes + 4 minutes Q&A.
> Audience: judges (mixed clinical / technical background).

---

## Slide 1 — Title & one-sentence pitch
- Title: **MD. Piece — A Disease-Agnostic, AI-Augmented N-of-1 Framework for Chronic Immune Disease**
- Pitch: *"What if every chronic immune patient had a personal digital twin that learns from their own data and from thousands of plausible virtual patients?"*

## Slide 2 — The problem
- Chronic immune diseases (RA, asthma, SSc...) are heterogeneous — average-cohort guidelines miss the individual.
- N-of-1 trials are the gold standard for personalization but produce too little data.
- Real patient registries are scarce, biased, and not shareable.
- Gap: **how to fit personalized models without exposing real patients or starving the model**.

## Slide 3 — Our five-layer solution
```
Layer 0: real N-of-1 data (wearable + diary)
Layer 1: LLM virtual-patient narratives (qualitative)
Layer 2: physics-based simulator (quantitative time series) ← this poster
Layer 3: fine-tuned predictive model (LSTM + attention)   ← this poster
Layer 4: Bayesian hierarchical fusion (future)
```
- Disease-agnostic design philosophy: **one engine + N YAMLs**.

## Slide 4 — Layer 2: generic ODE engine
- Master equation:
  `dI/dt = -k * (I - target(t))`
  `target(t) = baseline + triggers - treatments + circadian`
  `+ irreversible accumulation [progressive only]`
- Three dynamics types cover every immune disease we surveyed:
  - `chronic_relapsing` (RA), `reversible` (asthma), `progressive` (SSc)
- **One figure: three trajectories, one model, three diseases.**

## Slide 5 — Validation that the simulator behaves like the disease
- Sanity tests (all PASS): flare frequency in RA (mean ~6 / year), asthma reversibility, SSc monotonic burden, biomarker ranges, reproducibility, treatment-effect direction (TNF inhibitor lowers DAS28).
- Comorbidity rates match YAML within ±10 pp at n=300.
- Figure: cohort overlay + flare histogram for each disease.

## Slide 6 — Layer 3: predicting flares + activity from past week
- Input: past 7 days of biomarkers + demographics + treatment status (33 features).
- Two heads:
  - Regression: tomorrow's immune-activity score.
  - Classification: any flare in the next 7 days.
- Architecture: 2-layer LSTM + attention pooling, 59k params.
- Split: 80/10/10 **by patient** (no leakage).

## Slide 7 — Results
| Task | Metric | Result | 95% CI |
|---|---|---|---|
| Activity prediction | MAE | 0.23 | [0.22, 0.24] |
| | R² | 0.91 | [0.90, 0.92] |
| | baseline MAE | 1.08 | — |
| Flare risk (7-day) | AUROC | 0.88 | [0.87, 0.89] |
| | AUPRC | 0.73 | [0.71, 0.75] |
- vs. simple-mean baseline: 4.7× MAE improvement, well-separated CIs.

## Slide 8 — What makes this disease-agnostic
- Adding a 4th disease = write one YAML (~30 min, **no code change**).
- Demo: walk through `diseases/asthma.yaml` and point at the three blocks that differ from RA.
- The Layer-3 model picks it up via union-of-features schema.

## Slide 9 — Limitations & ethics
- Pure synthetic data — no clinical validity claim.
- Treatment effects use simplified pharmacology (single-dose exponential decay).
- No external validation against real registries.
- Disclaimer reproduced in README and model card.
- IRB n/a because no human-subject data is used.

## Slide 10 — Why this matters & next steps
- Demonstrates that **physics-based simulation + small-model fine-tuning** can
  generate decision-support hypotheses before any real patient data are spent.
- Roadmap:
  - Layer 4 Bayesian fusion of real N-of-1 with cohort prior.
  - Calibration against published RA / asthma cohort statistics.
  - Pilot N-of-1 study with the consented user (the developer himself).
- Open source — anyone can add a disease YAML and reuse the engine.

---

### Backup slides (for Q&A)
- Architecture diagram with module dependencies.
- Sample biomarker formulas with YAML excerpts.
- Loss curves + early-stopping rationale.
- "Why LSTM, not Transformer" justification.
- All five sanity-test specifications + pass/fail status.
