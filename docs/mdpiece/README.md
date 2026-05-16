# MD. Piece — Disease-Agnostic Immune Disease Simulator + Predictor

> Science-fair project. **Not for clinical use.** All data are synthetic.

MD. Piece is a five-layer framework for chronic immune-mediated disease management
that combines N-of-1 self-experimentation with AI-generated virtual patients.

## Five-layer architecture

| Layer | What it is | Status |
|---|---|---|
| 0 | User N-of-1 real data (wearables, diary, meds) | external |
| 1 | LLM-generated virtual-patient narratives | (separate) |
| 2 | Probabilistic immune-disease time-series simulator | **this repo** (`md_piece/`) |
| 3 | Fine-tuned predictive model (LSTM+attention) | **this repo** (`ml/`) |
| 4 | Bayesian hierarchical integration | (next phase) |

## Why disease-agnostic?

Every supported disease uses the same generic ODE engine. The only thing that
changes is a YAML knowledge base. Adding a new disease means writing a YAML — no
code changes.

Three dynamics types cover the breadth of immune diseases:

| Type | Examples | Time constant | Special mechanic |
|---|---|---|---|
| `chronic_relapsing` | RA, SLE, IBD, MS | days | flare/remission cycle |
| `reversible` | Asthma, urticaria | hours | rapid return to baseline |
| `progressive` | SSc, IPF | slow | monotonic fibrosis burden |

## Quick start

```bash
pip install -r requirements_mdpiece.txt   # numpy, pandas, pyyaml, matplotlib, scipy, torch, scikit-learn

# 1. simulate 100 virtual patients * 90 days for all 3 reference diseases
python main.py --n 100 --days 90 --seed 42

# 2. run sanity tests
pytest tests/test_mdpiece -v

# 3. train Layer-3 prediction model (≈3-10 min CPU)
python -m ml.train

# outputs:
#   output/mdpiece/*_timeseries.csv   - simulated cohorts
#   output/mdpiece/*_cohort.png       - validation figures
#   output/mdpiece/checkpoints/best.pt
#   output/mdpiece/logs/run_*.json    - full metrics
#   docs/mdpiece/model_card.md        - human-readable model card
```

## Repo layout

```
md_piece/                            simulator package
├── disease_loader.py                YAML loader
├── dynamics.py                      generic target-tracking ODE
├── triggers.py                      stochastic events + treatment assignment
├── patient.py                       Patient class + biomarker mapping
├── cohort_generator.py              batch simulation
└── visualize.py                     matplotlib figures

diseases/                            knowledge base (one YAML per disease)
├── rheumatoid_arthritis.yaml
├── asthma.yaml
└── systemic_sclerosis.yaml

ml/                                  Layer-3 PyTorch model
├── config.yaml                      hyperparameters + paths
├── features.py                      cohort -> long DataFrame
├── dataset.py                       windowing + patient-level split
├── model.py                         LSTM + attention pooling + 2 heads
├── train.py                         training loop + early stopping + model card
└── evaluate.py                      metrics with 95% bootstrap CI

tests/test_mdpiece/                  sanity tests (dynamics, comorbidity,
                                     treatment direction, biomarker range,
                                     reproducibility)
main.py                              one-shot demo
docs/mdpiece/                        README, DESIGN, NEW_DISEASE_GUIDE, model card
```

## Adding a new disease

See [`NEW_DISEASE_GUIDE.md`](NEW_DISEASE_GUIDE.md).

## Disclaimer

This system is a science-fair research artifact. All patient data are synthetic.
**It does not constitute medical advice and must not be used for clinical
decision-making.** Outputs (including AI-generated content and simulated
biomarkers) carry no warranty of accuracy.

## References
- Lillie EO et al. (2011) *Personalized Medicine* — N-of-1 trials.
- Zucker DR et al. (1997) *Stat Med* — Bayesian hierarchical N-of-1.
- Walonoski J et al. (2018) *JAMIA* — Synthea synthetic patients.
- Topol EJ (2019) *Nature Medicine* — Digital twins in medicine.
- FDA guidance (2023) — In silico clinical trials.
