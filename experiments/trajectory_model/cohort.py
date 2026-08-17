# -*- coding: utf-8 -*-
"""模組零＋模組一：外部參數檔與合成世代生成器。

為什麼分成「參數檔 → 檢核 → 校準 → 生成」四步：參數檔讓每一個數字都有出處欄位
（建置提示詞 模組零），檢核把沒有出處或屬假設／校準的列印出來（決定書 補充指示 4），
校準只動決定書明說要反推的兩個量（delta_mu 中位數：§1；kappa：§3），其餘一律照抄。
"""
import json
import numpy as np
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from fade_components import MU_C, simulate_S0, apply_S2

X_FOLD = -1.0 / np.sqrt(3.0)          # 摺疊點座標：dV'/dx=0 → x=-1/sqrt(3)，對應 mu=MU_C
DAYS_PER_YEAR = 365.25


# ------------------------------------------------------------------ 參數檔
def _val(entry):
    """參數列可以是純數值，也可以是 {value, source, derived_from}。"""
    return entry["value"] if isinstance(entry, dict) and "value" in entry else entry


def load_params(path, verbose=True):
    with open(path, encoding="utf-8") as f:
        P = json.load(f)
    missing, derived = [], []

    def walk(node, trail):
        if isinstance(node, dict):
            if "value" in node or "share_raw" in node:
                if not node.get("source"):
                    missing.append(trail)
                if str(node.get("derived_from", "")).startswith(("assumption", "calibrated")):
                    derived.append((trail, node.get("derived_from"), node.get("value", node.get("share_raw"))))
            for k, v in node.items():
                if not k.startswith("_"):
                    walk(v, f"{trail}.{k}" if trail else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{trail}[{i}]")

    walk(P, "")
    if verbose:
        for m in missing:
            print(f"[警告] 參數列缺少出處：{m}")
        print("[參數檔] 非直接抄錄自文獻的數值（assumption / calibrated_*）：")
        for trail, how, val in derived:
            print(f"    {trail:55s} {how:35s} 現值={val}")
    P["_provenance"] = {"missing_source": missing,
                        "derived": [{"param": t, "derived_from": h, "value": v} for t, h, v in derived]}
    return P


# ------------------------------------------------------------------ 刻度與物理量
def lower_state(mu):
    """x^3 - x - mu = 0 的最小實根（mu < MU_C 時為健康穩態）。"""
    r = np.roots([1.0, 0.0, -1.0, -mu])
    return float(np.min(r[np.abs(r.imag) < 1e-9].real))


def derived_scale(P, tau=None):
    """決定書 §2 §4 §5：由錨點推出 x↔eGFR 映射、事件門檻、兩型雜訊參數。"""
    sc, fl, nz = P["scale"], P["flip"], P["noise"]
    tau = _val(fl["tau_days"]) if tau is None else tau
    mu0 = _val(fl["mu_start"])
    xL = lower_state(mu0)
    b = (_val(sc["egfr_at_healthy_state"]) - _val(sc["egfr_at_fold"])) / (X_FOLD - xL)
    a = _val(sc["egfr_at_healthy_state"]) + b * xL
    lam0 = 3.0 * xL ** 2 - 1.0                      # 健康態線性化回復率（單位 1/tau）
    sd_x = _val(nz["stationary_sd_egfr"]) / b
    tau_ou = _val(nz["tau_ou_days"])
    if tau_ou is None:
        tau_ou = tau / lam0                          # 使兩型 lag-1 自相關 exp(-lam0/tau) 相同
    return dict(a=a, b=b, x_event=(a - _val(sc["event_threshold_egfr"])) / b, x_fold=X_FOLD,
                x_healthy=xL, lambda0=lam0, tau=tau, tau_ou=tau_ou, sd_stat_x=sd_x,
                sigma_flip=sd_x * np.sqrt(2.0 * lam0 / tau),   # 線性化 OU 定態變異 = sigma^2 tau/(2 lam0)
                sigma_ou=sd_x * np.sqrt(2.0 / tau_ou),        # OU 定態變異 = sigma^2 tau_ou/2
                egfr_to_x=lambda e: (a - e) / b,
                slope_egfr_yr_to_x_day=lambda s: s / b / DAYS_PER_YEAR)


# ------------------------------------------------------------------ 生成
def draw_baseline(P, n, rng, kappa):
    """年齡、性別、易感度 s。s = kappa*u + sqrt(1-kappa^2)*eps，u 為年齡／性別的加權標準化組合。"""
    B = P["baseline"]
    age = np.clip(rng.normal(_val(B["age_mean"]), _val(B["age_sd"]), n), *B["age_range"])
    male = (rng.random(n) < _val(B["male_share"])).astype(int)
    w = B["susceptibility_weights"]
    z_age = (age - _val(B["age_mean"])) / _val(B["age_sd"])
    p = _val(B["male_share"])
    z_male = (male - p) / np.sqrt(p * (1 - p))
    u = (w["age"] * z_age + w["male"] * z_male) / np.hypot(w["age"], w["male"])
    s = kappa * u + np.sqrt(max(0.0, 1 - kappa ** 2)) * rng.normal(0, 1, n)
    return age, male, s


def _class_thresholds(share, beta):
    """找 theta_k 使 E_s[expit(theta_k - beta*s)] = 累積比例，讓邊際子類別比例仍等於 O'Hare 的值
    （否則 beta>0 會把人數推向斜率高的類別）。s ~ N(0,1) 用 Gauss–Hermite 積分。"""
    from scipy.optimize import brentq
    z, w = np.polynomial.hermite_e.hermegauss(40); w = w / w.sum()
    cum = np.cumsum(share)[:-1]
    return np.array([brentq(lambda th: np.sum(w * expit(th - beta * z)) - c, -20, 20) for c in cum])


def assign_linear_class(P, s, rng):
    """累積 logit：P(class<=k | s) = expit(theta_k - beta*s)，theta 由 O'Hare 比例決定。"""
    C = P["linear_classes"]["classes"]
    share = np.array([c["share_raw"] for c in C]); share = share / share.sum()
    beta = _val(P["baseline"]["class_link_beta"])
    theta = _class_thresholds(share, beta)
    cum = expit(theta[None, :] - beta * s[:, None])            # n × (K-1)
    u = rng.random(len(s))
    return (u[:, None] > cum).sum(axis=1)                       # 0..K-1


def simulate_linear(P, sc, cls, s, rng, T, substeps):
    """(甲) x = x0 + slope*t + eta，eta 為 OU（決定書 §4：不得用白雜訊）。"""
    C = P["linear_classes"]["classes"]
    n = len(cls)
    mode = _val(P["linear_classes"]["linear_start_mode"])
    if mode == "ohare_ranges":
        # 決定書 §1 字面：起始水準取 O'Hare 各類別範圍（= 透析前兩年的水準 → 幾乎全數在兩年內發生事件）
        lo = np.array([C[k]["egfr_start_range"][0] for k in cls]); hi = np.array([C[k]["egfr_start_range"][1] for k in cls])
    else:
        # 預設 kdigo_g2_g4_uniform：起始 eGFR 與子類別無關，均勻取自 KDIGO G2–G4（15–90）。
        # 為什麼：字面 O'Hare 起始水準使線性型 5 年事件率 ≈ 99%，靜態 C ≈ 0.97，違反決定書 §3 的
        # 0.65–0.75 校準目標且使 H2 在半個世代上無事可預測（規則 7：衝突攤開，擇一並標記）。
        rg = P["linear_classes"]["uniform_start_range_egfr"]
        lo = np.full(n, rg[0], dtype=float); hi = np.full(n, rg[1], dtype=float)
    egfr0 = rng.uniform(lo, hi)
    slope_egfr = rng.normal([C[k]["slope_mean"] for k in cls], [C[k]["slope_sd"] for k in cls])
    x0 = sc["egfr_to_x"](egfr0)
    slope = sc["slope_egfr_yr_to_x_day"](slope_egfr)          # eGFR 下降 → x 上升
    dt = 1.0 / substeps
    eta = rng.normal(0, sc["sd_stat_x"], n)                     # 由定態分布起始
    X = np.zeros((n, T), dtype=np.float32)
    for t in range(T):
        for _ in range(substeps):
            eta = eta - eta / sc["tau_ou"] * dt + sc["sigma_ou"] * np.sqrt(dt) * rng.normal(0, 1, n)
        X[:, t] = x0 + slope * (t + 1) + eta
    return X, x0, egfr0, slope, slope_egfr


def simulate_flip(P, sc, s, rng, T, substeps, delta_mu_median):
    """(乙) 雙穩態 SDE，複用 FADE simulate_S0（加 tau）。mu_end 由易感度決定（決定書 §3）。"""
    n = len(s)
    mu0 = _val(P["flip"]["mu_start"])
    dmu = delta_mu_median * np.exp(_val(P["flip"]["delta_mu_log_spread"]) * s)
    x0 = sc["x_healthy"] + rng.normal(0, sc["sd_stat_x"], n)
    X, t_crit, _, _ = simulate_S0(n=n, T=T, substeps=substeps, tau=sc["tau"], mu_start=mu0,
                                  mu_end=mu0 + dmu, sigma=np.full(n, sc["sigma_flip"]), x0=x0, rng=rng)
    return X, x0, mu0 + dmu, t_crit


def first_crossing(X, thr):
    """每列首次 >= thr 的索引；未跨過回傳 -1（右設限）。"""
    hit = X >= thr
    idx = hit.argmax(axis=1)
    return np.where(hit.any(axis=1), idx, -1)


def make_cohort(P, seed, n=None, tau=None, delta_mu_median=None, kappa=None, dropout=False):
    """產生一個世代。回傳 dict（全部 numpy 陣列＋衍生刻度）。"""
    S = P["sim"]
    n = S["n"] if n is None else n
    T, sub = S["T_days"], S["substeps"]
    sc = derived_scale(P, tau)
    kappa = _val(P["baseline"]["kappa"]) if kappa is None else kappa
    dmu = _val(P["flip"]["delta_mu_median"]) if delta_mu_median is None else delta_mu_median
    if kappa is None or dmu is None:
        raise ValueError("kappa / delta_mu_median 尚未校準（先呼叫 calibrate_*）")
    rng = np.random.default_rng(seed)

    age, male, s = draw_baseline(P, n, rng, kappa)
    is_flip = rng.random(n) < _val(S["flip_share"])
    X = np.zeros((n, T), dtype=np.float32)
    x0 = np.zeros(n); egfr0 = np.zeros(n); slope = np.full(n, np.nan); slope_egfr = np.full(n, np.nan)
    cls = np.full(n, -1); mu_end = np.full(n, np.nan); t_crit = np.full(n, -1)

    li = np.where(~is_flip)[0]
    if len(li):
        cls[li] = assign_linear_class(P, s[li], rng)
        X[li], x0[li], egfr0[li], slope[li], slope_egfr[li] = simulate_linear(P, sc, cls[li], s[li], rng, T, sub)
    fi = np.where(is_flip)[0]
    if len(fi):
        X[fi], x0[fi], mu_end[fi], t_crit[fi] = simulate_flip(P, sc, s[fi], rng, T, sub, dmu)
        egfr0[fi] = sc["a"] - sc["b"] * x0[fi]

    t_event = first_crossing(X, sc["x_event"])
    t_depart = np.where(is_flip, first_crossing(X, sc["x_fold"]), -1)
    C = dict(X=X, is_flip=is_flip, cls=cls, age=age, male=male, s=s, x0=x0, egfr0=egfr0,
             slope=slope, slope_egfr=slope_egfr, mu_end=mu_end, t_crit=t_crit, t_event=t_event,
             t_depart=t_depart, event=t_event >= 0, T=T, n=n, seed=seed, kappa=kappa,
             delta_mu_median=dmu, scale={k: v for k, v in sc.items() if not callable(v)})
    if dropout:
        # 決定書 §6：複用 FADE apply_S2 的退出邏輯（fill_rate=1、無延遲 → 只剩退出）。
        # 退出 = 停止記錄（觀測值變 NaN），結果事件仍已知（FADE 語意：S0 真實病理仍在）。
        X_obs, active = apply_S2(X, 1.0, _val(P["prediction"]["dropout_hazard"]), 0.0, 0, rng)
        C["X_obs"] = X_obs
        C["drop_day"] = np.where(active.all(axis=1), -1, (~active).argmax(axis=1))
    return C


def flip_timing_summary(C):
    """翻轉型三種時程（決定書 §1/§2 用來對照 O'Hare 災難型 <=6 個月）：
    t_event - t_crit（機制參考點起算）、t_event - t_depart（首次越過摺疊座標）、
    fall = t_event - 最後一次低於 x_fold 的日期（eGFR 60 → 15 的實際下墜時間）。"""
    f = C["is_flip"] & C["event"]
    out = dict(n_flip=int(C["is_flip"].sum()), n_flip_event=int(f.sum()),
               frac_flip_event=float(f.sum() / max(1, C["is_flip"].sum())))
    if f.sum() < 5:
        return out
    idx = np.where(f)[0]
    te, tc, td = C["t_event"][idx], C["t_crit"][idx], C["t_depart"][idx]
    xf = C["scale"]["x_fold"]
    fall = np.empty(len(idx))
    for j, i in enumerate(idx):
        below = np.where(C["X"][i, :te[j]] < xf)[0]
        fall[j] = te[j] - below[-1] if len(below) else np.nan

    def q(v):
        v = v[np.isfinite(v)]
        return dict(median=float(np.median(v)), q25=float(np.percentile(v, 25)), q75=float(np.percentile(v, 75)), n=int(len(v)))
    ok = tc >= 0
    out.update(event_minus_crit_days=q((te - tc)[ok].astype(float)), frac_event_with_crit=float(ok.mean()),
               event_minus_depart_days=q((te - td)[td >= 0].astype(float)), fall_days=q(fall))
    return out


# ------------------------------------------------------------------ 校準（決定書 §1、§3）
def calibrate_delta_mu(P, tau=None, target_days=None, seed=None, n_pilot=800, iters=14, verbose=True):
    """二分法找 delta_mu 中位數，使翻轉型 median(t_event - t_crit) = target。
    為什麼是這個量：決定書 §1 把『穩態偏離』操作化為 t_crit（機制參考點）。
    漂移愈快、鞍結延遲愈短（~ r^-1/3），故函數單調遞減，可二分。"""
    S = P["sim"]
    target = _val(P["flip"]["flip_time_target_days"]) if target_days is None else target_days
    seed = (S["seed"] + 1000) if seed is None else seed
    sc = derived_scale(P, tau)
    lo_b, hi_b = np.log(P["flip"]["delta_mu_bounds"])

    def timing(logm):
        rng = np.random.default_rng(seed)
        s = rng.normal(0, 1, n_pilot)
        X, _, _, tc = simulate_flip(P, sc, s, rng, S["T_days"], S["substeps"], np.exp(logm))
        te = first_crossing(X, sc["x_event"])
        ok = (tc >= 0) & (te >= 0)
        med = float(np.median(te[ok] - tc[ok])) if ok.sum() >= 20 else np.nan
        return med, float(ok.mean())

    # 先掃格點：延遲對漂移速率不一定單調（雜訊誘發的提早逃逸會讓 t_event 早於 t_crit），
    # 只有目標被相鄰兩格夾住時才二分，否則誠實回報不可行並退回預設，不硬湊。
    grid = np.linspace(lo_b, hi_b, 7)
    curve = [(float(np.exp(g)),) + timing(g) for g in grid]
    meds = np.array([c[1] for c in curve])
    best, feasible = None, False
    for i in range(len(grid) - 1):
        m0, m1 = meds[i], meds[i + 1]
        if np.isfinite(m0) and np.isfinite(m1) and (m0 - target) * (m1 - target) <= 0:
            lo, hi = grid[i], grid[i + 1]
            for _ in range(iters):
                mid = 0.5 * (lo + hi)
                gm, _ = timing(mid)
                if not np.isfinite(gm):
                    break
                if (gm - target) * (m0 - target) > 0:
                    lo = mid
                else:
                    hi = mid
            best, feasible = 0.5 * (lo + hi), True
            break
    if not feasible:
        # 退回 FADE 等價分布：mu_end ~ U(-0.10, 2.00) → delta_mu 中位 1.55（決定書 §10 複用來源）
        best = np.log(_val(P["flip"]["delta_mu_fallback_median"]))
    med, frac = timing(best)
    out = dict(delta_mu_median=float(np.exp(best)), achieved_median_days=med, target_days=float(target),
               frac_crossing=frac, feasible=feasible, tau=sc["tau"],
               derived_from="calibrated_to_catastrophic_class" if feasible else "fade_default_fallback",
               scan=[dict(delta_mu_median=m, median_event_minus_crit_days=d, frac_crossing=f) for m, d, f in curve])
    if verbose:
        tag = "" if feasible else "  ※ 目標在掃描範圍內不可達（見 scan），退回 FADE 等價 delta_mu，請裁決"
        print(f"[校準 delta_mu] tau={sc['tau']:g} 目標 {target:g} 天 → delta_mu 中位 {out['delta_mu_median']:.3f}，"
              f"實得中位(t_event-t_crit) {med:.0f} 天，跨臨界比例 {frac:.2f}{tag}")
    return out


def static_auc(C):
    """基線特徵 → 5 年事件的 in-sample AUC（只用於校準 kappa）。"""
    Xb = np.c_[C["age"], C["male"], C["x0"]]
    if C["event"].all() or not C["event"].any():
        return np.nan
    p = LogisticRegression(max_iter=1000).fit(Xb, C["event"]).predict_proba(Xb)[:, 1]
    return roc_auc_score(C["event"], p)


def calibrate_kappa(P, delta_mu_median, tau=None, seed=None, n_pilot=1500, iters=10, verbose=True):
    """二分法找 kappa 使靜態 C 指數落在目標區間中點（決定書 §3）。單調：kappa 越大基線越有資訊。"""
    S = P["sim"]
    seed = (S["seed"] + 1000) if seed is None else seed
    lo_t, hi_t = _val(P["baseline"]["static_c_target"])
    mid_t = 0.5 * (lo_t + hi_t)

    def auc(k):
        return static_auc(make_cohort(P, seed, n=n_pilot, tau=tau, delta_mu_median=delta_mu_median, kappa=k))

    a0, a1 = auc(0.0), auc(1.0)
    clamped = None
    if a0 > mid_t:
        clamped, best = "kappa=0 (baseline already too informative)", 0.0
    elif a1 < mid_t:
        clamped, best = "kappa=1 (target unreachable)", 1.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(iters):
            m = 0.5 * (lo + hi)
            if auc(m) < mid_t:
                lo = m
            else:
                hi = m
        best = 0.5 * (lo + hi)
    got = auc(best)
    out = dict(kappa=float(best), static_auc_pilot=float(got), target=[lo_t, hi_t],
               in_target=bool(lo_t <= got <= hi_t), clamped=clamped, auc_kappa0=float(a0), auc_kappa1=float(a1))
    if verbose:
        print(f"[校準 kappa] kappa={best:.3f} → pilot 靜態 C={got:.3f}（目標 {lo_t}–{hi_t}；kappa=0 時 {a0:.3f}、=1 時 {a1:.3f}）"
              + ("" if out["in_target"] else "  ※ 未落在目標區間，見 clamped"))
    return out
