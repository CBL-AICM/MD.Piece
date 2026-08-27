# -*- coding: utf-8 -*-
"""M0 洩漏基準（必須最先建立，且數字要凍結）。

M0 是一個「故意作弊」的模型：它可以看切片免疫螢光強度、新月體比例、事後有沒有
開免疫抑制劑、編碼診斷、追蹤一年的 eGFR —— 全都是在真實決策時點拿不到、或
根本就是答案本身的東西。

先建 M0 有三個用途，缺一不可：
  1. 天花板：M0 的分數就是「答案幾乎攤在桌上時能做到多好」。誠實模型 M1 的
     分數要對著它讀，而不是對著 0.5 讀。
  2. 絆線：如果 M1 逼近甚至超過 M0，那不是 M1 很強，是 M1 也在洩漏。這條絆線
     只有在 M0 先存在時才有效 —— 事後才補跑 M0 已經失去警報意義。
  3. 清單：M0 的特徵重要度直接指出「哪些欄位一旦混進特徵集就會毀掉這個研究」，
     那份清單就是 pipeline.BANNED_IN_MODEL 的來源。

M0 永遠不上線。它的存在是為了讓 M1 的數字有意義。
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from cohort import LEAKY
from pipeline import _npv_threshold


def _matrix(coh, ok):
    return np.column_stack([coh["leaky"][k][ok] for k in LEAKY])


def build(coh, ok, seed=0, target_npv=0.95):
    """回傳 M0 的基準數字。ok = L1 通過的遮罩（與 M1 同一個分母才可比）。"""
    Xl = _matrix(coh, ok)
    y_bin = coh["immune_gn"][ok].astype(int)
    y_pat = coh["label"][ok]
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=5, random_state=seed, n_jobs=1)

    p_bin = cross_val_predict(rf, Xl, y_bin, cv=cv, method="predict_proba")[:, 1]
    auc_bin = float(roc_auc_score(y_bin, p_bin))
    t = _npv_threshold(p_bin, y_bin, target_npv)
    neg = p_bin < t if t is not None else np.zeros_like(p_bin, dtype=bool)
    npv = float((y_bin[neg] == 0).mean()) if neg.sum() else float("nan")

    p_pat = cross_val_predict(rf, Xl, y_pat, cv=cv, method="predict_proba")
    auc_pat = float(roc_auc_score(y_pat, p_pat, multi_class="ovr", average="macro"))
    acc_pat = float((p_pat.argmax(axis=1) == y_pat).mean())

    rf.fit(Xl, y_bin)
    imp = sorted(zip(LEAKY, rf.feature_importances_), key=lambda kv: -kv[1])
    return dict(
        n=int(ok.sum()), features=list(LEAKY),
        immune_binary=dict(auroc=auc_bin, npv=npv, ruleout_rate=float(neg.mean()), threshold=t),
        histologic_pattern=dict(macro_auroc=auc_pat, accuracy=acc_pat),
        importances=[(k, round(float(v), 4)) for k, v in imp],
        note="M0 僅供對照與絆線之用，任何情況下都不得部署。",
    )
