# -*- coding: utf-8 -*-
"""抽出 docx 的段落、表格、圖（含圖說）、參考文獻 → <name>.json，並匯出圖檔。用法：python extract.py X.docx outdir"""
import json
import os
import re
import sys

import docx
from docx.oxml.ns import qn

src, out = sys.argv[1], sys.argv[2]
name = os.path.splitext(os.path.basename(src))[0]
d = docx.Document(src)
os.makedirs(os.path.join(out, name + "_img"), exist_ok=True)

body = d.element.body
items, heading = [], ""
ti = pi = 0
rels = d.part.rels
for el in body.iterchildren():
    tag = el.tag.split("}")[1]
    if tag == "p":
        p = docx.text.paragraph.Paragraph(el, d)
        t = p.text.strip()
        blips = el.findall(".//" + qn("a:blip"))
        for b in blips:
            rid = b.get(qn("r:embed"))
            part = rels[rid].target_part
            fn = f"P{pi}_{os.path.basename(part.partname)}"
            open(os.path.join(out, name + "_img", fn), "wb").write(part.blob)
            items.append(dict(kind="image", where=f"P{pi}", file=fn, section=heading))
        if t:
            if re.match(r"^([壹貳參肆伍陸柒捌玖拾]+、|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）)", t) and len(t) < 40:
                heading = t
            items.append(dict(kind="para", where=f"P{pi}", text=t, section=heading))
        pi += 1
    elif tag == "tbl":
        t = docx.table.Table(el, d)
        rows = [[c.text.strip() for c in r.cells] for r in t.rows]
        items.append(dict(kind="table", where=f"T{ti}", rows=rows, section=heading))
        ti += 1

# 參考文獻：「參考文獻」標題之後的段落
paras = [i for i in items if i["kind"] == "para"]
ri = next((k for k, i in enumerate(paras) if re.fullmatch(r".{0,6}參考(文獻|資料).{0,6}", i["text"])), None)
refs = [i["text"] for i in paras[ri + 1:]] if ri is not None else []
json.dump(dict(items=items, refs=refs), open(os.path.join(out, name + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(name, "paras", len(paras), "tables", ti, "images", sum(i["kind"] == "image" for i in items), "refs", len(refs))
