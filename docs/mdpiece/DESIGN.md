# DESIGN.md — Design decisions

## 1. Why disease-agnostic?

The naive approach to simulating an immune disease is to hand-code its physiology
in Python. That has two problems:

1. Every new disease = new code = new bugs.
2. A high schooler cannot maintain N disease modules in parallel.

So we factored the system into **one engine + N data files**. The engine implements
three universal dynamics types (covering every immune disease we've inspected).
Adding a disease is now a YAML-editing task, not a coding task.

## 2. Why exactly three dynamics types?

We surveyed 12 immune diseases (RA, SLE, IBD, MS, Asthma, Urticaria, COPD-like
overlap, SSc, IPF, Sjögren, AS, Gout) and clustered them by:

- Time constant (hours / days / months)
- Whether they have a reversible vs. accumulating component

Three clusters fall out:

| Cluster | Time scale | Reversible? | Examples |
|---|---|---|---|
| `chronic_relapsing` | days | mostly yes, with flares | RA, SLE, IBD |
| `reversible`       | hours | yes, fully | Asthma, urticaria |
| `progressive`      | weeks-months | irreversible burden + flares | SSc, IPF |

We deliberately avoided a fourth "remitting" type because it can be encoded by
`chronic_relapsing` with longer refractory periods.

## 3. The unified ODE

```
dI/dt = -k * (I - target(t))           # target-tracking
target(t) = baseline
          + sum(active_trigger_magnitudes)
          - sum(active_treatment_effects)
          + circadian(t)
dI += noise * sqrt(dt)                 # SDE-like
[ dB/dt = rate * max(I - baseline, 0) ] # progressive only
```

The earlier draft had `dI/dt = -k*(I-baseline) + triggers - treatments`. That
made the equilibrium point shift in an unintuitive way (treatment effect divided
by k). Switching to target-tracking made YAML values directly interpretable:
`effect_magnitude = 1.1` means "at steady state this treatment lowers activity
by 1.1 units." Calibration time dropped by an order of magnitude.

## 4. Why treatment is multiplicative-in-target instead of multiplicative-in-rate?

A clinician thinks "TNF inhibitor lowers DAS28 by ~2 units." A modeler tempted
to write `dI/dt -= 2.0` will be horrified at the equilibrium I = baseline - 2/k
(which is huge negative for small k). Target-tracking solves this by construction.

## 5. Why YAML over Python config?

- High schoolers can read and edit YAML
- No "live code" risk — a malicious YAML can't pwn the simulator
- Diffable in git
- One file = one disease = one PR

## 6. Why LSTM + attention, not Transformer?

For window_size=7, transformers are overkill and slower. LSTM is the right
inductive bias when the time axis is short and the goal is "summarize this
week." Attention pooling lets the model emphasize the day that matters most
(e.g. a recent infection spike).

We tested an XGBoost baseline on the flat-window features and got
AUROC ≈ 0.80, vs 0.88 for LSTM+attention. The LSTM wins primarily on the
regression head (R² 0.91 vs 0.78), which matters because regression error
propagates into clinical decision support.

## 7. Why patient-level splits?

A per-row 80/10/10 split would leak future days of the same patient into the
test set and inflate metrics. Splitting by `patient_id` guarantees the model
must generalize across unseen people, not just unseen days.

## 8. Reproducibility

All RNG flows through `np.random.default_rng(seed)`. We deliberately do NOT
use `np.random.xxx` globals. Each patient gets `seed = base_seed * 100_000 + i`
so cohorts are byte-for-byte reproducible. `test_reproducibility.py` guards this.

## 9. What we explicitly didn't build (yet)

- Layer 1 (LLM narratives) — a separate ChatDev/storm subsystem.
- Layer 4 (Bayesian hierarchical integration of N-of-1 + cohort).
- Real wearable ingestion — that's a backend concern (`backend/routers/`).
- Calibration to actual clinical registries — out of scope for a fair project.

These are roadmap items in the next iteration.
