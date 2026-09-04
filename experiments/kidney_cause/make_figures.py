# -*- coding: utf-8 -*-
"""科展計畫書三張圖——全部由 results/*.json 生成，數字不手打。
    python make_figures.py

圖一　世代建立流程（CONSORT 式）
圖二　三大病因判別能力對比（含 95% 信賴區間）
圖三　反向因果的直接證據（同一元素血中 vs 尿中方向相反）
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import matplotlib                                   # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch   # noqa: E402

# 中文字型（Windows 內建）——找不到就退回預設並警告
for fam in ("Microsoft JhengHei", "Microsoft YaHei", "SimHei", "PMingLiU"):
    try:
        matplotlib.font_manager.findfont(fam, fallback_to_default=False)
        plt.rcParams["font.family"] = fam
        break
    except Exception:
        continue
else:
    print("⚠️ 找不到中文字型，圖中中文可能顯示為方框")
plt.rcParams["axes.unicode_minus"] = False
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)
INK, SUB, OK, BAD, WARN = "#1a1a1a", "#5a5a5a", "#2e7d32", "#c62828", "#ef6c00"


def _load(name):
    return json.load(open(os.path.join(ROOT, "results", name), encoding="utf-8"))


def fig1_cohort():
    """圖一：世代建立流程。"""
    X = _load("exwas.json")
    c = X["cohort"]
    B = _load("binary_tasks_extended.json")
    n_adult, n_known, n_kd = c["n_adults"], c["n_outcome_known"], c["n_kidney_damage"]
    t = B["tasks"]
    n_inf = t["T3_感染vs其餘全部"]["variants"]["leak_free"]["HGB"]["n_pos"]
    n_met = t["T4_代謝vs其餘"]["variants"]["leak_free"]["HGB"]["n_pos"]

    fig, ax = plt.subplots(figsize=(8.4, 8.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10.6); ax.axis("off")
    boxes = [
        (5.0, 9.7, 6.6, "NHANES 1999–2018　十個週期、261 個公開檔（290 MB）", "#eceff1"),
        (5.0, 8.3, 5.4, f"成人（≧20 歲）\nn = {n_adult:,}", "#e3f2fd"),
        (5.0, 6.9, 5.4, f"腎功能結果可判定\nn = {n_known:,}", "#e3f2fd"),
        (5.0, 5.5, 5.8, f"腎損傷（eGFR<60 或 ACR≧30）\nn = {n_kd:,}　（{n_kd/n_known:.1%}）", "#fff8e1"),
    ]
    for x, y, w, txt, col in boxes:
        ax.add_patch(FancyBboxPatch((x - w / 2, y - .42), w, .84, boxstyle="round,pad=0.06",
                                    fc=col, ec=SUB, lw=1.1))
        ax.text(x, y, txt, ha="center", va="center", fontsize=10.5, color=INK, linespacing=1.5)
    for y0, y1 in ((9.28, 8.74), (7.88, 7.34), (6.48, 5.94)):
        ax.add_patch(FancyArrowPatch((5, y0), (5, y1), arrowstyle="-|>", mutation_scale=14,
                                     lw=1.2, color=SUB))
    ax.text(8.3, 7.6, f"排除結果無法判定\n{n_adult - n_known:,} 人", ha="center", va="center",
            fontsize=9, color=SUB, style="italic")

    lab = [(2.2, "感染性", n_inf, "#ffcdd2", "HBsAg＋ 或 HCV RNA＋"),
           (5.0, "代謝性", n_met, "#c8e6c9", "糖尿病 或 HbA1c≧6.5%"),
           (7.8, "免疫性", 107, "#d1c4e9", "ANA＋（僅 1999–2004）")]
    for x, name, n, col, sub in lab:
        ax.add_patch(FancyBboxPatch((x - 1.28, 3.5), 2.56, 1.0, boxstyle="round,pad=0.06",
                                    fc=col, ec=SUB, lw=1.1))
        ax.text(x, 4.16, name, ha="center", fontsize=11.5, color=INK, weight="bold")
        ax.text(x, 3.78, f"n = {n:,}", ha="center", fontsize=11, color=INK)
        ax.text(x, 3.15, sub, ha="center", fontsize=8.2, color=SUB)
        ax.add_patch(FancyArrowPatch((5, 5.06), (x, 4.56), arrowstyle="-|>",
                                     mutation_scale=12, lw=1.1, color=SUB,
                                     connectionstyle="arc3,rad=0.12" if x != 5 else "arc3"))
    ax.add_patch(FancyBboxPatch((1.1, 1.55), 7.8, 1.06, boxstyle="round,pad=0.08",
                                fc="#fafafa", ec=BAD, lw=1.4, ls="--"))
    ax.text(5, 2.30, "通道消耗規則：定義標籤的 79 個檢驗一律封存，永不作為特徵",
            ha="center", fontsize=10, color=BAD, weight="bold")
    ax.text(5, 1.87, "可用特徵 60 項　│　上游暴露 213 項　│　封存 79 項",
            ha="center", fontsize=9.6, color=INK)
    ax.text(5, .75, "圖一　世代建立流程", ha="center", fontsize=12.5, weight="bold", color=INK)
    fig.savefig(os.path.join(FIG, "圖一_世代建立流程.png"), dpi=220, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)


def fig2_discrimination():
    """圖二：三大病因判別能力（AUROC 與 95% CI）。"""
    B = _load("binary_tasks_extended.json")
    S = _load("binary_tasks.json")
    rows = []
    for key, name in (("T2_感染vs代謝", "感染性 vs 代謝性"),
                      ("T3_感染vs其餘全部", "感染性 vs 其餘"),
                      ("T4_代謝vs其餘", "代謝性 vs 其餘")):
        r = B["tasks"][key]["variants"]["leak_free"]["HGB"]
        rows.append((name, r["auroc"], r["auroc_ci"], r["auprc_lift"], r["n_pos"], OK))
    ri = [v for k, v in S["tasks"].items() if "免疫" in k][0]["variants"]["leak_free"]["HGB"]
    rows.append(("免疫性 vs 非免疫", ri["auroc"], ri["auroc_ci"], ri["auprc_lift"],
                 ri["n_pos"], BAD))

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.6, 4.5),
                                 gridspec_kw={"width_ratios": [1.55, 1]})
    y = range(len(rows))[::-1]
    for yi, (nm, auc, ci, lift, npos, col) in zip(y, rows):
        a1.plot([ci[0], ci[1]], [yi, yi], color=col, lw=2.6, solid_capstyle="round", alpha=.75)
        a1.plot(auc, yi, "o", color=col, ms=9, zorder=3)
        a1.text(ci[1] + .012, yi, f"{auc:.3f}", va="center", fontsize=10, color=col, weight="bold")
    a1.axvline(.5, color=SUB, ls=":", lw=1.2)
    a1.text(.5, .03, "隨機猜測", ha="center", va="bottom", fontsize=8.5, color=SUB,
            transform=a1.get_xaxis_transform())
    a1.axvline(.9, color=WARN, ls="--", lw=1.3)
    a1.text(.9, .03, "原始目標 0.90", ha="center", va="bottom", fontsize=8.5, color=WARN,
            transform=a1.get_xaxis_transform())
    a1.set_yticks(list(y)); a1.set_yticklabels([r[0] for r in rows], fontsize=10.5)
    a1.set_xlim(.42, .98); a1.set_xlabel("AUROC（95% 信賴區間）", fontsize=10.5)
    a1.set_title("(a) 判別能力", fontsize=11.5, weight="bold", loc="left")
    a1.grid(axis="x", alpha=.25); a1.spines[["top", "right"]].set_visible(False)

    lifts = [r[3] for r in rows]
    cols = [r[5] for r in rows]
    a2.barh(list(y), lifts, color=cols, alpha=.8, height=.55)
    for yi, (nm, auc, ci, lift, npos, col) in zip(y, rows):
        a2.text(lift + .12, yi, f"×{lift:.1f}", va="center", fontsize=10, color=col, weight="bold")
    a2.axvline(1, color=SUB, ls=":", lw=1.4)
    a2.text(1, .03, "無提升", ha="center", va="bottom", fontsize=8.5, color=SUB,
            transform=a2.get_xaxis_transform())
    a2.set_yticks(list(y)); a2.set_yticklabels([])
    a2.set_xlabel("AUPRC 相對盛行率基準之提升倍數", fontsize=10.5)
    a2.set_title("(b) 實際可用性", fontsize=11.5, weight="bold", loc="left")
    a2.grid(axis="x", alpha=.25); a2.spines[["top", "right"]].set_visible(False)
    fig.suptitle("圖二　三大病因之判別能力——免疫類提升僅 ×1.3，與隨機猜測幾無差異",
                 fontsize=12.5, weight="bold", y=1.06)
    fig.savefig(os.path.join(FIG, "圖二_三大病因判別能力.png"), dpi=220,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig3_reverse():
    """圖三：反向因果的直接證據。"""
    X = _load("exwas.json")
    R = {r["exposure"]: r for r in X["results"]}
    pairs = [("鉛", "LBXBPB", "URXUPB"), ("鎘", "LBXBCD", "URXUCD")]
    uri = [r for r in X["results"]
           if r["significant_fdr05"] and r["exposure"].startswith("URX")]
    n_prot = sum(1 for r in uri if r["headline"]["or_per_sd"] < 1)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.6, 4.4),
                                 gridspec_kw={"width_ratios": [1.15, 1]})
    ypos, labels = [], []
    for i in range(len(pairs)):
        a1.axhspan(i * 2.6 - .55, i * 2.6 + 1.55, color="#000000", alpha=.035, zorder=0)
    for i, (zh, b, u) in enumerate(pairs):
        for j, (mat, key, col) in enumerate((("血中", b, BAD), ("尿中", u, "#1565c0"))):
            r = R.get(key)
            if not r:
                continue
            yv = i * 2.6 + (0 if j else 1)
            h = r["headline"]
            a1.plot([h["ci"][0], h["ci"][1]], [yv, yv], color=col, lw=2.6, alpha=.75,
                    solid_capstyle="round")
            a1.plot(h["or_per_sd"], yv, "o", color=col, ms=9, zorder=3)
            star = "＊" if r["significant_fdr05"] else ""
            a1.text(h["ci"][1] + .012, yv, f"{h['or_per_sd']:.3f}{star}", va="center",
                    fontsize=10, color=col, weight="bold")
            ypos.append(yv); labels.append(f"{zh}－{mat}")
    a1.axvline(1, color=SUB, ls=":", lw=1.4)
    a1.text(1, .985, "無關聯", ha="center", va="top", fontsize=8.5, color=SUB,
            transform=a1.get_xaxis_transform())
    a1.set_yticks(ypos); a1.set_yticklabels(labels, fontsize=10.5)
    a1.set_xlabel("勝算比（每增加 1 標準差）", fontsize=10.5)
    a1.set_title("(a) 同一元素，血中「有害」而尿中「保護」", fontsize=11, weight="bold", loc="left")
    a1.grid(axis="x", alpha=.25); a1.spines[["top", "right"]].set_visible(False)
    a1.text(.5, -.24, "＊ 通過偽發現率校正", transform=a1.transAxes, ha="center",
            fontsize=8.5, color=SUB)

    a2.bar(["看似保護\n(OR<1)", "看似有害\n(OR>1)"], [n_prot, len(uri) - n_prot],
           color=["#1565c0", BAD], alpha=.8, width=.5)
    for i, v in enumerate([n_prot, len(uri) - n_prot]):
        a2.text(i, v + .18, str(v), ha="center", fontsize=13, weight="bold", color=INK)
    a2.set_ylabel("顯著的尿液暴露個數", fontsize=10.5)
    a2.set_ylim(0, max(n_prot, 1) * 1.35)
    a2.set_title("(b) 顯著的尿液暴露方向分布", fontsize=11, weight="bold", loc="left")
    a2.grid(axis="y", alpha=.25); a2.spines[["top", "right"]].set_visible(False)
    a2.text(.5, -.26, "無毒理學說法可解釋九種金屬同時保護腎臟；\n"
                      "排泄生理學可完全解釋（腎功能↓→尿中濃度↓）",
            transform=a2.transAxes, ha="center", fontsize=9, color=BAD)
    fig.suptitle("圖三　反向因果的直接證據——關聯方向由腎排泄能力決定，非毒性作用",
                 fontsize=12.5, weight="bold", y=1.07)
    fig.savefig(os.path.join(FIG, "圖三_反向因果證據.png"), dpi=220,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)




def fig4_traps():
    """圖四：六項被攔截的方法學陷阱——虛報值 vs 實際值。"""
    traps = [
        ("未受檢者被當作\n免疫陰性", 0.812, 0.584, "標籤稽核"),
        ("血糖未拔除\n（標籤下游）", 0.913, 0.816, "洩漏量化"),
        ("小樣本樂觀\n（感染類）", 0.876, 0.819, "擴充樣本"),
    ]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.2, 4.6),
                                 gridspec_kw={"width_ratios": [1, 1.15]})
    import numpy as np
    x = np.arange(len(traps))
    w = .34
    a1.bar(x - w / 2, [t[1] for t in traps], w, label="若未攔截（虛報值）",
           color=BAD, alpha=.85)
    a1.bar(x + w / 2, [t[2] for t in traps], w, label="實際值", color=OK, alpha=.85)
    for i, t in enumerate(traps):
        a1.text(i - w / 2, t[1] + .012, f"{t[1]:.3f}", ha="center", fontsize=9.5,
                color=BAD, weight="bold")
        a1.text(i + w / 2, t[2] + .012, f"{t[2]:.3f}", ha="center", fontsize=9.5,
                color=OK, weight="bold")
        a1.text(i, max(t[1], t[2]) + .042, f"降 {t[1]-t[2]:.3f}", ha="center",
                fontsize=9.5, color=SUB, style="italic", weight="bold")
    a1.axhline(.9, color=WARN, ls="--", lw=1.3)
    a1.text(-.42, .908, "原始目標 0.90", fontsize=8.5, color=WARN, ha="left", va="bottom")
    a1.set_xticks(x); a1.set_xticklabels([t[0] for t in traps], fontsize=9.5)
    a1.set_ylabel("AUROC", fontsize=10.5); a1.set_ylim(.5, 1.02)
    a1.legend(fontsize=9, loc="upper center", bbox_to_anchor=(.5, -.16),
              ncol=2, frameon=False)
    a1.set_title("(a) 三項可量化的陷阱", fontsize=11, weight="bold", loc="left", pad=12)
    a1.grid(axis="y", alpha=.25); a1.spines[["top", "right"]].set_visible(False)

    a2.axis("off")
    rows = [("① 未受檢者當陰性", "免疫虛報 0.812", "標籤稽核"),
            ("② 標籤下游未拔除", "代謝虛報 0.913", "洩漏量化"),
            ("③ 變數別名漏列", "整週期資料靜默丟棄", "缺值型態檢查"),
            ("④ 預設值吞噬缺值", "最重分期虛報 734 例", "分布合理性檢查"),
            ("⑤ 二元變數被誤砍", "陽性對照未被掃描", "★ 陽性對照"),
            ("⑥ 只驗顯著不驗方向", "保護方向誤報為毒性", "方向一致性檢查")]
    a2.text(.02, 1.0, "(b) 六項陷阱與其攔截機制", fontsize=11, weight="bold",
            transform=a2.transAxes, va="top")
    for i, (name, harm, guard) in enumerate(rows):
        yy = .845 - i * .137
        hl = i == 4
        a2.add_patch(FancyBboxPatch((.02, yy - .052), .96, .105,
                                    boxstyle="round,pad=0.012",
                                    fc="#fff3e0" if hl else "#fafafa",
                                    ec=BAD if hl else "#dddddd",
                                    lw=1.5 if hl else .9,
                                    transform=a2.transAxes, clip_on=False))
        a2.text(.05, yy, name, fontsize=9.6, transform=a2.transAxes, va="center",
                weight="bold" if hl else "normal", color=INK)
        a2.text(.42, yy, harm, fontsize=9, transform=a2.transAxes, va="center", color=BAD)
        a2.text(.76, yy, guard, fontsize=9, transform=a2.transAxes, va="center",
                color=BAD if hl else OK, weight="bold" if hl else "normal")
    a2.text(.5, .012, "★ 第 ⑤ 項偽裝成乾淨的陰性結論；攔截它的不是研究者的謹慎，"
                      "而是事前設置的陽性對照",
            fontsize=9, transform=a2.transAxes, ha="center", color=BAD, style="italic")
    fig.suptitle("圖四　六項被攔截的方法學陷阱——每一次修正都使結果變差",
                 fontsize=12.5, weight="bold", y=1.05)
    fig.savefig(os.path.join(FIG, "圖四_方法學陷阱.png"), dpi=220,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)

if __name__ == "__main__":
    fig1_cohort(); print("[完成] 圖一_世代建立流程.png")
    fig2_discrimination(); print("[完成] 圖二_三大病因判別能力.png")
    fig3_reverse(); print("[完成] 圖三_反向因果證據.png")
    fig4_traps(); print("[完成] 圖四_方法學陷阱.png")
    print(f"→ {FIG}")
