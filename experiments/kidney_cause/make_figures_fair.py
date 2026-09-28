# -*- coding: utf-8 -*-
"""科展作品說明書（得獎作品寫法）用圖——重用 make_figures_v3_2 的圖（數字全由結果檔產生），只做兩件事：
去掉圖內總標題（其中的舊編號改由說明書圖說承擔），並依說明書出現順序以中文數字重新命名。
圖一「研究架構示意圖」為 Codex 繪製之 SVG（figures/fair/圖一_研究架構示意圖.svg，只有架構、沒有數字），以 Edge 無頭模式轉成 PNG。
    python make_figures_fair.py   → figures/fair/"""
import os
import pathlib
import subprocess
import sys
import time

import matplotlib.figure

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import make_figures_v3_2 as M   # noqa: E402

OUT = os.path.join(ROOT, "figures", "fair")
FLOW = os.path.join(OUT, "圖一_研究架構示意圖")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
NEW = {   # 舊檔名 → 新檔名（依說明書出現順序）
    "圖1_分析樣本與資料修正.png": "圖二_分析樣本與資料修正.png",
    "圖2_判別力.png": "圖三_判別力.png",
    "圖3_校準_線性與非線性.png": "圖四_校準與分區.png",
    "圖4_穩健性.png": "圖五_穩健性.png",
    "圖7_外部資料.png": "圖六_外部資料.png",
    "圖5_決策曲線.png": "圖七_決策曲線.png",
    "圖6_暴露血尿比較.png": "圖八_暴露血尿比較.png",
    "圖8_重新校準交叉驗證.png": "圖九_重新校準交叉驗證.png",
}


def save(fig, name):
    fig.savefig(os.path.join(OUT, NEW[name]), dpi=220, bbox_inches="tight", facecolor="white")
    M.plt.close(fig)
    print(f"[完成] {NEW[name]}")


def main():
    os.makedirs(OUT, exist_ok=True)
    matplotlib.figure.Figure.suptitle = lambda self, *a, **k: None   # ponytail: 圖內總標題含舊編號，改由圖說承擔
    M.save = save
    for f in (M.fig1, M.fig2, M.fig3, M.fig4, M.fig5, M.fig6, M.fig7, M.fig8):
        f()
    svg = open(FLOW + ".svg", encoding="utf-8").read()
    w, h = (int(svg.split(f'{k}="')[1].split('"')[0]) for k in ("width", "height"))
    png = FLOW + ".png"
    if os.path.exists(png):
        os.remove(png)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1.5",
                    f"--window-size={w},{h}", f"--screenshot={png}", pathlib.Path(FLOW + ".svg").as_uri()],
                   check=True, capture_output=True)
    for _ in range(40):    # Edge 啟動程式先結束、截圖稍後才寫出
        if os.path.exists(png):
            break
        time.sleep(0.5)
    assert os.path.exists(png), "研究架構示意圖未轉出"
    print(f"[完成] 圖一_研究架構示意圖.png（{w}×{h} × 1.5）")


if __name__ == "__main__":
    main()
