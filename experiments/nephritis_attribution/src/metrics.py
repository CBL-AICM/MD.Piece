# -*- coding: utf-8 -*-
"""閘門與診斷指標。任一閘門未過即中止，並印出實際數值（鐵則 12：不准靜默通過）。

G1 L1 真的會棄權（棄權率落在合理區間，不是 0 也不是把人全擋光）
G2 L2 是決定性的（重跑一致 ＋ 原始碼掃描確認無模型／無隨機）
G3 旋轉不確定性演示：自由估計的解在旋轉下擬合完全不變，但機轉排序整個變掉
G4 禁逐人標準化：逐人標準化後歸因準確率顯著下降
G5 M0 洩漏基準高於誠實模型 M1（否則不是洩漏特徵沒用，就是 M1 也在洩漏）
G6 零新增：L3-L5 特徵集與「加驗檢驗」集合交集為空
"""
import inspect

import numpy as np
from scipy.optimize import lsq_linear, nnls
from sklearn.decomposition import FactorAnalysis
from sklearn.metrics import roc_auc_score

import deterministic as DET
import pipeline as PL
from attribution import _offdiag, nnls_attribution


def _gate(name, value, criterion, passed, fail_means, **extra):
    d = dict(gate=name, value=value, criterion=criterion, passed=bool(passed), fail_means=fail_means)
    d.update(extra)
    return d


def g1_quality(res):
    r = res["quality"]["abstain_rate"]
    return _gate("G1 L1 資料品質棄權率", round(float(r), 4), "0.01 <= r <= 0.50", 0.01 <= r <= 0.50,
                 "L1 沒在做事（=0）或把資料要求訂得不可能達成（過高），兩者都讓下游數字失去意義",
                 detail=res["quality"])


def g2_deterministic(coh):
    r1, _ = DET.apply(coh["raw"], coh["markers"])
    r2, _ = DET.apply(coh["raw"], coh["markers"])
    same = bool(np.all(r1 == r2))
    src = inspect.getsource(DET)
    banned = [t for t in ("sklearn", "random", "predict_proba", "np.random") if t in src]
    return _gate("G2 L2 決定性", dict(reproducible=same, banned_tokens=banned),
                 "重跑一致 且 無模型/隨機 token", same and not banned,
                 "決定性層混進了機率或隨機性，違反鐵則 5，且同一份資料會給出不同分流")


def g3_rotation(X, true_top, Lam, seed=0, n_rot=24):
    """旋轉不確定性：自由估計的因子解在正交旋轉下模型隱含共變完全相同，
    但每位病人的「主導機轉」會跟著旋轉整個換人 —— 因子在資料裡沒有名字。"""
    rng = np.random.default_rng(seed)
    fa = FactorAnalysis(n_components=3, random_state=seed).fit(X)
    Lf = fa.components_.T                                   # p x 3
    Xc = X - X.mean(axis=0)

    def implied_off(L):
        return _offdiag(L @ L.T)

    base_off = implied_off(Lf)
    base_scores = np.linalg.lstsq(Lf, Xc.T, rcond=None)[0].T
    base_top = base_scores.argmax(axis=1)

    fit_dev, agree, seen = [], [], np.zeros((X.shape[0], 3), dtype=bool)
    seen[np.arange(X.shape[0]), base_top] = True
    for _ in range(n_rot):
        Q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        Lr = Lf @ Q
        fit_dev.append(float(np.max(np.abs(implied_off(Lr) - base_off))))
        sc = np.linalg.lstsq(Lr, Xc.T, rcond=None)[0].T
        top = sc.argmax(axis=1)
        seen[np.arange(X.shape[0]), top] = True
        agree.append(float((top == base_top).mean()))

    A_fix = nnls_attribution(X, Lam)
    acc_fix = float((A_fix.argmax(axis=1) == true_top).mean())
    max_fit_dev = float(np.max(fit_dev))
    mean_agree = float(np.mean(agree))
    distinct = float(seen.sum(axis=1).mean())
    ok = (max_fit_dev < 1e-6) and (mean_agree <= 0.60) and (acc_fix >= 0.55)
    return _gate("G3 旋轉不確定性",
                 dict(max_offdiag_fit_deviation=max_fit_dev, mean_top1_agreement=mean_agree,
                      mean_distinct_top_drivers=distinct, fixed_lambda_top1_accuracy=acc_fix),
                 "擬合偏差 < 1e-6 且 旋轉間排序一致率 <= 0.60 且 固定 Lambda 準確率 >= 0.55", ok,
                 "若擬合偏差不為零，代表這個演示沒抓到旋轉不變性；若一致率很高，代表旋轉幅度不夠，"
                 "結論不成立；若固定 Lambda 準確率不高，代表文獻矩陣本身有問題")


def g4_person_standardization(X, prior_X, y, true_top, Lam, seed=0):
    """禁逐人標準化，理由是洩漏，不只是準確率。

    逐人標準化＝把每個病人的檢驗值對「他自己的分布」正規化。回溯研究裡計算那個
    分布時，手上有整段病程（含當次），於是正規化統計量偷看了當下這一筆 —— 上線後
    只能用過去的資料算，數字就掉下來。這裡把三種做法一次跑出來：

      A 絕對刻度                 —— 本模型採用的做法
      B 逐人標準化（含當次）     —— 論文裡通常報的數字
      C 逐人標準化（只用過去）   —— 上線後唯一拿得到的數字

    閘門要求兩件事同時成立：C 明顯輸給 A（絕對刻度本身較好），且 B - C > 0（B 是
    被洩漏墊高的假象）。另附一個較弱的橫斷面變體（逐人跨指標 z），誠實顯示它的
    傷害小得多 —— 不是所有形式的逐人縮放都一樣糟，混為一談會失去說服力。
    """
    def auc(F):
        _, _, oof = PL.fit_l3(F, y, target_npv=0.95, seed=seed)
        return float(roc_auc_score(y, oof))

    def norm(H):
        mu, sd = H.mean(0), H.std(0)
        return (X - mu) / np.where(sd > 1e-6, sd, 1.0)

    a_abs = auc(X)
    a_leak = auc(norm(np.concatenate([prior_X, X[None, ...]], axis=0)))
    a_prosp = auc(norm(prior_X))

    sd_row = X.std(axis=1, keepdims=True)
    Xz = (X - X.mean(axis=1, keepdims=True)) / np.where(sd_row > 1e-9, sd_row, 1.0)
    a_rowz = auc(Xz)

    A_fix = nnls_attribution(X, Lam)
    acc_abs = float((A_fix.argmax(axis=1) == true_top).mean())

    ok = (a_abs - a_prosp >= 0.05) and (a_leak - a_prosp >= 0.02)
    return _gate("G4 禁逐人標準化",
                 dict(A_absolute=round(a_abs, 4), B_person_norm_with_current=round(a_leak, 4),
                      C_person_norm_past_only=round(a_prosp, 4),
                      leakage_inflation_B_minus_C=round(a_leak - a_prosp, 4),
                      cost_vs_absolute_C_minus_A=round(a_prosp - a_abs, 4),
                      weak_variant_cross_sectional_row_z=round(a_rowz, 4),
                      attribution_top1_absolute=round(acc_abs, 4)),
                 "A - C >= 0.05 且 B - C >= 0.02", ok,
                 "若絕對刻度沒有比較好、或回溯版沒有被墊高，那禁逐人標準化這條規則在本資料上"
                 "沒有證據支持，應該撤回而不是留著當信仰")


def g5_m0_ceiling(m0_auc, m1_auc, margin=0.02):
    ok = m0_auc >= m1_auc + margin
    return _gate("G5 M0 洩漏基準為上界", dict(m0_auroc=round(m0_auc, 4), m1_auroc=round(m1_auc, 4),
                                              gap=round(m0_auc - m1_auc, 4)),
                 f"M0 - M1 >= {margin}", ok,
                 "M1 逼近或超過 M0 有兩種可能：洩漏特徵其實沒資訊（M0 設計錯了），"
                 "或 M1 自己也在洩漏（更危險）。兩者都必須先查清楚才能繼續。")


def g6_zero_new_assay(ind):
    used = {s["raw"] for s in ind}
    overlap = sorted(used & PL.BANNED_IN_MODEL)
    src = inspect.getsource(PL.fit_l3) + inspect.getsource(PL.l4_attribute)
    leaked_tokens = [t for t in PL.BANNED_IN_MODEL if t in src]
    ok = not overlap and not leaked_tokens
    return _gate("G6 零新增檢驗", dict(model_fields=len(used), overlap=overlap, tokens_in_source=leaked_tokens),
                 "交集為空 且 L3/L4 原始碼未出現加驗欄位", ok,
                 "只要有一個加驗欄位進了模型特徵集，『零新增』這個賣點就不成立，成本結構的差異化也沒了")


def run_gates(coh, res, m0_residual_auc, ind, Lam, true_top, seed=0):
    it = res["_internal"]
    m1_auc = float(roc_auc_score(it["yr"], it["oof"]))
    gates = [
        g1_quality(res),
        g2_deterministic(coh),
        g3_rotation(it["Xr"], true_top[it["residual"]], Lam, seed=seed),
        g4_person_standardization(it["Xr"], coh["prior_X"][:, it["residual"]], it["yr"],
                                  true_top[it["residual"]], Lam, seed=seed),
        g5_m0_ceiling(m0_residual_auc, m1_auc),
        g6_zero_new_assay(ind),
    ]
    return gates, m1_auc


# ---------------- 非閘門診斷 ----------------

def misspecification_curve(seed, levels=(0.0, 0.10, 0.20, 0.35, 0.50), n=2500):
    """文獻 Lambda 與真實 Lambda 有落差時，歸因退化多快。分兩種錯法：

      magnitude  文獻把載荷「大小」估錯，但指標歸屬正確；
      structure  一部分指標根本被歸到錯的驅動。

    兩種一起跑是必要的：只看 magnitude 會得出「Lambda 怎麼錯都沒差」的錯誤結論
    （因為 argmax 對等比例縮放不敏感），真正的風險全在 structure 這一側。
    非對角 RMSE 同時報出來，看它能不能在上線前就偵測到誤設。
    """
    from cohort import simulate, true_top_driver
    from attribution import fit_psi_offdiag, spec, transform_raw
    ind, Lam, _ = spec()
    out = []
    for mode in ("magnitude", "structure"):
        for lv in levels:
            coh = simulate(seed + 977, n=n, misspec=lv, misspec_mode=mode)
            X = transform_raw(coh["raw"], ind)
            ok, _ = PL.l1_quality(coh["raw"])
            A = nnls_attribution(X[ok], Lam)
            acc = float((A.argmax(axis=1) == true_top_driver(coh)[ok]).mean())
            _, rmse = fit_psi_offdiag(X[ok], Lam)
            out.append(dict(mode=mode, misspec=lv, top1_accuracy=round(acc, 4),
                            offdiag_rmse=round(rmse, 4)))
    return out


def shortlist_accuracy(coh, res):
    """量出「相容型態候選清單」到底多準——不量就顯示，等於請使用者自己腦補。"""
    from attribution import load, pattern_shortlist
    it = res["_internal"]
    prof = np.array([p["driver_mean"] for p in load("patterns.json")["patterns"]])
    order, _ = pattern_shortlist(it["sh"], prof, k=3)
    truth = coh["label"][it["residual"]]
    return dict(top1=float((order[:, 0] == truth).mean()),
                top3=float(np.mean([t in o for t, o in zip(truth, order)])),
                n=int(len(truth)),
                note="呈現用候選清單，非以組織型態訓練的分類器；此數字必須與清單一起顯示。")


def safety(coh, res):
    """安全終點必須拆開報，不可用平均 NPV 蓋過去。

    (1) 時效性且屬免疫介導（抗 GBM、寡免疫新月體）被 rule out ＝ 真正的 under-triage；
    (2) TMA 時效性但不屬免疫介導 —— 被 rule out 在二元定義上是「對的」，
        危險在於它可能就這樣沒有任何旗標地離開系統，所以另外報「零旗標」比率。
    """
    it = res["_internal"]
    r = it["residual"]
    tc, imm = coh["time_critical"][r], coh["immune_gn"][r]
    ruled = it["ruled_out"]
    crit = tc & imm
    tma = tc & ~imm
    flags = it["flags"]
    unflagged = int(sum(1 for i in np.where(tma)[0] if not flags[i]))
    return dict(
        immune_time_critical_n=int(crit.sum()),
        immune_time_critical_missed=int((ruled & crit).sum()),
        immune_time_critical_miss_rate=float((ruled & crit).sum() / crit.sum()) if crit.sum() else float("nan"),
        tma_n=int(tma.sum()), tma_without_any_flag=unflagged,
        tma_unflagged_rate=float(unflagged / tma.sum()) if tma.sum() else float("nan"),
    )
