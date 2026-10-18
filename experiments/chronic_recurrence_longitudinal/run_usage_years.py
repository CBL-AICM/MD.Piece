"""延伸實驗：假設患者已用 App 記錄 1、2、3…10 年，預測準確度與預警成功率各是多少；長期紀錄能否預測復發時間線。

分析計畫（跑資料前寫定）：
  對象與疾病同 run.py（NHEFS，18 歲以上、追蹤 3–10 年、四種慢性病）。
  為了讓 1 到 10 年的比較只差在「紀錄長度」，只取「預測時點之前 NHEFS 已完整觀察滿 10 年」的時點
  （預測時點 ≥ NHANES I 基線檢查日 + 10 年，且 ≥ 確診滿 1 年），所有 k 用同一批時點與同一批人。
  使用 k 年 = 模型只看得到預測時點前 k 年內的住院紀錄（模擬 App 用了 k 年）。

  實驗一（使用年數 × 準確度）：
    結果 = 未來 12 個月內以該病為主診斷再住院。
    模型 = logistic（年齡、性別、病別 + k 年窗內：近 12 個月住院數、該病住院數、該病主診斷住院數，
           1 年到 k 年前的同三項，距最近一次該病住院年數〔上限 k〕），依患者分組 5 折交叉驗證。
    MD.Piece 引擎同樣只餵 k 年內的紀錄。
    指標 = AUROC（患者層 bootstrap 95% CI）；把風險最高 20% 標為「預警」時：
           預警成功率（實際復發者中事先被標出的比例，敏感度）、命中率（被標出者中真的復發的比例，PPV）、
           相對隨機的倍數（命中率 ÷ 基礎復發率）、被成功預警者距復發的提前月數中位數。
  實驗二（時間線）：
    每位患者×疾病取第一個合格時點，結果 = 距下一次復發的時間（追蹤到 run.py 的追蹤結束日，最長 9 年）。
    Cox 模型（同特徵、5 折交叉驗證）對 k = 1、2、3、5、10 年 → Harrell C-index；
    k = 10 年模型在 1、2、3、5 年時點的時間依存 AUROC；
    依預測風險三分組，比較 Cox 預測的累積復發曲線與實際 Kaplan–Meier 曲線（時間線校準）。

跑法： PYTHONPATH=. python experiments/chronic_recurrence_longitudinal/run_usage_years.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.utils import concordance_index
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run as base  # noqa: E402
from run import DISEASES, YEAR, boot_auc, compress, ctx, cv_scores, episodes, recurrence  # noqa: E402

OUT = base.OUT
KS = list(range(1, 11))
TOP = 0.20


def build():
    h, vit = base.load_nhefs()
    hosp = h[h.fac == "1"]
    rows = []
    for key, (zh, codes, band) in DISEASES.items():
        has = hosp[hosp.dx.str.split("|").apply(lambda xs: any(x in codes for x in xs))]
        for seq, index in has.groupby("seq").adm.min().items():
            if seq not in vit.index:
                continue
            v = vit.loc[seq]
            if v.byear is None or not v.sex or v.end is None or v.exam is None:
                continue
            fu_end = min(v.end, index + 10 * YEAR)
            if index.year - v.byear < 18 or (fu_end - index).days / 365.25 < 3:
                continue
            mine = h[h.seq == seq]
            hs = mine[mine.fac == "1"]
            rec = [d for d in episodes(hs[hs.prin.isin(codes)].adm) if (d - index).days > 30 and d <= fu_end]
            dz = [r.adm for r in hs.itertuples() if any(x in codes for x in r.dx.split("|"))]
            pr = list(hs[hs.prin.isin(codes)].adm)
            allst = list(mine.adm)
            first_done = False
            for j in range(1, 10):
                L = index + j * YEAR
                nxt = [d for d in rec if L < d <= L + YEAR]
                if L >= fu_end or (L + YEAR > fu_end and not nxt):
                    break
                if L < v.exam + 10 * YEAR:          # 預測時點前未滿 10 年可觀察紀錄 → 不納入
                    continue
                later = [d for d in rec if d > L]
                r = {"SEQNUM": seq, "疾病": zh, "disease": key, "band": band, "L": L, "age": L.year - v.byear,
                     "male": int(v.sex == "男"), "y": int(bool(nxt)),
                     "lead_days": (nxt[0] - L).days if nxt else None,
                     "time": ((later[0] if later else fu_end) - L).days / 365.25, "event": int(bool(later)),
                     "first": int(not first_done)}
                first_done = True
                for k in KS:
                    lo = L - k * YEAR
                    c = lambda ds, a, b: sum(1 for d in ds if a < d <= b)
                    r[f"s1_{k}"] = c(allst, L - YEAR, L)
                    r[f"d1_{k}"] = c(dz, L - YEAR, L)
                    r[f"p1_{k}"] = c(pr, L - YEAR, L)
                    r[f"sk_{k}"] = c(allst, lo, L - YEAR)
                    r[f"dk_{k}"] = c(dz, lo, L - YEAR)
                    r[f"pk_{k}"] = c(pr, lo, L - YEAR)
                    last = [d for d in dz if lo < d <= L]
                    r[f"gap_{k}"] = min(k, (L - max(last)).days / 365.25) if last else k
                    if k <= 5 or k == 10:            # 引擎近期窗+基準窗共 4.3 年，k≥5 與完整紀錄相同
                        k14 = 365.25 / 14
                        src = {"medical_records": [{"visit_date": compress(d, k14).strftime("%Y-%m-%d %H:%M:%S")} for d in allst if lo < d <= L],
                               "symptoms_log": [{"created_at": compress(d, k14).strftime("%Y-%m-%d %H:%M:%S")} for d in dz if lo < d <= L],
                               "_context": ctx(band)}
                        r[f"eng_{k}"] = recurrence.risk_from(src, compress(L, k14))[0]
                rows.append(r)
    return pd.DataFrame(rows)


def feats(df, k):
    dz = pd.get_dummies(df.disease, prefix="dz", dtype=float)
    X = pd.concat([df[["age", "male"] + [f"{p}_{k}" for p in ("s1", "d1", "p1", "sk", "dk", "pk", "gap")]], dz], axis=1)
    X.columns = [str(c).replace(f"_{k}", "") for c in X.columns]
    return X


def flag_metrics(y, s, lead):
    cut = np.quantile(s, 1 - TOP)
    f = s >= cut
    tp = f & (y == 1)
    return {"sensitivity": tp.sum() / max(1, y.sum()), "ppv": tp.sum() / max(1, f.sum()),
            "lift": (tp.sum() / max(1, f.sum())) / y.mean(), "flagged": int(f.sum()),
            "lead_months_median": float(np.median(lead[tp]) / 30.44) if tp.sum() else None}


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    base.use_doc_fonts(plt)

    df = build().reset_index(drop=True)
    y, g = df.y.values, df.SEQNUM.values
    lead = df.lead_days.fillna(0).values
    res = {"n_landmarks": len(df), "n_patients": int(df.SEQNUM.nunique()), "n_patient_disease": int(df["first"].sum()),
           "events": int(y.sum()), "rate": round(float(y.mean()), 4), "usage": [], "timeline": {}}
    oof = {}
    for k in KS:
        X = feats(df, k)
        oof[k] = cv_scores(X, list(X.columns), y, g)
        auc = boot_auc(y, oof[k], g, n=500)
        row = {"years": k, "auc": [round(v, 3) for v in auc]}
        row.update({kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in flag_metrics(y, oof[k], lead).items()})
        if f"eng_{k}" in df:
            ea = boot_auc(y, df[f"eng_{k}"].values, g, n=500)
            row["engine_auc"] = [round(v, 3) for v in ea]
            row["engine_sensitivity"] = round(flag_metrics(y, df[f"eng_{k}"].values, lead)["sensitivity"], 3)
        res["usage"].append(row)
        print(row, flush=True)

    # 使用 10 年 vs 1 年、3 年的 AUROC 差（同一批時點、患者層配對 bootstrap）
    rng = np.random.default_rng(11)
    ug = np.unique(g); gi = {x: np.where(g == x)[0] for x in ug}
    diffs = {1: [], 3: []}
    for _ in range(1000):
        p = np.concatenate([gi[x] for x in rng.choice(ug, len(ug))])
        a10 = roc_auc_score(y[p], oof[10][p])
        for kk in diffs:
            diffs[kk].append(a10 - roc_auc_score(y[p], oof[kk][p]))
    res["auc_gain_10y_vs"] = {str(kk): [round(float(np.mean(v)), 3), round(float(np.percentile(v, 2.5)), 3),
                                        round(float(np.percentile(v, 97.5)), 3)] for kk, v in diffs.items()}
    print(res["auc_gain_10y_vs"], flush=True)

    # ── 實驗二：時間線（每位患者×疾病第一個合格時點）──
    fd = df[df["first"] == 1].reset_index(drop=True)
    gf = fd.SEQNUM.values
    tl = {}
    pred_curves = None
    grid = np.linspace(0, 9, 91)
    for k in (1, 2, 3, 5, 10):
        X = feats(fd, k)
        X = X.loc[:, X.std() > 0]          # 使用 1 年時「1 年以前」欄位全為 0，移除
        X = (X - X.mean()) / X.std()
        risk = np.zeros(len(fd))
        cum = np.zeros((len(fd), len(grid)))
        for tr, te in GroupKFold(5).split(X, fd.event, gf):
            d_tr = X.iloc[tr].assign(time=fd.time.values[tr], event=fd.event.values[tr])
            m = CoxPHFitter(penalizer=0.05).fit(d_tr, "time", "event")
            risk[te] = m.predict_partial_hazard(X.iloc[te]).values
            if k == 10:
                sf = m.predict_survival_function(X.iloc[te], times=grid).T.values
                cum[te] = 1 - sf
        c = concordance_index(fd.time, -risk, fd.event)
        bs = []
        rng = np.random.default_rng(7)
        ug = np.unique(gf); gi = {x: np.where(gf == x)[0] for x in ug}
        for _ in range(300):
            p = np.concatenate([gi[x] for x in rng.choice(ug, len(ug))])
            bs.append(concordance_index(fd.time.values[p], -risk[p], fd.event.values[p]))
        tdauc = {}
        for hz in (1, 2, 3, 5):
            case = (fd.event == 1) & (fd.time <= hz)
            ctrl = fd.time > hz
            m_ = case | ctrl
            if case.sum() >= 10 and ctrl.sum() >= 10:
                tdauc[hz] = round(roc_auc_score(case[m_].astype(int), risk[m_]), 3)
        tl[k] = {"c_index": [round(c, 3), round(np.percentile(bs, 2.5), 3), round(np.percentile(bs, 97.5), 3)],
                 "time_auc": tdauc}
        if k == 10:
            pred_curves, risk10 = cum, risk
        print(k, tl[k], flush=True)
    res["timeline"] = {str(k): v for k, v in tl.items()}
    res["timeline_n"] = {"n": len(fd), "events": int(fd.event.sum()), "fu_median": round(float(fd.time.median()), 2)}

    tert = pd.qcut(risk10, 3, labels=["低", "中", "高"])
    km = KaplanMeierFitter()
    calib = {}
    tl_rows = []
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    colors = {"低": "#3a7d44", "中": "#d08c2e", "高": "#c0392b"}
    for t_ in ("低", "中", "高"):
        m = np.asarray(tert == t_)
        km.fit(fd.time[m], fd.event[m])
        obs = 1 - km.survival_function_at_times(grid).values
        pred = pred_curves[m].mean(axis=0)
        ax.plot(grid, obs * 100, color=colors[t_], label=f"風險{t_}：實際")
        ax.plot(grid, pred * 100, color=colors[t_], ls="--", label=f"風險{t_}：模型預測")
        calib[t_] = {f"{yy}y": {"observed": round(float(obs[yy * 10]), 3), "predicted": round(float(pred[yy * 10]), 3)}
                     for yy in (1, 3, 5)}
        calib[t_]["n"] = int(m.sum())
        tl_rows.append(pd.DataFrame({"風險組": t_, "人數": int(m.sum()), "年": grid, "實際累積復發百分比": obs * 100,
                                     "模型預測累積復發百分比": pred * 100}))
    base.save_plot_data("圖八_復發時間線預測與實際", pd.concat(tl_rows).round(3))
    ax.set_xlabel("預測時點後經過年數"); ax.set_ylabel("累積復發比例（%）")
    ax.set_title("用滿 10 年紀錄預測的復發時間線：預測（虛線）與實際（實線）")
    ax.legend(fontsize=7.5, ncol=2); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figH_timeline_calibration.png"), dpi=200); plt.close(fig)
    res["timeline_calibration"] = calib

    u = pd.DataFrame(res["usage"])
    base.save_plot_data("圖七_使用年數與AUROC", pd.DataFrame([
        {"使用年數": r["years"], "長期紀錄模型AUROC": r["auc"][0], "下限": r["auc"][1], "上限": r["auc"][2],
         "MD.Piece引擎AUROC": (r["engine_auc"][0] if "engine_auc" in r else None)} for r in res["usage"]]))
    base.save_plot_data("表十六_預警成功率與命中率", pd.DataFrame([
        {"使用年數": r["years"], "預警成功率百分比": round(r["sensitivity"] * 100, 1), "命中率百分比": round(r["ppv"] * 100, 1),
         "隨機標記預警成功率百分比": TOP * 100} for r in res["usage"]]))
    fig, ax1 = plt.subplots(figsize=(6.4, 4.2))
    ax1.errorbar(u.years, [a[0] for a in u.auc], yerr=[[a[0] - a[1] for a in u.auc], [a[2] - a[0] for a in u.auc]],
                 marker="o", capsize=3, label="長期紀錄模型 AUROC")
    e = u.dropna(subset=["engine_auc"]) if "engine_auc" in u else u.iloc[0:0]
    ax1.plot(e.years, [a[0] for a in e.engine_auc], marker="s", ls="--", label="MD.Piece 引擎 AUROC")
    ax1.axhline(0.5, ls=":", c="grey"); ax1.set_ylim(0.45, 0.8)
    ax1.set_xlabel("App 已使用年數（模型可看到的紀錄長度）"); ax1.set_ylabel("AUROC（95% CI）")
    ax1.set_xticks(KS); ax1.legend(fontsize=8, loc="lower right")
    ax1.set_title("使用年數與未來 12 個月復發預測準確度"); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figG_usage_years_auc.png"), dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.bar(u.years - 0.2, u.sensitivity * 100, 0.4, label="預警成功率（復發者事先被標出）")
    ax.bar(u.years + 0.2, u.ppv * 100, 0.4, label="命中率（被標出者真的復發）")
    ax.axhline(TOP * 100, ls=":", c="grey", label="隨機標 20% 的預警成功率")
    ax.set_xticks(KS); ax.set_xlabel("App 已使用年數"); ax.set_ylabel("%")
    ax.set_ylim(0, 75); ax.set_title("標出風險最高 20% 時的預警成功率與命中率")
    ax.legend(fontsize=8, loc="upper left", ncol=2); fig.tight_layout()
    fig.savefig(os.path.join(OUT, "figI_usage_years_success.png"), dpi=200); plt.close(fig)

    df.drop(columns=[c for c in df.columns if c.startswith("eng_")]).assign(L=df.L.astype(str)).to_csv(
        os.path.join(OUT, "usage_years_預測時點紀錄.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(OUT, "results_usage_years.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "usage"}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
