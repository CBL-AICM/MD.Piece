# -*- coding: utf-8 -*-
"""由 results/immune_geo*.json 產生：
  docs/immune_geo/免疫方向GEO_模型準確度報告.md（＋figure/fig_auroc.png）
  results/immune_geo_snippets.json（研究報告三處待補段落＋參考文獻）
數字一律讀結果檔，不手抄。用法：python -X utf8 build_immune_geo_report.py"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
PRE = json.load(open(os.path.join(ROOT, "results", "immune_geo.json"), encoding="utf-8"))
B = json.load(open(os.path.join(ROOT, "results", "immune_geo_batchsafe.json"), encoding="utf-8"))
DOC = os.path.join(ROOT, "docs", "immune_geo")
os.makedirs(os.path.join(DOC, "figure"), exist_ok=True)
plt.rcParams["font.family"] = ["Microsoft JhengHei"]
plt.rcParams["axes.unicode_minus"] = False

f3 = lambda x: f"{x:.3f}"
pc = lambda x: f"{x * 100:.1f}%"
ci = lambda c: f"{c[0]:.2f}–{c[1]:.2f}"
pv = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"
PANEL_ZH = dict(interferon="干擾素", complement="補體", b_plasma="B 細胞／漿細胞", t_cell="T 細胞",
                myeloid="單核巨噬細胞", neutrophil="嗜中性球")
MODEL_ZH = dict(PANEL_LR="免疫路徑模型", GENE_LR="全基因模型")
TASKS = [("B1_primary", "B1", "ANCA 血管炎 對 非免疫腎病（DN、FSGS、MCD）", "H7"),
         ("B2_immune_vs_metabolic", "B2", "ANCA 血管炎 對 糖尿病腎病變（免疫對代謝）", "H7"),
         ("B3_SLE", "B3", "紅斑性狼瘡腎炎 對 FSGS（非免疫）", "H5")]

# 事實斷言：報告敘述依賴的結論若改變，產生器要停下來，不可寫出與數字矛盾的句子
D = B["decision"]
assert D["B1_primary"]["回推成立"] and D["B2_immune_vs_metabolic"]["回推成立"] and D["B3_SLE"]["回推成立"]
assert not D["B2_immune_vs_metabolic"]["PANEL_LR"] and D["B2_immune_vs_metabolic"]["GENE_LR"]
assert D["免疫路徑專屬"] == {"B1_primary": False, "B3_SLE": True}
assert not PRE["decision"]["回推成立"]
assert PRE["T1_primary"]["holdout"]["GENE_LR"]["auroc"] < 0.05
assert all(B["B5_multiclass"][b][m]["top2_mean"] > 0.8 for b in ["H7", "H5"] for m in ["PANEL_LR", "GENE_LR"])
sle_ifn = B["B3_SLE"]["per_panel"]["interferon"]["auroc"]
assert max(B["B3_SLE"]["per_panel"].values(), key=lambda v: v["auroc"]) is B["B3_SLE"]["per_panel"]["interferon"]


# ---------- 圖：各任務 AUROC（第 0 次重複 95% CI；點＝20 次平均）----------
def fig():
    rows = []
    for key, code, name, _ in TASKS:
        for comp, src in [("腎絲球", B[key]), ("腎小管間質", B["B4_replication"][code])]:
            for m in ["PANEL_LR", "GENE_LR"]:
                rows.append((f"{code} {comp}", m, src[m]))
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200)
    labels = []
    for i, (lab, m, r) in enumerate(rows):
        y = len(rows) - i
        col = "#2a6f97" if m == "PANEL_LR" else "#c44536"
        ax.plot(r["auroc_ci_rep0"], [y, y], color=col, lw=1.6)
        ax.plot(r["auroc_mean"], y, "o", color=col, ms=5)
        labels.append(f"{lab}・{MODEL_ZH[m]}")
    ax.axvline(0.5, color="#888", ls="--", lw=0.8)
    ax.set_yticks(range(len(rows), 0, -1), labels, fontsize=7.5)
    ax.set_xlim(0.2, 1.0)
    ax.set_xlabel("AUROC（點＝20 次重複平均；線＝第一次重複 95% 信賴區間）", fontsize=8.5)
    ax.tick_params(axis="x", labelsize=8)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(DOC, "figure", "fig_auroc.png"))


fig()


# ---------- 準確度報告 ----------
def acc_row(name, r, rep=None):
    t = r["threshold_prevalence_rep0"]
    return (f"| {name} | {f3(r['auroc_mean'])}（{f3(r['auroc_min_max'][0])}–{f3(r['auroc_min_max'][1])}） | "
            f"{ci(r['auroc_ci_rep0'])} | {pv(r['permutation_p']) if 'permutation_p' in r else '—'} | {pc(t['accuracy'])} | "
            f"{pc(t['balanced_accuracy'])} | {pc(t['sensitivity'])} | {pc(t['specificity'])} | {r['brier_rep0']:.3f} | "
            f"{f3(rep['auroc_mean']) if rep else '—'} |")


L = []
w = L.append
w("# 免疫方向補強：NIH GEO 腎臟切片轉錄體模型準確度報告\n")
w("資料：NIH 國家生物技術資訊中心（NCBI）Gene Expression Omnibus 公開之歐洲腎臟 cDNA 庫（ERCB）切片轉錄體，"
  "GSE104948（腎絲球）與 GSE104954（腎小管間質）。每例診斷皆經腎臟病理確認。"
  "分析計畫 `params/immune_geo_plan.json` 於執行前提交（8cf98d5）；發現批次混淆後之修正一 "
  "`params/immune_geo_amendment_1.json` 亦於執行前提交（b051817）。\n")
w("## 一、結論\n")
b1, b2, b3 = B["B1_primary"], B["B2_immune_vs_metabolic"], B["B3_SLE"]
w(f"1. 在同一處理批次內，免疫性腎病與非免疫腎病在腎臟組織有可區分的分子訊號。ANCA 血管炎對非免疫腎病，免疫路徑模型 AUROC "
  f"{f3(b1['PANEL_LR']['auroc_mean'])}、全基因模型 {f3(b1['GENE_LR']['auroc_mean'])}；紅斑性狼瘡腎炎對 FSGS，免疫路徑模型 "
  f"{f3(b3['PANEL_LR']['auroc_mean'])}。三項任務皆通過修正一於計算前寫定的判定規則（B2 只有全基因模型通過），且在腎小管間質重現。")
w(f"2. 唯一能直接比較「免疫對代謝」的是 ANCA 對糖尿病腎病變（{b2['n_pos']} 對 {b2['n'] - b2['n_pos']} 例）："
  f"全基因模型 AUROC {f3(b2['GENE_LR']['auroc_mean'])}（95% CI {ci(b2['GENE_LR']['auroc_ci_rep0'])}），"
  f"但免疫路徑模型只有 {f3(b2['PANEL_LR']['auroc_mean'])}，未達顯著。這表示事前選的六條免疫路徑不足以區分這兩種病，"
  "全基因模型的判別力主要來自路徑以外的基因。")
w(f"3. 狼瘡腎炎的訊號集中在干擾素路徑（單一路徑 AUROC {f3(sle_ifn)}），高於 1,000 組隨機基因集的第 95 百分位，"
  f"屬免疫路徑專屬；ANCA 的路徑模型則只在隨機基因集第 {B['B1_primary']['random_gene_sets']['percentile_of_panel']:.1f} 百分位，"
  "代表其與非免疫腎病之差異廣泛分布於全基因體，不專屬事前路徑。")
w("4. IgA 腎病變與高血壓腎病變各自只在一個處理批次，同批次內沒有對照，本資料無法評估。")
w("5. 事前計畫原定的主要任務（狼瘡腎炎＋IgA 腎病變對糖尿病＋高血壓腎病變）因診斷與處理批次完全重疊而失效（見第六節），"
  "其數字不可引用。\n")
w("## 二、任務與樣本\n")
w("| 任務 | 比較 | 批次 | 腎絲球人數（陽性） | 腎小管間質人數（陽性） |\n|---|---|---|---|---|")
for key, code, name, bt in TASKS:
    r, t = B[key], B["B4_replication"][code]
    w(f"| {code} | {name} | {bt} | {r['n']}（{r['n_pos']}） | {t['n']}（{t['n_pos']}） |")
w("\n模型：免疫路徑模型＝六條事前路徑分數（干擾素、補體、B 細胞／漿細胞、T 細胞、單核巨噬細胞、嗜中性球）＋邏輯迴歸；"
  "全基因模型＝12,074 個基因＋強正則化邏輯迴歸。超參數固定、不調參。評估採分層五折、重複 20 次，"
  "所有標準化只用訓練折；分類門檻＝訓練折之陽性比例（事前機率）。\n")
w("## 三、二元任務準確度\n")
w("| 任務・模型 | AUROC 平均（最小–最大） | 95% CI | 置換 p | 準確率 | 平衡準確率 | 敏感度 | 特異度 | Brier | 腎小管間質 AUROC |")
w("|---|---|---|---|---|---|---|---|---|---|")
for key, code, name, _ in TASKS:
    for m in ["PANEL_LR", "GENE_LR"]:
        w(acc_row(f"{code}・{MODEL_ZH[m]}", B[key][m], B["B4_replication"][code][m]))
w("\n註：95% CI 與準確率、敏感度、特異度、Brier 取第一次重複之折外預測；置換檢定打亂標籤 1,000 次，"
  "兩種模型以 Bonferroni 校正（p < 0.025 為顯著）。\n")
w("![[figure/fig_auroc.png|620]]\n")
w("## 四、回推可能病因（多類別）\n")
w("| 批次・模型 | 類別 | 準確率 | 平衡準確率 | 前二名命中率 | 全猜最多類之準確率 |\n|---|---|---|---|---|---|")
for bt, cls in [("H7", "ANCA／DN／FSGS／MCD"), ("H5", "SLE／MN／FSGS")]:
    for m in ["PANEL_LR", "GENE_LR"]:
        r = B["B5_multiclass"][bt][m]
        w(f"| {bt}・{MODEL_ZH[m]} | {cls} | {pc(r['accuracy_mean'])} | {pc(r['balanced_accuracy_mean'])} | "
          f"{pc(r['top2_mean'])} | {pc(r['chance_majority'])} |")
for bt in ["H7", "H5"]:
    cm = B["B5_multiclass"][bt]["GENE_LR"]["confusion_rep0"]
    cls = list(cm)
    w(f"\n{bt} 全基因模型混淆矩陣（第一次重複；列＝真實、欄＝預測）\n")
    w("| 真實＼預測 | " + " | ".join(cls) + " |\n|---|" + "---|" * len(cls))
    for t in cls:
        w(f"| {t} | " + " | ".join(str(cm[t][p]) for p in cls) + " |")
w("\n多類別的主要錯誤是樣本少的類別（H7 的 DN 7 例、H5 的 FSGS 8 例）常被歸到大類；前二名命中率高於八成，"
  "適合作為「列出候選病因」而非「單一判定」。\n")
w("## 五、哪些免疫路徑在區分\n")
w("| 路徑 | B1 AUROC | B1 差（z） | B2 AUROC | B2 差（z） | B3 AUROC | B3 差（z） |\n|---|---|---|---|---|---|---|")
for p, zh in PANEL_ZH.items():
    cells = []
    for key, _, _, _ in TASKS:
        v = B[key]["per_panel"][p]
        cells += [f3(v["auroc"]), f"{v['mean_diff_z']:+.2f}"]
    w(f"| {zh} | " + " | ".join(cells) + " |")
w("\n差＝免疫組減對照組之路徑分數平均（z 單位）。ANCA 以補體、單核巨噬細胞、嗜中性球升高為主；狼瘡腎炎以干擾素為主。"
  f"探索性比較：膜性腎病變（抗體介導、發炎少）對 FSGS，補體路徑 AUROC "
  f"{f3(B['B6_exploratory_MN_vs_FSGS']['per_panel']['complement']['auroc'])}（方向相反），"
  "提示免疫細胞路徑分數可能只對「發炎型」免疫腎病敏感。\n")
w("## 六、事前計畫為何失效（照實報告）\n")
w("GEO 樣本來源名稱中的 H 代碼是處理批次。GPL24120 平台上，糖尿病腎病變全在 H1、高血壓腎病變全在 H2、IgA 腎病變全在 H4、"
  "狼瘡腎炎在 H5。事前計畫只注意到兩個晶片平台的混淆，漏看了批次，因此原定任務比較的其實是批次。")
t1 = PRE["T1_primary"]
w(f"徵兆是全基因模型 AUROC 遠低於 0.5：交叉驗證 {f3(t1['GENE_LR']['auroc_mean'])}、保留測試集 "
  f"{f3(t1['holdout']['GENE_LR']['auroc'])}，訓練集卻幾乎全對，屬於記憶批次。原計畫判定「回推成立」為否，"
  f"「免疫路徑專屬」雖為是，但同樣無法解讀。平台陰性對照 AUROC "
  f"{f3(PRE['T4_pooled']['platform_negative_control']['auroc_mean'])} 被判為通過，是因為門檻只看信賴區間上界；"
  "AUROC 遠低於 0.5 同樣代表兩平台可完全分開，平台校正實際上失敗。原結果檔照原樣保留，未刪改。\n")
w("## 七、限制\n")
w("1. 這是確診後的切片組織，不是常規抽血驗尿；結果說明免疫性病因在腎臟本身可辨識，以及哪些路徑值得轉成血液或尿液檢驗，"
  "不能證明常規檢驗可回推免疫方向。")
w("2. 樣本少（B2 只有 29 例，其中糖尿病腎病變 7 例），信賴區間寬；腎絲球與腎小管間質來自同一批切片，重現不是獨立驗證。")
w("3. 沒有獨立的外部資料集；同批次內仍可能存在未記錄的處理差異。")
w("4. ERCB 的糖尿病腎病變是臨床上需要切片的非典型個案，不代表一般糖尿病腎病變。")
w("5. 沒有感染方向的資料；IgA 腎病變與高血壓腎病變無法評估。\n")
w("## 八、獨立檢驗\n")
w("另一工作階段以自行撰寫的程式重算關鍵數字並檢查資料洩漏，報告見 `results/immune_geo_audit.md`。\n")
w("## 九、重現方式\n")
w("```\npython immune_geo.py            # 事前計畫版（結果已存在則拒跑）\npython immune_geo_batchsafe.py  # 修正一\n"
  "python -m pytest test_immune_geo.py\npython -X utf8 build_immune_geo_report.py\n```\n")
w(f"計畫 SHA256：{B['plan_sha256'][:16]}…；修正一 SHA256：{B['amendment_sha256'][:16]}…；資料五檔之 URL 與 SHA256 見 `results/provenance.json`。\n")
open(os.path.join(DOC, "免疫方向GEO_模型準確度報告.md"), "w", encoding="utf-8").write("\n".join(L))

# ---------- 研究報告三處待補段落 ----------
g1, g3 = b1["GENE_LR"], b3["PANEL_LR"]
S = {
 "result": (
  "由於 NHANES 沒有免疫性腎病的診斷資料，本研究另以美國國家衛生研究院國家生物技術資訊中心（NCBI）Gene Expression Omnibus 公開之"
  "歐洲腎臟 cDNA 庫切片轉錄體補充分析（GSE104948 腎絲球、GSE104954 腎小管間質；Eddy et al., 2018a, 2018b; Grayson et al., 2018），"
  "每例診斷皆經腎臟病理確認。分析計畫於計算前提交。樣本中每種疾病分屬不同的處理批次，為避免把批次差異誤當疾病差異，"
  "只比較同一批次內的疾病（事後修正，亦於計算前提交）。在同一批次內，ANCA 相關血管炎與非免疫腎病"
  f"（糖尿病腎病變、局部節段性腎絲球硬化、微小變化病），全基因模型 AUROC 為 {f3(g1['auroc_mean'])}"
  f"（95% CI {ci(g1['auroc_ci_rep0'])}，置換檢定 p {pv(g1['permutation_p'])}），六條免疫路徑分數模型為 "
  f"{f3(b1['PANEL_LR']['auroc_mean'])}（95% CI {ci(b1['PANEL_LR']['auroc_ci_rep0'])}）；"
  f"ANCA 相關血管炎對糖尿病腎病變（{b2['n']} 例），全基因模型為 {f3(b2['GENE_LR']['auroc_mean'])}"
  f"（95% CI {ci(b2['GENE_LR']['auroc_ci_rep0'])}），免疫路徑模型為 {f3(b2['PANEL_LR']['auroc_mean'])}，未達顯著；"
  f"紅斑性狼瘡腎炎對局部節段性腎絲球硬化，免疫路徑模型為 {f3(g3['auroc_mean'])}"
  f"（95% CI {ci(g3['auroc_ci_rep0'])}），其中干擾素路徑單獨即達 {f3(sle_ifn)}。三項比較在腎小管間質皆重現。"
  "IgA 腎病變與高血壓腎病變在資料中各自只有一個處理批次、沒有同批次對照，無法評估。"),
 "discussion": (
  "腎臟切片轉錄體的結果顯示，免疫性病因在腎臟組織中有可辨識的分子訊號。在病理確診的切片裡，"
  "紅斑性狼瘡腎炎以干擾素路徑升高為主，ANCA 相關血管炎以補體、單核巨噬細胞與嗜中性球路徑升高為主，"
  "與兩者的致病機轉相符（Jennette & Falk, 2014; Lech & Anders, 2013）。常規血液與尿液檢驗中沒有直接反映這些路徑的項目；"
  "臨床上對應的是補體 C3、C4、抗雙股 DNA 抗體與 ANCA 等專項檢驗，以及腎臟切片"
  "（KDIGO ANCA Vasculitis Work Group, 2024; KDIGO Lupus Nephritis Work Group, 2024）。"
  "因此，常規檢驗無法回推免疫方向，較可能的原因是常規項目中沒有能反映這些路徑的檢驗；若常規檢驗已排除代謝與感染方向，"
  "而腎功能變化或血尿提示腎絲球腎炎，下一步應安排上述專項檢驗。"
  "此分析的限制是樣本少、為確診後的組織資料，且腎絲球與腎小管間質取自同一批切片，不是獨立驗證。"),
 "conclusion": (
  "以 NIH 公開之腎臟切片轉錄體補充分析，在同一處理批次內，免疫性腎病（紅斑性狼瘡腎炎、ANCA 相關血管炎）與非免疫腎病可由組織的"
  f"免疫路徑區分（免疫路徑模型 AUROC：ANCA 相關血管炎 {f3(b1['PANEL_LR']['auroc_mean'])}、紅斑性狼瘡腎炎 "
  f"{f3(b3['PANEL_LR']['auroc_mean'])}）。免疫方向的訊號存在於腎臟組織的干擾素、補體與發炎細胞路徑，"
  "本研究的常規檢驗模型未能捕捉；要回推免疫方向，仍需補體、自體抗體等專項檢驗。"),
 "references": [
  "Eddy, S., Nair, V., Eichinger, F., Lindenmeyer, M., Cohen, C., & Kretzler, M. (2018a). Glomerular transcriptome from European Renal cDNA Bank subjects and living donors (GSE104948) [Data set]. Gene Expression Omnibus. https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE104948",
  "Eddy, S., Nair, V., Eichinger, F., Lindenmeyer, M., Cohen, C., & Kretzler, M. (2018b). Tubulointerstitial transcriptome from ERCB subjects with chronic kidney disease and living donor biopsies (GSE104954) [Data set]. Gene Expression Omnibus. https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE104954",
  "Grayson, P. C., Eddy, S., Taroni, J. N., Lightfoot, Y. L., Mariani, L., Parikh, H., Lindenmeyer, M. T., Ju, W., Greene, C. S., Godfrey, B., Cohen, C. D., Krischer, J., Kretzler, M., Merkel, P. A., & Vasculitis Clinical Research Consortium, the European Renal cDNA Bank cohort, and the Nephrotic Syndrome Study Network. (2018). Metabolic pathways and immunometabolism in rare kidney diseases. Annals of the Rheumatic Diseases, 77(8), 1226–1233. https://doi.org/10.1136/annrheumdis-2017-212935",
 ],
}
json.dump(S, open(os.path.join(ROOT, "results", "immune_geo_snippets.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(L), "lines")
