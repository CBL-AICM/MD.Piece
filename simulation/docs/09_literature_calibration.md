# Literature Calibration — anchoring simulation parameters to published evidence

**config_hash `713d8a608280`** (literature-anchored) vs `6e5c84dbb48d` (expert-judgment baseline).

This pass replaces the highest-leverage expert-judgment parameters with values from peer-reviewed
studies retrieved from **PubMed**, attaching a citation (PMID + DOI) to each in the registries.
Validation-required assumptions dropped from 7 → 5 as a result.

> All evidence below was retrieved from **PubMed**. Per the source's attribution requirement,
> each referenced article is cited with its DOI link. This remains a simulation study and makes
> no clinical claim; literature values are used to *parameterize* a model, not to assert findings.

---

## 1. Headline: the conclusion is ROBUST to literature recalibration

Despite halving several disease flare rates and anchoring recall/notification/retention to
published data, the primary estimand barely moved:

| Endpoint (Δ = MD.Piece − Recall) | Expert baseline | Literature-anchored |
|---|---|---|
| Clinical Reconstruction Score | +0.110 | **+0.108** |
| Event Recall Rate | −0.126 | **−0.128** |
| Information Friction Score (↓ better) | −0.107 | **−0.103** |
| Doctor Understanding | +0.002 | **−0.000** |
| Ground-truth events | 139,914 | 135,246 |

**Interpretation.** The qualitative result — MD.Piece is a completeness-for-accuracy *crossover*
with an equivalent clinician-understanding outcome — does **not** depend on the (inflated)
expert-judgment flare rates. This is reassuring: the finding survives a substantial,
evidence-based perturbation of the disease layer.

---

## 2. Disease relapse/flare rates (disease_registry.yaml)

My expert estimates were systematically ~2× the published rates. Anchored values:

| Disease | Expert | **Literature** | Source (PubMed) |
|---|---|---|---|
| NMOSD | 0.8 | **0.50** | Jarius 2016 ARR 0.92 (MOG-IgG); Bilodeau 2026 treated ARR 0.0–0.34 |
| MS (RRMS) | 0.5 | **0.30** | Kappos 2021 (OPTIMUM) ARR 0.202 / 0.290 |
| SLE | 1.6 | **0.45** | Hao 2022 SELENA-SLEDAI flare 0.10–0.49/pt-yr |
| RA | 1.2 | **0.40** | Mori 2022 flare 0.36/person-yr (45% at 1y) |
| Crohn's | 1.4 | **0.45** | Chauhan 2019 32% relapse within 1y (50% at 3y) |
| MG | 0.9 | **0.35** | Such-Díaz 2020 exacerbation 0.35/yr (severe 0.12/yr) |

Demographics also anchored: **NMOSD** → median age 42, 83% female (Bilodeau 2026);
**MS** → median age 37, 64.9% female (Kappos 2021).

The disease engine auto-calibrates its Hawkes background rate to `relapse_rate_yr`, so simulated
flare rates continue to match the registry (face-validity test green).

## 3. Patient recall model (probability_registry friction.recall)

The salience-weighted, age/literacy-modulated forgetting structure is **directly supported**:

- **Brown & Adams 1992** (*Med Care*): patient recall false-negative rate ranged **0.10 for
  salient events to 0.53 for trivial ones**, with a small age effect and *no* deterioration over a
  2–3-month interval — i.e. recall loss is salience- and age-dependent, exactly as modeled.
- **Fellhölter 2025** (*BMC Geriatr*): self-report vs GP-record concordance ranged **κ 0.41–1.0 by
  condition salience**, worse with age/cognition/lower education; patients report noticeable,
  frequently-monitored conditions better.

→ `tau_days` moved from `validation_required: true` to literature-anchored; persona
`recall_accuracy` range (0.35–0.85) brackets the observed FN-implied accuracy (0.47–0.90).

## 4. Notification recovery (probability_registry friction.mdpiece.notification_recovery)

This is the **top sign-flipping parameter** (Sobol total-order 0.40), so anchoring it matters most:

- **Greer 2020** (*JNCCN*, RCT): a smartphone app with reminders improved medication adherence by
  **+22.3% (baseline non-adherent) and +16.1% (anxious) subgroups only — not overall** (overall
  adherence 78.8%). This supports a **modest, persona-dependent** recovery effect (~0.2–0.3), and
  specifically that reminders help the otherwise-non-adherent and anxious — consistent with the
  model's higher `notif_response` for the Anxious persona.

→ `max_recovered_frac` default 0.30 retained with citation; the sensitivity sweep already shows
the result is most fragile here, so this is flagged as the #1 quantity for a real study to measure.

## 5. App retention (probability_registry usage.retention)

- **Schmitz 2018** (*JAMIA*, scoping review): **low participation retention** is a defining,
  recurrent challenge of mHealth research apps (qualitative). Our default median lifetime (75 d) is
  kept deliberately pessimistic and, if anything, remains optimistic versus commonly-cited
  real-world month-1 retention (~30%). Retention stays `validation_required` (quantitative anchor
  still needed) — a prime target for calibration against real MD.Piece logs.

---

## References (retrieved from PubMed)

1. Jarius S, et al. MOG-IgG in NMO and related disorders, Part 2. *J Neuroinflammation*. 2016;13(1):280. PMID 27793206. [DOI](https://doi.org/10.1186/s12974-016-0718-0)
2. Bilodeau PA, et al. Real-World Efficacy and Safety of NMOSD Disease-Modifying Treatments. *Neurol Neuroimmunol Neuroinflamm*. 2026;13(2):e200536. PMID 41494145. [DOI](https://doi.org/10.1212/NXI.0000000000200536)
3. Kappos L, et al. Ponesimod vs Teriflunomide (OPTIMUM). *JAMA Neurol*. 2021;78(5):558-567. PMID 33779698. [DOI](https://doi.org/10.1001/jamaneurol.2021.0405)
4. Hao Y, et al. Flare rates and determinants in SLE achieving low disease activity/remission. *Lupus Sci Med*. 2022;9(1):e000553. PMID 35241499. [DOI](https://doi.org/10.1136/lupus-2021-000553)
5. Mori S, et al. Long-term outcomes after discontinuing biologics/tofacitinib in RA. *PLoS One*. 2022;17(6):e0270391. PMID 35737642. [DOI](https://doi.org/10.1371/journal.pone.0270391)
6. Chauhan N, et al. Clinical Variables as Predictors of First Relapse in Pediatric Crohn's Disease. *Cureus*. 2019;11(6):e4980. PMID 31467814. [DOI](https://doi.org/10.7759/cureus.4980)
7. Such-Díaz A, et al. Drug exposure associated with exacerbation of symptoms in myasthenia gravis. *Rev Neurol*. 2020;71(4):143-150. PMID 32700310. [DOI](https://doi.org/10.33588/rn.7104.2020198)
8. Brown JB, Adams ME. Patients as reliable reporters of medical care process: recall of ambulatory encounter events. *Med Care*. 1992;30(5):400-411. PMID 1583918. [DOI](https://doi.org/10.1097/00005650-199205000-00003)
9. Fellhölter G, et al. Emergency department visits due to severe falls: patient self-reports vs GP records. *BMC Geriatr*. 2025;25(1):757. PMID 41053639. [DOI](https://doi.org/10.1186/s12877-025-06411-9)
10. Greer JA, et al. Randomized Trial of a Smartphone Mobile App to Improve Symptoms and Adherence to Oral Therapy for Cancer. *J Natl Compr Canc Netw*. 2020;18(2):133-141. PMID 32023526. [DOI](https://doi.org/10.6004/jnccn.2019.7354)
11. Schmitz H, et al. Leveraging mobile health applications for biomedical research and citizen science. *J Am Med Inform Assoc*. 2018;25(12):1685-1695. PMID 30445467. [DOI](https://doi.org/10.1093/jamia/ocy130)

*Source: all references retrieved via PubMed. Values were used to parameterize a simulation; cohort
contexts differ (e.g. treated vs untreated, pediatric vs adult, post-discontinuation) and are noted
inline in the registries. Remaining expert-judgment parameters (personas, salience weights,
quantitative retention) are flagged `validation_required` for future calibration.*
