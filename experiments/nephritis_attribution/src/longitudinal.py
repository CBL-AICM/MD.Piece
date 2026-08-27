# -*- coding: utf-8 -*-
"""公式 1–3：縱向特徵（變化量、變化率、混合模型隨機斜率）。

三條公式在數學上都沒有問題，會出事的是**時間視窗怎麼取**：

  公式 1  ΔX = X(t2) − X(t1)
  公式 2  Slope = (X(t2) − X(t1)) / (t2 − t1)

兩者都沒有規定 t2 落在決策點的哪一側。回溯資料庫裡「上一次」與「下一次」抽血
長得一樣近，寫 SQL 的時候很容易就把決策點之後的那一筆抓進來 —— 論文的數字會
變漂亮，上線後會掉下來。這與閘門 G4 抓到的是同一類錯誤，只是換了個入口。
所以本檔案的所有特徵一律只吃 t <= 0 的面板，而 leak_demo() 把踩下去的代價量出來。

公式 3（線性混合模型）在這裡的角色要講清楚：

  X_it = β0 + β1·t + b0i + b1i·t + ε_it

族群層的 β1 在這個世代裡**沒有意義** —— 世代裡同時有惡化中的壞死性血管炎與
穩定的硬化型，把它們的時間趨勢平均起來不代表任何一個人。真正被拿來當特徵的是
b1i（個人斜率），而 LMM 在此純粹是一個**收縮裝置**：把雜訊大的個人斜率往族群
拉回去。三個時間點的個人斜率標準誤很大，收縮確實有道理，但也因為只有三點，
收縮後的 b1i 與公式 2 的簡單斜率會非常接近 —— 這是可以量的，見 run_formulas.py。

實作說明：統計環境沒有 statsmodels。平衡設計（每人時間點相同）下，隨機斜率的
BLUP 有封閉解，等價於對個人 OLS 斜率做經驗貝氏收縮，本檔即以此實作，
不是近似而是同一個估計量。若日後改成不平衡設計（每人回診時間不同），
這條封閉解就不成立，必須改用真正的 LMM 求解器。
"""
import numpy as np


def panels(coh, include_future=False):
    """回傳 (X_series[T, n, p], times[T])。預設只給決策點與其之前。"""
    from attribution import load
    C = load("patterns.json")["context"]
    t = list(C["panel_weeks"])                      # 例如 [-12, -6, 0]
    series = [coh["prior_X"][k] for k in range(coh["prior_X"].shape[0])] + [coh["_X_now"]]
    if include_future:
        series.append(coh["future_X"])
        t = t + [C["future_panel_weeks"]]
    return np.stack(series), np.array(t, dtype=float)


def delta(series):
    """公式 1：ΔX = X(t_last) − X(t_prev)。單位與原指標相同，不做任何正規化。"""
    return series[-1] - series[-2]


def slope(series, times):
    """公式 2：以最早與最後一個面板算單位時間變化率。

    刻意用兩端點而非全部點的迴歸，因為公式 2 寫的就是兩點式；
    三點以上的最小平方版本由 blup_slope 的 OLS 部分提供，兩者一起比才看得出差別。
    """
    return (series[-1] - series[0]) / (times[-1] - times[0])


def ols_slope(series, times):
    """每人每指標的個人 OLS 斜率（公式 3 的 b1i 在收縮之前的樣子）。"""
    t = times - times.mean()
    stt = float((t ** 2).sum())
    xbar = series.mean(axis=0)
    return np.tensordot(t, series - xbar, axes=(0, 0)) / stt, stt


def blup_slope(series, times):
    """公式 3：隨機斜率的 BLUP（平衡設計下的封閉解）。

    b1i = τ² / (τ² + σ²/Stt) · (個人 OLS 斜率 − 族群平均斜率)

    τ² 為個人斜率的真實變異，用「觀察到的斜率變異 − 抽樣變異」估計；
    負值截斷為 0，代表資料看不出個人間有斜率差異，此時收縮到底＝所有人都用族群斜率。
    收縮係數一併回傳：它接近 1 表示 LMM 幾乎沒動簡單斜率，接近 0 表示個人斜率全是雜訊。
    """
    s, stt = ols_slope(series, times)                       # (n, p)
    t = times - times.mean()
    fitted = s[None, :, :] * t[:, None, None] + series.mean(axis=0)[None, :, :]
    dof = max(1, len(times) - 2)
    sigma2 = ((series - fitted) ** 2).sum(axis=0).mean(axis=0) / dof   # (p,) 誤差變異
    se2 = sigma2 / stt
    tau2 = np.maximum(0.0, s.var(axis=0) - se2)
    shrink = tau2 / np.maximum(tau2 + se2, 1e-12)
    return shrink * (s - s.mean(axis=0)) + s.mean(axis=0), shrink


def build(coh, X_now, kind):
    """組出要餵給 L3 的特徵矩陣。kind: base / delta / slope / both / blup。"""
    coh = dict(coh, _X_now=X_now)
    series, times = panels(coh)
    if kind == "base":
        return X_now, ["base"]
    if kind == "delta":
        return np.hstack([X_now, delta(series)]), ["base", "Δ"]
    if kind == "slope":
        return np.hstack([X_now, slope(series, times)]), ["base", "slope"]
    if kind == "both":
        return np.hstack([X_now, delta(series), slope(series, times)]), ["base", "Δ", "slope"]
    if kind == "blup":
        b, _ = blup_slope(series, times)
        return np.hstack([X_now, b]), ["base", "BLUP"]
    raise ValueError(kind)


def leak_demo(coh, X_now):
    """把「t2 取到決策點之後」的代價量出來。

    回傳 (誠實斜率特徵, 洩漏斜率特徵)。兩者唯一的差別是後者的最後一個面板
    來自決策點之後 —— 在真實資料庫裡，這個差別只是 SQL 的一個不等號方向。
    """
    honest = dict(coh, _X_now=X_now)
    s_h, t_h = panels(honest)
    s_l, t_l = panels(honest, include_future=True)
    return (np.hstack([X_now, slope(s_h, t_h)]),
            np.hstack([X_now, slope(s_l, t_l)]))


def build_deployable(X_now, X_prev, weeks_ago):
    """可部署版：只需要「一次既往檢驗 ＋ 距今幾週」。

    評估時用的是 3 個面板，但真實使用者手上通常只翻得到上一次抽血。
    刻意用使用者拿得出來的形式訓練，而不是用評估時的理想形式 ——
    否則上線後餵進去的東西與訓練時不同，效能會無聲地掉下來。
    """
    d = X_now - X_prev
    w = np.maximum(np.asarray(weeks_ago, dtype=float), 1e-6)
    if d.ndim == 2:
        w = w.reshape(-1, 1)
    return np.hstack([X_now, d, d / w])
