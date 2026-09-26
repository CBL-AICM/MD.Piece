# -*- coding: utf-8 -*-
"""鉛、鎘的血尿比較與共同分母檢查（回應審查 §八.三、S1.4）。  python exwas_v3_checks.py

同一批人（血、尿皆有值且結果已知）、同一調整集（M3）、同一量尺（log2，OR 為濃度加倍）。
尿液三種寫法：原濃度、原濃度＋log2 尿肌酸酐共變數、肌酸酐比值；結果三種定義：
  腎臟異常（eGFR<60 或 ACR≥30，ACR 分母含尿肌酸酐）、僅 eGFR<60（與尿肌酸酐無共同分母）、僅 ACR≥30。
另報低於檢出極限（LC 碼＝1）的比例。輸出 results/exwas_v3_checks.json。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                                   # noqa: E402
import pandas as pd                                                  # noqa: E402

import exwas                                                         # noqa: E402
from exposure_cohort import _load_channel, build as build_exposure   # noqa: E402
from run_exwas import attach_race                                    # noqa: E402

M3 = exwas.ADJ_SETS["M3_＋糖尿病高血壓"]
METALS = [("鉛", "LBXBPB", "URXUPB", ("LBDBPBLC",), ("URDUPBLC",)),
          ("鎘", "LBXBCD", "URXUCD", ("LBDBCDLC",), ("URDUCDLC",))]


def per_doubling(df, col, outcome, adj):
    r = exwas._logit_or(df, col, outcome, adj, 20260926)
    if r is None:
        return None
    b, se = r["beta"] / r["sd_exposure"], r["se"] / r["sd_exposure"]
    return dict(n=r["n"], n_pos=r["n_pos"], OR_per_doubling=float(np.exp(b)),
                ci=[float(np.exp(b - 1.96 * se)), float(np.exp(b + 1.96 * se))], p=r["p_two_sided"])


def main():
    man = json.load(open(os.path.join(ROOT, "params", "manifest.json"), encoding="utf-8"))
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    df = build_exposure(P, verbose=False)["cohort"]
    df, _ = attach_race(df, man, False)
    lc_cols = {c for _, _, _, b, u in METALS for c in b + u}
    for ch in ("血金屬", "尿金屬"):
        f = _load_channel(man, ch, cols_filter=lambda c: c in lc_cols, verbose=False)
        if f is not None:
            f = f.drop_duplicates("SEQN")
            df = df.merge(f[[c for c in f.columns if c == "SEQN" or c not in df.columns]], on="SEQN", how="left")
    df["egfr_lt60"] = np.where(df["eGFR"].notna(), (df["eGFR"] < 60).astype(float), np.nan)
    df["acr_ge30"] = np.where(df["ACR"].notna(), (df["ACR"] >= 30).astype(float), np.nan)
    df["log2_ucr"] = np.log2(df["URXUCR"].where(df["URXUCR"] > 0))
    out = dict(note="同一批人、M3 調整、log2 量尺；OR＝濃度加倍", adjustment=M3, metals={})
    for zh, blood, urine, blc, ulc in METALS:
        d = df[df[blood].notna() & df[urine].notna() & df["URXUCR"].notna() & df["kidney_damage"].notna()].copy()
        d = d.dropna(subset=[c for c in M3 if c in d.columns])
        pos = lambda s: s.where(s > 0)
        d["b_log2"] = np.log2(pos(d[blood]))
        d["u_log2"] = np.log2(pos(d[urine]))
        d["uratio_log2"] = np.log2(pos(d[urine]) / (d["URXUCR"] / 100.0))
        lod = {c: float((d[c] == 1).mean()) for c in blc + ulc if c in d.columns}
        res = dict(n_both=int(len(d)), cycles=sorted(d["cycle"].unique().tolist()), below_lod_share=lod, models={})
        for oname in ("kidney_damage", "egfr_lt60", "acr_ge30"):
            res["models"][oname] = {
                "血中": per_doubling(d, "b_log2", oname, M3),
                "尿中_原濃度": per_doubling(d, "u_log2", oname, M3),
                "尿中_原濃度＋尿肌酸酐共變數": per_doubling(d, "u_log2", oname, M3 + ["log2_ucr"]),
                "尿中_肌酸酐比值": per_doubling(d, "uratio_log2", oname, M3)}
        out["metals"][zh] = res
        print(f"\n[{zh}] 同時有血、尿值 n={len(d):,}｜低於檢出極限比例 {lod}")
        for oname, mm in res["models"].items():
            print("   " + oname + "： " + "｜".join(
                f"{k} {v['OR_per_doubling']:.2f} [{v['ci'][0]:.2f},{v['ci'][1]:.2f}]" for k, v in mm.items() if v))
    json.dump(out, open(os.path.join(ROOT, "results", "exwas_v3_checks.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n[存檔] results/exwas_v3_checks.json")


if __name__ == "__main__":
    main()
