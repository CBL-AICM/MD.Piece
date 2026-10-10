# -*- coding: utf-8 -*-
"""網頁工具 v3.1：常規套組模型＋以 NHANES 2021–2023 更新校準（2026-09-27；使用者於外部確認之後決定）。
    python recalibrate_v3_1.py      → params/direction_model_v3_1.json、results/direction_v3_1_recalibration.json

來源模型：params/direction_model_basic.json（凍結之常規套組候選，外部確認已評；本程式只讀不改）。
資料：外部確認主要分析的同一批人（external_validation_2021.load_2021，CDC 官方回推式調和後）。
更新方法（規則先寫定再計算；由簡到繁，Vergouwe 2017）：
  1) 截距更新：logit p' = a + logit p
  2) 截距與斜率更新：logit p' = a + b·logit p
  p 為保序校準後之機率，以 EPS 截斷（同 evaluate_v3.calib）。該軸陽性 ≥ MIN_EVENTS（外部驗證之最低事件數）
  且斜率之概似比檢定 p < 0.05 才用 2)，否則用 1)。
事前機率改為 2021–2023 該軸之實際比例，分區門檻依同一勝算規則重算（傾向 ≥2×、不傾向 ≤0.5× 事前勝算）。
判別不受單調轉換影響；更新後的校準與分區只能在同一批資料上計算（表面值），尚無獨立資料驗證。"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
import numpy as np                                               # noqa: E402
from scipy.stats import chi2                                     # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

import external_validation_2021 as ev                            # noqa: E402
from direction import AXES, EPS, odds_thresholds, predict_matrix  # noqa: E402
from evaluate_v3 import band_stats, calib                        # noqa: E402

SRC = os.path.join(ROOT, "params", "direction_model_basic.json")
REPORT = os.path.join(ROOT, "results", "direction_v3_1_recalibration.json")
OUT_V31 = os.path.join(ROOT, "params", "direction_model_v3_1.json")   # 明寫路徑：direction.PARAMS 之後指向 v3.2
MIN_EVENTS = 100


def fit(y, o, slope):
    """logit μ = a + b·o（slope=True）或 a + o（offset）；牛頓法。回傳 (係數, 對數概似)。"""
    X = np.column_stack([np.ones_like(o), o]) if slope else np.ones((len(o), 1))
    off = 0.0 if slope else o
    b = np.zeros(X.shape[1])
    for _ in range(100):
        mu = 1 / (1 + np.exp(-(X @ b + off)))
        step = np.linalg.solve((X.T * (mu * (1 - mu))) @ X, X.T @ (y - mu))
        b += step
        if np.max(np.abs(step)) < 1e-12:
            break
    mu = 1 / (1 + np.exp(-(X @ b + off)))
    return b, float(np.sum(y * np.log(mu) + (1 - y) * np.log(1 - mu)))


def update(M, kd, version, data_desc):
    """依規則更新校準（v3.1、v3.2 共用）；kd 為腎臟指標異常者。回傳 (模型, 逐軸報告)。"""
    axes, rep = {}, {}
    for name, spec in AXES.items():
        a = M["axes"][name]
        d = kd[kd[spec["label"]].notna()]
        y = d[spec["label"]].astype(int).to_numpy()
        X = np.column_stack([d[f].to_numpy(float) if f in d.columns else np.full(len(d), np.nan) for f in a["features"]])
        p0 = predict_matrix(a, X)[1]
        c = np.clip(p0, EPS, 1 - EPS)
        o = np.log(c / (1 - c))
        (a1,), ll1 = fit(y, o, False)
        (a2, b2), ll2 = fit(y, o, True)
        p_slope = float(chi2.sf(2 * (ll2 - ll1), 1))
        use_slope = int(y.sum()) >= MIN_EVENTS and p_slope < 0.05
        r = dict(method="截距與斜率更新" if use_slope else "截距更新",
                 a=float(a2 if use_slope else a1), b=float(b2 if use_slope else 1.0),
                 data=data_desc, n=int(len(y)), n_pos=int(y.sum()),
                 rule=f"陽性 ≥{MIN_EVENTS} 且斜率概似比檢定 p<0.05 才更新斜率；否則只更新截距")
        prev = float(y.mean())
        t_hi, t_lo = odds_thresholds(prev)
        axes[name] = dict(a, recalibration=r, prevalence_development=a["prevalence"], prevalence=prev,
                          t_high=t_hi, t_low=t_lo)
        _, p1, band = predict_matrix(axes[name], X)
        ok = band >= 0
        rep[name] = dict(
            n=int(len(y)), n_pos=int(y.sum()), recalibration=r,
            candidates=dict(intercept_only=dict(a=float(a1), loglik=ll1),
                            intercept_slope=dict(a=float(a2), b=float(b2), loglik=ll2), slope_lr_test_p=p_slope),
            before=dict(auroc=float(roc_auc_score(y, p0)), ap=float(average_precision_score(y, p0)), calibration=calib(y, p0)),
            after_apparent=dict(auroc=float(roc_auc_score(y, p1)), ap=float(average_precision_score(y, p1)),
                                calibration=calib(y, p1), thresholds=dict(t_high=t_hi, t_low=t_lo),
                                insufficient_data_n=int((~ok).sum()), bands=band_stats(y[ok], band[ok])))
        print(f"[{name}] n={len(y):,} 陽性 {int(y.sum())}｜斜率檢定 p={p_slope:.3g} → {r['method']}：a={r['a']:.3f}、b={r['b']:.3f}"
              f"｜平均預測 {p0.mean():.4f} → {p1.mean():.4f}（實際 {prev:.4f}）｜門檻 傾向 ≥{t_hi:.4f}、不傾向 ≤{t_lo:.4f}"
              f"｜AUROC {rep[name]['before']['auroc']:.3f} → {rep[name]['after_apparent']['auroc']:.3f}")
    return dict(M, version=version, axes=axes), rep


def main():
    assert os.path.exists(ev.OUT), "更新校準須在外部確認（一次性評估）之後"
    M = json.load(open(SRC, encoding="utf-8"))
    kd = ev.load_2021(True)
    out, rep = update(M, kd[kd["kidney3"] == 1], "v3.1", "NHANES 2021–2023（週期 L；CDC 官方回推式調和後）")
    out.update(source_model=dict(path=os.path.relpath(SRC, ROOT), sha256=hashlib.sha256(open(SRC, "rb").read()).hexdigest()),
               performance="判別：內部見 results/v3_eval.json（常規套組）、外部見 results/external_2021_2023.json；"
                           "更新後之表面值見 results/direction_v3_1_recalibration.json（尚無獨立資料驗證）",
               band_rule="勝算倍數：傾向 ≥2× 事前勝算、不傾向 ≤0.5×；事前＝2021–2023 該軸比例；常規套組有值 <50% → 資料不足")
    json.dump(out, open(OUT_V31, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(dict(note="表面值：更新校準與評估用同一批資料，不是獨立驗證", axes=rep), open(REPORT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"[存檔] {OUT_V31}\n[存檔] {REPORT}")


if __name__ == "__main__":
    main()
