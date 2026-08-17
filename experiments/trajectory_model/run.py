# -*- coding: utf-8 -*-
"""單一入口：python run.py [--params params.json] [--out results] [--seeds 5] [--jobs 12] [--quick]

流程：載入參數檔（檢核出處）→ 逐變體校準（§1 delta_mu、§3 kappa、模組二係數）→
      (變體 × seed) 平行跑模組二～五 → 全部結果（不挑）寫 results.json → 五張圖。
格點（模組六）：窗長 4 × 去趨勢 3、分層 2 × 分群法 2、seed >= 5、tau 14/30/60、
      翻轉時程 3/6/12 個月（不可達則改掃 delta_mu 倍數並明說）、含退出的一組（僅模組四）。
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from cohort import (load_params, _val, make_cohort, calibrate_delta_mu, calibrate_kappa,
                    flip_timing_summary, derived_scale)
from risk import fit_risk_coefficients, risk_score, stratify
from clustering import run_clustering, generator_labels
from prediction import run_prediction, _auc
from warning import run_warning, rolling_indicators
import figures as FG


# ------------------------------------------------------------------ 單一 job
def cohort_summary(C):
    f, ev = C["is_flip"], C["event"]
    cls = C["cls"][~f]
    return dict(n=int(C["n"]), event_rate=float(ev.mean()), event_rate_linear=float(ev[~f].mean()),
                event_rate_flip=float(ev[f].mean()), flip_share=float(f.mean()),
                linear_class_shares=[float(v) for v in np.bincount(cls, minlength=3) / max(1, len(cls))],
                flip_timing=flip_timing_summary(C), scale=C["scale"], kappa=C["kappa"], delta_mu_median=C["delta_mu_median"])


def run_job(args):
    P, variant, seed, calib, want_fig = args
    t0 = time.time()
    C = make_cohort(P, seed, tau=variant["tau"], delta_mu_median=calib["delta_mu"]["delta_mu_median"],
                    kappa=calib["kappa"]["kappa"], dropout=variant.get("dropout", False))
    res = dict(variant=variant["name"], seed=int(seed), cohort=cohort_summary(C))
    if variant.get("dropout"):
        res["prediction"] = run_prediction(C, P, seed, dropout=True)
        res["seconds"] = time.time() - t0
        return res

    score = risk_score(C, calib["risk_coefs"])
    res["risk"] = dict(auc_of_score=_auc(C["event"], score))
    rng = np.random.default_rng(seed + 7)
    res["clustering"] = {}
    for q in P["risk_score"]["quantiles"]:
        strata = stratify(score, q)
        res["risk"][f"event_rate_by_q{q}"] = [float(C["event"][strata == s].mean()) for s in range(q)]
        for m in ("A", "B"):
            res["clustering"][f"q{q}_{m}"] = run_clustering(C, strata, m, P, rng)
    res["prediction"] = run_prediction(C, P, seed)
    res["warning"] = {}
    first_alarm_default = None
    for win in P["warning"]["windows_days"]:
        for mode in P["warning"]["detrend_modes"]:
            r = run_warning(C, P, win, mode, rng)
            fa = r.pop("_first_alarm")
            if win == P["warning"]["windows_days"][min(1, len(P["warning"]["windows_days"]) - 1)] and mode == "linear":
                first_alarm_default = (win, mode, fa)
            res["warning"][f"w{win}_{mode}"] = r
    if want_fig:
        res["fig"] = figure_data(C, P, res, first_alarm_default, score)
    else:
        for k in res["clustering"].values():
            for r in k:
                r.pop("mean_traj", None)
    res["seconds"] = time.time() - t0
    return res


def figure_data(C, P, res, fad, score):
    win, mode, first = fad
    te, tc, f = C["t_event"], C["t_crit"], C["is_flip"]
    cand = np.where(f & (te >= 0) & (tc > 200) & (first >= 0))[0]
    if len(cand) == 0:
        cand = np.where(f & (te >= 0) & (tc > 0))[0]
    i = int(cand[len(cand) // 2]) if len(cand) else int(np.where(f)[0][0])
    AR, SD = rolling_indicators(C["X"][i:i + 1], win, mode, P["warning"]["gaussian_bw_frac"]["value"])
    fig1 = dict(idx=i, x=C["X"][i].tolist(), ar1=AR[0].tolist(), sd=SD[0].tolist(), window=win, detrend=mode,
                t_crit=int(tc[i]), t_event=int(te[i]), first_alarm=int(first[i]), x_event=float(C["scale"]["x_event"]))
    q5 = stratify(score, 5)
    g = generator_labels(C)
    names = {0: "線性-緩慢", 1: "線性-進行", 2: "線性-加速", 10: "翻轉型"}
    gen_share = [{names[k]: float((g[q5 == s] == k).mean()) for k in names} for s in range(5)]
    ev = te >= 0
    fig5 = dict(flip_event=(te - first)[f & ev & (first >= 0) & (first <= te)].astype(float).tolist(),
                linear_event=(te - first)[~f & ev & (first >= 0) & (first <= te)].astype(float).tolist(),
                flip_crit=(tc - first)[f & (tc >= 0) & (first >= 0)].astype(float).tolist(),
                perm_p=res["warning"][f"w{win}_{mode}"]["perm_test_lead_flip_vs_linear"]["p"],
                perm_diff=res["warning"][f"w{win}_{mode}"]["perm_test_lead_flip_vs_linear"]["diff"])
    return dict(fig1=fig1, gen_share=gen_share, fig5=fig5, setting=f"w{win}_{mode}")


# ------------------------------------------------------------------ 聚合（不挑：全部 seed 的平均與範圍）
def aggregate(objs):
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    o0 = objs[0]
    if isinstance(o0, dict):
        return {k: aggregate([o.get(k) for o in objs]) for k in o0 if not str(k).startswith("_") and k != "mean_traj"}
    if isinstance(o0, list):
        if all(isinstance(o, list) and len(o) == len(o0) for o in objs) and o0 and not isinstance(o0[0], str):
            return [aggregate([o[i] for o in objs]) for i in range(len(o0))]
        return o0
    if isinstance(o0, (bool, np.bool_)):
        return dict(mean=float(np.mean([bool(o) for o in objs])), any=bool(any(objs)))
    if isinstance(o0, (int, float, np.integer, np.floating)):
        v = np.array([float(o) for o in objs if o is not None], float)
        v = v[np.isfinite(v)]
        if len(v) == 0:
            return dict(mean=np.nan, min=np.nan, max=np.nan, n=0)
        return dict(mean=float(v.mean()), min=float(v.min()), max=float(v.max()), n=int(len(v)))
    return o0


def _json_default(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if isinstance(o, np.ndarray): return o.tolist()
    if callable(o): return None
    return str(o)


# ------------------------------------------------------------------ 主程式
def build_variants(P, quick):
    fl = P["flip"]
    tau0 = _val(fl["tau_days"]); tgt0 = _val(fl["flip_time_target_days"])
    V = [dict(name="default", tau=tau0, target=tgt0)]
    if quick:
        return V
    for tau in fl["tau_grid_days"]:
        if tau != tau0:
            V.append(dict(name=f"tau{tau}", tau=tau, target=tgt0))
    for tgt in fl["flip_time_grid_days"]:
        if tgt != tgt0:
            V.append(dict(name=f"fliptime{tgt}", tau=tau0, target=tgt))
    V.append(dict(name="dropout", tau=tau0, target=tgt0, dropout=True))
    return V


def calibrate_variant(P, v, calib_cache):
    """§1 delta_mu → §3 kappa → 模組二係數（pilot 世代）。不可達的翻轉時程改為 delta_mu 倍數變體。"""
    key = (v["tau"], v["target"])
    if key in calib_cache:
        return calib_cache[key], v
    print(f"\n=== 校準變體 {v['name']}（tau={v['tau']}，翻轉時程目標 {v['target']} 天）===")
    dm = calibrate_delta_mu(P, tau=v["tau"], target_days=v["target"])
    if not dm["feasible"] and v["target"] != _val(P["flip"]["flip_time_target_days"]):
        # 目標不可達 → 這個變體改為掃描 delta_mu 倍數（決定書原則：錨不到就標假設並做敏感度）
        mult = min(P["flip"]["delta_mu_sensitivity_multipliers"], key=lambda m: abs(np.log(m) - np.log(0.5 if v["target"] < 180 else 2.0)))
        base = calib_cache[(v["tau"], _val(P["flip"]["flip_time_target_days"]))]["delta_mu"]["delta_mu_median"]
        dm["delta_mu_median"] = base * mult
        dm["derived_from"] = f"fallback_x{mult}"
        v = dict(v, name=f"dmu_x{mult}", note=f"翻轉時程 {v['target']} 天不可達，改為 delta_mu × {mult}")
        print(f"    → 改為變體 {v['name']}：delta_mu 中位 {dm['delta_mu_median']:.3f}")
    kp = calibrate_kappa(P, dm["delta_mu_median"], tau=v["tau"])
    pilot = make_cohort(P, P["sim"]["seed"] + 1000, n=1500, tau=v["tau"], delta_mu_median=dm["delta_mu_median"], kappa=kp["kappa"])
    coefs = P["risk_score"]["coefficients"]["value"] or fit_risk_coefficients(pilot)
    print(f"[模組二] 風險分數係數（pilot 配適）：{coefs}")
    calib = dict(delta_mu=dm, kappa=kp, risk_coefs=coefs, pilot_flip_timing=flip_timing_summary(pilot))
    calib_cache[key] = calib
    return calib, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"))
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--seeds", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--quick", action="store_true", help="小規模煙霧測試（n=400、1 seed、少量置換）")
    a = ap.parse_args()

    P = load_params(a.params)
    if a.n: P["sim"]["n"] = a.n
    if a.seeds: P["sim"]["n_seeds"] = a.seeds
    if a.quick:
        P["sim"].update(n=min(P["sim"]["n"], 400), n_seeds=1)
        P["clustering"].update(n_bootstrap=20, n_permutation=10)
        P["warning"].update(windows_days=[21], detrend_modes=["linear"], null_subjects=20, null_perms_per_subject=10,
                            n_permutation_leadtime=200)
        P["prediction"].update(landmarks_days=[180, 365, 730])
    os.makedirs(a.out, exist_ok=True)

    variants = build_variants(P, a.quick)
    seeds = [P["sim"]["seed"] + i for i in range(P["sim"]["n_seeds"])]
    cache, jobs, calibrations = {}, [], {}
    for v in variants:
        calib, v2 = calibrate_variant(P, v, cache)
        calibrations[v2["name"]] = dict(variant=v2, **calib)
        for i, s in enumerate(seeds):
            jobs.append((P, v2, s, calib, v2["name"] == "default" and i == 0))
    print(f"\n共 {len(jobs)} 個 job（{len(variants)} 變體 × {len(seeds)} seed），平行 {a.jobs} 程序 …")

    t0 = time.time()
    per = {}
    if a.jobs > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            for r in ex.map(run_job, jobs):
                per.setdefault(r["variant"], []).append(r)
                print(f"  完成 {r['variant']} seed={r['seed']}（{r['seconds']:.0f} s）")
    else:
        for j in jobs:
            r = run_job(j); per.setdefault(r["variant"], []).append(r)
            print(f"  完成 {r['variant']} seed={r['seed']}（{r['seconds']:.0f} s）")

    fig_res = next(r for r in per["default"] if "fig" in r)
    figdata = fig_res.pop("fig")
    agg = {v: aggregate([{k: x for k, x in r.items() if k != "fig"} for r in rs]) for v, rs in per.items()}

    # 洩漏警訊（建置提示詞 模組四）：任何地標動態 C 指數增益 > 門檻就大聲說
    leak = [(v, L, row["c_gain"]["mean"]) for v, A in agg.items() if "prediction" in A and A["prediction"] and "landmarks" in A["prediction"]
            for L, row in A["prediction"]["landmarks"].items() if row["c_gain"]["mean"] > P["prediction"]["leak_alert_c_gain"]["value"]]

    results = dict(meta=dict(date=time.strftime("%Y-%m-%d %H:%M"), seconds=time.time() - t0, quick=a.quick,
                             n=P["sim"]["n"], seeds=seeds, params_file=a.params),
                   provenance=P["_provenance"], params={k: v for k, v in P.items() if not k.startswith("_")},
                   calibration=calibrations, aggregate=agg, per_seed=per, leak_alert=leak,
                   figure_setting=figdata["setting"])
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=_json_default)

    figdir = os.path.join(a.out, "figures")
    d = per["default"][0]
    FG.fig1_single_case(figdata["fig1"], figdir)
    FG.fig2_strata_types(fig_res["clustering"]["q5_A"], figdata["gen_share"], figdir, title="預設變體 seed 0")
    FG.fig3_static_vs_dynamic(agg["default"]["prediction"], figdir)
    FG.fig4_timing_shift(fig_res["prediction"]["timing"], figdir)
    FG.fig5_leadtime(figdata["fig5"], figdir)

    print(f"\n完成，{time.time() - t0:.0f} s。結果：{a.out}/results.json、figures/")
    if leak:
        print("※ 洩漏警訊：以下 (變體, 地標) 的動態 C 指數增益 > 0.05，請檢查資料流再解讀：", leak)
    for v, A in agg.items():
        if "warning" not in A:
            continue
        pr = A["prediction"]["landmarks"]
        print(f"[{v}] 事件率 {A['cohort']['event_rate']['mean']:.2f}；靜態 C {A['prediction']['static']['auc']['mean']:.3f}；"
              + "；".join(f"L{L}: 靜態 {r['auc_static']['mean']:.3f} 動態 {r['auc_dynamic']['mean']:.3f} NRI(abs) {r['reclass_abs']['nri']['mean']:+.3f}" for L, r in pr.items()))
        for k, w in A["warning"].items():
            fl, li = w["by_type"]["flip"], w["by_type"]["linear"]
            print(f"    {k}: 提前期中位 翻轉 {fl['lead_to_event_days']['median']['mean']:.0f} / 爬升 {li['lead_to_event_days']['median']['mean']:.0f} 天，"
                  f"p={w['perm_test_lead_flip_vs_linear']['p']['mean']:.3f}；偽警報/人年 {fl['false_alarms_per_person_year']['mean']:.2f}/{li['false_alarms_per_person_year']['mean']:.2f}；"
                  f"基線 AR1 {w['baseline_ar1']['flip']['mean']:.2f}/{w['baseline_ar1']['linear']['mean']:.2f}")


if __name__ == "__main__":
    main()
