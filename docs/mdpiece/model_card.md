# MD. Piece — Layer-3 Model Card

**Generated**: 2026-05-16T23:18:34.572094Z
**Checkpoint**: `output/mdpiece/checkpoints/best.pt`

## Intended use
Predict next-day immune activity (regression) and next-7-day flare risk
(binary classification) for chronic immune-mediated diseases, using the past
7 days of self-monitored signals.

**NOT FOR CLINICAL USE.** Trained entirely on synthetic data from the
MD. Piece Layer-2 simulator. Intended for science-fair research,
methodological demonstration, and educational discussion only.

## Training data
- Diseases: ['rheumatoid_arthritis', 'asthma', 'systemic_sclerosis']
- Cohort size per disease: 200 virtual patients
- Simulated horizon: 180 days
- Window size (input): 7 days
- Prediction horizon: 1 day (activity), 7 days (flare)
- Split: 0.8/0.1/0.1 **by patient** (no leakage)
- Final sample counts: train=79680, val=9960, test=9960

## Architecture
- Type: lstm_attention
- Hidden: 64, Layers: 2, Dropout: 0.2
- Parameters: 58,819
- Input features (33): see JSON log

## Training
- Optimizer: AdamW (lr=0.001, weight_decay=1e-05)
- Batch size: 128
- Loss weights: activity MSE=1.0, flare BCE=0.5
- Early stopping patience: 10 epochs
- Best epoch: 16 (val loss 0.2942)
- Random seed: 2024

## Test-set performance (95% CI from bootstrap)

### Activity regression (immune activity score)
- MAE  = 0.231  CI95=[0.224, 0.239]
- RMSE = 0.451 CI95=[0.428, 0.474]
- R^2  = 0.905   CI95=[0.895, 0.915]
- Baseline (mean predictor) MAE: 1.075

### Flare classification (any flare in next 7 days)
- AUROC = 0.882 CI95=[0.872, 0.893]
- AUPRC = 0.731 CI95=[0.707, 0.753]
- F1@0.5 = 0.720 CI95=[0.696, 0.741]
- Positive class rate: 0.108

## Known limitations
1. **Synthetic data only** — no real patient signals; biomarker formulas are
   stylized and not clinically validated.
2. **No external validation** — generalization to real-world wearable data is unknown.
3. **Disease-agnostic but small set** — three reference diseases only; behavior on
   unseen YAML profiles is untested.
4. **Treatment effects are simplified** — single-dose exponential decay rather than
   real pharmacokinetics.
5. **Not for medical decision-making**. See README disclaimer.

## References
- Lillie EO et al. (2011) *Personalized Medicine* — N-of-1 trials.
- Zucker DR et al. (1997) *Stat Med* — Bayesian hierarchical N-of-1.
- Walonoski J et al. (2018) *JAMIA* — Synthea synthetic patients.
- Topol EJ (2019) *Nature Medicine* — Digital twins.
- FDA guidance (2023) — In silico clinical trials.
