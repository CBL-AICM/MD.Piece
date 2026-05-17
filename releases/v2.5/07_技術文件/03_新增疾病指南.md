# Adding a New Disease to MD. Piece

Adding a fourth (or N-th) immune disease should take ~30 minutes and **zero code
changes**. You only write one YAML file.

## Step 1: choose a dynamics type

| If the disease... | Use |
|---|---|
| ...flares and remits over days/weeks (RA, SLE, IBD, MS, AS, PsA, Sjögren) | `chronic_relapsing` |
| ...is triggered acutely and reverses in hours (asthma, urticaria, angioedema) | `reversible` |
| ...accumulates irreversible damage (SSc, IPF, OA progression) | `progressive` |

## Step 2: copy a template

```bash
cp diseases/rheumatoid_arthritis.yaml diseases/your_disease.yaml
```

## Step 3: fill in the YAML

A minimum-viable disease YAML has eight blocks:

```yaml
disease:
  id: your_disease            # MUST match filename (without .yaml)
  name: Your Disease
  short: YD
  icd10: M99.9                # any plausible ICD-10
  dynamics_type: chronic_relapsing   # one of the three
  time_unit: day              # 'day' or 'hour'

baseline:
  activity: 2.0               # immune-activity score at quiescence
  range: [0.0, 10.0]          # global clip range

decay:
  k: 0.15                     # rate of return to target (per time_unit)

circadian:
  amplitude: 0.1              # how much activity oscillates diurnally
  phase_hours: 6              # peak hour (0-23)

noise:
  sigma: 0.1                  # daily SDE noise

triggers:                     # at least one
  - id: infection
    prob_per_day: 0.02
    effect_mean: 3.0          # how much it bumps target during the event
    effect_sigma: 0.5
    duration_days: [3, 10]

flare:
  threshold: 5.0              # activity > threshold = flare
  refractory_days: 14         # min gap between counted flares

treatments:                   # at least one
  - id: my_drug
    class: csDMARD
    assignment_prob: 0.6
    onset_days: 14            # time to peak effect
    effect_magnitude: 1.0     # equilibrium activity reduction
    half_life_days: 30        # decay of effect after onset

biomarkers:                   # at least one
  some_score:
    range: [0, 10]
    formula: "clip(activity + noise, 0, 10)"
                              # variables available: activity, burden, noise
                              # functions:           max, min, clip
```

Optional blocks:
- `comorbidity`: list of `{id, conditional_prob}`
- `demographics`: `age: {mean, sd, range}`, `female_ratio`
- `accumulation` (**required** for `progressive`): `{rate_per_unit_activity, saturation}`

## Step 4: sanity-test

```bash
python -c "
from md_piece.disease_loader import load_disease
from md_piece.patient import simulate_patient
cfg = load_disease('your_disease')
p = simulate_patient('TEST', cfg, sim_days=180, seed=0)
print(p.timeseries.describe())
print('flares:', p.flare_count)
"
```

Targets:
- `chronic_relapsing`: 3-8 flares in 365 days
- `reversible`: max activity < baseline + 3, recovers within 24h
- `progressive`: `irreversible_burden` strictly non-decreasing

## Step 5: run the full sanity-test suite

```bash
pytest tests/test_mdpiece -v
```

Two of the five tests are RA-specific (flare-count band, TNF-inhibitor effect)
and will still pass because they only inspect their own disease's YAML.

## Step 6: regenerate the ML training set

```bash
# add your disease id to ml/config.yaml under data.diseases
python -m ml.train
```

The Layer-3 model will pick up the new disease automatically through the
union-of-features schema in `ml/dataset.py`.

## Worked example: adding Gout

- Type: `chronic_relapsing` (acute attacks, days of pain, then remission)
- Trigger: `purine_meal` (high probability), `dehydration`, `alcohol`
- Treatment: `nsaid`, `colchicine`, `allopurinol`
- Biomarker: `serum_urate_mg_dL`, `pain_vas`, `joint_swelling`
- Comorbidity: `ckd` (0.35), `hypertension` (0.55)

Total writing time: ~25 minutes.

## Common pitfalls

| Symptom | Likely fix |
|---|---|
| Mean activity << baseline | treatment `effect_magnitude` too large |
| Never flares | trigger magnitudes too small, or k too low |
| Activity stuck at clip range | conflicting trigger + treatment, narrow `range`, or pathological noise |
| Biomarker out of `range` | formula can exceed bounds — wrap in `clip(x, lo, hi)` |
| Test `test_treatment.py` fails | that test is RA-specific (`tnf_inhibitor` + `das28`), unrelated to your new disease |
