# -*- coding: utf-8 -*-
"""研究計畫書 V3（完整版）——八段式，與科展作品說明書 v3.2 同源，數字全由結果檔產生。
    python build_plan_v3.py [--force]
全文取自 build_fair_v3_2.emit()（已驗證之內容、圖與 APA 參考文獻），改排為研究計劃書 V_2 的八段格式，另加計畫書才有的三段：
貳之一 核心問題、柒之一 研究結論（回答「能不能找原因」）、捌之二 研究進度。只用公開資料（2026-09-28 使用者決定）。
輸出：Obsidian 主稿 研究計畫書/研究計劃書V_3.md（在 Obsidian 修改、定稿後再轉 Word；主稿已被修改時預設不覆蓋，--force 才覆蓋）
與 repo 副本 experiments/docs/科展計畫書_v3.md。"""
import os
import subprocess
import sys

import build_fair_v3_2 as F
from build_fair_v3_2 import CK, E, EXW, HG, IM, IM1, IMD, IML, LR, SL, X, auc, ci, dca0, n, sgn

VAULT_MD = os.path.join(F.VAULT, "研究計劃書V_3.md")
REPO_MD = os.path.join(F.REPO_DOCS, "科展計畫書_v3.md")
CN = "〇一二三四五六七八九十"


def cut(t, a, b=None):
    assert t.count(a) == 1, a
    i = t.index(a) + len(a)
    return t[i:t.index(b, i)] if b else t[i:]


def day(sha):
    return subprocess.run(["git", "show", "-s", "--format=%ad", "--date=short", sha], cwd=F.ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


# ── 柒之一「研究結論」之數字與方向斷言（全部來自結果檔）
XW = {r["exposure"]: r for r in EXW["results"]}
xo = lambda e: XW[e]["headline"]
pbm = lambda k: CK["metals"]["鉛"]["models"]["egfr_lt60"][k]
xa = lambda ax, s: X[ax]["models"][s]["auroc"]
xm1 = lambda ax: X[ax]["M1_demographics"]["auroc"]
C_ONLY, B_ONLY = SL["僅C型_HCV_RNA"]["auroc"], SL["僅B型_HBsAg"]["auroc"]
H0 = dca0("肝炎", LR)
assert B_ONLY < 0.6 < C_ONLY, "B／C 型肝炎之敘述不成立"
assert auc("糖尿病", HG) > auc("糖尿病", LR) > E["糖尿病"]["M1_demographics"]["auroc_mean"], "內部糖尿病之敘述不成立"
assert min(xa("糖尿病", LR), xa("糖尿病", HG)) > xm1("糖尿病") and xa("肝炎", LR) <= xm1("肝炎"), "外部資料之敘述不成立"
assert H0["pt"] == 0.005 and abs(H0["nb_model"] - H0["nb_test_all"]) < 0.001, "肝炎決策曲線之敘述不成立"
assert XW["藥_ACEI_ARB"]["significant_fdr05"] and xo("藥_ACEI_ARB")["OR"] > 1
assert XW["藥_雙胍"]["significant_fdr05"] and xo("藥_雙胍")["OR"] < 1
assert pbm("血中")["ci"][0] > 1 and pbm("尿中_原濃度")["ci"][1] < 1

MILESTONES = [   # (階段, 內容, 提交)——日期取自 git
    ("v1", "NHANES 1999–2004 真實資料、出處帳本、三類病因模型", ["d5a16da"]),
    ("v2", "擴充至 NHANES 1999–2018 十個週期", ["4cf0dcf", "e4ab5c0"]),
    ("v3", "依外部方法學審查以真實資料重建：三值標籤、巢狀評估", ["bf269c5", "d5140a9"]),
    ("外部確認", "NHANES 2021–2023：協定 → 評估前修正一 → 一次評估", ["9ca4e9f", "44b0ace", "a7c4af8"]),
    ("網頁工具 v3.1", "常規套組模型，以 2021–2023 年資料重新校準", ["59a2455"]),
    ("設計變異", "依 PSU 與分層之刪一摺刀法", ["9edd968", "e7d16e4"]),
    ("v3.2", "三類資料修正後重建、非線性模型校準、網頁工具 v3.2", ["f6abc91", "4d48842"]),
    ("獨立稽核", "工具規則之分區統計、外部年齡性別基準", ["95e9db4"]),
    ("暴露分析 v3.2", "以 v3.2 資料修正重跑", ["6737bf5", "4cd396b"]),
    ("只用公開資料", "研究範圍定為公開資料", ["a21cf7c"]),
    ("免疫方向 v3.2", "以公開抗核抗體次樣本，在修正後資料上重跑", ["29e1d3b", "9eb8cf6"]),
]


def build(fmt):
    t, _ = F.emit(fmt)
    t = t.replace("本作品", "本研究").replace("本說明書", "本計畫書").replace("<!-- 分頁 -->\n", "")
    t = t[t.index(f"# {F.TITLE}\n"):]
    ABS = cut(t, "## 摘要\n", "## 壹、前言")
    MOT = cut(t, "### 一、研究動機\n", "### 二、研究目的")
    OBJ = cut(t, "### 二、研究目的\n", "### 三、文獻回顧")
    LIT = cut(t, "### 三、文獻回顧\n", "## 貳、研究設備與器材")
    EQUIP = cut(t, "## 貳、研究設備與器材\n", "## 參、研究過程與方法")
    METH = cut(t, "## 參、研究過程與方法\n", "## 肆、研究結果")
    RES = cut(t, "## 肆、研究結果\n", "## 伍、討論")
    DISC = cut(t, "## 伍、討論\n", "## 陸、結論")
    CONC = cut(t, "## 陸、結論\n", "## 柒、參考文獻資料")
    REFS = cut(t, "## 柒、參考文獻資料\n", "## 附錄")
    APPX = cut(t, "## 附錄\n").replace("\n### 附錄", "\n#### 附錄")
    for h in ("### 三、檢驗量尺與資料修正", "### 八、決策曲線與暴露探索"):      # 貳之一引用之肆之三、肆之八
        assert h in METH, h
    errs = cut(DISC, "### 四、雜湊抓不到的錯誤\n", "### 五、")
    n_err = sum(1 for line in errs.split("\n") if line.startswith("| v3"))
    assert f"{CN[n_err]}項能通過雜湊檢查" in CONC, "錯誤項數與結論不一致"
    rows = "\n".join(f"| {v} | {day(c[-1])} | {d} | {' → '.join(c)} |" for v, d, c in MILESTONES)
    return f"""# {F.TITLE}

## ——研究計畫書（完整版）：只用公開資料，以常規抽血驗尿回推腎炎（腎損傷）的病因方向（感染、免疫、代謝）

## 摘要
{ABS}
## 壹、研究動機

### 一、研究動機
{MOT}
### 二、研究背景與文獻回顧
{LIT}
## 貳、研究目的

### 一、核心問題：回推腎炎的病因方向

本研究的核心問題是：腎炎（腎損傷）時，能不能用健檢原本就有的常規血液與尿液檢驗，往回推出病因方向——感染、免疫，還是代謝？本研究只使用公開、去識別化的 NHANES 資料。NHANES 沒有腎炎診斷，以腎臟指標異常（eGFR < 60 或 ACR ≧ 30）作為腎炎（腎損傷）的操作型定義；三個病因方向各以一個可驗證的標籤代表：

| 病因方向 | 標籤（操作型定義） | 可用資料 |
|---|---|---|
| 感染 | 病毒性肝炎：HBsAg 或 HCV RNA 陽性 | 1999–2018 年；另以 2021–2023 年評估 |
| 代謝 | 糖尿病：醫師診斷或 HbA1c ≧ 6.5% | 1999–2018 年；另以 2021–2023 年評估 |
| 免疫 | 抗核抗體：1:80 稀釋 3+／4+ | 1999–2004 年剩餘血清次樣本 |

回推的是「方向」（候選病因），不是確診：標籤成立不代表腎損傷由該病造成（貳之二的 H₁）。本研究同時實證公開、單次的健檢資料在「找原因」上的邊界：上游暴露掃描（肆之八）與逐週期資料稽核（肆之三）。

### 二、研究假設與具體目的
{OBJ}
## 參、研究設備及器材
{EQUIP}
## 肆、研究過程或方法
{METH}
## 伍、研究結果
{RES}
## 陸、討論
{DISC}
## 柒、結論

### 一、研究結論：回推腎炎的病因方向

**三個方向中，代謝方向可以回推、感染方向只能部分回推、免疫方向回推不了；回推的是方向，不是確診。**

1. **代謝方向（糖尿病）：可以回推。** 在腎炎（腎損傷）成人中，內部巢狀交叉驗證 AUROC {auc('糖尿病', LR):.3f}（邏輯迴歸）、{auc('糖尿病', HG):.3f}（梯度提升）；NHANES 2021–2023 年（事後評估）{xa('糖尿病', LR):.3f}、{xa('糖尿病', HG):.3f}，同一批人只用年齡、性別為 {xm1('糖尿病'):.3f}。
2. **感染方向（病毒性肝炎）：只能部分回推。** 只看 C 型肝炎 AUROC {C_ONLY:.3f}；B 型肝炎只有 {B_ONLY:.3f}，幾乎辨識不出。新資料只有 {X['肝炎']['n_pos']} 名陽性，邏輯迴歸 {xa('肝炎', LR):.3f} 未高於只用年齡、性別的 {xm1('肝炎'):.3f}，無法確認。
3. **免疫方向（抗核抗體）：回推不了。** {n(IM['n'])} 人中 {IM['n_pos']} 人陽性；常規檢驗 AUROC {IML:.3f}，未優於只用年齡、性別的 {IM1:.3f}（配對 ΔAUROC {sgn(IMD['d_auroc'])}，95% CI {ci(IMD['ci95']['d_auroc'])}）。公開資料缺補體與病理，是這一方向的天花板。
4. **方向不能拿來省略檢驗。** 肝炎軸在閾值 0.5% 時，依模型送驗與全數送驗的淨效益幾乎相同（{H0['nb_model']:.4f} 對 {H0['nb_test_all']:.4f}）；肝炎血清檢驗便宜、無創，且指引建議成人普遍篩檢。
5. **暴露掃描找不到可確認的原因。** {EXW['n_scanned']} 個上游暴露中 {EXW['n_significant_fdr05']} 個通過偽發現率校正，但單次橫斷面資料分不出誰先誰後：護腎藥 ACEI／ARB 呈正相關（OR {xo('藥_ACEI_ARB')['OR']:.2f}）、腎功能差時應停用的雙胍類呈負相關（OR {xo('藥_雙胍')['OR']:.2f}），符合用藥適應症與反向因果；同一批人中，血鉛與 eGFR < 60 正相關（OR {pbm('血中')['OR_per_doubling']:.2f}），尿鉛卻呈負相關（OR {pbm('尿中_原濃度')['OR_per_doubling']:.2f}），符合腎臟排泄下降。這些關聯不能當作原因，也不能一律歸為反向因果。
6. **天花板在標籤，不在方法。** 公開資料沒有病理或臨床確立的病因，模型只能預測「有沒有這個病」，預測不出「腎臟異常是不是它造成的」。研究過程另找出並更正{CN[n_err]}項能通過雜湊檢查的資料問題（陸之四），說明資料來源正確不等於分析正確。
7. **下一步（只用公開資料）。** 要從關聯走到因果，需要公開的縱貫資料或公開的基因摘要統計；在那之前，本研究的結論停在「病因方向」。

### 二、各目的之結論
{CONC}
## 捌、參考資料及其他

### 一、參考文獻
{REFS}
### 二、研究進度

| 階段 | 日期 | 內容 | 提交（計畫 → 結果） |
|---|---|---|---|
{rows}

**待研究者填寫**：研究動機（壹之一）；延續性研究說明（若本主題曾參賽）；AI 輔助工具使用聲明；參賽組別。

**後續研究（只用公開資料）**：

1. NHANES 新週期釋出後，以獨立資料驗證網頁工具 v3.2 的校準（2021–2023 年資料已用於更新，不能再當驗證）。
2. 累積肝炎事件，另建 B 型肝炎的模型。
3. 以可解釋的非線性方法保留糖尿病軸的增益。
4. 以公開縱貫資料或公開基因摘要統計，檢驗關聯的因果方向。
5. 舊附錄三變數字典（352 項）改寫。

### 三、附錄
{APPX}"""


def write(path, txt, guard):
    if guard and os.path.exists(path):
        old = open(path, encoding="utf-8").read()
        if old == txt:
            print(f"[未變] {path}")
            return
        if "--force" not in sys.argv:
            sys.exit(f"[停止] {path} 已存在且內容不同（可能已在 Obsidian 修改）；確認要覆蓋請加 --force")
    open(path, "w", encoding="utf-8").write(txt)
    print(f"[寫出] {path}（{len(txt):,} 字元）")


def main():
    fm = ("---\ntitle: 研究計劃書 V3（完整版）\ntype: 研究計畫書\nversion: 3\nstatus: draft\ncreated: 2026-09-28\n"
          "supersedes: 研究計劃書V_2\ndata: NHANES 公開資料（v3.2 資料修正；只用公開資料）\n"
          "source_repo: MD.Piece/experiments/docs/科展計畫書_v3.md\ntags: [腎病病因, 科展, 研究計畫書]\ntodo:\n"
          "  - 補真實研究動機（壹之一）\n  - 延續性研究說明（若適用）\n  - AI 輔助工具使用聲明\n  - 確認參賽組別\n---\n\n")
    note = ("> [!info] 第三版（完整版）：只用公開資料；內容與 [[科展作品說明書_v3.2]] 同源，數字由 "
            "`experiments/kidney_cause/build_plan_v3.py` 自結果檔產生。可直接在此筆記修改，定稿後再轉 Word（重跑產生程式預設不覆蓋已修改的筆記）。\n"
            "> 前版 [[研究計劃書V_2]]｜配套 [[科展作品說明書_v3.2]]｜[[研究論文_v3.2]]｜[[附錄三_變數字典]]\n\n")
    head = ("> Obsidian 主稿：`腎炎模型/研究計畫書/研究計劃書V_3.md`（修改在 Obsidian 進行，此為產生時之副本）｜"
            "前版 [科展計畫書_v2](科展計畫書_v2.md)\n\n")
    vault, repo = build("vault"), build("repo")
    for bad in ("醫院", "IRB", "免審"):
        assert bad not in vault, f"計畫書含「{bad}」"
    write(VAULT_MD, fm + note + vault, guard=True)
    write(REPO_MD, head + repo, guard=False)


if __name__ == "__main__":
    main()
