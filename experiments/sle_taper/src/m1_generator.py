# -*- coding: utf-8 -*-
"""M1：合成世代生成器（SLE 減藥翻轉）。

動力學（指示 三之二）：dx = (1/τ)(−x³ + x + μ(t)) dt + ξ(t) dt，ξ 為 OU 有色雜訊
    dξ = −(1/τ_OU) ξ dt + σ√(2/τ_OU) dW   → 定態 SD = σ、相關時間 = τ_OU
    μ(t) = μ_intrinsic − g(t)，g 為免疫抑制的穩定效果，依減藥排程遞減（已知）
Euler–Maruyama，每日 10 子步，記錄每日值。

型別不是抽的：翻轉／穩定由 μ_intrinsic 與排程終點決定（μ_intrinsic − g_end > μ_c 者在減藥途中跨臨界）；
逐步惡化型（Ning 持續下降型 5.1%）為獨立慢性損傷群：x 自 t_onset 起線性上升＋同一 OU 雜訊，無雙穩態項
（與 CKD 版線性型同構；起始日與減藥同日以免「早期是否平坦」成為混淆，見 assumptions）。

觀測層與生成層分開：observe() 只產生看得到的版本，不改 X（tests 以雜湊比對）。
非侵入臂看到的活動度以各人自己的定態期平均置中（x_obs = x − mean_run_in(x) − 1），
因為臨床上「看起來一樣」指的是相對於自身緩解基線的變化，而模型的緩解固定點會隨 μ 微移。"""
import numpy as np

from m0_params import value


def lower_state(mu):
    """y³ − y − μ = 0 的最小實根（μ < μ_c 時為緩解穩態）。"""
    r = np.roots([1.0, 0.0, -1.0, -mu])
    return float(np.min(r[np.abs(r.imag) < 1e-9].real))


def ou_noise(n, T, tau_ou, sigma, rng, substeps=10):
    """OU 有色雜訊，回傳每日取樣的 (n, T)；內部每日 substeps 子步。定態 SD = sigma、相關時間 = tau_ou。"""
    dt = 1.0 / substeps
    xi = rng.normal(0.0, sigma, n)
    out = np.empty((n, T), dtype=np.float32)
    coef = sigma * np.sqrt(2.0 / tau_ou) * np.sqrt(dt)
    for t in range(T):
        for _ in range(substeps):
            xi = xi - xi / tau_ou * dt + coef * rng.normal(0.0, 1.0, n)
        out[:, t] = xi
    return out


def taper_schedule(t, spec):
    """g(t)：t < onset 為 g0；之後於 duration 天內線性降至 g0·(1−fraction_withdrawn)，再保持。
    spec = dict(g0, onset, duration_days, complete(bool) 或 residual_fraction)。"""
    t = np.asarray(t, dtype=float)
    g0, onset, dur = spec["g0"], spec["onset"], max(spec["duration_days"], 1)
    g_end = 0.0 if spec.get("complete", True) else g0 * spec.get("residual_fraction", 0.5)
    frac = np.clip((t - onset) / dur, 0.0, 1.0)
    return g0 + (g_end - g0) * frac


def _draw_baseline(Cj, n, rng):
    """基線臨床特徵（分布形狀來自 cohort.json）。"""
    out = {}
    for k, row in Cj["baseline_features"].items():
        d = row["dist"]
        if d == "lognormal":
            v = np.exp(np.log(row["median"]) + row["sigma_log"] * rng.normal(0, 1, n))
        elif d == "normal":
            v = rng.normal(row["mean"], row["sd"], n)
        elif d == "poisson":
            v = rng.poisson(row["lam"], n).astype(float)
        else:
            raise ValueError(d)
        out[k] = np.clip(v, *row["clip"])
    return out


def _susceptibility(Cj, feats, kappa, rng):
    """s = kappa·u + sqrt(1−kappa²)·ε，u 為加權標準化特徵和（再標準化）。"""
    L = Cj["susceptibility_link"]
    u = np.zeros(len(next(iter(feats.values()))))
    for k, w in L["weights"].items():
        v = np.log(feats[k]) if k in L.get("log_transform", []) else feats[k]
        z = (v - v.mean()) / (v.std() + 1e-12)
        u += w * z
    u = (u - u.mean()) / (u.std() + 1e-12)
    return kappa * u + np.sqrt(max(0.0, 1 - kappa ** 2)) * rng.normal(0, 1, len(u))


def hazard_events(X, lam0, beta, rng, t_start=0):
    """風險驅動事件（三之三）：λ(t) = λ0·exp(β·x(t))；逆變換法。回傳 (t_event, U)。
    t_start 之前不計風險（run-in 為觀察期）。"""
    U = rng.random(X.shape[0])
    lam = lam0 * np.exp(beta * X.astype(np.float64))
    lam[:, :t_start] = 0.0
    H = np.cumsum(lam, axis=1)
    hit = H >= (-np.log(U))[:, None]
    idx = hit.argmax(axis=1)
    return np.where(hit.any(axis=1), idx, -1), U


def events_from_U(X, lam0, beta, U, t_start=0):
    """同一世代、同一組 U 換 (λ0, β) 重算事件（校準與 G2 用，不必重生成序列）。"""
    lam = lam0 * np.exp(beta * X.astype(np.float64))
    lam[:, :t_start] = 0.0
    H = np.cumsum(lam, axis=1)
    hit = H >= (-np.log(U))[:, None]
    idx = hit.argmax(axis=1)
    return np.where(hit.any(axis=1), idx, -1)


def first_cross(X, thr, start=0):
    hit = X[:, start:] >= thr
    idx = hit.argmax(axis=1) + start
    return np.where(hit.any(axis=1), idx, -1)


def simulate_cohort(P, Cj, master_seed, n=None, tau=None, mu_mean=None, kappa=None, taper=None,
                    lam0=None, beta=None, substeps=10):
    """產生世代。P = thresholds、Cj = cohort.json。回傳 dict（全部 numpy 陣列＋設定）。"""
    from seeding import module_rng
    n = int(value(P, "N")) if n is None else n
    tau = float(value(P, "tau")) if tau is None else tau
    tau_ou = value(P, "tau_ou") or tau                                # null → 與 tau 同量級
    sigma = float(value(P, "sigma"))
    run_in, T = int(value(P, "run_in_days")), int(value(P, "T"))
    T_total = run_in + T
    mu_c = float(value(P, "mu_c"))
    dist = value(P, "mu_intrinsic_dist")
    mu_mean = dist["mean"] if mu_mean is None else mu_mean
    if mu_mean is None:
        raise ValueError("mu_intrinsic 平均尚未校準（步驟一）")
    kappa = float(value(P, "kappa")) if kappa is None else kappa
    hz = value(P, "hazard")
    lam0 = hz["lambda0_per_day"] if lam0 is None else lam0
    beta = hz["beta_per_x"] if beta is None else beta
    tp = value(P, "taper_schedule")                                   # 佔位（pending_extraction）
    taper = taper or {}
    spec = dict(g0=float(value(P, "g0")), onset=run_in, duration_days=taper.get("duration_days", tp["taper_duration_days"]),
                complete=taper.get("complete", tp["complete_withdrawal"]), residual_fraction=taper.get("residual_fraction", 0.5))

    rng_b = module_rng(master_seed, "generator", 0)
    rng_x = module_rng(master_seed, "generator", 1)
    rng_e = module_rng(master_seed, "generator", 2)
    rng_t = module_rng(master_seed, "generator", 3)

    feats = _draw_baseline(Cj, n, rng_b)
    s = _susceptibility(Cj, feats, kappa, rng_b)
    mu_intr = mu_mean + dist["sd"] * s
    is_grad = rng_t.random(n) < value(P, "traj_egfr_proportions")["persistent_decline"]   # Ning 5.1%（anchored）
    slope_x = value(P, "traj_slopes")["persistent_decline_x_per_year"] / 365.25            # 佔位（pending）
    sd_slope = value(P, "traj_slope_sd")["persistent_decline_x_per_year_sd"] / 365.25
    grad_slope = np.where(is_grad, rng_t.normal(slope_x, sd_slope, n), 0.0)

    t = np.arange(T_total)
    g = taper_schedule(t, spec)                                       # (T_total,)
    mu_path = mu_intr[:, None] - g[None, :]                           # (n, T_total)
    # 起點：各自的緩解固定點 + 小擾動
    xL = np.array([lower_state(m) for m in np.round(mu_path[:, 0], 3)])
    # sigma 定義為「緩解態 x 波動的定態 SD」（x 單位）。ξ 是被慢動力學積分的力：對線性化回復率 a=λ_lin/τ、
    # OU 相關時間 τ_OU，Var(x) = s_ξ²·τ_OU / (a(1 + a τ_OU))；由此反推 ξ 的振幅 s_ξ（以世代中位的 a 計）。
    a_ref = float(np.median(3.0 * xL ** 2 - 1.0)) / tau
    s_xi = sigma / np.sqrt(tau_ou / (a_ref * (1.0 + a_ref * tau_ou)))
    xi = ou_noise(n, T_total, tau_ou, s_xi, rng_x, substeps)           # 有色雜訊（每日值；子步內視為常數）
    x = xL + rng_x.normal(0, sigma * 0.5, n)
    X = np.empty((n, T_total), dtype=np.float32)
    dt = 1.0 / substeps
    # 逐步惡化型：無雙穩態項，改為對「線性上升的目標路徑」做線性回復（回復率取各自緩解固定點的線性化率
    # λ_lin = 3x_L² − 1 除以 τ，與翻轉型在緩解態的回復率相同 → 兩型定態期 AR(1) 可比，不會由雜訊結構洩漏型別）
    lam_lin = 3.0 * xL ** 2 - 1.0
    for k in range(T_total):
        mu_k = mu_path[:, k]
        target = xL + grad_slope * max(k - run_in, 0)
        for _ in range(substeps):
            drift = np.where(is_grad, lam_lin * (target - x) / tau, (-(x ** 3) + x + mu_k) / tau)
            x = x + (drift + xi[:, k]) * dt
        X[:, k] = x

    t_crit = np.full(n, -1)
    cross = mu_path >= mu_c
    has = cross.any(axis=1)
    t_crit[has] = cross[has].argmax(axis=1)
    t_crit[is_grad] = -1                                              # 逐步惡化型無分岔臨界日
    x_thr = value(P, "flare_definition_threshold")["x_threshold"]     # 佔位（pending）
    t_threshold = first_cross(X, x_thr, start=run_in)
    t_event, U = hazard_events(X, lam0, beta, rng_e, t_start=run_in)
    typ = np.where(is_grad, "gradual", np.where(t_crit >= 0, "flip", "stable"))
    return dict(X=X, mu_intrinsic=mu_intr, mu_path=mu_path.astype(np.float32), g=g.astype(np.float32),
                s=s, features=feats, is_gradual=is_grad, type=typ, t_onset=run_in, t_crit=t_crit,
                t_threshold=t_threshold, t_event=t_event, U=U, T=T_total, run_in=run_in, n=n,
                event=t_event >= 0, event_24m=(t_event >= 0) & (t_event < run_in + 730),
                event_52w=(t_event >= 0) & (t_event < run_in + 364),
                settings=dict(tau=tau, tau_ou=tau_ou, sigma=sigma, s_xi=float(s_xi), mu_mean=float(mu_mean), mu_sd=dist["sd"], kappa=kappa,
                              lam0=lam0, beta=beta, taper=spec, master_seed=master_seed))


def observe(X, run_in, interval_days, error_sd, rng):
    """觀測層：x_obs = x − mean_run_in(x) − 1（各人自身緩解基線置中）+ N(0, σ_meas²)，僅取樣日有值，其餘 NaN。
    不改 X。"""
    Xo = X.astype(np.float64) - X[:, :run_in].astype(np.float64).mean(axis=1, keepdims=True) - 1.0
    noise = rng.normal(0.0, error_sd, Xo.shape) if error_sd > 0 else 0.0
    Xo = Xo + noise
    mask = np.zeros(X.shape[1], bool)
    mask[::max(int(interval_days), 1)] = True
    Xo[:, ~mask] = np.nan
    return Xo.astype(np.float32)
