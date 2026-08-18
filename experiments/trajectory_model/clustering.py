# -*- coding: utf-8 -*-
"""模組三：風險層內的軌跡分群（H1）。

方法 A：每人整條 x(t) 的三次多項式係數（時間標準化到 [0,1]）→ 高斯有限混合（GMM）。
       這是群組軌跡模型的兩階段近似：先把每條序列壓成基底係數，再對係數做混合模型。
       ponytail: 沒有寫完整的 EM 群組軌跡模型（共用殘差變異、逐點似然），需要時再換。
方法 B：[水準, 斜率, 曲率, 變異度] → k-means。
群數：對 K=1..k_max 算 BIC 與 bootstrap 穩定度（同一對個案是否落在同一群的一致率），
     在穩定度 >= stability_min 的 K 中取 BIC 最小者；沒有任何 K 過門檻就取 1。
置換檢定：把每條序列的時間順序打亂後重算特徵、以同一 K 重跑，比較 silhouette。
       注意：時間打亂保留每條序列的「水準」，所以這個 p 值只回答「分群是否由時間形狀（斜率、
       曲率、變異）驅動」；只靠起始水準分開的群，p 會不顯著——這不是 bug，是該檢定的定義。
【重要】分群標籤只在本模組內使用，不得流入模組四（會帶進未來資訊）。
"""
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.mixture import GaussianMixture


def _design(T, deg):
    """正交（Legendre，欄向量單位化）多項式基底。為什麼不用 1, t, t²：那組基底高度共線，
    純雜訊序列的係數會強相關，k-means／BIC 會把相關結構誤認成群（測試抓到過）。"""
    V = np.polynomial.legendre.legvander(np.linspace(-1.0, 1.0, T), deg)
    return V / np.linalg.norm(V, axis=0)


def poly_coefs(X, deg=3):
    """每列 OLS 多項式係數（共用設計矩陣，一次矩陣乘法）。"""
    return X.astype(float) @ np.linalg.pinv(_design(X.shape[1], deg)).T


def traj_features(X):
    """[level, slope, curvature, variability]；斜率／曲率取正交基底一、二次係數，變異度取二次配適殘差 SD。"""
    A = _design(X.shape[1], 2)
    c = X.astype(float) @ np.linalg.pinv(A).T
    resid = X - c @ A.T
    return np.c_[X.mean(axis=1), c[:, 1], c[:, 2], resid.std(axis=1)]


def partition_bic(F, lab):
    """k-means 分割的分類似然 BIC：各群配適均值＋完整共變異數（加混合權重項）。
    為什麼不用常見的 k-means 等向 BIC（共用單一變異）：它在純高斯雜訊上也會一路選到 k_max
    （測試抓到過）；完整共變異數的似然在雜訊上選 K=1、在植入的兩群上選 K=2。"""
    n, d = F.shape
    K = int(lab.max()) + 1
    ll = 0.0
    for k in range(K):
        Z = F[lab == k]; nk = len(Z)
        if nk == 0:
            continue
        cov = (np.cov(Z.T, bias=True) if nk > 1 else np.zeros((d, d))) + 1e-4 * np.eye(d)
        diff = Z - Z.mean(axis=0)
        sign, logdet = np.linalg.slogdet(cov)
        maha = np.einsum("ij,jk,ik->i", diff, np.linalg.inv(cov), diff)
        ll += -0.5 * (nk * (d * np.log(2 * np.pi) + logdet) + maha.sum()) + nk * np.log(nk / n)
    params = K * (d + d * (d + 1) / 2) + (K - 1)
    return float(-2 * ll + params * np.log(n))


def _z(F):
    sd = F.std(axis=0); sd[sd < 1e-12] = 1.0
    return (F - F.mean(axis=0)) / sd


def featurize(X, method, deg=3):
    # 方法 A 的多項式係數（時間在 [0,1]）全都是 x 單位、彼此可比，不做 z 分數：
    # 若逐欄標準化，純雜訊的高次項會被放大到與斜率同權，GMM 會沿雜訊維度切群（測試抓到過）。
    # 方法 B 的四個特徵單位不同，必須標準化。
    return poly_coefs(X, deg) if method == "A" else _z(traj_features(X))


def _fit(F, K, method, seed):
    if method == "A":
        m = GaussianMixture(K, covariance_type="full", reg_covar=1e-4, n_init=1, random_state=seed).fit(F)
        return m, float(m.bic(F))
    m = KMeans(K, n_init=3, random_state=seed).fit(F)
    return m, partition_bic(F, m.labels_)


def _co(labels):
    return labels[:, None] == labels[None, :]


def stability(F, K, method, ref_labels, n_boot, rng):
    """bootstrap 重抽個案，重配適後對兩者都在的個案，算「同群/不同群」與參考分割一致的配對比例。"""
    if K == 1:
        return 1.0
    n = len(F); acc = []
    for b in range(n_boot):
        idx = rng.choice(n, n, replace=True)
        u = np.unique(idx)
        try:
            m, _ = _fit(F[idx], K, method, int(rng.integers(1 << 31)))
            lab = m.predict(F[u])
        except Exception:
            continue
        sub_ref = _co(ref_labels[u]); sub_b = _co(lab)
        iu_u = np.triu_indices(len(u), 1)
        acc.append(float((sub_ref[iu_u] == sub_b[iu_u]).mean()))
    return float(np.mean(acc)) if acc else np.nan


def select_k(F, method, k_max, n_boot, stab_min, rng):
    rows = []
    for K in range(1, k_max + 1):
        if K >= len(F):
            break
        m, bic = _fit(F, K, method, int(rng.integers(1 << 31)))
        lab = m.predict(F)
        st = stability(F, K, method, lab, n_boot, rng)
        rows.append(dict(K=K, bic=bic, stability=st, labels=lab))
    ok = [r for r in rows if r["K"] == 1 or (np.isfinite(r["stability"]) and r["stability"] >= stab_min)]
    best = min(ok, key=lambda r: r["bic"])
    return best, rows


def _silhouette(F, labels):
    if len(np.unique(labels)) < 2 or len(np.unique(labels)) >= len(F):
        return -1.0
    return float(silhouette_score(F, labels))


def perm_test(X, method, K, n_perm, rng, deg):
    """時間順序置換：破壞每條序列的時間結構後，同 K 重跑，看真實 silhouette 是否超過虛無 95 分位。"""
    if K == 1:
        return dict(silhouette=np.nan, null_q95=np.nan, p=np.nan)
    F = featurize(X, method, deg)
    m, _ = _fit(F, K, method, int(rng.integers(1 << 31)))
    obs = _silhouette(F, m.predict(F))
    null = []
    for _ in range(n_perm):
        Xp = rng.permuted(X, axis=1)
        Fp = featurize(Xp, method, deg)
        mp, _ = _fit(Fp, K, method, int(rng.integers(1 << 31)))
        null.append(_silhouette(Fp, mp.predict(Fp)))
    null = np.array(null)
    return dict(silhouette=obs, null_q95=float(np.quantile(null, 0.95)),
                p=float((1 + (null >= obs).sum()) / (1 + n_perm)))


def cluster_stratum(X, method, P, rng, gen_labels=None):
    Q = P["clustering"]
    deg = Q["poly_degree"]
    F = featurize(X, method, deg)
    best, rows = select_k(F, method, Q["k_max"], Q["n_bootstrap"],
                          P["clustering"]["stability_min"]["value"], rng)
    lab = best["labels"]
    shares = np.bincount(lab, minlength=best["K"]) / len(lab)
    out = dict(K=int(best["K"]), hit_kmax=bool(best["K"] == Q["k_max"]),      # 撞到上限要明說（無靜默上限）
               shares=[float(s) for s in shares], stability=float(best["stability"]),
               bic_by_k={int(r["K"]): float(r["bic"]) for r in rows},
               stability_by_k={int(r["K"]): float(r["stability"]) for r in rows},
               perm=perm_test(X, method, best["K"], Q["n_permutation"], rng, deg), n=int(len(X)))
    if gen_labels is not None:
        # 「可推回比例」：分群結果對生成器標籤（型別＋子類別）的 ARI / NMI；高 = 重現生成器而非發現
        out["ari_vs_generator"] = float(adjusted_rand_score(gen_labels, lab))
        out["nmi_vs_generator"] = float(normalized_mutual_info_score(gen_labels, lab))
    # 代表性軌跡：各群平均序列，每 7 天取一點（供繪圖；避免 results.json 膨脹）
    out["mean_traj"] = [X[lab == k].mean(axis=0)[::7].astype(float).round(4).tolist() for k in range(best["K"])]
    return out


def generator_labels(C):
    """線性型 = 子類別 0..2；翻轉型分「五年內未跨 μc（穩定）」= 10 與「已跨 μc（翻轉）」= 11——
    漂移起始日隨機後，多數翻轉型在 T 內未翻轉、序列近似定態，與已翻轉者是兩種形狀。"""
    return np.where(C["is_flip"], np.where(C["t_crit"] >= 0, 11, 10), C["cls"])


def run_clustering(C, strata, method, P, rng):
    """對每一層跑一次；回傳 list（層序）。"""
    g = generator_labels(C)
    res = []
    for s in range(strata.max() + 1):
        idx = np.where(strata == s)[0]
        r = cluster_stratum(C["X"][idx], method, P, rng, g[idx])
        r["stratum"] = int(s)
        res.append(r)
    return res
