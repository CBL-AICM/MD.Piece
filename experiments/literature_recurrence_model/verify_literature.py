"""最後查核：literature.py 每一個數字是否真的出現在該 PMID 的 PubMed 摘要裡。

摘要本身不進儲存庫（版權），查核時需要 PubMed 快取資料夾（pm.py 下載的 <pmid>.json）。
輸出 outputs/literature_check.csv；有任何一筆對不上就以非零結束碼結束。

跑法： python experiments/literature_recurrence_model/verify_literature.py <PubMed 快取資料夾>
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import literature as LIT  # noqa: E402

# 換算前的原始寫法（摘要中的字樣）；由比例或倒數換算來的值，查核原始數字
RAW = {
    ("19714602", 0.333): ["One-third"], ("28929239", 0.144): ["13.0-15.7%"], ("36631164", 0.16): ["16%", "14.8 months"],
    ("35737642", 0.36): ["0.36 per person-year"], ("29862047", 41 / 97): ["Ninety-seven", "Forty-one"],
    ("33864158", 1 - 0.865): ["86.5%"], ("40774410", 0.17): ["0.17 events/year"], ("40774410", 0.42): ["0.42 events/year"],
    ("40321140", 0.106): ["10.6%", "1.96"], ("34877757", 45 / 124): ["45 patients", "124 patients"],
    ("33864158", 1 - 0.607): ["60.7%"], ("33864158", 1 - 0.80): ["80%"], ("29724729", 1 - 0.494): ["49.4%"],
    ("29724729", 1 - 0.719): ["71.9%"], ("40948107", 0.95): ["0.95"], ("40948107", 0.52): ["0.52"], ("40948107", 0.28): ["0.28"],
    ("20089952", 0.40): ["0.40 with placebo"], ("20089952", 0.18): ["0.18 with 0.5 mg"], ("25154681", 0.40): ["40%"],
    ("25154681", 0.51): ["51%"], ("12543288", 19 / 86): ["19 of 86"], ("19101844", 0.83): ["83%"],
    ("39292608", 0.095): ["9.5%"], ("39292608", 0.333): ["33.3%"], ("21319592", 0.086): ["8.6%"], ("32205147", 0.076): ["7.6%"],
    ("32097488", 0.1286): ["12.86%"], ("33151477", 0.295): ["29.5%", "21 [6-111] months"],
}


def main(cache):
    rows = []

    def check(kind, pmid, desc, needles):
        ab = json.load(open(os.path.join(cache, f"{pmid}.json"), encoding="utf-8"))["abstract"]
        ab = ab.replace("·", ".").replace("\xa0", " ")  # 部分期刊以中間點作小數點
        ok = all(n in ab for n in needles)
        rows.append({"type": kind, "pmid": pmid, "item": desc, "abstract_text_checked": " / ".join(needles), "found": ok})

    for d, pmid, kind, v, y, note in LIT.RATES:
        check("年復發率", pmid, f"{d}: {note}", RAW[(pmid, v)])
    for hyp, dis, pmid, m, est, lo, hi, note in LIT.EFFECTS:
        if pmid == "9541091":
            needles = ["0.43 (95% CI: 0.17, 1.12)"]
        else:
            needles = [f"{est:g}", f"{lo:g}", f"{hi:g}"]
        check(hyp, pmid, f"{dis}: {note}", needles)
    for name, pmid, t, c in LIT.CURVES:
        fmt = {"35737642": ["45% at 1 year", "64% at 3 years", "80% at 5 years"], "25154681": ["40%, 63%, and 66%", "51%, 75%, and 79%"],
               "32097488": ["12.86%, 27.84% and 36.1%"], "21319592": ["8.6%, 12.6%, and 23.9%"]}[pmid]
        check("H3 曲線", pmid, name, fmt)
    check("劑量反應", "16344520", "MS prior relapses", ["0.59 for one, 0.91 for two, and 1.45 for three"])
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, "outputs", "literature_check.csv"), index=False, encoding="utf-8-sig")
    print(f"{df.found.sum()}/{len(df)} 筆在摘要中找到原始數字")
    print(df[~df.found].to_string() if (~df.found).any() else "全部相符")
    return 0 if df.found.all() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
