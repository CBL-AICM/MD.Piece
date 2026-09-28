# -*- coding: utf-8 -*-
"""免疫方向（v3.2 資料）——完全依 params/immune_v3_2_plan.json（計畫先提交，之後才執行）。  python immune_v3_2.py
公開 ANA 次樣本（SSANA_A，1999–2004）∩ 腎臟指標異常成人；標籤 imm3＝ANA 1:80 稀釋 3+／4+（SSTOT≥3）。
評估沿用 evaluate_v3_2（部署工具結構、分層 5 折 × 5 次、seed 20260926）；不做時間外推、加權與外部評估（見計畫 not_done）。"""
import hashlib
import json
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np                                                    # noqa: E402
import pandas as pd                                                   # noqa: E402

from binary_tasks import LABEL_ADJACENT                               # noqa: E402
from evaluate_v3 import SEED, dca                                     # noqa: E402
from evaluate_v3_2 import (MAIN, MODELS, PAIRS, demographics, nested, paired, paired_auroc,  # noqa: E402
                           sets_for, summarize)
from nhanes_cohort import build_v3                                    # noqa: E402

PLAN = os.path.join(ROOT, "params", "immune_v3_2_plan.json")
OUT = os.path.join(ROOT, "results", "immune_v3_2.json")
GRID = np.round(np.arange(0.05, 0.3001, 0.05), 3)
SPECIFIC = ["SSU1RNP", "SSSM", "SSRIBOP", "SSROSSA", "SSLASSB", "SSSUAR2", "SSRPA", "SSJO_1", "SSPL_7", "SSPL_12", "SSEJ",
            "SSOJ", "SSSRP", "SSKU", "SSPM_SCL", "SSMI_2", "SSTOPOI", "SSRNAPOL", "SSU3RNP", "SSNOR_90"]
SLE = {"SSSM": "Sm", "SSU1RNP": "U1-RNP", "SSROSSA": "Ro/SSA", "SSLASSB": "La/SSB"}


def main():
    P0 = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = build_v3(P0, verbose=False, fixes=True)
    kd, feats = V["cohort"].copy(), V["features"]
    assert not any(f.startswith("SS") for f in feats), "SS* 不可作特徵"
    ana = kd["in_ana_subsample"].fillna(False).astype(bool)
    kd["imm3"] = np.select([ana & (kd["SSTOT"] >= 3), ana & (kd["SSTOT"] < 3)], [1.0, 0.0], np.nan)
    d = kd[kd["imm3"].notna()].reset_index(drop=True)
    assert set(d["cycle"]) <= {"1999-2000", "2001-2002", "2003-2004"}
    assert d.loc[d["imm3"] == 0, SPECIFIC].isna().all().all(), "特異抗體應只在 ANA 陽性者檢驗"
    spec = dict(label="imm3", adjacent=LABEL_ADJACENT["immune"])
    s = sets_for(feats, spec)
    X, y = d[s["full"]].to_numpy(float), d["imm3"].to_numpy(int)
    sets = {k: [s["full"].index(f) for f in v] for k, v in s.items()}
    P = nested(X, y, sets, MODELS)
    insufficient = d[s["routine"]].notna().mean(axis=1).to_numpy() < 0.5
    m1, p_m1 = demographics(X, y, sets)
    pos = d[d["imm3"] == 1]
    out = dict(created=pd.Timestamp.now().isoformat(timespec="seconds"), plan=os.path.relpath(PLAN, ROOT),
               plan_sha256=hashlib.sha256(open(PLAN, "rb").read()).hexdigest(), seed=SEED,
               label="imm3＝SSTOT≥3（ANA 1:80 稀釋 3+／4+）", n=int(len(y)), n_pos=int(y.sum()), prevalence=float(y.mean()),
               by_cycle={c: dict(n=int((d.cycle == c).sum()), n_pos=int(((d.cycle == c) & (d.imm3 == 1)).sum()))
                         for c in sorted(d["cycle"].unique())},
               by_sex={("男" if k == 1 else "女"): dict(n=int((d.sex == k).sum()), n_pos=int(((d.sex == k) & (d.imm3 == 1)).sum()))
                       for k in (1, 2)},
               sle_antibodies_among_pos={v: int((pos[k] == 1).sum()) for k, v in SLE.items()},
               any_specific_among_pos=int((pos[SPECIFIC] == 1).any(axis=1).sum()),
               features=s["full"], routine_panel=s["routine"],
               models={m: summarize(y, P[m], insufficient) for m in MODELS}, M1_demographics=m1,
               paired_repeat0={f"{a}−{b}": paired(y, P[a]["cal"][0], P[b]["cal"][0]) for a, b in PAIRS},
               paired_vs_demographics_repeat0={f"{m}−M1_demographics": paired_auroc(y, P[m]["cal"][0], p_m1) for m in MAIN},
               decision_curve={m: dca(pd.DataFrame(dict(repeat=0, y=y, cal=P[m]["cal"][0])), GRID) for m in MAIN})
    pv = out["paired_vs_demographics_repeat0"]["LR_routine−M1_demographics"]
    out["decision"] = "可回推" if pv["d_auroc"] > 0 and pv["ci95"]["d_auroc"][0] > 0 else "無法可靠回推"
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    with open(os.path.join(ROOT, "results", "runs_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(kind="immune_v3_2", created=out["created"], plan_sha256=out["plan_sha256"], n=out["n"],
                                n_pos=out["n_pos"], auroc={m: out["models"][m]["repeats"]["mean"]["auroc"] for m in MODELS},
                                decision=out["decision"]), ensure_ascii=False) + "\n")
    print(f"[存檔] {OUT}")
    print(f"[免疫] n={out['n']}（陽性 {out['n_pos']}，{out['prevalence']:.1%}）｜年齡性別 AUROC {m1['auroc_mean']:.3f}")
    for m in MODELS:
        sm = out["models"][m]
        print(f"  {m}: AUROC {sm['repeats']['mean']['auroc']:.3f}｜截距 {sm['calibration_repeat0']['intercept']:+.3f}"
              f" 斜率 {sm['calibration_repeat0']['slope']:.3f}")
    print(f"  LR_routine−年齡性別 ΔAUROC {pv['d_auroc']:+.3f}（95% CI {pv['ci95']['d_auroc'][0]:+.3f}～{pv['ci95']['d_auroc'][1]:+.3f}）→ {out['decision']}")


if __name__ == "__main__":
    main()
