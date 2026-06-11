"""Test — MD.Piece App 使用模擬：驗證行為背後的『為什麼』(規則 9)。

不只是檢查程式有跑，而是驗證：
  - 同種子可重現（科學可信度）
  - 註冊選取剛好 N 位
  - 未註冊者不產生紀錄、且有原因
  - 高參與 profile 真的用得比低參與多（模型有編碼「參與度的成因」）
  - 用藥記錄完成率反映既有 adherence（依從差→更常忘記/沒記）
  - 反應型患者在 flare 日記得更多（症狀驅動）
  - 地區欄位有被指派（社經 profile 擴充生效）
  - 留存隨時間下降（流失定律）
"""

from __future__ import annotations

import numpy as np

from md_piece import app_usage as au
from md_piece.cohort_generator import generate_cohort
from md_piece.disease_loader import load_disease
from md_piece.social_profile import REGIONS, build_full_profile

SIM = 365
FLAT = np.full(SIM, 2.0, dtype=np.float32)        # 平穩低活動度
NOFLARE = np.zeros(SIM, dtype=np.int8)


def _profile(seed, **over):
    """造一個 profile 並覆寫指定欄位，方便控制變因。"""
    rng = np.random.default_rng(seed)
    prof = build_full_profile(50, "F", "35-55", rng)
    for k, v in over.items():
        if k in ("health_literacy", "trust_in_medicine"):
            setattr(prof.health_behavior, k, v)
        elif k in ("family_support", "living_arrangement"):
            setattr(prof.social, k, v)
        elif k == "conscientiousness":
            setattr(prof.personality, k, v)
        elif k == "adherence_multiplier":
            prof.adherence_multiplier = v
    return prof


def _usage(profile, seed, *, age=50, activity=FLAT, flare=NOFLARE,
           registered=True, join_day=0):
    return au.simulate_patient_usage(
        patient_id="T", disease_id="rheumatoid_arthritis", age=age, sex="F",
        profile=profile, comorbidities=[], has_treatments=True,
        activity=activity, in_flare=flare, registered=registered,
        join_day=join_day, sim_days=SIM, seed=seed,
    )


def test_determinism_same_seed_same_record():
    prof = _profile(1)
    a = _usage(prof, seed=42)
    b = _usage(prof, seed=42)
    assert a.archetype == b.archetype
    assert a.active_days == b.active_days
    assert a.total_records == b.total_records
    assert a.med_log_adherence == b.med_log_adherence


def test_select_exactly_n_registered():
    props = {f"p{i}": (i % 100) / 100.0 for i in range(500)}
    chosen = au.select_registered(props, 160, seed=7)
    assert len(chosen) == 160
    assert chosen == au.select_registered(props, 160, seed=7)   # 可重現


def test_unregistered_has_reason_and_no_records():
    prof = _profile(3, health_literacy="低")
    rec = _usage(prof, seed=3, registered=False)
    assert rec.registered is False
    assert rec.total_records == 0
    assert rec.archetype == ""
    assert rec.non_registration_reason != ""


def test_engagement_gradient_high_beats_low():
    """高盡責+高識讀+高信任 應比 低識讀+低盡責+高齡獨居 用得更多。"""
    hi, lo = [], []
    for s in range(20):
        p_hi = _profile(s, conscientiousness=0.9, health_literacy="高",
                        trust_in_medicine=0.9, family_support="高")
        p_lo = _profile(s, conscientiousness=0.2, health_literacy="低",
                        trust_in_medicine=0.3, family_support="低",
                        living_arrangement="alone")
        hi.append(_usage(p_hi, seed=1000 + s, age=50).active_days)
        lo.append(_usage(p_lo, seed=1000 + s, age=78).active_days)
    assert np.mean(hi) > np.mean(lo) * 1.5


def test_med_logging_reflects_adherence():
    """adherence_multiplier 高(依從差) → med_log_adherence 低（忘記/沒記更多）。"""
    good, bad = [], []
    for s in range(20):
        pg = _profile(s, adherence_multiplier=0.4)   # 依從好
        pb = _profile(s, adherence_multiplier=2.6)   # 依從差
        good.append(_usage(pg, seed=2000 + s).med_log_adherence)
        bad.append(_usage(pb, seed=2000 + s).med_log_adherence)
    assert np.mean(good) > np.mean(bad)


def test_reactive_logs_more_symptoms_on_flares():
    """同一人、同種子，活動度有 flare 時症狀紀錄應 ≥ 平穩時。"""
    flares = NOFLARE.copy()
    act = FLAT.copy()
    for start in range(40, SIM, 60):                 # 週期性 flare
        flares[start:start + 8] = 1
        act[start:start + 8] = 6.0
    more, less = [], []
    for s in range(25):
        prof = _profile(s)
        r_flare = _usage(prof, seed=3000 + s, activity=act, flare=flares)
        r_flat = _usage(prof, seed=3000 + s, activity=FLAT, flare=NOFLARE)
        more.append(r_flare.features["symptoms"]["n_records"])
        less.append(r_flat.features["symptoms"]["n_records"])
    assert np.mean(more) > np.mean(less)


def test_region_assigned_to_every_patient():
    valid_counties = {r[0] for r in REGIONS}
    valid_macro = {r[1] for r in REGIONS}
    cfg = load_disease("rheumatoid_arthritis")
    cohort = generate_cohort(cfg, 40, 30, base_seed=5)
    for p in cohort.patients:
        se = p.social_profile.socioeconomic
        assert se.region in valid_counties
        assert se.region_macro in valid_macro


def test_retention_declines_over_time():
    """留存應隨時間非遞增：D7 ≥ D90 ≥ D365（流失定律）。"""
    recs = []
    for s in range(120):
        prof = build_full_profile(50, "F", "35-55", np.random.default_rng(s))
        recs.append(_usage(prof, seed=4000 + s, join_day=0))
    d7 = np.mean([r.retained["D7"] for r in recs])
    d90 = np.mean([r.retained["D90"] for r in recs])
    d365 = np.mean([r.retained["D365"] for r in recs])
    assert d7 >= d90 >= d365
    assert d365 < d7        # 確實有流失
