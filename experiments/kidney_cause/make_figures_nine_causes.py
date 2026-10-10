# -*- coding: utf-8 -*-
"""九種病因文獻回顧之圖一——全部由 results/nine_causes_nhanes.json 生成，數字不手打。  python make_figures_nine_causes.py
圖一 腎損傷成人之調整盛行率比：左＝腎損傷對無腎損傷；右＝依腎臟型態對兩項皆正常者。橫線為 95% CI，對數刻度。
樣式沿用 make_figures_v3（細線、灰階文字）；未計算之疾病（status）不畫。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import matplotlib                                                    # noqa: E402
import matplotlib.pyplot as plt                                      # noqa: E402

from make_figures_v3 import GRAY, INK, MUTED, SUB, tidy              # noqa: E402  (同時套用字型設定)

if not set(plt.rcParams["font.family"]) & {"Microsoft JhengHei", "Microsoft YaHei", "PMingLiU"}:   # 非 Windows：改用文泉驛正黑
    try:
        matplotlib.font_manager.findfont("WenQuanYi Zen Hei", fallback_to_default=False)
        plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    except Exception:
        pass

FIG = os.path.join(ROOT, "figures", "nine_causes")
os.makedirs(FIG, exist_ok=True)
R = json.load(open(os.path.join(ROOT, "results", "nine_causes_nhanes.json"), encoding="utf-8"))
P, PH = R["primary"], R["phenotype"]
DONE = [d for d in P if "status" not in P[d]]
DIR = {"糖尿病": "代謝", "肥胖": "代謝", "高尿酸血症": "代謝", "痛風": "代謝", "B型肝炎": "感染", "C型肝炎": "感染", "HIV": "感染"}
COLOR = {"代謝": "#eb6834", "感染": "#2a78d6"}                       # 與 make_figures_v3 之兩軸類別色相同
DISP = {"B型肝炎": "B 型肝炎", "C型肝炎": "C 型肝炎"}
TYPES = [("只有白蛋白尿", "o"), ("只有eGFR<60", "s"), ("兩者皆有", "D")]


def fig1():
    rows = DONE[::-1]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 0.55 * len(rows) + 1.6), sharey=True, gridspec_kw={"wspace": 0.08})
    allv = [c for d in DONE for c in P[d]["contrasts"]["腎損傷"]["aPR"]["ci95"]] + \
           [c for d in DONE for k, _ in TYPES for c in PH[d]["contrasts"][k]["aPR"]["ci95"]]
    lo, hi = min(allv) / 1.15, max(allv) * 1.15
    for i, d in enumerate(rows):
        c, col = P[d]["contrasts"]["腎損傷"]["aPR"], COLOR[DIR[d]]
        a1.plot(c["ci95"], [i, i], color=col, lw=1.6)
        a1.plot(c["est"], i, "o", color=col, ms=6.5)
        for j, (k, m) in enumerate(TYPES):
            ck, y = PH[d]["contrasts"][k]["aPR"], i - (j - 1) * 0.24
            a2.plot(ck["ci95"], [y, y], color=col, lw=1.1, alpha=0.85)
            a2.plot(ck["est"], y, m, color=col, ms=5, mfc="white" if j == 0 else col, mec=col)
    for ax, t in ((a1, "腎損傷（eGFR<60 或 ACR≧30）對無腎損傷"), (a2, "依腎臟型態對兩項皆正常者")):
        ax.set_xscale("log")
        ax.set_xlim(lo, hi)
        ax.axvline(1, color=GRAY, lw=1, ls="--")
        ax.set_xticks([0.5, 1, 2, 4, 8]); ax.set_xticks([], minor=True)
        ax.set_xticklabels(["0.5", "1", "2", "4", "8"])
        ax.set_xlim(lo, hi)
        ax.set_xlabel("調整盛行率比（對數刻度）", fontsize=9.5)
        ax.set_title(t, fontsize=10.5, color=INK, loc="left")
        tidy(ax)
    a1.set_yticks(range(len(rows)))
    est = lambda c: f"{c['est']:.2f}（{c['ci95'][0]:.2f}–{c['ci95'][1]:.2f}）"
    a1.set_yticklabels([f"{DISP.get(d, d)}（{DIR[d]}）\n{est(P[d]['contrasts']['腎損傷']['aPR'])}" for d in rows], fontsize=9.6)
    a2.legend(handles=[plt.Line2D([], [], marker=m, ls="", color=MUTED, mfc="white" if j == 0 else MUTED, label=k.replace("eGFR", " eGFR "))
                       for j, (k, m) in enumerate(TYPES)], fontsize=8.6, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3)
    fig.text(0.01, -0.1, "調整年齡、性別、種族；刪一 PSU 摺刀法 95% CI。橫斷面共存，不代表因果方向。", fontsize=8.6, color=MUTED)
    fig.savefig(os.path.join(FIG, "圖一_九種病因調整盛行率比.png"), dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("[完成] 圖一_九種病因調整盛行率比.png")


if __name__ == "__main__":
    fig1()
