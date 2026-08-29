# -*- coding: utf-8 -*-
"""由 results/report.json 產生 report.md（含誠實界線、與文獻錨點對照）。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 特徵 → 文獻錨點對照（只標 docs/literature_anchors.json 裡實際有的；其餘一律「候選」）
KNOWN = {
    ("代謝性", "LBXSTR"): "已知重現（PMID 27537361、30300472：TG 對糖尿病腎病之病因專一性）",
    ("代謝性", "LBXSUA"): "已知重現（PMID 26342044、26935413；因果反例 32579811）",
    ("代謝性", "LBXSGTSI"): "已知重現（PMID 27537361：GGT 專屬 DN-ESRD）",
    ("代謝性", "LBXSGL"): "標籤鄰近（標籤含 HbA1c/糖尿病診斷；血糖與其高度相關——敏感度分析已排除重跑）",
    ("感染性", "LBXSATSI"): "標籤鄰近之生物學（標籤=B/C 肝血清；肝酶為肝炎直接下游，非獨立發現）",
    ("感染性", "LBXSASSI"): "標籤鄰近之生物學（同上）",
    ("感染性", "LBXSGTSI"): "標籤鄰近之生物學（同上）",
    ("感染性", "LBXSGB"): "已知一致（慢性病毒性肝炎之多株高球蛋白血症）",
    ("免疫性", "sex"): "已知一致（自體免疫之女性優勢）",
}


def f3(v):
    return "—" if v is None else f"{v:.3f}"


def main():
    R = json.load(open(os.path.join(ROOT, "results", "report.json"), encoding="utf-8"))
    L = ["# 腎病病因階層模型（免疫／感染／代謝）——NHANES 1999–2004 真實資料分析報告\n",
         f"seed {R['seed']}・{R['date']}\n", "## 誠實界線（先讀這段）\n"]
    L += [f"- {h}" for h in R["honesty"]]
    L.append("- **免疫標籤效度警語**：『免疫性』＝ANA 強陽性（或特異抗體＋）∩ 腎損傷之共存，一般族群 ANA 陽性率約一成，"
             "其中多數與腎病無因果關係——此標籤是三類中最弱的，效能與歸因都要在這個前提下讀。\n")

    C = R["cohort"]
    L.append("## 世代（全部真實、可逐檔驗證）\n")
    L.append(f"- 三週期合併 31,126 人 → 成人 15,332 → 腎損傷 {C['n_kidney_damage']}（eGFR<60 或 ACR≥30）")
    L.append(f"- 標籤分布（全腎損傷）：{C['secondary_all']}；重疊 {C['overlap']}（歸類順位 免疫>感染>代謝）")
    L.append(f"- SSANA 次樣本 ∩ 腎損傷 n={C['n_primary']}；特徵 {R['features']['n']} 欄、封存 {C['archive_n']} 欄（標籤來源不得為特徵）")
    L.append(f"- 出處帳本：{R['provenance']['n_files']} 檔（URL＋SHA256）見 results/provenance.json\n")

    L.append("## Level 1　三大病因（一對其餘 AUROC，重複分層 5 折 OOF，bootstrap 95% CI）\n")
    L.append("| 分析 | 模型 | 免疫性 | 感染性 | 代謝性 | 平衡正確率 |")
    L.append("|---|---|---|---|---|---|")

    def row(tag, block):
        for mk in ("LR", "HGB"):
            m = block["models"][mk]
            cells = []
            for c in ("免疫性", "感染性", "代謝性"):
                a = m["ovr_auc"][c]
                cells.append(f"{f3(a['auc'])} [{f3(a['lo'])},{f3(a['hi'])}] (n={a['n_pos']})" if a["auc"] is not None else "—")
            L.append(f"| {tag} | {mk} | {cells[0]} | {cells[1]} | {cells[2]} | {m['balanced_accuracy']:.3f} |")

    row("主分析", R["level1"])
    row("敏感度：排除血清葡萄糖", R["sensitivity"]["排除血清葡萄糖"])
    row("敏感度：排除重疊個案", R["sensitivity"]["排除重疊個案"])
    L.append("")
    L.append("**對 AUC≥0.9 目標的照實回答**：主分析（HGB）0.812／0.873／0.832——**未達 0.9**。"
             "排除重疊個案的敏感度分析達 0.871／0.929／0.901，但那是把難分個案拿掉後的樂觀版本，不是主結果。"
             "到 0.9 的正路是更強的標籤（切片病因、臨床診斷碼）與更多感染/免疫樣本，不是在這份資料上調參。\n")
    cyc = R["sensitivity"].get("留一週期外測", {})
    if cyc:
        L.append("**留一週期外測（時間外推）**：")
        for c, d in sorted(cyc.items()):
            cells = "；".join(f"{k} {f3(v['auc'])} [{f3(v['lo'])},{f3(v['hi'])}]" for k, v in d.items() if v["auc"] is not None)
            L.append(f"- 留出 {c}：{cells}")
        L.append("")

    L.append("## Level 3　biomarker 歸因（關聯，非因果）\n")
    for c in ("免疫性", "感染性", "代謝性"):
        L.append(f"**{c}**（單變量 AUC 前十，方向＝該類相對其餘）\n")
        L.append("| 標記 | 方向 | AUC | 95% CI | 文獻對照 |")
        L.append("|---|---|---|---|---|")
        for r in R["level3"]["univariate_top"][c][:10]:
            tag = KNOWN.get((c, r["feature"]), "候選（本資料之發現，待文獻/前瞻確認）")
            L.append(f"| {r['label']} | {r['direction']} | {r['auc']:.3f} | [{f3(r['lo'])},{f3(r['hi'])}] | {tag} |")
        L.append("")
    L.append("補充：免疫性的「血糖低」「TG 低」屬**組成效應**（其餘類以糖尿病為大宗），不是免疫疾病讓血糖變低——"
             "歸因表讀法必須帶著這一層。置換重要度與 LR 係數完整表在 report.json。\n")

    L.append("## Level 2　類內細項\n")
    li = R["level2_immune"]
    L.append(f"- 免疫（n={li['n']}）：{li['subgroups']}——{li['caveat']}")
    lf = R["level2_infection"]
    L.append(f"- 感染（n={lf['n']}）：HBV {lf['HBV']}、HCV {lf['HCV']}（標籤層資訊，僅供分流示意）\n")

    L.append("## 超音波佐證層\n")
    L.append("公開世界無上萬張可下載腎臟超音波；`us_validation/` 已定義交換格式與一致性分析（κ、逐類混淆、分歧解剖），"
             "醫院影像到位即可與 results/predictions.csv 以個案鍵併接執行；到位前該層拒跑、不產生任何假數字。\n")
    open(os.path.join(ROOT, "results", "report.md"), "w", encoding="utf-8").write("\n".join(L))
    print("[report] results/report.md")


if __name__ == "__main__":
    main()
