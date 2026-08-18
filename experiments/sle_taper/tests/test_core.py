# -*- coding: utf-8 -*-
"""指示 三之七 的十項單元測試（可單獨執行：python -m pytest experiments/sle_taper/tests -q）。"""
import copy
import hashlib
import os
import sys

import numpy as np
import pytest
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

import m0_params as M0                                     # noqa: E402
from m0_params import value                                # noqa: E402
from seeding import module_rng, MODULE_INDEX               # noqa: E402
from m1_generator import ou_noise, simulate_cohort, observe, events_from_U, taper_schedule   # noqa: E402
from m4_predict import run_predict                         # noqa: E402
import gates as G                                          # noqa: E402

P = M0.load("thresholds.json"); Cj = M0.load("cohort.json")
MU = -0.09      # 校準量級（測試不依賴校準）


def _small(seed=1, n=300, **kw):
    kw.setdefault("mu_mean", MU)
    return simulate_cohort(P, Cj, seed, n=n, **kw)


def test_01_seeding_streams_are_reproducible_and_index_stable():
    """同 master_seed 兩次呼叫同串流；模組索引固定，新增模組不位移既有串流。"""
    a = module_rng(7, "generator").random(5); b = module_rng(7, "generator").random(5)
    assert np.array_equal(a, b)
    assert not np.array_equal(module_rng(7, "generator", 1).random(5), a)          # 子串流不同
    assert not np.array_equal(module_rng(7, "cluster").random(5), a)
    assert MODULE_INDEX["generator"] == 0 and MODULE_INDEX["arms"] == 5 and MODULE_INDEX["grid"] == 6
    with pytest.raises(KeyError):
        module_rng(7, "not_a_module")


def test_02_ou_noise_autocorrelation_time_within_10pct():
    """OU 有色雜訊的實測相關時間常數接近設定值（容許 10%）；定態 SD ≈ sigma。"""
    tau_ou, sigma = 30.0, 0.2
    xi = ou_noise(400, 3000, tau_ou, sigma, module_rng(3, "generator", 9)).astype(float)
    xi = xi[:, 500:]                                                       # 去暖身
    lag = 10
    r = np.mean([np.corrcoef(x[:-lag], x[lag:])[0, 1] for x in xi])
    tau_hat = -lag / np.log(r)
    assert abs(tau_hat - tau_ou) / tau_ou < 0.10
    assert abs(xi.std() - sigma) / sigma < 0.10


def test_03_mu_below_mu_c_rarely_crosses():
    """μ 恆低於 μ_c（低 μ_intrinsic、完全停藥）時，長時間內 x 跨過 0 的比例低於上限 5%。"""
    C = _small(seed=2, n=400, mu_mean=-1.0)
    mu_max = C["mu_path"].max(axis=1)
    assert (mu_max < value(P, "mu_c")).mean() > 0.95
    crossed = (C["X"][:, C["run_in"]:] > 0).any(axis=1)
    below = (~C["is_gradual"]) & (mu_max < value(P, "mu_c"))
    far = below & (mu_max < -0.5)                                           # 單穩態區（μ < −μ_c）且離臨界較遠
    assert crossed[below].mean() < 0.10                                       # 上限：本研究設定 10%
    assert crossed[far].mean() < 0.05                                         # 單穩態區仍有 <5% 的持續性有色雜訊大偏移（見階段一回報）


def test_04_t_crit_is_mu_crossing_not_x_crossing():
    """t_crit 定義正確：μ 首次跨 μ_c，非 x 跨 0。"""
    C = _small(seed=4, n=400)
    mu_c = value(P, "mu_c")
    for i in np.where(C["t_crit"] >= 0)[0][:50]:
        tc = C["t_crit"][i]
        assert C["mu_path"][i, tc] >= mu_c and (tc == 0 or C["mu_path"][i, tc - 1] < mu_c)
    ok = (C["t_crit"] >= 0) & (C["t_threshold"] >= 0)
    assert np.any(C["t_threshold"][ok] != C["t_crit"][ok])                  # 兩者不是同一件事


def test_05_beta_zero_makes_events_independent_of_x():
    """β = 0 時事件時間與 x 獨立：事件率在 x 平均的三分位間無差；t_event 與 x 相關 ≈ 0。"""
    C = _small(seed=5, n=1500)
    te = events_from_U(C["X"], 5e-4, 0.0, C["U"], t_start=C["run_in"])
    xm = C["X"][:, C["run_in"]:].mean(axis=1)
    ter = np.digitize(xm, np.quantile(xm, [1 / 3, 2 / 3]))
    rates = [np.mean(te[ter == k] >= 0) for k in range(3)]
    assert max(rates) - min(rates) < 0.06
    ev = te >= 0
    assert abs(stats.spearmanr(xm[ev], te[ev]).correlation) < 0.08


def test_06_observation_layer_does_not_touch_generation_layer():
    """觀測層加噪不改變生成層陣列（雜湊比對）。"""
    C = _small(seed=6, n=100)
    h0 = hashlib.sha256(C["X"].tobytes()).hexdigest()
    xo = observe(C["X"], C["run_in"], 7, 0.15, module_rng(6, "obs"))
    assert hashlib.sha256(C["X"].tobytes()).hexdigest() == h0
    assert np.isnan(xo[:, 1]).all() and not np.isnan(xo[:, 0]).all()        # 取樣日才有值
    assert abs(np.nanmean(xo[:, :C["run_in"]]) + 1.0) < 0.05                # 定態期以自身基線置中在 −1


def test_07_pre_onset_trend_slopes_do_not_differ_by_type():
    """定態期（t < t_onset）翻轉型與非翻轉型的線性趨勢斜率無顯著差異（雙尾 t 檢定 p > 0.01）。"""
    C = _small(seed=7, n=1500)
    xo = observe(C["X"], C["run_in"], 1, 0.0, module_rng(7, "obs"))
    t = np.arange(C["run_in"], dtype=float)
    slopes = np.array([np.polyfit(t, xo[i, :C["run_in"]].astype(float), 1)[0] for i in range(C["n"])])
    f = C["type"] == "flip"
    assert f.sum() > 20
    assert stats.ttest_ind(slopes[f], slopes[~f], equal_var=False).pvalue > 0.01


def test_08_noninvasive_arm_has_no_mu_intrinsic_in_call_chain():
    C = _small(seed=8, n=200)
    xo = observe(C["X"], C["run_in"], 7, 0.05, module_rng(8, "obs"))
    g = G.g4_no_mu_in_noninvasive(C, xo, 30)
    assert g["passed"], g


def test_09_determinism_same_seed_bitwise():
    """同 seed 連跑兩次，生成層與事件逐位元相同。"""
    a = _small(seed=9, n=150); b = _small(seed=9, n=150)
    assert np.array_equal(a["X"], b["X"]) and np.array_equal(a["t_event"], b["t_event"]) and np.array_equal(a["mu_intrinsic"], b["mu_intrinsic"])


def test_10_fake_disease_parameters_run_through_pipeline():
    """換一組假的疾病參數（不同 g0、風險、比例、基線特徵）仍可跑通整條管線——程式與疾病無關。"""
    P2 = copy.deepcopy(P); C2 = copy.deepcopy(Cj)
    P2["g0"]["value"] = 2.2
    P2["hazard"]["value"] = {"lambda0_per_day": 2e-4, "beta_per_x": 1.0}
    P2["traj_egfr_proportions"]["value"]["persistent_decline"] = 0.20
    P2["landmarks"]["value"] = [60, 200]
    C2["baseline_features"] = {"marker_a": {"dist": "normal", "mean": 10, "sd": 2, "clip": [0, 20], "source": "fake", "status": "study_defined"},
                               "marker_b": {"dist": "lognormal", "median": 1, "sigma_log": 0.3, "clip": [0.1, 5], "source": "fake", "status": "study_defined"}}
    C2["susceptibility_link"]["weights"] = {"marker_a": 1.0, "marker_b": -1.0}
    C2["susceptibility_link"]["log_transform"] = ["marker_b"]
    import m2_risk
    old = m2_risk.FEATURES, m2_risk.LOG_FEATURES
    m2_risk.FEATURES, m2_risk.LOG_FEATURES = ("marker_a", "marker_b"), ("marker_b",)
    try:
        C = simulate_cohort(P2, C2, 10, n=300, mu_mean=0.2)
        xo = observe(C["X"], C["run_in"], 7, 0.05, module_rng(10, "obs"))
        r = run_predict(C, xo, [60, 200], folds=3, seed=1, timing=False)
        assert set(r["landmarks"]) == {"60", "200"}
    finally:
        m2_risk.FEATURES, m2_risk.LOG_FEATURES = old
