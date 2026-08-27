# -*- coding: utf-8 -*-
"""三驅動歸因：文獻固定負載矩陣 Lambda ＋ 非負最小平方（NNLS）。

為什麼 Lambda 必須固定（不可自由估計）：
  自由估計（EFA/PCA/一般因子分析）的解只在旋轉意義下唯一。對任一可逆 R，
  (Lambda R, R^-1 a) 與 (Lambda, a) 產生完全相同的模型隱含共變異數，
  因此「哪一個因子叫免疫沉積」在資料裡沒有答案 —— 命名靠的是分析者事後
  看載荷猜的，不是資料識別出來的。歸因（attribution）恰恰是要對「被命名的
  機轉」下結論，所以旋轉不確定性不是精度問題，是致命的識別問題。
  metrics.g3_rotation() 把這件事跑出數字來證明，不是用講的。

為什麼只用非對角：
  模型隱含共變 Sigma = Lambda Psi Lambda^T + Theta，Theta 為對角（各指標的
  獨特變異＋量測誤差）。只擬合 i != j 的元素時 Theta 整個消掉，於是：
    1) 不需要估 20 個獨特變異參數（少 20 個自由度全給了 Psi 的 6 個）；
    2) 沒有任何指標可以「自己解釋自己」—— 對角線是自我一致性最強、也最容易
       被單一儀器批次／單位錯誤污染的地方；
    3) 擬合優度變成真正的證偽測試：文獻 Lambda 若錯，非對角共動結構對不上。

為什麼禁逐人標準化（結論已依實測修正，見 results/assumptions.md C.1）：
  依據是「洩漏」，不是「橫斷面縮放一定比較差」。逐人標準化要算病人自己的分布，
  回溯研究算的時候手上有整段病程（含當次），上線後只能用過去的資料算，
  於是論文上的數字上線後就掉下來。實測（metrics.g4_person_standardization）：
    絕對刻度 0.902 / 逐人標準化含當次 0.719 / 逐人標準化只用過去 0.563。
  單純的橫斷面逐人 z（跨指標置中除以標準差）只讓 AUROC 掉 0.008 —— 傷害小得多，
  不要把兩者混為一談，那會讓論證失去可信度。
"""
import json
import os

import numpy as np
from scipy.optimize import minimize, nnls

PARAMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "params")


def load(name):
    with open(os.path.join(PARAMS_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def spec():
    """回傳 (indicator specs, Lambda[p,3], driver names)。"""
    L = load("loadings.json")
    ind = L["indicators"]
    return ind, np.array([i["loadings"] for i in ind], dtype=float), L["drivers"]


def transform_raw(raw, ind):
    """常規原始值 -> 方向化指標矩陣 X[n, p]（越大代表該方向的證據越強）。

    raw: dict[field] = ndarray[n]，缺值以 np.nan 表示。
    缺值一律轉成 0 = 「沒有證據」，而不是 0 = 「正常」的插補猜測；
    L1 已經先把缺太多的個案擋掉了，這裡只處理殘餘的零星缺值。
    """
    n = len(next(iter(raw.values())))
    X = np.zeros((n, len(ind)), dtype=float)
    for j, s in enumerate(ind):
        v = np.asarray(raw[s["raw"]], dtype=float)
        ref, sc, k = float(s["ref"]), float(s["scale"]), s["kind"]
        if k == "deficit":
            x = np.maximum(0.0, (ref - v) / sc)
        elif k == "excess":
            x = np.maximum(0.0, (v - ref) / sc)
        elif k == "logexcess":
            x = np.log1p(np.maximum(0.0, (v - ref)) / sc)
        elif k == "binary":
            x = v
        elif k == "level":
            x = v / sc
        else:
            raise ValueError("unknown transform kind: " + k)
        X[:, j] = np.where(np.isfinite(x), x, 0.0)
    return X


def invert_transform(X, ind, rng, jitter=0.0):
    """方向化指標 -> 可信的原始值（只給合成世代用；真實資料走 transform_raw）。

    這條反轉讓合成資料長得像真的檢驗報告（有地板效應、有單位、有整數位），
    也讓 L1 資料品質層有東西可檢查 —— 否則 L1 只是裝飾。
    """
    raw = {}
    for j, s in enumerate(ind):
        x = X[:, j]
        ref, sc, k = float(s["ref"]), float(s["scale"]), s["kind"]
        if k == "deficit":
            v = ref - np.maximum(0.0, x) * sc + rng.normal(0, jitter * sc, x.shape)
        elif k == "excess":
            v = ref + np.maximum(0.0, x) * sc + rng.normal(0, jitter * sc, x.shape)
        elif k == "logexcess":
            v = ref + np.expm1(np.maximum(0.0, x)) * sc
        elif k == "binary":
            v = (rng.random(x.shape) < 1.0 / (1.0 + np.exp(-(x - 0.5) * 4))).astype(float)
        elif k == "level":
            v = np.clip(np.round(x * sc), 0, 3)
        else:
            raise ValueError(k)
        raw[s["raw"]] = np.maximum(v, 0.0)
    return raw


# ---------- 非對角擬合（confirmatory，Lambda 固定，只估 Psi） ----------

def _offdiag(M):
    p = M.shape[0]
    iu = np.triu_indices(p, k=1)
    return M[iu]


def implied_cov(Lam, Psi):
    return Lam @ Psi @ Lam.T


def offdiag_rmse(S, Sig):
    """非對角殘差 RMSE，除以觀察非對角的 RMS 做成相對量（尺度無關）。"""
    r = _offdiag(S) - _offdiag(Sig)
    denom = np.sqrt(np.mean(_offdiag(S) ** 2))
    return float(np.sqrt(np.mean(r ** 2)) / denom) if denom > 0 else np.inf


def fit_psi_offdiag(X, Lam):
    """只用非對角元素的 ULS 擬合 Psi（3x3，Cholesky 參數化保證半正定）。

    Theta（對角獨特變異）在非對角擬合中完全消去 —— 這正是只用非對角的理由，
    不是為了省事，是為了不讓「每個指標自己的雜訊」進入機轉參數的估計。
    """
    S = np.cov(X, rowvar=False)
    k = Lam.shape[1]
    tril = np.tril_indices(k)

    def unpack(theta):
        Lo = np.zeros((k, k))
        Lo[tril] = theta
        return Lo @ Lo.T

    def obj(theta):
        return float(np.sum((_offdiag(S) - _offdiag(implied_cov(Lam, unpack(theta)))) ** 2))

    x0 = np.eye(k)[tril] * 0.8
    res = minimize(obj, x0, method="L-BFGS-B")
    Psi = unpack(res.x)
    return Psi, offdiag_rmse(S, implied_cov(Lam, Psi))


# ---------- 逐人歸因（NNLS） ----------

def nnls_attribution(X, Lam):
    """對每一列解 min_{a>=0} ||Lam a - x||^2。非負約束讓 a 可以讀成
    「這個病人身上有多少這個機轉」，負值在機轉語意下沒有意義。"""
    A = np.empty((X.shape[0], Lam.shape[1]), dtype=float)
    for i in range(X.shape[0]):
        A[i], _ = nnls(Lam, X[i])
    return A


def shares(A, eps=1e-9):
    """驅動占比（每列和為 1；全零列回傳均勻分布並不做任何宣稱）。"""
    s = A.sum(axis=1, keepdims=True)
    out = np.where(s > eps, A / np.maximum(s, eps), 1.0 / A.shape[1])
    return out


def top_contributors(x, a, Lam, ind, k=3, eps=0.02):
    """對某一位病人、某個驅動，列出實際有證據支持的常規指標。

    貢獻取 min(Lambda[j,d] * a[d], x[j])：模型「想」用這個指標解釋多少，
    與這位病人「真的有」多少，取較小者。少了這個下限就會變成純看載荷排序，
    每個病人的理由都一樣（蛋白尿永遠排第一），等於沒有解釋。
    設計憲法第 2 條要求附「為什麼」；為什麼必須是這個人的，不是這個矩陣的。
    """
    out = {}
    for d in range(Lam.shape[1]):
        c = np.minimum(Lam[:, d] * a[d], np.maximum(x, 0.0))
        idx = np.argsort(-c)[:k]
        out[d] = [(ind[j]["name"], round(float(c[j]), 3)) for j in idx if c[j] > eps]
    return out


def pattern_shortlist(shares, profiles, k=3):
    """依驅動占比比對各組織型態的驅動輪廓，回傳最相容的前 k 個。

    這是**呈現用的候選清單，不是分類器輸出**：它只是把 L4 的三個數字換一種說法，
    沒有經過任何以組織型態為標籤的訓練或校準。因此
      1) 介面上必須標示為「相容型態」而非「診斷」；
      2) 它的 top-1／top-3 準確率必須一起量出來顯示（metrics.shortlist_accuracy），
         不然使用者會把「排第一」讀成「就是這個」。
    用餘弦相似度而非歐氏距離：要比的是機轉的**組成比例**，不是嚴重度。
    """
    P = profiles / np.maximum(np.linalg.norm(profiles, axis=1, keepdims=True), 1e-9)
    v = shares / np.maximum(np.linalg.norm(shares, axis=-1, keepdims=True), 1e-9)
    sim = v @ P.T
    order = np.argsort(-sim, axis=-1)[..., :k]
    return order, np.take_along_axis(sim, order, axis=-1)
