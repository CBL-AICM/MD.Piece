# -*- coding: utf-8 -*-
"""v3 資料與標籤稽核（2026-09-26，回應《深度審查與補強方案》§四、§六）。
    python audit_v3.py

1. 先以舊定義重建舊計數（8,983／169／3,183）——對不上就停，證明比較基準正確。
2. 逐週期：成人、SEQN 重複、肌酸酐／ACR 可用、腎臟 陽/陰/未知、兩標籤 陽/陰/未知與未知原因、各軸分母。
3. 校正前後重分類：1999-2000 血清肌酸酐公式更正、2007 前尿肌酸酐轉換，各自造成多少人跨越門檻。
4. 兩標籤交叉表（含未知）。
輸出 results/v3_audit.json。只讀資料、不訓練模型。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np                                             # noqa: E402
import pandas as pd                                            # noqa: E402
from nhanes_cohort import build_v3, egfr_ckdepi2021            # noqa: E402

OUT = os.path.join(ROOT, "results", "v3_audit.json")
OLD_SCR_9900 = (-0.184, 0.960)                                 # 舊碼誤用的 NHANES III 公式（僅供重建舊計數）


def tri(s):
    return dict(pos=int((s == 1).sum()), neg=int((s == 0).sum()), unknown=int(s.isna().sum()))


def main():
    P = json.load(open(os.path.join(ROOT, "params", "design.json"), encoding="utf-8"))
    V = build_v3(P)
    df = V["adults"]

    # ── 舊定義重建（v2）
    scr_old = df["LBXSCR"].copy()
    m99 = df["cycle"] == "1999-2000"
    scr_old[m99] = OLD_SCR_9900[0] + OLD_SCR_9900[1] * df.loc[m99, "LBXSCR_raw"]
    egfr_old = egfr_ckdepi2021(scr_old.to_numpy(float), df["age"].to_numpy(float), (df["sex"] == 2).to_numpy())
    ucr_old = df["URXUCR_raw"].fillna(df["URXUCR"]) if "URXUCR_raw" in df else df["URXUCR"]
    acr_old = df["URXUMA"] / (ucr_old / 100.0)
    kd_old = (egfr_old < 60) | (acr_old >= 30)
    hep_old = (df["LBDHBG"] == 1) | (df["LBXHCR"] == 1)
    dm_old = (df["DIQ010"] == 1) | (df["LBXGH"] >= 6.5)
    old = dict(n_adults=int(len(df)), kidney=int(kd_old.sum()),
               outcome_known_old_rule=int((~(pd.isna(egfr_old) & acr_old.isna())).sum()),
               hep=int((kd_old & hep_old).sum()), dm=int((kd_old & dm_old).sum()),
               dm_excl_hep=int((kd_old & dm_old & ~hep_old).sum()), union=int((kd_old & (hep_old | dm_old)).sum()))
    assert (old["kidney"], old["hep"], old["dm"]) == (8983, 169, 3183), f"舊計數重建失敗：{old}"
    assert old["n_adults"] == 55081 and old["outcome_known_old_rule"] == 51792, old
    print(f"[舊定義重建] 成人 {old['n_adults']:,}｜可判定(舊規則) {old['outcome_known_old_rule']:,}｜腎 {old['kidney']:,}"
          f"｜肝炎 {old['hep']}｜糖尿病 {old['dm']:,}｜排除肝炎後糖尿病 {old['dm_excl_hep']:,}｜聯集 {old['union']:,} ✅ 與原稿一致")

    # ── 重分類（腎臟）：兩項校正各自的貢獻
    egfr_new, acr_new = df["eGFR"], df["ACR"]
    kd_new = df["kidney3"] == 1
    scr_only = (egfr_new < 60) | (acr_old >= 30)                 # 只改血清公式
    ucr_only = (egfr_old < 60) | (acr_new >= 30)                 # 只改尿肌酸酐
    recl = dict(
        scr_fix_1999_2000=dict(
            egfr_lt60_old=int((m99 & (egfr_old < 60)).sum()), egfr_lt60_new=int((m99 & (egfr_new < 60)).sum()),
            kidney_gained=int((scr_only & ~kd_old).sum()), kidney_lost=int((~scr_only & kd_old).sum()),
            scr_raw_1p0_old=round(OLD_SCR_9900[0] + OLD_SCR_9900[1] * 1.0, 3), scr_raw_1p0_new=round(0.147 + 1.013 * 1.0, 3)),
        ucr_fix_pre2007=dict(
            acr_ge30_old=int((acr_old >= 30).sum()), acr_ge30_new=int((acr_new >= 30).sum()),
            acr_cross30_up=int(((acr_old < 30) & (acr_new >= 30)).sum()), acr_cross30_down=int(((acr_old >= 30) & (acr_new < 30)).sum()),
            acr_cross300_up=int(((acr_old < 300) & (acr_new >= 300)).sum()), acr_cross300_down=int(((acr_old >= 300) & (acr_new < 300)).sum()),
            kidney_gained=int((ucr_only & ~kd_old).sum()), kidney_lost=int((~ucr_only & kd_old).sum()),
            median_ucr_change_pct=float(np.nanmedian((df["URXUCR"] / ucr_old - 1)[df["cycle"].isin(
                ["1999-2000", "2001-2002", "2003-2004", "2005-2006"])]) * 100)),
        combined=dict(kidney_old=old["kidney"], kidney_new=int(kd_new.sum()),
                      gained=int((kd_new & ~kd_old).sum()), lost=int((~kd_new & kd_old).sum())))
    print(f"[重分類] 1999-2000 eGFR<60：{recl['scr_fix_1999_2000']['egfr_lt60_old']} → {recl['scr_fix_1999_2000']['egfr_lt60_new']}"
          f"｜尿肌酸酐轉換使 ACR 跨 30：+{recl['ucr_fix_pre2007']['acr_cross30_up']}/−{recl['ucr_fix_pre2007']['acr_cross30_down']}"
          f"｜腎臟異常 {recl['combined']['kidney_old']:,} → {recl['combined']['kidney_new']:,}"
          f"（新增 {recl['combined']['gained']}、移出 {recl['combined']['lost']}）")

    # ── 逐週期稽核
    kd = df[kd_new]
    per = []
    for cyc, g in df.groupby("cycle"):
        k = g[g["kidney3"] == 1]
        hep_unk = k[k["hep3"].isna()]
        row = dict(
            cycle=cyc, adults=int(len(g)), dup_seqn=int(g["SEQN"].duplicated().sum()),
            scr_available=int(g["LBXSCR"].notna().sum()), acr_available=int(g["ACR"].notna().sum()),
            kidney=tri(g["kidney3"]),
            kidney_unknown_one_normal_one_missing=int((g["kidney3"].isna() & (g["eGFR"].notna() | g["ACR"].notna())).sum()),
            hep_in_kidney=tri(k["hep3"]), hbv_in_kidney=tri(k["hbv3"]), hcv_in_kidney=tri(k["hcv3"]),
            hep_unknown_reason=dict(
                no_hepatitis_test=int((hep_unk["LBDHBG"].isna() & hep_unk["LBXHCR"].isna() & hep_unk["LBDHCV"].isna()).sum()),
                hcv_antibody_pos_or_indet_without_rna=int((hep_unk["LBDHCV"].isin([1, 5]) & hep_unk["LBXHCR"].isna()).sum()),
                other=0),
            dm_in_kidney=tri(k["dm3"]), dm_questionnaire=tri(k["dmq3"]), dm_hba1c=tri(k["dma3"]),
            diq010_codes_in_kidney={str(int(c)) if pd.notna(c) else "missing": int(n)
                                    for c, n in k["DIQ010"].value_counts(dropna=False).sort_index().items()},
            axis_n=dict(hep=int(k["hep3"].notna().sum()), dm=int(k["dm3"].notna().sum())))
        row["hep_unknown_reason"]["other"] = int(len(hep_unk)) - sum(row["hep_unknown_reason"].values())
        per.append(row)
        print(f"  {cyc}: 成人 {row['adults']:,}｜腎 陽/陰/未知 {row['kidney']['pos']}/{row['kidney']['neg']}/{row['kidney']['unknown']}"
              f"｜肝炎 {row['hep_in_kidney']}｜糖尿病 {row['dm_in_kidney']}")

    # ── 全體彙總與交叉表
    tot = dict(adults=int(len(df)), kidney=tri(df["kidney3"]),
               kidney_unknown_one_normal_one_missing=int((df["kidney3"].isna() & (df["eGFR"].notna() | df["ACR"].notna())).sum()),
               kidney_unknown_both_missing=int((df["eGFR"].isna() & df["ACR"].isna()).sum()),
               hep_in_kidney=tri(kd["hep3"]), hbv_in_kidney=tri(kd["hbv3"]), hcv_in_kidney=tri(kd["hcv3"]),
               dm_in_kidney=tri(kd["dm3"]), dmq_in_kidney=tri(kd["dmq3"]), dma_in_kidney=tri(kd["dma3"]),
               both_hbv_and_hcv=int(((kd["hbv3"] == 1) & (kd["hcv3"] == 1)).sum()))
    lab = lambda s: s.map({1.0: "陽性", 0.0: "陰性"}).fillna("未知")
    ct = pd.crosstab(lab(kd["hep3"]), lab(kd["dm3"]))
    crosstab = {r: {c: int(ct.loc[r, c]) for c in ct.columns} for r in ct.index}
    # 標籤轉移：舊（布林，未知當陰性）→ 新（三值）
    trans = {}
    for name, new, oldv in (("hep", kd["hep3"], hep_old[kd_new]), ("dm", kd["dm3"], dm_old[kd_new])):
        t = pd.crosstab(oldv.map({True: "舊陽性", False: "舊陰性"}), lab(new))
        trans[name] = {r: {c: int(t.loc[r, c]) for c in t.columns} for r in t.index}
    print(f"[全體] 腎臟 {tot['kidney']}｜一正常一缺（舊規則當陰性）{tot['kidney_unknown_one_normal_one_missing']:,}")
    print(f"[腎臟異常者] 肝炎 {tot['hep_in_kidney']}（HBV {tot['hbv_in_kidney']}、HCV {tot['hcv_in_kidney']}）")
    print(f"[腎臟異常者] 糖尿病 {tot['dm_in_kidney']}（問卷 {tot['dmq_in_kidney']}、HbA1c {tot['dma_in_kidney']}）")
    print(f"[交叉表] {crosstab}")
    print(f"[標籤轉移] {trans}")

    out = dict(created=pd.Timestamp.now().isoformat(timespec="seconds"),
               purpose="v3 資料與標籤稽核（回應 2026-09-26 深度審查）",
               corrections=["1999-2000 血清肌酸酐：Y = 1.013X + 0.147（LAB18；原誤用 NHANES III 的 −0.184 + 0.960X）",
                            "2007 前尿肌酸酐：ALB_CR_E 分段轉換（1999–2006 四週期）",
                            "三值標籤：未知不再當陰性（腎臟、B 肝、C 肝、糖尿病）",
                            "封存規則改列名：血比容 LBXHCT 不再被 LBXHC 字首誤封"],
               old_rebuild=old, reclassification=recl, per_cycle=per, total=tot,
               two_label_crosstab_in_kidney=crosstab, label_transition_old_to_new=trans,
               features_v3=V["features"], n_features_v3=len(V["features"]))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[存檔] {OUT}")


if __name__ == "__main__":
    main()
