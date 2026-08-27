# -*- coding: utf-8 -*-
"""每一條測試都對應一個「如果這件事壞了，這個模型就不該上線」的性質。

刻意不測「函式有沒有回傳東西」這種東西：那種測試永遠會綠，改壞商業邏輯也不會紅。
"""
import numpy as np
import pytest

import attribution as AT
import deterministic as DET
import pipeline as PL
from cohort import simulate


# --- 決定性層 ------------------------------------------------------------

def test_pending_marker_is_not_negative():
    """標記還沒回來 != 標記陰性。

    這是這類系統最典型的靜默錯誤：把「檢驗單還在跑」當成「檢驗結果正常」，
    於是一位抗 GBM 陽性但報告未回的病人被歸到低風險。壞掉時病人會死。
    """
    n = 3
    raw = {"cr_now": np.ones(n), "cr_slope_per_week": np.zeros(n), "upcr": np.ones(n),
           "rbc_cast": np.zeros(n), "urine_rbc_hpf": np.zeros(n), "dysmorphic_rbc_pct": np.zeros(n)}
    markers = {m: np.zeros(n) for m in ("anti_gbm", "anca", "anti_pla2r", "maha_triad")}
    markers.update({m + "_available": np.zeros(n) for m in
                    ("anti_gbm", "anca", "anti_pla2r", "maha_triad")})
    markers["anti_gbm"][0] = 1.0                    # 陽性，但 available = 0（還沒回）
    route, _ = DET.apply(raw, markers)
    assert route[0] == DET.NO_ROUTE, "未回覆的陽性標記不得觸發硬分流"

    markers["anti_gbm_available"][0] = 1.0          # 報告回來了
    route, rule = DET.apply(raw, markers)
    assert route[0] == "ANTI_GBM" and rule[0] == "R1_ANTI_GBM"


def test_deterministic_layer_has_no_model():
    """L2 一旦混進機率或隨機性，鐵則 5 就破了，而且同一份資料會給出不同分流。"""
    import inspect
    src = inspect.getsource(DET)
    for token in ("sklearn", "predict", "np.random", "import random"):
        assert token not in src, f"決定性層出現 {token}"


def test_safety_override_is_one_way():
    """安全否決只能把人從『可排除』拉回『不可排除』。

    反過來（用規則去製造 rule-out）等於讓門檻規則凌駕機率證據，
    會在規則沒想到的情境下產生無法察覺的漏判。
    """
    coh = simulate(11, n=400)
    res = PL.run(coh, seed=0)
    it = res["_internal"]
    raw_only = PL.l3_ruleout(it["oof"], it["thr"])
    assert set(np.where(it["ruled_out"])[0]) <= set(np.where(raw_only)[0])


# --- 只用非對角 ----------------------------------------------------------

def test_offdiag_fit_ignores_indicator_specific_noise():
    """只用非對角的整個理由：Theta（各指標自己的量測誤差）是對角的，非對角擬合把它消掉。

    測法：只往對角線灌雜訊（每個指標各自加獨立誤差，指標之間互不相關），
    Psi 的估計必須幾乎不動。若會動，代表擬合其實吃到了對角線，
    那麼換一批試劑、換一台儀器就會讓機轉參數漂移。
    """
    rng = np.random.default_rng(0)
    ind, Lam, _ = AT.spec()
    coh = simulate(5, n=1500)
    X = AT.transform_raw(coh["raw"], ind)
    Psi_a, rmse_a = AT.fit_psi_offdiag(X, Lam)
    X_noisy = X + rng.normal(0, 0.8, X.shape)        # 純獨立雜訊：只膨脹對角
    Psi_b, rmse_b = AT.fit_psi_offdiag(X_noisy, Lam)
    assert np.max(np.abs(Psi_a - Psi_b)) < 0.15 * np.max(np.abs(Psi_a))
    assert abs(rmse_a - rmse_b) < 0.10


# --- 旋轉不確定性 --------------------------------------------------------

def test_fixed_lambda_has_no_rotational_freedom():
    """固定 Lambda 的歸因唯一；自由估計的解在旋轉下擬合相同但歸因不同。

    這條就是『負載矩陣必須文獻固定』的全部理由。若哪天有人把 Lambda 改成自由估計，
    這條測試會紅。
    """
    ind, Lam, _ = AT.spec()
    coh = simulate(6, n=800)
    X = AT.transform_raw(coh["raw"], ind)
    a1 = AT.nnls_attribution(X, Lam)
    a2 = AT.nnls_attribution(X, Lam)
    assert np.allclose(a1, a2)                       # 固定 Lambda：完全決定性

    rng = np.random.default_rng(1)
    Q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    Lr = Lam @ Q
    implied_same = np.allclose(Lam @ Lam.T, Lr @ Lr.T)
    assert implied_same, "正交旋轉必須保持模型隱含共變不變（前提本身）"
    Xc = X - X.mean(axis=0)
    top_a = np.linalg.lstsq(Lam, Xc.T, rcond=None)[0].T.argmax(axis=1)
    top_r = np.linalg.lstsq(Lr, Xc.T, rcond=None)[0].T.argmax(axis=1)
    assert (top_a == top_r).mean() < 0.9, "旋轉後歸因若不變，旋轉不確定性的論證就不成立"


# --- 禁逐人標準化 --------------------------------------------------------

def test_person_standardization_destroys_absolute_level():
    """逐人標準化把『量』抹成『形狀』：x 與 2x 標準化後完全相同。

    臨床上這兩個人不是同一個人 —— C3 40 和 C3 85 差在有沒有正在消耗補體。
    這是數學恆等式層級的資訊損失，不是調參可以救的。
    """
    x = np.array([[1.0, 2.0, 3.0, 4.0]])
    z = lambda M: (M - M.mean(1, keepdims=True)) / M.std(1, keepdims=True)
    assert np.allclose(z(x), z(2 * x))
    assert np.allclose(z(x), z(x + 10))


# --- NPV 端操作點 --------------------------------------------------------

def test_threshold_respects_time_critical_cap():
    """安全上限必須真的能否決一個 NPV 已達標的門檻。

    構造：低機率端塞入時效性個案。只看 NPV 會選到較寬的門檻；加上漏判率上限後
    必須退到更保守的門檻。若這條紅了，代表『安全終點優先於平均 NPV』只是文件裡的口號。
    """
    p = np.linspace(0.0, 1.0, 400)
    y = (p > 0.55).astype(int)
    y[100] = 1                                       # 一個藏在低風險端的時效性陽性
    crit = np.zeros(400, dtype=bool)
    crit[100] = True
    t_npv = PL._npv_threshold(p, y, 0.95)
    t_safe = PL._npv_threshold(p, y, 0.95, y_critical=crit, crit_cap=0.0)
    assert t_npv is not None and t_safe is not None
    assert t_safe < t_npv, "加上漏判率上限後門檻必須更保守"
    assert p[100] >= t_safe, "時效性個案不得落在 rule-out 區"
    # 上限嚴到沒有任何可行門檻時，必須回傳 None（＝這個族群不該提供 rule-out），
    # 而不是退而求其次挑一個會漏判的門檻
    crit_low = np.zeros(400, dtype=bool)
    crit_low[5] = True
    y_low = y.copy(); y_low[5] = 1
    assert PL._npv_threshold(p, y_low, 0.95, y_critical=crit_low, crit_cap=0.0) is None


def test_zero_new_assay_invariant():
    """模型特徵集不得包含任何需要加驗的檢驗。這是與 KidneyIntelX 路線的唯一結構差異，
    破了就沒有差異化，也沒有成本優勢。"""
    ind, _, _ = AT.spec()
    assert not ({s["raw"] for s in ind} & PL.BANNED_IN_MODEL)


# --- 資料品質層 ----------------------------------------------------------

def test_unit_error_is_blocked_not_silently_converted():
    """umol/L 被當成 mg/dL 時要擋下來，不可自動換算。

    自動換算看起來聰明，但你無法區分『單位錯』和『真的是洗腎級數值』，
    猜錯的那一次會把一個急性腎損傷病人變成正常人。
    """
    n = 2
    raw = {"cr_now": np.array([1.2, 1.2 * 88.4]), "albumin": np.full(n, 4.0),
           "upcr": np.full(n, 0.3), "urine_rbc_hpf": np.full(n, 2.0),
           "c3": np.full(n, 95.0), "c4": np.full(n, 20.0),
           "days_since_last_panel": np.zeros(n)}
    ok, rep = PL.l1_quality(raw)
    assert ok[0] and not ok[1] and rep["unit_error"] == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
