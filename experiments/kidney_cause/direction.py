# -*- coding: utf-8 -*-
"""兩軸病因線索工具（v3，2026-09-26）：常規檢驗數值 → 肝炎病毒感染／糖尿病兩個共存標籤的相對傾向。

    python direction.py train                 # 以 v3 三值標籤訓練，存成可攜參數
    python direction.py predict values.json   # 對一組數值判定
    python direction.py demo                  # 用真實受試者示範（僅展示，不是準確率證據）

## 能說什麼、不能說什麼
輸出是「這組數值與肝炎病毒感染（HBsAg 或 HCV RNA 陽性）／糖尿病標籤者相比，像不像」，
是病因線索，不是病因診斷：共存標籤不等於腎損傷由該病造成。效能以巢狀外層評估報告於
results/v3_eval.json（本檔不再寫入樣本內的分區統計）。

## v3 相對 v2 的變更（版本紀錄見 docs/VERSION_LOG.md）
1. 標籤三值、各軸排除未知；1999-2000 肌酸酐公式更正；2007 前尿肌酸酐轉換（見 nhanes_cohort.build_v3）
2. 分區改用勝算倍數：p 的勝算 ≥ 2×事前勝算 → 傾向；≤ 0.5× → 不傾向。v2 的「2×盛行率」在盛行率 >50% 時
   無法達成，且兩軸代表的證據強度不同；此規則於結果產生前決定（params/v3_analysis_plan.json）
3. 新增「資料不足」：常規套組特徵有值 <50% 不給分區；另標出超出開發資料範圍的輸入值

## v3.1（2026-09-27，NHANES 2021–2023 外部確認之後）
網頁工具與 predict 預設改用常規套組模型（params/direction_model_v3_1.json，由 recalibrate_v3_1.py 產生）：
保序校準之後再做一次邏輯重新校準 logit p' = a + b·logit p，事前機率改為 2021–2023 之盛行率。
凍結之 v3 兩個模型檔不變（外部確認協定登錄其雜湊）；沒有 recalibration 欄位的模型行為與 v3 完全相同。
"""
import json
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np                                          # noqa: E402
from sklearn.isotonic import IsotonicRegression             # noqa: E402
from sklearn.impute import SimpleImputer                    # noqa: E402
from sklearn.linear_model import LogisticRegression         # noqa: E402
from sklearn.metrics import roc_auc_score                   # noqa: E402
from sklearn.model_selection import StratifiedKFold         # noqa: E402
from sklearn.preprocessing import StandardScaler            # noqa: E402

from binary_tasks import LABEL_ADJACENT                     # noqa: E402
from evaluate_v3 import BASIC, EPS                          # noqa: E402
from nhanes_cohort import DERIVED, FEATURE_LABELS, build_v3  # noqa: E402

PARAMS_FULL = os.path.join(ROOT, "params", "direction_model.json")     # v3 全特徵（凍結；外部確認時之部署模型）
PARAMS = os.path.join(ROOT, "params", "direction_model_v3_1.json")     # 網頁工具 v3.1：常規套組＋2021–2023 重新校準
LABEL = {**FEATURE_LABELS, **DERIVED, "age": "年齡", "sex": "性別"}
AXES = {
    "肝炎": dict(label="hep3", adjacent=LABEL_ADJACENT["infection"], title="肝炎病毒感染（HBsAg 或 HCV RNA 陽性）"),
    "糖尿病": dict(label="dm3", adjacent=LABEL_ADJACENT["metabolic"], title="糖尿病（醫師診斷或 HbA1c ≥6.5%）"),
}
MIN_BASIC_PRESENT = 0.5


def odds_thresholds(prev):
    o = prev / (1 - prev)
    return 2 * o / (1 + 2 * o), 0.5 * o / (1 + 0.5 * o)


def _fit(X, y, seed):
    imp = SimpleImputer(strategy="median").fit(X)
    sc = StandardScaler().fit(imp.transform(X))
    lr = LogisticRegression(class_weight="balanced", max_iter=4000,
                            random_state=seed).fit(sc.transform(imp.transform(X)), y)
    return dict(medians=imp.statistics_.tolist(), mean=sc.mean_.tolist(),
                scale=sc.scale_.tolist(), coef=lr.coef_[0].tolist(),
                intercept=float(lr.intercept_[0]))


def _raw(fp, x):
    xi = np.where(np.isnan(x), np.array(fp["medians"]), x)
    z = (xi - np.array(fp["mean"])) / np.array(fp["scale"])
    return float(1 / (1 + np.exp(-(z @ np.array(fp["coef"]) + fp["intercept"])))), z


def recal(a, p):
    """v3.1 邏輯重新校準（p 以 EPS 截斷，同 evaluate_v3.calib）；無 recalibration 欄位者原樣返回。"""
    r = a.get("recalibration")
    if not r:
        return p
    c = np.clip(p, EPS, 1 - EPS)
    return 1 / (1 + np.exp(-(r["a"] + r["b"] * np.log(c / (1 - c)))))


def predict_matrix(a, X):
    """一軸、多人（X: n×p，欄序＝a['features']，缺值 NaN）→ (raw, cal, band 2/1/0/-1)。-1＝資料不足。"""
    raws = []
    for fp in a["ensemble"]:
        Xi = np.where(np.isnan(X), np.array(fp["medians"]), X)
        z = (Xi - np.array(fp["mean"])) / np.array(fp["scale"])
        raws.append(1 / (1 + np.exp(-(z @ np.array(fp["coef"]) + fp["intercept"]))))
    raw = np.mean(raws, axis=0)
    cal = recal(a, np.interp(raw, a["isotonic_x"], a["isotonic_y"]))
    ib = [a["features"].index(f) for f in a["basic_panel"]]
    band = np.where(cal >= a["t_high"], 2, np.where(cal <= a["t_low"], 0, 1))
    band = np.where((~np.isnan(X[:, ib])).mean(axis=1) < MIN_BASIC_PRESENT, -1, band)
    return raw, cal, band


def train(seed=20260926, folds=5, feature_set="full", path=PARAMS_FULL):
    """feature_set：full＝全部特徵（部署版）；basic＝僅常規套組（比較用候選版，待新資料確認）。"""
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = build_v3(P, verbose=False)
    kd, feats = V["cohort"], V["features"]
    out = dict(version="v3" if feature_set == "full" else "v3-basic", feature_set=feature_set, seed=seed,
               performance="見 results/v3_eval.json（巢狀外層評估）",
               band_rule="勝算倍數：傾向 ≥2× 事前勝算、不傾向 ≤0.5×；常規套組有值 <50% → 資料不足", axes={})
    for name, spec in AXES.items():
        d = kd[kd[spec["label"]].notna()]
        ff = [f for f in feats if f not in spec["adjacent"]]
        if feature_set == "basic":
            ff = [f for f in BASIC if f in ff]
        y = d[spec["label"]].astype(int).to_numpy()
        X = d[ff].to_numpy(float)
        oof, models = np.zeros(len(y)), []
        for tr, va in StratifiedKFold(folds, shuffle=True, random_state=seed).split(X, y):
            fp = _fit(X[tr], y[tr], seed)
            oof[va] = np.array([_raw(fp, r)[0] for r in X[va]])
            models.append(fp)
        iso = IsotonicRegression(out_of_bounds="clip").fit(oof, y)
        prev = float(y.mean())
        t_hi, t_lo = odds_thresholds(prev)
        out["axes"][name] = dict(
            title=spec["title"], n=int(len(y)), n_pos=int(y.sum()), features=ff,
            basic_panel=[f for f in BASIC if f in ff], prevalence=prev, t_high=t_hi, t_low=t_lo,
            oof_auroc_raw_crossfit=float(roc_auc_score(y, oof)),
            train_min=np.nanmin(X, axis=0).tolist(), train_max=np.nanmax(X, axis=0).tolist(),
            ensemble=models, isotonic_x=iso.X_thresholds_.tolist(), isotonic_y=iso.y_thresholds_.tolist())
        print(f"[{name}] n={len(y):,} 陽性 {y.sum():,}（{prev:.4f}）｜交叉配適 AUROC {out['axes'][name]['oof_auroc_raw_crossfit']:.3f}"
              f"｜門檻 傾向 ≥{t_hi:.4f}、不傾向 ≤{t_lo:.4f}")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[存檔] {path}")
    return out


def predict(values, model=None, top_k=4):
    """values: dict{變數代碼: 數值}。缺的變數以訓練集中位數補，並在輸出標明。"""
    M = model or json.load(open(PARAMS, encoding="utf-8"))
    res = dict(input_n=len(values), axes={})
    for name, a in M["axes"].items():
        ff = a["features"]
        x = np.array([float(values.get(f, np.nan)) for f in ff])
        missing = [f for f, v in zip(ff, x) if np.isnan(v)]
        basic_present = float(np.mean([not np.isnan(x[ff.index(f)]) for f in a["basic_panel"]]))
        out_of_range = [f for i, f in enumerate(ff) if not np.isnan(x[i]) and
                        (x[i] < a["train_min"][i] or x[i] > a["train_max"][i])]
        raws, contribs = [], np.zeros(len(ff))
        for fp in a["ensemble"]:
            r, z = _raw(fp, x)
            raws.append(r)
            contribs += z * np.array(fp["coef"])
        cal = float(recal(a, np.interp(float(np.mean(raws)), a["isotonic_x"], a["isotonic_y"])))
        prev = a["prevalence"]
        odds_ratio = (cal / (1 - cal)) / (prev / (1 - prev)) if 0 < cal < 1 else (0.0 if cal <= 0 else float("inf"))
        if basic_present < MIN_BASIC_PRESENT:
            band = "資料不足"
        else:
            band = "傾向" if cal >= a["t_high"] else "不傾向" if cal <= a["t_low"] else "不確定"
        contribs /= len(a["ensemble"])
        order = np.argsort(-np.abs(contribs))
        drivers = [dict(var=ff[i], name=LABEL.get(ff[i], ff[i]), value=float(x[i]),
                        push=("→推向" if contribs[i] > 0 else "←推離"), weight=float(contribs[i]))
                   for i in order if not np.isnan(x[i])][:top_k]
        res["axes"][name] = dict(
            title=a["title"], probability=cal, prevalence=prev, odds_ratio_vs_prior=odds_ratio, band=band,
            drivers=drivers, missing_filled_with_median=missing, n_missing=len(missing), n_features=len(ff),
            basic_panel_present=basic_present, out_of_range=out_of_range)
    return res


def render(res):
    L = ["病因線索（共存標籤之相對傾向，非診斷）", "─" * 62]
    for name, a in res["axes"].items():
        L.append(f"  {a['title']}  機率 {a['probability']:.4f}（事前 {a['prevalence']:.4f}；勝算 ×{a['odds_ratio_vs_prior']:.2f}）"
                 f" → **{a['band']}**")
        for d in a["drivers"]:
            L.append(f"        {d['push']} {d['name']}={d['value']:.3g}")
        if a["n_missing"]:
            L.append(f"        ⚠ 缺 {a['n_missing']}/{a['n_features']} 項以中位數補入（常規套組有值 {a['basic_panel_present']:.0%}）")
        if a["out_of_range"]:
            L.append(f"        ⚠ 超出開發資料範圍：{', '.join(LABEL.get(f, f) for f in a['out_of_range'])}")
    return "\n".join(L)


def demo(n_each=2, seed=7):
    """示範：每類真實受試者各取 n_each 人。僅作展示（見 v3_eval.json 之整體效能），不代表準確率。"""
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    kd = build_v3(P, verbose=False)["cohort"]
    M = json.load(open(PARAMS, encoding="utf-8"))
    rng = np.random.default_rng(seed)
    allf = sorted({f for a in M["axes"].values() for f in a["features"]})
    for tag, mask in (("肝炎標籤陽性", kd["hep3"] == 1), ("糖尿病標籤陽性", kd["dm3"] == 1),
                      ("兩標籤皆陰性", (kd["hep3"] == 0) & (kd["dm3"] == 0))):
        for i in rng.choice(kd[mask].index, size=n_each, replace=False):
            vals = {f: kd.loc[i, f] for f in allf if not np.isnan(kd.loc[i, f])}
            print(f"\n══ {tag}（SEQN {int(kd.loc[i, 'SEQN'])}，{kd.loc[i, 'cycle']}）══")
            print(render(predict(vals, M)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "train":
        train()
        train(feature_set="basic", path=os.path.join(ROOT, "params", "direction_model_basic.json"))
    elif cmd == "predict":
        print(render(predict(json.load(open(sys.argv[2], encoding="utf-8")))))
    else:
        demo()
