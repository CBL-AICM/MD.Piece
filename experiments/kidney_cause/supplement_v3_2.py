# -*- coding: utf-8 -*-
"""v3.2 補充分析（研究論文 v3.2 與審查回應表用）——v3 有、v3.2 計畫（f6abc91）未列之項目，
依 v3 計畫（bf269c5）之定義在 v3.2 修正後資料重跑；本程式先提交、後執行。
    python supplement_v3_2.py → results/v3_2_supplement.json

1. 描述性計數：腎臟未知之分解、兩標籤及其組成、兩標籤交叉表（同 audit_v3.py）
2. 近端特徵消融：全特徵邏輯迴歸含 vs 不含近端特徵，第 0 次切分之配對差（同 evaluate_v3.ablation_adjacent）
3. 時間外推之擴展視窗：網頁工具模型族（常規套組邏輯迴歸）；每一評估週期只用更早週期訓練（同 evaluate_v3.temporal）
4. 糖尿病標籤定義敏感度：僅問卷、僅 HbA1c、排除邊緣回答（常規套組邏輯迴歸 1 次重複，同 evaluate_v3_2.single，
   與 v3.2 肝炎單一標籤分析同一模型）
5. 梯形 PR-AUC：由 results/v3_2_oof.csv.gz 重算（五次重複）"""
import json
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd                                                   # noqa: E402

from evaluate_v3 import AXES, ablation_adjacent, axis_data, prauc_trapz, temporal  # noqa: E402
from evaluate_v3_2 import single                                      # noqa: E402
from nhanes_cohort import build_v3                                    # noqa: E402

OUT = os.path.join(ROOT, "results", "v3_2_supplement.json")
tri = lambda s: dict(pos=int((s == 1).sum()), neg=int((s == 0).sum()), unknown=int(s.isna().sum()))


def counts(V):
    df, kd = V["adults"], V["cohort"]
    lab = lambda s: s.map({1.0: "陽性", 0.0: "陰性"}).fillna("未知")
    ct = pd.crosstab(lab(kd["hep3"]), lab(kd["dm3"]))
    return dict(adults=int(len(df)), kidney=tri(df["kidney3"]),
                kidney_unknown_one_normal_one_missing=int((df["kidney3"].isna() & (df["eGFR"].notna() | df["ACR"].notna())).sum()),
                kidney_unknown_both_missing=int((df["eGFR"].isna() & df["ACR"].isna()).sum()),
                **{f"{k}_in_kidney": tri(kd[c]) for k, c in (("hep", "hep3"), ("hbv", "hbv3"), ("hcv", "hcv3"),
                                                             ("dm", "dm3"), ("dmq", "dmq3"), ("dma", "dma3"))},
                both_hbv_and_hcv=int(((kd["hbv3"] == 1) & (kd["hcv3"] == 1)).sum()),
                two_label_crosstab_in_kidney={r: {c: int(ct.loc[r, c]) for c in ct.columns} for r in ct.index})


def main():
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = build_v3(P, verbose=False, fixes=True)
    kd, feats = V["cohort"], V["features"]
    EV = json.load(open(os.path.join(ROOT, "results", "v3_2_eval.json"), encoding="utf-8"))["axes"]
    oof = pd.read_csv(os.path.join(ROOT, "results", "v3_2_oof.csv.gz"))
    out = dict(created=pd.Timestamp.now().isoformat(timespec="seconds"),
               basis="v3 計畫（bf269c5）之定義於 v3.2 修正後資料重跑；非 v3.2 計畫（f6abc91）所列，於 v3.2 結果之後執行",
               counts=counts(V), axes={})
    for name, spec in AXES.items():
        d, ff, basic, y = axis_data(kd, feats, spec)
        assert len(y) == EV[name]["n"] and int(y.sum()) == EV[name]["n_pos"], f"{name}：樣本與 v3.2 評估不同"
        a = dict(ablation_adjacent=ablation_adjacent(kd, feats, spec, y, d))
        t = temporal(d, basic, y)
        assert abs(t["early_to_late"]["auroc"] - EV[name]["temporal"]["LR_routine"]["auroc"]) < 1e-9, f"{name}：時間外推與 v3.2 評估不一致"
        a["expanding_window_LR_routine"] = t["expanding_window"]
        g = oof[oof["axis"] == name]
        a["prauc_trapz"] = {}
        for m, gm in g.groupby("model"):
            v = [prauc_trapz(gr["y"].to_numpy(), gr["cal"].to_numpy()) for _, gr in gm.groupby("repeat")]
            a["prauc_trapz"][m] = dict(mean=float(sum(v) / len(v)), min=float(min(v)), max=float(max(v)), n_repeats=len(v))
        out["axes"][name] = a
        print(f"[{name}] 消融 {a['ablation_adjacent']['auroc_with']:.3f}→{a['ablation_adjacent']['auroc_without']:.3f}｜擴展視窗 "
              + "、".join(f"{c} {r.get('auroc', float('nan')):.3f}" for c, r in t["expanding_window"].items()), flush=True)
    dm = AXES["糖尿病"]
    out["axes"]["糖尿病"]["label_sensitivity_LR_routine"] = {
        "僅問卷_DIQ010": single(kd, feats, dm, "dmq3"),
        "僅HbA1c": single(kd, feats, dm, "dma3"),
        "排除邊緣_DIQ010=3": single(kd[kd["DIQ010"] != 3], feats, dm, "dm3")}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print(f"[存檔] {OUT}")
    for k, r in out["axes"]["糖尿病"]["label_sensitivity_LR_routine"].items():
        print(f"  [糖尿病｜{k}] n={r['n']:,} 陽性 {r['n_pos']:,}｜AUROC {r['auroc']:.3f}｜AP {r['ap']:.3f}")
    print("  計數", json.dumps(out["counts"], ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
