# -*- coding: utf-8 -*-
"""五張圖（建置提示詞 輸出規格）：黑白灰、可讀字型、座標軸有單位。"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.style.use("grayscale")
plt.rcParams.update({"font.size": 10, "axes.grid": False, "figure.dpi": 130,
                     "font.family": ["Microsoft JhengHei", "DejaVu Sans"],
                     "axes.unicode_minus": False})
GREYS = ["0.15", "0.45", "0.7", "0.85", "0.3", "0.6"]
HATCH = ["", "//", "..", "xx", "\\\\", "++"]


def _save(fig, outdir, name):
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, name)
    fig.tight_layout(); fig.savefig(p); plt.close(fig)
    return p


def fig1_single_case(fd, outdir):
    """單一翻轉型個案：x(t)、滾動 AR(1)、滾動 SD，標出臨界日／事件日／首次警報。"""
    x, ar, sd = np.asarray(fd["x"]), np.asarray(fd["ar1"]), np.asarray(fd["sd"])
    win, T = fd["window"], len(x)
    tt = np.arange(T); tw = np.arange(len(ar)) + win - 1
    fig, ax = plt.subplots(3, 1, figsize=(7.5, 6.5), sharex=True)
    ax[0].plot(tt, x, color="0.2", lw=0.8); ax[0].axhline(fd["x_event"], color="0.5", ls=":", lw=1)
    ax[0].set_ylabel("活動度 x（無單位；虛線=事件門檻）")
    ax[1].plot(tw, ar, color="0.2", lw=0.8); ax[1].set_ylabel(f"滾動 AR(1)（窗 {win} 天）")
    ax[2].plot(tw, sd, color="0.2", lw=0.8); ax[2].set_ylabel(f"滾動 SD（窗 {win} 天）")
    ax[2].set_xlabel("時間（天）")
    for a in ax:
        if fd["t_crit"] >= 0: a.axvline(fd["t_crit"], color="0.1", ls="--", lw=1)
        if fd["t_event"] >= 0: a.axvline(fd["t_event"], color="0.1", ls="-", lw=1)
        if fd["first_alarm"] >= 0: a.axvline(fd["first_alarm"], color="0.55", ls="-.", lw=1)
    ax[0].set_title(f"翻轉型個案 #{fd['idx']}：--臨界日 {fd['t_crit']}，—事件日 {fd['t_event']}，-·-首次警報 {fd['first_alarm']}（去趨勢：{fd['detrend']}）", fontsize=9)
    return _save(fig, outdir, "fig1_flip_case_indicators.png")


def fig2_strata_types(cl_res, gen_share, outdir, title=""):
    """各風險層的軌跡型態分布：左＝分群結果的群比例（方法 A、五分位），右＝生成器型別組成（對照）。"""
    S = len(cl_res)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))
    for s, r in enumerate(cl_res):
        bottom = 0
        for k, sh in enumerate(r["shares"]):
            ax[0].bar(s, sh, bottom=bottom, color=GREYS[k % 6], hatch=HATCH[k % 6], edgecolor="k", lw=0.5)
            bottom += sh
        ax[0].text(s, 1.02, f"K={r['K']}\nARI={r.get('ari_vs_generator', np.nan):.2f}", ha="center", fontsize=7)
    ax[0].set_xlabel("風險層（五分位，0=最低）"); ax[0].set_ylabel("群比例"); ax[0].set_ylim(0, 1.15)
    ax[0].set_title("分群結果（方法 A）", fontsize=9)
    names = list(gen_share[0].keys())
    for s in range(S):
        bottom = 0
        for k, nm in enumerate(names):
            ax[1].bar(s, gen_share[s][nm], bottom=bottom, color=GREYS[k % 6], hatch=HATCH[k % 6], edgecolor="k", lw=0.5,
                      label=nm if s == 0 else None)
            bottom += gen_share[s][nm]
    ax[1].set_xlabel("風險層（五分位）"); ax[1].set_ylabel("比例"); ax[1].set_title("生成器真值（對照，非發現）", fontsize=9)
    ax[1].legend(fontsize=7, loc="upper right")
    fig.suptitle(title, fontsize=9)
    return _save(fig, outdir, "fig2_strata_trajectory_types.png")


def fig3_static_vs_dynamic(agg_pred, outdir):
    """C 指數（靜態 vs 動態，多 seed 均值與範圍）與淨重新分類（兩種閾值）。"""
    Ls = sorted(agg_pred["landmarks"].keys(), key=int)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    xs = np.arange(len(Ls))
    for j, (key, lab, mk) in enumerate((("auc_static", "靜態", "o"), ("auc_dynamic", "動態（地標）", "s"))):
        m = [agg_pred["landmarks"][L][key]["mean"] for L in Ls]
        lo = [agg_pred["landmarks"][L][key]["min"] for L in Ls]; hi = [agg_pred["landmarks"][L][key]["max"] for L in Ls]
        ax[0].errorbar(xs + 0.08 * j, m, yerr=[np.subtract(m, lo), np.subtract(hi, m)], fmt=mk, color=GREYS[j], capsize=3, label=lab)
    ax[0].set_xticks(xs); ax[0].set_xticklabels([f"{L} 天" for L in Ls]); ax[0].set_ylabel("C 指數（AUC）"); ax[0].legend(fontsize=8)
    ax[0].set_title("鑑別力（誤差棒＝各 seed 範圍）", fontsize=9)
    for j, rule in enumerate(("abs", "rel")):
        nri = [agg_pred["landmarks"][L][f"reclass_{rule}"]["nri"]["mean"] for L in Ls]
        mi = [agg_pred["landmarks"][L][f"reclass_{rule}"]["moved_in"]["mean"] for L in Ls]
        mo = [agg_pred["landmarks"][L][f"reclass_{rule}"]["moved_out"]["mean"] for L in Ls]
        ax[1].bar(xs + (j - 0.5) * 0.35, mi, 0.35, color=GREYS[j], hatch=HATCH[j], edgecolor="k", lw=0.5, label=f"移入高風險（{rule}）")
        ax[1].bar(xs + (j - 0.5) * 0.35, [-v for v in mo], 0.35, color="1.0", hatch=HATCH[j], edgecolor="k", lw=0.5, label=f"移出高風險（{rule}）")
        for xi, v in zip(xs, nri):
            ax[1].text(xi + (j - 0.5) * 0.35, 0.02 + max(mi), f"NRI\n{v:+.2f}", ha="center", fontsize=6.5)
    ax[1].axhline(0, color="k", lw=0.6); ax[1].set_xticks(xs); ax[1].set_xticklabels([f"{L} 天" for L in Ls])
    ax[1].set_ylabel("風險集內比例（上=移入，下=移出）"); ax[1].legend(fontsize=6.5, loc="lower right")
    ax[1].set_title("淨重新分類（abs=事件率閾值，rel=前 20%）", fontsize=9)
    return _save(fig, outdir, "fig3_static_vs_dynamic.png")


def fig4_timing_shift(timing, outdir):
    """介入時點位移：直方圖＋累積分布（決定書 §8），兩種閾值各一列。"""
    fig, ax = plt.subplots(2, 2, figsize=(9, 6))
    for i, rule in enumerate(("abs", "rel")):
        t = timing[rule]; Ls = np.array(t["landmarks"])
        hb, hd = np.array(t["shift_days_both"]["hist"], float), np.array(t["first_flag_hist_dynamic_only"], float)
        ax[i, 0].bar(Ls - 20, hb, 40, color="0.3", edgecolor="k", lw=0.4, label=f"靜態也高（n={t['n_both']}）：位移=動態首次判定日")
        ax[i, 0].bar(Ls + 20, hd, 40, color="0.8", hatch="//", edgecolor="k", lw=0.4, label=f"僅動態高（n={t['n_dynamic_only']}）：新增判定日")
        ax[i, 0].set_xlabel("天"); ax[i, 0].set_ylabel("人數"); ax[i, 0].legend(fontsize=7)
        ax[i, 0].set_title(f"閾值 {rule}；靜態高但動態從未判定 n={t['n_static_only']}", fontsize=9)
        for h, c, lab in ((hb, "0.3", "靜態也高"), (hd, "0.7", "僅動態高")):
            if h.sum() > 0:
                ax[i, 1].step(Ls, np.cumsum(h) / h.sum(), where="post", color=c, label=lab)
        ax[i, 1].set_xlabel("動態首次判定日（天）"); ax[i, 1].set_ylabel("累積比例"); ax[i, 1].set_ylim(0, 1.02); ax[i, 1].legend(fontsize=7)
    return _save(fig, outdir, "fig4_intervention_timing_shift.png")


def fig5_leadtime(lead, outdir):
    """翻轉型 vs 爬升型的提前期（到事件日）分布；翻轉型另附到臨界日。"""
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    data = [np.asarray(lead["flip_event"]), np.asarray(lead["linear_event"])]
    bp = ax[0].boxplot([d[np.isfinite(d)] for d in data], labels=["翻轉型", "爬升型"], patch_artist=True, widths=0.5)
    for p, c in zip(bp["boxes"], ["0.4", "0.85"]):
        p.set_facecolor(c)
    ax[0].axhline(0, color="k", lw=0.6, ls=":")
    ax[0].set_ylabel("提前期＝事件日 − 首次警報日（天）")
    ax[0].set_title(f"到事件日；雙尾置換 p={lead['perm_p']:.3f}（中位差 {lead['perm_diff']:+.0f} 天）", fontsize=9)
    fc = np.asarray(lead["flip_crit"]); fc = fc[np.isfinite(fc)]
    if len(fc):
        ax[1].hist(fc, bins=30, color="0.5", edgecolor="k", lw=0.4)
    ax[1].axvline(0, color="k", lw=0.8, ls="--")
    ax[1].set_xlabel("臨界日 − 首次警報日（天；>0 = 臨界日前就警報）"); ax[1].set_ylabel("人數")
    ax[1].set_title("翻轉型：到已知臨界日", fontsize=9)
    return _save(fig, outdir, "fig5_leadtime_flip_vs_linear.png")
