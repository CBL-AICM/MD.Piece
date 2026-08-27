# -*- coding: utf-8 -*-
"""五層管線：L1 資料品質 -> L2 決定性標記 -> L3 二元免疫判定 -> L4 三驅動歸因排序 -> L5 混合旗標。

兩層架構的意思是：L2 是硬分流（確定的事用程式碼答完），L3-L5 只處理 L2 沒接住的人。
所有對外宣稱的效能都必須報在「L1 通過且 L2 未命中」這個子集上 —— 把 L2 接住的
簡單個案混進分母會讓數字好看但沒有意義。
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import deterministic as DET
from attribution import load, nnls_attribution, shares, spec, top_contributors, transform_raw

# L3-L5 允許使用的欄位＝常規資料。決定性標記與洩漏特徵都不在此列（閘門 G6 驗證）。
BANNED_IN_MODEL = {
    # 決定性標記：只給 L2 用，L3-L5 不得取用（否則「零新增」就破功了）
    "anti_gbm", "anca", "anti_pla2r", "maha_triad",
    # KidneyIntelX 式的加驗生物標記：本模型明確不採用
    "stnfr1", "stnfr2", "kim1",
    # 洩漏特徵：切片所見、事後治療、編碼診斷、追蹤結果
    "if_deposit_intensity", "crescent_pct", "icd_group", "egfr_12m",
    "immunosuppressant_started", "true_anti_gbm", "true_anca", "true_pla2r"}


# ---------------- L1 資料品質 ----------------

def l1_quality(raw, Q=None):
    """回傳 (ok[n], reasons dict)。棄權是功能不是失敗：資料不夠就說不夠，不猜。"""
    Q = Q or load("patterns.json")["quality"]
    n = len(raw["cr_now"])
    miss = np.zeros(n, dtype=int)
    for f in Q["required_fields"]:
        miss += ~np.isfinite(raw[f])
    r_missing = miss > Q["max_missing_allowed"]
    # 單位錯置：肌酸酐若是 umol/L 被當 mg/dL，數值會落在 60-900。不自動換算 —— 靜默修正
    # 比擋下來危險，因為你無法確認那到底是單位錯還是真的洗腎級數值。
    r_unit = np.nan_to_num(raw["cr_now"], nan=1.0) > 20.0
    r_impossible = (np.nan_to_num(raw["albumin"], nan=4.0) > 6.5) | (np.nan_to_num(raw["upcr"], nan=0.1) < 0)
    r_stale = raw["days_since_last_panel"] > Q["max_window_days"]
    ok = ~(r_missing | r_unit | r_impossible | r_stale)
    return ok, {"missing": int(r_missing.sum()), "unit_error": int(r_unit.sum()),
                "impossible": int(r_impossible.sum()), "stale": int(r_stale.sum()),
                "abstain_rate": float(1 - ok.mean())}


# ---------------- L3 二元免疫判定（NPV 端） ----------------

def _npv_threshold(p, y, target, veto=None, y_critical=None, crit_cap=None):
    """挑最大的門檻 t，同時滿足兩個條件：

      NPV( 被 rule out 的人 ) >= target
      時效性型態被 rule out 的比率 <= crit_cap

    兩件事都必須在「套用決定性否決之後」的集合上算 —— 否決會把一部分人抽走，
    在抽走之前算的 NPV 上線後不成立。而且漏判率是硬上限，不是達標後的加分項：
    平均 NPV 漂亮但漏掉抗 GBM，正是這類系統最典型的失敗方式。
    """
    keep = ~veto if veto is not None else np.ones_like(y, dtype=bool)
    best_t, best_cov = None, -1.0
    for t in np.unique(np.round(p, 4)):
        neg = (p < t) & keep
        if neg.sum() < 20:
            continue
        if float((y[neg] == 0).mean()) < target:
            continue
        if crit_cap is not None and y_critical is not None and y_critical.sum():
            if float((neg & y_critical).sum() / y_critical.sum()) > crit_cap:
                continue
        if neg.mean() > best_cov:
            best_t, best_cov = float(t), float(neg.mean())
    return best_t


def fit_l3(X, y, target_npv, seed=0, veto=None, y_critical=None, crit_cap=None):
    """回傳 (model, threshold, oof_prob)。門檻用 out-of-fold 機率挑，避免用同一批資料
    既訓練又定門檻（那會讓 NPV 在上線後立刻掉下來）。"""
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    oof = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    t = _npv_threshold(oof, y, target_npv, veto=veto, y_critical=y_critical, crit_cap=crit_cap)
    model.fit(X, y)
    return model, t, oof


def ruleout_curve(prob, y, veto, y_critical=None, crit_cap=None, targets=(0.90, 0.95, 0.98, 0.99)):
    """不同 NPV 門檻下能安全排除多少人。NPV 高度依賴盛行率，單報一個點會誤導。"""
    out = []
    for tg in targets:
        t = _npv_threshold(prob, y, tg, veto=veto, y_critical=y_critical, crit_cap=crit_cap)
        if t is None:
            out.append(dict(target_npv=tg, achievable=False))
            continue
        neg = (prob < t) & ~veto
        out.append(dict(target_npv=tg, achievable=True, threshold=round(float(t), 4),
                        ruleout_rate=round(float(neg.mean()), 4),
                        npv=round(float((y[neg] == 0).mean()), 4) if neg.sum() else None,
                        time_critical_miss=round(float((neg & y_critical).sum() / max(1, y_critical.sum())), 4)
                        if y_critical is not None else None))
    return out


def l3_ruleout(prob, t):
    """True = 判定為『免疫介導腎絲球腎炎不太可能』（可 rule out）。"""
    return prob < t if t is not None else np.zeros_like(prob, dtype=bool)


# ---------------- L4 三驅動歸因排序 ----------------

def l4_attribute(X, Lam):
    A = nnls_attribution(X, Lam)
    return A, shares(A)


# ---------------- L5 混合旗標 ----------------

def l5_flags(sh, raw, ind_idx, X, markers, R=None):
    """回傳每人的旗標 list。混合旗標存在的理由：強制單一機轉會把重疊病理
    （狼瘡＋抗磷脂 TMA、膜性＋足細胞）壓成一個錯的單一答案。"""
    R = R or DET.rules()
    F = R["l5_flags"]
    n = sh.shape[0]
    order = np.argsort(-sh, axis=1)
    first = sh[np.arange(n), order[:, 0]]
    second = sh[np.arange(n), order[:, 1]]
    mixed = (second >= F["mixed_driver"]["second_share_min"]) & ((first - second) <= F["mixed_driver"]["gap_max"])

    pyu = X[:, ind_idx["pyuria"]]
    prot = X[:, ind_idx["proteinuria"]]
    cast = raw["rbc_cast"] > 0.5
    tin = (pyu >= F["TUBULOINTERSTITIAL_SUSPECT"]["pyuria_min"]) & \
          (prot <= F["TUBULOINTERSTITIAL_SUSPECT"]["proteinuria_max"]) & (~cast)
    sed = DET.active_sediment(raw, R["active_sediment"])
    vasc = (np.nan_to_num(raw["cr_slope_per_week"]) >= F["VASCULITIS_PRIORITY"]["cr_slope_per_week_min"]) & \
           sed & (prot <= F["VASCULITIS_PRIORITY"]["proteinuria_max"])
    pending = np.zeros(n, dtype=bool)
    for k, v in DET.pending_markers(markers).items():
        pending |= v

    flags = []
    for i in range(n):
        f = []
        if mixed[i]:
            f.append("MIXED_DRIVER")
        if tin[i]:
            f.append("TUBULOINTERSTITIAL_SUSPECT")
        if vasc[i]:
            f.append("VASCULITIS_PRIORITY")
        if pending[i]:
            f.append("SEROLOGY_PENDING")
        flags.append(f)
    return flags, dict(mixed=float(mixed.mean()), tin=float(tin.mean()),
                       vasculitis=float(vasc.mean()), pending=float(pending.mean()))


# ---------------- 串接 ----------------

def run(coh, seed=0, target_npv=None):
    """跑完五層，回傳彙總結果 dict。"""
    ind, Lam, drivers = spec()
    R = DET.rules()
    target_npv = target_npv if target_npv is not None else R["npv_targets"]["immune_gn_ruleout"]
    raw, markers = coh["raw"], coh["markers"]

    ok, qrep = l1_quality(raw)                                   # L1
    route, rule_id = DET.apply(raw, markers, R)                  # L2
    routed = (route != DET.NO_ROUTE) & ok
    residual = ok & ~routed                                      # L3-L5 的作用域

    X = transform_raw(raw, ind)
    ind_idx = {s["name"]: j for j, s in enumerate(ind)}
    Xr, yr = X[residual], coh["immune_gn"][residual].astype(int)

    A, sh = l4_attribute(Xr, Lam)                                # L4（先跑，L5 要用）
    raw_r = {k: v[residual] for k, v in raw.items()}
    flags, frep = l5_flags(sh, raw_r, ind_idx, Xr,
                           {k: v[residual] for k, v in markers.items()}, R)  # L5
    veto = DET.safety_override(raw_r, flags, R)                  # 決定性否決（單向）

    crit = (coh["time_critical"] & coh["immune_gn"])[residual]
    model, thr, oof = fit_l3(Xr, yr, target_npv, seed=seed, veto=veto, y_critical=crit,
                             crit_cap=R["npv_targets"]["time_critical_miss_cap"])   # L3
    ruled_out = l3_ruleout(oof, thr) & ~veto
    npv = float((yr[ruled_out] == 0).mean()) if ruled_out.sum() else float("nan")
    sens = float((~ruled_out & (yr == 1)).sum() / max(1, (yr == 1).sum()))
    cap = R["npv_targets"]["time_critical_miss_cap"]
    curve = ruleout_curve(oof, yr, veto, crit, cap)
    curve_npv_only = ruleout_curve(oof, yr, veto)          # 拿掉安全上限，單看盛行率效應
    # 三法則：k 個時效性個案裡 0 次漏判，漏判率的 95% 單側上界約 3/k。
    # 要「證明」漏判率 <= cap，時效性個案數必須 >= 3/cap —— 這條決定研究的樣本量，
    # 不是 AUROC 決定的。
    n_crit_required = int(np.ceil(3.0 / cap))

    l2_correct = float(np.mean([coh["label_names"][coh["label"][i]] == route[i]
                                for i in np.where(routed)[0]])) if routed.sum() else float("nan")
    return dict(
        n=len(ok), quality=qrep,
        l2=dict(routed_rate=float(routed.mean()), accuracy=l2_correct,
                by_rule={r["id"]: int((rule_id == r["id"]).sum()) for r in R["rules"]}),
        l3=dict(n=int(residual.sum()), threshold=thr, npv=npv, ruleout_rate=float(ruled_out.mean()),
                sensitivity=sens, prevalence=float(yr.mean()), target_npv=target_npv,
                veto_rate=float(veto.mean()), ruleout_curve=curve,
                ruleout_curve_npv_only=curve_npv_only,
                time_critical_n=int(crit.sum()), time_critical_miss_cap=cap,
                time_critical_n_required_rule_of_three=n_crit_required,
                safety_endpoint_powered=bool(crit.sum() >= n_crit_required)),
        l4=dict(driver_names=drivers, mean_shares=[float(v) for v in sh.mean(axis=0)]),
        l5=frep,
        _internal=dict(residual=residual, X=X, Xr=Xr, yr=yr, A=A, sh=sh, oof=oof, thr=thr,
                       flags=flags, model=model, ind=ind, Lam=Lam, ruled_out=ruled_out, veto=veto),
    )


def explain(coh, res, i_local, k=3):
    """對殘餘子集中的第 i_local 位病人產出可讀的歸因說明（附為什麼）。"""
    it = res["_internal"]
    ind, Lam = it["ind"], it["Lam"]
    a, x = it["A"][i_local], it["Xr"][i_local]
    sh = it["sh"][i_local]
    order = np.argsort(-sh)
    contrib = top_contributors(x, a, Lam, ind, k=k)
    return dict(
        ruled_out=bool(it["oof"][i_local] < (it["thr"] if it["thr"] is not None else 0.5)),
        ranking=[(res["l4"]["driver_names"][d], round(float(sh[d]), 3), contrib[d]) for d in order],
        flags=it["flags"][i_local],
    )
