"""L5 friction-engine tests — the core. Each encodes the research-relevant intent (Rule 9):
the asymmetry between the two observers, and the V-SANITY bias check.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from simulation.common import load_config
from simulation.build_arms import build_arms, event_recall_rate


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def arms(cfg):
    patients, truth, recall, mdp = build_arms(cfg, n=1000)
    return patients, truth, recall, mdp


def _truth_capture(truth: pd.DataFrame, arm: pd.DataFrame) -> pd.DataFrame:
    """Annotate each ground-truth event with whether the arm captured it (TP)."""
    keys = arm.dropna(subset=["true_event_id"])[["patient_id", "true_event_id"]].drop_duplicates()
    keys["captured"] = True
    m = truth.merge(keys, left_on=["patient_id", "event_id"],
                    right_on=["patient_id", "true_event_id"], how="left")
    m["captured"] = m["captured"].fillna(False)
    return m


# ---------------------------------------------------------------- recall asymmetries
def test_recall_decays_with_event_age(arms, cfg):
    """V-INT-3: recall captures recent events better than old ones (forgetting bites)."""
    _, truth, recall, _ = arms
    m = _truth_capture(truth, recall)
    recall_day = cfg.horizon_days - 1
    m["age"] = recall_day - m["event_date_true"]
    recent = m[m["age"] < 60]["captured"].mean()
    old = m[m["age"] > 270]["captured"].mean()
    assert recent > old + 0.05, f"recall should favor recent events: recent={recent:.3f} old={old:.3f}"


def test_recall_favors_salient_events(arms):
    """Salient events (hospitalizations) are recalled far better than trivial ones (symptoms)."""
    _, truth, recall, _ = arms
    m = _truth_capture(truth, recall)
    hi = m[m["salience"] >= 0.9]["captured"].mean()
    lo = m[m["salience"] <= 0.35]["captured"].mean()
    assert hi > lo + 0.1, f"salient recall {hi:.3f} should exceed trivial recall {lo:.3f}"


# ---------------------------------------------------------------- the core asymmetry
def test_mdpiece_dates_more_accurate_than_recall(arms):
    """MD.Piece logs day-of => near-zero temporal error; recall telescopes dates."""
    _, _, recall, mdp = arms
    rec_err = recall.dropna(subset=["true_event_id"])["temporal_error_days"].abs().mean()
    mdp_err = mdp.dropna(subset=["true_event_id"])["temporal_error_days"].abs().mean()
    assert mdp_err < rec_err, f"mdpiece date error ({mdp_err:.2f}) should beat recall ({rec_err:.2f})"


def test_mdpiece_does_not_fabricate(arms):
    """Prospective logging never invents events; only memory (recall) fabricates."""
    _, _, recall, mdp = arms
    assert not mdp["is_false"].any(), "MD.Piece must not fabricate events"
    # recall is allowed to (and generally does) produce some false memories
    assert recall["is_false"].sum() >= 0


# ---------------------------------------------------------------- the crossover (H2)
def test_persona_crossover(arms):
    """H2: MD.Piece helps engaged/caregiver personas and harms disengaged ones — a crossover,
    not a uniform lift. If MD.Piece were modeled as a perfect recorder, every delta would be
    positive and this would fail (catching the anti-strawman violation, arch §2.1)."""
    patients, truth, recall, mdp = arms
    df = patients.assign(
        recall=event_recall_rate(patients, truth, recall).values,
        mdpiece=event_recall_rate(patients, truth, mdp).values,
    )
    df["delta"] = df["mdpiece"] - df["recall"]
    d = df.groupby("persona")["delta"].mean()
    assert d["CAREGIVER_MANAGED"] > 0.1, "caregiver-managed should benefit"
    assert d["PERFECT_LOGGER"] > 0.0, "perfect logger should benefit"
    assert d["TECH_AVOIDANT"] < 0.0, "tech-avoidant should be harmed"
    assert d["LOW_ENGAGEMENT"] < 0.0, "low-engagement should be harmed"
    # a genuine crossover: best persona positive AND worst persona negative
    assert d.max() > 0 and d.min() < 0


# ---------------------------------------------------------------- the bias gate
def test_v_sanity_parity(cfg):
    """V-SANITY (arch §10): with MD.Piece reduced to the recall process, the MDPIECE-RECALL
    effect must vanish. A non-zero effect here would mean the metric/bookkeeping is biased and
    NO downstream result is trustworthy. This is the single most important test in the suite."""
    patients, truth, recall, mdp = build_arms(cfg, n=800, parity=True)
    rr_recall = event_recall_rate(patients, truth, recall)
    rr_mdp = event_recall_rate(patients, truth, mdp)
    delta = float((rr_mdp - rr_recall).mean())
    assert abs(delta) < 0.04, f"parity effect should be ~0, got {delta:+.3f} (metric machinery biased!)"
