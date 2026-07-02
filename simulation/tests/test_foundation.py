"""Phase 5 foundation tests. Each verifies INTENT (Rule 9), not just execution:
a test that still passes when the business logic breaks is worthless.

Covers: determinism (T-DET-1), scale/worker invariance (T-DET-2), the deliberate
adoption-selection confound (V-INT-2), config fail-loud, and basic face validity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from simulation.common import load_config, PERSONAS, DISEASES
from simulation.build_population import build_population


@pytest.fixture(scope="module")
def cfg():
    return load_config()


# ---------------------------------------------------------------- determinism
def test_reproducible_same_seed(cfg):
    """T-DET-1: identical config+seed => byte-identical population."""
    a = build_population(cfg, n=150)
    b = build_population(cfg, n=150)
    pd.testing.assert_frame_equal(a, b)


def test_scale_invariance(cfg):
    """T-DET-2: patient i depends ONLY on its spawned stream, not on n_patients or order.

    If this fails, parallel runs with different worker counts would diverge — the whole
    reproducibility guarantee (arch §3.3) is void.
    """
    small = build_population(cfg, n=100)
    large = build_population(cfg, n=300)
    pd.testing.assert_frame_equal(small, large.iloc[:100].reset_index(drop=True))


# ---------------------------------------------------------------- the confound
def test_adoption_selection_confound_present(cfg):
    """V-INT-2: adopters skew higher tech-literacy ON PURPOSE (assumption A05).

    This is not a nuisance — it's a designed feature so evaluation can adjust for it.
    The test encodes WHY: if persona assignment were independent of attributes (a real
    bug that would silently inflate or distort the MD.Piece effect), the correlation
    would vanish and this test would fail. That is exactly the failure we want to catch.
    """
    df = build_population(cfg, n=2000)
    eng = cfg.persona_registry["personas"]
    df = df.assign(engagement=df["persona"].map(lambda p: eng[p]["engagement_level"]))

    r = np.corrcoef(df["tech_literacy"], df["engagement"])[0, 1]
    assert r > 0.2, f"expected positive tech_literacy~engagement correlation, got r={r:.3f}"

    by_persona = df.groupby("persona")["tech_literacy"].mean()
    assert by_persona["PERFECT_LOGGER"] > by_persona["TECH_AVOIDANT"], (
        "adopter persona should have higher mean tech-literacy than the tech-avoidant one"
    )


def test_latent_factor_correlates_attributes(cfg):
    """Single latent advantage factor really does couple the socio-cognitive attributes (A04)."""
    df = build_population(cfg, n=2000)
    assert np.corrcoef(df["latent_advantage_z"], df["health_literacy"])[0, 1] > 0.2
    assert np.corrcoef(df["latent_advantage_z"], df["baseline_adherence"])[0, 1] > 0.2
    # health and tech literacy are correlated but must NOT be collapsed into one (per-axis residual)
    rht = np.corrcoef(df["health_literacy"], df["tech_literacy"])[0, 1]
    assert 0.1 < rht < 0.95, f"literacies should be correlated but dissociable, r={rht:.3f}"


# ---------------------------------------------------------------- face validity
def test_disease_mix_matches_config(cfg):
    df = build_population(cfg, n=3000)
    target = cfg.population["disease_mix"]
    got = df["disease"].value_counts(normalize=True)
    for d in DISEASES:
        assert abs(got.get(d, 0.0) - target[d]) < 0.03, f"{d}: {got.get(d,0):.3f} vs {target[d]}"


def test_attribute_ranges(cfg):
    df = build_population(cfg, n=500)
    assert df["age"].between(18, 95).all()
    assert df["severity"].between(0, 4).all()
    assert df["ses_quintile"].between(1, 5).all()
    assert df["education_level"].between(0, 3).all()
    assert df["health_literacy"].between(0, 1).all()
    assert df["tech_literacy"].between(0, 1).all()
    assert set(df["persona"]).issubset(set(PERSONAS))


def test_elderly_tech_penalty(cfg):
    """Digital divide: older patients should have lower mean tech-literacy."""
    df = build_population(cfg, n=3000)
    young = df[df["age"] < 50]["tech_literacy"].mean()
    old = df[df["age"] >= 70]["tech_literacy"].mean()
    assert old < young, f"expected elderly tech-literacy lower: old={old:.3f} young={young:.3f}"


def test_config_validation_catches_bad_mix(cfg):
    """Fail-loud (Rule 12): a disease mix that doesn't sum to 1 must raise, not silently run."""
    from simulation.common import _validate_config
    bad = {
        "population": {"disease_mix": {d: 0.1 for d in DISEASES}},  # sums to 0.7
        "persona_registry": cfg.persona_registry,
        "disease_registry": cfg.disease_registry,
    }
    with pytest.raises(ValueError, match="disease_mix must sum"):
        _validate_config(bad)
