# MD. Piece — Layer-3 Model Card

**Generated**: 2026-05-17T01:22:03.708255Z
**Checkpoint**: `output/mdpiece/checkpoints/best.pt`

## Intended use
Predict next-day immune activity (regression) and next-7-day flare risk
(binary classification) for chronic immune-mediated diseases, using the past
7 days of self-monitored signals.

**NOT FOR CLINICAL USE.** Trained entirely on synthetic data from the
MD. Piece Layer-2 simulator. Intended for science-fair research,
methodological demonstration, and educational discussion only.

## Training data
- Diseases: ['rheumatoid_arthritis', 'asthma', 'systemic_sclerosis', 'systemic_lupus_erythematosus', 'inflammatory_bowel_disease', 'multiple_sclerosis', 'gout', 'ankylosing_spondylitis', 'psoriatic_arthritis', 'sjogren_syndrome', 'behcet_disease', 'anca_vasculitis', 'igg4_related_disease', 'chronic_urticaria', 'osteoarthritis', 'idiopathic_pulmonary_fibrosis']
- Cohort size per disease: 200 virtual patients
- Simulated horizon: 180 days
- Window size (input): 7 days
- Prediction horizon: 1 day (activity), 7 days (flare)
- Split: 0.8/0.1/0.1 **by patient** (no leakage)
- Final sample counts: train=424960, val=53120, test=53120

## Architecture
- Type: lstm_attention
- Hidden: 64, Layers: 2, Dropout: 0.2
- Parameters: 82,371
- Input features (125): see JSON log

## Training
- Optimizer: AdamW (lr=0.001, weight_decay=1e-05)
- Batch size: 128
- Loss weights: activity MSE=1.0, flare BCE=0.5
- Early stopping patience: 10 epochs
- Best epoch: 6 (val loss 0.1560)
- Random seed: 2024

## Test-set performance (95% CI from bootstrap)

### Activity regression (immune activity score)
- MAE  = 0.164  CI95=[0.162, 0.166]
- RMSE = 0.307 CI95=[0.297, 0.317]
- R^2  = 0.927   CI95=[0.922, 0.932]
- Baseline (mean predictor) MAE: 0.853

### Flare classification (any flare in next 7 days)
- AUROC = 0.933 CI95=[0.929, 0.937]
- AUPRC = 0.693 CI95=[0.680, 0.707]
- F1@0.5 = 0.630 CI95=[0.617, 0.646]
- Positive class rate: 0.065

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
