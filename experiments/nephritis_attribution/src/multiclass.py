# -*- coding: utf-8 -*-
"""公式 4–6：多類別亞型機率、線性預測式、亞型分數。

  公式 4  P(Y=k) = exp(η_k) / Σ_h exp(η_h)
  公式 5  η_ik = β_0k + Σ_j β_jk X_ij
  公式 6  Score_ik = β_0k + β_1k(病理特徵) + β_2k(補體變化率) + β_3k(蛋白尿變化率)
                     + β_4k(eGFR 斜率) + β_5k(自體抗體組合)

三件必須先講清楚的事：

一、公式 6 不是第六條公式，它就是公式 5。
   把 X_ij 換成具名的變項群之後，η 與 Score 是同一個東西，softmax 之後就是公式 4。
   這不是挑語病：把同一個模型寫成三條，容易讓人以為驗證了三次。

二、公式 6 若把「病理特徵」放進預測變項、而 Y 又是組織型態，那是循環的。
   本專案的 M0 洩漏基準已經量過這件事：把切片所見（免疫螢光強度、新月體比例）
   放進特徵，組織型態的 macro AUROC 會到 0.99、準確率 0.925。那不是模型很強，
   是答案在特徵裡。circularity_demo() 把這條重跑一次，讓數字自己說話。
   若 Y 指的是「病因亞型」（狼瘡／IgA／ANCA…）而病理特徵是組織型態，
   則不循環 —— 這是臨床上本來的推理方向。**Y 到底是哪一個，必須先定義。**

三、公式 4 的 softmax 與本專案「二元輸出為主」的設計是衝突的，不能混用。
   softmax 強制各亞型互斥且機率和為 1，重疊病理（狼瘡合併抗磷脂 TMA、
   膜性合併足細胞病）只能被壓成一個答案。K 個獨立二元頭則可以同時為真。
   兩者各有代價，binary_from_softmax() 把「用 softmax 推回二元 rule-out」
   與「直接訓練二元」放在同一個操作點上比，讓取捨變成數字而不是偏好。
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def _model(seed):
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=1.0))


def fit_softmax(X, y, seed=0):
    """公式 4＋5：多類別 logistic（softmax）。回傳 out-of-fold 機率矩陣。"""
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    return cross_val_predict(_model(seed), X, y, cv=cv, method="predict_proba")


def ece(prob, y, bins=10):
    """期望校準誤差：機率說 0.7 的那一群，實際上是不是 70% 真的是那一類。

    多類別模型最常見的問題不是準確率，是**機率不可信**。若要拿 P(Y=k) 去跟病人
    或醫師溝通「有七成可能是膜性腎病」，這個數字必須先站得住。
    """
    conf = prob.max(axis=1)
    hit = (prob.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    e, n = 0.0, len(y)
    for i in range(bins):
        m = (conf > edges[i]) & (conf <= edges[i + 1])
        if m.sum():
            e += m.sum() / n * abs(hit[m].mean() - conf[m].mean())
    return float(e)


def evaluate(X, y_pattern, n_classes, seed=0):
    """多類別頭的整體表現：top-1／top-3／macro AUROC／校準誤差。"""
    p = fit_softmax(X, y_pattern, seed=seed)
    order = np.argsort(-p, axis=1)
    return dict(
        top1=float((order[:, 0] == y_pattern).mean()),
        top3=float(np.mean([t in o for t, o in zip(y_pattern, order[:, :3])])),
        macro_auroc=float(roc_auc_score(y_pattern, p, multi_class="ovr", average="macro")),
        ece=ece(p, y_pattern),
        n=int(len(y_pattern)),
    ), p


def binary_from_softmax(p_soft, immune_mask):
    """把多類別機率加總回二元：P(免疫介導 GN) = Σ_{k 屬免疫} P(Y=k)。

    這是「先分型再推回二元」的路線。與直接訓練二元相比，它多繞了一圈：
    要先把機率分配到 8 個類別（其中好幾類樣本很少），再加總。
    少數類別的估計誤差會被一起加進來，而 NPV 端恰恰對這種誤差敏感。
    """
    return p_soft[:, immune_mask].sum(axis=1)


def circularity_demo(X_routine, X_pathology, y_pattern, seed=0):
    """公式 6 逐字實作的循環性演示。

    A 只用常規資料；B 照公式 6 把「病理特徵」也放進去。
    若 Y 是組織型態，B 的分數會跳到近乎完美 —— 那是答案在特徵裡，不是模型有效。
    """
    a, _ = evaluate(X_routine, y_pattern, None, seed=seed)
    b, _ = evaluate(np.hstack([X_routine, X_pathology]), y_pattern, None, seed=seed)
    return dict(routine_only=a, with_pathology=b,
                top1_gain=round(b["top1"] - a["top1"], 4),
                verdict=("病理特徵一放進去分數就跳起來：若 Y 是組織型態，公式 6 這樣寫是循環的；"
                         "若 Y 是病因亞型（狼瘡／IgA／ANCA…），則不循環但必須明講。"))
