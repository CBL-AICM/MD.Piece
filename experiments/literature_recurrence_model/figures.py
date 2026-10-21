"""說明書全部圖表（中、英文各一套），只讀 run.py 的輸出（results.json、plot_data/*.csv），不重算任何數字。

字型：中文新細明體、英數 Times New Roman；本機沒有時改用外型最接近的
Noto Serif CJK TC（明體）與 Liberation Serif（與 Times New Roman 字寬相同）。
配色經 dataviz 驗證腳本檢查（色盲可分辨）：文獻＝藍、原始虛擬＝橘、新數據＝青綠、模型＝紫、對照＝灰虛線。

跑法： python experiments/literature_recurrence_model/figures.py [字型資料夾]
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
PD = os.path.join(OUT, "plot_data")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)
R = json.load(open(os.path.join(OUT, "results.json"), encoding="utf-8"))
LIT, ORIG, NEW, MODEL, GOLD, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#eda100", "#8c8c8c"
INK = "#333333"


def setup_fonts(font_dir):
    cands = [("PMingLiU", "Times New Roman"), ("Noto Serif CJK TC", "Liberation Serif")]
    for f in os.listdir(font_dir) if font_dir and os.path.isdir(font_dir) else []:
        if f.lower().endswith((".otf", ".ttf", ".ttc")):
            fm.fontManager.addfont(os.path.join(font_dir, f))
    names = {f.name for f in fm.fontManager.ttflist}
    for cjk, latin in cands:
        if cjk in names:
            plt.rcParams["font.family"] = [latin if latin in names else "DejaVu Serif", cjk]
            break
    plt.rcParams.update({
        "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "axes.grid.axis": "y", "grid.color": "#e3e3e3", "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.edgecolor": "#777777", "axes.titlesize": 12, "axes.labelsize": 11, "xtick.labelsize": 10,
        "ytick.labelsize": 10, "legend.frameon": False, "legend.fontsize": 9.5, "figure.dpi": 100,
        "savefig.dpi": 200, "lines.linewidth": 2, "text.color": INK, "axes.labelcolor": INK,
    })


T = {  # 圖中文字（zh / en）
    "lit": ("文獻", "Literature"), "orig": ("原始虛擬患者", "Original virtual cohort"),
    "new": ("新數據（文獻校準）", "New data (literature-calibrated)"), "model": ("模型預測", "Model prediction"),
    "annual": ("一年內至少復發一次的比例", "Proportion with ≥1 recurrence in one year"),
    "rr": ("相對風險（對數刻度）", "Relative risk (log scale)"),
}


def t(key, lang):
    return T[key][0 if lang == "zh" else 1]


def dname(row, lang):
    return row["疾病"] if lang == "zh" else row["en"]


def save(fig, name, lang):
    fig.savefig(os.path.join(FIG, f"{name}_{lang}.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ───────── 圖 1 研究架構、圖 2 研究流程 ─────────
def box(ax, x, y, w, h, s, fc="white", ec="#9a9a9a", size=10.5, color=INK, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=ec, lw=1))
    ax.text(x + w / 2, y + h / 2, s, ha="center", va="center", fontsize=size, color=color, linespacing=1.45, weight=weight)


def arrow(ax, a, b):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=13, color="#777777", lw=1.3))


def fig_framework(lang):
    zh = lang == "zh"
    fig = plt.figure(figsize=(8.2, 6.2))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 82); ax.set_ylim(62, 0); ax.axis("off")
    box(ax, 4, 2, 74, 6, "研究問題：長期紀錄能不能預測慢性病復發與復發時間？（沿用前一份研究的目的）" if zh else
        "Question: can long-term records predict chronic-disease recurrence and its timing? (same aim as the previous study)",
        fc="#eef3fa", ec=LIT, size=11)
    cols = [
        (4, "資料來源一　文獻" if zh else "Source 1: literature",
         "PubMed 46 篇摘要\n只取族群層級數字\n（復發率、效果量、\n累積復發曲線）" if zh else
         "46 PubMed abstracts\npopulation-level numbers only\n(rates, effect sizes,\ncumulative curves)", LIT),
        (30, "資料來源二　虛擬患者" if zh else "Source 2: virtual patients",
         "過去合成的 3,200 人\n16 種慢性病 × 200 人\n延長模擬為 3 年" if zh else
         "The 3,200 patients made earlier\n16 chronic diseases × 200\nextended to 3 years", ORIG),
        (56, "不使用" if zh else "Not used",
         "公開資料庫的個人資料\n（NHEFS、Framingham 等）\n不用來訓練或回推" if zh else
         "Individual-level public data\n(NHEFS, Framingham, etc.)\nno training, no back-fitting", GREY),
    ]
    for x, head, body, c in cols:
        box(ax, x, 12, 22, 5, head, fc=c, ec=c, color="white", size=11)
        box(ax, x, 17, 22, 12, body, size=10)
    arrow(ax, (15, 29), (30, 35)); arrow(ax, (41, 29), (41, 35))
    box(ax, 18, 35, 46, 7, "文獻校準：每病只調一個門檻，讓第 2 年復發率＝文獻值\n→ 新數據（3,200 人）" if zh else
        "Calibration: one threshold per disease so year-2 recurrence = literature value\n→ new data (3,200 patients)",
        fc="#e8f7f1", ec=NEW, size=10.5)
    arrow(ax, (41, 42), (41, 46))
    items = [("機制檢驗\nH1 過去活動紀錄\nH2 未按時用藥\nH3 時間型態" if zh else "Mechanisms\nH1 activity history\nH2 missed doses\nH3 timing pattern", 4),
             ("模型訓練\nlogistic、梯度提升樹、Cox\n紀錄長度 30–730 天" if zh else "Models\nlogistic, boosting, Cox\nrecord length 30–730 days", 30),
             ("交叉對比\n文獻 × 原始虛擬\n× 新數據 × 模型" if zh else "Cross-comparison\nliterature × original\n× new data × model", 56)]
    for s, x in items:
        box(ax, x, 46, 22, 11, s, size=10)
    ax.text(41, 60, "MD. Piece 只作輔助，不做診斷，也不取代醫師" if zh else
            "MD. Piece is a support tool: it does not diagnose and does not replace the doctor", ha="center", fontsize=10, color="#666666")
    save(fig, "fig01_framework", lang)


def fig_workflow(lang):
    zh = lang == "zh"
    steps = [
        ("1", "文獻檢索與擷取" if zh else "Literature search & extraction",
         "PubMed 檢索 16 種疾病的復發、惡化、再發研究；逐篇記錄摘要中的數字與換算方式" if zh else
         "Search PubMed for recurrence/flare studies in 16 diseases; record each number and its conversion"),
        ("2", "文獻縱向統整" if zh else "Longitudinal synthesis",
         "換算一年復發機率；隨機效應統合 H1、H2；Weibull 擬合累積復發曲線（H3）" if zh else
         "Convert to one-year probability; random-effects pooling of H1, H2; Weibull fits of cumulative curves (H3)"),
        ("3", "虛擬患者重跑與校準" if zh else "Re-run and calibrate virtual patients",
         "同一模擬器、同一組 seed 跑 3 年；每病調一個門檻對齊文獻第 2 年復發率" if zh else
         "Same simulator and seeds for 3 years; one threshold per disease matched to the literature year-2 rate"),
        ("4", "模型訓練與驗證" if zh else "Model training & validation",
         "第 730 天預測未來 90 天復發與復發時間；5 折交叉驗證、bootstrap、標籤置換" if zh else
         "At day 730 predict 90-day recurrence and time to recurrence; 5-fold CV, bootstrap, label permutation"),
        ("5", "交叉對比與查證" if zh else "Cross-comparison & check",
         "新數據 × 原始虛擬 × 文獻逐項比對；最後再與文獻中的模型表現對照" if zh else
         "Compare new data, original cohort and literature item by item; then against published model performance"),
    ]
    fig = plt.figure(figsize=(8.2, 6.0))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 82); ax.set_ylim(60, 0); ax.axis("off")
    for i, (n, head, body) in enumerate(steps):
        y = 2 + i * 11.5
        box(ax, 3, y, 8, 8.5, n, fc=LIT, ec=LIT, color="white", size=15)
        box(ax, 13, y, 66, 8.5, "", size=10)
        ax.text(16, y + 2.6, head, fontsize=11.5, va="center", color=INK, weight="bold")
        ax.text(16, y + 6.0, body, fontsize=9.8, va="center", color=INK)
        if i < len(steps) - 1:
            arrow(ax, (7, y + 8.5), (7, y + 11.5))
    save(fig, "fig02_workflow", lang)


# ───────── 圖 3 逐病一年復發機率：文獻 vs 原始 vs 新數據 vs 模型 ─────────
def fig_annual(lang):
    c = pd.read_csv(os.path.join(PD, "交叉對比_逐病一年復發率.csv"))
    studies = pd.read_csv(os.path.join(PD, "文獻_各研究一年復發機率.csv"))
    c = c.sort_values("lit_target", na_position="first").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.2, 7.0))
    for i, r in c.iterrows():
        s = studies[studies.disease == r.disease]
        if len(s):
            ax.plot([r.lit_lo, r.lit_hi], [i, i], color=LIT, lw=5, alpha=0.25, solid_capstyle="round")
            ax.scatter(s.annual_p, [i] * len(s), s=22, color=LIT, zorder=3, edgecolor="white", lw=0.8)
        ax.scatter(r.orig_p_y2, i, marker="x", s=40, color=ORIG, zorder=4, lw=2)
        ax.scatter(r.calib_p_y3, i, marker="o", s=46, facecolor="white", edgecolor=NEW, lw=2, zorder=5)
        ax.scatter(r.model_pred_365, i, marker="D", s=26, color=MODEL, zorder=6)
    labels = [dname(r, lang) + ("" if r.lit_k else (" *" if lang == "zh" else " *")) for _, r in c.iterrows()]
    ax.set_yticks(range(len(c)), labels)
    ax.set_xlabel(t("annual", lang)); ax.set_xlim(-0.02, 1.04)
    ax.grid(axis="x", color="#e3e3e3"); ax.grid(axis="y", visible=False)
    h = [plt.Line2D([], [], color=LIT, marker="o", lw=5, alpha=0.6, label=("文獻（點＝各研究，帶＝範圍）" if lang == "zh" else "Literature (dots = studies, band = range)")),
         plt.Line2D([], [], color=ORIG, marker="x", lw=0, markersize=7, mew=2, label=("原始虛擬患者（第 2 年）" if lang == "zh" else "Original virtual cohort (year 2)")),
         plt.Line2D([], [], color=NEW, marker="o", lw=0, mfc="white", mew=2, label=("新數據（第 3 年，未參與校準）" if lang == "zh" else "New data (year 3, not used in calibration)")),
         plt.Line2D([], [], color=MODEL, marker="D", lw=0, label=("模型預測（Cox，折外）" if lang == "zh" else "Model prediction (Cox, out-of-fold)"))]
    ax.legend(handles=h, loc="lower right", fontsize=9)
    fig.text(0.02, 0.005, "* 無文獻錨，未校準" if lang == "zh" else "* no literature anchor, not calibrated", fontsize=9, color="#666666")
    save(fig, "fig03_annual_recurrence", lang)


# ───────── 圖 4 森林圖：H1、H2 ─────────
def fig_forest(lang):
    e = pd.read_csv(os.path.join(PD, "文獻_效果量.csv"))
    pooled = R["literature"]["pooled"]
    mech = R["mechanisms"]
    en_d = {"氣喘": "Asthma", "類風濕性關節炎": "Rheumatoid arthritis", "ANCA 血管炎": "ANCA vasculitis", "慢性蕁麻疹": "Chronic urticaria",
            "潰瘍性結腸炎": "Ulcerative colitis", "紅斑性狼瘡": "SLE"}
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 8.4), sharex=True, gridspec_kw={"height_ratios": [8, 6]})
    for ax, hyp, vkey, title in ((axes[0], "H1", "H1_prior_flare", ("H1　過去或近期疾病活動 → 未來復發", "H1  Past/recent activity → future recurrence")),
                                 (axes[1], "H2", "H2_missed_dose_quartile", ("H2　未按時用藥或停藥 → 未來復發", "H2  Missed doses or stopping → future recurrence"))):
        g = e[e.hyp == hyp].reset_index(drop=True)
        rows = []
        for _, r in g.iterrows():
            lab = (r["疾病"] if lang == "zh" else en_d[r["疾病"]]) + f"（{r.measure}）" if lang == "zh" else (en_d[r["疾病"]] + f" ({r.measure})")
            rows.append((lab, r.est, r.lo, r.hi, LIT, "o", 7))
        p = pooled[hyp]
        rows.append((("文獻統合（隨機效應）" if lang == "zh" else "Literature pooled (random effects)"), p["pooled"], p["lo"], p["hi"], LIT, "D", 9))
        for lab, key, col in ((t("orig", lang), "original", ORIG), (("新數據" if lang == "zh" else "New data"), "calibrated", NEW)):
            m = mech[key][vkey]
            rows.append((lab, m["rr"], m["lo"], m["hi"], col, "s", 8))
        n = len(rows)
        for i, (lab, est, lo, hi, col, mk, ms) in enumerate(rows):
            y = n - 1 - i
            ax.plot([lo, hi], [y, y], color=col, lw=2)
            ax.plot(est, y, marker=mk, color=col, markersize=ms, mec="white", mew=0.8)
            ax.text(1.02, y, f"{est:.2f} ({lo:.2f}–{hi:.2f})", transform=ax.get_yaxis_transform(), fontsize=8.5, va="center", color=INK)
        ax.set_yticks(range(n), [r[0] for r in rows][::-1], fontsize=9)
        ax.axvline(1, color=GREY, ls="--", lw=1)
        ax.axhline(2.5, color="#cccccc", lw=0.8)
        ax.set_xscale("log"); ax.set_xticks([0.5, 1, 2, 4, 8, 16, 32], ["0.5", "1", "2", "4", "8", "16", "32"])
        ax.minorticks_off()
        ax.set_xlim(0.4, 40); ax.grid(axis="x", color="#eeeeee"); ax.grid(axis="y", visible=False)
        ax.set_title(title[0 if lang == "zh" else 1], fontsize=11, loc="left")
        p_txt = f"I² = {p['I2'] * 100:.0f}%"
        ax.text(0.98, 0.02, p_txt, transform=ax.transAxes, ha="right", fontsize=9, color="#666666")
    axes[1].set_xlabel(t("rr", lang))
    fig.tight_layout(h_pad=2)
    save(fig, "fig04_forest_H1_H2", lang)


# ───────── 圖 5 時間型態（H3） ─────────
def fig_weibull(lang):
    cur = R["literature"]["curves"]
    en_c = {"類風濕性關節炎（停藥後）": "RA (after stopping biologics)", "克隆氏症（新診斷）": "Crohn's (new diagnosis)",
            "潰瘍性結腸炎（新診斷）": "UC (new diagnosis)", "IgG4 相關疾病": "IgG4-RD", "特發性肺纖維化（急性惡化）": "IPF (acute exacerbation)"}
    styles = [("-", "o"), ("--", "s"), (":", "^"), ("-.", "D"), ((0, (5, 1, 1, 1)), "v")]  # 文獻曲線同為藍色，以線型區分
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.3), gridspec_kw={"width_ratios": [1.25, 1]})
    tt = np.linspace(0.05, 7.5, 200)
    for c, (ls, mk) in zip(cur, styles):
        k, lam = c["k"], c["lambda_years"]
        lab = (c["curve"] if lang == "zh" else en_c[c["curve"]]) + f"  k={k:.2f}"
        a1.plot(tt, 1 - np.exp(-(tt / lam) ** k), color=LIT, ls=ls, lw=1.6)
        a1.plot(c["t"], c["cum"], color=LIT, ls=ls, lw=0, marker=mk, markersize=6, mec="white", label=lab)
    a1.set_xlabel("追蹤年數" if lang == "zh" else "Years of follow-up"); a1.set_ylabel("累積復發比例" if lang == "zh" else "Cumulative recurrence")
    a1.set_ylim(0, 1)
    h = [plt.Line2D([], [], color=LIT, ls=ls, marker=mk, mec="white", label=l.get_label()) for (ls, mk), l in zip(styles, a1.lines[1::2])]
    a1.legend(handles=h, fontsize=8.3, loc="lower right", handlelength=3)
    a1.set_title("（a）文獻累積復發曲線與 Weibull 擬合" if lang == "zh" else "(a) Published curves and Weibull fits", loc="left", fontsize=11)
    c = pd.read_csv(os.path.join(PD, "交叉對比_逐病一年復發率.csv"))
    data = [[x["k"] for x in cur], c.weibull_k_orig.dropna().values, c.weibull_k_calib.dropna().values]
    names = [t("lit", lang), "原始虛擬" if lang == "zh" else "Original", "新數據" if lang == "zh" else "New data"]
    for i, (d, col) in enumerate(zip(data, [LIT, ORIG, NEW])):
        x = np.full(len(d), i) + np.linspace(-0.12, 0.12, len(d))
        a2.scatter(x, d, color=col, s=30, edgecolor="white", zorder=3)
        a2.plot([i - 0.25, i + 0.25], [np.median(d)] * 2, color=INK, lw=2)
        a2.text(i + 0.28, np.median(d), f"{np.median(d):.2f}", va="center", fontsize=9)
    a2.axhline(1, color=GREY, ls="--", lw=1)
    a2.text(2.45, 1.02, "k = 1：風險不隨時間改變" if lang == "zh" else "k = 1: constant risk", fontsize=8.5, color="#666666", ha="right", va="bottom")
    a2.set_xticks(range(3), names); a2.set_ylabel("Weibull 形狀參數 k" if lang == "zh" else "Weibull shape k")
    a2.set_title("（b）k < 1 代表越早期越容易復發" if lang == "zh" else "(b) k < 1 means risk is highest early", loc="left", fontsize=11)
    fig.tight_layout()
    save(fig, "fig05_timing_weibull", lang)


# ───────── 圖 6 劑量反應：過去復發次數 → 未來復發 ─────────
def fig_dose(lang):
    ms = R["literature"]["ms_prior_relapse_rr"]
    o = np.array(R["mechanisms"]["original"]["dose_response_rate_y2"])
    n = np.array(R["mechanisms"]["calibrated"]["dose_response_rate_y2"])
    x = np.arange(4)
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    for y, col, mk, lab in ((ms, LIT, "o", "文獻：多發性硬化症（Held 等，2005）" if lang == "zh" else "Literature: MS (Held et al., 2005)"),
                            (o / o[0], ORIG, "x", t("orig", lang)), (n / n[0], NEW, "s", "新數據" if lang == "zh" else "New data")):
        ax.plot(x, y, color=col, marker=mk, markersize=8, mew=2, label=lab)
        ax.text(3.08, y[-1], f"{y[-1]:.1f}", va="center", fontsize=9, color=INK)
    ax.set_xticks(x, ["0", "1", "2", "≥3"])
    ax.set_xlabel("過去一段時間的復發次數" if lang == "zh" else "Number of recent past recurrences")
    ax.set_ylabel("之後的復發率（相對於 0 次）" if lang == "zh" else "Later recurrence rate (relative to 0)")
    ax.legend(fontsize=9)
    save(fig, "fig06_dose_response", lang)


# ───────── 圖 7 紀錄長度與 AUROC ─────────
def fig_length(lang):
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    W = R["settings"]["windows"]
    for key, col, mk, lab in (("calibrated", NEW, "o", "新數據" if lang == "zh" else "New data"), ("original", ORIG, "s", t("orig", lang))):
        a = R["models"][key]["auroc"]
        v = np.array([a[f"紀錄 {w} 天"] for w in W])
        ax.fill_between(range(len(W)), v[:, 1], v[:, 2], color=col, alpha=0.15, lw=0)
        ax.plot(range(len(W)), v[:, 0], color=col, marker=mk, label=lab + ("：logistic（年齡性別病別＋紀錄）" if lang == "zh" else ": logistic (age, sex, disease + records)"))
        ax.axhline(a["只用年齡性別病別"][0], color=col, ls="--", lw=1.2)
        ax.text(len(W) - 0.95, a["只用年齡性別病別"][0], "只用年齡性別病別" if lang == "zh" else "age, sex, disease only", fontsize=8.5, color=col, va="bottom")
        ax.axhline(a["只用文獻（未訓練）"][0], color=col, ls=":", lw=1.2)
        ax.text(len(W) - 0.95, a["只用文獻（未訓練）"][0], "只用文獻（未訓練）" if lang == "zh" else "literature only (untrained)", fontsize=8.5, color=col, va="bottom")
    ax.set_xticks(range(len(W)), [str(w) for w in W]); ax.set_xlim(-0.2, len(W) + 0.6)
    ax.set_xlabel("預測時往回看的紀錄長度（天）" if lang == "zh" else "Length of records used (days)")
    ax.set_ylabel("AUROC（未來 90 天復發）" if lang == "zh" else "AUROC (recurrence within 90 days)")
    ax.set_ylim(0.5, 0.9); ax.legend(fontsize=8.8, loc="upper left")
    save(fig, "fig07_record_length_auroc", lang)


# ───────── 圖 8 ROC、圖 9 校準 ─────────
NAMES = {"只用年齡性別病別": "Age, sex, disease only", "只用文獻（未訓練）": "Literature only (untrained)",
         "紀錄 730 天": "Records 730 days (logistic)", "梯度提升樹 730 天": "Gradient boosting 730 days"}


def fig_roc(lang):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.5))
    for ax, key, title in ((axes[0], "calibrated", "（a）新數據" if lang == "zh" else "(a) New data"),
                           (axes[1], "original", "（b）原始虛擬患者" if lang == "zh" else "(b) Original virtual cohort")):
        d = pd.read_csv(os.path.join(PD, f"ROC_{key}.csv"))
        a = R["models"][key]["auroc"]
        for (m, g), col, ls in zip(d.groupby("模型", sort=False), [GREY, LIT, NEW, MODEL], ["--", ":", "-", "-"]):
            lab = (m if lang == "zh" else NAMES[m]) + f"  {a[m][0]:.2f}"
            ax.plot(g.fpr, g.tpr, color=col, ls=ls, lw=1.8, label=lab)
        ax.plot([0, 1], [0, 1], color="#cccccc", lw=0.8)
        ax.set_title(title, loc="left", fontsize=11); ax.legend(fontsize=8.3, loc="lower right")
        ax.set_xlabel("1 − 特異度" if lang == "zh" else "1 − specificity"); ax.set_ylabel("敏感度" if lang == "zh" else "Sensitivity")
        ax.grid(axis="x", color="#e3e3e3")
    fig.tight_layout()
    save(fig, "fig08_roc", lang)


def fig_calibration(lang):
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    for key, col, mk, lab in (("calibrated", NEW, "o", "新數據" if lang == "zh" else "New data"), ("original", ORIG, "s", t("orig", lang))):
        d = pd.read_csv(os.path.join(PD, f"校準_{key}.csv"))
        cs = R["models"][key]["calibration"]["紀錄 730 天"]
        ax.plot(d.pred, d.obs, color=col, marker=mk, label=f"{lab}（斜率 {cs['slope']:.2f}）" if lang == "zh" else f"{lab} (slope {cs['slope']:.2f})")
    ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1)
    ax.set_xlabel("模型預測的復發機率（十分位平均）" if lang == "zh" else "Predicted probability (decile mean)")
    ax.set_ylabel("實際復發比例" if lang == "zh" else "Observed proportion")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.legend(fontsize=9, loc="upper left"); ax.grid(axis="x", color="#e3e3e3")
    save(fig, "fig09_calibration", lang)


# ───────── 圖 10 時間線 ─────────
def fig_timeline(lang):
    d = pd.read_csv(os.path.join(PD, "時間線_風險三分組.csv"))
    en = {"低": "Low", "中": "Middle", "高": "High"}
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    for (g, gg), col in zip(d.groupby("組別", sort=False), ["#b3a9ee", "#7d6be0", "#3b2a9e"]):  # 模型色（紫）由淺到深＝低到高
        name = (f"{g}風險組" if lang == "zh" else f"{en[g]} risk")
        ax.step(gg.day, gg.observed, where="post", color=col, lw=2, label=name + ("：實際" if lang == "zh" else ": observed"))
        ax.plot(gg.day, gg.predicted, color=col, ls="--", lw=1.4, label=name + ("：模型預測" if lang == "zh" else ": predicted"))
    ax.set_xlabel("預測時點之後的天數" if lang == "zh" else "Days after the prediction point")
    ax.set_ylabel("累積復發比例" if lang == "zh" else "Cumulative recurrence")
    ax.legend(fontsize=8.5, ncol=2, loc="upper left"); ax.set_xlim(0, 365)
    save(fig, "fig10_timeline", lang)


# ───────── 圖 11 紀錄品質、圖 12 預警、圖 13 特徵 ─────────
def fig_quality(lang):
    s = R["sensitivity"]
    en = ["Recall-style (30% of days, 0.8 SD error)", "This study (70%, 0.3 SD)", "Complete records (100%, no error)", "Upper bound: latent activity seen"]
    names = list(s)
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    y = np.arange(len(names))[::-1]
    for yy, n, col in zip(y, names, [GREY, NEW, "#127a55", MODEL]):
        a = s[n]["auc"]
        ax.barh(yy + 0.18, a[0], height=0.34, color=col)
        ax.plot([a[1], a[2]], [yy + 0.18] * 2, color=INK, lw=1)
        ax.barh(yy - 0.18, s[n]["within_disease_auc_weighted"], height=0.34, color=col, alpha=0.45)
        ax.text(a[2] + 0.005, yy + 0.18, f"{a[0]:.3f}", va="center", fontsize=8.5)
        ax.text(s[n]["within_disease_auc_weighted"] + 0.005, yy - 0.18, f"{s[n]['within_disease_auc_weighted']:.3f}", va="center", fontsize=8.5)
    ax.set_yticks(y, names if lang == "zh" else en, fontsize=9)
    ax.set_xlim(0.5, 0.85); ax.grid(axis="x", color="#e3e3e3"); ax.grid(axis="y", visible=False)
    ax.set_xlabel("AUROC（深色＝全體；淺色＝病別內平均）" if lang == "zh" else "AUROC (dark = overall; light = within-disease mean)")
    save(fig, "fig11_record_quality", lang)


def fig_warning(lang):
    ew = R["models"]["calibrated"]["early_warning"]
    keys = ["只用年齡性別病別", "只用文獻（未訓練）", "紀錄 730 天"]
    labs = keys if lang == "zh" else [NAMES[k] for k in keys]
    met = [("sensitivity", "敏感度" if lang == "zh" else "Sensitivity"), ("ppv", "陽性預測值" if lang == "zh" else "PPV"),
           ("lift", "提升倍數" if lang == "zh" else "Lift")]
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.4), gridspec_kw={"width_ratios": [1, 1, 1, 1.3]})
    for ax, (m, title) in zip(axes[:3], met):
        v = [ew[k][m] for k in keys]
        ax.bar(range(3), v, color=[GREY, LIT, NEW], width=0.6)
        for i, x in enumerate(v):
            ax.text(i, x, f"{x:.2f}", ha="center", va="bottom", fontsize=8.5)
        ax.set_xticks(range(3), ["①", "②", "③"]); ax.set_title(title, fontsize=10.5)
    ax = axes[3]
    for i, (k, col) in enumerate(zip(keys, [GREY, LIT, NEW])):
        q1, q3 = ew[k]["lead_days_iqr"]
        ax.plot([q1, q3], [i, i], color=col, lw=6, alpha=0.5, solid_capstyle="round")
        ax.plot(ew[k]["lead_days_median"], i, "o", color=col, markersize=8, mec="white")
        ax.text(q3 + 2, i, f"{ew[k]['lead_days_median']:.0f}", va="center", fontsize=8.5)
    ax.set_yticks(range(3), ["①", "②", "③"]); ax.set_xlim(0, 95); ax.grid(axis="x", color="#e3e3e3")
    ax.set_title("提前天數（中位數與四分位距）" if lang == "zh" else "Lead time, days (median, IQR)", fontsize=10.5)
    fig.text(0.5, -0.04, "　".join(f"{n}{l}" for n, l in zip(["①", "②", "③"], labs)), ha="center", fontsize=9)
    fig.tight_layout()
    save(fig, "fig12_early_warning", lang)


def fig_coef(lang):
    c = R["models"]["calibrated"]["coef_730"]
    zh = {"n_onsets": "過去兩年復發次數", "days_since_onset": "距上次復發天數", "sym_mean": "症狀平均", "sym_max": "症狀最高值",
          "sym_sd": "症狀起伏（標準差）", "sym_last14": "最近 14 天症狀", "sym_slope": "症狀變化斜率", "skip_frac": "漏服比例",
          "trig_frac": "誘發因子天數比例", "lab_last": "最近一次檢驗", "lab_mean": "檢驗平均"}
    en = {"n_onsets": "Recurrences in past 2 years", "days_since_onset": "Days since last recurrence", "sym_mean": "Mean symptom score",
          "sym_max": "Max symptom score", "sym_sd": "Symptom variability (SD)", "sym_last14": "Symptoms, last 14 days",
          "sym_slope": "Symptom slope", "skip_frac": "Missed-dose fraction", "trig_frac": "Days with triggers", "lab_last": "Latest lab value",
          "lab_mean": "Mean lab value"}
    items = sorted(((k.replace("w730_", ""), v) for k, v in c.items()), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    for i, (k, v) in enumerate(items):
        ax.barh(i, v, color=NEW if v > 0 else GREY, height=0.6)
        ax.text(v + (0.01 if v >= 0 else -0.01), i, f"{v:+.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=8.5)
    ax.set_yticks(range(len(items)), [(zh if lang == "zh" else en)[k] for k, _ in items], fontsize=9)
    ax.axvline(0, color=INK, lw=0.8); ax.grid(axis="x", color="#e3e3e3"); ax.grid(axis="y", visible=False)
    ax.set_xlim(-0.35, 0.55)
    ax.set_xlabel("標準化 logistic 係數（正值＝風險較高）" if lang == "zh" else "Standardized logistic coefficient (positive = higher risk)")
    save(fig, "fig13_features", lang)


if __name__ == "__main__":
    setup_fonts(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FONT_DIR"))
    for lang in ("zh", "en"):
        for f in (fig_framework, fig_workflow, fig_annual, fig_forest, fig_weibull, fig_dose, fig_length, fig_roc,
                  fig_calibration, fig_timeline, fig_quality, fig_warning, fig_coef):
            f(lang)
    print("figures ->", FIG, len(os.listdir(FIG)))
