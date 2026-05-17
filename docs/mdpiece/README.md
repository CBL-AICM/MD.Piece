# MD. Piece v2 — Disease-Agnostic Simulator + Unpredictability Engine + PWA

> Science-fair project. **Not for clinical use.** All data are synthetic.

MD. Piece is a five-layer framework for chronic immune-mediated disease management
that combines N-of-1 self-experimentation with AI-generated virtual patients.
**v2** adds an eight-source unpredictability engine, full age stratification
(20–90), and a Progressive Web App for interactive exploration.

## Five-layer architecture

| Layer | What | Status |
|---|---|---|
| 0 | User N-of-1 real data (wearables, diary, meds) | external |
| 1 | LLM-generated virtual-patient narratives | (separate) |
| 2 | Probabilistic disease simulator + **8 unpredictability sources** | **this repo** (`md_piece/`) |
| 3 | LSTM+attention predictor (next-day activity / 7-day flare risk) | **this repo** (`ml/`) |
| 4 | Bayesian hierarchical integration | (next phase) |
| UI | Cross-platform PWA explorer | **this repo** (`pwa/`) |

## Eight unpredictability sources (v2)

| # | Source | Where it lives |
|---|---|---|
| 1 | Individual variability (YAML `{mean, std, min, max}` distributions) | `unpredictability.sample_param` |
| 2 | Responder classes (super / typical / partial / non) | `unpredictability.sample_responder_class` |
| 3 | Hidden subtypes (seropositive vs seronegative, eosinophilic vs neutrophilic, …) | `unpredictability.sample_subtype` |
| 4 | Non-adherence (daily miss + discontinuation + dose self-adjust) | `adherence.py` |
| 5 | Stochastic life events (infection, surgery, menstruation, pregnancy, …) | `life_events.py` |
| 6 | Placebo / nocebo on subjective biomarkers | `unpredictability.sample_placebo_effect` |
| 7 | Long-tail rare events (3% probability atypical flare) | `unpredictability.sample_long_tail_event` |
| 8 | Age stratification (20–90 with elderly mechanism) | `age_stratification.py` |

## Three dynamics types cover every immune disease

| Type | Examples | Time constant | Special mechanic |
|---|---|---|---|
| `chronic_relapsing` | RA, SLE, IBD, MS | days | flare/remission cycle |
| `reversible` | Asthma, urticaria | hours | rapid return to baseline |
| `progressive` | SSc, IPF | slow | monotonic fibrosis burden |

## Quick start

```bash
pip install -r requirements_mdpiece.txt

# 1. simulate 100 virtual patients × 90 days × 3 diseases
#    + emit pwa/data/cohort.json for the PWA
python main.py --n 100 --days 90 --seed 42

# 2. run all sanity tests (15 tests, ≈ 20 s)
pytest tests/test_mdpiece -v

# 3. serve the PWA locally
python -m http.server 8765 --directory pwa
# → http://localhost:8765

# 4. (optional) train the Layer-3 prediction model
python -m ml.train
# → output/mdpiece/checkpoints/best.pt + docs/mdpiece/model_card.md

# 5. (optional) use the trained model on a new virtual patient
PYTHONPATH=. python -m ml.predict --disease rheumatoid_arthritis --seed 999
```

## PWA — five screens

1. **🏠 Dashboard** — KPIs + disease/age/responder pie & bar charts.
2. **👥 Patient Browser** — filter (disease/age/sex/responder) + per-patient detail (activity curve, biomarkers, life-event ribbon).
3. **🎓 Training Mode** — show 60 days, you predict whether days 61–90 will flare; local score persisted.
4. **🔬 Experiment Mode** — pick a treatment, watch the whole cohort respond by responder class.
5. **📊 N-of-1 Mode** — enter your own age/sex/activity, the PWA finds similar virtual patients and returns a 95 % CI.

**PWA features**: `manifest.json` + `service-worker.js` (cache-first shell, network-first data), IndexedDB caching of `cohort.json`, LocalStorage for training scores, fully responsive.

## Repo layout

```
md_piece/
├── disease_loader.py            # YAML loader + v2 schema validation
├── dynamics.py                  # universal ODE engine + age modifier
├── triggers.py                  # trigger sampling + distribution-aware tx assignment
├── patient.py                   # Patient class — orchestrates all 8 sources
├── cohort_generator.py          # batch generation
├── unpredictability.py          # 8-source orchestrator
├── age_stratification.py        # 20-90 + elderly mechanism
├── adherence.py                 # miss / discontinue / self-adjust
├── life_events.py               # stochastic events
└── visualize.py                 # matplotlib outputs

diseases/                        # one YAML per disease (v2 schema)
├── rheumatoid_arthritis.yaml
├── asthma.yaml
└── systemic_sclerosis.yaml

ml/                              # Layer-3 PyTorch model (unchanged from v1)
├── config.yaml
├── features.py
├── dataset.py
├── model.py                     # LSTM + attention pooling
├── train.py
├── evaluate.py                  # 95 % bootstrap CI
└── predict.py                   # single-patient inference

pwa/                             # 5-screen Progressive Web App
├── index.html
├── manifest.json
├── service-worker.js
├── icons/icon-*.svg
├── css/style.css
└── js/{main,data,dashboard,patient-browser,training,experiment,n-of-1}.js

tests/test_mdpiece/              # 15 sanity tests
├── test_age_distribution.py     # 3 tests — age range / distribution / elderly mechanism
├── test_unpredictability.py     # 5 tests — responder dist / heterogeneity CV / adherence / life events / subtypes
├── test_biomarker_range.py
├── test_comorbidity.py
├── test_dynamics.py             # 3 tests — chronic / reversible / progressive
├── test_reproducibility.py
└── test_treatment.py

main.py                          # one-shot demo + cohort.json export
docs/mdpiece/                    # README, DESIGN, NEW_DISEASE_GUIDE, model card, slides
```

## Disclaimer

This system is a science-fair research artifact. All patient data are synthetic.
**It does not constitute medical advice and must not be used for clinical
decision-making.** Outputs (including AI-generated content and simulated
biomarkers) carry no warranty of accuracy. The PWA stores no personally
identifiable information; only training scores and UI preferences are kept in
LocalStorage.

## References
- Lillie EO et al. (2011) *Personalized Medicine* — N-of-1 trials.
- Zucker DR et al. (1997) *Stat Med* — Bayesian hierarchical N-of-1.
- Walonoski J et al. (2018) *JAMIA* — Synthea synthetic patients.
- Topol EJ (2019) *Nature Medicine* — Digital twins.
- FDA guidance (2023) — In silico clinical trials.
- Senn S (2016) *Stat Methods Med Res* — Response heterogeneity.
- Fulop T et al. (2018) *Front Immunol* — Immunosenescence.
