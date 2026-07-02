"""L1 Patient Generator (arch §4 L1).

Patients are NOT 15 independent marginal draws. A single latent "advantage" factor
z ~ N(0,1) loads onto SES, education, both literacies, access, and adherence (a one-factor
Gaussian copula) with a per-axis residual so health- and tech-literacy can dissociate
(e.g. a health-literate but tech-avoidant elder). This deliberately creates the adoption-
selection confound (assumption A04/A05) which evaluation later adjusts for.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

from simulation.common import Config, PatientRow


def _disease(rng: np.random.Generator, cfg: Config) -> str:
    mix = cfg.population["disease_mix"]
    diseases = list(mix.keys())
    probs = np.array([mix[d] for d in diseases], dtype=float)
    return diseases[rng.choice(len(diseases), p=probs)]


def _ordinal_from_dist(u: float, dist: list[float]) -> int:
    """Map a uniform u in [0,1] to an ordinal index via the cumulative distribution."""
    c = np.cumsum(dist)
    return int(np.searchsorted(c, u, side="right"))


def generate_patient(index: int, rng: np.random.Generator, cfg: Config) -> PatientRow:
    pop = cfg.population
    lf = pop["latent_factor"]
    loadings = lf["loadings"]
    resid_sd = float(lf["residual_sd"])

    disease = _disease(rng, cfg)
    dreg = cfg.disease_registry[disease]

    # demographics conditional on disease
    a = dreg["age_sex"]
    age = int(np.clip(rng.normal(a["mean_age"], a["sd_age"]), 18, 95))
    sex = "F" if rng.random() < a["sex"]["F"] else "M"
    severity = _ordinal_from_dist(rng.random(), dreg["severity_dist"])
    # disease duration: exponential-ish, longer for older patients (truncated)
    disease_duration_yrs = float(np.clip(rng.exponential(5.0) * (0.5 + age / 100), 0.1, age - 17))

    # --- latent advantage factor z and the correlated socio-cognitive attributes ---
    z = float(rng.normal(0.0, 1.0))

    def corr_unit(load_key: str) -> float:
        """A [0,1] attribute correlated with z (via Gaussian copula) + idiosyncratic residual."""
        latent = float(loadings[load_key]) * z + resid_sd * rng.normal()
        # standardize the composite then push through the normal CDF -> ~uniform[0,1] marginal
        scale = np.sqrt(float(loadings[load_key]) ** 2 + resid_sd ** 2)
        return float(norm.cdf(latent / scale))

    health_literacy = corr_unit("health_literacy")
    tech_literacy = corr_unit("tech_literacy")
    baseline_adherence = corr_unit("baseline_adherence")

    # elderly digital divide: tech literacy decremented for age over 60
    tech_literacy = float(np.clip(
        tech_literacy - lf["age_tech_penalty"] * max(0, age - 60), 0.0, 1.0))

    ses_quintile = _ordinal_from_dist(corr_unit("ses"), pop["ses_dist"]) + 1
    education_level = _ordinal_from_dist(corr_unit("education"), pop["education_dist"])
    clinic_access = _ordinal_from_dist(corr_unit("clinic_access"), pop["clinic_access_dist"])

    # insurance: weakly tied to SES; kept near-marginal (minor influence)
    ins = pop["insurance_dist"]
    insurance = list(ins.keys())[rng.choice(len(ins), p=np.array(list(ins.values())))]

    # caregiver support: rises with age and severity
    cg = pop["caregiver"]
    p_support = cg["base_prob"] + cg["severity_bonus_per_level"] * severity
    if age >= 65:
        p_support = max(p_support, cg["age65_plus_prob"])
    p_support = min(p_support, 0.95)
    if rng.random() < p_support:
        caregiver_support = 1.0 if rng.random() < cg["full_proxy_share"] else 0.5
    else:
        caregiver_support = 0.0

    # comorbidity count
    com = pop["comorbidity"]
    lam = com["poisson_lambda_base"] + com["age_scaling"] * max(0, age - 50)
    comorbidity_count = int(rng.poisson(lam))

    return PatientRow(
        patient_id=f"P{index + 1:05d}",
        age=age,
        sex=sex,
        disease=disease,
        severity=severity,
        disease_duration_yrs=round(disease_duration_yrs, 2),
        comorbidity_count=comorbidity_count,
        ses_quintile=ses_quintile,
        education_level=education_level,
        health_literacy=round(health_literacy, 4),
        tech_literacy=round(tech_literacy, 4),
        caregiver_support=caregiver_support,
        clinic_access=clinic_access,
        insurance=insurance,
        baseline_adherence=round(baseline_adherence, 4),
        latent_advantage_z=round(z, 4),
    )
