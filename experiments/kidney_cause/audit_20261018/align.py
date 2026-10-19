# -*- coding: utf-8 -*-
"""把 Word 文件的每段／每表列，對齊到產生器（讀結果檔、有 assert）重新產生的正典文字，比較數字序列。
對不齊的段落列出，供人工逐段核對。用法：python align.py <kidney_cause_dir>"""
import difflib
import json
import os
import re
import sys

KC = sys.argv[1]
sys.path.insert(0, KC)
os.chdir(KC)
import build_fair_award as FA  # noqa: E402
import build_tisf_report as TR  # noqa: E402

canon = {"B_fair": FA.emit("repo")[0], "A_tisf": TR.build("repo")}
os.chdir(os.path.dirname(os.path.abspath(__file__)))

NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def clean(s):
    s = re.sub(r"\*\*|==|`|!\[\]\([^)]*\)|\[\[[^\]]*\]\]", "", s)
    return s.replace("−", "-").replace("：", "").replace(":", "").strip()


def units_md(md):
    out = []
    for line in md.split("\n"):
        line = line.strip()
        if not line or line.startswith("|---") or line.startswith("<!--"):
            continue
        if line.startswith("|"):
            out.append(" | ".join(c.strip() for c in line.strip("|").split("|")))
        else:
            out.append(re.sub(r"^#+\s*|^>\s*|^\d+\.\s+(?=\D)|^-\s+", "", line))
    return [clean(u) for u in out if clean(u)]


def units_doc(J):
    refs = set(J["refs"])
    out = []
    for i in J["items"]:
        if i["kind"] == "para" and i["text"] not in refs:
            out.append((i["where"], clean(i["text"])))
        elif i["kind"] == "table":
            for r, row in enumerate(i["rows"]):
                out.append((f"{i['where']}r{r}", clean(" | ".join(row))))
    return out


res = {}
for doc, md in canon.items():
    J = json.load(open(f"{doc}.json", encoding="utf-8"))
    cu = units_md(md)
    du = units_doc(J)
    cnum = [NUM.findall(c) for c in cu]
    report = dict(aligned_same=0, aligned_diff=[], unaligned=[])
    for where, t in du:
        nums = NUM.findall(t)
        if not nums:
            continue
        best, bs = None, 0
        for k, c in enumerate(cu):
            if abs(len(c) - len(t)) > max(len(t), len(c)) * 0.8:
                continue
            s = difflib.SequenceMatcher(None, t, c, autojunk=False).quick_ratio()
            if s > bs:
                s = difflib.SequenceMatcher(None, t, c, autojunk=False).ratio()
                if s > bs:
                    best, bs = k, s
        if best is None or bs < 0.55:
            report["unaligned"].append(dict(where=where, text=t[:300]))
            continue
        if nums == cnum[best]:
            report["aligned_same"] += 1
        else:
            sm = difflib.SequenceMatcher(None, nums, cnum[best])
            diffs = [(nums[a:b], cnum[best][c:d]) for op, a, b, c, d in sm.get_opcodes() if op != "equal"]
            report["aligned_diff"].append(dict(where=where, sim=round(bs, 2), diffs=diffs, doc=t[:300], canon=cu[best][:300]))
    res[doc] = report
    print(doc, "same", report["aligned_same"], "diff", len(report["aligned_diff"]), "unaligned", len(report["unaligned"]))
json.dump(res, open("align.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
