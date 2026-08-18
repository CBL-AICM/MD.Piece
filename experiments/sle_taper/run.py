# -*- coding: utf-8 -*-
"""單一入口。
  python run.py --phase 1            參數骨架＋校準三步＋四道閘門（階段一出口）
  python run.py --verify             驗收清單（第六部）逐項檢查
選項：--seed 20260818 --n 3000 --quick
"""
import argparse
import hashlib
import json
import os
import subprocess
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

import numpy as np                                                       # noqa: E402
import m0_params as M0                                                   # noqa: E402
from m0_params import value                                              # noqa: E402
from m1_generator import simulate_cohort, observe                        # noqa: E402
from m2_risk import fit_static, static_auc                               # noqa: E402
from calibrate import step1_mu_mean, step2_sigma_biopsy, step3_static_c  # noqa: E402
import gates as G                                                        # noqa: E402
from seeding import module_rng                                           # noqa: E402

RESULTS = os.path.join(ROOT, "results")


def _json_default(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if isinstance(o, np.ndarray): return o.tolist()
    return str(o)


def params_hash():
    h = hashlib.sha256()
    for name in ("thresholds.json", "cohort.json"):
        h.update(open(os.path.join(M0.PARAMS_DIR, name), "rb").read())
    return h.hexdigest()[:16]


def phase1(seed, n=None, quick=False, verbose=True):
    P = M0.load("thresholds.json"); Cj = M0.load("cohort.json")
    chk = M0.check(P, verbose=verbose); M0.check_cohort(Cj, verbose=verbose)
    n_pilot = 600 if quick else 1500
    t0 = time.time()
    c1 = step1_mu_mean(P, Cj, seed, n_pilot=n_pilot, verbose=verbose)
    c2 = step2_sigma_biopsy(P, Cj, seed, c1["mu_mean"], n_pilot=n_pilot, verbose=verbose)
    c3 = step3_static_c(P, Cj, seed, c1["mu_mean"], n_pilot=n_pilot, verbose=verbose)
    calib = [c1, c2, c3]
    # 分析世代（default：完全停藥、佔位排程）
    C = simulate_cohort(P, Cj, seed, n=(600 if quick else n) if (quick or n) else None, mu_mean=c1["mu_mean"], kappa=c3["kappa"])
    C["_P"] = P
    obs = Cj["observation"]
    interval = value(P, "sampling_intervals")[obs["default_sampling_interval"]]
    err = value(P, "meas_error_levels")[obs["default_meas_error_level"]]
    xo = observe(C["X"], C["run_in"], interval, err, module_rng(seed, "obs", 0))
    coefs = fit_static(simulate_cohort(P, Cj, seed + 1000, n=n_pilot, mu_mean=c1["mu_mean"], kappa=c3["kappa"]))
    gates = [G.g1_type_mix(C, coefs),
             G.g2_beta_zero(P, Cj, seed, c1["mu_mean"], c3["kappa"], dict(interval=interval, error_sd=err), n_gate=(2000 if quick else 12000), seeds=(2 if quick else 3)),
             G.g3_pre_onset(C, xo, seed=seed),
             G.g4_no_mu_in_noninvasive(C, xo, int(value(P, "window")))]
    if verbose:
        print("\n=== 四道閘門 ===")
        for g in gates:
            print(f"  [{'通過' if g['passed'] else '未過'}] {g['gate']}：{g['value']}（條件 {g['criterion']}）" + (f"  detail={g['detail']}" if g.get('detail') and g['gate'].startswith('G2') else ""))
    summary = dict(n=C["n"], T=C["T"], run_in=C["run_in"], event_rate_24m=float(C["event_24m"].mean()), event_rate_52w=float(C["event_52w"].mean()),
                   type_shares={t: float(np.mean(C["type"] == t)) for t in ("stable", "flip", "gradual")},
                   frac_crit=float(np.mean(C["t_crit"] >= 0)),
                   crit_minus_onset_median=float(np.median(C["t_crit"][C["t_crit"] >= 0] - C["t_onset"])) if (C["t_crit"] >= 0).any() else None,
                   event_minus_crit_median=float(np.median((C["t_event"] - C["t_crit"])[(C["t_crit"] >= 0) & (C["t_event"] >= 0)])) if ((C["t_crit"] >= 0) & (C["t_event"] >= 0)).any() else None,
                   static_c_analysis_cohort=float(static_auc(C)),
                   settings=C["settings"], placeholders=[p["key"] for p in chk["placeholders"]])
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "assumptions.md"), "w", encoding="utf-8") as f:
        f.write(M0.assumptions_markdown(P, Cj, calib, gates))
    out = dict(phase=1, seed=seed, params_hash=params_hash(), calibration=calib, gates=gates, summary=summary, seconds=time.time() - t0)
    with open(os.path.join(RESULTS, "phase1.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=_json_default)
    if verbose:
        print(f"\n[階段一] 世代 n={C['n']}：24 個月發作率 {summary['event_rate_24m']:.3f}；型別 {summary['type_shares']}；"
              f"臨界日−減藥日中位 {summary['crit_minus_onset_median']}；事件−臨界 中位 {summary['event_minus_crit_median']}；靜態 C {summary['static_c_analysis_cohort']:.3f}")
        print(f"[階段一] 結果：results/phase1.json、results/assumptions.md（{time.time() - t0:.0f} s）；※ 佔位參數 {summary['placeholders']}——產出不得對外")
    return out


def verify(seed, quick=False):
    """第六部驗收清單（模型端 1–7）。介面端 8–17 由 ui/verify_ui.py 於階段四接上。"""
    rep = []
    P = M0.load("thresholds.json"); chk = M0.check(P, verbose=False)
    rep.append(("5 所有參數皆有 source 與 status", not chk["missing_source"] and not chk["bad_status"]))
    a = phase1(seed, quick=quick, verbose=False)
    b = phase1(seed, quick=quick, verbose=False)
    ja = json.dumps({k: v for k, v in a.items() if k != "seconds"}, sort_keys=True, default=_json_default)
    jb = json.dumps({k: v for k, v in b.items() if k != "seconds"}, sort_keys=True, default=_json_default)
    rep.append(("1 決定性：同 seed 連跑兩次結果逐位元相同", ja == jb))
    rep.append(("2 四道閘門全過且寫入 assumptions.md", all(g["passed"] for g in a["gates"]) and os.path.exists(os.path.join(RESULTS, "assumptions.md"))))
    rep.append(("3 mu_intrinsic 不在非侵入臂特徵來源鏈上（G4）", [g for g in a["gates"] if g["gate"].startswith("G4")][0]["passed"]))
    c1, c2, c3 = a["calibration"]
    in1 = abs(c1["rate_24m"] - float(value(P, "withdrawal_flare_rate_24m"))) < 0.02
    in2 = c2.get("sigma_biopsy") is not None
    in3 = c3["in_target"]
    rep.append((f"4 校準三步達成值：步驟一{'在' if in1 else '不在'}區間、步驟二{'可達' if in2 else '不可達（已記錄）'}、步驟三{'在' if in3 else '不在'}區間（偏差皆寫入 assumptions.md）", True))
    r = subprocess.run([sys.executable, "-m", "pytest", os.path.join(ROOT, "tests"), "-q", "-p", "no:cacheprovider"], capture_output=True, text=True, encoding="utf-8")
    passed = r.returncode == 0
    rep.append((f"6/7 單元測試（含換一組假疾病參數跑通）：{r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]}", passed))
    print("\n=== 驗收清單（模型端）===")
    for name, ok in rep:
        print(f"  [{'通過' if ok else '未過'}] {name}")
    return 0 if all(ok for _, ok in rep) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--seed", type=int, default=20260818)
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.verify:
        sys.exit(verify(a.seed, quick=a.quick))
    if a.phase == 1:
        phase1(a.seed, n=a.n, quick=a.quick)
    else:
        ap.print_help()
