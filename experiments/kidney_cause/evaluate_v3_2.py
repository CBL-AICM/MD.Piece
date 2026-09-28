# -*- coding: utf-8 -*-
"""v3.2 內部評估——完全依 params/v3_2_plan.json（計畫先提交 f6abc91，之後才寫本程式與執行）。
    python evaluate_v3_2.py audit   → results/v3_2_cohort_audit.json（資料修正的影響，數十秒）
    python evaluate_v3_2.py         → 上列＋results/v3_2_eval.json、results/v3_2_oof.csv.gz

候選模型全部採部署工具結構（外層訓練資料內 5 折交叉配適 → 平均 → 內層折外分數配適保序校準），
在與 v3 相同規則的外層切分（分層 5 折 × 5 次，seed 20260926）上比較。v3 結果檔不修改。"""
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np                                                    # noqa: E402
import pandas as pd                                                   # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score   # noqa: E402
from sklearn.model_selection import StratifiedKFold                   # noqa: E402

import design_variance as dv                                          # noqa: E402
from evaluate_v3 import (AXES, BASIC, FOLDS, REPEATS, SEED, band_stats, bands, boot, calib, curve, dca,  # noqa: E402
                         fit_tool, hgb, lr, tool_predict)
from nhanes_cohort import build_v3                                    # noqa: E402

PLAN = os.path.join(ROOT, "params", "v3_2_plan.json")
OUT_AUDIT = os.path.join(ROOT, "results", "v3_2_cohort_audit.json")
OUT = os.path.join(ROOT, "results", "v3_2_eval.json")
OOF = os.path.join(ROOT, "results", "v3_2_oof.csv.gz")
N_JOBS = min(8, os.cpu_count() or 1)
MODELS = {"LR_routine": ("routine", lr), "LR_routine_noHDL": ("routine_noHDL", lr), "HGB_routine": ("routine", hgb),
          "LR_full": ("full", lr), "HGB_full": ("full", hgb)}
PAIRS = [("HGB_routine", "LR_routine"), ("LR_routine", "LR_full"), ("LR_routine", "LR_routine_noHDL")]
MAIN = ("LR_routine", "HGB_routine")
BRIDGED = ["LBXSAL", "LBXSAPSI", "LBXSASSI", "LBXSATSI", "LBXSBU", "LBXSCH", "LBXSCR", "LBXSGTSI", "LBXSIR",
           "LBXSLDSI", "LBXSTR", "LBXSUA", "LBXSGB", "LBXSOSSI"]
FASTING = ("LBXTR", "LBDLDL")      # 只在早上空腹子樣本測量
GRIDS = {"肝炎": np.round(np.arange(0.005, 0.1001, 0.005), 4), "糖尿病": np.round(np.arange(0.10, 0.6001, 0.05), 3)}


def sets_for(feats, spec):
    full = [f for f in feats if f not in spec["adjacent"]]
    routine = [f for f in BASIC if f in full]
    return dict(full=full, routine=routine, routine_noHDL=[f for f in routine if f != "LBDHDL"], demo=["age", "sex"])


def counts(s):
    return dict(pos=int((s == 1).sum()), neg=int((s == 0).sum()), unknown=int(s.isna().sum()))


def audit(V0, V):
    """資料修正的影響：逐週期標籤、特徵有值比例、2017–2018 換算前後中位數。常規套組有缺週期即中止。"""
    A0, A, kd = V0["adults"], V["adults"], V["cohort"]
    per_cycle = {}
    for c in sorted(A["cycle"].unique()):
        a0, a = A0[A0.cycle == c], A[A.cycle == c]
        k0, k = a0[a0.kidney3 == 1], a[a.kidney3 == 1]
        per_cycle[c] = dict(adults=int(len(a)), kidney_v3=counts(a0.kidney3), kidney_v3_2=counts(a.kidney3),
                            hep_v3_2=counts(k.hep3), dm_v3_2=counts(k.dm3), hep_v3=counts(k0.hep3), dm_v3=counts(k0.dm3))
    j = A[A.cycle == "2017-2018"]
    change = pd.crosstab(j["kidney3_rep"].fillna(-1), j["kidney3"].fillna(-1))
    avail = kd.groupby("cycle")[V["features"]].apply(lambda g: g.notna().mean()).round(4)
    routine = [f for f in BASIC if f in V["features"]]
    gaps = {f: avail[f][avail[f] < 0.9].to_dict() for f in routine if f not in FASTING and (avail[f] < 0.9).any()}
    assert not gaps, f"常規套組仍有週期缺值：{gaps}"
    med = lambda X, c: X.loc[X.cycle == c, BRIDGED].median()
    bridged = pd.DataFrame({"2015-2016": med(A0, "2015-2016"), "2017-2018_reported": med(A0, "2017-2018"),
                            "2017-2018_DxC": med(A, "2017-2018")}).round(4)
    return dict(plan_sha256=hashlib.sha256(open(PLAN, "rb").read()).hexdigest(),
                n_adults=int(len(A)), kidney=dict(v3=counts(A0.kidney3), v3_2=counts(A.kidney3)),
                features=dict(v3=len(V0["features"]), v3_2=len(V["features"]),
                              added=sorted(set(V["features"]) - set(V0["features"]))),
                kidney_2017_2018_reported_vs_DxC={f"{int(r)}→{int(c)}": int(change.loc[r, c]) for r in change.index
                                                  for c in change.columns if change.loc[r, c] and r != c},
                per_cycle=per_cycle, feature_availability_in_kidney=avail.to_dict(),
                routine_gaps=gaps, bridged_medians_adults=bridged.to_dict())


def one_fold(X, y, sets, models, fold_key, tr, te):
    out = {}
    for name, (fs, make) in models.items():
        T = fit_tool(X[tr][:, sets[fs]], y[tr], make=make)
        raw, cal = tool_predict(T, X[te][:, sets[fs]])
        out[name] = (raw, cal, bands(cal, T["prev"], "B"))
    return fold_key, te, out


def nested(X, y, sets, models, repeats=REPEATS):
    jobs = [((r, f), tr, te) for r in range(repeats)
            for f, (tr, te) in enumerate(StratifiedKFold(FOLDS, shuffle=True, random_state=SEED + r).split(X, y))]
    with ProcessPoolExecutor(N_JOBS) as ex:     # ponytail: 標準函式庫；joblib 在 Python 3.14 的 ast.Num 會壞
        res = list(ex.map(one_fold, *zip(*[(X, y, sets, models, *j) for j in jobs])))
    P = {m: {k: np.full((repeats, len(y)), np.nan) for k in ("raw", "cal", "band")} for m in models}
    for (r, _), te, out in res:
        for m, (raw, cal, band) in out.items():
            P[m]["raw"][r, te], P[m]["cal"][r, te], P[m]["band"][r, te] = raw, cal, band
    for m in P:
        assert not np.isnan(P[m]["cal"]).any(), f"{m} 有人沒有外層預測"
    return P


def demographics(X, y, sets):
    """→ (摘要, 第 0 次重複之外層預測)；切分與候選模型相同，可做配對比較。"""
    out, p0 = [], None
    for r in range(REPEATS):
        p = np.zeros(len(y))
        for tr, te in StratifiedKFold(FOLDS, shuffle=True, random_state=SEED + r).split(X, y):
            p[te] = lr(SEED).fit(X[tr][:, sets["demo"]], y[tr]).predict_proba(X[te][:, sets["demo"]])[:, 1]
        out.append((roc_auc_score(y, p), average_precision_score(y, p)))
        p0 = p if r == 0 else p0
    a = np.array(out)
    return dict(auroc_mean=float(a[:, 0].mean()), auroc_range=[float(a[:, 0].min()), float(a[:, 0].max())],
                ap_mean=float(a[:, 1].mean()), ap_range=[float(a[:, 1].min()), float(a[:, 1].max())]), p0


def paired_auroc(y, a, b):
    """a − b 之 ΔAUROC（同一批受試者）；年齡性別模型用 class_weight 未校準，故只比排序。"""
    f = dict(d_auroc=lambda i: roc_auc_score(y[i], a[i]) - roc_auc_score(y[i], b[i]))
    return dict(d_auroc=float(f["d_auroc"](np.arange(len(y)))), ci95=boot(y, f))


def tool_bands(y, b, insufficient):
    """網頁工具實際輸出：常規套組有值 <50% 為「資料不足」、不給方向。涵蓋率分母為全部受試者；
    「只略過不傾向區」時，資料不足者照常送驗。（bands_B_repeat0 則把分區規則套在每個人身上。）"""
    t = np.where(insufficient, -1, b)
    low_pos = int(((t == 0) & (y == 1)).sum())
    return dict(band={k: dict(n=int((t == v).sum()), n_pos=int(((t == v) & (y == 1)).sum()),
                              observed_rate=float(y[t == v].mean()) if (t == v).any() else None)
                      for k, v in (("傾向", 2), ("不確定", 1), ("不傾向", 0), ("資料不足", -1))},
                coverage=float(np.isin(t, (0, 2)).mean()),
                per_1000_if_skip_low=dict(tested=1000 * float((t != 0).mean()), missed=1000 * low_pos / len(y),
                                          missed_share_of_pos=low_pos / max(int(y.sum()), 1)))


def summarize(y, M, insufficient):
    per = pd.DataFrame([dict(auroc=roc_auc_score(y, M["cal"][r]), auroc_raw=roc_auc_score(y, M["raw"][r]),
                             ap=average_precision_score(y, M["cal"][r]), coverage=float((M["band"][r] != 1).mean()),
                             **{f"cal_{k}": v for k, v in calib(y, M["cal"][r]).items()}) for r in range(M["cal"].shape[0])])
    c0, b0 = M["cal"][0], M["band"][0]
    ci = boot(y, dict(auroc=lambda i: roc_auc_score(y[i], c0[i]), ap=lambda i: average_precision_score(y[i], c0[i]),
                      brier=lambda i: float(np.mean((c0[i] - y[i]) ** 2))))
    return dict(repeats=dict(mean=per.mean().to_dict(), min=per.min().to_dict(), max=per.max().to_dict()),
                ci95_repeat0=ci, calibration_repeat0=calib(y, c0), calibration_curve_repeat0=curve(y, c0),
                bands_B_repeat0=band_stats(y, b0), insufficient_data_n=int(insufficient.sum()),
                bands_B_excluding_insufficient=band_stats(y[~insufficient], b0[~insufficient]),
                bands_tool_repeat0=tool_bands(y, b0, insufficient))


def paired(y, a, b):
    """a − b，第 0 次重複同一批受試者。"""
    f = dict(d_auroc=lambda i: roc_auc_score(y[i], a[i]) - roc_auc_score(y[i], b[i]),
             d_ap=lambda i: average_precision_score(y[i], a[i]) - average_precision_score(y[i], b[i]),
             d_brier=lambda i: float(np.mean((a[i] - y[i]) ** 2) - np.mean((b[i] - y[i]) ** 2)))
    idx = np.arange(len(y))
    return dict(**{k: float(fn(idx)) for k, fn in f.items()}, ci95=boot(y, f))


def temporal(d, X, y, sets):
    cyc = d["cycle"].to_numpy()
    early = np.isin(cyc, sorted(set(cyc))[:5])
    out = {}
    for name in MAIN:
        fs, make = MODELS[name]
        T = fit_tool(X[early][:, sets[fs]], y[early], make=make)
        _, cal = tool_predict(T, X[~early][:, sets[fs]])
        yy = y[~early]
        out[name] = dict(n=int(len(yy)), n_pos=int(yy.sum()), prevalence_train=T["prev"], prevalence_test=float(yy.mean()),
                         mean_pred=float(cal.mean()), auroc=float(roc_auc_score(yy, cal)),
                         ap=float(average_precision_score(yy, cal)), ci95=boot(yy, dict(auroc=lambda i: roc_auc_score(yy[i], cal[i]))),
                         calibration=calib(yy, cal), bands_B=band_stats(yy, bands(cal, T["prev"], "B")))
    return out


def subtypes(d, y, cal, band, insufficient):
    """肝炎軸：C 型、B 型陽性各自對全部陰性者之 AUROC 與三區分布（合併感染兩邊都算，另列人數）。
    bands 把分區規則套在每個人身上；bands_tool 依工具規則另列「資料不足」。"""
    hbv, hcv, neg = (d["hbv3"] == 1).to_numpy(), (d["hcv3"] == 1).to_numpy(), y == 0
    tb = np.where(insufficient, -1, band)
    out = dict(coinfected=int((hbv & hcv).sum()))
    for k, m in (("C型_HCV_RNA", hcv), ("B型_HBsAg", hbv)):
        pos = m & (y == 1)
        yy = np.r_[np.ones(pos.sum()), np.zeros(neg.sum())]
        pp = np.r_[cal[pos], cal[neg]]
        out[k] = dict(n_pos=int(pos.sum()), auroc=float(roc_auc_score(yy, pp)),
                      ci95=boot(yy, dict(auroc=lambda i: roc_auc_score(yy[i], pp[i]))),
                      bands={n: int((band[pos] == v).sum()) for n, v in (("傾向", 2), ("不確定", 1), ("不傾向", 0))},
                      bands_tool={n: int((tb[pos] == v).sum()) for n, v in (("傾向", 2), ("不確定", 1), ("不傾向", 0), ("資料不足", -1))})
    return out


def single(kd, feats, spec, label):
    d = kd[kd[label].notna()].reset_index(drop=True)
    s = sets_for(feats, spec)
    X, y = d[s["full"]].to_numpy(float), d[label].to_numpy(int)
    sets = {k: [s["full"].index(f) for f in v] for k, v in s.items()}
    M = nested(X, y, sets, {"LR_routine": MODELS["LR_routine"]}, repeats=1)["LR_routine"]
    return dict(n=int(len(y)), n_pos=int(y.sum()), prevalence=float(y.mean()), auroc=float(roc_auc_score(y, M["cal"][0])),
                ap=float(average_precision_score(y, M["cal"][0])), calibration=calib(y, M["cal"][0]))


def run_axis(name, spec, kd, feats, adults, design):
    d = kd[kd[spec["label"]].notna()].reset_index(drop=True)
    s = sets_for(feats, spec)
    X, y = d[s["full"]].to_numpy(float), d[spec["label"]].to_numpy(int)
    sets = {k: [s["full"].index(f) for f in v] for k, v in s.items()}
    t0 = time.time()
    P = nested(X, y, sets, MODELS)
    insufficient = d[s["routine"]].notna().mean(axis=1).to_numpy() < 0.5
    m1, p_m1 = demographics(X, y, sets)
    a = dict(label=spec["label"], n=int(len(y)), n_pos=int(y.sum()), prevalence=float(y.mean()),
             features=s["full"], routine_panel=s["routine"], models={m: summarize(y, P[m], insufficient) for m in MODELS},
             M1_demographics=m1,
             paired_repeat0={f"{a_}−{b_}": paired(y, P[a_]["cal"][0], P[b_]["cal"][0]) for a_, b_ in PAIRS},
             paired_vs_demographics_repeat0={f"{m}−M1_demographics": paired_auroc(y, P[m]["cal"][0], p_m1) for m in MAIN},
             temporal=temporal(d, X, y, sets),
             decision_curve={m: dca(pd.DataFrame(dict(repeat=0, y=y, cal=P[m]["cal"][0])), GRIDS[name]) for m in MAIN})
    w = d["w_mec20"].to_numpy(float)
    h, j = d["SDMVSTRA"].to_numpy(int), d["SDMVPSU"].to_numpy(int)
    a["design_weighted"] = {m: dv.analyse(y.astype(float), P[m]["cal"][0], w, h, j, design) for m in MAIN}
    if name == "肝炎":
        a["subtypes_LR_routine"] = subtypes(d, y, P["LR_routine"]["cal"][0], P["LR_routine"]["band"][0], insufficient)
        a["single_label_LR_routine"] = {k: single(kd, feats, spec, lab) for k, lab in (("僅B型_HBsAg", "hbv3"), ("僅C型_HCV_RNA", "hcv3"))}
    rep = adults[adults["kidney3_rep"] == 1]
    dr = rep[rep[spec["label"]].notna()].reset_index(drop=True)
    Xr, yr = dr[s["full"]].to_numpy(float), dr[spec["label"]].to_numpy(int)
    Pr = nested(Xr, yr, sets, {m: MODELS[m] for m in MAIN}, repeats=1)
    a["kidney_label_as_reported"] = dict(n=int(len(yr)), n_pos=int(yr.sum()), **{
        m: dict(auroc=float(roc_auc_score(yr, Pr[m]["cal"][0])), ap=float(average_precision_score(yr, Pr[m]["cal"][0])),
                calibration=calib(yr, Pr[m]["cal"][0])) for m in MAIN})
    oof = pd.concat([pd.DataFrame(dict(axis=name, model=m, repeat=r, SEQN=d["SEQN"].astype(int), cycle=d["cycle"], y=y,
                                       cal=P[m]["cal"][r], band=P[m]["band"][r].astype(int)))
                     for m in MODELS for r in range(REPEATS)], ignore_index=True)
    return a, oof, time.time() - t0


def main(only_audit=False):
    t0 = time.time()
    P0 = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V0, V = build_v3(P0, verbose=False), build_v3(P0, verbose=False, fixes=True)
    au = audit(V0, V)
    json.dump(au, open(OUT_AUDIT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[稽核] 腎臟 v3 {au['kidney']['v3']} → v3.2 {au['kidney']['v3_2']}｜2017–2018 標籤改變 {au['kidney_2017_2018_reported_vs_DxC']}"
          f"｜特徵 {au['features']['v3']}→{au['features']['v3_2']}（新增 {au['features']['added']}）｜常規套組缺週期：無")
    if only_audit:
        return
    kd, feats, adults = V["cohort"], V["features"], V["adults"]
    design = dv.design_of(adults)
    out = dict(created=pd.Timestamp.now().isoformat(timespec="seconds"), plan=os.path.relpath(PLAN, ROOT),
               plan_sha256=au["plan_sha256"], seed=SEED, n_jobs=N_JOBS, n_kidney=int(len(kd)), n_features=len(feats), axes={})
    oofs = []
    for name, spec in AXES.items():
        a, oof, sec = run_axis(name, spec, kd, feats, adults, design)
        out["axes"][name] = a
        oofs.append(oof)
        print(f"[{name}] 完成 {sec:.0f}s")
    out["runtime_s"] = round(time.time() - t0, 1)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    pd.concat(oofs, ignore_index=True).to_csv(OOF, index=False, compression="gzip", float_format="%.6g")
    with open(os.path.join(ROOT, "results", "runs_log.jsonl"), "a", encoding="utf-8") as f:
        for name, a in out["axes"].items():
            f.write(json.dumps(dict(kind="v3_2_eval", created=out["created"], axis=name, plan_sha256=out["plan_sha256"],
                                    n=a["n"], n_pos=a["n_pos"],
                                    auroc={m: a["models"][m]["repeats"]["mean"]["auroc"] for m in MODELS}), ensure_ascii=False) + "\n")
    print(f"[存檔] {OUT}｜{OOF}｜{out['runtime_s']}s")
    for name, a in out["axes"].items():      # 全部存檔之後才列印
        for m in MODELS:
            s = a["models"][m]
            print(f"  [{name}｜{m}] AUROC {s['repeats']['mean']['auroc']:.3f}｜AP {s['repeats']['mean']['ap']:.3f}"
                  f"｜截距 {s['calibration_repeat0']['intercept']:+.3f} 斜率 {s['calibration_repeat0']['slope']:.3f}"
                  f"｜Brier {s['calibration_repeat0']['brier']:.4f}")


if __name__ == "__main__":
    main(only_audit=len(sys.argv) > 1 and sys.argv[1] == "audit")
