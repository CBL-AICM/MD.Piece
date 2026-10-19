"""說明書圖一（研究架構）與圖二（研究流程）的 matplotlib 版本。

文字用平實說法，不用公式化或誇大的詞；版型、配色沿用 FigureLabs 版。
跑法： PYTHONUTF8=1 python experiments/chronic_recurrence_longitudinal/flowcharts.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run as base  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

NAVY, INK, EDGE, FILL, GREY = "#2d5f8b", "#333333", "#9a9a9a", "#eef2f6", "#f3f3f3"


def canvas(w, h):
    fig = plt.figure(figsize=(w / 10, h / 10))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w); ax.set_ylim(h, 0); ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, fc="white", ec=EDGE, r=1.2, lw=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw))


def text(ax, x, y, s, size=11, color=INK, ha="center", weight="normal", ls=1.5):
    ax.text(x, y, s, fontsize=size, color=color, ha=ha, va="center", weight=weight, linespacing=ls)


def arrow(ax, pts, color="#777777"):
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=1.4)
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=14, color=color, lw=1.4))


def framework():
    fig, ax = canvas(82, 100)
    box(ax, 5, 3, 72, 7)
    text(ax, 41, 6.5, "把患者的長期紀錄整理成風險高低和近期變化，看診前交給醫師和患者", 12)

    steps = [("記錄", "每天記下症狀、用藥、\n睡眠、心情與生理數值"), ("預測", "算出復發風險高低"),
             ("解釋", "找出近期變化\n最大的項目"), ("摘要", "整理成一份\n看診前的報告")]
    xs = [4, 23.5, 43, 62.5]
    for (t, d), x in zip(steps, xs):
        box(ax, x, 15, 16, 12, fc=FILL)
        text(ax, x + 8, 18, t, 14, NAVY)
        text(ax, x + 8, 22.5, d, 10.5)
    for x in xs[:-1]:
        arrow(ax, [(x + 16, 21), (x + 19.5, 21)])

    box(ax, 14, 33.5, 24.5, 9, fc=FILL)
    text(ax, 26.25, 36.3, "假說二　復發預測", 14)
    text(ax, 26.25, 40, "長期紀錄能不能預測復發和復發時間", 10.5)
    box(ax, 43.5, 33.5, 24.5, 9, fc=FILL)
    text(ax, 55.75, 36.3, "假說一　醫病溝通", 14)
    text(ax, 55.75, 40, "診前報告能不能縮小醫病資訊落差", 10.5)
    arrow(ax, [(31.5, 27), (31.5, 33.5)])
    ax.plot([51, 51, 31.5], [27, 30, 30], color="#777777", lw=1.4)
    arrow(ax, [(70.5, 27), (70.5, 30), (55.75, 30), (55.75, 33.5)])

    text(ax, 41, 47, "用五種方法檢驗兩個假說", 14)
    cols = [(6, 14), (20, 24), (44, 32)]
    rows = [("方法", "假說一", "假說二"),
            ("文獻驗證", "OpenNotes、診前問卷研究", "用手機預測 COPD 惡化等研究"),
            ("競品分析", "Previsit.ai 等診前摘要產品", "Welldoc 等風險預測產品"),
            ("數位雙生模擬", "留下的感染線索：\nMD. Piece 37%，病人回憶 11%", "3,200 位虛擬病患，\nAUROC 約 0.77"),
            ("真實縱向資料", "無", "NHEFS 2,486 位成人，\n長期紀錄 AUROC 0.71"),
            ("量表研究", "醫護接受度與情境量表，\n送倫理審查後再做", "無")]
    y = 50
    for i, r in enumerate(rows):
        h = 5.5
        for (cx, cw), s in zip(cols, r):
            ax.add_patch(Rectangle((cx, y), cw, h, fc=NAVY if i == 0 else "white", ec="#888888", lw=0.8))
            text(ax, cx + cw / 2, y + h / 2, s, 11 if i == 0 else 10, "white" if i == 0 else INK)
        y += h

    box(ax, 19, 88, 44, 7, fc=FILL)
    text(ax, 41, 91.5, "MD. Piece 只是輔助工具，不做診斷，也不取代醫師", 13)
    return fig


def workflow():
    fig, ax = canvas(82, 100)
    LX, LW, RX, RW = 5, 11.5, 18.5, 59

    def stage(y, h, month, title, lines):
        box(ax, LX, y, LW, h, fc=NAVY, ec=NAVY, r=0.6)
        text(ax, LX + LW / 2, y + h / 2, month, 14, "white")
        box(ax, RX, y, RW, h)
        text(ax, RX + RW / 2, y + 2.6, title, 14)
        for k, s in enumerate(lines):
            text(ax, RX + 3.5, y + 6 + k * 2.4, s, 11, ha="left")

    def down(y0, y1):
        arrow(ax, [(LX + LW / 2, y0), (LX + LW / 2, y1)], "#aaaaaa")

    stage(3, 13, "第 1 至 2 月", "合成資料與建模",
          ["用 Synthea 和自建數位雙生做出 3,200 位虛擬慢性病患",
           "每位病患各有真相、MD. Piece 紀錄、病人回憶三種紀錄",
           "訓練 Cox、隨機存活森林與 logistic 模型，再用 SHAP 找主因"])
    down(16, 19.5)
    stage(19.5, 10, "第 3 月", "溝通模擬與結果檢查",
          ["比較三種紀錄各留下多少感染線索", "用置換檢定確認訓練資料沒有混進答案"])
    down(29.5, 33)
    stage(33, 10, "第 4 月", "競品分析與文獻查證",
          ["比較 9 款國內外慢性病管理產品", "在 PubMed 查文獻，整理各研究的效果大小"])
    down(43, 46.5)

    y0, h0 = 46.5, 35
    box(ax, LX, y0, LW, h0, fc=NAVY, ec=NAVY, r=0.6)
    text(ax, LX + LW / 2, y0 + h0 / 2, "第 5 月", 14, "white")
    box(ax, RX, y0, RW, h0)
    text(ax, RX + RW / 2, y0 + 2.6, "真實縱向資料驗證", 14)
    box(ax, 20.5, 51, 34, 24.5, fc=GREY, ec="#bbbbbb")
    text(ax, 37.5, 53.2, "主要資料　NHEFS（CDC）", 11.5, weight="bold")
    nh = ["因四種慢性病住院 6,669 人次", "18 歲以上、資料完整、追蹤 3 至 10 年",
          "納入 2,486 位成人（3,615 筆患者與疾病組合）", "22,429 個預測時點，預測之後 12 個月會不會復發"]
    for k, s in enumerate(nh):
        yy = 55.2 + k * 4.6
        box(ax, 21.8, yy, 31.4, 3.2, r=0.5, ec="#bbbbbb")
        text(ax, 37.5, yy + 1.6, s, 10)
        if k:
            arrow(ax, [(37.5, yy - 1.4), (37.5, yy)], "#aaaaaa")
    text(ax, 37.5, 73.8, "四種病：COPD 或氣喘、心衰竭、缺血性心臟病、糖尿病", 9)
    box(ax, 55.5, 51, 21, 24.5, fc=GREY, ec="#bbbbbb")
    text(ax, 66, 53.2, "輔助資料 Framingham（NIH）", 9.5, weight="bold")
    fr = [("第 1 次檢查已有高血壓的成人", 3.2), ("兩次檢查數值完整，\n檢查前沒有心血管事件", 4.6),
          ("納入 779 位，預測\n10 年內心血管事件", 4.6)]
    yy = 55.2
    for k, (s, hh) in enumerate(fr):
        box(ax, 57, yy, 18, hh, r=0.5, ec="#bbbbbb")
        text(ax, 66, yy + hh / 2, s, 9.5)
        if k:
            arrow(ax, [(66, yy - 1.4), (66, yy)], "#aaaaaa")
        yy += hh + 1.4
    box(ax, 20.5, 77, 55.5, 3.2, fc="#dddddd", ec="#bbbbbb", r=0.5)
    text(ax, 48.25, 78.6, "MD. Piece 引擎和三個對照模型比較，再用 Kaplan-Meier 與 Cox 模型看復發時間", 10)
    down(81.5, 85)

    stage(85, 12, "第 5 月", "App 要用幾年才夠準",
          ["假設使用 App 1 到 10 年，比較預測準確度和提前預警的比例",
           "用 Cox 模型預測復發時間線，和實際累積復發曲線對照"])
    return fig


if __name__ == "__main__":
    base.use_doc_fonts(plt)
    plt.rcParams["axes.grid"] = False
    for name, fn in [("fig0_framework_plain.png", framework), ("fig0_workflow_plain.png", workflow)]:
        f = fn()
        f.savefig(os.path.join(base.OUT, name), dpi=250)
        plt.close(f)
        print("saved", name)
