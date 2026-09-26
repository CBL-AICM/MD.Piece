# -*- coding: utf-8 -*-
"""v3 論文圖（回應審查 §五）——全部由 results/v3_audit.json、v3_eval.json、exwas_v3_checks.json 與
params/direction_model.json 生成，數字不手打。  python make_figures_v3.py [複製目的資料夾]

圖1 分析樣本與三值標籤      圖2 判別力：部署工具與同切分基準、標籤定義敏感度
圖3 校準與分區              圖4 回溯時間評估（擴展視窗）
圖5 決策曲線                圖6 暴露探索：同一批人血尿比較（鉛、鎘 × 三種結果定義）
圖S1 單一受試者輸出示範（概似比量尺；僅展示）
不畫「原始目標 0.90」參考線；差值一律由未四捨五入值計算並於圖說註明。
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib                                                    # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import numpy as np                                                   # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch       # noqa: E402

for fam in ("Microsoft JhengHei", "Microsoft YaHei", "PMingLiU"):
    try:
        matplotlib.font_manager.findfont(fam, fallback_to_default=False)
        plt.rcParams["font.family"] = fam
        break
    except Exception:
        continue
plt.rcParams.update({"axes.unicode_minus": False, "axes.edgecolor": "#b9b8b3", "axes.linewidth": 0.8,
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "axes.labelcolor": "#0b0b0b"})
FIG = os.path.join(ROOT, "figures", "v3")
os.makedirs(FIG, exist_ok=True)
INK, SUB, MUTED, GRID, GRAY = "#0b0b0b", "#52514e", "#8a8985", "#e6e5e1", "#a3a29d"
AX = {"肝炎": "#2a78d6", "糖尿病": "#eb6834"}          # 驗證過之類別色（slot 1、2）
NAME = {"肝炎": "肝炎病毒感染標籤", "糖尿病": "糖尿病標籤"}
J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))
A, E = J("results", "v3_audit.json"), J("results", "v3_eval.json")["axes"]


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[完成] {name}")


def tidy(ax, grid="x"):
    ax.spines[["top", "right"]].set_visible(False)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.8)
        ax.set_axisbelow(True)


def box(ax, x, y, w, h, text, fc="#f4f3f0", ec="#b9b8b3", fs=10, bold=False, color=INK):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.05", fc=fc, ec=ec, lw=1.1))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=color, linespacing=1.55,
            weight="bold" if bold else "normal")


def arrow(ax, p, q):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=13, lw=1.1, color=SUB))


def fig1():
    T, R = A["total"], A["reclassification"]
    k = T["kidney"]
    fig, ax = plt.subplots(figsize=(10.5, 8.6))
    ax.set_xlim(0, 10.5); ax.set_ylim(0, 10); ax.axis("off")
    box(ax, 5.25, 9.35, 7.4, 0.8, f"NHANES 1999–2018 十個週期　成人（≧20 歲）\nn = {A['old_rebuild']['n_adults']:,}", fs=10.5)
    arrow(ax, (5.25, 8.93), (5.25, 8.38))
    box(ax, 5.25, 7.75, 9.6, 1.15,
        f"腎臟指標（單次檢驗；eGFR<60 或 ACR≧30 mg/g）三值判定\n"
        f"異常 {k['pos']:,}　｜　兩項皆測且正常 {k['neg']:,}　｜　未知 {k['unknown']:,}\n"
        f"（未知＝一項正常另一項缺 {T['kidney_unknown_one_normal_one_missing']:,}；兩項皆缺 {T['kidney_unknown_both_missing']:,}）",
        fc="#fff8e6", fs=10)
    for x, key, sub in ((2.65, "肝炎", "hep_in_kidney"), (7.85, "糖尿病", "dm_in_kidney")):
        arrow(ax, (5.25, 7.15), (x, 6.35))
        t = T[sub]
        extra = (f"HBsAg 陽性 {T['hbv_in_kidney']['pos']}、HCV RNA 陽性 {T['hcv_in_kidney']['pos']}（兩者皆陽 {T['both_hbv_and_hcv']}）"
                 if key == "肝炎" else
                 f"醫師診斷 {T['dmq_in_kidney']['pos']:,}、HbA1c≧6.5% {T['dma_in_kidney']['pos']:,}")
        box(ax, x, 5.55, 4.9, 1.55,
            f"{NAME[key]}\n陽性 {t['pos']:,}　陰性 {t['neg']:,}　未知 {t['unknown']:,}\n→ 該軸分析 n = {t['pos'] + t['neg']:,}\n{extra}",
            fc="#ffffff", ec=AX[key], fs=9.6)
    ax.text(5.25, 4.45, "兩個標籤各自判定、可同時成立；各軸只排除該軸未知者", ha="center", fontsize=9, color=SUB, style="italic")
    # 交叉表
    ct = A["two_label_crosstab_in_kidney"]
    rows, cols = ["陽性", "陰性", "未知"], ["陽性", "陰性", "未知"]
    x0, y0, cw, rh = 3.15, 3.75, 1.4, 0.36
    ax.text(x0 - 0.1, y0 + 0.05, "肝炎＼糖尿病", ha="right", va="center", fontsize=9, color=SUB)
    for j, c in enumerate(cols):
        ax.text(x0 + cw * (j + 0.5), y0 + 0.05, c, ha="center", va="center", fontsize=9.2, color=SUB, weight="bold")
    for i, r in enumerate(rows):
        yy = y0 - rh * (i + 1)
        ax.text(x0 - 0.1, yy, r, ha="right", va="center", fontsize=9.2, color=SUB, weight="bold")
        for j, c in enumerate(cols):
            ax.add_patch(plt.Rectangle((x0 + cw * j, yy - rh / 2), cw, rh, fc="#fafaf8", ec="#d6d5d0", lw=0.8))
            ax.text(x0 + cw * (j + 0.5), yy, f"{ct[r][c]:,}", ha="center", va="center", fontsize=9.6, color=INK)
    ax.text(x0 + 1.5 * cw, y0 - rh * 4 + 0.02, "腎臟指標異常者之兩標籤交叉表（人數）", ha="center", va="center", fontsize=9, color=SUB)
    s, u = R["scr_fix_1999_2000"], R["ucr_fix_pre2007"]
    box(ax, 5.25, 1.05, 9.6, 1.25,
        f"v3 資料更正（與原稿相比）\n1999–2000 血清肌酸酐改用官方式 1.013X＋0.147：該週期 eGFR<60 由 {s['egfr_lt60_old']} 人更正為 {s['egfr_lt60_new']} 人\n"
        f"2007 年前尿肌酸酐依官方分段式轉換：ACR 跨越 30 mg/g 者 增 {u['acr_cross30_up']}、減 {u['acr_cross30_down']}"
        f"　→　腎臟指標異常 {R['combined']['kidney_old']:,} → {R['combined']['kidney_new']:,}",
        fc="#f7f7fb", ec="#b9b8b3", fs=9.3)
    save(fig, "圖1_分析樣本與三值標籤.png")


MODELS = [("M1_demographics", "僅年齡、性別"), ("M2_basic_panel", "常規套組 LR"),
          ("M3_full", "全特徵 LR（單一模型）"), ("M4_full_HGB", "全特徵梯度提升")]


def fig2():
    fig, axs = plt.subplots(2, 3, figsize=(15.2, 7.6), gridspec_kw={"width_ratios": [1.15, 1.15, 1]})
    fig.subplots_adjust(wspace=0.55, hspace=0.62)
    for r, key in enumerate(("肝炎", "糖尿病")):
        a, t = E[key], E[key]["tool"]
        c = a["comparisons"]
        labs = [lab for _, lab in MODELS] + ["部署工具（集成＋校準）"]
        for col, (metric, rng_key, xlabel) in enumerate((("auroc", "auroc_range", "AUROC"), ("ap", "ap_range", "AP（平均精確率）"))):
            ax = axs[r, col]
            vals = [c[m][f"{metric}_mean"] for m, _ in MODELS] + [t["repeats"]["mean"][f"{metric}_cal"]]
            lo = [c[m][rng_key][0] for m, _ in MODELS] + [t["repeats"]["min"][f"{metric}_cal"]]
            hi = [c[m][rng_key][1] for m, _ in MODELS] + [t["repeats"]["max"][f"{metric}_cal"]]
            y = np.arange(len(vals))[::-1]
            for yi, v, l, h, lab in zip(y, vals, lo, hi, labs):
                col_ = AX[key] if lab.startswith("部署") else GRAY
                ax.plot([l, h], [yi, yi], color=col_, lw=2.2, solid_capstyle="round")
                ax.plot(v, yi, "o", color=col_, ms=8, zorder=3, mec="white", mew=1.2)
                ax.annotate(f"{v:.3f}", xy=(max(h, v), yi), xytext=(7, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
            base = 0.5 if metric == "auroc" else t["prevalence"]
            ax.axvline(base, color=MUTED, ls=":", lw=1.1)
            ax.text(base, 0.015, " 隨機" if metric == "auroc" else f" 盛行率 {base:.3f}", transform=ax.get_xaxis_transform(),
                    ha="left", va="bottom", fontsize=8.3, color=SUB)
            ax.set_yticks(y); ax.set_yticklabels(labs, fontsize=9.2)
            ax.set_xlabel(xlabel, fontsize=9.6)
            ax.set_xlim((0.45, 0.9) if metric == "auroc" else (0, max(hi) * 1.3))
            tidy(ax)
            ax.set_title(f"({'ab'[col]}{r + 1}) {NAME[key]}：{xlabel.split('（')[0]}", fontsize=10.4, loc="left", weight="bold")
        # 標籤敏感度
        ax = axs[r, 2]
        ls = a["label_sensitivity"]
        items = [("主分析標籤", t["n"], t["n_pos"], t["repeats"]["mean"]["auroc_cal"], True)] + \
                [(k.split("_", 1)[0] + "（" + k.split("_", 1)[1] + "）" if "_" in k else k, v["n"], v["n_pos"], v["auroc"], False)
                 for k, v in ls.items()]
        y = np.arange(len(items))[::-1]
        for yi, (lab, n, npos, v, main) in zip(y, items):
            ax.barh(yi, v - 0.5, left=0.5, height=0.55, color=AX[key] if main else GRAY, alpha=0.9 if main else 0.8)
            ax.text(v + 0.008, yi, f"{v:.3f}", va="center", fontsize=9, color=INK)
        ax.set_yticks(y); ax.set_yticklabels([f"{i[0]}\n陽性 {i[2]:,}／n {i[1]:,}" for i in items], fontsize=8.6)
        ax.set_xlim(0.5, 0.9); ax.set_xlabel("AUROC（巢狀外層，單次重複）", fontsize=9.6)
        tidy(ax)
        ax.set_title(f"(c{r + 1}) 標籤定義敏感度", fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖2　判別力：部署工具與同一切分之基準模型（點＝五次重複平均，線＝五次重複之最小至最大）",
                 fontsize=12.2, weight="bold", y=1.0)
    save(fig, "圖2_判別力與基準.png")


def fig3():
    fig, axs = plt.subplots(2, 2, figsize=(12.6, 9.2), gridspec_kw={"width_ratios": [1, 1.25]})
    fig.subplots_adjust(wspace=0.32, hspace=0.5)
    for r, key in enumerate(("肝炎", "糖尿病")):
        t = E[key]["tool"]
        cv = t["calibration_curve_repeat0"]
        ax = axs[r, 0]
        mp, ob = [p["mean_pred"] for p in cv], [p["observed"] for p in cv]
        lim = max(max(mp), max(ob)) * 1.12
        ax.plot([0, lim], [0, lim], color=MUTED, ls="--", lw=1)
        ax.plot(mp, ob, "-o", color=AX[key], lw=2, ms=7, mec="white", mew=1.2)
        c = t["calibration_repeat0"]
        ax.text(0.04, 0.96, f"校準截距 {c['intercept']:.2f}\n校準斜率 {c['slope']:.2f}\nBrier {c['brier']:.3f}（skill {c['brier_skill']:.2f}）",
                transform=ax.transAxes, va="top", fontsize=9, color=INK)
        ax.set_xlim(0, lim); ax.set_ylim(0, lim)
        ax.set_xlabel("平均預測機率（分位數分箱）", fontsize=9.6); ax.set_ylabel("實際陽性比例", fontsize=9.6)
        tidy(ax, "both")
        ax.set_title(f"(a{r + 1}) {NAME[key]}：校準曲線", fontsize=10.4, loc="left", weight="bold")
        ax = axs[r, 1]
        bands = ["傾向", "不確定", "不傾向"]
        w = 0.36
        for j, (rule, lab, colr) in enumerate((("A", "舊規則（2×／0.5× 盛行率）", GRAY), ("B", "v3 規則（2×／0.5× 事前勝算）", AX[key]))):
            bs = t["bands_repeat0"][rule]["band"]
            xs = np.arange(3) + (j - 0.5) * w
            rates = [bs[b]["observed_rate"] or 0 for b in bands]
            ax.bar(xs, rates, width=w - 0.03, color=colr, label=lab, alpha=0.9)
            for x, b, rt in zip(xs, bands, rates):
                ax.text(x, rt, f"{rt:.1%}\nn={bs[b]['n']:,}", ha="center", va="bottom", fontsize=8.2, color=INK)
        ax.axhline(t["prevalence"], color=MUTED, ls=":", lw=1.1)
        ax.text(2.55, t["prevalence"], f"盛行率 {t['prevalence']:.1%}", va="bottom", ha="right", fontsize=8.3, color=SUB)
        ax.set_xticks(range(3)); ax.set_xticklabels(bands, fontsize=9.6)
        ax.set_ylabel("該區實際陽性比例", fontsize=9.6)
        ax.set_ylim(0, max(bs[b]["observed_rate"] or 0 for b in bands) * 1.35 + 0.01)
        bA, bB = t["bands_repeat0"]["A"], t["bands_repeat0"]["B"]
        ax.legend(fontsize=8.6, frameon=False, loc="upper right")
        ax.text(0.0, -0.2, f"涵蓋率 舊 {bA['coverage']:.1%} → v3 {bB['coverage']:.1%}；不傾向區之陽性 舊 {bA['positives_in_low']} → v3 {bB['positives_in_low']} 人"
                           f"（共 {t['n_pos']:,}）", transform=ax.transAxes, fontsize=8.8, color=SUB)
        tidy(ax, "y")
        ax.set_title(f"(b{r + 1}) {NAME[key]}：三段分區之實際陽性比例", fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖3　校準與分區（巢狀外層預測；校準器與門檻只用外層訓練資料）", fontsize=12.2, weight="bold", y=0.995)
    save(fig, "圖3_校準與分區.png")


def fig4():
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    fig.subplots_adjust(wspace=0.25)
    for ax, key in zip(axs, ("肝炎", "糖尿病")):
        tm = E[key]["temporal"]
        ew = tm["expanding_window"]
        cyc = list(ew.keys())
        x = np.arange(len(cyc))
        v = [ew[c]["auroc"] for c in cyc]
        lo = [ew[c]["ci95"]["auroc"][0] for c in cyc]
        hi = [ew[c]["ci95"]["auroc"][1] for c in cyc]
        ax.vlines(x, lo, hi, color=AX[key], lw=2.2, alpha=0.55)
        ax.plot(x, v, "o", color=AX[key], ms=8, mec="white", mew=1.2, zorder=3)
        for xi, c, vi, h in zip(x, cyc, v, hi):
            ax.text(xi, h + 0.012, f"{vi:.3f}", ha="center", fontsize=8.6, color=INK)
            ax.text(xi, 0.405, f"陽性 {ew[c]['n_pos']}", ha="center", fontsize=8.2, color=SUB)
        ref = E[key]["tool"]["repeats"]["mean"]["auroc_cal"]
        ax.axhline(ref, color=MUTED, ls="--", lw=1)
        ax.text(len(cyc) - 0.45, ref, "巢狀外層\n" + f"{ref:.3f}", va="center", ha="left", fontsize=8.6, color=SUB)
        ax.set_xlim(-0.5, len(cyc) + 0.5)
        ax.axhline(0.5, color=MUTED, ls=":", lw=1)
        el = tm["early_to_late"]
        ax.set_xticks(x); ax.set_xticklabels([c[:4] + "–" + c[7:] for c in cyc], fontsize=8.8)
        ax.set_ylim(0.38, 1.0); ax.set_ylabel("AUROC（95% CI）", fontsize=9.6)
        ax.set_xlabel("評估週期（只以更早的週期訓練）", fontsize=9.6)
        tidy(ax, "y")
        ax.set_title(f"{NAME[key]}：1999–2008→2009–2018 為 {el['auroc']:.3f} [{el['ci95']['auroc'][0]:.3f}, {el['ci95']['auroc'][1]:.3f}]",
                     fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖4　回溯時間評估（擴展視窗；較晚週期先前已被檢視，非確認性驗證）", fontsize=12.2, weight="bold", y=1.03)
    save(fig, "圖4_回溯時間評估.png")


def fig5():
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8))
    fig.subplots_adjust(wspace=0.28)
    for ax, key in zip(axs, ("肝炎", "糖尿病")):
        d = E[key]["decision_curve"]
        pt = [r["pt"] for r in d]
        ax.plot(pt, [r["nb_model"] for r in d], color=AX[key], lw=2.2, label="依部署工具機率送驗（p ≧ pt）")
        ax.plot(pt, [r["nb_test_all"] for r in d], color=GRAY, lw=1.8, ls="--", label="全數送驗")
        ax.axhline(0, color=INK, lw=1, label="全不送驗")
        top = max(max(r["nb_model"] for r in d), max(r["nb_test_all"] for r in d))
        ax.set_ylim(-top * 0.35, top * 1.2)
        ax.set_xlim(min(pt), max(pt))
        ax.set_xlabel("閾值機率 pt（願意為找出 1 名陽性而多驗之人數＝(1-pt)/pt）", fontsize=9.4)
        ax.set_ylabel("淨效益", fontsize=9.6)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0 if key == "糖尿病" else 1))
        tidy(ax, "both")
        ax.legend(fontsize=8.6, frameon=False, loc="upper right")
        b = E[key]["tool"]["bands_repeat0"]["B"]["per_1000_if_skip_low"]
        ax.set_title(f"{NAME[key]}", fontsize=10.4, loc="left", weight="bold")
        note = "\n".join(["若只略過「不傾向」區：", f"每千人送驗 {b['tested']:.0f}、漏 {b['missed']:.1f} 名陽性",
                          f"（占陽性 {b['missed_share_of_pos']:.0%}）"])
        ax.text(0.98, 0.70, note, transform=ax.transAxes, fontsize=8.6, color=SUB, ha="right", va="top")
    fig.suptitle("圖5　決策曲線（巢狀外層預測）——閾值須由實際檢驗之利弊決定；肝炎指引建議成人普遍篩檢，相當於極低閾值",
                 fontsize=12, weight="bold", y=1.03)
    save(fig, "圖5_決策曲線.png")


def fig6():
    X = J("results", "exwas_v3_checks.json")
    outs = [("kidney_damage", "腎臟指標異常\n（eGFR<60 或 ACR≧30）"), ("egfr_lt60", "僅 eGFR<60\n（與尿肌酸酐無共同分母）"),
            ("acr_ge30", "僅 ACR≧30")]
    meas = [("血中", "血中", "#2a78d6"), ("尿中_原濃度", "尿中（原濃度）", "#eb6834"),
            ("尿中_原濃度＋尿肌酸酐共變數", "尿中（＋尿肌酸酐共變數）", "#eb6834"), ("尿中_肌酸酐比值", "尿中（肌酸酐比值）", "#eb6834")]
    fig, axs = plt.subplots(2, 3, figsize=(14, 6.6), sharex=True)
    fig.subplots_adjust(wspace=0.08, hspace=0.35)
    for r, metal in enumerate(("鉛", "鎘")):
        M = X["metals"][metal]
        for cidx, (ok, olab) in enumerate(outs):
            ax = axs[r, cidx]
            y = np.arange(len(meas))[::-1]
            for yi, (mk, mlab, colr) in zip(y, meas):
                m = M["models"][ok][mk]
                ax.plot(m["ci"], [yi, yi], color=colr, lw=2.2, solid_capstyle="round", alpha=0.8)
                ax.plot(m["OR_per_doubling"], yi, "o", color=colr, ms=7.5, mec="white", mew=1.1, zorder=3)
                ax.text(m["ci"][1] * 1.03, yi, f"{m['OR_per_doubling']:.2f}", va="center", fontsize=8.6, color=INK)
            ax.axvline(1, color=MUTED, ls=":", lw=1.1)
            ax.set_xscale("log")
            ax.set_xticks([0.5, 0.7, 1, 1.4, 2]); ax.set_xticklabels(["0.5", "0.7", "1", "1.4", "2"])
            ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
            ax.set_xlim(0.5, 2)
            ax.set_yticks(y)
            ax.set_yticklabels([m[1] for m in meas] if cidx == 0 else [], fontsize=9)
            tidy(ax)
            if r == 0:
                ax.set_title(olab, fontsize=10, weight="bold")
            if cidx == 0:
                ax.text(-0.62, 0.5, f"{metal}\nn={M['n_both']:,}", transform=ax.transAxes, fontsize=11, weight="bold", va="center")
        axs[1, 1].set_xlabel("勝算比（濃度加倍；M3 調整；95% CI，對數刻度）", fontsize=9.6)
    fig.suptitle("圖6　探索性暴露關聯：同一批受試者（2005–2018，血、尿皆有值）之血中與尿中鉛、鎘", fontsize=12.2, weight="bold", y=1.0)
    save(fig, "圖6_暴露血尿比較.png")


def figS1():
    from direction import predict
    M = J("params", "direction_model.json")
    v = J("params", "direction_demo_patient.json")
    exp = J("params", "direction_demo_expected.json")
    res = predict(v, M)
    fig, axs = plt.subplots(2, 2, figsize=(13, 6.6), gridspec_kw={"width_ratios": [1.2, 1]})
    fig.subplots_adjust(hspace=0.75, wspace=0.42)
    for r, key in enumerate(("肝炎", "糖尿病")):
        a = res["axes"][key]
        ax = axs[r, 0]
        lo, hi = np.log2(0.5), np.log2(2)
        ax.axvspan(-2.2, lo, color=AX[key], alpha=0.14, lw=0)
        ax.axvspan(lo, hi, color="#eeeeea", lw=0)
        ax.axvspan(hi, 2.2, color=AX[key], alpha=0.38, lw=0)
        for x0, x1, lab in ((-2.2, lo, "不傾向"), (lo, hi, "不確定"), (hi, 2.2, "傾向")):
            ax.text((x0 + x1) / 2, 0.84, lab, ha="center", fontsize=9.6, color=INK, weight="bold")
        xv = float(np.clip(np.log2(max(a["odds_ratio_vs_prior"], 1e-9)), -2.1, 2.1))
        ax.plot([xv, xv], [0, 0.62], color=INK, lw=2.2)
        ax.plot(xv, 0.62, "v", color=INK, ms=11)
        ax.text(xv + (-0.08 if xv > 0 else 0.08), 0.3, f"機率 {a['probability']:.1%}\n（事前 {a['prevalence']:.1%}）\n勝算 ×{a['odds_ratio_vs_prior']:.2f}",
                ha="right" if xv > 0 else "left", va="center", fontsize=9.2, color=INK,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=AX[key], lw=1))
        ax.set_xlim(-2.2, 2.2); ax.set_ylim(0, 1); ax.set_yticks([])
        ax.set_xticks([-2, -1, 0, 1, 2]); ax.set_xticklabels(["×0.25", "×0.5", "×1", "×2", "×4"])
        ax.set_xlabel("相對事前勝算（概似比，對數刻度；×1＝與開發樣本盛行率相同）", fontsize=9)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.set_title(f"{a['title'].replace('≥', '≧')} → 「{a['band']}」", fontsize=10.4, loc="left", weight="bold", color=INK)
        ax = axs[r, 1]
        dv = a["drivers"]
        w = np.array([d["weight"] for d in dv])
        y = np.arange(len(dv))[::-1]
        ax.barh(y, w, color=[AX[key] if x > 0 else GRAY for x in w], height=0.55)
        ax.axvline(0, color=INK, lw=0.9)
        for yi, d, x in zip(y, dv, w):
            ax.text(x + (0.05 if x > 0 else -0.05), yi, d["push"], va="center", ha="left" if x > 0 else "right", fontsize=8.8, color=SUB)
        ax.set_yticks(y); ax.set_yticklabels([f"{d['name']} = {d['value']:.3g}" for d in dv], fontsize=9.2)
        lim = max(abs(w)) * 1.7
        ax.set_xlim(-lim, lim)
        ax.set_xlabel("對該軸模型分數之貢獻（標準化值×係數，五模型平均）", fontsize=8.8)
        tidy(ax)
        ax.set_title(f"主要依據（缺 {a['n_missing']}/{a['n_features']} 項以中位數補入）", fontsize=9.8, loc="left", weight="bold")
    fig.suptitle(f"圖S1　單一受試者輸出示範（SEQN {exp['SEQN']}，{exp['cycle']}；HCV RNA 陽性、無糖尿病）——僅展示，不代表準確率",
                 fontsize=11.6, weight="bold", y=1.0)
    save(fig, "圖S1_示範輸出.png")


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6(); figS1()
    if len(sys.argv) > 1:
        dst = sys.argv[1]
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(FIG):
            shutil.copy(os.path.join(FIG, f), os.path.join(dst, f))
        print(f"→ 已複製至 {dst}")
