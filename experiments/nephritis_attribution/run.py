# -*- coding: utf-8 -*-
"""單一入口。

  python run.py                   建 M0 洩漏基準 -> 跑五層管線 -> 跑六道閘門
  python run.py --curve           另跑 Lambda 誤設退化曲線
  python run.py --demo 3          印出 3 位病人的歸因說明（附為什麼）

選項：--seed 20260827 --n 4000 --target-npv 0.95

執行順序是硬性的：M0 一定先建、數字先寫進 results/m0.json，之後才允許看 M1。
"""
import argparse
import hashlib
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

import metrics as MT                                                  # noqa: E402
import pipeline as PL                                                 # noqa: E402
from attribution import PARAMS_DIR, fit_psi_offdiag, spec             # noqa: E402
from cohort import simulate, true_top_driver                          # noqa: E402
from m0 import build as build_m0                                      # noqa: E402

RESULTS = os.path.join(ROOT, "results")


def _default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _write(name, obj):
    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=_default)
    return p


def params_hash():
    h = hashlib.sha256()
    for n in ("loadings.json", "patterns.json", "deterministic.json"):
        h.update(open(os.path.join(PARAMS_DIR, n), "rb").read())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--target-npv", type=float, default=None)
    ap.add_argument("--curve", action="store_true")
    ap.add_argument("--demo", type=int, default=0)
    ap.add_argument("--casemix", choices=("referral", "primary"), default="referral")
    a = ap.parse_args()

    ind, Lam, drivers = spec()
    coh = simulate(a.seed, n=a.n, casemix=a.casemix)
    ok, qrep = PL.l1_quality(coh["raw"])

    # ---- 第一步（不可調換）：M0 洩漏基準 ----
    print("[1/4] M0 洩漏基準（L1 通過者）…")
    m0 = build_m0(coh, ok, seed=a.seed)
    m0["params_hash"] = params_hash()
    print(f"      M0 免疫二元 AUROC = {m0['immune_binary']['auroc']:.3f}"
          f" / 組織型態 macro AUROC = {m0['histologic_pattern']['macro_auroc']:.3f}")
    print(f"      洩漏訊號主要來自：{', '.join(k for k, _ in m0['importances'][:3])}")
    print("      -> " + _write(f"m0_{a.casemix}.json", m0))

    # ---- 第二步：五層管線 ----
    print("[2/4] 五層管線…")
    res = PL.run(coh, seed=a.seed, target_npv=a.target_npv)
    it = res["_internal"]
    m1_auc = float(roc_auc_score(it["yr"], it["oof"]))
    _, psi_rmse = fit_psi_offdiag(it["Xr"], Lam)
    print(f"      L1 棄權 {res['quality']['abstain_rate']:.1%}"
          f" / L2 硬分流 {res['l2']['routed_rate']:.1%}（正確率 {res['l2']['accuracy']:.1%}）")
    print(f"      L3 殘餘 n={res['l3']['n']}，AUROC {m1_auc:.3f}，"
          f"NPV {res['l3']['npv']:.3f} @ rule-out {res['l3']['ruleout_rate']:.1%}")
    print(f"      L4 平均驅動占比 " + ", ".join(
        f"{d.split('_')[0]} {v:.2f}" for d, v in zip(drivers, res["l4"]["mean_shares"])))
    print(f"      L5 混合旗標 {res['l5']['mixed']:.1%} / 間質疑似 {res['l5']['tin']:.1%}"
          f" / 血管炎優先 {res['l5']['vasculitis']:.1%}")

    # ---- 第三步：閘門 ----
    print("[3/4] 閘門…")
    m0_res = build_m0(coh, it["residual"], seed=a.seed)   # 與 M1 同分母才可比
    gates, _ = MT.run_gates(coh, res, m0_res["immune_binary"]["auroc"], ind, Lam,
                            true_top_driver(coh), seed=a.seed)
    for g in gates:
        print(f"      [{'PASS' if g['passed'] else 'FAIL'}] {g['gate']}: {g['value']}  ({g['criterion']})")
        if not g["passed"]:
            print(f"             未過代表：{g['fail_means']}")

    # ---- 第四步：彙總 ----
    safety = MT.safety(coh, res)
    shortlist = MT.shortlist_accuracy(coh, res)
    out = dict(seed=a.seed, n=a.n, casemix=a.casemix, params_hash=params_hash(),
               quality=qrep, l2=res["l2"], l3=dict(res["l3"], auroc=m1_auc),
               l4=dict(res["l4"], psi_offdiag_rmse=round(psi_rmse, 4)), l5=res["l5"],
               m0_same_denominator=m0_res["immune_binary"], safety=safety, shortlist=shortlist,
               gates=[{k: v for k, v in g.items()} for g in gates],
               all_gates_passed=all(g["passed"] for g in gates))
    if a.curve:
        print("[4/4] Lambda 誤設退化曲線…")
        out["misspecification_curve"] = MT.misspecification_curve(a.seed)
        for row in out["misspecification_curve"]:
            print(f"      [{row['mode']:9s}] 誤設 {row['misspec']:.2f} -> top1 {row['top1_accuracy']:.3f}"
                  f" / 非對角 RMSE {row['offdiag_rmse']:.3f}")
    print(f"      免疫＋時效性被 rule out（under-triage）：{safety['immune_time_critical_missed']}"
          f"/{safety['immune_time_critical_n']} = {safety['immune_time_critical_miss_rate']:.2%}")
    print(f"      TMA 完全無旗標離開系統：{safety['tma_without_any_flag']}/{safety['tma_n']}"
          f" = {safety['tma_unflagged_rate']:.2%}")
    print("      -> " + _write(f"results_{a.casemix}.json", out))

    if a.demo:
        print("\n— 歸因說明範例 —")
        for i in range(a.demo):
            e = PL.explain(coh, res, i)
            print(f"  病人 #{i}: rule-out={e['ruled_out']}  旗標={e['flags'] or '無'}")
            for name, share, contrib in e["ranking"]:
                why = ", ".join(f"{k}({v})" for k, v in contrib) or "無正貢獻指標"
                print(f"    {name} {share:.2f}  <- {why}")

    if not out["all_gates_passed"]:
        print("\n有閘門未通過：上面的效能數字在問題釐清前不得引用。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
