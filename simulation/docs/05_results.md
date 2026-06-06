# MD.Piece Digital-Twin Simulation — Evaluation Report

config_hash `6e5c84dbb48d` · seed 20260606 · n=3200 patients · PROSPECTIVE mode

## ⚠️ Read before the numbers — threats to validity
- This is a **microsimulation**; the sign of the result is, in the limit, a function of the friction/capture parameters we chose. The value is the **response surface**, not a point estimate.
- We author BOTH the recall-loss and MD.Piece-capture models. Mitigations: dropouts/non-adoption counted against MD.Piece; deliberately pessimistic retention; a **V-SANITY parity check** (MD.Piece reduced to recall ⇒ effect ≈ 0).
- Absolute fidelity numbers are optimistic vs a real study (ground truth here is lossless; real EHR is not). Only **relative** arm comparisons are claimed.
- **Assumption registry:** 15 structural assumptions, **7 still validation-required (expert judgment)**. Net design bias: 4 assumptions favor MD.Piece, 4 favor recall (the design is balanced).

## Primary estimand — MD.Piece − Patient Recall (paired, per patient)
| metric | recall | mdpiece | Δ (mdpiece−recall) | 95% CI |
|---|---|---|---|---|
| Clinical Reconstruction Score | 0.344 | 0.454 | +0.110 | [+0.103, +0.117] |
| Event Recall Rate | 0.467 | 0.341 | -0.126 | [-0.137, -0.116] |
| Information Friction Score (↓ better) | 0.621 | 0.514 | -0.107 | [-0.113, -0.101] |
| Doctor Understanding | 0.215 | 0.218 | +0.002 | [-0.010, +0.014] |

## Effect heterogeneity by persona (the crossover, H2) — Δ Clinical Reconstruction Score
| persona | n | recall | mdpiece | Δ |
|---|---|---|---|---|
| CAREGIVER_MANAGED | 408 | 0.316 | 0.752 | +0.436 |
| PERFECT_LOGGER | 198 | 0.462 | 0.786 | +0.324 |
| ANXIOUS | 309 | 0.336 | 0.584 | +0.249 |
| SYMPTOM_DRIVEN | 324 | 0.345 | 0.441 | +0.096 |
| NORMAL | 772 | 0.361 | 0.427 | +0.065 |
| ELDERLY_LOW_LITERACY | 419 | 0.290 | 0.322 | +0.031 |
| LOW_ENGAGEMENT | 463 | 0.332 | 0.284 | -0.048 |
| TECH_AVOIDANT | 307 | 0.361 | 0.235 | -0.127 |

## By disease — Δ Clinical Reconstruction Score
| disease | n | Δ |
|---|---|---|
| RA | 656 | +0.130 |
| SLE | 532 | +0.122 |
| MS | 594 | +0.117 |
| OTHER | 271 | +0.105 |
| MG | 255 | +0.094 |
| NMOSD | 348 | +0.092 |
| CROHN | 544 | +0.090 |

## App retention (MD.Piece arm) — deliberately pessimistic (D3/A09)
| onboarded | D1 | W1 | M1 | M3 | M6 | M12 |
|---|---|---|---|---|---|---|
| 0.66 | 0.66 | 0.63 | 0.53 | 0.41 | 0.33 | 0.29 |

## Interpretation
- Overall MD.Piece effect on reconstruction fidelity is **net POSITIVE** (Δ=+0.110); MD.Piece improves the record for **64%** of patients and worsens it for the rest — a **crossover**, not a uniform effect.
- The benefit concentrates in caregiver-supported / high-engagement personas; the harm concentrates in low-engagement / technology-avoidant personas — consistent with H2.
- **A negative or null aggregate is a valid, informative result** (brief §philosophy). The actionable implication is targeting: MD.Piece's value is conditional on engagement, so deployment should focus on caregiver-mediated and high-engagement segments, and the headline is sensitive to app retention (the #1 Phase-7 sensitivity axis).