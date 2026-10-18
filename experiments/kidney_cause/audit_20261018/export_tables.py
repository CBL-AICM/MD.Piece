# -*- coding: utf-8 -*-
"""審核結果匯出成 Excel 可開的 CSV（UTF-8 BOM）。用法：python export_tables.py <outdir>"""
import csv
import json
import os
import sys

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
R = json.load(open("refcheck.json", encoding="utf-8"))
FALSE_POS = {"第一作者不符：Crossref＝Floege": "團體作者（KDIGO 工作小組）；Crossref 列第一位委員，非錯誤",
             "第一作者不符：Crossref＝Stevens": "團體作者（KDIGO 工作小組）；Crossref 列第一位委員，非錯誤",
             "無 DOI 也無網址（請人工確認來源）": "NCHS Vital and Health Statistics Series 2 No. 175 為政府報告、無 DOI；已確認 CDC 原文 PDF 存在（sr02_175.pdf）"}
with open(os.path.join(out, "文獻核對表.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["文獻", "出現於", "DOI／網址", "Crossref 標題", "Crossref 期刊", "年", "卷", "頁", "標題相似度", "判定", "說明"])
    for r in R["refs"]:
        cr = r.get("crossref", {})
        issues = r["issues"]
        note = "；".join(FALSE_POS.get(i, i) for i in issues)
        verdict = "正確" if not issues or all(i in FALSE_POS for i in issues) else "需確認"
        if "url" in r:
            note = (note + "；" if note else "") + f"網址可開啟（HTTP {r.get('url_status')}）"
        w.writerow([r["ref"], "、".join({"B_fair": "說明書", "A_tisf": "研究報告"}[d] for d in r["docs"]),
                    r.get("doi") or r.get("url", ""), cr.get("title", ""), cr.get("journal", ""), cr.get("year", ""),
                    cr.get("volume", ""), cr.get("page", ""), r.get("title_sim", ""), verdict, note])

A = json.load(open("align.json", encoding="utf-8"))
rows = []
for doc, rep in A.items():
    name = {"B_fair": "說明書", "A_tisf": "研究報告"}[doc]
    for d in rep["aligned_diff"]:
        rows.append([name, d["where"], "與產生器對齊、數字序列有差", json.dumps(d["diffs"], ensure_ascii=False), d["doc"][:200], d["canon"][:200]])
    for u in rep["unaligned"]:
        rows.append([name, u["where"], "新寫或改寫段落（逐項人工／claims.py 核對）", "", u["text"][:200], ""])
with open(os.path.join(out, "數字核對紀錄.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["文件", "位置", "類別", "差異（文件數字 vs 產生器數字）", "文件文字", "產生器文字"])
    w.writerows(rows)
    w.writerow([])
    for doc, rep in A.items():
        w.writerow([{"B_fair": "說明書", "A_tisf": "研究報告"}[doc], "", f"與產生器逐段一致：{rep['aligned_same']} 段／列"])
print("ok", len(R["refs"]), len(rows))
