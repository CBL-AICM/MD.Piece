"""MD.Piece 復發引擎 × 真實公開縱向資料（NHANES I 追蹤研究 NHEFS、NIH/NHLBI Framingham 教學資料）。

分析計畫在跑資料前寫死於此（跑完不回頭改門檻或權重）：

A. NHEFS（CDC/NCHS，NHANES I 1971–75 基線，1982–92 四波追蹤，含每次住院日期與 ICD-9-CM 診斷）
   - 對象：≥18 歲（NHEFS 基線本就 25–74 歲）男女；住院病歷摘要完整（record status MAT/ASF/CRM、
     入院年月齊全）；以「首次在任一診斷欄出現該病」的住院當確診索引日；索引後追蹤 ≥3 年，最多取 10 年。
   - 疾病（常見復發型慢性病）：COPD/氣喘 490–496、心衰竭 428、缺血性心臟病 410–414、糖尿病 250。
   - 復發 = 索引後 >30 天、以該病為「主診斷」的再住院；相隔 <30 天視為同一次。
   - 預測時點：索引後每滿 1 年設一個 landmark；預測「未來 12 個月內是否復發」；
     12 個月內死亡且未復發者，該 landmark 觀察不完整，不納入二元分析（存活分析另計）。
   - MD.Piece 引擎原封不動（backend/utils/recurrence.risk_from），只做時間壓縮橋接：
     1 引擎日 = 365.25/14 真實日 → 引擎「近 14 天 vs 第 15–60 天」= 真實「近 12 個月 vs 前 1–4.3 年」，
     引擎「未來 14 天」= 真實「未來 12 個月」。
     住院紀錄 → medical_records（就診 / 急性事件）；含該病診斷的住院 → symptoms_log（疾病活動紀錄）。
     疾病錨 band 依文獻分級事先指定（下方 DISEASES），不以本資料調整。
   - 對照：只用年齡性別（無紀錄）、只用近 12 個月紀錄、加入長期紀錄（索引前後全部歷史）三個 logistic，
     依患者分組 5 折交叉驗證；AUROC 以患者為單位 bootstrap 1000 次給 95% CI。
   - 發病時機：第 1 個 landmark 的引擎 band 分組，畫 Kaplan–Meier 首次復發曲線、log-rank、Cox HR。

B. Framingham 教學資料（NIH/NHLBI，三次檢查約隔 6 年，追蹤 24 年）
   - 對象：第 1 次檢查已有高血壓、第 1、2 次檢查皆到且血壓/膽固醇/血糖/BMI 完整、第 2 次檢查前無心血管事件；
     第 2 次檢查後觀察 ≥3 年（或期間發生事件）；最多取 10 年。
   - 結果：心血管事件（CVD）發生時機。引擎以檢驗列（異常=收縮壓≥140、舒張壓≥90、總膽固醇≥240、
     血糖≥126、BMI≥30）計分；1 引擎日 = 3×365.25/14 真實日，近期窗只含第 2 次檢查。
   - 對照：單次檢查（第 2 次）vs 兩次檢查（加入第 1→2 次變化）的 logistic（10 年內 CVD）。
   - 注意：NHLBI 教學資料經去識別擾動，官方說明不適合正式發表，只作教學與方法示範。

跑法： PYTHONPATH=. python experiments/chronic_recurrence_longitudinal/run.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

from backend.utils import recurrence  # noqa: E402

RAW = os.path.join(HERE, "data_raw")
OUT = os.path.join(HERE, "outputs")
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(2026)
YEAR = timedelta(days=365.25)

DISEASES = {  # key: (中文名, ICD-9 前三碼, 文獻復發 band)
    "copd_asthma": ("COPD／氣喘", {str(c) for c in range(490, 497)}, "high"),
    "heart_failure": ("心衰竭", {"428"}, "high"),
    "ihd": ("缺血性心臟病", {"410", "411", "412", "413", "414"}, "medium"),
    "diabetes": ("糖尿病", {"250"}, "medium"),
}
DRIVERS = [
    {"maps_to": "visits", "weight": "high", "evidence": "近一年住院次數增加為再住院的已知前兆（橋接：任何住院）。"},
    {"maps_to": "symptoms", "weight": "high", "evidence": "該病相關住院變頻繁代表疾病活動上升（橋接：含該病診斷的住院）。"},
    {"maps_to": "labs", "weight": "high", "evidence": "血壓、膽固醇、血糖、肥胖為心血管事件的經典風險因子（Framingham）。"},
]
EPOCH = datetime(1950, 1, 1)


def compress(d, k):
    """真實日期 → 引擎時間（壓縮 k 倍），引擎常數不動。"""
    d = d if isinstance(d, datetime) else datetime(d.year, d.month, d.day)
    return EPOCH + (d - EPOCH) / k


def ctx(band):
    return {"disease_name": "", "recurrence": {"band": band, "drivers": DRIVERS}}


def boot_auc(y, s, groups, n=1000):
    y, s, groups = np.asarray(y), np.asarray(s), np.asarray(groups)
    ug = np.unique(groups)
    idx = {g: np.where(groups == g)[0] for g in ug}
    vals = []
    for _ in range(n):
        pick = np.concatenate([idx[g] for g in RNG.choice(ug, len(ug))])
        if y[pick].min() != y[pick].max():
            vals.append(roc_auc_score(y[pick], s[pick]))
    return roc_auc_score(y, s), np.percentile(vals, 2.5), np.percentile(vals, 97.5)


def cv_scores(df, cols, y, groups):
    pred = np.zeros(len(df))
    for tr, te in GroupKFold(5).split(df, y, groups):
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
        m.fit(df.iloc[tr][cols], y[tr])
        pred[te] = m.predict_proba(df.iloc[te][cols])[:, 1]
    return pred


# ═════════════════════════ A. NHEFS ═════════════════════════
def _d(mo, dy, yr, century=1900):
    try:
        y, m = int(yr), int(mo)
    except ValueError:
        return None
    if not 1 <= m <= 12:
        m = 7
    try:
        d = int(dy)
    except ValueError:
        d = 15
    return date(century + y if y < 100 else y, m, min(max(d, 1), 28))


def load_nhefs():
    stays = []
    for f in ("n82hcfs.txt", "n86hcfs.txt", "n87hcfs.txt", "n92hcfs.txt", "n92hcfsp.txt"):
        for line in open(os.path.join(RAW, f), encoding="latin-1"):
            L = line.rstrip("\r\n").ljust(430)
            if L[59:62] not in ("MAT", "ASF", "CRM"):        # 只收有病歷摘要（日期+ICD 完整）的住院
                continue
            if not L[209:211].strip() or not L[213:215].strip():
                continue
            adm = _d(L[209:211], L[211:213], L[213:215])
            if adm is None:
                continue
            dx = [L[239 + 11 * i:245 + 11 * i][1:4].strip() for i in range(10)]
            stays.append({"seq": L[0:5], "adm": adm, "fac": L[208],
                          "prin": dx[0], "dx": "|".join(x for x in dx if x)})
    h = pd.DataFrame(stays).drop_duplicates(["seq", "adm", "fac"]).sort_values(["seq", "adm"])

    vit = []
    for line in open(os.path.join(RAW, "n92vitl.txt"), encoding="latin-1"):
        L = line.rstrip("\r\n").ljust(230)
        exam = _d(L[32:34], L[34:36], L[36:38])
        dead = L[16] == "3"
        end = _d(L[60:62], L[62:64], L[64:66]) if dead else _d(L[17:19], L[19:21], L[21:23])
        try:
            byear = int(L[28:32])
        except ValueError:
            byear = None
        vit.append({"seq": L[11:16], "sex": {"1": "男", "2": "女"}.get(L[45], ""),
                    "byear": byear, "exam": exam, "dead": dead, "end": end})
    return h, pd.DataFrame(vit).set_index("seq")


def episodes(dates, gap=30):
    out = []
    for d in sorted(dates):
        if not out or (d - out[-1]).days > gap:
            out.append(d)
    return out


def run_nhefs():
    h, vit = load_nhefs()
    hosp = h[h.fac == "1"]
    flow, subjects, events, lms = [], [], [], []
    for key, (zh, codes, band) in DISEASES.items():
        has = hosp[hosp.dx.str.split("|").apply(lambda xs: any(x in codes for x in xs))]
        idx = has.groupby("seq").adm.min()
        f = {"disease": zh, "確診住院人數": len(idx)}
        keep = []
        for seq, index in idx.items():
            if seq not in vit.index:
                continue
            v = vit.loc[seq]
            if v.byear is None or not v.sex or v.end is None:
                continue
            age = index.year - v.byear
            fu_end = min(v.end, index + 10 * YEAR)
            fu = (fu_end - index).days / 365.25
            keep.append((seq, index, age, v, fu_end, fu))
        f["人口資料完整"] = len(keep)
        keep = [k for k in keep if k[2] >= 18]
        f["≥18歲"] = len(keep)
        keep = [k for k in keep if k[5] >= 3]
        f["追蹤≥3年（納入）"] = len(keep)
        flow.append(f)

        for seq, index, age, v, fu_end, fu in keep:
            mine = h[h.seq == seq]
            rec = [d for d in episodes(mine[(mine.fac == "1") & mine.prin.isin(codes)].adm)
                   if (d - index).days > 30 and d <= fu_end]
            for d in rec:
                events.append({"SEQNUM": seq, "疾病": zh, "復發住院日": d.isoformat(),
                               "距確診年": round((d - index).days / 365.25, 2)})
            subjects.append({"SEQNUM": seq, "疾病": zh, "性別": v.sex, "確診時年齡": age,
                             "確診住院日": index.isoformat(), "追蹤結束日": fu_end.isoformat(),
                             "追蹤年數": round(fu, 2), "結束原因": "死亡" if (v.dead and fu_end == v.end) else ("滿10年" if fu >= 9.999 else "最後確認存活"),
                             "復發次數": len(rec),
                             "首次復發距確診年": round((rec[0] - index).days / 365.25, 2) if rec else None})
            med = [{"visit_date": compress(r.adm, 365.25 / 14).strftime("%Y-%m-%d %H:%M:%S"), "diagnosis": r.dx}
                   for r in mine.itertuples()]
            sym = [{"created_at": compress(r.adm, 365.25 / 14).strftime("%Y-%m-%d %H:%M:%S")}
                   for r in mine.itertuples() if r.fac == "1" and any(x in codes for x in r.dx.split("|"))]
            sources = {"medical_records": med, "symptoms_log": sym, "_context": ctx(band)}
            for j in range(1, 10):
                L = index + j * YEAR
                nxt = [d for d in rec if L < d <= L + YEAR]
                if L >= fu_end or (L + YEAR > fu_end and not nxt):
                    break
                score, factors = recurrence.risk_from(sources, compress(L, 365.25 / 14))
                prior = mine[mine.adm <= L]
                lms.append({
                    "SEQNUM": seq, "疾病": zh, "disease": key, "landmark_year": j, "性別": v.sex,
                    "age": L.year - v.byear, "male": int(v.sex == "男"),
                    "engine_risk": round(score, 4), "engine_band": recurrence._band_for(score),
                    "top_factor": max(factors, key=lambda x: x["value"])["plain_text"] if factors else "",
                    "stays_12m": int((prior.adm > L - YEAR).sum()),
                    "dz_stays_12m": int(sum(1 for d in sym_dates(prior, codes) if d > L - YEAR)),
                    "stays_1to5y": int(((prior.adm <= L - YEAR) & (prior.adm > L - 5 * YEAR)).sum()),
                    "dz_stays_1to5y": int(sum(1 for d in sym_dates(prior, codes) if L - 5 * YEAR < d <= L - YEAR)),
                    "stays_before_index": int((prior.adm < index).sum()),
                    "prior_recurrences": sum(1 for d in rec if d <= L),
                    "years_since_index": j,
                    "y": int(bool(nxt)),
                })
    return pd.DataFrame(flow), pd.DataFrame(subjects), pd.DataFrame(events), pd.DataFrame(lms)


def sym_dates(prior, codes):
    return [r.adm for r in prior.itertuples() if r.fac == "1" and any(x in codes for x in r.dx.split("|"))]


# ═════════════════════════ B. Framingham ═════════════════════════
LAB_RULES = [("SYSBP", 140, "收縮壓"), ("DIABP", 90, "舒張壓"), ("TOTCHOL", 240, "總膽固醇"),
             ("GLUCOSE", 126, "血糖"), ("BMI", 30, "BMI")]


def run_framingham():
    import pyreadr
    df = list(pyreadr.read_r(os.path.join(RAW, "framingham.rda")).values())[0]
    need = [c for c, _, _ in LAB_RULES]
    p1, p2 = df[df.PERIOD == 1].set_index("RANDID"), df[df.PERIOD == 2].set_index("RANDID")
    flow = {"第1次檢查人數": len(p1)}
    ids = p1.index[(p1.PREVHYP == 1) & (p1.AGE >= 18)]
    flow["第1次已有高血壓且≥18歲"] = len(ids)
    ids = [i for i in ids if i in p2.index]
    flow["第2次檢查有到"] = len(ids)
    ids = [i for i in ids if p1.loc[i, need].notna().all() and p2.loc[i, need].notna().all()]
    flow["兩次檢查數值完整"] = len(ids)
    ids = [i for i in ids if p2.loc[i, "PREVCHD"] == 0 and p2.loc[i, "PREVSTRK"] == 0
           and p2.loc[i, "TIMECVD"] > p2.loc[i, "TIME"]]
    flow["第2次檢查前無心血管事件"] = len(ids)
    rows = []
    k = 3 * 365.25 / 14
    for i in ids:
        a, b = p1.loc[i], p2.loc[i]
        t2 = b.TIME
        t_event = b.TIMECVD - t2 if b.CVD == 1 else None
        t_cens = min(b.TIMEDTH, 8766) - t2
        obs = min(t_event if t_event is not None else 1e9, t_cens, 3652.5)
        evt = int(t_event is not None and t_event <= min(t_cens, 3652.5))
        if not evt and t_cens < 3 * 365.25:
            continue
        labs = []
        for exam, t in ((a, 0), (b, t2)):
            for col, cut, _ in LAB_RULES:
                labs.append({"created_at": compress(EPOCH + timedelta(days=float(t)), k).strftime("%Y-%m-%d %H:%M:%S"),
                             "status": "high" if exam[col] >= cut else "normal"})
        score, factors = recurrence.risk_from({"labs": labs, "_context": ctx("medium")},
                                              compress(EPOCH + timedelta(days=float(t2)), k))
        r = {"RANDID": int(i), "性別": "男" if b.SEX == 1 else "女", "年齡_第2次": int(b.AGE),
             "engine_risk": round(score, 4), "engine_band": recurrence._band_for(score),
             "abn_count_exam2": sum(int(b[c] >= cut) for c, cut, _ in LAB_RULES),
             "time_years": round(obs / 365.25, 3), "event": evt,
             "y10": evt if (evt or t_cens >= 3652.5) else None, "male": int(b.SEX == 1),
             "CURSMOKE": int(b.CURSMOKE), "BPMEDS": b.BPMEDS if pd.notna(b.BPMEDS) else 0}
        for c in need:
            r[c + "_2"], r[c + "_1"] = float(b[c]), float(a[c])
            r[c + "_delta"] = float(b[c] - a[c])
        rows.append(r)
    flow["第2次檢查後觀察≥3年或發生事件（納入）"] = len(rows)
    return flow, pd.DataFrame(rows)


# ═════════════════════════ 分析 + 圖 ═════════════════════════
def analyze():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from lifelines import CoxPHFitter, KaplanMeierFitter
    from lifelines.statistics import multivariate_logrank_test
    plt.rcParams["font.family"] = ["Microsoft JhengHei"]
    plt.rcParams["axes.unicode_minus"] = False
    res = {}

    flow, subj, ev, lm = run_nhefs()
    subj.to_csv(os.path.join(OUT, "nhefs_納入對象原始名單.csv"), index=False, encoding="utf-8-sig")
    ev.to_csv(os.path.join(OUT, "nhefs_復發住院事件清單.csv"), index=False, encoding="utf-8-sig")
    lm.to_csv(os.path.join(OUT, "nhefs_landmark_預測紀錄.csv"), index=False, encoding="utf-8-sig")
    flow.to_csv(os.path.join(OUT, "nhefs_篩選流程.csv"), index=False, encoding="utf-8-sig")
    res["nhefs_flow"] = flow.to_dict("records")
    res["nhefs_subjects"] = {"n": int(subj.SEQNUM.nunique()), "patient_disease_rows": len(subj),
                             "male": int((subj.drop_duplicates("SEQNUM").性別 == "男").sum()),
                             "age_mean": round(subj.確診時年齡.mean(), 1), "age_sd": round(subj.確診時年齡.std(), 1),
                             "fu_mean": round(subj.追蹤年數.mean(), 2), "fu_median": round(subj.追蹤年數.median(), 2),
                             "fu_ge5": int((subj.追蹤年數 >= 5).sum()), "fu_10": int((subj.追蹤年數 >= 9.999).sum()),
                             "any_recurrence": int((subj.復發次數 > 0).sum()), "events": len(ev)}
    res["nhefs_landmarks"] = {"n": len(lm), "events": int(lm.y.sum()), "rate": round(lm.y.mean(), 4)}

    y, g = lm.y.values, lm.SEQNUM.values
    dz = pd.get_dummies(lm.disease, prefix="dz", dtype=float)
    X = pd.concat([lm, dz], axis=1)
    sets = {
        "無紀錄（年齡+性別+病別）": ["age", "male"] + list(dz.columns),
        "只用近12個月紀錄": ["age", "male"] + list(dz.columns) + ["stays_12m", "dz_stays_12m"],
        "加入長期紀錄": ["age", "male"] + list(dz.columns) + ["stays_12m", "dz_stays_12m", "stays_1to5y",
                                                             "dz_stays_1to5y", "stays_before_index",
                                                             "prior_recurrences", "years_since_index"],
    }
    aucs = {"MD.Piece 引擎（未訓練、原規則）": boot_auc(y, lm.engine_risk.values, g)}
    preds = {}
    for name, cols in sets.items():
        preds[name] = cv_scores(X, cols, y, g)
        aucs[name] = boot_auc(y, preds[name], g)
    res["nhefs_auc"] = {k: [round(v, 3) for v in t] for k, t in aucs.items()}
    # 長期 − 近期 的 AUROC 差（患者層 bootstrap）
    ug = np.unique(g); gi = {x: np.where(g == x)[0] for x in ug}; diffs = []
    for _ in range(1000):
        p = np.concatenate([gi[x] for x in RNG.choice(ug, len(ug))])
        if y[p].min() != y[p].max():
            diffs.append(roc_auc_score(y[p], preds["加入長期紀錄"][p]) - roc_auc_score(y[p], preds["只用近12個月紀錄"][p]))
    res["nhefs_longterm_minus_recent"] = [round(np.mean(diffs), 3), round(np.percentile(diffs, 2.5), 3),
                                          round(np.percentile(diffs, 97.5), 3)]
    per = {}
    for key, (zh, _, _) in DISEASES.items():
        m = lm.disease == key
        per[zh] = {"landmarks": int(m.sum()), "patients": int(lm[m].SEQNUM.nunique()), "events": int(lm[m].y.sum()),
                   "rate": round(lm[m].y.mean(), 3),
                   "engine_auc": [round(v, 3) for v in boot_auc(y[m], lm[m].engine_risk.values, g[m])],
                   "longterm_auc": [round(v, 3) for v in boot_auc(y[m], preds["加入長期紀錄"][m], g[m])]}
    res["nhefs_per_disease"] = per
    band = lm.groupby("engine_band").y.agg(["size", "mean"]).reindex(["low", "medium", "high"])
    res["nhefs_band"] = {b: {"n": int(r["size"]), "rate": round(r["mean"], 3)} for b, r in band.iterrows() if pd.notna(r["size"])}
    q = pd.qcut(preds["加入長期紀錄"], 5, labels=False, duplicates="drop")
    res["nhefs_longterm_quintile_rate"] = [round(v, 3) for v in lm.groupby(q).y.mean().values]

    # 首次 landmark 的 band → 首次復發時間（發病時機）
    first = lm.assign(lt_risk=preds["加入長期紀錄"])[lambda d: d.landmark_year == 1].merge(subj, on=["SEQNUM", "疾病"])
    # 第 1 年 landmark 之後的「下一次」復發（第 1 年內已復發者，往後找下一次）
    nxt = ev[ev.距確診年 > 1].groupby(["SEQNUM", "疾病"]).距確診年.min().rename("next_rec").reset_index()
    first = first.merge(nxt, on=["SEQNUM", "疾病"], how="left")
    first["t"] = first.next_rec.fillna(first.追蹤年數) - 1
    first["e"] = first.next_rec.notna().astype(int)
    first = first[first.t > 0]
    lr = multivariate_logrank_test(first.t, first.engine_band, first.e)
    cph = CoxPHFitter().fit(pd.DataFrame({"t": first.t, "e": first.e, "band_level": first.engine_band.map({"low": 0, "medium": 1, "high": 2})}), "t", "e")
    res["nhefs_km"] = {"n": len(first), "logrank_p": float(lr.p_value),
                       "hr_per_band": [round(float(np.exp(cph.params_["band_level"])), 2),
                                       round(float(np.exp(cph.confidence_intervals_.iloc[0, 0])), 2),
                                       round(float(np.exp(cph.confidence_intervals_.iloc[0, 1])), 2)]}

    # 事後探索（非事前計畫）：以長期紀錄模型（交叉驗證外樣本預測）第 1 年風險三分位看復發時機
    first["lt_tertile"] = pd.qcut(first.lt_risk, 3, labels=["低", "中", "高"])
    lr_lt = multivariate_logrank_test(first.t, first.lt_tertile, first.e)
    res["nhefs_km_longterm_tertile_exploratory"] = {
        "logrank_p": float(lr_lt.p_value),
        "rate_by_tertile": first.groupby("lt_tertile", observed=True).e.mean().round(3).to_dict(),
        "median_years_to_recurrence_or_censor": first.groupby("lt_tertile", observed=True).t.median().round(2).to_dict()}

    # ── Framingham ──
    fflow, fr = run_framingham()
    fr.to_csv(os.path.join(OUT, "framingham_納入對象原始名單.csv"), index=False, encoding="utf-8-sig")
    res["fram_flow"] = fflow
    res["fram"] = {"n": len(fr), "male": int(fr.male.sum()), "age_mean": round(fr.年齡_第2次.mean(), 1),
                   "events": int(fr.event.sum()), "fu_median": round(fr.time_years.median(), 2)}
    f10 = fr[fr.y10.notna()].reset_index(drop=True)
    yf, gf = f10.y10.astype(int).values, f10.RANDID.values
    base = ["年齡_第2次", "male", "CURSMOKE", "BPMEDS"]
    snap = base + [c + "_2" for c, _, _ in LAB_RULES]
    longi = snap + [c + "_delta" for c, _, _ in LAB_RULES]
    fa = {"MD.Piece 引擎（未訓練、原規則）": boot_auc(yf, f10.engine_risk.values, gf)}
    fp = {}
    for name, cols in {"只用年齡性別抽菸用藥": base, "單次檢查（第2次）": snap, "兩次檢查（加入變化量）": longi}.items():
        fp[name] = cv_scores(f10, cols, yf, gf)
        fa[name] = boot_auc(yf, fp[name], gf)
    res["fram_auc"] = {k: [round(v, 3) for v in t] for k, t in fa.items()}
    res["fram_n10"] = {"n": len(f10), "events": int(yf.sum())}
    flr = multivariate_logrank_test(fr.time_years, fr.engine_band, fr.event)
    fcph = CoxPHFitter().fit(pd.DataFrame({"t": fr.time_years, "e": fr.event, "abn": fr.abn_count_exam2}), "t", "e")
    res["fram_km"] = {"logrank_p": float(flr.p_value),
                      "hr_per_abnormal_item": [round(float(np.exp(fcph.params_["abn"])), 2),
                                               round(float(np.exp(fcph.confidence_intervals_.iloc[0, 0])), 2),
                                               round(float(np.exp(fcph.confidence_intervals_.iloc[0, 1])), 2)],
                      "band_n": fr.engine_band.value_counts().to_dict(),
                      "band_rate": fr.groupby("engine_band").event.mean().round(3).to_dict()}

    # ── 圖 ──
    from sklearn.metrics import roc_curve
    fig, ax = plt.subplots(figsize=(6.2, 5))
    for name, s in [("MD.Piece 引擎（未訓練、原規則）", lm.engine_risk.values)] + list(preds.items()):
        fpr, tpr, _ = roc_curve(y, s)
        ax.plot(fpr, tpr, label=f"{name}  AUROC {aucs[name][0]:.2f}")
    ax.plot([0, 1], [0, 1], ls=":", c="grey")
    ax.set_xlabel("偽陽性率"); ax.set_ylabel("真陽性率"); ax.set_title("NHEFS 未來12個月復發預測 ROC")
    ax.legend(fontsize=8, loc="lower right"); fig.tight_layout(); fig.savefig(os.path.join(OUT, "figA_nhefs_roc.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    km = KaplanMeierFitter()
    names = {"low": "穩定（low）", "medium": "中度關注（medium）", "high": "較需留意（high）"}
    for b in ("low", "medium", "high"):
        m = first.engine_band == b
        if m.sum() >= 5:
            km.fit(first.t[m], first.e[m], label=f"{names[b]} n={int(m.sum())}")
            km.plot_cumulative_density(ax=ax, ci_show=False)
    ax.set_xlabel("確診滿1年後經過年數"); ax.set_ylabel("累積復發比例"); ax.set_title(f"引擎分級與確診滿1年後的下一次復發時機（log-rank p={lr.p_value:.3g}）")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "figB_nhefs_km.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4))
    names_d = list(per.keys())
    xs = np.arange(len(names_d))
    e = [per[d]["engine_auc"] for d in names_d]; l = [per[d]["longterm_auc"] for d in names_d]
    ax.bar(xs - 0.18, [v[0] for v in e], 0.36, yerr=[[v[0] - v[1] for v in e], [v[2] - v[0] for v in e]], label="MD.Piece 引擎", capsize=3)
    ax.bar(xs + 0.18, [v[0] for v in l], 0.36, yerr=[[v[0] - v[1] for v in l], [v[2] - v[0] for v in l]], label="加入長期紀錄模型", capsize=3)
    ax.axhline(0.5, ls=":", c="grey"); ax.set_xticks(xs); ax.set_xticklabels(names_d); ax.set_ylim(0.3, 1)
    ax.set_ylabel("AUROC（95% CI）"); ax.set_title("四種慢性病的復發預測鑑別力"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "figC_nhefs_per_disease.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    qs = res["nhefs_longterm_quintile_rate"]
    ax.bar(range(1, len(qs) + 1), [v * 100 for v in qs], color="#4a7bb7")
    for i, v in enumerate(qs):
        ax.text(i + 1, v * 100 + 0.5, f"{v*100:.1f}%", ha="center", fontsize=9)
    ax.set_xlabel("長期紀錄模型預測風險五分位（1 最低 → 5 最高）"); ax.set_ylabel("實際12個月復發率（%）")
    ax.set_title("預測風險分組與實際復發率"); fig.tight_layout(); fig.savefig(os.path.join(OUT, "figD_nhefs_quintile.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for b in ("low", "medium", "high"):
        m = fr.engine_band == b
        if m.sum() >= 5:
            km.fit(fr.time_years[m], fr.event[m], label=f"{names[b]} n={int(m.sum())}")
            km.plot_cumulative_density(ax=ax, ci_show=False)
    ax.set_xlabel("第2次檢查後經過年數"); ax.set_ylabel("累積心血管事件比例")
    ax.set_title(f"Framingham 高血壓者：引擎分級與發病時機（p={flr.p_value:.3g}）")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "figE_framingham_km.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    for t_ in ("低", "中", "高"):
        m = first.lt_tertile == t_
        km.fit(first.t[m], first.e[m], label=f"長期紀錄風險{t_}三分之一 n={int(m.sum())}")
        km.plot_cumulative_density(ax=ax, ci_show=False)
    ax.set_xlabel("確診滿1年後經過年數"); ax.set_ylabel("累積復發比例")
    ax.set_title(f"長期紀錄風險分組與復發時機（探索性，p={lr_lt.p_value:.2g}）")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "figF_nhefs_km_longterm.png"), dpi=200); plt.close(fig)

    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    analyze()
