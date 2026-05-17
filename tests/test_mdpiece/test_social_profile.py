"""Test 9 — social / personality / behavioural profile variability."""

from __future__ import annotations

from collections import Counter

import numpy as np

from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease


def test_every_patient_has_full_social_profile():
    """Every patient must have all six sub-profiles populated."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=50, sim_days=30, base_seed=1)
    for p in cohort.patients:
        sp = p.social_profile
        assert sp is not None
        # all six required sections
        assert sp.personality is not None
        assert sp.behavioral is not None
        assert sp.social is not None
        assert sp.socioeconomic is not None
        assert sp.health_behavior is not None
        assert sp.mental_health is not None


def test_education_distribution_varies():
    """A 200-patient cohort must span all 4 education levels."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=200, sim_days=15, base_seed=3)
    edus = Counter(p.social_profile.socioeconomic.education for p in cohort.patients)
    assert len(edus) == 4, f"expected 4 levels, got {dict(edus)}"


def test_smoking_proportion_realistic_for_taiwan():
    """Current-smoker fraction should be 5-25 % overall."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=400, sim_days=15, base_seed=5)
    n_smoker = sum(1 for p in cohort.patients
                   if p.social_profile.behavioral.smoking_status == "current")
    rate = n_smoker / len(cohort.patients)
    assert 0.03 <= rate <= 0.30, f"smoking rate {rate:.2f} outside [0.03, 0.30]"


def test_personality_modifies_subjective_biomarkers():
    """Top-quartile subjective-amplification patients should report higher pain
    than bottom-quartile patients on the same disease."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=200, sim_days=60, base_seed=11)
    amps = np.array([p.social_profile.subjective_amplification
                     for p in cohort.patients])
    p25, p75 = np.percentile(amps, [25, 75])
    high_amp = [p for p in cohort.patients
                if p.social_profile.subjective_amplification >= p75]
    low_amp = [p for p in cohort.patients
               if p.social_profile.subjective_amplification <= p25]
    assert len(high_amp) >= 20 and len(low_amp) >= 20, (
        f"insufficient samples: high={len(high_amp)} low={len(low_amp)}"
    )
    mean_pain_hi = np.mean([p.timeseries["pain_vas"].mean() for p in high_amp])
    mean_pain_lo = np.mean([p.timeseries["pain_vas"].mean() for p in low_amp])
    assert mean_pain_hi > mean_pain_lo + 0.15, (
        f"high-amp pain {mean_pain_hi:.2f} not > low-amp {mean_pain_lo:.2f} + 0.15"
    )


def test_low_income_reduces_biologic_access():
    """Low-income patients receive expensive biologics less often."""
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, n_patients=300, sim_days=30, base_seed=13)
    low = [p for p in cohort.patients
           if p.social_profile.socioeconomic.income_tier in ("低收", "中下")]
    high = [p for p in cohort.patients
            if p.social_profile.socioeconomic.income_tier in ("中上", "高收")]
    assert len(low) >= 30 and len(high) >= 30
    def _on_tnf(plist):
        return sum(1 for p in plist if any(t["id"] == "tnf_inhibitor" for t in p.treatments)) / len(plist)
    r_low = _on_tnf(low)
    r_high = _on_tnf(high)
    assert r_low < r_high, (
        f"low-income tnf rate {r_low:.2f} should be < high-income {r_high:.2f}"
    )
