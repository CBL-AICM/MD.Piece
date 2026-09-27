# -*- coding: utf-8 -*-
"""重建示範受試者（v3.2 修正後樣本）、產生 ui/direction.html，並以 node 執行網頁中的數學區塊，逐軸比對 Python。
    python verify_direction_html.py
示範受試者 SEQN 89459（2015–2016，HCV RNA 陽性）僅作展示，不代表準確率。"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                        # noqa: E402

import make_direction_html                                # noqa: E402
from direction import PARAMS, predict                     # noqa: E402
from nhanes_cohort import build_v3                        # noqa: E402

SEQN = 89459
DEMO = os.path.join(ROOT, "params", "direction_demo_patient.json")
EXPECTED = os.path.join(ROOT, "params", "direction_demo_expected.json")


def main():
    M = json.load(open(PARAMS, encoding="utf-8"))
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    kd = build_v3(P, verbose=False, fixes=True)["cohort"]      # v3.2 修正後資料（示範者 2015–2016 年，量尺換算不影響）
    row = kd[kd["SEQN"] == SEQN].iloc[0]
    allf = sorted({f for a in M["axes"].values() for f in a["features"]})
    vals = {f: float(row[f]) for f in allf if not np.isnan(row[f])}
    json.dump(vals, open(DEMO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    res = predict(vals, M)
    exp = dict(SEQN=SEQN, cycle=row["cycle"], labels=dict(hep3=float(row["hep3"]), hcv3=float(row["hcv3"]),
                                                          hbv3=float(row["hbv3"]), dm3=float(row["dm3"])),
               axes={k: dict(cal=round(a["probability"], 6), band=a["band"], miss=a["n_missing"],
                             odds_ratio=round(a["odds_ratio_vs_prior"], 4), drivers=[d["var"] for d in a["drivers"]])
                     for k, a in res["axes"].items()})
    json.dump(exp, open(EXPECTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    make_direction_html.main()
    html = open(os.path.join(ROOT, "ui", "direction.html"), encoding="utf-8").read()
    consts = re.search(r"^const M=.*?;$", html, re.M).group(0)
    math = html[html.index("/*MATH-START*/"):html.index("/*MATH-END*/")]
    js = consts + "\n" + math + "\nconst r=predict(DEMO);console.log(JSON.stringify(Object.fromEntries(Object.entries(r).map(" \
        "([k,a])=>[k,{cal:a.cal,band:a.band,miss:a.miss,or:a.or,drivers:a.drivers.map(d=>d.f)}]))));"
    tmp = os.path.join(ROOT, "ui", "_verify.js")
    open(tmp, "w", encoding="utf-8").write(js)
    out = json.loads(subprocess.run(["node", tmp], capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    os.remove(tmp)
    for k, e in exp["axes"].items():
        j = out[k]
        ok = abs(j["cal"] - e["cal"]) < 5e-7 and j["band"] == e["band"] and j["miss"] == e["miss"] \
            and abs(j["or"] - e["odds_ratio"]) < 5e-4 and j["drivers"] == e["drivers"]
        print(f"[{k}] Python {e['cal']:.6f} {e['band']} ×{e['odds_ratio']:.2f} 缺{e['miss']}｜JS {j['cal']:.6f} {j['band']} "
              f"×{j['or']:.2f} 缺{j['miss']}｜推動因子順序{'相同' if j['drivers'] == e['drivers'] else '不同'} → {'✅ 一致' if ok else '❌ 不一致'}")
        assert ok
    print(f"[示範] SEQN {SEQN}（{exp['cycle']}）標籤 {exp['labels']}")


if __name__ == "__main__":
    main()
