# -*- coding: utf-8 -*-
"""最終模型：腎損傷者的感染性病因分診。
    python final_model.py [--seed 20260830]

## 這個模型做什麼

輸入常規血液／尿液檢驗 → 輸出**是否建議開立肝炎血清學檢驗**。

三種輸出，不是二分：`建議檢驗` ／ `不建議` ／ **`無法判定`**（拒答）。
拒答是設計的一部分——模型在把握不足時明說，而非硬猜。
報告時**拒答率與作答者正確率一律並列**，只報後者是誤導。

## 為什麼只做這一件事

本專案測過三個病因軸，只有這一軸站得住：

| 軸 | 結論 | 依據 |
|---|---|---|
| 感染 | ✅ 可用 | AUROC 0.79–0.82；AUPRC 為盛行率基準的 6.7 倍；十週期外測全部 >0.67 |
| 代謝 | ⚠️ 不納入 | 0.816 但無增益價值——臨床上本來就知道誰有糖尿病 |
| 免疫 | ❌ 不可用 | 0.575；60 個標記單標記掃描僅「性別」過 FDR（q=0.004），無生理訊號 |

## 事前登錄（寫在跑之前）

* **模型**：邏輯迴歸（LR）。理由不是它分數高，而是 `TRAINING_SUMMARY.md` §5.1 已證明
  HGB 在本任務的優勢（小世代 +0.060）在樣本擴大後歸零（−0.002）＝過擬合產物。
  同分時取較簡單、係數可讀、可攜出的那個。HGB 一併報告以供對照。
* **校準**：`class_weight="balanced"` 會使輸出機率嚴重高估（LR 的 Brier 0.149 遠高於
  盛行率 0.019）。故最終模型加保序回歸（isotonic）校準，**只在內層折上配適**。
* **作業點**：篩檢用途，事前指定**作答者敏感度 ≥ 0.80**——漏掉一例感染的代價
  高於多開一張肝炎血清學單（該檢驗便宜、無創、無風險）。
* **拒答帶**：雙門檻於內層折選定，限制條件為**拒答率 ≤ 30%**，在此限制下最大化
  作答者平衡正確率。
* **成功判準**：作答者敏感度 ≥ 0.80 **且** 拒答率 ≤ 30% **且** 保留集 AUROC 之
  CI 下界 > 0.70。未達成則照實報告，不調參。

## 關於保留集的誠實聲明

`results/holdout_eval.json` 記錄的既有保留集是為**三類問題**建的
（`test_lab.py` 以 `cause` 三分類擬合），且僅涵蓋 1999–2004。該問題已因
結構性不可解而作廢，故其保留集對本模型不適用，本檔另立保留集。

**但必須說明其限制**：1999–2018 的資料在本專案中已被反覆分析，
現在才切出的保留集**不是未曾窺視的測試集**。真正接近外部驗證的證據是
**留一週期外測**（`binary_tasks_extended.py`），本檔一併重報該結果，
並以它而非保留集作為主要的類化證據。"""
import argparse
import hashlib
import json
import os
import sys
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np                                              # noqa: E402
from sklearn.isotonic import IsotonicRegression                 # noqa: E402
from sklearn.impute import SimpleImputer                        # noqa: E402
from sklearn.linear_model import LogisticRegression             # noqa: E402
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,   # noqa: E402
                             brier_score_loss, roc_auc_score)
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold     # noqa: E402
from sklearn.preprocessing import StandardScaler                # noqa: E402

from nhanes_cohort import build_extended                        # noqa: E402
import pipeline as PL                                           # noqa: E402
from binary_tasks import LABEL_ADJACENT                         # noqa: E402

RESULTS = os.path.join(ROOT, "results")

# ── 事前登錄常數，不得於見到結果後修改
MIN_SENSITIVITY = 0.80        # 作答者敏感度下限（篩檢用途）
MAX_ABSTAIN = 0.30            # 拒答率上限
MIN_HOLDOUT_CI_LOWER = 0.70   # 保留集 AUROC 之 CI 下界
HOLDOUT_FRAC = 0.25


def _fit(Xtr, ytr, seed):
    """插補→標準化→加權 LR。回傳 (predict_fn, 可攜出參數)。"""
    imp = SimpleImputer(strategy="median").fit(Xtr)
    sc = StandardScaler().fit(imp.transform(Xtr))
    lr = LogisticRegression(class_weight="balanced", max_iter=4000,
                            random_state=seed).fit(sc.transform(imp.transform(Xtr)), ytr)
    return (lambda X: lr.predict_proba(sc.transform(imp.transform(X)))[:, 1],
            dict(medians=imp.statistics_.tolist(), mean=sc.mean_.tolist(),
                 scale=sc.scale_.tolist(), coef=lr.coef_[0].tolist(),
                 intercept=float(lr.intercept_[0])))


def pick_bands(p, y, min_sens=MIN_SENSITIVITY, max_abstain=MAX_ABSTAIN):
    """在內層機率上選雙門檻：拒答率≤上限、作答者敏感度≥下限，其中最大化作答者平衡正確率。

    回傳 (t_low, t_high, 診斷資訊)。找不到可行解時回退為單門檻（拒答率 0）。"""
    qs = np.quantile(p, np.linspace(0.01, 0.99, 60))
    best, best_score = None, -1.0
    for i, lo in enumerate(qs):
        for hi in qs[i:]:
            ans = (p <= lo) | (p >= hi)
            ab = 1.0 - ans.mean()
            if ab > max_abstain or ans.sum() < 30:
                continue
            ya, pa = y[ans], (p[ans] >= hi).astype(int)
            if ya.sum() == 0 or (1 - ya).sum() == 0:
                continue
            sens = float(pa[ya == 1].mean())
            if sens < min_sens:
                continue
            score = balanced_accuracy_score(ya, pa)
            if score > best_score:
                best_score, best = score, (float(lo), float(hi),
                                           dict(abstain_rate=float(ab), sensitivity=sens,
                                                balanced_accuracy=float(score), feasible=True))
    if best is None:   # 無可行解：退為單門檻，如實標記
        thr = float(np.quantile(p, 1 - min(0.5, max(0.05, y.mean() * 3))))
        return thr, thr, dict(abstain_rate=0.0, feasible=False,
                              note="事前限制條件下無可行雙門檻——退回單門檻並照實標記")
    return best


def evaluate(y, p, t_low, t_high):
    """含拒答的評估：拒答率與作答者指標並列。"""
    ans = (p <= t_low) | (p >= t_high)
    ya, pa = y[ans], (p[ans] >= t_high).astype(int)
    out = dict(n=int(len(y)), abstain_rate=float(1 - ans.mean()), n_answered=int(ans.sum()),
               auroc_all=float(roc_auc_score(y, p)), auprc_all=float(average_precision_score(y, p)),
               auprc_baseline=float(y.mean()), brier=float(brier_score_loss(y, p)))
    if ya.sum() and (1 - ya).sum():
        out.update(answered_sensitivity=float(pa[ya == 1].mean()),
                   answered_specificity=float(1 - pa[ya == 0].mean()),
                   answered_balanced_accuracy=float(balanced_accuracy_score(ya, pa)),
                   answered_ppv=float(ya[pa == 1].mean()) if pa.sum() else None,
                   answered_npv=float(1 - ya[pa == 0].mean()) if (1 - pa).sum() else None)
    return out


def run(seed=20260830, verbose=True):
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    E = build_extended(P, verbose=verbose)
    kd, feats = E["cohort"], E["features"]
    adj = set(LABEL_ADJACENT["infection"])
    ff = [f for f in feats if f not in adj]
    y = kd["lab_infection"].fillna(False).astype(bool).astype(int).to_numpy()
    X = kd[ff].to_numpy(float)
    seqn = kd["SEQN"].to_numpy()

    if verbose:
        print(f"\n[最終模型] n={len(y)}｜陽性 {y.sum()}（盛行率 {y.mean():.4f}）｜特徵 {len(ff)} 欄")
        print(f"           已拔除標籤鄰近 {sorted(adj)}")

    # ── 保留集（新立；理由與限制見檔頭）
    hp = os.path.join(RESULTS, "final_holdout_seqn.json")
    if os.path.exists(hp):
        doc = json.load(open(hp, encoding="utf-8"))
        assert hashlib.sha256(json.dumps(sorted(doc["seqn"])).encode()).hexdigest()[:16] == doc["hash"], \
            "保留集檔案被改動——拒絕繼續"
        hold = set(doc["seqn"])
    else:
        rng = np.random.default_rng(seed + 4242)
        hold = set()
        for cls in (0, 1):                               # 依結果分層
            ids = seqn[y == cls]
            hold |= set(int(v) for v in rng.choice(ids, size=int(round(HOLDOUT_FRAC * len(ids))),
                                                   replace=False))
        hold = sorted(hold)
        json.dump(dict(note="最終模型專用保留集；開發階段永不觸碰",
                       caveat="1999–2018 已於本專案反覆分析，此非未曾窺視之測試集；"
                              "主要類化證據為留一週期外測",
                       frac=HOLDOUT_FRAC, seed=seed + 4242, seqn=hold,
                       hash=hashlib.sha256(json.dumps(sorted(hold)).encode()).hexdigest()[:16],
                       created=time.strftime("%Y-%m-%dT%H:%M:%S")),
                  open(hp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        hold = set(hold)
    te_mask = np.isin(seqn, list(hold))
    Xd, yd, Xt, yt = X[~te_mask], y[~te_mask], X[te_mask], y[te_mask]
    if verbose:
        print(f"[分割] 開發 {len(yd)}（陽性 {yd.sum()}）／保留 {len(yt)}（陽性 {yt.sum()}）")

    # ── 開發集上：巢狀 CV 取 OOF 機率 → 校準 → 選拒答帶
    if verbose:
        print("\n[訓練] 開發集 5×5 重複分層 CV → OOF 機率")
    acc, cnt = np.zeros(len(yd)), np.zeros(len(yd))
    for tr, va in RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=seed).split(Xd, yd):
        f, _ = _fit(Xd[tr], yd[tr], seed)
        acc[va] += f(Xd[va])
        cnt[va] += 1
    oof_raw = acc / np.maximum(cnt, 1)

    # 校準：內層 5 折上配適保序回歸，避免用同一筆資料既校準又評估
    if verbose:
        print("[校準] 保序回歸（內層 5 折，不用同一筆資料既校準又評估）")
    oof_cal = np.zeros(len(yd))
    for tr, va in StratifiedKFold(5, shuffle=True, random_state=seed).split(oof_raw.reshape(-1, 1), yd):
        iso = IsotonicRegression(out_of_bounds="clip").fit(oof_raw[tr], yd[tr])
        oof_cal[va] = iso.predict(oof_raw[va])

    t_low, t_high, band_info = pick_bands(oof_cal, yd)
    if verbose:
        print(f"[作業點] 拒答帶 [{t_low:.4f}, {t_high:.4f})　可行={band_info.get('feasible')}"
              f"　內層拒答率 {band_info.get('abstain_rate', 0):.1%}")

    dev_metrics = evaluate(yd, oof_cal, t_low, t_high)
    if verbose:
        print(f"[開發集] AUROC {dev_metrics['auroc_all']:.3f}｜校準後 Brier {dev_metrics['brier']:.4f}"
              f"｜拒答 {dev_metrics['abstain_rate']:.1%}"
              f"｜作答者敏感度 {dev_metrics.get('answered_sensitivity', float('nan')):.3f}"
              f"／特異度 {dev_metrics.get('answered_specificity', float('nan')):.3f}")

    # ── 全開發集重配適 → 可攜出參數；並在保留集上評一次
    predict, params = _fit(Xd, yd, seed)
    iso_full = IsotonicRegression(out_of_bounds="clip").fit(oof_raw, yd)
    p_te = iso_full.predict(predict(Xt))
    rng = np.random.default_rng(seed)
    boots = [roc_auc_score(yt[b], p_te[b]) for b in
             (rng.integers(0, len(yt), len(yt)) for _ in range(1000)) if 0 < yt[b].sum() < len(b)]
    ho = evaluate(yt, p_te, t_low, t_high)
    ho["auroc_ci"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    if verbose:
        print(f"\n[保留集｜一次性] AUROC {ho['auroc_all']:.3f} "
              f"[{ho['auroc_ci'][0]:.3f}, {ho['auroc_ci'][1]:.3f}]"
              f"｜AUPRC {ho['auprc_all']:.3f}（基準 {ho['auprc_baseline']:.4f}）")
        print(f"                拒答 {ho['abstain_rate']:.1%}"
              f"｜作答者敏感度 {ho.get('answered_sensitivity', float('nan')):.3f}"
              f"／特異度 {ho.get('answered_specificity', float('nan')):.3f}"
              f"｜PPV {ho.get('answered_ppv') if ho.get('answered_ppv') is None else round(ho['answered_ppv'], 3)}")

    # ── 事前判準判定（程式比對，不容事後詮釋）
    verdict = dict(
        sensitivity_ok=bool(ho.get("answered_sensitivity", 0) >= MIN_SENSITIVITY),
        abstain_ok=bool(ho["abstain_rate"] <= MAX_ABSTAIN),
        holdout_ci_ok=bool(ho["auroc_ci"][0] > MIN_HOLDOUT_CI_LOWER))
    verdict["all_met"] = bool(all(verdict.values()))

    # ── 係數（可讀性；標準化尺度）
    coefs = sorted(zip(ff, params["coef"]), key=lambda t: -abs(t[1]))[:15]

    out = dict(
        model="腎損傷者感染性病因分診（LR＋保序校準＋拒答帶）", seed=seed,
        created=time.strftime("%Y-%m-%dT%H:%M:%S"),
        cohort=dict(source="NHANES 1999–2018（10 週期，131 檔真實檔案）", n=int(len(y)),
                    n_pos=int(y.sum()), prevalence=float(y.mean()),
                    n_dev=int(len(yd)), n_holdout=int(len(yt))),
        features=ff, n_features=len(ff), label_adjacent_removed=sorted(adj),
        prereg=dict(min_sensitivity=MIN_SENSITIVITY, max_abstain=MAX_ABSTAIN,
                    min_holdout_ci_lower=MIN_HOLDOUT_CI_LOWER,
                    model_choice_reason="HGB 於本任務的優勢經證實為過擬合（見 TRAINING_SUMMARY §5.1）"),
        operating_point=dict(t_low=t_low, t_high=t_high, **band_info),
        development=dev_metrics, holdout=ho, verdict=verdict,
        top_coefficients=[dict(feature=f, coef_standardized=round(c, 4)) for f, c in coefs],
        portable_params=params,
        holdout_caveat="1999–2018 已於本專案反覆分析，此保留集非未曾窺視之測試集；"
                       "主要類化證據應以留一週期外測為準（binary_tasks_extended.json）",
        not_included=dict(
            免疫="不納入——AUROC 0.575，60 標記單標記掃描僅『性別』過 FDR（q=0.004），無生理訊號",
            代謝="不納入——0.816 但無增益價值，臨床上已知誰有糖尿病"),
        disclaimers=["標籤為血清學共病代理，非腎切片確診",
                     "輸出為『是否建議開立肝炎血清學』，非診斷",
                     "模型抓的是『此人可能有 B/C 肝』，不等於『肝炎導致腎損傷』",
                     "不構成臨床診斷工具"])
    PL._dump(out, "final_model.json")
    with open(os.path.join(RESULTS, "runs_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(kind="FINAL_MODEL", at=out["created"], **verdict,
                                holdout_auroc=ho["auroc_all"], holdout_ci=ho["auroc_ci"],
                                abstain=ho["abstain_rate"]), ensure_ascii=False) + "\n")
    if verbose:
        print("\n" + "═" * 70)
        for k, v in verdict.items():
            print(f"  {'✅' if v else '❌'}  {k}")
        print(f"\n事前判準整體：{'✅ 全數達成' if verdict['all_met'] else '❌ 未全數達成——照實報告，不調參'}")
        print("═" * 70)
        print("\n前 8 大係數（標準化尺度）：")
        for f_, c in coefs[:8]:
            print(f"  {f_:12s} {c:+.4f}")
        print("\n[完成] results/final_model.json（含可攜出參數，可於任何語言重建）")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260830)
    run(ap.parse_args().seed)
