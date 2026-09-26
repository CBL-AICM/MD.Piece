# -*- coding: utf-8 -*-
"""外部確認：NHANES 2021–2023（週期 L，從未參與任何開發決策）——先凍結、後取用、只評一次。

    python external_validation_2021.py --freeze     # 1) 訓練 HGB 比較模型、寫入協定與所有模型雜湊（已執行並提交）
    python external_validation_2021.py --download   # 2) 需使用者明確同意：自 CDC 下載 17 個公開檔（約 12.5 MB）
    python external_validation_2021.py --evaluate   # 3) 驗證雜湊 → 建立同規則樣本 → 一次性評估；結果已存在則拒跑

規則與 v3 完全相同（nhanes_cohort.labels_v3、direction.predict_matrix）；不重新配適、不重新校準、不改門檻。
2021–2023 血清肌酸酐為酵素法、尿肌酸酐為 Roche 法，官方不需轉換。
"""
import hashlib
import json
import os
import pickle
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                                     # noqa: E402
import pandas as pd                                                    # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score    # noqa: E402

PROTO = os.path.join(ROOT, "params", "external_validation_protocol.json")
OUT = os.path.join(ROOT, "results", "external_2021_2023.json")
HGB_PKL = os.path.join(ROOT, "models", "v3_hgb.pkl")
MODELS = {"v3_full_LR（部署）": os.path.join(ROOT, "params", "direction_model.json"),
          "v3_basic_LR（常規套組候選）": os.path.join(ROOT, "params", "direction_model_basic.json")}
CYC = {"2021-2023": dict(demo="DEMO_L.xpt", biochem="BIOPRO_L.xpt", cbc="CBC_L.xpt", acr="ALB_CR_L.xpt",
                         hba1c="GHB_L.xpt", diq="DIQ_L.xpt", hepb="HEPBD_L.xpt", hepc="HEPC_L.xpt", crp="HSCRP_L.xpt")}
EXTRA = {"2021-2023": ["TCHOL_L.xpt", "HDL_L.xpt", "TRIGLY_L.xpt", "PBCD_L.xpt", "FERTIN_L.xpt",
                       "FOLATE_L.xpt", "VID_L.xpt", "COT_L.xpt"]}
URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/{}"
BYTES = {"DEMO_L": 2582160, "DIQ_L": 847600, "ALB_CR_L": 545440, "BIOPRO_L": 2425520, "CBC_L": 1609840,
         "GHB_L": 174000, "HEPBD_L": 324160, "HEPC_L": 324160, "TCHOL_L": 259520, "HDL_L": 259520,
         "TRIGLY_L": 321840, "HSCRP_L": 280560, "PBCD_L": 1190000, "FERTIN_L": 83360, "FOLATE_L": 280560,
         "VID_L": 700320, "COT_L": 341200}   # 2026-09-26 以 HTTP HEAD 取得（未下載）


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def files():
    return [f for c in CYC.values() for f in c.values()] + [f for fs in EXTRA.values() for f in fs]


def freeze():
    from direction import AXES
    from evaluate_v3 import hgb
    from nhanes_cohort import build_v3
    man = json.load(open(os.path.join(ROOT, "params", "manifest.json"), encoding="utf-8"))
    assert not any(k.endswith("_L.xpt") for k in man.get("files", {})), "帳本已有 2021–2023 檔——不再是未取用資料"
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = build_v3(P, verbose=False)
    kd = V["cohort"]
    full = json.load(open(MODELS["v3_full_LR（部署）"], encoding="utf-8"))
    hg = {}
    for name, spec in AXES.items():
        ff = full["axes"][name]["features"]
        d = kd[kd[spec["label"]].notna()]
        hg[name] = dict(features=ff, model=hgb(20260926).fit(d[ff].to_numpy(float), d[spec["label"]].astype(int).to_numpy()))
    os.makedirs(os.path.dirname(HGB_PKL), exist_ok=True)
    pickle.dump(hg, open(HGB_PKL, "wb"))
    proto = dict(
        title="外部確認協定：NHANES 2021–2023（週期 L）",
        frozen_at=pd.Timestamp.now().isoformat(timespec="seconds"),
        why_new="週期 L 於 2024 年釋出；本專案帳本 params/manifest.json 在凍結時沒有任何 *_L 檔，未參與任何模型、特徵、門檻或規則決策",
        frozen_models={**{k: dict(path=os.path.relpath(p, ROOT), sha256=sha(p)) for k, p in MODELS.items()},
                       "v3_full_HGB（比較，僅判別）": dict(path=os.path.relpath(HGB_PKL, ROOT), sha256=sha(HGB_PKL))},
        data_files=[dict(file=f, url=URL.format(f), bytes=BYTES[f[:-4]]) for f in files()],
        total_bytes=int(sum(BYTES.values())),
        cohort_rules="與 v3 相同：成人 ≥20、labels_v3 三值、各軸排除未知；不做肌酸酐或尿肌酸酐轉換（官方方法已一致）",
        primary=dict(model="v3_full_LR（部署）", metrics=["AP 與 AUROC（受試者層 bootstrap 1,000 次 95% CI）",
                                                     "校準截距、斜率、Brier", "勝算分區六格表、涵蓋率、各區實際陽性率、資料不足人數"]),
        secondary=["v3_basic_LR：與部署模型之配對 ΔAUROC、ΔAP", "v3_full_HGB：判別（AUROC、AP）", "舊分區規則（2×／0.5× 盛行率）", "MEC 權重加權指標"],
        rules=["只評一次；結果已存在則程式拒跑", "不重新配適、不重新校準、不改門檻", "無論結果如何皆完整報告",
               "不設通過／不通過門檻；內部參考值（巢狀外層）：肝炎 AUROC 0.783、AP 0.116；糖尿病 AUROC 0.765、AP 0.641"],
        internal_reference=os.path.relpath(os.path.join(ROOT, "results", "v3_eval.json"), ROOT))
    json.dump(proto, open(PROTO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[凍結] {PROTO}\n  模型雜湊：" + "；".join(f"{k} {v['sha256'][:12]}" for k, v in proto["frozen_models"].items()))
    print(f"  待取用資料 {len(proto['data_files'])} 檔、{proto['total_bytes']/1e6:.1f} MB——下載前須取得使用者同意")


def download():
    from fetch_data import fetch
    for f in files():
        fetch(f, URL.format(f))


def evaluate():
    from direction import AXES, predict_matrix
    from evaluate_v3 import band_stats, bands, boot, calib
    from nhanes_cohort import egfr_ckdepi2021, labels_v3, load_extended
    assert not os.path.exists(OUT), f"{OUT} 已存在——協定規定只評一次"
    proto = json.load(open(PROTO, encoding="utf-8"))
    for k, v in proto["frozen_models"].items():
        assert sha(os.path.join(ROOT, v["path"])) == v["sha256"], f"{k} 雜湊不符——模型在凍結後被改動"
    df = load_extended(verbose=True, cycles=CYC, extra=EXTRA)
    df = df[df["age"] >= 20].copy()
    df["eGFR"] = egfr_ckdepi2021(df["LBXSCR"].to_numpy(float), df["age"].to_numpy(float), (df["sex"] == 2).to_numpy())
    df["ACR"] = df["URXUMA"] / (df["URXUCR"] / 100.0)
    df["NLR"] = df["LBXNEPCT"] / df["LBXLYPCT"].replace(0, np.nan)
    labels_v3(df)
    kd = df[df["kidney3"] == 1]
    out = dict(protocol_sha256=sha(PROTO), evaluated_at=pd.Timestamp.now().isoformat(timespec="seconds"),
               n_adults=int(len(df)), kidney=dict(pos=int((df.kidney3 == 1).sum()), neg=int((df.kidney3 == 0).sum()),
                                                   unknown=int(df.kidney3.isna().sum())), axes={})
    hg = pickle.load(open(HGB_PKL, "rb"))
    Ms = {k: json.load(open(p, encoding="utf-8")) for k, p in MODELS.items()}
    for name, spec in AXES.items():
        d = kd[kd[spec["label"]].notna()]
        y = d[spec["label"]].astype(int).to_numpy()
        res = dict(n=int(len(y)), n_pos=int(y.sum()), prevalence=float(y.mean()), models={})
        preds = {}
        for mk, M in Ms.items():
            a = M["axes"][name]
            X = np.column_stack([d[f].to_numpy(float) if f in d.columns else np.full(len(d), np.nan) for f in a["features"]])
            raw, cal, band = predict_matrix(a, X)
            preds[mk] = cal
            ok = band >= 0
            res["models"][mk] = dict(
                auroc=float(roc_auc_score(y, cal)), ap=float(average_precision_score(y, cal)),
                ci95=boot(y, dict(auroc=lambda i, c=cal: roc_auc_score(y[i], c[i]),
                                  ap=lambda i, c=cal: average_precision_score(y[i], c[i]))),
                calibration=calib(y, cal), insufficient_data_n=int((~ok).sum()),
                features_absent_in_2021=[f for f in a["features"] if f not in d.columns or d[f].isna().all()],
                bands_B=band_stats(y[ok], band[ok]), bands_A=band_stats(y, bands(cal, a["prevalence"], "A")))
        h = hg[name]
        ph = h["model"].predict_proba(np.column_stack([d[f].to_numpy(float) if f in d.columns else np.full(len(d), np.nan)
                                                       for f in h["features"]]))[:, 1]
        res["models"]["v3_full_HGB（比較，僅判別）"] = dict(auroc=float(roc_auc_score(y, ph)), ap=float(average_precision_score(y, ph)))
        a0, b0 = preds["v3_full_LR（部署）"], preds["v3_basic_LR（常規套組候選）"]
        res["basic_minus_full"] = boot(y, dict(d_auroc=lambda i: roc_auc_score(y[i], b0[i]) - roc_auc_score(y[i], a0[i]),
                                               d_ap=lambda i: average_precision_score(y[i], b0[i]) - average_precision_score(y[i], a0[i])))
        w = d["WTMEC2YR"].to_numpy(float) if "WTMEC2YR" in d.columns else None
        if w is not None and np.isfinite(w).all():
            res["weighted_full"] = dict(prevalence=float(np.average(y, weights=w)), mean_pred=float(np.average(a0, weights=w)),
                                        auroc=float(roc_auc_score(y, a0, sample_weight=w)))
        out["axes"][name] = res
        m = res["models"]["v3_full_LR（部署）"]
        print(f"[{name}] n={res['n']:,} 陽性 {res['n_pos']}｜AUROC {m['auroc']:.3f} {m['ci95']['auroc']}｜AP {m['ap']:.3f}"
              f"｜截距 {m['calibration']['intercept']:.2f} 斜率 {m['calibration']['slope']:.2f}")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[存檔] {OUT}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    {"--freeze": freeze, "--download": download, "--evaluate": evaluate}.get(arg, lambda: print(__doc__))()
