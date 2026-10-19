# -*- coding: utf-8 -*-
"""把研究報告 Word 檔內的圖 1–9 換成 figures/report/ 重畫版（make_figures_report.py 產生；寬度不變、高度依新圖比例）。
以圖說「圖 N」定位：圖片段落＝圖說的前一段。原檔不動，另存新檔。
    python -X utf8 update_report_figures_docx.py <輸入.docx> <輸出.docx>"""
import re
import sys
from pathlib import Path

from docx import Document
from PIL import Image

ROOT = Path(__file__).resolve().parent
FIG = {int(p.name.split("_")[0][1:]): p for p in (ROOT / "figures" / "report").glob("圖*.png")}
src, dst = sys.argv[1:3]
assert Path(src).resolve() != Path(dst).resolve(), "不覆寫原檔"
d = Document(src)
P = d.paragraphs
done = []
for i, p in enumerate(P):
    m = re.match(r"圖 (\d+) ", p.text)
    if not m or int(m.group(1)) not in FIG or i == 0:
        continue
    n = int(m.group(1))
    blips = P[i - 1]._p.xpath(".//a:blip")
    assert len(blips) == 1, f"圖 {n} 的前一段應恰有一張圖"
    rid = blips[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
    d.part.related_parts[rid]._blob = FIG[n].read_bytes()
    w, h = Image.open(FIG[n]).size
    for e in P[i - 1]._p.xpath(".//wp:extent") + P[i - 1]._p.xpath(".//a:ext"):
        e.set("cy", str(round(int(e.get("cx")) * h / w)))
    done.append(n)
assert sorted(done) == sorted(n for n in FIG if n <= 9), f"換圖不完整：{done}"
d.save(dst)
print("已換圖", sorted(done), "→", dst)
