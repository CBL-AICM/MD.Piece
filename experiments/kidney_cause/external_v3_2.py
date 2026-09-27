# -*- coding: utf-8 -*-
"""v3.2：2021–2023 事後評估、網頁工具 v3.2、重新校準之交叉驗證——依 params/v3_2_plan.json（先提交 f6abc91）。
    python external_v3_2.py
    → params/direction_model_v3_2_basic.json（重新校準前）、params/direction_model_v3_2.json（網頁工具）、
      results/direction_v3_2_recalibration.json、results/v3_2_external.json

2021–2023 年資料已用於 v3 之一次性外部確認（結果 a7c4af8，照原樣保留）與 v3.1 重新校準，本檔所有外部數字皆為事後分析。
資料：修正一（Cobas 8000 → 6000）之後再以 BIOPRO_J 換成 DxC 660i 量尺（C4），與 v3.2 開發資料同一量尺。"""
import hashlib
import json
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np                                                    # noqa: E402
import pandas as pd                                                   # noqa: E402
from scipy.stats import chi2                                          # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score   # noqa: E402

import design_variance as dv                                          # noqa: E402
import direction                                                      # noqa: E402
import external_validation_2021 as ev                                 # noqa: E402
import nhanes_cohort as nc                                            # noqa: E402
import recalibrate_v3_1 as rc                                         # noqa: E402
from evaluate_v3 import band_stats, bands, boot, calib, fit_tool, tool_predict  # noqa: E402
from evaluate_v3_2 import MODELS, PLAN, sets_for                      # noqa: E402

BASE = os.path.join(ROOT, "params", "direction_model_v3_2_basic.json")
TOOL = os.path.join(ROOT, "params", "direction_model_v3_2.json")
REPORT = os.path.join(ROOT, "results", "direction_v3_2_recalibration.json")
OUT = os.path.join(ROOT, "results", "v3_2_external.json")
FROZEN = {"v3_full_LR（凍結）": ev.MODELS["v3_full_LR（部署）"], "v3_basic_LR（凍結）": ev.MODELS["v3_basic_LR（常規套組候選）"]}
N_SPLITS, SPLIT_SEED = 200, 20260927
EPS = direction.EPS
col = lambda d, f: d[f].to_numpy(float) if f in d.columns else np.full(len(d), np.nan)
logit = lambda p: np.log(np.clip(p, EPS, 1 - EPS) / (1 - np.clip(p, EPS, 1 - EPS)))


def metrics(y, cal, band):
    ok = band >= 0
    return dict(auroc=float(roc_auc_score(y, cal)), ap=float(average_precision_score(y, cal)),
                ci95=boot(y, dict(auroc=lambda i: roc_auc_score(y[i], cal[i]), ap=lambda i: average_precision_score(y[i], cal[i]))),
                calibration=calib(y, cal), insufficient_data_n=int((~ok).sum()), bands_B=band_stats(y[ok], band[ok]))


def phlebotomy_weight(L):
    """WTPH2YR（2021–2023 抽血權重）：各抽血檔同一人之值應相同，以 BIOPRO_L 為準並核對；<1 視為 0（read_sas 把 0 讀成 5e-79）。"""
    w = nc._read("BIOPRO_L.xpt")[["SEQN", "WTPH2YR"]]
    for f in ("CBC_L.xpt", "GHB_L.xpt", "HDL_L.xpt"):
        m = w.merge(nc._read(f)[["SEQN", "WTPH2YR"]], on="SEQN", suffixes=("", "_o"))
        assert np.allclose(m["WTPH2YR"], m["WTPH2YR_o"], equal_nan=True), f"{f} 之 WTPH2YR 與 BIOPRO_L 不一致"
    out = L[["SEQN"]].merge(w, on="SEQN", how="left", validate="one_to_one")["WTPH2YR"].to_numpy(float)
    return np.where(np.nan_to_num(out) < 1, 0.0, out)


def recal_cv(base_axes, kd, tag):
    """在訓練半依 rc 之規則重新校準（含是否更新斜率之判斷、事前機率、門檻），在測試半評估；另列不重新校準。"""
    rng = np.random.default_rng(SPLIT_SEED)
    out = {}
    for name, spec in direction.AXES.items():
        a = base_axes[name]
        d = kd[kd[spec["label"]].notna()]
        y = d[spec["label"]].astype(int).to_numpy()
        _, p0, band0 = direction.predict_matrix(a, np.column_stack([col(d, f) for f in a["features"]]))
        h, j = d["SDMVSTRA"].to_numpy(int), d["SDMVPSU"].to_numpy(int)
        strata = sorted(set(h))
        assert all(sorted(set(j[h == s])) == [1, 2] for s in strata), f"{tag}{name}：有層不是恰好兩個 PSU"
        splits = [("固定：PSU 1 訓練、PSU 2 測試", j == 1)]
        for k in range(N_SPLITS):
            pick = dict(zip(strata, rng.integers(1, 3, len(strata))))
            splits.append((f"隨機 {k + 1}", j == np.array([pick[s] for s in h])))
        rows = []
        for sname, tr in splits:
            te = ~tr
            o_tr = logit(p0[tr])
            (a1,), ll1 = rc.fit(y[tr], o_tr, False)
            try:
                (a2, b2), ll2 = rc.fit(y[tr], o_tr, True)
                p_slope = float(chi2.sf(2 * (ll2 - ll1), 1))
            except np.linalg.LinAlgError:
                p_slope = 1.0
            slope = int(y[tr].sum()) >= rc.MIN_EVENTS and p_slope < 0.05
            ra, rb = (a2, b2) if slope else (a1, 1.0)
            p_te = 1 / (1 + np.exp(-(ra + rb * logit(p0[te]))))
            prev = float(y[tr].mean())
            hi, lo = direction.odds_thresholds(prev)
            ok = band0[te] >= 0
            bt = np.where(p_te >= hi, 2, np.where(p_te <= lo, 0, 1))
            yt, n_pos = y[te], int(y[te].sum())
            cal_ok = n_pos >= 2
            r = dict(split=sname, n_train=int(tr.sum()), n_pos_train=int(y[tr].sum()), n_test=int(te.sum()), n_pos_test=n_pos,
                     slope_update=bool(slope), a=float(ra), b=float(rb), prior_train=prev,
                     observed_test=float(yt.mean()), mean_pred_recal=float(p_te.mean()), mean_pred_none=float(p0[te].mean()),
                     calib_recal=calib(yt, p_te) if cal_ok else None, calib_none=calib(yt, p0[te]) if cal_ok else None,
                     band_rate={k: (float(yt[ok][bt[ok] == v].mean()) if (bt[ok] == v).any() else None)
                                for k, v in (("傾向", 2), ("不確定", 1), ("不傾向", 0))},
                     band_n={k: int((bt[ok] == v).sum()) for k, v in (("傾向", 2), ("不確定", 1), ("不傾向", 0))})
            rows.append(r)
        rnd = rows[1:]

        def q(vals):
            v = np.array([x for x in vals if x is not None and np.isfinite(x)], float)
            return dict(median=float(np.median(v)), p2_5=float(np.percentile(v, 2.5)), p97_5=float(np.percentile(v, 97.5)), n=int(len(v))) if len(v) else None
        summ = dict(
            n_random_splits=len(rnd), share_slope_update=float(np.mean([r["slope_update"] for r in rnd])),
            calib_intercept_recal=q([r["calib_recal"]["intercept"] if r["calib_recal"] else None for r in rnd]),
            calib_slope_recal=q([r["calib_recal"]["slope"] if r["calib_recal"] else None for r in rnd]),
            calib_intercept_none=q([r["calib_none"]["intercept"] if r["calib_none"] else None for r in rnd]),
            calib_slope_none=q([r["calib_none"]["slope"] if r["calib_none"] else None for r in rnd]),
            oe_recal=q([r["mean_pred_recal"] / r["observed_test"] if r["observed_test"] > 0 else None for r in rnd]),
            oe_none=q([r["mean_pred_none"] / r["observed_test"] if r["observed_test"] > 0 else None for r in rnd]),
            band_rate={k: q([r["band_rate"][k] for r in rnd]) for k in ("傾向", "不確定", "不傾向")},
            n_pos_test=q([r["n_pos_test"] for r in rnd]))
        out[name] = dict(n=int(len(y)), n_pos=int(y.sum()), strata=len(strata), fixed_split=rows[0], random_summary=summ)
    return out


def main():
    plan_sha = hashlib.sha256(open(PLAN, "rb").read()).hexdigest()
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = nc.build_v3(P, verbose=False, fixes=True)
    kd, feats = V["cohort"], V["features"]
    # 1) 網頁工具 v3.2 之基礎模型：常規套組 LR（與內部評估 LR_routine 同一演算法），以全部 v3.2 開發資料訓練
    base = direction.train(feature_set="basic", path=BASE, fixes=True)
    L = ev.load_2021(True, dxc=True)
    L["WTPH2YR"] = phlebotomy_weight(L)
    design = dv.design_of(L)
    kx = L[L["kidney3"] == 1]
    res = dict(created=pd.Timestamp.now().isoformat(timespec="seconds"), plan=os.path.relpath(PLAN, ROOT), plan_sha256=plan_sha,
               status="事後分析：2021–2023 已用於 v3 之一次性外部確認（a7c4af8）與 v3.1 重新校準",
               data=dict(n_adults=int(len(L)), kidney=dict(pos=int((L.kidney3 == 1).sum()), neg=int((L.kidney3 == 0).sum()),
                                                           unknown=int(L.kidney3.isna().sum())),
                         kidney_with_WTPH2YR=int((kx["WTPH2YR"] > 0).sum())), axes={})
    for name, spec in direction.AXES.items():
        d = kd[kd[spec["label"]].notna()]
        s = sets_for(feats, spec)
        Xd, yd = d[s["full"]].to_numpy(float), d[spec["label"]].to_numpy(int)
        dx = kx[kx[spec["label"]].notna()]
        yx = dx[spec["label"]].astype(int).to_numpy()
        Xx = np.column_stack([col(dx, f) for f in s["full"]])
        insufficient = np.mean([~np.isnan(col(dx, f)) for f in s["routine"]], axis=0) < 0.5
        assert base["axes"][name]["features"] == s["routine"], "工具基礎模型之特徵與內部評估之常規套組不同"
        preds, r = {}, dict(n=int(len(yx)), n_pos=int(yx.sum()), prevalence=float(yx.mean()),
                            features_absent_in_2021=[f for f in s["full"] if f not in dx.columns or dx[f].isna().all()], models={})
        for m, (fs, make) in MODELS.items():
            idx = [s["full"].index(f) for f in s[fs]]
            if m == "LR_routine":
                _, cal, band = direction.predict_matrix(base["axes"][name], Xx[:, idx])
            else:
                T = fit_tool(Xd[:, idx], yd, make=make)
                _, cal = tool_predict(T, Xx[:, idx])
                band = np.where(insufficient, -1, bands(cal, T["prev"], "B"))
            preds[m] = cal
            r["models"][m] = metrics(yx, cal, band)
        for fk, fp in FROZEN.items():
            a = json.load(open(fp, encoding="utf-8"))["axes"][name]
            _, cal, band = direction.predict_matrix(a, np.column_stack([col(dx, f) for f in a["features"]]))
            r["models"][fk] = metrics(yx, cal, band)
        r["paired"] = {f"{a_}−{b_}": dict(d_auroc=float(roc_auc_score(yx, preds[a_]) - roc_auc_score(yx, preds[b_])),
                                           ci95=boot(yx, dict(d_auroc=lambda i: roc_auc_score(yx[i], preds[a_][i]) - roc_auc_score(yx[i], preds[b_][i]))))
                       for a_, b_ in (("HGB_routine", "LR_routine"), ("LR_routine", "LR_full"))}
        h, j = dx["SDMVSTRA"].to_numpy(int), dx["SDMVPSU"].to_numpy(int)
        ws = {wk: dx[wk].to_numpy(float) for wk in ("WTMEC2YR", "WTPH2YR")}
        r["weighted"] = {m: {wk: dict(n_weight_positive=int((w > 0).sum()),
                                      **dv.analyse(yx[w > 0].astype(float), preds[m][w > 0], w[w > 0], h[w > 0], j[w > 0], design))
                             for wk, w in ws.items()} for m in ("LR_routine", "HGB_routine")}
        res["axes"][name] = r
    # 2) 網頁工具 v3.2：與 v3.1 相同之更新規則
    tool, rep = rc.update(base, kx, "v3.2", "NHANES 2021–2023（週期 L；修正一後再以 BIOPRO_J 換成 DxC 660i 量尺）")
    tool.update(source_model=dict(path=os.path.relpath(BASE, ROOT), sha256=hashlib.sha256(open(BASE, "rb").read()).hexdigest()),
                data_fixes="v3.2 修正後之開發資料（params/v3_2_plan.json：2001–2002 改名對應、HDL、2017–2018 BIOPRO_J 換算）",
                performance="判別：內部見 results/v3_2_eval.json（LR_routine）、2021–2023 事後評估見 results/v3_2_external.json；"
                            "更新後之校準為表面值，交叉驗證見 results/v3_2_external.json 之 recalibration_cv",
                band_rule="勝算倍數：傾向 ≥2× 事前勝算、不傾向 ≤0.5×；事前＝2021–2023 該軸比例；常規套組有值 <50% → 資料不足")
    json.dump(tool, open(TOOL, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(dict(note="表面值：更新校準與評估用同一批資料，不是獨立驗證", axes=rep), open(REPORT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # 3) 肝炎陽性分 B／C 型（工具 v3.2，重新校準後）
    dx = kx[kx["hep3"].notna()]
    a = tool["axes"]["肝炎"]
    _, cal, band = direction.predict_matrix(a, np.column_stack([col(dx, f) for f in a["features"]]))
    y = dx["hep3"].astype(int).to_numpy()
    hbv, hcv = (dx["hbv3"] == 1).to_numpy(), (dx["hcv3"] == 1).to_numpy()
    sub = dict(coinfected=int((hbv & hcv).sum()))
    for k, m in (("C型_HCV_RNA", hcv), ("B型_HBsAg", hbv)):
        pos, neg = m & (y == 1), y == 0
        yy, pp = np.r_[np.ones(pos.sum()), np.zeros(neg.sum())], np.r_[cal[pos], cal[neg]]
        sub[k] = dict(n_pos=int(pos.sum()), auroc=float(roc_auc_score(yy, pp)),
                      ci95=boot(yy, dict(auroc=lambda i: roc_auc_score(yy[i], pp[i]))),
                      bands={n: int((band[pos] == v).sum()) for n, v in (("傾向", 2), ("不確定", 1), ("不傾向", 0), ("資料不足", -1))})
    res["hepatitis_subtypes_tool_v3_2"] = sub
    # 4) 重新校準之交叉驗證（v3.1：凍結常規套組模型＋修正一資料；v3.2：本版基礎模型＋C4 資料）
    L31 = ev.load_2021(True)
    base31 = json.load(open(ev.MODELS["v3_basic_LR（常規套組候選）"], encoding="utf-8"))["axes"]
    res["recalibration_cv"] = {"v3.1": recal_cv(base31, L31[L31["kidney3"] == 1], "v3.1 "),
                               "v3.2": recal_cv(base["axes"], kx, "v3.2 ")}
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print(f"[存檔] {BASE}\n[存檔] {TOOL}\n[存檔] {REPORT}\n[存檔] {OUT}")
    for name, r in res["axes"].items():      # 全部存檔後才列印
        for m, v in r["models"].items():
            print(f"  [{name}｜{m}] n={r['n']:,} 陽性 {r['n_pos']}｜AUROC {v['auroc']:.3f}（{v['ci95']['auroc'][0]:.3f}–{v['ci95']['auroc'][1]:.3f}）"
                  f"｜截距 {v['calibration']['intercept']:+.2f} 斜率 {v['calibration']['slope']:.2f}")
    for ver, cv in res["recalibration_cv"].items():
        for name, c in cv.items():
            sm = c["random_summary"]
            print(f"  [重新校準交叉驗證 {ver}｜{name}] 斜率更新比例 {sm['share_slope_update']:.2f}｜測試半 O/E 重新校準 {sm['oe_recal']}"
                  f"｜不重新校準 {sm['oe_none']}")


if __name__ == "__main__":
    main()
