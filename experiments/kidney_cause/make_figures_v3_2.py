# -*- coding: utf-8 -*-
"""v3.2 圖（科展作品說明書用）——全部由結果檔生成，數字不手打。  python make_figures_v3_2.py
    results/v3_2_cohort_audit.json、v3_2_eval.json、v3_2_external.json、external_2021_2023.json、direction_v3_2_recalibration.json、
    exwas_v3_2_checks.json

圖1 分析樣本、三值標籤與 v3.2 資料修正     圖2 判別力：常規／全特徵 × 線性／非線性
圖3 校準：線性與非線性模型                 圖4 穩健性：時間外推、人口加權、腎臟標籤定義
圖5 決策曲線                               圖6 暴露探索（v3.2 資料修正後重跑；params/exwas_v3_2_plan.json）
圖7 2021–2023：v3 事前指定之一次評估與 v3.2 事後評估   圖8 重新校準之交叉驗證
樣式沿用 make_figures_v3（驗證過之兩軸類別色、細線、2 px 間隔）。"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import matplotlib.pyplot as plt                                      # noqa: E402
import numpy as np                                                   # noqa: E402

from make_figures_v3 import AX, GRAY, INK, MUTED, NAME, SUB, arrow, box, tidy   # noqa: E402  (同時套用字型設定)

FIG = os.path.join(ROOT, "figures", "v3_2")
os.makedirs(FIG, exist_ok=True)
J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))
AU, E, X = J("results", "v3_2_cohort_audit.json"), J("results", "v3_2_eval.json")["axes"], J("results", "v3_2_external.json")
X3 = J("results", "external_2021_2023.json")["primary"]["axes"]
KEYS = ("肝炎", "糖尿病")
LR, HG = "LR_routine", "HGB_routine"
MLAB = {"LR_routine": "常規套組・邏輯迴歸", "LR_routine_noHDL": "常規套組・邏輯迴歸（不含 HDL）", "HGB_routine": "常規套組・梯度提升",
        "LR_full": "全特徵・邏輯迴歸", "HGB_full": "全特徵・梯度提升"}
DARK = {"肝炎": "#174a86", "糖尿病": "#a4410f"}     # 同色系深階：非線性模型


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[完成] {name}")


def total(key):
    return {k: sum(c[key][k] for c in AU["per_cycle"].values()) for k in ("pos", "neg", "unknown")}


def fig1():
    k = AU["kidney"]["v3_2"]
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    ax.set_xlim(0, 10.5); ax.set_ylim(0, 9); ax.axis("off")
    box(ax, 5.25, 8.35, 7.4, 0.8, f"NHANES 1999–2018 十個週期　成人（≧20 歲）\nn = {AU['n_adults']:,}", fs=10.5)
    arrow(ax, (5.25, 7.93), (5.25, 7.4))
    box(ax, 5.25, 6.85, 9.6, 0.95,
        f"腎臟指標（單次檢驗；eGFR<60 或 ACR≧30 mg/g）三值判定\n異常 {k['pos']:,}　｜　兩項皆測且正常 {k['neg']:,}　｜　未知 {k['unknown']:,}",
        fc="#fff8e6", fs=10)
    for x, key, tk in ((2.65, "肝炎", "hep_v3_2"), (7.85, "糖尿病", "dm_v3_2")):
        arrow(ax, (5.25, 6.35), (x, 5.6))
        t = total(tk)
        box(ax, x, 4.9, 4.9, 1.2, f"{NAME[key]}\n陽性 {t['pos']:,}　陰性 {t['neg']:,}　未知 {t['unknown']:,}\n→ 該軸分析 n = {t['pos'] + t['neg']:,}",
            fc="#ffffff", ec=AX[key], fs=9.8)
    ax.text(5.25, 3.95, "兩個標籤各自判定、可同時成立；各軸只排除該軸未知者", ha="center", fontsize=9, color=SUB, style="italic")
    ch = AU["kidney_2017_2018_reported_vs_DxC"]
    moved = sum(ch.values())
    f2001 = AU["feature_availability_in_kidney"]["LBXSAPSI"]["2001-2002"]
    hdl = min(AU["feature_availability_in_kidney"]["LBDHDL"].values())
    box(ax, 5.25, 1.75, 9.6, 2.35,
        "v3.2 資料修正（逐週期核對 CDC 文件後發現，皆能通過檔案雜湊檢查）\n"
        f"① 2001–2002 年鹼性磷酸酶、LDH、磷、總膽紅素以另一變數名發布，原被整週期當成缺值 → 對應後有值 {f2001:.0%}\n"
        "② 2017–2018 年生化儀器更換，依 CDC 回推式把 12 項檢驗（含肌酸酐）換回 1999–2016 年之量尺\n"
        f"　 → 該週期原判腎臟指標異常者中 {moved} 人改判（{ch.get('1→0', 0)} 人改為兩項皆正常、{ch.get('1→-1', 0)} 人改為未知）\n"
        f"③ HDL 膽固醇 2005 年起未讀入、1999–2004 年被封存規則誤排除 → 恢復（各週期有值 ≧{hdl:.0%}）",
        fc="#f7f7fb", ec="#b9b8b3", fs=9.2)
    save(fig, "圖1_分析樣本與資料修正.png")


ORDER = ["LR_routine", "LR_routine_noHDL", "HGB_routine", "LR_full", "HGB_full"]


def fig2():
    fig, axs = plt.subplots(2, 2, figsize=(14.2, 7.8))
    fig.subplots_adjust(wspace=0.62, hspace=0.6)
    for r, key in enumerate(KEYS):
        a = E[key]
        labs = ["只用年齡、性別"] + [MLAB[m] for m in ORDER]
        for col, (metric, xl) in enumerate((("auroc", "AUROC"), ("ap", "AP（平均精確率）"))):
            ax = axs[r, col]
            d = a["M1_demographics"]
            vals = [d[f"{metric}_mean"]] + [a["models"][m]["repeats"]["mean"][metric] for m in ORDER]
            lo = [d[f"{metric}_range"][0]] + [a["models"][m]["repeats"]["min"][metric] for m in ORDER]
            hi = [d[f"{metric}_range"][1]] + [a["models"][m]["repeats"]["max"][metric] for m in ORDER]
            y = np.arange(len(vals))[::-1]
            for yi, v, l_, h_, lab in zip(y, vals, lo, hi, labs):
                c = AX[key] if "邏輯" in lab and "常規" in lab and "不含" not in lab else DARK[key] if "梯度" in lab and "常規" in lab else GRAY
                ax.plot([l_, h_], [yi, yi], color=c, lw=2.2, solid_capstyle="round")
                ax.plot(v, yi, "o", color=c, ms=8, zorder=3, mec="white", mew=1.2)
                ax.annotate(f"{v:.3f}", xy=(max(h_, v), yi), xytext=(7, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
            base = 0.5 if metric == "auroc" else a["prevalence"]
            ax.axvline(base, color=MUTED, ls=":", lw=1.1)
            ax.text(base, 0.015, " 隨機" if metric == "auroc" else f" 盛行率 {base:.3f}", transform=ax.get_xaxis_transform(),
                    ha="left", va="bottom", fontsize=8.3, color=SUB)
            ax.set_yticks(y); ax.set_yticklabels(labs, fontsize=9.2)
            ax.set_xlabel(xl, fontsize=9.6)
            ax.set_xlim((0.45, 0.92) if metric == "auroc" else (0, max(hi) * 1.3))
            tidy(ax)
            ax.set_title(f"({'ab'[col]}{r + 1}) {NAME[key]}：{xl.split('（')[0]}", fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖2　判別力（v3.2 巢狀外層；點＝五次重複平均，線＝最小至最大；全部模型同一批切分）", fontsize=12.2, weight="bold", y=1.0)
    save(fig, "圖2_判別力.png")


def fig3():
    fig, axs = plt.subplots(2, 2, figsize=(12.6, 9.4), gridspec_kw={"width_ratios": [1, 1.25]})
    fig.subplots_adjust(wspace=0.32, hspace=0.52)
    for r, key in enumerate(KEYS):
        ax = axs[r, 0]
        lim = 0
        for m, c, ls in ((LR, AX[key], "-"), (HG, DARK[key], "--")):
            cv = E[key]["models"][m]["calibration_curve_repeat0"]
            mp, ob = [p["mean_pred"] for p in cv], [p["observed"] for p in cv]
            lim = max(lim, max(mp), max(ob))
            cal = E[key]["models"][m]["calibration_repeat0"]
            ax.plot(mp, ob, ls, marker="o", color=c, lw=2, ms=6.5, mec="white", mew=1.1,
                    label=f"{MLAB[m]}：截距 {cal['intercept']:+.2f}、斜率 {cal['slope']:.2f}")
        lim *= 1.12
        ax.plot([0, lim], [0, lim], color=MUTED, ls=":", lw=1)
        ax.set_xlim(0, lim); ax.set_ylim(0, lim)
        ax.set_xlabel("平均預測機率（分位數分箱）", fontsize=9.6); ax.set_ylabel("實際陽性比例", fontsize=9.6)
        ax.legend(fontsize=8.2, frameon=False, loc="upper left")
        tidy(ax, "both")
        ax.set_title(f"(a{r + 1}) {NAME[key]}：校準曲線", fontsize=10.4, loc="left", weight="bold")
        ax = axs[r, 1]
        bands = ["傾向", "不確定", "不傾向"]
        w = 0.36
        top = 0
        for j, (m, c) in enumerate(((LR, AX[key]), (HG, DARK[key]))):
            bs = E[key]["models"][m]["bands_tool_repeat0"]["band"]     # 工具規則：資料不足者不給方向
            xs = np.arange(3) + (j - 0.5) * w
            rates = [bs[b]["observed_rate"] or 0 for b in bands]
            top = max(top, max(rates))
            ax.bar(xs, rates, width=w - 0.03, color=c, label=MLAB[m], alpha=0.92)
            for x, b, rt in zip(xs, bands, rates):
                ax.text(x, rt, f"{rt:.1%}\nn={bs[b]['n']:,}", ha="center", va="bottom", fontsize=8.1, color=INK)
        ax.axhline(E[key]["prevalence"], color=MUTED, ls=":", lw=1.1)
        ax.text(2.55, E[key]["prevalence"], f"盛行率 {E[key]['prevalence']:.1%}", va="bottom", ha="right", fontsize=8.3, color=SUB)
        ax.set_xticks(range(3)); ax.set_xticklabels(bands, fontsize=9.6)
        ax.set_ylabel("該區實際陽性比例", fontsize=9.6)
        ax.set_ylim(0, top * 1.38 + 0.01)
        ax.legend(fontsize=8.4, frameon=False, loc="upper right")
        cov = [E[key]["models"][m]["bands_tool_repeat0"]["coverage"] for m in (LR, HG)]
        n_ins = E[key]["models"][LR]["bands_tool_repeat0"]["band"]["資料不足"]["n"]
        ax.text(0.0, -0.2, f"能給出方向（傾向或不傾向）的比例：邏輯迴歸 {cov[0]:.1%}、梯度提升 {cov[1]:.1%}"
                           f"（分母為全部；資料不足 {n_ins:,} 人不給方向）",
                transform=ax.transAxes, fontsize=8.8, color=SUB)
        tidy(ax, "y")
        ax.set_title(f"(b{r + 1}) {NAME[key]}：三段分區之實際陽性比例", fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖3　校準：線性與非線性模型（巢狀外層預測；校準器與門檻只用外層訓練資料）", fontsize=12.2, weight="bold", y=0.995)
    save(fig, "圖3_校準_線性與非線性.png")


def fig4():
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.9))
    fig.subplots_adjust(wspace=0.55)
    for ax, key in zip(axs, KEYS):
        a = E[key]
        rows = []
        for m, c in ((LR, AX[key]), (HG, DARK[key])):
            s = a["models"][m]
            rows += [(f"{MLAB[m]}｜巢狀外層", s["repeats"]["mean"]["auroc"], s["ci95_repeat0"]["auroc"], c),
                     (f"{MLAB[m]}｜時間外推", a["temporal"][m]["auroc"], a["temporal"][m]["ci95"]["auroc"], c),
                     (f"{MLAB[m]}｜人口加權", a["design_weighted"][m]["weighted"]["auroc"]["est"],
                      a["design_weighted"][m]["weighted"]["auroc"]["ci95"], c),
                     (f"{MLAB[m]}｜腎臟標籤用原發布肌酸酐", a["kidney_label_as_reported"][m]["auroc"], None, c)]
        y = np.arange(len(rows))[::-1]
        for yi, (lab, v, ci, c) in zip(y, rows):
            if ci:
                ax.plot(ci, [yi, yi], color=c, lw=2.2, solid_capstyle="round", alpha=0.75)
            ax.plot(v, yi, "o", color=c, ms=7.5, mec="white", mew=1.1, zorder=3)
            ax.annotate(f"{v:.3f}", xy=(ci[1] if ci else v, yi), xytext=(7, 0), textcoords="offset points", va="center", fontsize=8.8)
        ax.set_yticks(y); ax.set_yticklabels([r_[0] for r_ in rows], fontsize=8.6)
        ax.axvline(0.5, color=MUTED, ls=":", lw=1)
        ax.set_xlim(0.5, 0.92); ax.set_xlabel("AUROC（95% CI）", fontsize=9.6)
        tidy(ax)
        ax.set_title(NAME[key], fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖4　穩健性：時間外推（1999–2008 訓練→2009–2018 評估）、人口加權（設計 CI）、腎臟標籤定義", fontsize=12, weight="bold", y=1.03)
    save(fig, "圖4_穩健性.png")


def fig5():
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8))
    fig.subplots_adjust(wspace=0.28)
    for ax, key in zip(axs, KEYS):
        top = 0
        for m, c, ls in ((LR, AX[key], "-"), (HG, DARK[key], "--")):
            d = E[key]["decision_curve"][m]
            pt = [r["pt"] for r in d]
            ax.plot(pt, [r["nb_model"] for r in d], ls, color=c, lw=2.2, label=f"依{MLAB[m]}送驗")
            top = max(top, max(r["nb_model"] for r in d), max(r["nb_test_all"] for r in d))
        ax.plot(pt, [r["nb_test_all"] for r in d], color=GRAY, lw=1.8, ls=":", label="全數送驗")
        ax.axhline(0, color=INK, lw=1, label="全不送驗")
        ax.set_ylim(-top * 0.35, top * 1.2); ax.set_xlim(min(pt), max(pt))
        ax.set_xlabel("閾值機率 pt", fontsize=9.4); ax.set_ylabel("淨效益", fontsize=9.6)
        ax.xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0 if key == "糖尿病" else 1))
        tidy(ax, "both")
        ax.legend(fontsize=8.4, frameon=False, loc="upper right")
        b = E[key]["models"][LR]["bands_tool_repeat0"]["per_1000_if_skip_low"]     # 資料不足者照常送驗
        ax.set_title(NAME[key], fontsize=10.4, loc="left", weight="bold")
        hx, ha = (0.98, "right") if key == "肝炎" else (0.02, "left")      # 避開「全數送驗」線
        ax.text(hx, 0.04, f"若只略過「不傾向」區（邏輯迴歸）：\n每千人送驗 {b['tested']:.0f}、漏 {b['missed']:.1f} 名陽性\n（占陽性 {b['missed_share_of_pos']:.0%}）",
                transform=ax.transAxes, fontsize=8.5, color=SUB, ha=ha, va="bottom")
    fig.suptitle("圖5　決策曲線（巢狀外層預測）：閾值須由實際檢驗之利弊決定", fontsize=12, weight="bold", y=1.03)
    save(fig, "圖5_決策曲線.png")


def fig7():
    fig, axs = plt.subplots(1, 2, figsize=(14, 5.4))
    fig.subplots_adjust(wspace=0.62)
    for ax, key in zip(axs, KEYS):
        m3 = X3[key]["models"]
        xv = X["axes"][key]["models"]
        rows = [("v3 全特徵 LR（事前指定，原資料）", m3["v3_full_LR（部署）"], GRAY),
                ("v3 常規套組 LR（事前指定，原資料）", m3["v3_basic_LR（常規套組候選）"], GRAY),
                ("v3 常規套組 LR（凍結，量尺對齊後）", xv["v3_basic_LR（凍結）"], MUTED),
                ("只用年齡、性別（事後補做）", X["axes"][key]["M1_demographics"], MUTED),
                (f"v3.2 {MLAB[LR]}（事後）", xv[LR], AX[key]),
                (f"v3.2 {MLAB[HG]}（事後）", xv[HG], DARK[key])]
        y = np.arange(len(rows))[::-1]
        for yi, (lab, m, c) in zip(y, rows):
            ci = m["ci95"]["auroc"]
            ax.plot(ci, [yi, yi], color=c, lw=2.2, solid_capstyle="round")
            ax.plot(m["auroc"], yi, "o", color=c, ms=8, mec="white", mew=1.2, zorder=3)
            ax.annotate(f"{m['auroc']:.3f}", xy=(ci[1], yi), xytext=(7, 0), textcoords="offset points", va="center", fontsize=9)
        ax.set_yticks(y); ax.set_yticklabels([r_[0] for r_ in rows], fontsize=8.8)
        ax.axvline(0.5, color=MUTED, ls=":", lw=1)
        ax.set_xlim(0.4, 0.95); ax.set_xlabel("AUROC（受試者層 bootstrap 95% CI）", fontsize=9.6)
        tidy(ax)
        ax.set_title(f"{NAME[key]}：陽性 {X['axes'][key]['n_pos']}／n {X['axes'][key]['n']:,}（v3.2 標籤）", fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖7　NHANES 2021–2023：v3 事前指定之一次評估（灰）與 v3.2 事後評估（彩色）", fontsize=12, weight="bold", y=1.02)
    save(fig, "圖7_外部資料.png")


def fig8():
    cv = X["recalibration_cv"]
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    fig.subplots_adjust(wspace=0.3)
    for ax, key in zip(axs, KEYS):
        items = []
        for ver in ("v3.1", "v3.2"):
            s = cv[ver][key]["random_summary"]
            items += [(f"{ver} 不重新校準", s["oe_none"], GRAY), (f"{ver} 重新校準", s["oe_recal"], AX[key])]
        y = np.arange(len(items))[::-1]
        for yi, (lab, q, c) in zip(y, items):
            ax.plot([q["p2_5"], q["p97_5"]], [yi, yi], color=c, lw=2.4, solid_capstyle="round")
            ax.plot(q["median"], yi, "o", color=c, ms=8, mec="white", mew=1.2, zorder=3)
            ax.annotate(f"{q['median']:.2f}（{q['p2_5']:.2f}–{q['p97_5']:.2f}）", xy=(q["p97_5"], yi), xytext=(7, 0),
                        textcoords="offset points", va="center", fontsize=8.8)
        ax.axvline(1, color=INK, lw=1, ls=":")
        ax.set_yticks(y); ax.set_yticklabels([i[0] for i in items], fontsize=9.2)
        ax.set_xscale("log")
        ticks = [0.25, 0.5, 1, 2, 4, 8] if key == "肝炎" else [0.8, 0.9, 1.0, 1.1, 1.25]
        ax.set_xlim((0.2, 12) if key == "肝炎" else (0.75, 1.5))
        ax.set_xticks(ticks); ax.set_xticklabels([f"{t:g}" for t in ticks]); ax.minorticks_off()
        ax.set_xlabel("測試半：平均預測／實際陽性比例（1＝校準；對數刻度）", fontsize=9.4)
        tidy(ax)
        n_pos = cv["v3.2"][key]["random_summary"]["n_pos_test"]["median"]
        ax.set_title(f"{NAME[key]}（測試半陽性中位數 {n_pos:.0f} 人）", fontsize=10.4, loc="left", weight="bold")
    fig.suptitle("圖8　重新校準之交叉驗證：依抽樣設計把 2021–2023 切半 200 次（點＝中位數，線＝2.5–97.5 百分位）",
                 fontsize=11.8, weight="bold", y=1.03)
    save(fig, "圖8_重新校準交叉驗證.png")


def figS1():
    """研究論文 v3.2 圖 S1：網頁工具 v3.2 對示範受試者之輸出（事前＝2021–2023 年比例）。"""
    from make_figures_v3 import figS1 as plot
    plot(model="direction_model_v3_2.json", patient="direction_demo_patient.json", expected="direction_demo_expected.json",
         prior_note="與事前機率相同（2021–2023 年比例）", save_fn=save)


def fig6():
    """圖6：v3.2 資料修正後之鉛、鎘血尿比較（results/exwas_v3_2_checks.json）。"""
    from make_figures_v3 import fig6 as plot
    plot(checks="exwas_v3_2_checks.json", save_fn=save)


def main(dest=None):
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6(); fig7(); fig8(); figS1()
    if dest:
        os.makedirs(dest, exist_ok=True)
        for f in sorted(os.listdir(FIG)):
            shutil.copy2(os.path.join(FIG, f), os.path.join(dest, f))
        print(f"[複製] → {dest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
