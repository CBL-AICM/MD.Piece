# -*- coding: utf-8 -*-
"""公式 1–6 的可用性評估。不做主觀判斷，每一條都給一個數字。

  python run_formulas.py [--casemix referral|primary] [--n 6000] [--seed 20260827]

比較一律在同一個殘餘子集、同一組安全否決、同一個門檻規則下進行，
只換 L3 的特徵集 —— 否則比出來的差異可能來自別的地方。
輸出 results/formula_eval_<casemix>.json。
"""
import argparse
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

import numpy as np                                                    # noqa: E402
from sklearn.metrics import roc_auc_score                             # noqa: E402

import deterministic as DET                                           # noqa: E402
import longitudinal as LG                                             # noqa: E402
import multiclass as MC                                               # noqa: E402
import pipeline as PL                                                 # noqa: E402
from attribution import load, pattern_shortlist, spec, transform_raw   # noqa: E402
from cohort import LEAKY, simulate                                    # noqa: E402


def l3_variant(F, y, veto, crit, cap, npv_target, seed):
    """同一套規則下，換一組特徵重跑 L3。"""
    _, thr, oof = PL.fit_l3(F, y, npv_target, seed=seed, veto=veto, y_critical=crit, crit_cap=cap)
    auc = float(roc_auc_score(y, oof))
    if thr is None:
        return dict(auroc=round(auc, 4), threshold=None, ruleout_rate=0.0, npv=None,
                    note="在此特徵集下找不到同時滿足 NPV 與漏判上限的門檻")
    neg = (oof < thr) & ~veto
    return dict(auroc=round(auc, 4), threshold=round(float(thr), 4),
                ruleout_rate=round(float(neg.mean()), 4),
                npv=round(float((y[neg] == 0).mean()), 4) if neg.sum() else None,
                time_critical_miss=round(float((neg & crit).sum() / max(1, crit.sum())), 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casemix", choices=("referral", "primary"), default="referral")
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=20260827)
    a = ap.parse_args()

    ind, Lam, drivers = spec()
    R, P = DET.rules(), load("patterns.json")
    npv_target = R["npv_targets"]["immune_gn_ruleout"]
    cap = R["npv_targets"]["time_critical_miss_cap"]

    coh = simulate(a.seed, n=a.n, casemix=a.casemix)
    base = PL.run(coh, seed=a.seed)
    it = base["_internal"]
    res = it["residual"]
    Xn, y = it["Xr"], it["yr"]
    veto, crit = it["veto"], (coh["time_critical"] & coh["immune_gn"])[res]
    y_pat = coh["label"][res]
    sub = {k: v[res] for k, v in (("prior_X", coh["prior_X"].transpose(1, 0, 2)),)}
    cohR = dict(prior_X=sub["prior_X"].transpose(1, 0, 2), future_X=coh["future_X"][res])
    out = dict(casemix=a.casemix, n=a.n, seed=a.seed, n_residual=int(res.sum()),
               prevalence=round(float(y.mean()), 4))

    print(f"=== 公式評估（{a.casemix}，殘餘子集 n={int(res.sum())}，盛行率 {y.mean():.3f}）===\n")

    # ---------- 公式 1–2：Δ 與 slope 有沒有加值 ----------
    print("[公式 1–2] 變化量 ΔX 與變化率 Slope —— 加進 L3 有沒有用")
    variants = {}
    for kind in ("base", "delta", "slope", "both", "blup"):
        F, _ = LG.build(cohR, Xn, kind)
        variants[kind] = l3_variant(F, y, veto, crit, cap, npv_target, a.seed)
        v = variants[kind]
        print(f"      {kind:6s} 特徵 {F.shape[1]:3d}  AUROC {v['auroc']:.4f}"
              f"  rule-out {v['ruleout_rate']:.1%}  NPV {v['npv']}")
    out["longitudinal_variants"] = variants

    # ---------- 公式 3：LMM 收縮到底有沒有動到斜率 ----------
    series, times = LG.panels(dict(cohR, _X_now=Xn))
    b, shrink = LG.blup_slope(series, times)
    s_simple = LG.slope(series, times)
    corr = float(np.corrcoef(b.ravel(), s_simple.ravel())[0, 1])
    out["formula3_shrinkage"] = dict(
        mean_shrink=round(float(shrink.mean()), 4), min_shrink=round(float(shrink.min()), 4),
        max_shrink=round(float(shrink.max()), 4),
        corr_blup_vs_simple_slope=round(corr, 4),
        auroc_gain_over_simple=round(variants["blup"]["auroc"] - variants["slope"]["auroc"], 4))
    # 收縮係數 = tau^2/(tau^2 + sigma^2/Stt)。Stt 隨追蹤點數與跨度增加，
    # 因此可以反推「要讓 LMM 的個人斜率真的可用，追蹤設計最少要長成什麼樣」。
    stt_now = float(((times - times.mean()) ** 2).sum())
    kfac = shrink.mean() / max(1e-9, 1 - shrink.mean())
    need = {}
    for target in (0.5, 0.8):
        need_stt = stt_now * (target / (1 - target)) / max(kfac, 1e-9)
        best = None
        for T in range(3, 13):
            for span in range(12, 241, 6):
                t = np.linspace(-span, 0, T)
                if ((t - t.mean()) ** 2).sum() >= need_stt:
                    if best is None or T * span < best[0] * best[1]:
                        best = (T, span)
        need[str(target)] = dict(required_stt=round(need_stt, 1),
                                 min_design=None if best is None else "%d 個時間點 / 跨度 %d 週" % best)
    out["formula3_design_requirement"] = dict(current_stt=stt_now,
                                              current_shrink=round(float(shrink.mean()), 4), to_reach=need)
    print(f"\n[公式 3] LMM 隨機斜率 BLUP：平均收縮係數 {shrink.mean():.3f}"
          f"（1=完全不動簡單斜率，0=全收縮到族群平均）")
    print(f"      BLUP 與簡單斜率相關係數 r={corr:.4f}，"
          f"AUROC 差 {variants['blup']['auroc'] - variants['slope']['auroc']:+.4f}")
    for tgt, d in need.items():
        print(f"      要讓收縮係數達到 {tgt}：{d['min_design'] or '本設計範圍內達不到'}")

    # ---------- 時間視窗洩漏 ----------
    F_h, F_l = LG.leak_demo(cohR, Xn)
    hon = l3_variant(F_h, y, veto, crit, cap, npv_target, a.seed)
    lea = l3_variant(F_l, y, veto, crit, cap, npv_target, a.seed)
    out["time_window_leak"] = dict(honest=hon, leaky=lea,
                                   auroc_inflation=round(lea["auroc"] - hon["auroc"], 4))
    print(f"\n[時間視窗] t2 只取決策點以前 AUROC {hon['auroc']:.4f}"
          f"　／　t2 誤取到決策點之後 AUROC {lea['auroc']:.4f}"
          f"　→ 洩漏膨脹 {lea['auroc'] - hon['auroc']:+.4f}")

    # ---------- 公式 4–5：多類別 softmax ----------
    print("\n[公式 4–5] 多類別 softmax（8 種組織型態）")
    best_kind = max(variants, key=lambda k: variants[k]["auroc"])
    F_best, _ = LG.build(cohR, Xn, best_kind)
    mc_base, p_base = MC.evaluate(Xn, y_pat, None, seed=a.seed)
    mc_best, p_best = MC.evaluate(F_best, y_pat, None, seed=a.seed)
    prof = np.array([p["driver_mean"] for p in P["patterns"]])
    order, _ = pattern_shortlist(it["sh"], prof, k=3)
    cos = dict(top1=float((order[:, 0] == y_pat).mean()),
               top3=float(np.mean([t in o for t, o in zip(y_pat, order)])))
    out["multiclass"] = dict(routine_only=mc_base, with_longitudinal=mc_best,
                             best_feature_set=best_kind, cosine_shortlist=cos)
    print(f"      softmax（常規）      top-1 {mc_base['top1']:.3f}  top-3 {mc_base['top3']:.3f}"
          f"  macroAUC {mc_base['macro_auroc']:.3f}  校準誤差 {mc_base['ece']:.3f}")
    print(f"      softmax（＋縱向）    top-1 {mc_best['top1']:.3f}  top-3 {mc_best['top3']:.3f}"
          f"  macroAUC {mc_best['macro_auroc']:.3f}  校準誤差 {mc_best['ece']:.3f}")
    print(f"      現行餘弦候選清單     top-1 {cos['top1']:.3f}  top-3 {cos['top3']:.3f}")

    # ---------- 二元：直接訓練 vs 由 softmax 加總 ----------
    imm = np.array([p["immune_gn"] for p in P["patterns"]])
    p_bin = MC.binary_from_softmax(p_best, imm)
    thr = PL._npv_threshold(p_bin, y, npv_target, veto=veto, y_critical=crit, crit_cap=cap)
    neg = (p_bin < thr) & ~veto if thr is not None else np.zeros_like(y, dtype=bool)
    soft_bin = dict(auroc=round(float(roc_auc_score(y, p_bin)), 4),
                    threshold=None if thr is None else round(float(thr), 4),
                    ruleout_rate=round(float(neg.mean()), 4),
                    npv=round(float((y[neg] == 0).mean()), 4) if neg.sum() else None)
    out["binary_direct_vs_softmax"] = dict(direct=variants[best_kind], via_softmax=soft_bin)
    print(f"\n      二元 rule-out：直接訓練 AUROC {variants[best_kind]['auroc']:.4f}"
          f" / 覆蓋 {variants[best_kind]['ruleout_rate']:.1%}")
    print(f"                    　由 softmax 加總 AUROC {soft_bin['auroc']:.4f}"
          f" / 覆蓋 {soft_bin['ruleout_rate']:.1%}")

    # ---------- 公式 6：循環性 ----------
    print("\n[公式 6] 把「病理特徵」放進預測變項（逐字實作）")
    path_idx = [LEAKY.index(k) for k in ("if_deposit_intensity", "crescent_pct")]
    X_path = np.column_stack([coh["leaky"][LEAKY[i]][res] for i in path_idx])
    circ = MC.circularity_demo(F_best, X_path, y_pat, seed=a.seed)
    out["formula6_circularity"] = circ
    print(f"      只用常規          top-1 {circ['routine_only']['top1']:.3f}"
          f"  macroAUC {circ['routine_only']['macro_auroc']:.3f}")
    print(f"      ＋病理特徵        top-1 {circ['with_pathology']['top1']:.3f}"
          f"  macroAUC {circ['with_pathology']['macro_auroc']:.3f}"
          f"　→ 增益 {circ['top1_gain']:+.3f}")

    # ---------- 自體抗體：進模型 vs 留在 L2 ----------
    from cohort import MARKERS
    Xab = np.hstack([F_best, np.column_stack(
        [coh["markers"][m][res] * coh["markers"][m + "_available"][res] for m in MARKERS])])
    ab = l3_variant(Xab, y, veto, crit, cap, npv_target, a.seed)
    out["autoantibodies_in_model"] = dict(l2_only=variants[best_kind], as_features=ab,
                                          auroc_gain=round(ab["auroc"] - variants[best_kind]["auroc"], 4))
    print(f"\n[自體抗體組合] 留在 L2 硬分流 AUROC {variants[best_kind]['auroc']:.4f}"
          f"　／　放進模型當特徵 AUROC {ab['auroc']:.4f}"
          f"　→ 增益 {ab['auroc'] - variants[best_kind]['auroc']:+.4f}（代價：零新增檢驗不再成立）")

    p = os.path.join(ROOT, "results", f"formula_eval_{a.casemix}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n-> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
