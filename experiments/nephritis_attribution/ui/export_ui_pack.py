# -*- coding: utf-8 -*-
"""模型視覺化：把介面要顯示的每一個數字從模型端匯出，前端只負責畫。

前端不得實作任何模型邏輯、不得硬寫係數或門檻 —— 介面上出現的每一格
都必須來自這支腳本產出的 ui_pack.json，否則畫面與模型會各自漂移，
而畫面是給人看的、模型是給人用的，兩者不一致比沒有畫面更糟。

  ui/ui_pack.json          資料包（參數、兩種 case mix 的結果、閘門、曲線、病人樣本、旋轉演示）
  ui/index.html            由 index.template.html 嵌入 ui_pack.json 產生（單一檔、離線、可雙擊開啟）

執行：python ui/export_ui_pack.py [--seed 20260827] [--n 4000]
前提：results/results_{referral,primary}.json 必須already存在（先跑 run.py 兩種 case mix）。
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

from sklearn.decomposition import FactorAnalysis                       # noqa: E402
from sklearn.metrics import roc_auc_score                              # noqa: E402

import deterministic as DET                                           # noqa: E402
import pipeline as PL                                                 # noqa: E402
from attribution import PARAMS_DIR, _offdiag, load, spec, top_contributors   # noqa: E402
from cohort import MARKERS, simulate                                  # noqa: E402

N_PATIENTS = 24        # 病人卡樣本數：夠看出型態多樣性，又不會把單檔撐大
N_ROTATION = 60        # 旋轉演示的病人數：夠讓「重排」在畫面上看得出來


def _f(x):
    """np -> 可 JSON 化，且 NaN/Inf 一律變 None（前端才知道是「沒有」而不是 0）。"""
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 5)
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, np.ndarray):
        return [_f(v) for v in x]
    return x


def patient_cards(coh, res, ind, Lam, drivers, n_cards=N_PATIENTS):
    """挑一批涵蓋各種組織型態與各種管線路徑的病人，輸出完整的決策軌跡。

    刻意不只挑「模型答對」的：L2 誤分流、被否決的、混合旗標的都要有，
    否則介面會變成一份精選集，看的人會對真實表現產生錯誤印象。
    """
    it = res["_internal"]
    names, labels = coh["label_names"], coh["label"]
    ok, _ = PL.l1_quality(coh["raw"])
    route, rule_id = DET.apply(coh["raw"], coh["markers"])
    residual = it["residual"]
    res_idx = np.where(residual)[0]                      # 全域索引
    local_of = {g: i for i, g in enumerate(res_idx)}

    # 取樣：每個組織型態至少一位，剩下的名額給「有旗標」與「被否決」的個案
    picked = []
    for k in range(len(names)):
        cand = res_idx[labels[res_idx] == k]
        if len(cand):
            picked.append(int(cand[0]))
    flagged = [int(g) for g in res_idx if it["flags"][local_of[g]] and int(g) not in picked]
    vetoed = [int(g) for g in res_idx if it["veto"][local_of[g]] and int(g) not in picked]
    routed = [int(g) for g in np.where(route != DET.NO_ROUTE)[0][:3]]
    for pool in (vetoed[:4], flagged[:8], routed):
        for g in pool:
            if g not in picked and len(picked) < n_cards:
                picked.append(g)
    picked = picked[:n_cards]

    show_raw = ["c3", "c4", "upcr", "albumin", "urine_rbc_hpf", "dysmorphic_rbc_pct",
                "rbc_cast", "cr_now", "cr_slope_per_week", "platelet", "ldh",
                "urine_wbc_hpf", "cholesterol", "crp", "sbp"]
    ref_of = {s["raw"]: (s["ref"], s["kind"]) for s in ind}

    cards = []
    for g in picked:
        in_res = bool(residual[g])
        li = local_of.get(g)
        card = dict(
            id=int(g),
            truth=names[labels[g]],
            immune_gn=bool(coh["immune_gn"][g]),
            time_critical=bool(coh["time_critical"][g]),
            l1_pass=bool(ok[g]),
            l2_route=(None if route[g] == DET.NO_ROUTE else str(route[g])),
            l2_rule=(str(rule_id[g]) or None),
            markers={m: dict(available=bool(coh["markers"][m + "_available"][g] > 0.5),
                             positive=bool(coh["markers"][m][g] > 0.5)) for m in MARKERS},
            labs=[dict(name=k, value=_f(coh["raw"][k][g]),
                       ref=_f(ref_of.get(k, (None, None))[0]),
                       dir=ref_of.get(k, (None, None))[1]) for k in show_raw],
        )
        if in_res and li is not None:
            a, x = it["A"][li], it["Xr"][li]
            sh = it["sh"][li]
            contrib = top_contributors(x, a, Lam, ind, k=3)
            card.update(
                in_residual=True,
                prob=_f(it["oof"][li]),
                threshold=_f(it["thr"]),
                ruled_out=bool(it["ruled_out"][li]),
                vetoed=bool(it["veto"][li]),
                flags=list(it["flags"][li]),
                drivers=[dict(name=drivers[d], share=_f(sh[d]), amplitude=_f(a[d]),
                              why=[dict(indicator=n, weight=_f(v)) for n, v in contrib[d]])
                         for d in np.argsort(-sh)],
            )
        else:
            card.update(in_residual=False, drivers=[], flags=[])
        cards.append(card)
    return cards


def rotation_demo(X, Lam, seed=0, n_show=N_ROTATION, n_rot=3):
    """旋轉不確定性的可視化資料：同一批病人、擬合完全相同、歸因整個重排。

    這是整個專案裡最有說服力的一張圖，所以資料要能讓人自己核對：
    連 fit_deviation 都一起送出去，讓看的人確認「真的沒有變好變壞」。
    """
    rng = np.random.default_rng(seed)
    fa = FactorAnalysis(n_components=3, random_state=seed).fit(X)
    Lf = fa.components_.T
    Xc = X - X.mean(axis=0)
    base_off = _offdiag(Lf @ Lf.T)

    def raw_scores(L):
        return np.linalg.lstsq(L, Xc.T, rcond=None)[0].T

    def to_shares(sc):
        """截斷負值只為了畫成占比長條；一致率一律用未截斷的分數算，
        否則畫面上的數字會和閘門 G3 對不起來。"""
        s = np.maximum(sc, 0.0)
        tot = s.sum(axis=1, keepdims=True)
        return np.where(tot > 1e-9, s / np.maximum(tot, 1e-9), 1 / 3)

    sel = np.arange(min(n_show, X.shape[0]))
    out = dict(n=int(len(sel)), solutions=[])
    base_raw = raw_scores(Lf)
    base_top = base_raw.argmax(axis=1)
    out["solutions"].append(dict(label="自由估計原解", fit_deviation=0.0, agreement=1.0,
                                 shares=[[_f(v) for v in row] for row in to_shares(base_raw)[sel]]))
    for r in range(n_rot):
        Q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        Lr = Lf @ Q
        sc = raw_scores(Lr)
        out["solutions"].append(dict(
            label=f"旋轉解 {r + 1}",
            fit_deviation=float(np.max(np.abs(_offdiag(Lr @ Lr.T) - base_off))),
            agreement=_f(float((sc.argmax(axis=1) == base_top).mean())),
            shares=[[_f(v) for v in row] for row in to_shares(sc)[sel]]))
    return out


def l3_coefficients(model, threshold):
    """把 L3 的標準化統計與邏輯迴歸係數原樣匯出。

    前端拿到的是「參數」不是「模型」：它做的事只有 (x - mean)/scale 再內積再 sigmoid。
    這樣前端就無法自己發明權重，而模型端改係數時介面會跟著改，不需要兩邊各改一次。
    """
    sc, lr = model.steps[0][1], model.steps[1][1]
    return dict(mean=[_f(v) for v in sc.mean_], scale=[_f(v) for v in sc.scale_],
                coef=[_f(v) for v in lr.coef_[0]], intercept=_f(float(lr.intercept_[0])),
                threshold=_f(threshold))


def selftest_cases(coh, res, ind, n=12):
    """黃金案例：前端每次載入都用這些重算一遍並比對。

    前端一旦與模型端漂移（改錯轉換、少一個門檻、係數順序錯位），畫面會自己說出來，
    而不是安靜地給出看起來很合理的錯答案。這是鐵則 12 在介面上的實作。
    """
    it = res["_internal"]
    res_idx = np.where(it["residual"])[0][:n]
    fields = [s["raw"] for s in ind] + ["cr_now", "days_since_last_panel"]
    cases = []
    for li, g in enumerate(res_idx):
        cases.append(dict(
            inputs={f: _f(coh["raw"][f][g]) for f in fields},
            markers={m: dict(available=bool(coh["markers"][m + "_available"][g] > 0.5),
                             positive=bool(coh["markers"][m][g] > 0.5)) for m in MARKERS},
            expect=dict(prob=_f(it["model"].predict_proba(it["Xr"][li:li + 1])[0, 1]),
                        shares=[_f(v) for v in it["sh"][li]],
                        flags=sorted(it["flags"][li])),
        ))
    return cases


def build(seed, n):
    ind, Lam, drivers = spec()
    P, R = load("patterns.json"), DET.rules()
    pack = dict(
        meta=dict(seed=seed, n=n, title="腎炎機轉歸因模型",
                  params_hash=__import__("hashlib").sha256(
                      b"".join(open(os.path.join(PARAMS_DIR, f), "rb").read()
                               for f in ("loadings.json", "patterns.json", "deterministic.json"))
                  ).hexdigest()[:16]),
        drivers=drivers,
        indicators=[dict(name=s["name"], raw=s["raw"], zh=s["zh"], unit=s["unit"], kind=s["kind"],
                         ref=s["ref"], scale=s["scale"], loadings=[_f(v) for v in s["loadings"]],
                         rationale=s["rationale"]) for s in ind],
        extra_fields=load("loadings.json")["extra_fields"],
        patterns=[dict(name=p["name"], zh=p["zh"], immune_gn=p["immune_gn"],
                       time_critical=p["time_critical"],
                       prevalence=p["prevalence"], prevalence_primary=p["prevalence_primary"],
                       driver_mean=[_f(v) for v in p["driver_mean"]]) for p in P["patterns"]],
        rules=[dict(id=r["id"], route=r["route"], action=r["action"], why=r["why"],
                    when=r["when"]) for r in R["rules"]],
        active_sediment=R["active_sediment"],
        l5_thresholds=R["l5_flags"],
        actions=R["actions"],
        quality_rules=dict(P["quality"], cr_unit_max=20.0, albumin_max=6.5),
        pattern_profiles=[[_f(v) for v in p["driver_mean"]] for p in P["patterns"]],
        flag_defs={k: v.get("why", "") for k, v in R["l5_flags"].items()},
        safety_override=dict(cr_slope_per_week_min=R["safety_override"]["cr_slope_per_week_min"],
                             or_flag=R["safety_override"]["or_flag"],
                             why=R["safety_override"]["_note"]),
        casemix={},
    )

    for mix in ("referral", "primary"):
        rp = os.path.join(ROOT, "results", f"results_{mix}.json")
        if not os.path.exists(rp):
            raise SystemExit(f"缺少 {rp} —— 請先跑 python run.py --casemix {mix}")
        saved = json.load(open(rp, encoding="utf-8"))
        # 一律沿用 results 檔的 seed/n 重建同一個世代，讓畫面上每個數字同源
        s_seed, s_n = int(saved["seed"]), int(saved["n"])
        coh = simulate(s_seed, n=s_n, casemix=mix)
        res = PL.run(coh, seed=s_seed)
        it = res["_internal"]
        m1_auc = float(roc_auc_score(it["yr"], it["oof"]))
        ok, _ = PL.l1_quality(coh["raw"])
        n_tot = len(ok)
        n_res = int(it["residual"].sum())
        n_ruled = int(it["ruled_out"].sum())

        pack["casemix"][mix] = dict(
            label={"referral": "腎切片轉介族群", "primary": "基層／一般腎臟科族群"}[mix],
            funnel=[
                dict(layer="收案", n=n_tot, note="L1 之前的全部個案"),
                dict(layer="L1 棄權", n=int((~ok).sum()), note="缺值／單位錯置／時間窗過期 → 不猜",
                     detail=res["quality"]),
                dict(layer="L2 硬分流", n=int(n_tot - (~ok).sum() - n_res),
                     note="決定性標記命中，純 if-else 定案", detail=res["l2"]["by_rule"],
                     accuracy=_f(res["l2"]["accuracy"])),
                dict(layer="L3-L5 殘餘", n=n_res, note="標記缺席或未回覆 → 常規資料模型"),
                dict(layer="可安全排除", n=n_ruled, note="免疫介導腎絲球腎炎不太可能"),
                dict(layer="不可排除", n=int(n_res - n_ruled), note="需免疫學套組／考慮切片"),
            ],
            l3=dict(prevalence=_f(res["l3"]["prevalence"]), auroc=_f(m1_auc),
                    npv=_f(res["l3"]["npv"]), ruleout_rate=_f(res["l3"]["ruleout_rate"]),
                    veto_rate=_f(res["l3"]["veto_rate"]),
                    target_npv=res["l3"]["target_npv"],
                    time_critical_n=res["l3"]["time_critical_n"],
                    n_required=res["l3"]["time_critical_n_required_rule_of_three"],
                    powered=res["l3"]["safety_endpoint_powered"]),
            ruleout_curve=res["l3"]["ruleout_curve"],
            ruleout_curve_npv_only=res["l3"]["ruleout_curve_npv_only"],
            l4_mean_shares=[_f(v) for v in res["l4"]["mean_shares"]],
            psi_offdiag_rmse=saved["l4"]["psi_offdiag_rmse"],
            l5={k: _f(v) for k, v in res["l5"].items()},
            safety=saved["safety"],
            m0=saved["m0_same_denominator"],
            gates=[dict(gate=g["gate"], passed=g["passed"], value=g["value"],
                        criterion=g["criterion"], fail_means=g["fail_means"]) for g in saved["gates"]],
            misspecification_curve=saved.get("misspecification_curve"),
            patients=patient_cards(coh, res, ind, Lam, drivers),
            scoring=l3_coefficients(it["model"], it["thr"]),
            narrative=R["narrative"],
            cohort_ref=dict(
                prob_quantiles=[_f(v) for v in np.percentile(it["oof"], np.arange(0, 101))],
                x_p10=[_f(v) for v in np.percentile(it["Xr"], 10, axis=0)],
                x_p50=[_f(v) for v in np.percentile(it["Xr"], 50, axis=0)],
                x_p90=[_f(v) for v in np.percentile(it["Xr"], 90, axis=0)],
                note="殘餘子集的分布。報告用來回答「這個數字在同類病人裡算高還是低」——"
                     "沒有這個參照，一個機率值對讀報告的人沒有意義。"),
            applicability=dict(
                x_p01=[_f(v) for v in np.percentile(it["Xr"], 1, axis=0)],
                x_p99=[_f(v) for v in np.percentile(it["Xr"], 99, axis=0)],
                note="訓練子集的指標分布範圍。全零向量（完全沒有異常所見）不在此模型的適用族群內——"
                     "轉介世代裡沒有這種人，模型對它只能外推。"),
            shortlist=saved.get("shortlist"),
            selftest=selftest_cases(coh, res, ind),
        )
        pack["meta"]["seed"], pack["meta"]["n"] = s_seed, s_n
        if mix == "referral":
            pack["rotation"] = rotation_demo(it["Xr"], Lam, seed=s_seed)
    return pack


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--n", type=int, default=4000, help="僅在 results 檔缺欄位時使用；正常情況沿用 results 檔的 n")
    ap.add_argument("--publish", action="store_true", help="同時寫入 frontend/nephritis-model.html（＝準備上正式站）")
    a = ap.parse_args()

    pack = build(a.seed, a.n)
    pj = os.path.join(HERE, "ui_pack.json")
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, separators=(",", ":"))

    tpl = open(os.path.join(HERE, "index.template.html"), encoding="utf-8").read()
    if "__UI_PACK__" not in tpl:
        raise SystemExit("index.template.html 缺少 __UI_PACK__ 佔位符")
    html = tpl.replace("__UI_PACK__", json.dumps(pack, ensure_ascii=False, separators=(",", ":")))
    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    # --publish 才寫進 frontend/（正式站由 vercel.json 的 frontend/** 靜態規則提供）。
    # 預設不寫：這頁一旦躺在 frontend/ 裡，任何一次為了別的理由合併 main 都會把它
    # 一起推上公開醫療網域。要上線必須是明確的動作，不能是合併的副作用。
    pub = os.path.join(ROOT, "..", "..", "frontend", "nephritis-model.html")
    if a.publish and os.path.isdir(os.path.dirname(pub)):
        with open(pub, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"ui_pack.json  {os.path.getsize(pj) / 1024:.0f} KB")
    print(f"index.html    {os.path.getsize(out) / 1024:.0f} KB  （單一檔，可直接開啟）")
    if a.publish and os.path.isdir(os.path.dirname(pub)):
        print("frontend/nephritis-model.html  已同步（正式站 /nephritis-model.html）")


if __name__ == "__main__":
    main()
