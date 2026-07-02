"""L2+L3 disease/utilization engine tests. Each encodes a mechanism's INTENT (Rule 9):
the test fails if the clinical logic breaks, not merely if the code throws.

Built once at moderate n and reused (module fixture) to keep runtime sane.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from simulation.common import load_config
from simulation.build_ground_truth import build_ground_truth


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def gt(cfg):
    patients, events = build_ground_truth(cfg, n=1500)
    events = events.merge(patients[["patient_id", "disease", "severity", "clinic_access"]],
                          on="patient_id", how="left")
    return patients, events


# ---------------------------------------------------------------- determinism
def test_ground_truth_reproducible(cfg):
    _, e1 = build_ground_truth(cfg, n=120)
    _, e2 = build_ground_truth(cfg, n=120)
    pd.testing.assert_frame_equal(e1, e2)


# ---------------------------------------------------------------- the regression guard
def test_hawkes_not_supercritical(gt):
    """REGRESSION GUARD for the branching-ratio bug: a stationary Hawkes process must NOT
    produce hundreds of flares/patient. If hawkes_excitation is ever mis-used as a raw
    kernel weight again (branching ratio > 1), flare counts explode and this fails."""
    patients, events = gt
    flares = events[events["event_type"] == "FLARE"]
    per_pt = flares.groupby("patient_id").size()
    assert per_pt.max() < 25, f"flare count per patient exploded: max={per_pt.max()}"
    overall = len(flares) / len(patients)
    assert overall < 5, f"population flare rate implausibly high: {overall:.1f}/patient-yr"


# ---------------------------------------------------------------- face validity
def test_flare_rate_matches_registry(gt, cfg):
    """V-FACE-1: simulated flare/patient-year ~ registry relapse_rate_yr (auto-calibration)."""
    patients, events = gt
    yrs = cfg.horizon_days / 365.0
    flares = events[events["event_type"] == "FLARE"]
    per_pt = flares.groupby("patient_id").size().reindex(patients["patient_id"], fill_value=0)
    sim = patients.assign(f=per_pt.values).groupby("disease")["f"].mean() / yrs
    for d in sim.index:
        target = cfg.disease_registry[d]["relapse_rate_yr"]
        assert abs(sim[d] - target) < 0.5, f"{d}: sim={sim[d]:.2f} vs registry={target:.2f}"


def test_event_load_rises_with_severity(gt):
    """V-INT-1: sicker patients accrue more ground-truth events."""
    patients, events = gt
    ec = events.groupby("patient_id").size().reindex(patients["patient_id"], fill_value=0)
    p = patients.assign(n=ec.values)
    r = np.corrcoef(p["severity"], p["n"])[0, 1]
    assert r > 0.25, f"event load should rise with severity, r={r:.3f}"
    assert p[p.severity >= 3]["n"].mean() > p[p.severity <= 1]["n"].mean()


def test_ed_substitution_for_poor_access(gt):
    """Social determinant (arch §4 L2): poor clinic access drives ED substitution."""
    patients, events = gt
    ed = events[events["event_type"] == "EMERGENCY_VISIT"]
    edpt = ed.groupby("patient_id").size().reindex(patients["patient_id"], fill_value=0)
    by_acc = patients.assign(ed=edpt.values).groupby("clinic_access")["ed"].mean()
    assert by_acc[0] > by_acc[2], f"poor-access ED ({by_acc[0]:.2f}) should exceed good-access ({by_acc[2]:.2f})"


def test_infection_seasonality(gt, cfg):
    """Infections follow the seasonal Poisson hazard (cluster near the winter peak)."""
    _, events = gt
    inf = events[events["event_type"] == "INFECTION"]["event_date_true"]
    winter = ((inf >= 0) & (inf < 45)).sum()      # around peak_day=15
    summer = ((inf >= 180) & (inf < 225)).sum()
    assert winter > summer, f"expected winter>summer infections, got {winter} vs {summer}"


# ---------------------------------------------------------------- event-chain integrity
def test_hospitalization_triggers_escalation(gt):
    """The infection→worsening→admission→escalation chain: every admission is paired with a
    same-day medication change (treatment escalation)."""
    _, events = gt
    hosp = events[events["event_type"] == "HOSPITALIZATION"][["patient_id", "event_date_true"]]
    med = events[(events["event_type"] == "MEDICATION_CHANGE")][["patient_id", "event_date_true"]]
    merged = hosp.merge(med, on=["patient_id", "event_date_true"], how="left", indicator=True)
    assert (merged["_merge"] == "both").all(), "every hospitalization should trigger an escalation"


def test_no_infusion_for_non_infusion_disease(gt):
    """Structural: SLE has infusion_interval=null in the registry => no INFUSION events."""
    _, events = gt
    sle_infusions = events[(events["disease"] == "SLE") & (events["event_type"] == "INFUSION")]
    assert len(sle_infusions) == 0, "SLE (no maintenance infusion) should not produce INFUSION events"


def test_ground_truth_is_lossless(gt):
    """GROUND_TRUTH is the lossless reference: recorded == true, self-linked, no omission/falsity."""
    _, events = gt
    assert (events["arm"] == "GROUND_TRUTH").all()
    assert (events["event_date_recorded"] == events["event_date_true"]).all()
    assert (events["true_event_id"] == events["event_id"]).all()
    assert not events["is_omitted"].any()
    assert not events["is_false"].any()
