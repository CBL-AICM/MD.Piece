# -*- coding: utf-8 -*-
"""科展作品說明書 v3.2（得獎作品寫法）——與 build_fair_v3_2 同源、數字全由結果檔產生，只改寫法與編排。
    python make_figures_fair.py && python build_fair_award.py [--force]
寫法取自近年全國科展得獎作品說明書與評審評語（2026-09-28 閱讀，未保存原檔）：
  研究目的以（一）（二）…平行列出；參之一以研究架構示意圖與「目的—方法—結果」對照表呈現研究過程；
  肆、研究結果各節與研究目的一一同名；伍、討論先以總覽表綜合，再逐方向解釋；陸、結論逐條對應研究目的；
  圖表以中文數字編號、圖說註明來源，內文以「由圖X可看出」引用；另加評估指標的白話說明表。
格式仍依第 64 屆作品說明書附件五至七（見 build_fair_v3_2）。已驗證之段落（動機、文獻回顧、方法、各項結果）
直接取自 build_fair_v3_2.BODY，只重新編排；新寫段落的數字一律來自結果檔，方向性敘述皆有斷言。
輸出：Obsidian 主稿 研究計畫書/科展作品說明書_v3.2_得獎格式.md（圖在 figure/fair/；主稿已被修改時預設不覆蓋，--force 才覆蓋）
與 repo 副本 experiments/docs/。Word：python -X utf8 md2docx.py <主稿.md> --fair"""
import os
import re
import shutil

import build_fair_v3_2 as F
from build_fair_v3_2 import (AU, E, EC, EXW, HG, IM, IM1, IMD, IML, LR, Pb, X, ap, auc, band, cal, dauc, dvd, mdiff, n,
                             pct, sgn, ci, xd, xm)
from build_plan_v3 import pbm, write, xo
from make_figures_fair import NEW

NAME = "科展作品說明書_v3.2_得獎格式"
SRC = F.BODY                                        # 已驗證之 v3.2 內文（數字已代入、引用尚未轉換）
COMMIT_EXW, COMMIT_IMM = "6737bf5", "29e1d3b"       # 暴露分析 v3.2、免疫方向之計畫提交（皆在執行計算前）
CNUM = "一二三四五六七八九十"


def cn(k):
    """1–99 之中文數字。"""
    t, o = divmod(k, 10)
    return ((CNUM[t - 1] if t > 1 else "") + "十" if t else "") + (CNUM[o - 1] if o else "")


TB = {k: "表" + cn(i) for i, k in enumerate(["metrics", "data", "soft", "map", "labels", "conv", "qa", "errors", "dm", "hep",
                                              "sub", "imm", "delta", "rob", "ext", "bands", "tool", "synth"], 1)}
FG = {k: "圖" + cn(i) for i, k in enumerate(["flow", "sample", "disc", "cal", "rob", "ext", "dca", "exw", "recal"], 1)}
FIGFILE = {"flow": "圖一_研究架構示意圖.png", **dict(zip(list(FG)[1:], NEW.values()))}
FIGW = {"sample": 490}                               # Word 中的圖寬（px，1/96 吋）；未列者為版心寬 17 cm
assert all(FIGFILE[k].startswith(FG[k] + "_") for k in FG), "圖檔編號與說明書不一致（make_figures_fair.NEW）"


def cut(a, b):
    assert SRC.count(a) == 1, a
    i = SRC.index(a) + len(a)
    return SRC[i:SRC.index(b, i)].strip("\n")


def para(start):
    """以 start 開頭之段落（至空行為止）。"""
    assert SRC.count(start) == 1, start
    i = SRC.index(start)
    return SRC[i:SRC.index("\n\n", i)]


def table(anchor):
    """anchor（表頭或舊圖說）起的第一個表格。"""
    assert SRC.count(anchor) == 1, anchor
    i = SRC.index(anchor)
    i = i if anchor.startswith("|") else SRC.index("\n|", i) + 1
    return SRC[i:SRC.index("\n\n", i)]


def swap(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


# ── 研究目的與結論：取自 v3.2 內文，與計畫書、論文同步
AIMS = cut("### 二、研究目的\n", "### 三、文獻回顧")
OBJ = re.findall(r"^\d\. (.+)$", AIMS, re.M)
OL = [t.split("：", 1)[0] for t in OBJ]              # 各目的之短名＝肆、研究結果之節名
assert len(OBJ) == 7 and AIMS.startswith("本研究的總目的")
CONC = re.findall(r"^\d\. (.+?)：(.+)$", cut("## 陸、結論\n", "## 柒、參考文獻資料"), re.M)
assert len(CONC) == 7

# ── 各病因方向之模型表現（判別力：五次重複平均；校準：第一次重複）
MODELS = [("LR_routine", "常規套組・邏輯迴歸"), ("LR_routine_noHDL", "常規套組・邏輯迴歸（不含 HDL）"), ("HGB_routine", "常規套組・梯度提升"),
          ("LR_full", "全特徵・邏輯迴歸"), ("HGB_full", "全特徵・梯度提升")]


def perf(ev):
    m1 = ev["M1_demographics"]
    out = ["| 模型 | AUROC | AP | 校準截距 | 校準斜率 | Brier 分數 |", "|---|---|---|---|---|---|",
           f"| 只用年齡、性別（基準） | {m1['auroc_mean']:.3f} | {m1['ap_mean']:.3f} | — | — | — |"]
    for s, lab in MODELS:
        r, c = ev["models"][s]["repeats"]["mean"], ev["models"][s]["calibration_repeat0"]
        out.append(f"| {lab} | {r['auroc']:.3f} | {r['ap']:.3f} | {sgn(c['intercept'], 2)} | {c['slope']:.2f} | {c['brier']:.4f} |")
    return "\n".join(out)


PERF_NOTE = "註：AUROC 與 AP 為巢狀外層五次重複之平均；校準取第一次重複之外層預測；基準模型只比較判別力。"

# ── 新寫段落之方向性斷言（全部來自結果檔）
dm1 = lambda ax, s: E[ax]["paired_vs_demographics_repeat0"][f"{s}−M1_demographics"]["ci95"]["d_auroc"]
xp = lambda ax, k: X[ax]["paired"][k]["ci95"]["d_auroc"]
pr = lambda ax, k: E[ax]["paired_repeat0"][k]
IMH_D = IM["paired_vs_demographics_repeat0"]["HGB_routine−M1_demographics"]
IM_AUC = [IM["models"][s]["repeats"]["mean"]["auroc"] for s, _ in MODELS]
IM_SLOPE = [IM["models"][s]["calibration_repeat0"]["slope"] for s, _ in MODELS]
bd = lambda ax, s, z: band(ax, s)["band"][z]["observed_rate"]
assert min(dm1("糖尿病", LR)[0], dm1("糖尿病", HG)[0], xp("糖尿病", "LR_routine−M1_demographics")[0],
           xp("糖尿病", "HGB_routine−M1_demographics")[0]) > 0, "代謝方向：內外皆明顯優於基準之敘述不成立"
assert min(dm1("肝炎", LR)[0], dm1("肝炎", HG)[0]) > 0 > xp("肝炎", "LR_routine−M1_demographics")[0], "感染方向之敘述不成立"
assert xp("肝炎", "LR_routine−M1_demographics")[1] > 0 and xp("肝炎", "HGB_routine−M1_demographics")[0] < 0
assert IMD["d_auroc"] < 0 and IMD["ci95"]["d_auroc"][0] < 0 and IMH_D["d_auroc"] < 0, "免疫方向之敘述不成立"
assert max(IM_AUC) < IM1 and max(IM_SLOPE) < 0.6, "免疫方向：所有模型皆低於基準、斜率皆小於 0.6 之敘述不成立"
assert pr("糖尿病", "HGB_routine−LR_routine")["ci95"]["d_auroc"][0] > 0 > pr("肝炎", "HGB_routine−LR_routine")["d_auroc"]
assert all(abs(cal("糖尿病", s)["intercept"]) < 0.05 and abs(cal("糖尿病", s)["slope"] - 1) < 0.1 for s in (LR, HG))
assert cal("糖尿病", HG)["brier"] < cal("糖尿病", LR)["brier"]
assert all(abs(pr(ax, "LR_routine−LR_routine_noHDL")["d_auroc"]) < 0.03 for ax in ("肝炎", "糖尿病")), "HDL 影響很小之敘述不成立"
assert band("糖尿病", HG)["coverage"] > band("糖尿病", LR)["coverage"] and band("肝炎", HG)["coverage"] < band("肝炎", LR)["coverage"]
assert bd("糖尿病", HG, "傾向") > bd("糖尿病", LR, "傾向") and bd("糖尿病", HG, "不傾向") < bd("糖尿病", LR, "不傾向")

# ── 取自 v3.2 內文之區塊（只改編號與位置）
ERR = table("| 版本 | 問題 | 後果 | 更正 |")
CN_ERR = cn(sum(line.startswith("| v3") for line in ERR.split("\n")))
assert f"{CN_ERR}項能通過雜湊檢查" in CONC[0][1], "資料錯誤項數與結論不一致"
ROB_ITEMS = re.findall(r"^\d\. (.+)$", cut("### 七、穩健性與分型\n", "### 八、決策曲線與暴露探索"), re.M)
assert [t[:4] for t in ROB_ITEMS] == ["時間外推", "人口加權", "腎臟標籤", "肝炎分型", "免疫方向"]
DCA_M, EXW_M = para("決策曲線比較").split("暴露探索", 1)
IM_SENT = "免疫方向在公開資料中只有抗核抗體可用，缺乏補體與病理，常規檢驗沒有可學習的訊號[@yang]。"
BANDS = "\n".join(line for line in table("**表2　").split("\n") if not line.startswith(("| 校準", "| Brier")))
QA = swap(table("| 機制 | 做法 | 防止什麼 |"), f"v3.2 {F.COMMITS['plan_v32']}）",
          f"v3.2 {F.COMMITS['plan_v32']}、暴露分析 {COMMIT_EXW}、免疫方向 {COMMIT_IMM}）") + \
    "\n| 研究紀錄 | 每次分析的計畫、程式與結果都以 Git 提交保存，版本沿革另記於 VERSION_LOG | 事後說不清結果從何而來 |"
LIT = swap(cut("### 三、文獻回顧\n", "## 貳、研究設備與器材"), "#### （四）本作品的延續與新增", f"""#### （四）本研究使用的評估指標

判別力回答「能不能把陽性與陰性的人分開」，校準回答「模型說 30% 的人，實際上是否約有 30% 陽性」；兩者都要看，缺一不可[@vancalster]。本研究使用的指標整理如{TB['metrics']}。

**{TB['metrics']}、本研究使用的評估指標（本研究整理）**

| 指標 | 意義 | 判讀 |
|---|---|---|
| AUROC | 隨機抽一名陽性者與一名陰性者，模型給陽性者較高分數的機率 | 0.5 等於亂猜，1 為完全分開 |
| 平均精確率（AP） | 依模型分數由高到低挑人時，各點「挑出者中真正陽性的比例」之平均 | 亂猜時約等於盛行率，須與盛行率比較 |
| 校準截距與斜率 | 預測機率與實際比例是否一致 | 截距接近 0、斜率接近 1 最理想；斜率小於 1 表示預測過度極端 |
| Brier 分數 | 預測機率與實際結果（0 或 1）之差的平方平均 | 越小越好 |
| 巢狀交叉驗證 | 資料分成數份，輪流保留一份只用來評估；補值、配適與校準都只用其餘資料 | 被評估的人從未參與建模，避免高估 |
| 配對 ΔAUROC | 同一批人上兩個模型的 AUROC 差，以重抽樣（bootstrap）估計 95% 信賴區間 | 信賴區間不含 0 才表示差異可靠 |
| 決策曲線 | 以「找到陽性的好處」扣除「多驗陰性的代價」所得的淨效益[@vickers] | 高於「全數送驗」與「全不送驗」才有用 |
| 偽發現率 | 同時檢驗很多關聯時，被判為顯著者中預期的錯誤比例[@benjamini] | 控制在 0.05 以下 |

#### （五）本作品的延續與新增""")

# ── 摘要（300 字以內含標點符號）
ABSTRACT = (f"腎炎（腎損傷）的病因可分為感染、免疫、代謝三個方向。本研究探討一般健檢的常規抽血、驗尿數值能否回推病因方向。"
            f"研究對象為美國 NHANES 1999–2018 年 {n(AU['n_adults'])} 名成人，依官方文件修正檢驗量尺與資料錯誤後，在腎臟指標異常者中以巢狀交叉驗證評估。"
            f"結果顯示，代謝方向（糖尿病）邏輯迴歸 AUROC {auc('糖尿病', LR):.3f}、梯度提升 {auc('糖尿病', HG):.3f}，2021–2023 年仍維持 "
            f"{xm('糖尿病', LR)['auroc']:.3f} 與 {xm('糖尿病', HG)['auroc']:.3f}；感染方向（病毒性肝炎）{auc('肝炎', LR):.3f}，訊號主要來自 C 型肝炎；"
            f"免疫方向（抗核抗體）{IML:.3f}，未優於只用年齡、性別的 {IM1:.3f}。常規檢驗可回推代謝與部分感染方向，不能回推免疫方向，也不能取代診斷。")
assert len(ABSTRACT) <= 300, f"摘要 {len(ABSTRACT)} 字，超過 300 字"

BODY = f"""**科　　別**：動物與醫學學科

**組　　別**：高級中等學校組

**作品名稱**：{F.TITLE}

**關 鍵 詞**：{F.KEYWORDS}

**編　　號**：

<!-- 分頁 -->

# {F.TITLE}

## 摘要

{ABSTRACT}

## 壹、前言

### 一、研究動機

{cut("### 一、研究動機" + chr(10), "### 二、研究目的")}

### 二、研究目的

{AIMS.split(chr(10))[0]}

{(chr(10) * 2).join(f"（{cn(i)}）{t}" for i, t in enumerate(OBJ, 1))}

{swap(para("**H₁**"), "**H₁**：", "**研究假設（H₁）**：")}

### 三、文獻回顧

{LIT}

## 貳、研究設備與器材

### 一、資料來源

{swap(cut("### 一、資料來源" + chr(10), "### 二、軟硬體"), "| 資料 | 週期 |", f"**{TB['data']}、本研究使用的 NHANES 資料（本研究整理）**{chr(10) * 2}| 資料 | 週期 |")}

### 二、軟硬體

**{TB['soft']}、軟硬體（本研究整理）**

{swap(table("| 項目 | 規格 |"), "Codex（OpenAI）：唯讀之獨立稽核", f"Codex（OpenAI）：唯讀之獨立稽核、研究架構示意圖（{FG['flow']}）之繪製")}

## 參、研究過程與方法

### 一、研究過程

{{FIG:flow}}

**{FG['flow']}、研究架構示意圖（本研究繪製）**

本研究依七個研究目的依序進行（{FG['flow']}）：先建立可回推的資料基礎（目的一）；再以同一套常規檢驗與模型，分別回推代謝、感染、免疫三個病因方向（目的二至四）；接著檢驗回推的可靠度與用途（目的五），並以上游暴露掃描界定單次公開資料「找原因」的邊界（目的六）；最後把回推結果做成網頁工具（目的七）。各目的對應之研究方法、研究結果與主要圖表如{TB['map']}。

**{TB['map']}、研究目的與對應之方法、結果（本研究整理）**

| 研究目的 | 方法 | 結果 | 主要圖表 |
|---|---|---|---|
| （一）{OL[0]} | 參之二（一）（二） | 肆之一 | {FG['sample']}、{TB['errors']} |
| （二）{OL[1]} | 參之二（三）（四） | 肆之二 | {FG['disc']}、{FG['cal']}、{TB['dm']} |
| （三）{OL[2]} | 參之二（三）（四） | 肆之三 | {FG['disc']}、{FG['cal']}、{TB['hep']}、{TB['sub']} |
| （四）{OL[3]} | 參之二（三）（四）（六） | 肆之四 | {TB['imm']} |
| （五）{OL[4]} | 參之二（五）（七） | 肆之五 | {FG['rob']}至{FG['dca']}、{TB['delta']}至{TB['bands']} |
| （六）{OL[5]} | 參之二（八） | 肆之六 | {FG['exw']} |
| （七）{OL[6]} | 參之二（五）（九） | 肆之七 | {FG['recal']}、{TB['tool']} |

註：研究品質管控（參之二（十））適用於所有目的。

### 二、研究方法

#### （一）分析樣本與三值標籤

{swap(cut("### 二、分析樣本與三值標籤" + chr(10), "### 三、檢驗量尺與資料修正"), "| 判定 | 陽性 | 陰性 | 未知 |", f"**{TB['labels']}、三值標籤之判定規則（本研究整理）**{chr(10) * 2}| 判定 | 陽性 | 陰性 | 未知 |")}

以下以「肝炎軸」「糖尿病軸」分別指回推感染方向與代謝方向的模型。

#### （二）檢驗量尺與資料修正

{swap(cut("### 三、檢驗量尺與資料修正" + chr(10), "### 四、特徵"), "| 週期 | 項目 | 官方文件 | 本研究的處理 |", f"**{TB['conv']}、各週期檢驗量尺之處理（本研究整理）**{chr(10) * 2}| 週期 | 項目 | 官方文件 | 本研究的處理 |")}

#### （三）特徵

{cut("### 四、特徵" + chr(10), "### 五、模型與巢狀評估")}

#### （四）模型與巢狀評估

{cut("### 五、模型與巢狀評估" + chr(10), "### 六、三段分區")}

感染方向另把 B 型與 C 型肝炎分開：以常規套組邏輯迴歸的外層預測，分別計算 C 型與 B 型陽性者對陰性者的 AUROC，並以 C 型或 B 型單獨作標籤重新建模。

#### （五）三段分區

{cut("### 六、三段分區" + chr(10), "### 七、穩健性與分型")}

#### （六）免疫方向之評估

抗核抗體只在 1999–2004 年剩餘血清次樣本檢驗。免疫方向的分析計畫在執行任何計算之前提交（{COMMIT_IMM}）：樣本為腎臟指標異常且在次樣本中的成人，特徵、模型與巢狀評估同（三）（四）（免疫軸沒有需要排除的近端特徵）；判定規則事先寫定——常規套組邏輯迴歸相對於只用年齡、性別的配對 ΔAUROC 大於 0，且 95% 信賴區間下限大於 0，才判為「可回推」，否則判為「無法可靠回推」。只有三個週期、2021–2023 年未檢驗抗核抗體，因此不做時間外推與外部評估；本分析以判別為主，只報告未加權結果。

#### （七）可靠度：基準比較、穩健性、外部資料與決策曲線

1. 基準比較：每個方向都與「只用年齡、性別」的模型比較，以第一次重複之配對 ΔAUROC 與 bootstrap 95% 信賴區間判讀；外部資料上的同一比較為事後分析。
2. {ROB_ITEMS[0]}
3. {ROB_ITEMS[1]}
4. {ROB_ITEMS[2]}
5. 外部資料：{para("2021–2023 年資料自 2024 年 9 月起分批釋出")}
6. 決策曲線：{DCA_M.strip().removeprefix('決策曲線')}

#### （八）上游暴露掃描

{"暴露探索" + EXW_M.rstrip("。")}；分析計畫在執行前提交（{COMMIT_EXW}）。目的在檢驗單次橫斷面資料能否找到「原因」：通過偽發現率的關聯，再以藥物適應症與同一批人的血尿比較判讀其方向。

#### （九）網頁工具與重新校準

{para("網頁工具採常規套組邏輯迴歸。")}

#### （十）研究品質管控

為避免「看到結果才改方法」與安靜發生的資料錯誤，本研究自行設計下列機制（{TB['qa']}）。

**{TB['qa']}、研究品質管控機制（本研究整理）**

{QA}

## 肆、研究結果

### 一、{OL[0]}

{{FIG:sample}}

**{FG['sample']}、分析樣本、三值標籤與 v3.2 資料修正（本研究繪製）**

{para("逐週期核對後，v3 另有三類資料錯誤")}免疫方向限於 1999–2004 年剩餘血清次樣本：腎臟指標異常且在次樣本中者 {n(IM['n'])} 人，抗核抗體 3+／4+ 陽性 {IM['n_pos']} 人（{pct(IM['prevalence'])}）。

連同前幾版的稽核，本研究共找出{CN_ERR}項能通過 SHA256 雜湊檢查的資料問題，全部依官方文件更正（{TB['errors']}）。

**{TB['errors']}、能通過雜湊檢查的資料錯誤與更正（本研究整理）**

{ERR}

### 二、{OL[1]}

{FG['disc']}與{FG['cal']}的上列為肝炎軸（感染方向）、下列為糖尿病軸（代謝方向）。{FG['disc']}的點為巢狀外層五次重複之平均、線為最小至最大，全部模型使用同一批切分；{FG['cal']}的校準器與門檻只用外層訓練資料。

{{FIG:disc}}

**{FG['disc']}、各模型之判別力：(a) AUROC、(b) 平均精確率（本研究繪製）**

{{FIG:cal}}

**{FG['cal']}、校準曲線與三段分區之實際陽性比例（本研究繪製）**

由{FG['disc']}、{FG['cal']}下列與{TB['dm']}可看出：

**{TB['dm']}、代謝方向（糖尿病軸）各模型之判別力與校準（本研究整理）**

{perf(E['糖尿病'])}

{PERF_NOTE}

1. 常規檢驗明顯優於只用年齡、性別：邏輯迴歸 AUROC {auc('糖尿病', LR):.3f}、梯度提升 {auc('糖尿病', HG):.3f}，基準為 {E['糖尿病']['M1_demographics']['auroc_mean']:.3f}；第一次重複之配對 ΔAUROC：邏輯迴歸 {dvd('糖尿病', LR)}、梯度提升 {dvd('糖尿病', HG)}。
2. 非線性模型較高：梯度提升減邏輯迴歸之配對 ΔAUROC {dauc('糖尿病', 'HGB_routine−LR_routine')}，五次重複平均差 {mdiff('糖尿病', HG, LR)}。
3. 校準良好：兩種模型經保序校準後，截距接近 0、斜率接近 1（{FG['cal']} (a2)）；梯度提升的 Brier 分數較低（{cal('糖尿病', HG)['brier']:.4f} 對 {cal('糖尿病', LR)['brier']:.4f}）。
4. 補回 HDL 的影響很小：配對 ΔAUROC {dauc('糖尿病', 'LR_routine−LR_routine_noHDL')}。

### 三、{OL[2]}

#### （一）判別力與校準

由{FG['disc']}、{FG['cal']}上列與{TB['hep']}可看出：

**{TB['hep']}、感染方向（肝炎軸）各模型之判別力與校準（本研究整理）**

{perf(E['肝炎'])}

{PERF_NOTE}

1. 常規檢驗優於只用年齡、性別：邏輯迴歸 AUROC {auc('肝炎', LR):.3f}，基準為 {E['肝炎']['M1_demographics']['auroc_mean']:.3f}，配對 ΔAUROC {dvd('肝炎', LR)}；AP {ap('肝炎', LR):.3f} 是盛行率 {pct(E['肝炎']['prevalence'])} 的 {ap('肝炎', LR) / E['肝炎']['prevalence']:.1f} 倍。
2. 非線性模型沒有優勢：梯度提升減邏輯迴歸之配對 ΔAUROC {dauc('肝炎', 'HGB_routine−LR_routine')}，五次重複平均差 {mdiff('肝炎', HG, LR)}；梯度提升校準斜率 {cal('肝炎', HG)['slope']:.2f}，邏輯迴歸為 {cal('肝炎', LR)['slope']:.2f}。
3. 補回 HDL 的影響很小：配對 ΔAUROC {dauc('肝炎', 'LR_routine−LR_routine_noHDL')}。

#### （二）C 型與 B 型肝炎

把 B 型與 C 型肝炎分開後，差異很明顯（{TB['sub']}）。

**{TB['sub']}、感染方向之 C 型與 B 型肝炎（常規套組邏輯迴歸之外層預測）（本研究整理）**

{table("**表4　")}

{para("以 C 型或 B 型單獨作標籤重新建模")}

### 四、{OL[3]}

**{TB['imm']}、免疫方向（抗核抗體）各模型之判別力與校準（本研究整理）**

{perf(IM)}

{PERF_NOTE}

{para("腎臟指標異常且在抗核抗體次樣本者")}

由{TB['imm']}可看出，五個模型的 AUROC 介於 {min(IM_AUC):.3f} 與 {max(IM_AUC):.3f}，都低於只用年齡、性別的 {IM1:.3f}；校準斜率都小於 0.6。

### 五、{OL[4]}

#### （一）與只用年齡、性別的基準比較

常規檢驗是否真的比只用年齡、性別更能回推，是研究假設 H₁ 的核心（{TB['delta']}）。

**{TB['delta']}、常規檢驗相對於只用年齡、性別之判別增益（ΔAUROC 與 95% 信賴區間）（本研究整理）**

| 病因方向 | 模型 | 內部：1999–2018 年（第一次重複之配對差） | 外部：2021–2023 年（事後分析） |
|---|---|---|---|
| 代謝（糖尿病軸） | 邏輯迴歸 | {dvd('糖尿病', LR)} | {xd('糖尿病', 'LR_routine−M1_demographics')} |
| 代謝（糖尿病軸） | 梯度提升 | {dvd('糖尿病', HG)} | {xd('糖尿病', 'HGB_routine−M1_demographics')} |
| 感染（肝炎軸） | 邏輯迴歸 | {dvd('肝炎', LR)} | {xd('肝炎', 'LR_routine−M1_demographics')} |
| 感染（肝炎軸） | 梯度提升 | {dvd('肝炎', HG)} | {xd('肝炎', 'HGB_routine−M1_demographics')} |
| 免疫（抗核抗體） | 邏輯迴歸 | {sgn(IMD['d_auroc'])}（95% CI {ci(IMD['ci95']['d_auroc'])}） | 無資料（未檢驗抗核抗體） |
| 免疫（抗核抗體） | 梯度提升 | {sgn(IMH_D['d_auroc'])}（95% CI {ci(IMH_D['ci95']['d_auroc'])}） | 無資料 |

代謝方向在內部與外部資料上都明顯為正；感染方向內部為正，外部只有 {X['肝炎']['n_pos']} 名陽性，信賴區間跨過 0 且極寬；免疫方向在內部即不為正。

#### （二）穩健性

{{FIG:rob}}

**{FG['rob']}、穩健性分析（本研究繪製）**

**{TB['rob']}、穩健性分析（本研究整理）**

{table("**表3　")}

{para("時間外推時，評估週期的糖尿病比例")}

#### （三）2021–2023 年外部資料

{{FIG:ext}}

**{FG['ext']}、2021–2023 年外部資料之判別力（本研究繪製）**

{FG['ext']}中灰色為 v3 事前指定之一次評估、彩色為 v3.2 事後評估；數值見{TB['ext']}。

**{TB['ext']}、2021–2023 年外部資料之判別與校準（本研究整理）**

{table("**表5　")}

{para("1. 糖尿病軸在新資料上大致維持")}

#### （四）三段分區與決策曲線

三段分區決定工具能對多少人給出方向（{FG['cal']} (b)、{TB['bands']}）。糖尿病軸的梯度提升能給出方向的比例由 {pct(band('糖尿病', LR)['coverage'])} 升至 {pct(band('糖尿病', HG)['coverage'])}，且傾向區與不傾向區分得更開；肝炎軸的梯度提升則降為 {pct(band('肝炎', HG)['coverage'])}（邏輯迴歸 {pct(band('肝炎', LR)['coverage'])}）。

**{TB['bands']}、三段分區之實際陽性比例（工具規則，第一次重複之外層預測）（本研究整理）**

{BANDS}

{para("註：能給出方向的比例")}

由{FG['dca']}可看出：{para("肝炎軸在閾值 0.5% 時")}

{{FIG:dca}}

**{FG['dca']}、決策曲線（本研究繪製）**

### 六、{OL[5]}

{{FIG:exw}}

**{FG['exw']}、同一批受試者之血中與尿中鉛、鎘（勝算比為濃度加倍）（本研究繪製）**

{EXW['n_scanned']} 個暴露中 {EXW['n_significant_fdr05']} 個通過偽發現率 0.05。資料修正使 2017–2018 年 {EC['label_changes']['n_changed']} 人的腎臟結果改變；與修正前資料的結果相比，沒有任何暴露改變顯著與否。

通過校正的關聯分不出誰先誰後：護腎藥 ACEI／ARB 呈正相關（OR {xo('藥_ACEI_ARB')['OR']:.2f}），腎功能差時應停用的雙胍類呈負相關（OR {xo('藥_雙胍')['OR']:.2f}），都可由適應症與反向因果解釋，不能當作致病證據。在同時有血、尿值的同一批 {n(Pb['n_both'])} 人中，血鉛與 eGFR < 60 正相關（濃度加倍之 OR {pbm('血中')['OR_per_doubling']:.2f}），尿鉛卻呈負相關（{pbm('尿中_原濃度')['OR_per_doubling']:.2f}）（{FG['exw']}）；尿中金屬的方向取決於結果定義與寫法。前一版「血中升、尿中降就是反向因果的直接證據」建立在沒有共同受試者的比較上，已撤回。

另一個邊界在資料本身：{TB['errors']}的{CN_ERR}項錯誤都能通過雜湊檢查，程式不會報錯。

### 七、{OL[6]}

{{FIG:recal}}

**{FG['recal']}、重新校準之交叉驗證（本研究繪製）**

{FG['recal']}為依抽樣設計把 2021–2023 年資料切半 200 次的結果：點為中位數，線為 2.5–97.5 百分位。

**{TB['tool']}、網頁工具 v3.2（本研究整理）**

{table("**表6　")}

{para("糖尿病軸在另一半資料上")}

## 伍、討論

### 一、三個病因方向能回推到哪裡

綜合肆之二至肆之五，三個病因方向的回推能力整理如{TB['synth']}。

**{TB['synth']}、三個病因方向的回推結果總覽（本研究整理）**

| 病因方向 | 標籤 | 能否回推 | 主要依據 | 界線 |
|---|---|---|---|---|
| 代謝 | 糖尿病 | 可以回推 | 內部與 2021–2023 年都明顯優於只用年齡、性別，校準良好（{TB['dm']}、{TB['delta']}） | 機率不能直接移植到組成不同的人群 |
| 感染 | 病毒性肝炎 | 只能部分回推 | 內部優於只用年齡、性別，訊號來自 C 型肝炎（{TB['hep']}、{TB['sub']}） | 對 B 型幾乎沒有訊號；外部陽性太少，無法確認 |
| 免疫 | 抗核抗體 | 回推不了 | 所有模型都未優於只用年齡、性別（{TB['imm']}） | 公開資料缺補體與病理；抗核抗體陽性不等於免疫性腎炎 |

依事先寫定的判定方式——常規檢驗相對於只用年齡、性別的配對 ΔAUROC，其 95% 信賴區間下限大於 0（{TB['delta']}）——H₁ 在代謝方向成立，且在 2021–2023 年資料上仍成立（外部比較為事後分析）；感染方向在內部成立，外部只有 {X['肝炎']['n_pos']} 名陽性，無法確認或否定；免疫方向不成立。因此 H₁ **部分成立**。

### 二、代謝方向：非線性模型帶來什麼

{swap(cut("### 二、非線性模型帶來什麼" + chr(10), "### 三、肝炎軸其實是 C 型肝炎軸"), "（表3）", f"（{TB['rob']}）")}

### 三、感染方向：其實是 C 型肝炎方向

{cut("### 三、肝炎軸其實是 C 型肝炎軸" + chr(10), "### 四、雜湊抓不到的錯誤")}

### 四、免疫方向：公開資料的天花板

{IM_SENT}抗核抗體陽性的 {IM['n_pos']} 人中，只有 {IM['any_specific_among_pos']} 人有任一特異自體抗體陽性，與狼瘡最相關的 Sm 抗體只有 {IM['sle_antibodies_among_pos']['Sm']} 人（肆之四）。抗核抗體陽性不等於免疫性腎炎；以這樣的標籤，常規檢驗找不到訊號並不意外。要回推免疫方向，需要補體或腎臟病理等更接近病因的標籤。

### 五、資料來源正確不等於分析正確

本研究最重要的方法學教訓是：資料來源正確，不等於分析正確。{TB['errors']}的{CN_ERR}項問題都能通過 SHA256 檢查。{para("這些錯誤都不會讓程式當掉")}

### 六、回推病因方向的意義與界線

{swap(cut("### 五、回推病因方向的意義與界線" + chr(10), "### 六、研究限制"), IM_SENT, "")}

### 七、研究限制

{cut("### 六、研究限制" + chr(10), "### 七、未來展望")}

### 八、未來展望

{cut("### 七、未來展望" + chr(10), "## 陸、結論")}

## 陸、結論

本研究以美國 NHANES 公開資料，檢驗一般健檢的常規抽血、驗尿能否回推腎炎（腎損傷）的病因方向。**三個方向中，代謝方向可以回推、感染方向只能部分回推、免疫方向回推不了；回推的是方向，不是確診。**主要結論依序對應研究目的（一）至（七）：

{chr(10).join(f"{i}. **{lab}（目的{cn(i)}）**：{txt}" for i, (lab, txt) in enumerate(CONC, 1))}

## 柒、參考文獻資料

{{REFERENCES}}

## 附錄

{swap(swap(SRC[SRC.index("## 附錄" + chr(10)) + len("## 附錄" + chr(10)):].strip(chr(10)), "`build_fair_v3_2.py`；", "`build_fair_v3_2.py` → `make_figures_fair.py` → `build_fair_award.py`；"),
       SRC[SRC.index("重要提交："):SRC.index("v3.2 重現入口")], f"各分析計畫之提交代碼見{TB['qa']}，外部確認之協定、修正與結果見參之二（七）。")}
"""


def check_numbering(text):
    """圖、表之圖說依序出現、不缺號不重號；內文引用之圖表都存在；不再有阿拉伯數字之舊編號。"""
    for kind, keys in (("圖", FG), ("表", TB)):
        caps = re.findall(rf"^\*\*{kind}([一二三四五六七八九十]+)、", text, re.M)
        assert caps == [v[1:] for v in keys.values()], (kind, caps)
        refs = set(re.findall(rf"{kind}([一二三四五六七八九十]+)", text))
        assert refs <= set(caps), (kind, refs - set(caps))
    assert not re.search(r"[圖表][0-9]", text), re.search(r".{20}[圖表][0-9].{20}", text)


def emit(fmt):
    text, refs = F.render_citations(BODY)
    text = text.replace("{REFERENCES}", "\n\n".join(refs))
    for k, f in FIGFILE.items():
        text = swap(text, "{FIG:" + k + "}", f"![[figure/fair/{f}{'|%d' % FIGW[k] if k in FIGW else ''}]]" if fmt == "vault" else f"![](../kidney_cause/figures/fair/{f})")
    assert "{" not in text and "[@" not in text, "仍有未處理之欄位或引用"
    check_numbering(text)
    return text, refs


def main():
    vault_txt, refs = emit("vault")
    repo_txt, _ = emit("repo")
    fm = ("---\ntitle: 科展作品說明書 v3.2（得獎作品寫法）\ndate: 2026-09-28\ntags: [腎臟研究, 科展, 說明書]\n"
          "待辦:\n  - 研究動機（壹之一）請填真實經驗\n  - 組別與科別請依參賽身分確認\n  - 延續性研究說明表與參與比重\n"
          "  - AI 輔助工具之使用聲明依比賽規定確認\n  - 附錄三是否附儲存庫網址（匿名規定）\n---\n\n")
    note = ("> [!info] 由 `experiments/kidney_cause/build_fair_award.py` 自結果檔產生（數字不手打），內容與 [[科展作品說明書_v3.2]] 同源，"
            "寫法改依近年全國科展得獎作品：研究結果各節與研究目的同名、圖表以中文數字編號。可直接在此筆記修改（重跑產生程式預設不覆蓋已修改的筆記）；"
            "Word 以 `md2docx.py <本檔> --fair` 轉出。全文不得出現校名與姓名。\n\n")
    dst_fig = os.path.join(F.VAULT, "figure", "fair")
    os.makedirs(dst_fig, exist_ok=True)
    for f in FIGFILE.values():
        shutil.copy2(os.path.join(F.ROOT, "figures", "fair", f), os.path.join(dst_fig, f))
    write(os.path.join(F.VAULT, f"{NAME}.md"), fm + note + vault_txt, guard=True)
    write(os.path.join(F.REPO_DOCS, f"{NAME}.md"), repo_txt, guard=False)
    body = vault_txt.split("## 摘要", 1)[1]
    print(f"摘要 {len(ABSTRACT)} 字（上限 300）｜參考文獻 {len(refs)} 筆｜圖 {len(FG)}｜表 {len(TB)}｜內文約 {len(body):,} 字元")


if __name__ == "__main__":
    main()
