"""Test — ML 強化(enrich_backend)的個人設與嚴重度邏輯(不需模型/後台)。

驗證：
  - 嚴重度在族群中有分布(每人不同)，且 band/score 合法
  - 疾病別 acuity 排序正確(IPF 普遍重於慢性蕁麻疹)
  - patient_profiles 個人設欄位合法且個別化
"""

from __future__ import annotations

import numpy as np

from ml.enrich_backend import assign_severity, build_profile, build_registered_patients


def test_severity_has_spread_and_valid_bands():
    regs = build_registered_patients(40, 365, 320, base_seed=2024, n_workers=2, limit=None)
    sev = assign_severity(regs)
    bands = {b for b, _ in sev.values()}
    assert bands == {"mild", "moderate", "severe"}          # 三個分級都有人
    for b, s in sev.values():
        assert b in ("mild", "moderate", "severe")
        assert 1 <= s <= 100


def test_acuity_orders_serious_above_benign():
    """同樣方法下，IPF 平均嚴重度分數應高於慢性蕁麻疹。"""
    regs = build_registered_patients(40, 365, 320, base_seed=2024, n_workers=2, limit=None)
    sev = assign_severity(regs)
    ipf = [s for p, (b, s) in zip(regs, [sev[p.patient_id] for p in regs])
           if p.disease_id == "idiopathic_pulmonary_fibrosis"]
    cu = [s for p, (b, s) in zip(regs, [sev[p.patient_id] for p in regs])
          if p.disease_id == "chronic_urticaria"]
    assert ipf and cu
    assert np.mean(ipf) > np.mean(cu)


def test_profile_fields_individualised():
    cfg_regs = build_registered_patients(20, 365, 80, base_seed=2024, n_workers=2, limit=20)
    seen_birthdays = set()
    for p in cfg_regs:
        prof = build_profile(p, np.random.default_rng(p.seed ^ 0xD0C7))
        assert prof["gender"] in ("male", "female")
        assert prof["blood"] in ("O", "A", "B", "AB")
        assert 140 <= prof["height_cm"] <= 195
        assert 35 <= prof["weight_kg"] <= 140
        assert prof["current_disease"] and prof["current_disease"] != p.disease_id  # 中文病名
        assert len(prof["birthday"]) == 10
        seen_birthdays.add(prof["birthday"])
    assert len(seen_birthdays) > 1                           # 不是所有人同一天生日
