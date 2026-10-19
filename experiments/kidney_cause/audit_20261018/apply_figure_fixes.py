# -*- coding: utf-8 -*-
"""依 audit_20261018/圖表核對_20261019.md 的四項建議修改兩份敘述版文件，另存新檔（原檔不動）。
  1. 說明書圖一、圖八：浮動圖改為內嵌，放在圖說上方（圖說在圖下，與其他 9 張一致）
  2. 說明書圖五、圖十一：顯示寬度放大到 17 cm（等比）
  3. 圖十一（研究報告圖 9）：換成右圖 x 軸下限 0.1 的新圖（make_figures_report.py）
  4. 研究報告：內文加上圖 1～圖 9 的引用
每處以原文定位，找不到或找到多處即停。
  python -X utf8 apply_figure_fixes.py <B原檔> <B新檔> <A原檔> <A新檔>"""
import copy
import io
import sys
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image

B_SRC, B_DST, A_SRC, A_DST = sys.argv[1:5]
assert B_SRC != B_DST and A_SRC != A_DST, "不覆寫原檔"
FIG11 = Path(__file__).resolve().parents[1] / "figures" / "report" / "圖9_九種病因調整盛行率比.png"
CM = 360000
text = lambda el: "".join(t.text or "" for t in el.iter(qn("w:t"))).strip()


def caption_para(d, prefix):
    hits = [el for el in d.element.body.iterchildren() if el.tag == qn("w:p") and text(el).startswith(prefix)]
    assert len(hits) == 1, f"圖說「{prefix}」找到 {len(hits)} 處"
    return hits[0]


def image_before(cap):
    """圖說之前最近一張圖所在的段落與 drawing。"""
    el = cap
    while el is not None:
        dr = el.findall(".//" + qn("w:drawing"))
        if dr:
            return el, dr[-1]
        el = el.getprevious()
    raise AssertionError("找不到圖")


def drawing_in(el):
    dr = el.findall(".//" + qn("w:drawing"))
    assert len(dr) == 1, f"段落內有 {len(dr)} 張圖"
    return dr[0]


def to_inline_below_caption(d, prefix, template_img_para, log):
    """把浮動圖（anchor）轉成內嵌（inline），放進新段落，插在圖說之前（圖在上、圖說在下）。"""
    cap = caption_para(d, prefix)
    anchors = [a for el in [cap, cap.getprevious(), cap.getprevious().getprevious()]
               for a in el.findall(".//" + qn("wp:anchor"))]
    assert len(anchors) == 1, f"[{prefix}] 浮動圖 {len(anchors)} 張"
    anchor = anchors[0]
    inline = OxmlElement("wp:inline")
    for a in ("distT", "distB", "distL", "distR"):
        inline.set(a, "0")
    for tag in ("wp:extent", "wp:effectExtent", "wp:docPr", "wp:cNvGraphicFramePr", "a:graphic"):
        el = anchor.find(qn(tag))
        if el is not None:
            inline.append(copy.deepcopy(el))
    run = anchor
    while run.tag != qn("w:r"):
        run = run.getparent()
    anchor.getparent().replace(anchor, inline)
    run.getparent().remove(run)
    newp = copy.deepcopy(template_img_para)
    for r in newp.findall(qn("w:r")):
        newp.remove(r)
    newp.append(run)
    prev = cap.getprevious()
    if prev.tag == qn("w:p") and not text(prev) and not prev.findall(".//" + qn("w:drawing")):
        prev.getparent().replace(prev, newp)   # 圖說前原本的空白置中段落，直接換成圖段落
        log.append((prefix, "浮動圖改內嵌，取代圖說前的空白段落"))
    else:
        cap.addprevious(newp)
        log.append((prefix, "浮動圖改內嵌，插在圖說前"))


def set_width(drawing, width_cm, log, label):
    ext = drawing.find(".//" + qn("wp:extent"))
    cx, cy = int(ext.get("cx")), int(ext.get("cy"))
    ncx = int(width_cm * CM)
    ncy = round(cy * ncx / cx)
    ext.set("cx", str(ncx))
    ext.set("cy", str(ncy))
    for e in drawing.iter(qn("a:ext")):
        e.set("cx", str(ncx))
        e.set("cy", str(ncy))
    log.append((label, f"{cx / CM:.2f}×{cy / CM:.2f} cm → {ncx / CM:.2f}×{ncy / CM:.2f} cm"))


def swap_blob(d, drawing, png, log, label):
    rid = drawing.find(".//" + qn("a:blip")).get(qn("r:embed"))
    part = d.part.related_parts[rid]
    old = Image.open(io.BytesIO(part.blob)).size
    new = Image.open(png).size
    assert old == new, f"[{label}] 圖檔尺寸改變 {old}→{new}，需重算顯示高度"
    part._blob = Path(png).read_bytes()
    log.append((label, f"換圖（{new[0]}×{new[1]}，尺寸不變）"))


def rep(d, old, new, log, label):
    hits = list({id(p._p): p for p in d.paragraphs if old in p.text}.values())
    assert len(hits) == 1, f"[{label}] 找到 {len(hits)} 處：{old[:30]}"
    p = hits[0]
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new, 1)
            break
    else:
        full = p.text.replace(old, new, 1)
        p.runs[0].text = full
        for r in p.runs[1:]:
            r.text = ""
    log.append((label, old, new))


# ======================= 說明書 =======================
B = docx.Document(B_SRC)
LB = []
tmpl = image_before(caption_para(B, "圖二、"))[0]          # 圖二的內嵌圖段落（置中）當作版式
to_inline_below_caption(B, "圖一、", tmpl, LB)
to_inline_below_caption(B, "圖八、", tmpl, LB)
for h in ("參、研究過程與方法", "一、研究過程"):   # 圖一改內嵌後，標題不可單獨留在上一頁底部
    hp = [p for p in B.paragraphs if p.text.strip() == h]
    assert len(hp) == 1, f"標題「{h}」找到 {len(hp)} 處"
    hp[0].paragraph_format.keep_with_next = True
    LB.append((h, "與下段同頁"))
set_width(image_before(caption_para(B, "圖五、"))[1], 17.0, LB, "圖五寬度")
p11, d11 = image_before(caption_para(B, "圖十一、"))
swap_blob(B, d11, FIG11, LB, "圖十一")
set_width(d11, 17.0, LB, "圖十一寬度")
B.save(B_DST)

# ======================= 研究報告 =======================
A = docx.Document(A_SRC)
LA = []
_, d9 = image_before(caption_para(A, "圖 9 "))
swap_blob(A, d9, FIG11, LA, "圖 9")
REFS = [
    ("以及 HDL 未讀入。修正後", "以及 HDL 未讀入（圖 1）。修正後", "圖 1"),
    ("是盛行率 2.0% 的 6.8 倍。糖尿病軸", "是盛行率 2.0% 的 6.8 倍（圖 2）。糖尿病軸", "圖 2"),
    ("都接近理想（截距接近 0、斜率接近 1）。", "都接近理想（截距接近 0、斜率接近 1；圖 3）。", "圖 3"),
    ("改用原發布肌酸酐判定腎臟標籤，結果幾乎不變。", "改用原發布肌酸酐判定腎臟標籤，結果幾乎不變（圖 4）。", "圖 4"),
    ("淨效益幾乎相同（0.0147 對 0.0146）。若只略過", "淨效益幾乎相同（0.0147 對 0.0146；圖 5）。若只略過", "圖 5"),
    ("尿中金屬關聯的方向會隨結果定義與模型設定而改變。", "尿中金屬關聯的方向會隨結果定義與模型設定而改變（圖 6）。", "圖 6"),
    ("糖尿病軸在新資料上大致維持，", "糖尿病軸在新資料上大致維持（圖 7），", "圖 7"),
    ("不重新校準則略為低估（0.95）；", "不重新校準則略為低估（0.95；圖 8）；", "圖 8"),
    ("B 型肝炎無法區分（1.35，95% CI 0.85–2.16）。7 項", "B 型肝炎無法區分（1.35，95% CI 0.85–2.16；圖 9）。7 項", "圖 9"),
]
for old, new, label in REFS:
    rep(A, old, new, LA, label)
A.save(A_DST)

def keep_figs_with_captions(path, prefixes, log):
    """圖段落設「與下段同頁」，避免圖與圖說被分頁拆開。"""
    d = docx.Document(path)
    for pre in prefixes:
        p = docx.text.paragraph.Paragraph(image_before(caption_para(d, pre))[0], d._body)
        p.paragraph_format.keep_with_next = True
    d.save(path)
    log.append(("全部圖", f"{len(prefixes)} 張圖段落設為與圖說同頁"))


keep_figs_with_captions(B_DST, [f"圖{c}、" for c in "一二三四五六七八九十"] + ["圖十一、"], LB)
keep_figs_with_captions(A_DST, [f"圖 {i} " for i in range(1, 11)], LA)

for name, log in (("說明書", LB), ("研究報告", LA)):
    print(f"== {name}（{len(log)} 處）")
    for row in log:
        print("  " + "｜".join(row))
