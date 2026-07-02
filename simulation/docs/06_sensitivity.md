# Phase 7 — Sensitivity & Bias Analysis

n=900/variant · base seed 20260606 · paired (same population per variant)

Primary estimand = Δ Clinical Reconstruction Score (MD.Piece − Recall). **Sign flips** mark parameters that decide whether MD.Piece helps or harms.

**Baseline** (n=900): ΔCRS=+0.109 · Δrecall=-0.126 · ΔIF=-0.107 · Δunderstanding=+0.009 · helped=64%

## retention_median_days  (base=75)
| value | ΔCRS | Δrecall | ΔIF (↓) | helped |
|---|---|---|---|---|
| 30 | +0.088 | -0.160 | -0.091 | 62% |
| 50 | +0.099 | -0.143 | -0.099 | 64% |
| 75 | +0.109 | -0.126 | -0.107 | 64% |
| 110 | +0.120 | -0.110 | -0.115 | 65% |
| 150 | +0.129 | -0.095 | -0.122 | 66% |
| 180 | +0.133 | -0.089 | -0.125 | 66% |

## onboarding_base  (base=0.7)
| value | ΔCRS | Δrecall | ΔIF (↓) | helped |
|---|---|---|---|---|
| 0.4 | +0.064 | -0.187 | -0.071 | 55% |
| 0.55 | +0.084 | -0.161 | -0.087 | 59% |
| 0.7 | +0.109 | -0.126 | -0.107 | 64% |
| 0.85 | +0.132 | -0.097 | -0.125 | 69% |
| 0.99 | +0.144 | -0.083 | -0.134 | 71% |

## recall_tau_days  (base=120)
| value | ΔCRS | Δrecall | ΔIF (↓) | helped |
|---|---|---|---|---|
| 60 | +0.164 | -0.013 | -0.142 | 78% |
| 90 | +0.137 | -0.070 | -0.124 | 71% |
| 120 | +0.109 | -0.126 | -0.107 | 64% |
| 180 | +0.069 | -0.212 | -0.080 | 55% |
| 240 | +0.038 | -0.274 | -0.059 | 49% |

## logged_quality_decay  (base=0.05)
| value | ΔCRS | Δrecall | ΔIF (↓) | helped |
|---|---|---|---|---|
| 0.0 | +0.109 | -0.126 | -0.108 | 64% |
| 0.05 | +0.109 | -0.126 | -0.107 | 64% |
| 0.1 | +0.109 | -0.126 | -0.106 | 64% |
| 0.2 | +0.109 | -0.126 | -0.104 | 64% |

## mis_entry_rate  (base=0.06)
| value | ΔCRS | Δrecall | ΔIF (↓) | helped |
|---|---|---|---|---|
| 0.0 | +0.110 | -0.125 | -0.110 | 64% |
| 0.06 | +0.109 | -0.126 | -0.107 | 64% |
| 0.15 | +0.109 | -0.126 | -0.103 | 64% |

## notif_recovery  (base=0.3)
| value | ΔCRS | Δrecall | ΔIF (↓) | helped |
|---|---|---|---|---|
| 0.0 | -0.020  ← SIGN FLIP | -0.219 | -0.047 | 48% |
| 0.3 | +0.109 | -0.126 | -0.107 | 64% |
| 0.5 | +0.155 | -0.061 | -0.135 | 75% |

## Bias scenarios
| scenario | ΔCRS | Δrecall | helped | reads |
|---|---|---|---|---|
| uniform salience (A07) | +0.097 | -0.167 | 62% | removes salience weighting; large shift ⇒ result is weight-driven |
| full adoption, no dropout (A02) | +0.235 | +0.053 | 85% | MD.Piece UPPER BOUND; gap to baseline = the engagement penalty |

## Tornado — parameters ranked by influence on ΔCRS (range across sweep)
| parameter | ΔCRS low | ΔCRS high | range | flips sign? |
|---|---|---|---|---|
| notif_recovery | -0.020 | +0.155 | 0.175 | **YES** |
| recall_tau_days | +0.038 | +0.164 | 0.126 | no |
| onboarding_base | +0.064 | +0.144 | 0.080 | no |
| retention_median_days | +0.088 | +0.133 | 0.046 | no |
| mis_entry_rate | +0.109 | +0.110 | 0.000 | no |
| logged_quality_decay | +0.109 | +0.109 | 0.000 | no |

## Takeaways
- The MD.Piece conclusion is **not robust**: its sign flips within the plausible range of **notif_recovery**. These must be measured in a real study before any claim.
- The full-adoption upper bound (ΔCRS=+0.235) vs baseline (ΔCRS=+0.109) shows how much of MD.Piece's potential is lost to non-adoption + dropout — the engagement penalty, and the main lever for real-world value.