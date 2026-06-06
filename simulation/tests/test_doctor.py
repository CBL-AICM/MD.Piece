"""L8 doctor-engine tests. Verify the last-mile friction mechanisms (Rule 9)."""
from __future__ import annotations

import numpy as np
import pytest

from simulation.common import load_config
from simulation.doctor_engine import review_record, assign_physician


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _understanding(cfg, persona, completeness, snr, n_events, accuracy, seed=0):
    # average over draws so the Bernoulli 'reviewed' gate doesn't dominate the comparison
    vals = []
    for s in range(40):
        rng = np.random.default_rng(seed + s)
        d = review_record(persona, completeness, snr, n_events, rng, cfg, accuracy=accuracy)
        vals.append(d["doctor_understanding"])
    return float(np.mean(vals))


def test_inaccurate_record_yields_false_confidence_discount(cfg):
    """A complete but INACCURATE record (wrong dates/severities) must yield LESS true
    understanding than an equally complete ACCURATE one. This is the A11 fix — without the
    accuracy discount, recall's misdated volume would buy unearned 'understanding'."""
    accurate = _understanding(cfg, "MODERATELY_ENGAGED", completeness=0.8, snr=0.6, n_events=40, accuracy=0.95)
    garbled = _understanding(cfg, "MODERATELY_ENGAGED", completeness=0.8, snr=0.6, n_events=40, accuracy=0.4)
    assert accurate > garbled + 0.05, f"accurate={accurate:.3f} should beat garbled={garbled:.3f}"


def test_time_constrained_extracts_less(cfg):
    """A time-constrained physician understands less of the SAME record than a highly engaged one."""
    engaged = _understanding(cfg, "HIGHLY_ENGAGED", 0.8, 0.6, 80, 0.9)
    rushed = _understanding(cfg, "TIME_CONSTRAINED", 0.8, 0.6, 80, 0.9)
    assert engaged > rushed, f"engaged={engaged:.3f} should exceed time-constrained={rushed:.3f}"


def test_noise_reduces_understanding(cfg):
    """Low signal-to-noise reduces understanding even at equal completeness (arch §4 L8)."""
    clean = _understanding(cfg, "DATA_ORIENTED", 0.7, 0.9, 30, 0.9)
    noisy = _understanding(cfg, "DATA_ORIENTED", 0.7, 0.3, 30, 0.9)
    assert clean > noisy, f"clean={clean:.3f} should exceed noisy={noisy:.3f}"


def test_unreviewed_is_zero_understanding(cfg):
    """If the physician never reviews, understanding is 0 and the record is fully unreviewed."""
    rng = np.random.default_rng(1)
    # TRADITIONAL has a strong negative review offset; find a non-reviewed outcome
    outs = [review_record("TRADITIONAL", 0.8, 0.6, 30, np.random.default_rng(s), cfg) for s in range(50)]
    not_reviewed = [o for o in outs if not o["reviewed"]]
    assert not_reviewed, "expected some non-reviews for a low-review-probability physician"
    assert all(o["doctor_understanding"] == 0.0 and o["unreviewed_fraction"] == 1.0 for o in not_reviewed)


def test_specialty_routing(cfg):
    """Disease routes to the right specialty (face validity)."""
    rng = np.random.default_rng(0)
    assert assign_physician("MS", rng, cfg)[1] == "NEUROLOGY"
    assert assign_physician("RA", rng, cfg)[1] == "RHEUMATOLOGY"
    assert assign_physician("CROHN", rng, cfg)[1] == "GASTROENTEROLOGY"
