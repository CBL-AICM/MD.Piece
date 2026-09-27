# -*- coding: utf-8 -*-
"""NHANES 1999–2004 三週期世代建構：合併 → 腎損傷族群 → 三大病因標籤 → 特徵/封存集分離。

誠實邊界（印在每份輸出）：
  * 標籤是「共病代理」（問卷診斷＋血清學＋surplus sera 自體抗體），不是切片病因。
  * 免疫標籤只在 SSANA 次樣本（1999–2004 surplus sera，n≈4,532）可判定——
    主世代因此限定為「SSANA 次樣本 ∩ 腎損傷」，三類標籤皆可判定；
    次世代（感染 vs 代謝，不含免疫）用全部三週期擴大樣本。
  * 每個輸入檔皆經 provenance.require_real()（雜湊驗證）——零自製資料。

變數名以候選清單在執行期自省；找不到即 raise 並列出該檔實際欄位（不猜、不填）。"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from provenance import require_real  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")

CYCLES = {  # 檔名 → 週期
    "1999-2000": dict(demo="DEMO.xpt", biochem="LAB18.xpt", cbc="LAB25.xpt", crp="LAB11.xpt",
                      acr="LAB16.xpt", hba1c="LAB10.xpt", hep="LAB02.xpt", diq="DIQ.xpt"),
    "2001-2002": dict(demo="DEMO_B.xpt", biochem="L40_B.xpt", cbc="L25_B.xpt", crp="L11_B.xpt",
                      acr="L16_B.xpt", hba1c="L10_B.xpt", hep="L02_B.xpt", diq="DIQ_B.xpt"),
    "2003-2004": dict(demo="DEMO_C.xpt", biochem="L40_C.xpt", cbc="L25_C.xpt", crp="L11_C.xpt",
                      acr="L16_C.xpt", hba1c="L10_C.xpt", hep="L02_C.xpt", diq="DIQ_C.xpt"),
}
# 第二批（腎臟相關指數全景）：脂質盤／重金屬（腎小管毒性）／營養素／維生素 D（CKD-MBD）／PTH 在 L11_C
EXTRA_FILES = {
    "1999-2000": ["LAB13.xpt", "LAB13AM.xpt", "LAB06.xpt"],
    "2001-2002": ["L13_B.xpt", "L13AM_B.xpt", "L06_B.xpt", "VID_B.xpt"],
    "2003-2004": ["L13_C.xpt", "L13AM_C.xpt", "L06BMT_C.xpt", "L06NB_C.xpt", "L06MH_C.xpt", "L06TFR_C.xpt", "VID_C.xpt"],
}
# ── 2005–2018 七個週期（僅供不需要 ANA 的任務：感染／代謝）
# 檔名皆以「HTTP 200 且內容開頭為 HEADER RECORD」實測驗證——
# 注意 /Nchs/Nhanes/YYYY-YYYY/ 這個路徑對任何檔名都回 200＋HTML 錯誤頁，不可用於探測存在性。
CYCLES_EXT = {
    "2005-2006": dict(demo="DEMO_D.xpt", biochem="BIOPRO_D.xpt", cbc="CBC_D.xpt", acr="ALB_CR_D.xpt",
                      hba1c="GHB_D.xpt", diq="DIQ_D.xpt", hepb="HEPBD_D.xpt", hepc="HEPC_D.xpt", crp="CRP_D.xpt"),
    "2007-2008": dict(demo="DEMO_E.xpt", biochem="BIOPRO_E.xpt", cbc="CBC_E.xpt", acr="ALB_CR_E.xpt",
                      hba1c="GHB_E.xpt", diq="DIQ_E.xpt", hepb="HEPBD_E.xpt", hepc="HEPC_E.xpt", crp="CRP_E.xpt"),
    "2009-2010": dict(demo="DEMO_F.xpt", biochem="BIOPRO_F.xpt", cbc="CBC_F.xpt", acr="ALB_CR_F.xpt",
                      hba1c="GHB_F.xpt", diq="DIQ_F.xpt", hepb="HEPBD_F.xpt", hepc="HEPC_F.xpt", crp="CRP_F.xpt"),
    "2011-2012": dict(demo="DEMO_G.xpt", biochem="BIOPRO_G.xpt", cbc="CBC_G.xpt", acr="ALB_CR_G.xpt",
                      hba1c="GHB_G.xpt", diq="DIQ_G.xpt", hepb="HEPBD_G.xpt", hepc="HEPC_G.xpt"),
    "2013-2014": dict(demo="DEMO_H.xpt", biochem="BIOPRO_H.xpt", cbc="CBC_H.xpt", acr="ALB_CR_H.xpt",
                      hba1c="GHB_H.xpt", diq="DIQ_H.xpt", hepb="HEPBD_H.xpt", hepc="HEPC_H.xpt"),
    "2015-2016": dict(demo="DEMO_I.xpt", biochem="BIOPRO_I.xpt", cbc="CBC_I.xpt", acr="ALB_CR_I.xpt",
                      hba1c="GHB_I.xpt", diq="DIQ_I.xpt", hepb="HEPBD_I.xpt", hepc="HEPC_I.xpt", crp="HSCRP_I.xpt"),
    "2017-2018": dict(demo="DEMO_J.xpt", biochem="BIOPRO_J.xpt", cbc="CBC_J.xpt", acr="ALB_CR_J.xpt",
                      hba1c="GHB_J.xpt", diq="DIQ_J.xpt", hepb="HEPBD_J.xpt", hepc="HEPC_J.xpt", crp="HSCRP_J.xpt"),
}
EXTRA_FILES_EXT = {   # 脂質盤在新週期拆成三個檔
    "2005-2006": ["TCHOL_D.xpt", "HDL_D.xpt", "TRIGLY_D.xpt"],
    "2007-2008": ["TCHOL_E.xpt", "HDL_E.xpt", "TRIGLY_E.xpt"],
    "2009-2010": ["TCHOL_F.xpt", "HDL_F.xpt", "TRIGLY_F.xpt"],
    "2011-2012": ["TCHOL_G.xpt", "HDL_G.xpt", "TRIGLY_G.xpt"],
    "2013-2014": ["TCHOL_H.xpt", "HDL_H.xpt", "TRIGLY_H.xpt"],
    "2015-2016": ["TCHOL_I.xpt", "HDL_I.xpt", "TRIGLY_I.xpt"],
    "2017-2018": ["TCHOL_J.xpt", "HDL_J.xpt", "TRIGLY_J.xpt"],
}
# 肌酸酐標準化校正係數 standard = a + b × 原值（NHANES 官方分析注記，逐週期查證；未列者不需校正）
# 2026-09-26 修正：1999-2000 原誤用 NHANES III（1988–94）的 (-0.184, 0.960)，使該週期肌酸酐被低估
# （原值 1.0 → 0.776，應為 1.160），eGFR 高估、腎損傷少算。LAB18 文件：Y = 1.013 X + 0.147。
SCR_CALIBRATION = {
    "1999-2000": (0.147, 1.013),     # LAB18 文件「Correction ... is highly recommended」
    "2005-2006": (-0.016, 0.978),    # BIOPRO_D 文件明載「Correction ... is highly recommended」
}
# 尿肌酸酐：2007 年起方法由 Beckman CX3 Jaffe 改為 Roche ModP 酵素法；ALB_CR_E 文件建議
# 對 2007 年前的值（X, mg/dL）做分段轉換後才與 2007 起的值比較。
UCR_PRE2007 = {"1999-2000", "2001-2002", "2003-2004", "2005-2006"}


def adjust_ucr_pre2007(x):
    """ALB_CR_E 官方分段式：X<75 → (1.02√X−0.36)²；75≤X<250 → (1.05√X−0.74)²；X≥250 → (1.01√X−0.10)²。"""
    x = np.asarray(x, float)
    s = np.sqrt(x)
    return np.where(x < 75, (1.02 * s - 0.36) ** 2, np.where(x < 250, (1.05 * s - 0.74) ** 2, (1.01 * s - 0.10) ** 2))


DESIGN = ["WTMEC2YR", "WTMEC4YR", "SDMVPSU", "SDMVSTRA"]    # 抽樣權重與設計變數（只作權重，不作特徵）

ANA_FILES = ["SSANA_A.xpt", "SSANA2_A.xpt"]
CYSTATIN_FILES = ["SSCYST_A.xpt", "SSCYST_B.xpt"]           # surplus sera 1999-2002，跨週期以 SEQN 併

# 變數候選（NHANES SAS 名；執行期驗證存在性）
CAND = dict(
    age=["RIDAGEYR"], sex=["RIAGENDR"],
    scr=["LBXSCR"], hba1c=["LBXGH"], diq=["DIQ010"],
    uma=["URXUMA"], ucr=["URXUCR"],
    hbsag=["LBDHBG", "LBXHBG"], hbcab=["LBXHBC"],
    hcv_ab=["LBXHCV", "LBDHCV"], hcv_rna=["LBXHCR", "LBDHCR", "SSHCV", "LBXHCVRNA"],
)

# 特徵通道（封存集除外的「全部」常規檢驗）：由檔案欄位動態決定，這裡列「已知語意」的中文名對照
FEATURE_LABELS = {
    "LBXSCR": "血清肌酸酐", "LBXSBU": "尿素氮 BUN", "LBXSUA": "尿酸", "LBXSAL": "血清白蛋白",
    "LBXSGL": "血清葡萄糖（隨機）", "LBXSCH": "總膽固醇", "LBXSTR": "三酸甘油酯",
    "LBXSGTSI": "GGT", "LBXSASSI": "AST", "LBXSATSI": "ALT", "LBXSLDSI": "LDH", "LBXSAPSI": "鹼性磷酸酶",
    "LBXSTB": "總膽紅素", "LBXSTP": "總蛋白", "LBXSGB": "球蛋白", "LBXSPH": "磷", "LBXSCA": "鈣",
    "LBXSNASI": "鈉", "LBXSKSI": "鉀", "LBXSCLSI": "氯", "LBXSC3SI": "碳酸氫根", "LBXSIR": "鐵", "LBXSOSSI": "滲透壓",
    "LBXWBCSI": "白血球", "LBXLYPCT": "淋巴球 %", "LBXMOPCT": "單核球 %", "LBXNEPCT": "嗜中性球 %",
    "LBXEOPCT": "嗜酸性球 %", "LBXBAPCT": "嗜鹼性球 %", "LBXRBCSI": "紅血球", "LBXHGB": "血色素",
    "LBXHCT": "血比容", "LBXMCVSI": "MCV", "LBXMC": "MCHC", "LBXMCHSI": "MCH", "LBXRDW": "RDW",
    "LBXPLTSI": "血小板", "LBXMPSI": "平均血小板體積", "LBXCRP": "CRP",
    "URXUMA": "尿白蛋白", "URXUCR": "尿肌酸酐",
    # ── 第二批：腎臟相關指數全景
    "LBXTC": "總膽固醇（脂質盤）", "LBDHDL": "HDL 膽固醇", "LBXHDD": "HDL 膽固醇（直接法）",
    "LBDLDL": "LDL 膽固醇", "LBXTR": "三酸甘油酯（空腹）",
    "LBXBPB": "血鉛", "LBXBCD": "血鎘", "LBXTHG": "血汞", "LBXCOT": "血清可丁尼（菸暴露）",
    "LBXFER": "鐵蛋白", "LBXFOL": "血清葉酸", "LBXRBF": "紅血球葉酸", "LBXB12": "維生素 B12",
    "LBXHCY": "同半胱胺酸", "LBXMMA": "甲基丙二酸",
    "LBDVIDMS": "25-羥維生素 D（LC-MS）", "LBXPT21": "副甲狀腺素 PTH", "LBXBAP": "骨鹼性磷酸酶 BAP",
    "SSCYPC": "胱蛋白酶抑制素 C（Cystatin C）",
}
# 衍生特徵
DERIVED = dict(ACR="尿白蛋白/肌酸酐比（mg/g）", eGFR="估計腎絲球過濾率（CKD-EPI 2021）", NLR="嗜中性球/淋巴球比")


# 跨週期變數別名：同一檢驗在不同週期的 SAS 名不同，讀檔即統一
#   LBDSCR  = 血清肌酸酐（2001-2002）；其餘週期為 LBXSCR
#   （2026-08-30 稽核發現：漏了這個別名會讓整個 2001-2002 週期的肌酸酐被靜默丟棄，
#     導致 708 人無 eGFR、753 人無法 KDIGO 分期——缺值看似是資料特性，實為合併缺陷）
ALIASES = {"LBDSCR": "LBXSCR"}

# ── v3.2 修正（params/v3_2_plan.json；2026-09-27 逐週期核對 CDC 文件後發現）
# C1：2001–2002 兩家實驗室交叉比對後之調和值以 LBD 名發布（L40_B、L06_B、L11_B），2003–2004 鐵蛋白為 LBDFER；
#     HDL 自 2005 年起名為 LBDHDD。單位皆與對應之 LBX／LBDHDL 相同。
V32_RENAMES = {"LBDSAPSI": "LBXSAPSI", "LBDSLDSI": "LBXSLDSI", "LBDSPH": "LBXSPH", "LBDSTB": "LBXSTB",
               "LBDHCY": "LBXHCY", "LBDBAP": "LBXBAP", "LBDFER": "LBXFER", "LBDHDD": "LBDHDL"}
# C3：BIOPRO_J 回推式，2017–2018 Roche Cobas 6000 → 2015–2016 Beckman DxC 660i 量尺：X = a + b·Y
BRIDGE_J = {"LBXSAL": (0.01128, 1.044), "LBXSASSI": (3.762, 1.018), "LBXSATSI": (2.688, 1.013),
            "LBXSBU": (0.4488, 1.001), "LBXSCH": (-2.203, 1.046), "LBXSCR": (-0.06945, 1.051),
            "LBXSGTSI": (2.363, 0.8042), "LBXSIR": (-4.494, 0.9776), "LBXSLDSI": (2.062, 0.8568),
            "LBXSTR": (-7.02, 0.9655), "LBXSUA": (0.2326, 0.9323)}
BRIDGE_J_LOG10 = {"LBXSAPSI": (-0.04294, 1.001)}     # log10 X = a + b·log10 Y


def to_dxc(df, mask):
    """C3：把 mask 列（Cobas 6000 量尺）換成 DxC 660i 量尺；換算值 <0 設為 0。
    球蛋白＝總蛋白－白蛋白（資料中兩者完全相等）；滲透壓（1.86Na＋GLU/18＋BUN/2.8＋9）只有 BUN 被換算。"""
    bun0 = df.loc[mask, "LBXSBU"].copy()
    for c, (a, b) in BRIDGE_J.items():
        df.loc[mask, c] = (a + b * df.loc[mask, c]).clip(lower=0)
    for c, (a, b) in BRIDGE_J_LOG10.items():
        df.loc[mask, c] = 10 ** (a + b * np.log10(df.loc[mask, c]))
    df.loc[mask, "LBXSGB"] = df.loc[mask, "LBXSTP"] - df.loc[mask, "LBXSAL"]
    df.loc[mask, "LBXSOSSI"] = df.loc[mask, "LBXSOSSI"] + ((df.loc[mask, "LBXSBU"] - bun0) / 2.8).fillna(0)
    return df


def _read(key):
    p = os.path.join(RAW, key)
    require_real(p)
    df = pd.read_sas(p, format="xport")
    df.columns = [c.upper() for c in df.columns]
    for src, dst in ALIASES.items():
        if src in df.columns and dst not in df.columns:
            df = df.rename(columns={src: dst})
    return df


def _pick(df, cands, where, required=True):
    for c in cands:
        if c in df.columns:
            return c
    if required:
        raise RuntimeError(f"{where} 找不到候選變數 {cands}；實際欄位：{sorted(df.columns)[:40]}…")
    return None


def egfr_ckdepi2021(scr_mgdl, age, is_female):
    """CKD-EPI 2021（無種族係數）。scr 需為標準化 mg/dL。"""
    k = np.where(is_female, 0.7, 0.9)
    a = np.where(is_female, -0.241, -0.302)
    r = scr_mgdl / k
    egfr = 142.0 * np.minimum(r, 1) ** a * np.maximum(r, 1) ** (-1.200) * (0.9938 ** age)
    return egfr * np.where(is_female, 1.012, 1.0)


def load_all(verbose=True):
    """回傳 (df 全體合併, meta)。血清肌酸酐依 NHANES 分析指引：1999-2000 需校正（standard = -0.184 + 0.960×SCr），
    2001-2004 不需（校正式為 NHANES 官方分析注記；敏感度分析含未校正版）。"""
    rows = []
    for cyc, files in CYCLES.items():
        demo = _read(files["demo"])
        d = demo[["SEQN", _pick(demo, CAND["age"], files["demo"]), _pick(demo, CAND["sex"], files["demo"])]].copy()
        d.columns = ["SEQN", "age", "sex"]
        d = d.merge(demo[["SEQN"] + [c for c in DESIGN if c in demo.columns]], on="SEQN", how="left")
        d["cycle"] = cyc
        for role in ("biochem", "cbc", "crp", "acr", "hba1c", "hep", "diq"):
            f = _read(files[role])
            keep = [c for c in f.columns if c == "SEQN" or c in FEATURE_LABELS or
                    any(c in CAND[k] for k in ("hba1c", "diq", "hbsag", "hbcab", "hcv_ab", "hcv_rna"))]
            d = d.merge(f[keep].drop_duplicates("SEQN"), on="SEQN", how="left", suffixes=("", f"_{role}"))
        for extra in EXTRA_FILES.get(cyc, []):
            f = _read(extra)
            keep = [c for c in f.columns if c == "SEQN" or c in FEATURE_LABELS]
            if len(keep) > 1:
                d = d.merge(f[keep].drop_duplicates("SEQN"), on="SEQN", how="left", suffixes=("", "_x"))
        if cyc in SCR_CALIBRATION and "LBXSCR" in d.columns:
            a, b = SCR_CALIBRATION[cyc]
            d["LBXSCR_raw"] = d["LBXSCR"]
            d["LBXSCR"] = a + b * d["LBXSCR"]                   # 肌酸酐標準化校正（逐週期依官方注記）
        if cyc in UCR_PRE2007 and "URXUCR" in d.columns:
            d["URXUCR_raw"] = d["URXUCR"]
            d["URXUCR"] = adjust_ucr_pre2007(d["URXUCR"])       # 2007 前尿肌酸酐方法轉換（ALB_CR_E）
        rows.append(d)
        if verbose:
            print(f"[cohort] {cyc}: n={len(d)}")
    df = pd.concat(rows, ignore_index=True)

    # Cystatin C（surplus 1999-2002）：兩檔各覆蓋一段，SEQN 併接
    for cf in CYSTATIN_FILES:
        cy = _read(cf)
        keep = [c for c in cy.columns if c in ("SEQN", "SSCYPC")]
        if "SSCYPC" in keep:
            df = df.merge(cy[keep].drop_duplicates("SEQN").rename(columns={"SSCYPC": f"SSCYPC_{cf[:8]}"}), on="SEQN", how="left")
    cys_cols = [c for c in df.columns if c.startswith("SSCYPC_")]
    if cys_cols:
        df["SSCYPC"] = df[cys_cols].bfill(axis=1).iloc[:, 0]
        df = df.drop(columns=cys_cols)
    # HDL 名稱跨週期不同（99-01 LBDHDL、03-04 LBXHDD）→ 合併為單欄
    if "LBXHDD" in df.columns:
        df["LBDHDL"] = df.get("LBDHDL", pd.Series(np.nan, index=df.index)).fillna(df["LBXHDD"])
        df = df.drop(columns=["LBXHDD"])
    ana = _read(ANA_FILES[0])
    ana_cols = [c for c in ana.columns if c != "SEQN"]
    df = df.merge(ana.drop_duplicates("SEQN"), on="SEQN", how="left", indicator="in_ana")
    df["in_ana_subsample"] = (df["in_ana"] == "both")
    df = df.drop(columns=["in_ana"])
    if verbose:
        print(f"[cohort] 合併：n={len(df)}；SSANA 次樣本 {int(df['in_ana_subsample'].sum())}")
    return df, dict(ana_cols=ana_cols)


def load_extended(verbose=True, cycles=None, extra=None):
    """2005–2018 七個週期（預設）。這些週期沒有 surplus sera ANA，故免疫狀態一律未知。
    cycles／extra 可傳入其他週期（外部驗證 2021–2023 用），規則完全相同。"""
    rows = []
    EXTRA_FILES_EXT_ = EXTRA_FILES_EXT if extra is None else extra
    for cyc, files in (CYCLES_EXT if cycles is None else cycles).items():
        demo = _read(files["demo"])
        d = demo[["SEQN", "RIDAGEYR", "RIAGENDR"] + [c for c in DESIGN if c in demo.columns]].copy()
        d = d.rename(columns={"RIDAGEYR": "age", "RIAGENDR": "sex"})
        d["cycle"] = cyc
        for role, fn in files.items():
            if role == "demo":
                continue
            f = _read(fn)
            keep = [c for c in f.columns if c == "SEQN" or c in FEATURE_LABELS or
                    c in ("LBXGH", "DIQ010", "LBDHBG", "LBXHBC", "LBXHCR", "LBDHCV", "LBXHCV", "LBDHCI")]
            if len(keep) > 1:
                d = d.merge(f[keep].drop_duplicates("SEQN"), on="SEQN", how="left", suffixes=("", "_x"))
        for extra in EXTRA_FILES_EXT_.get(cyc, []):
            f = _read(extra)
            keep = [c for c in f.columns if c == "SEQN" or c in FEATURE_LABELS]
            if len(keep) > 1:
                d = d.merge(f[keep].drop_duplicates("SEQN"), on="SEQN", how="left", suffixes=("", "_x"))
        if cyc in SCR_CALIBRATION and "LBXSCR" in d.columns:
            a, b = SCR_CALIBRATION[cyc]
            d["LBXSCR_raw"] = d["LBXSCR"]
            d["LBXSCR"] = a + b * d["LBXSCR"]
        if cyc in UCR_PRE2007 and "URXUCR" in d.columns:
            d["URXUCR_raw"] = d["URXUCR"]
            d["URXUCR"] = adjust_ucr_pre2007(d["URXUCR"])
        rows.append(d)
        if verbose:
            print(f"[cohort-ext] {cyc}: n={len(d)}")
    df = pd.concat(rows, ignore_index=True)
    df["in_ana_subsample"] = False
    return df


def build_extended(P, verbose=True):
    """1999–2018 全週期世代，**僅供不需要 ANA 的任務**（感染／代謝）。

    2005 年後沒有 ANA，免疫狀態是未知而非陰性——本函式回傳的世代不含可用的免疫標籤，
    任何免疫任務都必須改用 build() 的 primary（ANA 實測子樣本）。"""
    base, _ = load_all(verbose=verbose)
    ext = load_extended(verbose=verbose)
    df = pd.concat([base, ext], ignore_index=True, sort=False)
    df = df[df["age"] >= P["population"]["value"]["age_min"]].copy()
    female = df["sex"] == 2
    df["eGFR"] = egfr_ckdepi2021(df["LBXSCR"].to_numpy(float), df["age"].to_numpy(float), female.to_numpy())
    df["ACR"] = df["URXUMA"] / (df["URXUCR"] / 100.0)
    df["kidney_damage"] = (df["eGFR"] < 60) | (df["ACR"] >= 30)
    kd = df[df["kidney_damage"].fillna(False)].copy()
    hbsag = _pick(kd, CAND["hbsag"], "hep", required=False)
    hcv_rna = _pick(kd, CAND["hcv_rna"], "hep", required=False)
    hcv_ab = _pick(kd, CAND["hcv_ab"], "hep", required=False)
    kd["lab_metabolic"] = (kd["DIQ010"] == 1) | (kd["LBXGH"] >= 6.5)
    inf = pd.Series(False, index=kd.index)
    if hbsag:
        inf |= kd[hbsag] == 1
    if hcv_rna:
        inf |= kd[hcv_rna] == 1
    kd["lab_infection"] = inf
    kd["cause"] = np.where(kd["lab_infection"], "感染性",
                           np.where(kd["lab_metabolic"].fillna(False), "代謝性", "其他/未歸類"))
    kd["NLR"] = kd["LBXNEPCT"] / kd["LBXLYPCT"].replace(0, np.nan)
    archive = set(["LBXGH", "DIQ010"] + [c for c in kd.columns if c.startswith("SS")] +
                  [v for v in (hbsag, hcv_rna, hcv_ab) if v] +
                  [c for c in kd.columns if c.startswith(("LBXHB", "LBDHB", "LBXHC", "LBDHC", "LBXHA", "LBXHD", "LBDHD"))])
    feats = [c for c in kd.columns if c in FEATURE_LABELS and c not in archive] + ["ACR", "eGFR", "NLR", "age", "sex"]
    if verbose:
        print(f"[cohort-ext] 全週期成人 {len(df)}；腎損傷 {len(kd)}；"
              f"感染 {int(kd['lab_infection'].sum())}、代謝 {int(kd['lab_metabolic'].fillna(False).sum())}")
        print(f"[cohort-ext] 逐週期腎損傷：{kd['cycle'].value_counts().sort_index().to_dict()}")
    return dict(cohort=kd, features=feats, archive=sorted(archive),
                counts=dict(n=len(kd), infection=int(kd["lab_infection"].sum()),
                            metabolic=int(kd["lab_metabolic"].fillna(False).sum()),
                            by_cycle={str(k): int(v) for k, v in kd["cycle"].value_counts().sort_index().items()}),
                feature_labels={**FEATURE_LABELS, **DERIVED, "age": "年齡", "sex": "性別"})


def labels_v3(df):
    """三值標籤（1 陽性／0 陰性／NaN 未知），2026-09-26 依審查意見重建。
    規則：任一組成明確陽性 → 陽性；所有必要組成皆可排除 → 陰性；其餘 → 未知（不再以 False 代替）。
      腎臟：eGFR<60 或 ACR≥30 → 1；兩者皆測且正常 → 0；一正常一缺、兩者皆缺 → 未知
      B 肝：HBsAg（LBDHBG）1/2；未測 → 未知
      C 肝：RNA（LBXHCR）1 → 1；2 或 3（2013 起 3＝抗體篩檢陰性）→ 0；RNA 缺且抗體（LBDHCV）陰性 → 0
            （依檢驗流程抗體陰性不做 RNA）；抗體陽性／不確定而無 RNA（含 2003–04 全週期無 RNA）→ 未知
      糖尿病：問卷 DIQ010＝1 → 1、2 或 3（邊緣）→ 0、7/9/缺 → 未知；HbA1c ≥6.5 → 1、<6.5 → 0
            合成：任一為 1 → 1；兩者皆 0 → 0；其餘未知"""
    idx = df.index
    col = lambda c: df[c] if c in df.columns else pd.Series(np.nan, index=idx)
    e, a = df["eGFR"], df["ACR"]
    df["kidney3"] = np.select([(e < 60) | (a >= 30), (e >= 60) & (a < 30)], [1.0, 0.0], np.nan)
    hbs = col("LBDHBG")
    df["hbv3"] = np.select([hbs == 1, hbs == 2], [1.0, 0.0], np.nan)
    rna, ab = col("LBXHCR"), col("LBDHCV")
    df["hcv3"] = np.select([rna == 1, rna.isin([2, 3]), rna.isna() & (ab == 2)], [1.0, 0.0, 0.0], np.nan)
    df["hep3"] = np.select([(df["hbv3"] == 1) | (df["hcv3"] == 1), (df["hbv3"] == 0) & (df["hcv3"] == 0)],
                           [1.0, 0.0], np.nan)
    q, g = col("DIQ010"), col("LBXGH")
    df["dmq3"] = np.select([q == 1, q.isin([2, 3])], [1.0, 0.0], np.nan)
    df["dma3"] = np.select([g >= 6.5, g < 6.5], [1.0, 0.0], np.nan)
    df["dm3"] = np.select([(df["dmq3"] == 1) | (df["dma3"] == 1), (df["dmq3"] == 0) & (df["dma3"] == 0)],
                          [1.0, 0.0], np.nan)
    return df


def build_v3(P, verbose=True, fixes=False):
    """1999–2018 十週期、三值標籤版（2026-09-26）。回傳全體成人（稽核／權重用）與腎臟指標異常者。
    與 build_extended 的差異：①1999-2000 血清肌酸酐公式更正 ②2007 前尿肌酸酐轉換 ③標籤三值、未知不再當陰性
    ④封存規則改為明列肝炎變數，不再以字首誤封血比容（LBXHCT）。
    fixes=True 為 v3.2（C1 改名對應、C2 D 肝明列封存而保留 HDL、C3 2017–2018 生化換成 DxC 量尺）；
    預設 False 與 v3 逐位相同。v3.2 另存 LBXSCR_rep（換算前之肌酸酐）與 kidney3_rep（依之判定）供敏感度分析。"""
    saved = dict(ALIASES)
    if fixes:
        ALIASES.update(V32_RENAMES)     # ponytail: 借用讀檔的別名機制，只在這次讀取期間生效
    try:
        base, _ = load_all(verbose=False)
        ext = load_extended(verbose=False)
    finally:
        ALIASES.clear()
        ALIASES.update(saved)
    df = pd.concat([base, ext], ignore_index=True, sort=False)
    df = df[df["age"] >= P["population"]["value"]["age_min"]].copy()
    female = df["sex"] == 2
    if fixes:
        df["LBXSCR_rep"] = df["LBXSCR"]
        df = to_dxc(df, df["cycle"] == "2017-2018")
        e_rep = egfr_ckdepi2021(df["LBXSCR_rep"].to_numpy(float), df["age"].to_numpy(float), female.to_numpy())
    df["eGFR"] = egfr_ckdepi2021(df["LBXSCR"].to_numpy(float), df["age"].to_numpy(float), female.to_numpy())
    df["ACR"] = df["URXUMA"] / (df["URXUCR"] / 100.0)
    df["NLR"] = df["LBXNEPCT"] / df["LBXLYPCT"].replace(0, np.nan)
    # 合併 20 年 MEC 權重（NHANES 教學：1999–2002 用 4 年權重 ×4/20，其後 2 年權重 ×2/20）
    df["w_mec20"] = np.where(df["cycle"].isin(["1999-2000", "2001-2002"]), 0.2 * df["WTMEC4YR"], 0.1 * df["WTMEC2YR"])
    labels_v3(df)
    if fixes:
        a = df["ACR"]
        df["kidney3_rep"] = np.select([(e_rep < 60) | (a >= 30), (e_rep >= 60) & (a < 30)], [1.0, 0.0], np.nan)
    kd = df[df["kidney3"] == 1].copy()
    prefixes = ("LBXHB", "LBDHB", "LBXHA", "SSHCV") if fixes else ("LBXHB", "LBDHB", "LBXHA", "LBXHD", "LBDHD", "SSHCV")
    hep_vars = [c for c in df.columns if c.startswith(prefixes)
                or c in ("LBXHCV", "LBDHCV", "LBXHCR", "LBDHCR", "LBXHCG", "LBDHCI", "LBXHCVRNA")
                or (fixes and c in ("LBDHD", "LBXHD"))]
    archive = set(["LBXGH", "DIQ010"] + [c for c in df.columns if c.startswith("SS")] + hep_vars)
    feats = [c for c in kd.columns if c in FEATURE_LABELS and c not in archive] + ["ACR", "eGFR", "NLR", "age", "sex"]
    if verbose:
        print(f"[cohort-v3] 成人 {len(df):,}；腎臟 陽/陰/未知 = {int((df.kidney3 == 1).sum()):,}/"
              f"{int((df.kidney3 == 0).sum()):,}/{int(df.kidney3.isna().sum()):,}；特徵 {len(feats)}")
    return dict(adults=df, cohort=kd, features=feats, archive=sorted(archive),
                feature_labels={**FEATURE_LABELS, **DERIVED, "age": "年齡", "sex": "性別"})


def build(P, verbose=True):
    df, meta = load_all(verbose=verbose)
    pop = P["population"]["value"]
    df = df[df["age"] >= pop["age_min"]].copy()

    # 腎損傷定義
    female = df["sex"] == 2
    df["eGFR"] = egfr_ckdepi2021(df["LBXSCR"].to_numpy(float), df["age"].to_numpy(float), female.to_numpy())
    df["ACR"] = df["URXUMA"] / (df["URXUCR"] / 100.0)           # mg/L ÷ (mg/dL→mg/L 係數) → mg/g
    df["kidney_damage"] = (df["eGFR"] < 60) | (df["ACR"] >= 30)
    kd = df[df["kidney_damage"].fillna(False)].copy()
    if verbose:
        print(f"[cohort] 成人 {len(df)}；腎損傷（eGFR<60 或 ACR≥30）{len(kd)}")

    # ── 三大病因標籤（共病代理；操作型定義見 design.json）
    hbsag = _pick(kd, CAND["hbsag"], "hep", required=False)
    hcv_rna = _pick(kd, CAND["hcv_rna"], "hep", required=False)
    hcv_ab = _pick(kd, CAND["hcv_ab"], "hep", required=False)
    lab_meta = dict(hbsag_var=hbsag, hcv_rna_var=hcv_rna, hcv_ab_var=hcv_ab)
    kd["lab_metabolic"] = (kd["DIQ010"] == 1) | (kd["LBXGH"] >= 6.5)
    inf = pd.Series(False, index=kd.index)
    if hbsag:
        inf |= kd[hbsag] == 1
    if hcv_rna:
        inf |= kd[hcv_rna] == 1
    elif hcv_ab:
        inf |= kd[hcv_ab] == 1
        lab_meta["note_hcv"] = "無 RNA 變數，以抗體陽性代理（列敏感度）"
    kd["lab_infection"] = inf
    # 免疫：SSANA 次樣本內，SSTOT ≥3（該檔自身的 3+/4+ 陽性規則，對應滴度 ≥1:80 確認）或任一特異抗體陽性
    sp_cols = [c for c in meta["ana_cols"] if c.startswith("SS") and c not in
               ("SSTOT", "SSNUC", "SSCYT", "WTANA6YR") and not c.startswith(("SS8", "SS16", "SS32", "SS64", "SS12"))
               and not c.startswith(("SSNU", "SSCY", "SSMI"))]
    sp_pos = (kd[sp_cols] == 1).any(axis=1) if sp_cols else pd.Series(False, index=kd.index)
    kd["lab_immune"] = np.where(kd["in_ana_subsample"], ((kd["SSTOT"] >= 3) | sp_pos), np.nan)

    # 歸類（順位 免疫 > 感染 > 代謝；重疊另計）
    def assign(r):
        if r["in_ana_subsample"] and r["lab_immune"] == 1:
            return "免疫性"
        if r["lab_infection"]:
            return "感染性"
        if r["lab_metabolic"]:
            return "代謝性"
        return "其他/未歸類"
    kd["cause"] = kd.apply(assign, axis=1)
    overlap = dict(
        immune_and_infection=int(((kd["lab_immune"] == 1) & kd["lab_infection"]).sum()),
        immune_and_metabolic=int(((kd["lab_immune"] == 1) & kd["lab_metabolic"]).sum()),
        infection_and_metabolic=int((kd["lab_infection"] & kd["lab_metabolic"]).sum()))

    # ── 特徵／封存集分離（通道消耗規則）
    archive = set(["LBXGH", "DIQ010"] + [c for c in kd.columns if c.startswith("SS")] +
                  [v for v in (hbsag, hcv_rna, hcv_ab) if v] +
                  [c for c in kd.columns if c.startswith(("LBXHB", "LBDHB", "LBXHC", "LBDHC", "LBXHA", "LBXHD", "LBDHD"))])
    feat_cols = [c for c in kd.columns if c in FEATURE_LABELS and c not in archive]
    kd["NLR"] = kd["LBXNEPCT"] / kd["LBXLYPCT"].replace(0, np.nan)
    features = feat_cols + ["ACR", "eGFR", "NLR", "age", "sex"]

    primary = kd[kd["in_ana_subsample"]].copy()                 # 三類皆可判定
    secondary = kd.copy()                                        # 感染 vs 代謝（免疫未知者不進 Level1 三類）
    counts = dict(primary={c: int((primary["cause"] == c).sum()) for c in primary["cause"].unique()},
                  secondary_all={c: int((kd["cause"] == c).sum()) for c in kd["cause"].unique()},
                  overlap=overlap, n_kidney_damage=len(kd), n_primary=len(primary), lab_meta=lab_meta,
                  archive_n=len(archive), feature_n=len(features))
    if verbose:
        print(f"[cohort] 主世代（SSANA∩腎損傷）n={len(primary)}：{counts['primary']}")
        print(f"[cohort] 全腎損傷 n={len(kd)}：{counts['secondary_all']}；重疊 {overlap}")
        print(f"[cohort] 特徵 {len(features)} 欄；封存 {len(archive)} 欄（標籤來源，不得為特徵）")
    return dict(primary=primary, secondary=secondary, features=features, archive=sorted(archive),
                counts=counts, feature_labels={**FEATURE_LABELS, **DERIVED, "age": "年齡", "sex": "性別"})
