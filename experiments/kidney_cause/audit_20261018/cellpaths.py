# -*- coding: utf-8 -*-
"""每個表格數字 → 結果檔中所有能對上的欄位路徑（依呈現位數四捨五入），供逐格語意核對。
用法：python cellpaths.py <results_dir> <doc> <table_id...>"""
import glob
import json
import os
import re
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

RES, DOC, TIDS = sys.argv[1], sys.argv[2], sys.argv[3:]
idx = defaultdict(list)


def leaves(o, path):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, f"{path}[{i}]")
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield path, float(o)


for f in sorted(glob.glob(os.path.join(RES, "*.json"))):
    try:
        J = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    for p, x in leaves(J, os.path.basename(f)):
        if x != x or abs(x) > 1e9:
            continue
        for mult, tag in [(1, ""), (100, "×100")]:
            for d in range(0, 5):
                q = Decimal(repr(x * mult)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
                idx[(d, str(q))].append(p + tag)

J = json.load(open(f"{DOC}.json", encoding="utf-8"))
NUM = re.compile(r"[−\-]?\d{1,3}(?:,\d{3})+|[−\-]?\d+(?:\.\d+)?")
for i in J["items"]:
    if i["kind"] != "table" or i["where"] not in TIDS:
        continue
    print("####", i["where"])
    for r, row in enumerate(i["rows"]):
        for c, cell in enumerate(row):
            for tok in NUM.findall(cell):
                s = tok.replace(",", "").replace("−", "-")
                d = len(s.split(".")[1]) if "." in s else 0
                if d == 0 and 1990 <= abs(int(float(s))) <= 2030:
                    continue
                key = (d, str(Decimal(s)))
                hits = idx.get(key, [])
                # 負號：結果檔有正負，文件用 + 或 − 號
                if not hits and s.startswith("-"):
                    hits = idx.get((d, str(Decimal(s[1:]))), [])
                show = "; ".join(hits[:4]) + (f" …(+{len(hits) - 4})" if len(hits) > 4 else "")
                print(f"r{r}c{c} [{row[0][:14]}|{i['rows'][0][c][:10] if c < len(i['rows'][0]) else ''}] {tok} -> {show or '!!! 無對應'}")
