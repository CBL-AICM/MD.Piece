# -*- coding: utf-8 -*-
"""外部確認：NHANES 2021–2023（週期 L，從未參與任何開發決策）——先凍結、後取用、只評一次。

    python external_validation_2021.py --freeze     # 1) 訓練 HGB 比較模型、寫入協定與所有模型雜湊（已執行並提交）
    python external_validation_2021.py --download   # 2) 需使用者明確同意：自 CDC 下載 17 個公開檔（約 12.5 MB）
    python external_validation_2021.py --precheck   # 3) 取用後、評估前：只看變數分布與標籤計數，不算任何預測
    python external_validation_2021.py --amend      # 4) 寫入修正一（量尺調和）；須在評估前提交
    python external_validation_2021.py --evaluate   # 5) 驗證雜湊 → 建立同規則樣本 → 一次性評估；結果已存在則拒跑

規則與 v3 完全相同（nhanes_cohort.labels_v3、direction.predict_matrix）；不重新配適、不重新校準、不改門檻。
修正一（2026-09-27，評估前）：2021–2023 更換生化儀器（Cobas 6000→8000），尿白蛋白改用 LC-MS/MS，
空腹三酸甘油酯改為非甘油空白法並更名。依 CDC 文件之官方回推式把數值換回 2017–2020 量尺（主要分析）；
依凍結程式原樣、不調和的結果列為事前指定的敏感度分析。
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
AMEND = os.path.join(ROOT, "params", "external_validation_amendment_1.json")
PRECHECK = os.path.join(ROOT, "results", "external_2021_2023_precheck.json")
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

# ── 修正一：CDC 2021–2023 文件之官方回推式（新值 → 2017–March 2020 量尺）：舊 = a + b × 新
BACKWARD = {
    "LBXSAPSI": (0.6098, 0.9041, "BIOPRO_L"), "LBXSATSI": (-1.529, 1.035, "BIOPRO_L"),
    "LBXSBU": (0.09386, 1.021, "BIOPRO_L"), "LBXSC3SI": (1.37, 1.022, "BIOPRO_L"),
    "LBXSCLSI": (9.137, 0.919, "BIOPRO_L"), "LBXSGL": (-0.7821, 0.9669, "BIOPRO_L"),
    "LBXSGTSI": (0.9735, 0.9444, "BIOPRO_L"), "LBXSIR": (-1.679, 0.9918, "BIOPRO_L"),
    "LBXSKSI": (0.2108, 0.923, "BIOPRO_L"), "LBXSLDSI": (2.46, 0.979, "BIOPRO_L"),
    "LBXSNASI": (41.95, 0.6983, "BIOPRO_L"), "LBXSTB": (0.01793, 1.012, "BIOPRO_L"),
    "LBXSTR": (-0.8463, 0.9879, "BIOPRO_L"),
    "LBXTR": (-12.19, 0.9785, "TRIGLY_L"),       # 新儀器＋非甘油空白法；2021–2023 原名 LBXTLG
    "URXUMA": (-1.643, 1.189, "ALB_CR_L"),       # LC-MS/MS → 螢光免疫法（影響 ACR 與腎臟標籤）
}
RENAME = {"LBXTLG": "LBXTR", "LBXVIDMS": "LBDVIDMS"}   # 同一分析物更名（維生素 D 兩者皆為 LC-MS/MS 等值）
NOT_CONVERTED = {
    "LBXSCR、LBXSAL、LBXSASSI、LBXSCA、LBXSCH、LBXSPH、LBXSTP、LBXSUA": "BIOPRO_L：Adjustment Not Recommended",
    "LBXSGB": "計算值（總蛋白－白蛋白），兩者皆不需調整",
    "URXUCR": "ALB_CR_L：no adjustment is recommended",
    "LBXGH": "GHB_L：did not have to be adjusted（糖尿病標籤不受影響）",
    "LBXTC": "TCHOL_L：did not have to be adjusted",
    "CBC 全部": "CBC_L：no changes to the lab method, lab equipment, or lab site",
    "LBDHBG、LBXHCR": "HEPBD_L 無變更；HEPC_L 代碼 1／2／3 與 2013 年起相同",
    "LBXFER": "FERTIN_L：no changes",
    "LBXBPB、LBXBCD、LBXTHG": "PBCD_L 方法有變但未提供換算式 → 依凍結協定用原值",
    "LBXCOT": "COT_L 未提供換算式 → 依凍結協定用原值",
    "LBDRFO（紅血球葉酸）": "開發資料之 LBXRBF 為 1999–2004 放射免疫法，2021–2023 為微生物法，無一對一換算 → 不對應（同開發資料 2005–2018 缺值）",
    "LBXHSCRP": "開發資料未合併高敏感度 CRP（2011–2018 同樣缺值）→ 不對應",
    "LBDHDD（HDL）": "不是模型特徵（開發時被 D 肝變數字首規則一併封存，另列版本紀錄）",
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def files():
    return [f for c in CYC.values() for f in c.values()] + [f for fs in EXTRA.values() for f in fs]


def harmonize(df):
    """修正一：官方回推式，再以組成的變化量修正儀器計算值。回推值 <0 設為 0（只在量測下限附近發生）。"""
    raw = df[["LBXSNASI", "LBXSGL", "LBXSBU", "LBXTR"]].copy()
    for c, (a, b, _) in BACKWARD.items():
        df[c] = (a + b * df[c]).clip(lower=0)
    # 滲透壓為儀器計算值 1.86×Na＋GLU/18＋BUN/2.8＋9（BIOPRO_L）
    dosm = 1.86 * (df["LBXSNASI"] - raw["LBXSNASI"]) + (df["LBXSGL"] - raw["LBXSGL"]) / 18 + (df["LBXSBU"] - raw["LBXSBU"]) / 2.8
    df["LBXSOSSI"] = df["LBXSOSSI"] + dosm.fillna(0)
    # Friedewald LDL＝TC－HDL－TG/5（TRIGLY_L）
    df["LBDLDL"] = df["LBDLDL"] + ((raw["LBXTR"] - df["LBXTR"]) / 5).fillna(0)
    return df


def load_2021(harmonized=True):
    """與開發資料同規則建立 2021–2023 成人資料與三值標籤；harmonized=False 即凍結程式原樣。"""
    import nhanes_cohort as nc
    saved = dict(nc.ALIASES)
    if harmonized:
        nc.ALIASES.update(RENAME)          # ponytail: 借用讀檔的別名機制，只在這次讀取期間生效
    try:
        df = nc.load_extended(verbose=False, cycles=CYC, extra=EXTRA)
    finally:
        nc.ALIASES.clear()
        nc.ALIASES.update(saved)
    df = df[df["age"] >= 20].copy()
    if harmonized:
        df = harmonize(df)
    df["eGFR"] = nc.egfr_ckdepi2021(df["LBXSCR"].to_numpy(float), df["age"].to_numpy(float), (df["sex"] == 2).to_numpy())
    df["ACR"] = df["URXUMA"] / (df["URXUCR"] / 100.0)
    df["NLR"] = df["LBXNEPCT"] / df["LBXLYPCT"].replace(0, np.nan)
    return nc.labels_v3(df)


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


def precheck():
    """取用後、評估前的資料核對：兩種資料版本的標籤計數與特徵分布（有值比例、中位數對開發中位數）。
    不載入模型預測、不計算任何判別或校準指標。"""
    assert not os.path.exists(OUT), "已評估——核對應在評估前"
    from direction import AXES
    M = json.load(open(MODELS["v3_full_LR（部署）"], encoding="utf-8"))
    dev = {}
    for a in M["axes"].values():
        for f, m in zip(a["features"], np.median([fp["medians"] for fp in a["ensemble"]], axis=0)):
            dev.setdefault(f, float(m))
    cnt = lambda s: dict(pos=int((s == 1).sum()), neg=int((s == 0).sum()), unknown=int(s.isna().sum()))
    out = dict(note="只含標籤計數與特徵分布；未計算任何預測、判別或校準指標", versions={})
    for tag, harm in (("調和（修正一）", True), ("依凍結程式", False)):
        df = load_2021(harm)
        kd = df[df["kidney3"] == 1]
        feats = {}
        for f, m in dev.items():
            x = kd[f] if f in kd.columns else pd.Series(np.nan, index=kd.index)
            med = float(x.median()) if x.notna().any() else None
            feats[f] = dict(present=round(float(x.notna().mean()), 3), median_2021=med, median_dev=m,
                            ratio=round(med / m, 3) if med is not None and m else None)
        out["versions"][tag] = dict(n_adults=int(len(df)), kidney=cnt(df["kidney3"]),
                                    labels={ax: cnt(kd[s["label"]]) for ax, s in AXES.items()}, features=feats)
        absent = [f for f, v in feats.items() if v["present"] == 0]
        odd = {f: v["ratio"] for f, v in feats.items() if v["ratio"] is not None and not 0.67 <= v["ratio"] <= 1.5}
        print(f"[{tag}] 成人 {len(df):,}｜腎臟 {out['versions'][tag]['kidney']}｜"
              + "｜".join(f"{ax} {v}" for ax, v in out["versions"][tag]["labels"].items()))
        print(f"   全缺特徵 {len(absent)}：{absent}")
        print(f"   中位數對開發比值在 0.67–1.5 之外：{odd}")
    json.dump(out, open(PRECHECK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[存檔] {PRECHECK}")


def amend():
    assert not os.path.exists(OUT), "已評估——修正必須在評估前"
    assert os.path.exists(PRECHECK), "先執行 --precheck"
    doc = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/{}.htm"
    a = dict(
        title="外部確認協定修正一：2021–2023 資料與開發資料之量尺調和",
        amended_at=pd.Timestamp.now().isoformat(timespec="seconds"),
        base_protocol=dict(path=os.path.relpath(PROTO, ROOT), sha256=sha(PROTO)),
        status_at_amendment="17 檔已下載並核對大小；已做資料核對（標籤計數與特徵分布）；尚未計算任何預測、判別或校準指標",
        why="凍結時只核對血清與尿肌酸酐（官方不需轉換）。取用後逐檔核對 CDC 文件：2021–2023 生化儀器由 Cobas 6000 換為 8000，"
            "尿白蛋白由螢光免疫法改為 LC-MS/MS，空腹三酸甘油酯改為非甘油空白法並更名 LBXTLG，維生素 D 更名 LBXVIDMS；"
            "CDC 對需調整者提供回推至 2017–March 2020 量尺之官方式。不調和則部分特徵與腎臟標籤（ACR）不在開發時的量尺上，"
            "且兩個更名的特徵會被整欄以中位數補入。",
        rule="凡 CDC 2021–2023 文件建議用於與 2017–March 2020 比較之回推式，對模型或標籤用到的變數一律套用；"
             "儀器計算值（滲透壓、Friedewald LDL）與 ACR 以文件公式由調整後組成重算；同一分析物更名者對應回原名；其餘不動。",
        conversions={c: dict(equation=f"舊 = {a_:g} + {b_:g} × 新", source=doc.format(src)) for c, (a_, b_, src) in BACKWARD.items()},
        renames={k: v for k, v in RENAME.items()},
        derived=["LBXSOSSI：加上 1.86×ΔNa＋ΔGLU/18＋ΔBUN/2.8", "LBDLDL：加上 −ΔTG/5", "ACR：以調整後尿白蛋白重算"],
        floor="回推值 <0 設為 0（只在各檢驗量測下限附近發生）",
        not_converted=NOT_CONVERTED,
        unchanged=["模型、校準、門檻、分區規則", "主要與次要指標", "只評一次、結果不論好壞完整報告"],
        analyses=dict(primary="調和後資料（本修正）", sensitivity_prespecified="依凍結程式原樣（不調和），顯示調和的影響"),
        precheck=dict(path=os.path.relpath(PRECHECK, ROOT), sha256=sha(PRECHECK)))
    json.dump(a, open(AMEND, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[修正一] {AMEND}（sha256 {sha(AMEND)[:12]}）——提交後才可評估")


def eval_axes(df):
    """一個資料版本的全部事前指定指標；不列印（全部算完、存檔後才列印，避免中途失敗時先看到部分結果）。"""
    from direction import AXES, predict_matrix
    from evaluate_v3 import band_stats, bands, boot, calib
    kd = df[df["kidney3"] == 1]
    res_all = dict(n_adults=int(len(df)), kidney=dict(pos=int((df.kidney3 == 1).sum()), neg=int((df.kidney3 == 0).sum()),
                                                        unknown=int(df.kidney3.isna().sum())), axes={})
    hg = pickle.load(open(HGB_PKL, "rb"))
    Ms = {k: json.load(open(p, encoding="utf-8")) for k, p in MODELS.items()}
    col = lambda d, f: d[f].to_numpy(float) if f in d.columns else np.full(len(d), np.nan)
    for name, spec in AXES.items():
        d = kd[kd[spec["label"]].notna()]
        y = d[spec["label"]].astype(int).to_numpy()
        res = dict(n=int(len(y)), n_pos=int(y.sum()), prevalence=float(y.mean()), models={})
        preds = {}
        for mk, M in Ms.items():
            a = M["axes"][name]
            raw, cal, band = predict_matrix(a, np.column_stack([col(d, f) for f in a["features"]]))
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
        ph = h["model"].predict_proba(np.column_stack([col(d, f) for f in h["features"]]))[:, 1]
        res["models"]["v3_full_HGB（比較，僅判別）"] = dict(auroc=float(roc_auc_score(y, ph)), ap=float(average_precision_score(y, ph)))
        a0, b0 = preds["v3_full_LR（部署）"], preds["v3_basic_LR（常規套組候選）"]
        res["basic_minus_full"] = boot(y, dict(d_auroc=lambda i: roc_auc_score(y[i], b0[i]) - roc_auc_score(y[i], a0[i]),
                                               d_ap=lambda i: average_precision_score(y[i], b0[i]) - average_precision_score(y[i], a0[i])))
        w = d["WTMEC2YR"].to_numpy(float) if "WTMEC2YR" in d.columns else None
        if w is not None and np.isfinite(w).all():
            res["weighted_full"] = dict(prevalence=float(np.average(y, weights=w)), mean_pred=float(np.average(a0, weights=w)),
                                        auroc=float(roc_auc_score(y, a0, sample_weight=w)))
        res_all["axes"][name] = res
    return res_all


def evaluate():
    assert not os.path.exists(OUT), f"{OUT} 已存在——協定規定只評一次"
    assert os.path.exists(AMEND), "修正一尚未寫入——須於評估前以 --amend 寫入並提交"
    proto = json.load(open(PROTO, encoding="utf-8"))
    for k, v in proto["frozen_models"].items():
        assert sha(os.path.join(ROOT, v["path"])) == v["sha256"], f"{k} 雜湊不符——模型在凍結後被改動"
    am = json.load(open(AMEND, encoding="utf-8"))
    assert am["base_protocol"]["sha256"] == sha(PROTO), "協定在修正一之後被改動"
    out = dict(protocol_sha256=sha(PROTO), amendment_sha256=sha(AMEND),
               evaluated_at=pd.Timestamp.now().isoformat(timespec="seconds"),
               primary=dict(description="修正一：CDC 官方回推式調和後（主要分析）", **eval_axes(load_2021(True))),
               sensitivity_as_frozen=dict(description="依凍結程式原樣、不調和（事前指定敏感度分析）", **eval_axes(load_2021(False))))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[存檔] {OUT}")
    for part in ("primary", "sensitivity_as_frozen"):
        print(f"── {out[part]['description']}｜腎臟 {out[part]['kidney']}")
        for name, res in out[part]["axes"].items():
            m = res["models"]["v3_full_LR（部署）"]
            print(f"  [{name}] n={res['n']:,} 陽性 {res['n_pos']}｜AUROC {m['auroc']:.3f} {m['ci95']['auroc']}｜AP {m['ap']:.3f}"
                  f"｜截距 {m['calibration']['intercept']:.2f} 斜率 {m['calibration']['slope']:.2f}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    {"--freeze": freeze, "--download": download, "--precheck": precheck, "--amend": amend,
     "--evaluate": evaluate}.get(arg, lambda: print(__doc__))()
