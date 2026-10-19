# -*- coding: utf-8 -*-
"""數字逐一核對：文件中每個數字 → 是否能在 results/*.json 找到（依文件呈現的小數位數四捨五入；百分比另試 ×100）。
輸出 numcheck_<doc>.json 與未對上清單。用法：python numcheck.py <results_dir>"""
import glob
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

RES = sys.argv[1]
vals = {}  # 字串表示（各精度）→ 來源


def leaves(o, path):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, f"{path}[{i}]")
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield path, float(o)
    elif isinstance(o, str):
        for m in re.finditer(r"-?\d+(?:\.\d+)?", o):
            yield path + "#str", float(m.group())


def add(x, src):
    for d in range(0, 5):
        q = Decimal(str(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
        vals.setdefault((d, str(abs(q))), src)


for f in sorted(glob.glob(os.path.join(RES, "*.json"))):
    try:
        J = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    base = os.path.basename(f)
    for p, x in leaves(J, base):
        if abs(x) > 1e9:
            continue
        add(x, p)
        add(x * 100, p + "×100")
print("index size", len(vals))

NUM = re.compile(r"(?<![\w.])[−\-–]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[−\-]?\d+(?:\.\d+)?")


def classify(tok, ctx):
    s = tok.replace(",", "").replace("−", "-").replace("–", "-").lstrip("-")
    if "." in s:
        d = len(s.split(".")[1])
    else:
        d = 0
    x = Decimal(s)
    if d == 0:
        n = int(x)
        if 1990 <= n <= 2030:
            return "skip-year", None
        if n <= 12:
            return "skip-small", None
    key = (d, str(x))
    if key in vals:
        return "match", vals[key]
    return "unmatched", None


for doc in ["B_fair", "A_tisf"]:
    J = json.load(open(f"{doc}.json", encoding="utf-8"))
    refs = set(J["refs"])
    units = []
    for i in J["items"]:
        if i["kind"] == "para" and i["text"] not in refs:
            units.append((i["where"], i["section"], i["text"]))
        elif i["kind"] == "table":
            for r, row in enumerate(i["rows"]):
                for c, cell in enumerate(row):
                    units.append((f"{i['where']}r{r}c{c}", i["section"], cell))
    rows, seen = [], set()
    for where, sec, text in units:
        # 去掉圖表編號、條列編號、版本與協定號
        t = re.sub(r"(圖|表)\s*\d+", "", text)
        t = re.sub(r"#\S+", "", t)
        t = re.sub(r"GSE\d+|GPL\d+|GSM\d+|H\d\b|SHA256|CKD-EPI|ICD-10|1:80", "", t)
        for m in NUM.finditer(t):
            tok = m.group()
            st, src = classify(tok, t)
            ctx = t[max(0, m.start() - 25): m.end() + 15]
            key = (where, tok, ctx)
            if key in seen:
                continue
            seen.add(key)
            rows.append(dict(where=where, section=sec, tok=tok, status=st, src=src, ctx=ctx))
    json.dump(rows, open(f"numcheck_{doc}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(r["status"] for r in rows)
    print(doc, dict(c))
