"""Test — 活世界(world)的純邏輯(不碰後台/DB)。

驗證每日 tick 的關鍵零件：反應式用藥同步、單日紀錄產生、決定論 RNG、
候選者註冊的個人設欄位。
"""

from __future__ import annotations

from datetime import date

from ml import world


def _sim(**over):
    s = {
        "age": 60, "sex": "F", "disease_id": "rheumatoid_arthritis", "sim_day": 377,
        "registered_sim_day": 20, "activity": 3.4, "irreversible_burden": 0.0,
        "mean_act_ref": 3.5, "active_triggers": [],
        "treatments": [{"id": "methotrexate", "class": "csDMARD", "start_day": 10,
                        "onset_days": 28.0, "effect_magnitude": 0.7, "half_life_days": 30}],
        "archetype": "steady",
        "adopted": ["symptoms", "medications", "emotions", "vitals", "sleep", "diet"],
        "adherence_mult": 1.0, "comorbidities": ["depression"], "has_menstrual": False,
        "severity_band": "moderate", "severity_score": 50, "tick_seed": 202400002,
        "churn_at_day": None, "nickname": "黃玉珍",
    }
    s.update(over)
    return s


def test_rng_deterministic():
    a = world._rng(123, 7).random()
    b = world._rng(123, 7).random()
    c = world._rng(123, 8).random()
    assert a == b and a != c


def test_now_day():
    d = world.COHORT_START.date()
    assert world._now_day(d) == 0
    from datetime import timedelta
    assert world._now_day(d + timedelta(days=377)) == 377


def test_sync_meds_adds_app_drug():
    sim = _sim()
    cfg = world.cfg_for("rheumatoid_arthritis")
    changed = world._sync_meds(sim, cfg, {"methotrexate", "tnf_inhibitor"}, 380)
    ids = {t["id"] for t in sim["treatments"]}
    assert changed is True
    assert "tnf_inhibitor" in ids                      # App 新增的藥被併入


def test_sync_meds_removes_stopped_drug():
    sim = _sim()
    cfg = world.cfg_for("rheumatoid_arthritis")
    # App 端此人只剩 nsaid(methotrexate 已停)
    changed = world._sync_meds(sim, cfg, {"nsaid"}, 380)
    ids = {t["id"] for t in sim["treatments"]}
    assert changed is True
    assert "methotrexate" not in ids


def test_day_records_med_log_needs_med_id():
    sim = _sim(adopted=["medications"])
    cfg = world.cfg_for("rheumatoid_arthritis")
    rng = world._rng(sim["tick_seed"], 377)
    # 沒有 med_id → 不應產生用藥紀錄
    recs = world._day_records(sim, cfg, date(2026, 6, 13), 377, True, rng, "u1", None)
    assert "medication_logs" not in recs


def test_register_candidate_returns_consistent_persona():
    import numpy as np
    sim = _sim(sex="M", nickname="林志明")
    rng = np.random.default_rng(1)
    user, prof, meds = world._register_candidate(sim, "ra_0500", 380, rng)
    assert user["username"] == "sim3200_ra_0500"
    assert user["role"] == "patient"
    assert prof["gender"] == "male"                    # 與 sex 一致
    assert prof["current_disease"] == "類風濕關節炎"
    assert all(m["patient_id"] == user["id"] for m in meds)
