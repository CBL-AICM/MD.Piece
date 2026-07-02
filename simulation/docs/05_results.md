# MD.Piece Digital-Twin Simulation — Evaluation Report

config_hash `713d8a608280` · seed 20260606 · n=3200 patients · PROSPECTIVE mode

## ⚠️ Read before the numbers — threats to validity
- This is a **microsimulation**; the sign of the result is, in the limit, a function of the friction/capture parameters we chose. The value is the **response surface**, not a point estimate.
- We author BOTH the recall-loss and MD.Piece-capture models. Mitigations: dropouts/non-adoption counted against MD.Piece; deliberately pessimistic retention; a **V-SANITY parity check** (MD.Piece reduced to recall ⇒ effect ≈ 0).
- Absolute fidelity numbers are optimistic vs a real study (ground truth here is lossless; real EHR is not). Only **relative** arm comparisons are claimed.
- **Assumption registry:** 15 structural assumptions, **5 still validation-required (expert judgment)**. Net design bias: 4 assumptions favor MD.Piece, 4 favor recall (the design is balanced).

## Primary estimand — MD.Piece − Patient Recall (paired, per patient)
| metric | recall | mdpiece | Δ (mdpiece−recall) | 95% CI |
|---|---|---|---|---|
| Clinical Reconstruction Score | 0.342 | 0.450 | +0.108 | [+0.101, +0.115] |
| Event Recall Rate | 0.464 | 0.335 | -0.128 | [-0.139, -0.118] |
| Information Friction Score (↓ better) | 0.620 | 0.517 | -0.103 | [-0.109, -0.097] |
| Doctor Understanding | 0.216 | 0.215 | -0.000 | [-0.013, +0.012] |

## Effect heterogeneity by persona (the crossover, H2) — Δ Clinical Reconstruction Score
| persona | n | recall | mdpiece | Δ |
|---|---|---|---|---|
| CAREGIVER_MANAGED | 407 | 0.314 | 0.747 | +0.433 |
| PERFECT_LOGGER | 198 | 0.459 | 0.783 | +0.324 |
| ANXIOUS | 309 | 0.334 | 0.579 | +0.246 |
| SYMPTOM_DRIVEN | 324 | 0.341 | 0.436 | +0.095 |
| NORMAL | 772 | 0.360 | 0.421 | +0.061 |
| ELDERLY_LOW_LITERACY | 418 | 0.290 | 0.321 | +0.031 |
| LOW_ENGAGEMENT | 463 | 0.329 | 0.282 | -0.047 |
| TECH_AVOIDANT | 309 | 0.359 | 0.232 | -0.128 |

## By disease — Δ Clinical Reconstruction Score
| disease | n | Δ |
|---|---|---|
| RA | 656 | +0.124 |
| SLE | 532 | +0.118 |
| MS | 594 | +0.117 |
| OTHER | 271 | +0.105 |
| MG | 255 | +0.092 |
| NMOSD | 348 | +0.090 |
| CROHN | 544 | +0.089 |

## App retention (MD.Piece arm) — deliberately pessimistic (D3/A09)
| onboarded | D1 | W1 | M1 | M3 | M6 | M12 |
|---|---|---|---|---|---|---|
| 0.66 | 0.66 | 0.63 | 0.53 | 0.40 | 0.32 | 0.28 |

## Interpretation
- Overall MD.Piece effect on reconstruction fidelity is **net POSITIVE** (Δ=+0.108); MD.Piece improves the record for **64%** of patients and worsens it for the rest — a **crossover**, not a uniform effect.
- The benefit concentrates in caregiver-supported / high-engagement personas; the harm concentrates in low-engagement / technology-avoidant personas — consistent with H2.
- **A negative or null aggregate is a valid, informative result** (brief §philosophy). The actionable implication is targeting: MD.Piece's value is conditional on engagement, so deployment should focus on caregiver-mediated and high-engagement segments, and the headline is sensitive to app retention (the #1 Phase-7 sensitivity axis).