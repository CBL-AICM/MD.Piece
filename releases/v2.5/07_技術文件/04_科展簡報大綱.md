# MD. Piece v2 — 10-Slide Science Fair Outline

> Talk: 8 min + 4 min Q&A. Audience: judges (mixed clinical / technical).

---

## Slide 1 — Title & one-sentence pitch
- **MD. Piece v2 — A Disease-Agnostic, AI-Augmented N-of-1 Framework for Chronic Immune Disease**
- *"What if every chronic immune patient had a personal digital twin learning from their own data **and** from thousands of plausible, unpredictable virtual patients?"*

## Slide 2 — The problem
- Chronic immune diseases (RA, asthma, SSc) are heterogeneous — average guidelines fail individuals.
- N-of-1 trials are personalized but data-starved.
- Real registries are scarce, biased, unshareable.
- Gap: **how to model individual unpredictability without consuming real patients.**

## Slide 3 — Five-layer + PWA architecture
```
Layer 0: real N-of-1 data (wearable + diary)
Layer 1: LLM virtual-patient narratives (qualitative)
Layer 2: physics-based simulator + 8 unpredictability sources ⭐
Layer 3: LSTM+attention predictor (Next-day activity + 7-day flare) ⭐
Layer 4: Bayesian hierarchical fusion (future)
  ⇣
PWA explorer — 5 screens, offline-capable                ⭐
```
- **Disease-agnostic**: one engine, N YAMLs.

## Slide 4 — Eight unpredictability sources (v2's core novelty)
| # | Source | Why it matters clinically |
|---|---|---|
| 1 | Individual variability (parameter distributions) | No two RA patients have identical drug response |
| 2 | Responder classes (super/typical/partial/non) | RCTs report 30 % non-responders |
| 3 | Hidden subtypes (seropositive vs seronegative…) | Pathophysiology differs |
| 4 | Non-adherence (miss / discontinue / self-adjust) | Average adherence < 60 % in real chronic care |
| 5 | Stochastic life events (infection, surgery, menstruation, pregnancy…) | Real disease never lives in a vacuum |
| 6 | Placebo / nocebo on subjective biomarkers | VAS/symptom scores carry 10–30 % placebo |
| 7 | Long-tail rare events (3 % atypical flares) | The unexplained cases |
| 8 | **Age stratification 20–90** + elderly mechanism | Immunosenescence (Fulop 2018) — blunted CRP, polypharmacy, atypical presentations |

## Slide 5 — Three-line equation, three diseases
```
dI/dt = -k·(I - target(t))
target = baseline + Σ trig - Σ tx·dose + Σ life_event + circadian + age·severity
[ dB/dt = rate·max(I-base,0)·subtype_mult·antifibrotic_slow ]   (progressive only)
```
| dynamics_type | example | time const | special |
|---|---|---|---|
| chronic_relapsing | RA | days | flare/remission cycle |
| reversible | Asthma | hours | rapid return to baseline |
| progressive | SSc | slow | monotonic burden accumulation |

## Slide 6 — Validation that the simulator behaves like the disease
**15 sanity tests, all PASS** — covering:
- chronic_relapsing 365-day flare count ∈ [2, 12]
- reversible activity returns within ±1.5 of baseline after trigger
- progressive burden monotonically non-decreasing
- comorbidity rates match YAML within ±10 pp at n = 300
- treatment direction (TNF inhibitor lowers DAS28)
- biomarker outputs always inside YAML range
- byte-for-byte reproducibility under same seed
- **age distribution within ±15 pp** at n = 500
- **age ∈ [20, 90]** for every patient
- **elderly mechanism fires** at age ≥ 70
- **responder distribution within ±5 pp** at n = 400
- **response heterogeneity** under same disease + treatment (CV > 0.12)
- adherence skips happen in ≥ 30 % of treated patients
- life events scheduled for ≥ 50 % of patients
- every patient gets a non-empty subtype

## Slide 7 — Layer-3 prediction model
- Input: past 7 days × 33 features (biomarkers + treatment flags + demographics + disease one-hot).
- Two heads:
  - Regression → tomorrow's activity score.
  - Classification → any flare in the next 7 days.
- LSTM(64) × 2 layers + additive-attention pooling, 58 819 params.
- Patient-level 80/10/10 split (no leakage).

| Task | Metric | Result | 95 % CI |
|---|---|---|---|
| Activity (next day) | MAE | **0.23** | [0.22, 0.24] |
| | R² | **0.91** | [0.90, 0.92] |
| | vs mean baseline MAE | 1.08 → **4.7× better** | |
| Flare (next 7 days) | AUROC | **0.88** | [0.87, 0.89] |
| | AUPRC | **0.73** | [0.71, 0.75] |

## Slide 8 — PWA explorer (live demo)
Five screens, fully offline-capable:
1. **Dashboard** — KPIs, disease/age/responder pyramids.
2. **Patient Browser** — filter + per-patient time series, biomarker panel, life-event ribbon.
3. **Training Mode** — show 60 days, predict next 30; LocalStorage score.
4. **Experiment Mode** — pick a treatment, see super/typical/partial/non-responder distribution.
5. **N-of-1 Mode** — enter your profile, system returns 95 % CI from similar virtual patients.

`manifest.json` + `service-worker.js` (cache-first shell, network-first data), IndexedDB
caches 9.5 MB cohort.json. Works on phone / tablet / desktop.

## Slide 9 — Limitations & ethics
- **Pure synthetic data** — no clinical validity claim.
- Treatment effects use simplified pharmacology (no real PK/PD).
- No external validation against real registries.
- Disclaimer reproduced in every PWA screen footer.
- IRB n/a (no human-subject data).
- PWA stores no PII; only training scores and UI preferences in LocalStorage.

## Slide 10 — Why this matters & next steps
- Demonstrates that physics-based simulation × small-model fine-tuning generates
  decision-support hypotheses **before any real patient data are spent**.
- Roadmap:
  - Layer 4 — Bayesian fusion of real N-of-1 with cohort prior.
  - Calibration vs published RA / asthma registry statistics.
  - Pilot N-of-1 with the developer himself (1 person, IRB-exempt).
  - Add 4th–6th disease YAMLs (Gout / SLE / IBD).
- Open source — disease-agnostic by design, anyone can add a YAML.

---

### Backup slides for Q&A
- Repo dependency graph + LOC table.
- YAML excerpt: how a disease becomes "data, not code".
- Loss curves + early-stopping rationale.
- Why LSTM not Transformer for window_size = 7.
- All 15 sanity tests + pass status.
- PWA screenshots on phone vs desktop.
- References:
  Lillie 2011, Zucker 1997, Walonoski 2018, Topol 2019, FDA 2023,
  Senn 2016, Fulop 2018.
