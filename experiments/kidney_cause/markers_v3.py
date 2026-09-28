# -*- coding: utf-8 -*-
"""v3 單變量標記描述：肝炎軸（合成、僅 HCV、僅 HBV）與糖尿病軸，逐標記單變量 AUROC 與方向。
    python markers_v3.py      → results/v3_markers.json
描述性、雙尾（AUROC 與 0.5 之距離即方向與強度），不作特徵選擇；用於核對論文中「肝臟合成功能型態」之敘述。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                        # noqa: E402
from scipy.stats import mannwhitneyu                      # noqa: E402

from binary_tasks import LABEL_ADJACENT                   # noqa: E402
from exwas import bh_fdr                                  # noqa: E402
from nhanes_cohort import DERIVED, FEATURE_LABELS, build_v3  # noqa: E402

NAME = {**FEATURE_LABELS, **DERIVED, "age": "年齡", "sex": "性別"}


def scan(d, label, feats):
    y = d[label].astype(int).to_numpy()
    rows = []
    for f in feats:
        x = d[f].to_numpy(float)
        ok = ~np.isnan(x)
        a, b = x[ok & (y == 1)], x[ok & (y == 0)]
        if len(a) < 10 or len(b) < 10:
            continue
        u, p = mannwhitneyu(a, b, alternative="two-sided")
        rows.append(dict(marker=f, name=NAME.get(f, f), n_pos=int(len(a)), n_neg=int(len(b)),
                         auc=float(u / (len(a) * len(b))), p=float(p)))
    for r, q in zip(rows, bh_fdr([r["p"] for r in rows])):
        r["q"] = float(q)
    return sorted(rows, key=lambda r: -abs(r["auc"] - 0.5))


def main(v32=False):
    """v32=True（`python markers_v3.py v3.2`）：v3.2 修正後資料，另存全部標記 → results/v3_2_markers.json。"""
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = build_v3(P, verbose=False, fixes=v32)
    kd, feats = V["cohort"], V["features"]
    out = {}
    for name, lab, adj in (("肝炎（合成）", "hep3", "infection"), ("僅C肝", "hcv3", "infection"),
                           ("僅B肝", "hbv3", "infection"), ("糖尿病", "dm3", "metabolic")):
        ff = [f for f in feats if f not in LABEL_ADJACENT[adj]]
        rows = scan(kd[kd[lab].notna()], lab, ff)
        out[name] = dict(n_markers=len(rows), n_fdr05=sum(r["q"] < 0.05 for r in rows), top=rows[:10], **({"all": rows} if v32 else {}))
        print(f"[{name}] 標記 {len(rows)}、FDR<0.05 {out[name]['n_fdr05']}｜前五：" +
              "；".join(f"{r['name']} {r['auc']:.3f}" for r in rows[:5]))
    json.dump(out, open(os.path.join(ROOT, "results", "v3_2_markers.json" if v32 else "v3_markers.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(v32=len(sys.argv) > 1 and sys.argv[1] == "v3.2")
