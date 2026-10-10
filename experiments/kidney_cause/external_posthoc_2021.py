# -*- coding: utf-8 -*-
"""外部確認之事後探索（2026-09-27，於一次性評估之後撰寫；不取代主要結果，不改任何模型）。
    python external_posthoc_2021.py      → results/external_2021_2023_posthoc.json

問題：外部資料上，部署模型（全特徵）在糖尿病軸的 AUROC 低於常規套組模型。是否因為部分非常規特徵
（血中金屬、可丁尼、鐵蛋白、維生素 D）在開發資料只有 1999–2004 年有值、到 2021–2023 又有明顯年代位移？
做法：同一批人、同一部署模型，把「全特徵模型有、常規套組模型沒有、且 2021–2023 有值」的特徵設為缺值
（＝開發資料中 2005–2018 受試者的處理方式），以配對 bootstrap 比較 AUROC。另列肝炎標籤陽性者的組成（僅計數）。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
import numpy as np                                         # noqa: E402
from sklearn.metrics import roc_auc_score                  # noqa: E402

import external_validation_2021 as ev                      # noqa: E402
from direction import AXES, predict_matrix                 # noqa: E402
from evaluate_v3 import boot, calib                        # noqa: E402

OUT = os.path.join(ROOT, "results", "external_2021_2023_posthoc.json")


def main():
    assert os.path.exists(ev.OUT), "事後探索只能在一次性評估之後"
    kd = ev.load_2021(True)
    kd = kd[kd["kidney3"] == 1]
    full = json.load(open(ev.MODELS["v3_full_LR（部署）"], encoding="utf-8"))["axes"]
    basic = json.load(open(ev.MODELS["v3_basic_LR（常規套組候選）"], encoding="utf-8"))["axes"]
    out = dict(note="事後探索：於一次性評估之後撰寫，不取代主要結果、不改模型", axes={})
    for name, spec in AXES.items():
        d = kd[kd[spec["label"]].notna()]
        y = d[spec["label"]].astype(int).to_numpy()
        a = full[name]
        X = np.column_stack([d[f].to_numpy(float) if f in d.columns else np.full(len(d), np.nan) for f in a["features"]])
        masked = [f for f in a["features"] if f not in basic[name]["features"] and f in d.columns and d[f].notna().any()]
        Xm = X.copy()
        Xm[:, [a["features"].index(f) for f in masked]] = np.nan
        p0, p1 = predict_matrix(a, X)[1], predict_matrix(a, Xm)[1]
        out["axes"][name] = dict(
            n=int(len(y)), n_pos=int(y.sum()), masked=masked,
            auroc_all_inputs=float(roc_auc_score(y, p0)), auroc_masked=float(roc_auc_score(y, p1)),
            delta_masked_minus_all=float(roc_auc_score(y, p1) - roc_auc_score(y, p0)),
            delta_ci95=boot(y, dict(d=lambda i: roc_auc_score(y[i], p1[i]) - roc_auc_score(y[i], p0[i])))["d"],
            calibration_masked=calib(y, p1))
        r = out["axes"][name]
        print(f"[{name}] 遮蔽 {masked}｜AUROC {r['auroc_all_inputs']:.3f} → {r['auroc_masked']:.3f}"
              f"（差 {r['delta_masked_minus_all']:+.3f}，95% CI {r['delta_ci95'][0]:+.3f} 至 {r['delta_ci95'][1]:+.3f}）")
    h = kd[kd["hep3"] == 1]
    out["hep_positive_composition"] = dict(n=int(len(h)), hbsag_pos=int((h["hbv3"] == 1).sum()), hcv_rna_pos=int((h["hcv3"] == 1).sum()))
    print(f"[肝炎陽性組成] {out['hep_positive_composition']}")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[存檔] {OUT}")


if __name__ == "__main__":
    main()
