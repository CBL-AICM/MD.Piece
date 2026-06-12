# Phase 7 (global) — Sobol variance-based sensitivity

output = ΔCRS (MD.Piece − Recall) · N=64 · n=250/run · 384 model runs · Var(ΔCRS)=0.00483

S1 = first-order (alone); ST = total (incl. interactions). ST≫S1 ⇒ acts via interactions.

| parameter | S1 | ST | ST−S1 (interaction) |
|---|---|---|---|
| notif_recovery | +0.378 | 0.397 | 0.019 |
| recall_tau_days | +0.325 | 0.281 | 0.000 |
| onboarding_base | +0.253 | 0.236 | 0.000 |
| retention_median_days | +0.059 | 0.034 | 0.000 |

- Σ S1 ≈ 1.02 ⇒ ~102% of ΔCRS variance is first-order (additive); the remainder (~0%) is interactions + sampling noise.
- Highest total-order influence: **notif_recovery** (ST=0.397) — the parameter a real study should pin down first; its effect compounds with the others.
- Cross-check vs the one-at-a-time tornado (sensitivity_report.md): agreement on the top driver corroborates the finding; a parameter with ST≫S1 there would have looked weak in OAT.