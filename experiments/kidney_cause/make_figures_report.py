# -*- coding: utf-8 -*-
"""研究報告（整合版）圖 1–10，統一樣式（figures/fair2/draw_fair2.py：微軟正黑、300 dpi、字級 ≥7.5 pt、
無版本字樣、文字不重疊檢查）。數字全由結果檔產生：
  圖 1–8  ＝draw_fair2 讀 figures/fair2/fig_data.json（export_fig_data_fair2.py 由結果檔匯出），只改檔名為報告編號
  圖 9   ＝results/nine_causes_nhanes.json（九種病因調整盛行率比，重畫成同一樣式）
  圖 10  ＝results/immune_geo_batchsafe.json＋immune_geo_amendment2.json（NIH GEO 切片轉錄體，同批次三方向）
    python -X utf8 make_figures_report.py   → figures/report/"""
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
from matplotlib import ticker

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures" / "report"
OUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("draw_fair2", ROOT / "figures" / "fair2" / "draw_fair2.py")
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)
D.ROOT = OUT          # ponytail: draw_fair2.save 以模組層 ROOT 決定輸出位置
plt = D.plt
J = lambda name: json.load(open(ROOT / "results" / name, encoding="utf-8"))
RENAME = {"圖二_分析樣本與資料修正.png": "圖1_分析樣本與資料修正.png", "圖三_判別力.png": "圖2_判別力.png",
          "圖四_校準與分區.png": "圖3_校準與分區.png", "圖五_穩健性.png": "圖4_穩健性.png",
          "圖七_決策曲線.png": "圖5_決策曲線.png", "圖八_暴露血尿比較.png": "圖6_暴露血尿比較.png",
          "圖六_外部資料.png": "圖7_外部資料.png", "圖九_重新校準交叉驗證.png": "圖8_重新校準交叉驗證.png"}
DIRC = {"代謝": D.COLORS["糖尿病"]["axis"], "感染": D.COLORS["肝炎"]["axis"], "免疫": "#b23a76"}
D.DATA["display_cm"].update({"圖9": {"width": 17.0, "current_height": 9.4}, "圖10": {"width": 17.0, "current_height": 13.6}})
_save = D.save


def save(fig, filename):
    _save(fig, RENAME.get(filename, filename))


D.save = save


# ---------- 圖 9 九種病因調整盛行率比 ----------
def fig9():
    R = J("nine_causes_nhanes.json")
    P, PH = R["primary"], R["phenotype"]
    DIR = {"糖尿病": "代謝", "肥胖": "代謝", "高尿酸血症": "代謝", "痛風": "代謝", "B型肝炎": "感染", "C型肝炎": "感染", "HIV": "感染"}
    rows = [d for d in P if "status" not in P[d]]
    assert set(rows) == set(DIR), rows
    TYPES = [("只有白蛋白尿", "o", True), ("只有eGFR<60", "s", False), ("兩者皆有", "D", False)]
    fig = D.figure("圖9")
    a1 = fig.add_axes([.345, .2, .25, .64])
    a2 = fig.add_axes([.65, .2, .33, .64])
    for ax, t in ((a1, "腎損傷對無腎損傷"), (a2, "依腎臟型態對兩項皆正常者")):
        ax.set_xscale("log")
        ax.set(xlim=(.6, 4) if ax is a1 else (.1, 12), ylim=(len(rows) - .45, -.55), yticks=[])  # 右圖下限 0.1：HIV 只有 eGFR<60 之 CI 下限 0.13
        ax.xaxis.set_major_locator(ticker.FixedLocator([.25, .5, 1, 2, 4, 8] if ax is a2 else [1, 2, 4]))
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%g"))
        ax.xaxis.set_minor_locator(ticker.NullLocator())
        D.style(ax)
        ax.axvline(1, color=D.COLORS["sub"], ls="--", lw=.8)
        D.title(fig, ax.get_position().x0, .985, t)
    for y, d in enumerate(rows):
        c, col = P[d]["contrasts"]["腎損傷"]["aPR"], DIRC[DIR[d]]
        D.interval(a1, y, c["est"], c["ci95"], col)
        D.row_text(a1, y, f"{d.replace('型', ' 型')}（{DIR[d]}）", -1.31, ha="left")
        D.row_text(a1, y, f"{c['est']:.2f}（{c['ci95'][0]:.2f}–{c['ci95'][1]:.2f}）", -.64, ha="left")
        for j, (k, m, hollow) in enumerate(TYPES):
            ck = PH[d]["contrasts"][k]["aPR"]
            D.interval(a2, y + (j - 1) * .26, ck["est"], ck["ci95"], col, m, hollow=hollow)
    D.text(fig, .015, .875, "疾病（方向）", weight="bold")
    D.text(fig, .185, .875, "調整盛行率比（95% CI）", weight="bold")
    for i, (k, m, hollow) in enumerate(TYPES):
        x = (.62, .76, .905)[i]
        fig.lines.append(plt.Line2D([x], [.06], marker=m, ls="", color=D.COLORS["sub"], ms=4.2,
                                    mfc="white" if hollow else D.COLORS["sub"], transform=fig.transFigure))
        D.text(fig, x + .012, .06, k.replace("eGFR", " eGFR "), va="center")
    D.text(fig, .47, .06, "調整盛行率比（對數刻度）", va="center", ha="center")
    save(fig, "圖9_九種病因調整盛行率比.png")


# ---------- 圖 10 NIH GEO 切片轉錄體：免疫／代謝／兩者皆非 ----------
def fig10():
    B, C = J("immune_geo_batchsafe.json"), J("immune_geo_amendment2.json")
    rep = {**B["B4_replication"], **C["C4_replication"]}
    dec = {**B["decision"], **C["decision"]}
    ROWS = [("免疫 對 非免疫", "ANCA 對 DN、FSGS、MCD", B["B1_primary"], rep["B1"], dec["B1_primary"]),
            ("", "SLE 對 FSGS", B["B3_SLE"], rep["B3"], dec["B3_SLE"]),
            ("免疫 對 代謝", "ANCA 對 DN", B["B2_immune_vs_metabolic"], rep["B2"], dec["B2_immune_vs_metabolic"]),
            ("代謝 對 兩者皆非", "DN 對 FSGS、MCD", C["C1_metabolic_H7"], rep["C1"], dec["C1_metabolic_H7"]),
            ("", "DN 對 MCD、TMD", C["C2_metabolic_H1"], rep["C2"], dec["C2_metabolic_H1"]),
            ("免疫 對 免疫", "SLE 對 MN", C["C3_SLE_vs_MN"], rep["C3"], dec["C3_SLE_vs_MN"])]
    MOD = [("PANEL_LR", "免疫路徑模型", "o", DIRC["免疫"]), ("GENE_LR", "全基因模型", "s", D.COLORS["sub"])]
    fig = D.figure("圖10")
    # (a) AUROC：實心＝腎絲球 20 次平均＋第一次重複 95% CI；空心＝腎小管間質重現（20 次平均）
    ax = fig.add_axes([.43, .5, .36, .42])
    ax.set(xlim=(0, 1), ylim=(len(ROWS) - .45, -.55), yticks=[])
    D.style(ax)
    ax.axvline(.5, color=D.COLORS["sub"], ls="--", lw=.8)
    D.title(fig, .015, .995, "(a) 同一處理批次內的判別力（AUROC）")
    D.text(fig, .015, .945, "比較方向", weight="bold")
    D.text(fig, .165, .945, "陽性 對 對照（例數）", weight="bold")
    D.text(fig, .815, .945, "路徑／全基因", weight="bold")
    D.text(fig, .95, .945, "判定", weight="bold", ha="center")
    for y, (grp, lab, r, t, d) in enumerate(ROWS):
        D.row_text(ax, y, grp, -1.15, ha="left", weight="bold")
        D.row_text(ax, y, f"{lab}（{r['n_pos']} 對 {r['n'] - r['n_pos']}）", -.73, ha="left")
        for j, (m, _, sym, col) in enumerate(MOD):
            yy = y + (j - .5) * .34
            D.interval(ax, yy, r[m]["auroc_mean"], r[m]["auroc_ci_rep0"], col, sym)
            ax.plot(t[m]["auroc_mean"], yy, sym, ms=4.2, color=col, mfc="white", mec=col, mew=.65, zorder=3)
        D.row_text(ax, y, f"{r['PANEL_LR']['auroc_mean']:.2f}／{r['GENE_LR']['auroc_mean']:.2f}", 1.07, ha="left")
        D.row_text(ax, y, "成立" if d["回推成立"] else "不成立", 1.43, ha="center")
    ax.set_xlabel("AUROC（0.5＝亂猜）", fontsize=8, labelpad=2)
    for i, (m, name, sym, col) in enumerate(MOD):
        x = .2 + i * .19
        fig.lines.append(plt.Line2D([x], [.405], marker=sym, ls="", color=col, ms=4.2, mec=col, transform=fig.transFigure))
        D.text(fig, x + .012, .405, name, va="center")
    D.text(fig, .58, .405, "實心為腎絲球，空心為腎小管間質", va="center")
    # (b) 各免疫路徑單獨 AUROC（腎絲球；未經交叉驗證，只作描述）
    panels = list(B["B1_primary"]["per_panel"])
    zh = dict(interferon="干擾素", complement="補體", b_plasma="B／漿細胞", t_cell="T 細胞", myeloid="單核巨噬", neutrophil="嗜中性球")
    M = np.array([[r["per_panel"][p]["auroc"] for p in panels] for _, _, r, _, _ in ROWS])
    D.title(fig, .015, .36, "(b) 各免疫路徑單獨的 AUROC（腎絲球，描述用）")
    hx = fig.add_axes([.43, .02, .52, .29])
    hx.imshow(M, cmap="RdBu_r", vmin=0, vmax=1, aspect="auto")
    hx.set_xticks(range(len(panels)), [zh[p] for p in panels], fontsize=7.5)
    hx.xaxis.tick_top()
    hx.set_yticks([])
    hx.tick_params(length=0)
    for s in hx.spines.values():
        s.set_visible(False)
    for i in range(M.shape[0]):
        D.row_text(hx, i, f"{ROWS[i][1]}", -.79, ha="left")
        for j in range(M.shape[1]):
            hx.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if abs(M[i, j] - .5) > .3 else D.INK)
    save(fig, "圖10_免疫方向切片轉錄體.png")
    return M, panels


def main():
    for draw in (D.draw_flow, D.draw_discrimination, D.draw_calibration, D.draw_robustness,
                 D.draw_external, D.draw_decision, D.draw_exposure, D.draw_recalibration, fig9, fig10):
        draw()
    for path, w, h in D.OUTPUTS:
        print(f"[完成] {path.name}\t{w}×{h}")


if __name__ == "__main__":
    main()
