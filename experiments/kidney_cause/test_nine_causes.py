# -*- coding: utf-8 -*-
"""nine_causes.py 的意圖測試（合成小資料，只測方法本身）。  python -m pytest test_nine_causes.py"""
import numpy as np
import pandas as pd

import nine_causes as nc
from design_variance import jkn


def _toy(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame(dict(grp=rng.integers(0, 2, n), age_cat=rng.integers(0, 3, n), race=rng.integers(1, 6, n),
                          sex=rng.integers(1, 3, n), w_mec20=rng.uniform(0.5, 3, n),
                          SDMVSTRA=rng.integers(1, 4, n), SDMVPSU=rng.integers(1, 3, n)))
    logit = -1.5 + 0.8 * d["grp"] + 0.5 * d["age_cat"] - 0.3 * (d["sex"] == 2)
    d["y"] = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(float)
    return d


def test_logit_recovers_weighted_log_odds_in_2x2_table():
    # 只有截距＋組別時，MLE 必須等於兩組加權勝算的對數：否則 aOR 就不是勝算比
    d = _toy()
    X = np.column_stack([np.ones(len(d)), d["grp"]])
    y, w, g = d["y"].to_numpy(), d["w_mec20"].to_numpy(), d["grp"].to_numpy()
    b = nc.logit_fit(X, y, w, ridge=0.0)
    p0, p1 = (np.average(y[g == k], weights=w[g == k]) for k in (0, 1))
    lo = lambda p: np.log(p / (1 - p))
    assert np.allclose(b, [lo(p0), lo(p1) - lo(p0)], atol=1e-8)


def test_adjusted_ratio_equals_crude_when_covariates_are_constant():
    # 共變項全部只有一類時，調整與粗盛行率比必須相同：標準化不應憑空改變估計
    d = _toy().assign(age_cat=0, race=1, sex=1)
    X = nc.design_matrix(d, [0, 1])[:, :2]          # 常數共變項欄位會退化，只留截距與組別
    est, _ = nc.theta(X, d["y"].to_numpy(), d["grp"].to_numpy(), d["w_mec20"].to_numpy(), [0, 1])
    assert np.isclose(est[2], est[3], atol=1e-8)    # log 粗 PR == log 調整 PR


def test_jackknife_prevalence_se_matches_existing_design_variance():
    # 新程式的刪一 PSU 摺刀法必須與 design_variance.py（已核對泰勒法）對盛行率給出同一標準誤
    d = _toy()
    design = nc.design_of(d)
    r = nc.analyse(d.assign(lab=d["y"]), "lab", [0, 1], ["無", "有"], design)
    m = d["grp"] == 1
    sub = d[m]
    w_full = np.where(m, d["w_mec20"], 0.0)          # 範圍外權重 0，與 design_variance 的指示變數做法相同
    _, se_ref, _ = jkn(d["y"].to_numpy(), np.where(m, 0.3, 0.6) + 0.01 * d["age_cat"].to_numpy(), w_full,
                       d["SDMVSTRA"].to_numpy(), d["SDMVPSU"].to_numpy(), design)
    assert len(sub) == r["groups"]["有"]["n"]
    assert np.isclose(r["groups"]["有"]["se"], se_ref[0], rtol=1e-9)


def test_hiv_algorithm_follows_cdc_testing_sequence():
    # 2015 起：篩檢陰性→陰性；分型陽性→陽性；分型非陽性時以核酸定案；核酸缺→未知；受檢年齡外→未知
    df = pd.DataFrame(dict(
        cycle=["2017-2018"] * 5 + ["2005-2006"] * 3,
        age=[30, 30, 30, 30, 30, 30, 30, 55],
        LBXHIVC=[2, 1, 1, 1, np.nan, np.nan, np.nan, np.nan],
        LBXHIV1=[np.nan, 1, 2, 2, np.nan, np.nan, np.nan, np.nan],
        LBXHIV2=[np.nan, 2, 2, 2, np.nan, np.nan, np.nan, np.nan],
        LBXHNAT=[np.nan, np.nan, 2, np.nan, np.nan, np.nan, np.nan, np.nan],
        LBDHI=[np.nan] * 5 + [1, 3, 1]))
    got = nc.hiv_label(df)
    want = [0, 1, 0, np.nan, np.nan, 1, np.nan, np.nan]
    assert np.array_equal(got, np.array(want, float), equal_nan=True)
