"""Age stratification (20-90) + elderly mechanisms.

Implements unpredictability source #8.
Reference: Fulop et al., Front Immunol 2018 (immunosenescence).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

AGE_BINS = ["20-35", "35-55", "55-70", "70-90"]

# severity / treatment-response modifiers by age bin
AGE_SEVERITY_MOD = {
    "20-35": 1.2,   # young — acute, high activity
    "35-55": 1.0,   # baseline
    "55-70": 0.9,   # older
    "70-90": 0.7,   # elderly — blunted inflammation
}
AGE_TREATMENT_MOD = {
    "20-35": 1.1,
    "35-55": 1.0,
    "55-70": 0.8,
    "70-90": 0.6,
}

AGE_BIN_RANGES = {
    "20-35": (20, 35),
    "35-55": (35, 55),
    "55-70": (55, 70),
    "70-90": (70, 90),
}


@dataclass
class AgeProfile:
    """Per-patient age-derived modifiers."""
    age: int
    sex: str
    age_bin: str
    severity_modifier: float
    treatment_response_modifier: float
    is_elderly: bool = False
    crp_dampening: float = 1.0          # blunted inflammatory response
    atypical_presentation: bool = False
    frailty_score: float = 0.0          # 0..1
    polypharmacy_count: int = 0
    adverse_event_risk_multiplier: float = 1.0
    elderly_comorbidities: list[str] = field(default_factory=list)


def _bin_for_age(age: int) -> str:
    for b in AGE_BINS:
        lo, hi = AGE_BIN_RANGES[b]
        if lo <= age < hi:
            return b
    return "70-90"  # cap


def sample_age_and_sex(
    age_distribution: dict[str, float],
    sex_ratio_by_age: dict[str, float],
    rng: np.random.Generator,
) -> tuple[int, str, str]:
    """Sample (age, sex, age_bin) from a disease's age × sex joint distribution.

    Parameters
    ----------
    age_distribution : dict
        e.g. {"20-35": 0.15, "35-55": 0.45, ...}.  Probabilities sum ≈ 1.
    sex_ratio_by_age : dict
        female-to-male ratio per bin, e.g. {"20-35": 3.0, ...}.
    rng : np.random.Generator
    """
    bins = list(age_distribution.keys())
    probs = np.array([age_distribution[b] for b in bins], dtype=float)
    probs = probs / probs.sum()
    chosen_bin = rng.choice(bins, p=probs)

    lo, hi = AGE_BIN_RANGES[chosen_bin]
    age = int(rng.integers(lo, hi))

    ratio = float(sex_ratio_by_age.get(chosen_bin, 1.0))
    p_female = ratio / (ratio + 1.0)
    sex = "F" if rng.random() < p_female else "M"
    return age, sex, chosen_bin


def build_age_profile(age: int, sex: str, rng: np.random.Generator) -> AgeProfile:
    """Build the AgeProfile, triggering elderly mechanisms when age >= 70."""
    bin_ = _bin_for_age(age)
    prof = AgeProfile(
        age=age,
        sex=sex,
        age_bin=bin_,
        severity_modifier=AGE_SEVERITY_MOD[bin_],
        treatment_response_modifier=AGE_TREATMENT_MOD[bin_],
    )
    if age >= 70:
        prof.is_elderly = True
        prof.crp_dampening = 0.6
        prof.atypical_presentation = bool(rng.random() < 0.30)
        prof.frailty_score = float(np.clip(
            rng.normal((age - 70) / 20.0 + 0.3, 0.15), 0.0, 1.0
        ))
        prof.polypharmacy_count = int(rng.poisson(6))
        prof.adverse_event_risk_multiplier = 2.0

        # auto-add age-related comorbidities
        auto_comorb = []
        if rng.random() < 0.6:
            auto_comorb.append("hypertension")
        if rng.random() < 0.4:
            auto_comorb.append("diabetes_t2")
        if rng.random() < 0.3:
            auto_comorb.append("ckd")
        if rng.random() < 0.5:
            auto_comorb.append("osteoarthritis")
        if rng.random() < 0.3:
            auto_comorb.append("cataract")
        prof.elderly_comorbidities = auto_comorb
    return prof
