# -*- coding: utf-8 -*-
"""合成世代：由組織型態標籤生成常規檢驗資料。

誠實聲明（鐵則 12）：
  本檔案生成的資料是「依文獻設定的機轉結構」造出來的，不是真實病人。
  它可以驗證：管線是否接得起來、閘門是否真的會擋、旋轉不確定性是否
  真的會毀掉歸因、逐人標準化是否真的會退化 —— 這幾件事要嘛是管線性質、
  要嘛是數學事實，用合成資料證明是有效的。
  它「不能」驗證：文獻 Lambda 是否正確、真實盛行率、真實 NPV。
  那些只有腎切片配對的真實世代能回答，見 results/assumptions.md 的待驗清單。

反循環設計：X 由 Lambda_true 生成後再加上「型態專屬偏移 offsets」與雜訊，
Lambda_true 預設等於文獻 Lambda 但 offsets 不在 Lambda 的張成空間裡，
所以 NNLS 拿回 a 不是把生成過程照抄回來 —— 這是刻意的模型誤設。
另有 --misspec 旋鈕直接擾動 Lambda_true，量測誤設下的退化曲線。
"""
import numpy as np

from attribution import invert_transform, load, spec

MARKERS = ("anti_gbm", "anca", "anti_pla2r", "maha_triad")
LEAKY = ("if_deposit_intensity", "crescent_pct", "true_anti_gbm", "true_anca",
         "true_pla2r", "immunosuppressant_started", "icd_group", "egfr_12m")


def _pattern_draw(P, rng, n, casemix="referral"):
    key = "prevalence" if casemix == "referral" else "prevalence_primary"
    names = [p["name"] for p in P["patterns"]]
    prev = np.array([p[key] for p in P["patterns"]], dtype=float)
    prev = prev / prev.sum()
    idx = rng.choice(len(names), size=n, p=prev)
    return idx, names


def simulate(seed, n=4000, misspec=0.0, misspec_mode="magnitude", casemix="referral"):
    """回傳 dict：raw（常規原始值）、label（組織型態）、A_true、markers、leaky、quality 標記。"""
    rng = np.random.default_rng(seed)
    P = load("patterns.json")
    ind, Lam, _ = spec()
    p_idx, names = _pattern_draw(P, rng, n, casemix)
    C, Q = P["context"], P["quality"]

    # 真實負載矩陣：預設＝文獻矩陣；misspec > 0 時乘上非負擾動（模擬文獻與真實的落差）
    Lam_true = Lam.copy()
    if misspec > 0 and misspec_mode == "magnitude":
        # 幅度誤設：文獻把權重估錯，但指標歸在哪個驅動是對的
        Lam_true = np.maximum(0.0, Lam * (1.0 + rng.normal(0, misspec, Lam.shape)))
    elif misspec > 0:
        # 結構誤設：一部分指標根本被歸錯驅動 —— 這才是會毀掉歸因的錯法
        Lam_true = Lam.copy()
        wrong = rng.random(Lam.shape[0]) < misspec
        for j in np.where(wrong)[0]:
            Lam_true[j] = Lam[j][rng.permutation(Lam.shape[1])]

    # 非典型表現：一部分病人的驅動輪廓抽自「別的型態」。臨床上真正難的就是這群
    # （IgA 腎病以腎病症候群表現、狼瘡腎炎以純足細胞病表現…）。組織型態仍是原本的，
    # 於是「表現機轉」與「組織標籤」被刻意解偶 —— L4 歸因的是前者，L3 判的是後者。
    atyp = rng.random(n) < C["atypical_frac"]
    prof_idx = p_idx.copy()
    prof_idx[atyp] = rng.integers(0, len(names), int(atyp.sum()))

    # 驅動振幅：輪廓專屬平均，截斷於 0（負的機轉量沒有意義）
    A = np.zeros((n, 3))
    for k, pat in enumerate(P["patterns"]):
        m = prof_idx == k
        A[m] = np.maximum(0.0, rng.normal(pat["driver_mean"], pat["driver_sd"], (int(m.sum()), 3)))

    # 每人整體嚴重度：同一個機轉可以很輕也可以很猛。這個乘數就是「絕對刻度」的來源，
    # 也正是逐人標準化會抹掉的東西（見 metrics.g4）。
    A = A * rng.lognormal(0.0, C["severity_log_sd"], (n, 1))

    X = A @ Lam_true.T
    # 型態專屬偏移：Lambda 抓不到的殘餘結構（間質、溶血、脂質…）＝刻意的誤設
    name_to_col = {s["name"]: j for j, s in enumerate(ind)}
    for k, pat in enumerate(P["patterns"]):
        m = p_idx == k
        for iname, off in pat["offsets"].items():
            X[m, name_to_col[iname]] += off
    X += rng.normal(0, C["noise_sd"], X.shape)

    # 既往常規檢驗面板：同一個機轉、較輕的嚴重度（疾病在進展）。
    # 只有縱向資料才驗得了「逐人標準化」的真正問題（見 metrics.g4）。
    prior = np.stack([A * np.exp(-C["prior_decay"] * k) * rng.lognormal(0, 0.15, (n, 1)) @ Lam_true.T
                      + rng.normal(0, C["noise_sd"], X.shape)
                      for k in range(C["n_prior_panels"], 0, -1)]) if C["n_prior_panels"] else None

    raw = invert_transform(X, ind, rng, jitter=0.03)

    # 病歷情境欄位
    age = np.clip(rng.normal(C["age_mean"], C["age_sd"], n), 18, 95)
    female = rng.random(n) < C["female_prob"]
    weeks = rng.integers(2, 13, n).astype(float)
    cr_base = np.clip(rng.normal(C["cr_baseline_mean"], C["cr_baseline_sd"], n), 0.5, 3.0)
    cr_now = cr_base + raw["cr_slope_per_week"] * weeks
    raw.update(age=age, female=female.astype(float), weeks_observed=weeks,
               cr_baseline=cr_base, cr_now=cr_now,
               days_since_last_panel=rng.integers(0, 8, n).astype(float))

    # 決定性標記：有沒有回來（available）與結果分開；沒回來 != 陰性
    mk, P_mk = {}, P["markers"]
    for name in MARKERS:
        cfg = P_mk[name]
        pos = np.full(n, cfg["spec_fp"])
        for pat_name, s in cfg["sens"].items():
            pos[p_idx == names.index(pat_name)] = s
        mk[name] = (rng.random(n) < pos).astype(float)
        mk[name + "_available"] = (rng.random(n) < P_mk["available_prob"]).astype(float)

    # M0 專用的洩漏特徵（切片所見、事後治療、編碼診斷、追蹤結果）
    leaky = {
        "if_deposit_intensity": np.clip(rng.normal(
            np.where(np.isin(p_idx, [names.index(x) for x in ("IC_PROLIF", "MEMBRANOUS")]), 2.6, 0.4), 0.5), 0, 3),
        "crescent_pct": np.clip(rng.normal(
            np.where(np.isin(p_idx, [names.index(x) for x in ("PAUCI_CRESCENTIC", "ANTI_GBM")]), 45, 3), 12), 0, 100),
        "true_anti_gbm": mk["anti_gbm"], "true_anca": mk["anca"], "true_pla2r": mk["anti_pla2r"],
        "immunosuppressant_started": (rng.random(n) < np.where(
            np.isin(p_idx, [names.index(x) for x in ("IC_PROLIF", "PAUCI_CRESCENTIC", "ANTI_GBM", "MEMBRANOUS")]),
            0.8, 0.15)).astype(float),
        "icd_group": np.where(rng.random(n) < 0.85, p_idx, rng.integers(0, len(names), n)).astype(float),
        "egfr_12m": np.clip(rng.normal(75 - 22 * A[:, 1] - 8 * A[:, 2], 12), 5, 130),
    }

    # 刻意注入資料缺陷，讓 L1 有東西可擋
    for f in Q["required_fields"]:
        m = rng.random(n) < Q["missing_rate_per_field"]
        raw[f] = np.where(m, np.nan, raw[f])
    unit_err = rng.random(n) < Q["unit_error_rate"]
    raw["cr_now"] = np.where(unit_err, raw["cr_now"] * 88.4, raw["cr_now"])  # umol/L 誤當 mg/dL
    stale = rng.random(n) < Q["stale_rate"]
    raw["days_since_last_panel"] = np.where(stale, rng.integers(15, 90, n), raw["days_since_last_panel"])

    return dict(raw=raw, X_true=X, A_true=A, prior_X=prior, label=p_idx, profile_idx=prof_idx, label_names=names,
                markers=mk, leaky=leaky, Lam_true=Lam_true,
                immune_gn=np.array([P["patterns"][k]["immune_gn"] for k in p_idx]),
                time_critical=np.array([P["patterns"][k]["time_critical"] for k in p_idx]))


def true_top_driver(coh):
    """真值的主導驅動＝該病人「表現輪廓」的 argmax（非典型者用抽到的那個輪廓，
    不是組織型態）。理由：L4 要回答的是「這個人身上現在由哪個機轉主導」，
    不是「這個組織型態通常由哪個機轉主導」—— 後者查書就好，不需要模型。
    用輪廓平均而非該病人的抽樣值，是為了避免把抽樣雜訊當成真值。"""
    P = load("patterns.json")
    prof = np.array([p["driver_mean"] for p in P["patterns"]])
    return prof[coh["profile_idx"]].argmax(axis=1)
