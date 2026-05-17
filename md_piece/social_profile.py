"""第 9 個不可預測性來源：人格 + 行為 + 家庭 + 學歷 + 社經 + 心理健康。

預設人口分布以台灣為參考（教育、保險、TCM 使用率等）。
Reference:
  - Costa & McCrae (1992): Big 5 NEO-PI-R.
  - Kroenke et al. (2001): PHQ-9 depression.
  - Spitzer et al. (2006): GAD-7 anxiety.
  - Edwards et al. (2016) Pain: personality × chronic pain.
  - 行政院主計總處 (2024): 台灣教育、家戶收入分布.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np


# ============================================================================
# Population defaults (Taiwan-flavoured)
# ============================================================================

EDUCATION_LEVELS = ["國中以下", "高中職", "大專", "研究所以上"]
EDUCATION_PROBS_BY_AGE_BIN = {
    "20-35": [0.02, 0.18, 0.55, 0.25],
    "35-55": [0.05, 0.30, 0.50, 0.15],
    "55-70": [0.20, 0.40, 0.35, 0.05],
    "70-90": [0.45, 0.35, 0.18, 0.02],
}

INCOME_TIERS = ["低收", "中下", "中等", "中上", "高收"]
INCOME_PROBS = [0.10, 0.25, 0.35, 0.20, 0.10]

INSURANCE = ["健保_only", "健保+私保", "健保+企業團保"]
INSURANCE_PROBS = [0.55, 0.30, 0.15]

EMPLOYMENT_LEVELS = ["全職", "兼職", "自雇", "失業", "退休", "家管", "學生"]

MARITAL = ["未婚", "已婚", "離婚", "喪偶"]
URBAN_RURAL = ["都會", "城鎮", "鄉村"]
URBAN_PROBS = [0.55, 0.30, 0.15]

DIET_TYPES = ["台式_常見", "地中海", "西式高脂", "素食", "低碳"]
DIET_PROBS = [0.55, 0.10, 0.12, 0.15, 0.08]

SLEEP_QUALITY = ["佳", "普通", "差"]
SOCIAL_SUPPORT = ["高", "中", "低"]
HEALTH_LITERACY = ["低", "中", "高"]


# ============================================================================
# Data classes
# ============================================================================

@dataclass
class PersonalityVector:
    """Big 5 + 延伸（每個值 ∈ [0,1]，0.5 = 人口中位數）。"""
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float
    optimism: float
    self_efficacy: float
    pain_catastrophizing: float


@dataclass
class BehavioralProfile:
    smoking_status: str        # never / former / current
    pack_years: float
    alcohol_units_per_week: float
    exercise_sessions_per_week: int
    sleep_hours_avg: float
    sleep_quality: str
    diet_type: str
    caffeine_cups_per_day: int


@dataclass
class SocialProfile:
    marital_status: str
    children_count: int
    family_support: str
    social_isolation: float    # 0..1
    living_arrangement: str    # alone / with_family / institution


@dataclass
class SocioeconomicProfile:
    education: str
    income_tier: str
    insurance_type: str
    employment_status: str
    urban_rural: str


@dataclass
class HealthBehaviorProfile:
    health_literacy: str
    trust_in_medicine: float       # 0..1
    self_medication_tendency: float
    appointment_adherence: float
    uses_tcm: bool


@dataclass
class MentalHealthProfile:
    phq9_score: int                # 0-27 depression
    gad7_score: int                # 0-21 anxiety
    perceived_stress: float        # 0..1


@dataclass
class FullPersonProfile:
    personality: PersonalityVector
    behavioral: BehavioralProfile
    social: SocialProfile
    socioeconomic: SocioeconomicProfile
    health_behavior: HealthBehaviorProfile
    mental_health: MentalHealthProfile
    # derived modifiers — pre-computed for performance
    adherence_multiplier: float = 1.0          # × daily_miss_probability
    subjective_amplification: float = 1.0      # × subjective biomarker value
    placebo_amplification: float = 1.0         # × placebo response probability
    trigger_amplification: dict = field(default_factory=dict)
    treatment_access_multiplier: dict = field(default_factory=dict)


# ============================================================================
# Samplers
# ============================================================================

def _sample_big5(age: int, rng: np.random.Generator) -> PersonalityVector:
    """Big 5 trait sampling. Slight age effects (conscientiousness ↑ with age)."""
    base = lambda: float(np.clip(rng.normal(0.5, 0.18), 0.0, 1.0))
    cons = float(np.clip(rng.normal(0.45 + (age - 40) * 0.003, 0.18), 0.0, 1.0))
    return PersonalityVector(
        openness=base(),
        conscientiousness=cons,
        extraversion=base(),
        agreeableness=base(),
        neuroticism=base(),
        optimism=base(),
        self_efficacy=base(),
        pain_catastrophizing=base(),
    )


def _sample_behavior(age: int, sex: str, rng: np.random.Generator) -> BehavioralProfile:
    """Health behaviours with realistic Taiwan / age-sex baselines."""
    # smoking — males higher (Taiwan adult ~25% male, ~3% female)
    smoke_base = 0.25 if sex == "M" else 0.03
    smoke_base *= 1.0 if age < 65 else 0.6
    smoke_r = rng.random()
    if smoke_r < smoke_base:
        status = "current"
        pack_years = float(rng.exponential(10)) * (1 + (age - 30) / 50)
    elif smoke_r < smoke_base + 0.10:
        status = "former"
        pack_years = float(rng.exponential(15))
    else:
        status = "never"
        pack_years = 0.0

    # alcohol — males avg 5/wk, females avg 1/wk
    alc_base = 5 if sex == "M" else 1.0
    alc = max(0.0, float(rng.exponential(alc_base)))

    # exercise — ~30% Taiwanese exercise regularly
    ex = max(0, int(rng.poisson(2.0 if age < 60 else 1.5)))

    # sleep
    sh = float(np.clip(rng.normal(6.8, 1.2), 3, 11))
    sq = rng.choice(SLEEP_QUALITY, p=[0.35, 0.45, 0.20])

    diet = rng.choice(DIET_TYPES, p=DIET_PROBS)

    caf = max(0, int(rng.poisson(1.5)))

    return BehavioralProfile(
        smoking_status=status,
        pack_years=pack_years,
        alcohol_units_per_week=alc,
        exercise_sessions_per_week=ex,
        sleep_hours_avg=sh,
        sleep_quality=str(sq),
        diet_type=str(diet),
        caffeine_cups_per_day=caf,
    )


def _sample_social(age: int, sex: str, rng: np.random.Generator) -> SocialProfile:
    # marital: depends on age
    if age < 28:
        marital_p = [0.85, 0.13, 0.02, 0.0]
    elif age < 55:
        marital_p = [0.20, 0.65, 0.13, 0.02]
    elif age < 70:
        marital_p = [0.10, 0.65, 0.15, 0.10]
    else:
        marital_p = [0.05, 0.50, 0.15, 0.30]
    marital = rng.choice(MARITAL, p=marital_p)

    if marital in ("已婚", "離婚", "喪偶"):
        children = int(rng.poisson(1.6 if age >= 30 else 0.5))
    else:
        children = int(rng.poisson(0.1))

    # family support
    fam = rng.choice(SOCIAL_SUPPORT, p=[0.55, 0.30, 0.15])
    if marital == "喪偶" and age >= 70:
        fam = rng.choice(SOCIAL_SUPPORT, p=[0.30, 0.40, 0.30])
    isolation = float(np.clip(rng.normal(0.3, 0.2), 0, 1))
    if marital == "未婚" and age >= 60:
        isolation = float(np.clip(rng.normal(0.55, 0.2), 0, 1))

    if age >= 75 and rng.random() < 0.12:
        living = "institution"
    elif marital in ("未婚", "喪偶", "離婚") and rng.random() < 0.4:
        living = "alone"
    else:
        living = "with_family"

    return SocialProfile(
        marital_status=str(marital),
        children_count=children,
        family_support=str(fam),
        social_isolation=isolation,
        living_arrangement=str(living),
    )


def _sample_socioeconomic(
    age: int, age_bin: str, rng: np.random.Generator
) -> SocioeconomicProfile:
    edu_probs = EDUCATION_PROBS_BY_AGE_BIN[age_bin]
    education = rng.choice(EDUCATION_LEVELS, p=edu_probs)
    # income correlates with education
    edu_idx = EDUCATION_LEVELS.index(str(education))
    base_income_shift = (edu_idx - 1.5) * 0.6
    income_logits = np.array(INCOME_PROBS, dtype=float).copy()
    # shift probability mass towards higher tier for higher education
    if base_income_shift > 0:
        for k in range(len(INCOME_TIERS)):
            income_logits[k] *= np.exp(base_income_shift * (k - 2) / 2)
    income_logits = income_logits / income_logits.sum()
    income = rng.choice(INCOME_TIERS, p=income_logits)

    insurance = rng.choice(INSURANCE, p=INSURANCE_PROBS)
    # higher income → more likely private supplement
    if str(income) in ("中上", "高收"):
        insurance = rng.choice(INSURANCE, p=[0.35, 0.50, 0.15])

    if age >= 65:
        employment = rng.choice(EMPLOYMENT_LEVELS, p=[0.05, 0.05, 0.05, 0.05, 0.75, 0.04, 0.01])
    elif age < 22:
        employment = rng.choice(EMPLOYMENT_LEVELS, p=[0.10, 0.10, 0.02, 0.05, 0.0, 0.03, 0.70])
    else:
        employment = rng.choice(EMPLOYMENT_LEVELS, p=[0.55, 0.10, 0.10, 0.05, 0.0, 0.18, 0.02])

    urban = rng.choice(URBAN_RURAL, p=URBAN_PROBS)

    return SocioeconomicProfile(
        education=str(education),
        income_tier=str(income),
        insurance_type=str(insurance),
        employment_status=str(employment),
        urban_rural=str(urban),
    )


def _sample_health_behavior(
    education: str, age: int, rng: np.random.Generator,
) -> HealthBehaviorProfile:
    # health literacy correlates with education
    edu_idx = EDUCATION_LEVELS.index(education)
    lit_probs = [
        [0.55, 0.35, 0.10],     # 國中以下
        [0.20, 0.55, 0.25],     # 高中職
        [0.05, 0.45, 0.50],     # 大專
        [0.02, 0.28, 0.70],     # 研究所
    ][edu_idx]
    health_literacy = rng.choice(HEALTH_LITERACY, p=lit_probs)

    trust = float(np.clip(rng.normal(0.65, 0.15), 0, 1))
    self_med = float(np.clip(rng.normal(0.25, 0.15), 0, 1))
    appt = float(np.clip(rng.normal(0.75, 0.15), 0, 1))
    if str(health_literacy) == "低":
        appt *= 0.8

    # ~50% Taiwanese adults have used TCM at some point
    tcm_p = 0.55 if age >= 50 else 0.40
    uses_tcm = bool(rng.random() < tcm_p)

    return HealthBehaviorProfile(
        health_literacy=str(health_literacy),
        trust_in_medicine=trust,
        self_medication_tendency=self_med,
        appointment_adherence=appt,
        uses_tcm=uses_tcm,
    )


def _sample_mental_health(
    personality: PersonalityVector,
    social: SocialProfile,
    rng: np.random.Generator,
) -> MentalHealthProfile:
    # PHQ-9 baseline shift by neuroticism + isolation
    base = personality.neuroticism * 8 + social.social_isolation * 4 - personality.optimism * 4
    phq9 = int(np.clip(rng.normal(base + 4, 4), 0, 27))
    gad7 = int(np.clip(rng.normal(personality.neuroticism * 6 + 2, 3), 0, 21))
    stress = float(np.clip(rng.normal(0.4 + personality.neuroticism * 0.3, 0.18), 0, 1))
    return MentalHealthProfile(
        phq9_score=phq9,
        gad7_score=gad7,
        perceived_stress=stress,
    )


# ============================================================================
# Effect computation
# ============================================================================

def _compute_modifiers(profile: FullPersonProfile) -> None:
    """Fill in profile.{adherence,subjective,placebo,trigger,treatment}_multiplier."""
    p = profile.personality
    b = profile.behavioral
    s = profile.social
    se = profile.socioeconomic
    hb = profile.health_behavior
    mh = profile.mental_health

    # --- adherence (smaller = better adherence)
    adh = 1.0
    adh *= (1.0 - p.conscientiousness * 0.5)       # 盡責性
    if hb.health_literacy == "高":   adh *= 0.7
    elif hb.health_literacy == "低": adh *= 1.4
    if s.family_support == "高":     adh *= 0.7
    elif s.family_support == "低":   adh *= 1.5
    if se.education in ("大專", "研究所以上"): adh *= 0.85
    elif se.education == "國中以下":            adh *= 1.2
    if hb.appointment_adherence < 0.5:           adh *= 1.5
    profile.adherence_multiplier = float(np.clip(adh, 0.2, 3.0))

    # --- subjective biomarker amplification
    sa = 1.0
    sa *= (1.0 + p.neuroticism * 0.5)
    sa *= (1.0 + mh.phq9_score / 27 * 0.4)
    sa *= (1.0 + p.pain_catastrophizing * 0.4)
    sa *= (1.0 - p.self_efficacy * 0.2)
    profile.subjective_amplification = float(np.clip(sa, 0.5, 2.5))

    # --- placebo amplification
    pa = 1.0 + (p.optimism - 0.5) * 0.8 + (hb.trust_in_medicine - 0.5) * 0.4
    profile.placebo_amplification = float(np.clip(pa, 0.3, 2.0))

    # --- trigger amplification (per trigger id)
    trig = {}
    if mh.perceived_stress > 0.6:
        trig["emotional_stress"] = 1.5
        trig["stress"] = 1.5
    if b.sleep_hours_avg < 6.0 or b.sleep_quality == "差":
        trig["poor_sleep"] = 2.0
    if b.smoking_status == "current":
        trig["smoke_exposure"] = 2.0
        trig["viral_uri"] = 1.3
    if b.alcohol_units_per_week > 14:
        trig["alcohol"] = 2.0
        trig["dehydration"] = 1.5
    profile.trigger_amplification = trig

    # --- treatment access (per drug class)
    access = {}
    if se.income_tier in ("低收", "中下"):
        # expensive biologics + new antifibrotics get harder to access
        access["bDMARD"] = 0.5
        access["biologic"] = 0.5
        access["antifibrotic"] = 0.4
        access["anti_cd20"] = 0.4
    if se.urban_rural == "鄉村":
        access["bDMARD"] = access.get("bDMARD", 1.0) * 0.7
        access["biologic"] = access.get("biologic", 1.0) * 0.7
    if hb.health_literacy == "低":
        # complex regimens (immunosuppressant) more often skipped
        access["immunosuppressant"] = 0.7
    profile.treatment_access_multiplier = access


# ============================================================================
# Public entrypoint
# ============================================================================

def build_full_profile(
    age: int, sex: str, age_bin: str, rng: np.random.Generator,
) -> FullPersonProfile:
    """One-shot constructor: sample all six dimensions + derive modifiers."""
    personality = _sample_big5(age, rng)
    behavioral = _sample_behavior(age, sex, rng)
    social = _sample_social(age, sex, rng)
    socioeconomic = _sample_socioeconomic(age, age_bin, rng)
    health_behavior = _sample_health_behavior(socioeconomic.education, age, rng)
    mental_health = _sample_mental_health(personality, social, rng)

    profile = FullPersonProfile(
        personality=personality,
        behavioral=behavioral,
        social=social,
        socioeconomic=socioeconomic,
        health_behavior=health_behavior,
        mental_health=mental_health,
    )
    _compute_modifiers(profile)
    return profile


def profile_to_dict(profile: FullPersonProfile) -> dict[str, Any]:
    """JSON-serialisable dict for cohort.json."""
    d = asdict(profile)
    # cohort.json prefers plain types
    return d
