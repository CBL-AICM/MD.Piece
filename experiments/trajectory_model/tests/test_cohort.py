# -*- coding: utf-8 -*-
import os

import numpy as np

from cohort import (load_params, derived_scale, make_cohort, assign_linear_class, _val, X_FOLD)
from fade_components import _detrend

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = load_params(os.path.join(HERE, "params.json"), verbose=False)


def test_every_parameter_row_has_a_source():
    """禁止事項 6：沒有出處不得填軌跡參數。參數檔任何一列缺 source 就該在這裡被抓到。"""
    assert P["_provenance"]["missing_source"] == []
    assert any(d["derived_from"].startswith("assumption") for d in P["_provenance"]["derived"])  # 假設列會被列出


def test_scale_anchors_and_event_threshold():
    """決定書 §2：兩型共用同一 x 刻度，事件門檻是臨床門檻（eGFR 15）映射到 x 的固定值。"""
    sc = derived_scale(P)
    a, b = sc["a"], sc["b"]
    assert abs((a - b * sc["x_healthy"]) - 90) < 1e-9          # 健康穩態 ↔ 90
    assert abs((a - b * X_FOLD) - 60) < 1e-9                    # 摺疊點 ↔ 60
    assert abs(sc["x_event"] - (a - 15) / b) < 1e-12            # 事件門檻 ↔ 15
    assert X_FOLD < sc["x_event"] < 1.15                        # 門檻落在翻轉路徑之內（否則翻轉不會變成事件）


def test_linear_class_marginal_shares_match_ohare_despite_susceptibility_link():
    """決定書 §3 讓易感度決定子類別，但邊際比例仍要是 O'Hare 的值——否則『比例來自文獻』就是假的。"""
    rng = np.random.default_rng(0)
    s = rng.normal(0, 1, 200_000)
    cls = assign_linear_class(P, s, rng)
    got = np.bincount(cls, minlength=3) / len(cls)
    raw = np.array([c["share_raw"] for c in P["linear_classes"]["classes"]]); want = raw / raw.sum()
    assert np.allclose(got, want, atol=0.01)
    assert cls[s > 1].mean() > cls[s < -1].mean()               # 高易感度 → 斜率較陡的類別


def test_cohort_records_crit_and_event_separately_and_is_reproducible():
    """建置提示詞【重要】：翻轉型臨界日必須記錄；決定書 §2：臨界日與事件日分開。同 seed 必須重現。"""
    C1 = make_cohort(P, 5, n=120, delta_mu_median=1.55, kappa=0.5)
    C2 = make_cohort(P, 5, n=120, delta_mu_median=1.55, kappa=0.5)
    assert np.array_equal(C1["X"], C2["X"]) and np.array_equal(C1["t_event"], C2["t_event"])
    f = C1["is_flip"]
    assert (C1["t_crit"][~f] == -1).all()                       # 線性型沒有臨界日
    assert (C1["t_crit"][f] >= -1).all() and (C1["t_crit"][f] >= 0).any()
    ev = C1["event"]
    assert (C1["X"][ev, :][np.arange(ev.sum()), C1["t_event"][ev]] >= C1["scale"]["x_event"]).all()
    # 事件前一天必須低於門檻（首次跨越）
    ok = ev & (C1["t_event"] > 0)
    assert (C1["X"][ok, :][np.arange(ok.sum()), C1["t_event"][ok] - 1] < C1["scale"]["x_event"]).all()


def test_linear_ou_and_flip_have_comparable_baseline_autocorrelation():
    """決定書 §4（關鍵）：線性型用 OU 有色雜訊且基線自相關與翻轉型相當，H3 才是真的檢定。"""
    C = make_cohort(P, 11, n=400, delta_mu_median=1.55, kappa=0.5)
    f = C["is_flip"]

    def ar1(v):
        d = _detrend(v[:180].astype(float)); return np.corrcoef(d[:-1], d[1:])[0, 1]
    a_lin = np.mean([ar1(C["X"][i]) for i in np.where(~f)[0]])
    a_flip = np.mean([ar1(C["X"][i]) for i in np.where(f)[0]])
    assert a_lin > 0.5 and a_flip > 0.5                          # 都不是白雜訊
    assert abs(a_lin - a_flip) < 0.05                            # 起點相當


def test_dropout_variant_keeps_outcome_but_blanks_observations():
    """決定書 §6 退出＝停止記錄（複用 FADE apply_S2 語意）：結果事件仍已知，觀測值退出後為 NaN。"""
    C = make_cohort(P, 3, n=100, delta_mu_median=1.55, kappa=0.5, dropout=True)
    d = C["drop_day"]
    i = np.where(d >= 0)[0][0]
    assert np.isnan(C["X_obs"][i, d[i]:]).all() and not np.isnan(C["X_obs"][i, :d[i]]).any()
    assert C["event"].dtype == bool and len(C["t_event"]) == 100
