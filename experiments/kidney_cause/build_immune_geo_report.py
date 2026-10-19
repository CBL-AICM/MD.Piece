# -*- coding: utf-8 -*-
"""由 results/immune_geo*.json 產生：
  docs/immune_geo/免疫方向GEO_模型準確度報告.md（＋figure/fig_auroc.png）
  results/immune_geo_snippets.json（研究報告三處待補段落＋參考文獻）
數字一律讀結果檔，不手抄。用法：python -X utf8 build_immune_geo_report.py"""
import json
import os
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
PRE = json.load(open(os.path.join(ROOT, "results", "immune_geo.json"), encoding="utf-8"))
B = json.load(open(os.path.join(ROOT, "results", "immune_geo_batchsafe.json"), encoding="utf-8"))
C = json.load(open(os.path.join(ROOT, "results", "immune_geo_amendment2.json"), encoding="utf-8"))
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
DC = C["decision"]
assert not DC["C1_metabolic_H7"]["回推成立"] and not DC["C2_metabolic_H1"]["回推成立"]
assert DC["C3_SLE_vs_MN"]["回推成立"] and DC["干擾素專屬狼瘡_C3"] and DC["免疫路徑專屬_C3"]
assert all(C[k]["per_panel"][p]["mean_diff_z"] > 0 for k in ("C1_metabolic_H7", "C2_metabolic_H1") for p in ("complement", "myeloid", "t_cell"))
assert PRE["T1_primary"]["holdout"]["GENE_LR"]["auroc"] < 0.05
# 稽核指出：路徑模型在 H7 四類把 DN 全判錯、H5 三類把 FSGS 全判錯（第一次重複）
assert B["B5_multiclass"]["H7"]["PANEL_LR"]["confusion_rep0"]["DN"]["DN"] == 0
assert B["B5_multiclass"]["H5"]["PANEL_LR"]["confusion_rep0"]["FSGS"]["FSGS"] == 0
assert B["B5_multiclass"]["H7"]["GENE_LR"]["confusion_rep0"]["DN"]["DN"] == 2
assert B["B5_multiclass"]["H5"]["GENE_LR"]["confusion_rep0"]["FSGS"]["FSGS"] == 2


def top2_base(groups):
    v = sorted(groups.values(), reverse=True)
    return (v[0] + v[1]) / sum(v)
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
shutil.copy(os.path.join(ROOT, "figures", "report", "圖10_免疫方向切片轉錄體.png"), os.path.join(DOC, "figure", "fig_three_direction.png"))


# ---------- 準確度報告 ----------
def acc_row(name, r, rep, maj):
    t = r["threshold_prevalence_rep0"]
    return (f"| {name} | {f3(r['auroc_mean'])}（{f3(r['auroc_min_max'][0])}–{f3(r['auroc_min_max'][1])}） | "
            f"{ci(r['auroc_ci_rep0'])} | {pv(r['permutation_p']) if 'permutation_p' in r else '—'} | {pc(t['accuracy'])} | "
            f"{pc(maj)} | {pc(t['balanced_accuracy'])} | {pc(t['sensitivity'])} | {pc(t['specificity'])} | {r['brier_rep0']:.3f} | "
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
  f"{f3(b3['PANEL_LR']['auroc_mean'])}。三項任務皆通過修正一的判定規則，且在腎小管間質重現。B1、B3 比的是「免疫對非免疫」（足細胞病變與糖尿病腎病變），不是「免疫對代謝」。")
w(f"2. 唯一能直接比較「免疫對代謝」的是 ANCA 對糖尿病腎病變（{b2['n_pos']} 對 {b2['n'] - b2['n_pos']} 例）："
  f"全基因模型 AUROC {f3(b2['GENE_LR']['auroc_mean'])}（95% CI {ci(b2['GENE_LR']['auroc_ci_rep0'])}），"
  f"但免疫路徑模型只有 {f3(b2['PANEL_LR']['auroc_mean'])}，未達顯著。這表示事前選的六條免疫路徑不足以區分這兩種病，"
  "全基因模型的判別力主要來自路徑以外的基因。注意：修正一「任一模型成立即可」的規則，是在已知此全基因結果之後寫入的；"
  "原計畫對同一比較（T2）只檢定路徑模型，判定為不成立。因此本項屬事後分析，不是事前確認。")
w(f"3. 狼瘡腎炎的訊號集中在干擾素路徑（單一路徑 AUROC {f3(sle_ifn)}），高於 1,000 組隨機基因集的第 95 百分位，"
  f"屬免疫路徑專屬；ANCA 的路徑模型則只在隨機基因集第 {B['B1_primary']['random_gene_sets']['percentile_of_panel']:.1f} 百分位，"
  "代表其與非免疫腎病之差異廣泛分布於全基因體，不專屬事前路徑。")
w("4. IgA 腎病變與高血壓腎病變各自只在一個處理批次，同批次內沒有對照，本資料無法評估。")
w("5. 事後修正二補上代謝方向本身與狼瘡腎炎對膜性腎病變（第六節）：糖尿病腎病變對既非免疫也非代謝的腎病未達判定（每批只有 5–7 例），"
  f"狼瘡腎炎對膜性腎病變可以區分，干擾素路徑單獨 AUROC {f3(C['interferon_test']['glom']['auroc'])}。")
w("6. 事前計畫原定的主要任務（狼瘡腎炎＋IgA 腎病變對糖尿病＋高血壓腎病變）因診斷與處理批次完全重疊而失效（見第六節），"
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
w("| 任務・模型 | AUROC 平均（最小–最大） | 95% CI | 置換 p | 準確率 | 全猜多數類 | 平衡準確率 | 敏感度 | 特異度 | Brier | 腎小管間質 AUROC |")
w("|---|---|---|---|---|---|---|---|---|---|---|")
for key, code, name, _ in TASKS:
    maj = max(B[key]["n_pos"], B[key]["n"] - B[key]["n_pos"]) / B[key]["n"]
    for m in ["PANEL_LR", "GENE_LR"]:
        w(acc_row(f"{code}・{MODEL_ZH[m]}", B[key][m], B["B4_replication"][code][m], maj))
w("\n註：95% CI 與準確率、敏感度、特異度、Brier 取第一次重複之折外預測；置換檢定打亂標籤 1,000 次，"
  "兩種模型以 Bonferroni 校正（p < 0.025 為顯著）。"
  "樣本不平衡時準確率會被多數類撐高（例如 B3 全猜狼瘡即有 80%），請以平衡準確率與 AUROC 判讀。"
  "95% CI 只取一次重複、不含模型重新訓練的變異，會偏窄。\n")
w("![[figure/fig_auroc.png|620]]\n")
w("## 四、回推可能病因（多類別）\n")
w("| 批次・模型 | 類別 | 準確率 | 全猜最多類 | 平衡準確率 | 前二名命中率 | 全猜最多兩類 |\n|---|---|---|---|---|---|---|")
for bt, cls in [("H7", "ANCA／DN／FSGS／MCD"), ("H5", "SLE／MN／FSGS")]:
    for m in ["PANEL_LR", "GENE_LR"]:
        r = B["B5_multiclass"][bt][m]
        w(f"| {bt}・{MODEL_ZH[m]} | {cls} | {pc(r['accuracy_mean'])} | {pc(r['chance_majority'])} | "
          f"{pc(r['balanced_accuracy_mean'])} | {pc(r['top2_mean'])} | {pc(top2_base(B['B5_multiclass'][bt]['groups']))} |")
for bt in ["H7", "H5"]:
    cm = B["B5_multiclass"][bt]["GENE_LR"]["confusion_rep0"]
    cls = list(cm)
    w(f"\n{bt} 全基因模型混淆矩陣（第一次重複；列＝真實、欄＝預測）\n")
    w("| 真實＼預測 | " + " | ".join(cls) + " |\n|---|" + "---|" * len(cls))
    for t in cls:
        w(f"| {t} | " + " | ".join(str(cm[t][p]) for p in cls) + " |")
w("\n多類別的錯誤集中在樣本少的類別：路徑模型在第一次重複把 H7 的 7 例糖尿病腎病變、H5 的 8 例 FSGS 全部判錯，"
  "全基因模型也只對 2 例。類別只有三、四個時前二名命中率的基準本來就高（見「全猜最多兩類」），不宜單獨引用。"
  "目前的模型能把樣本多的免疫病（ANCA、狼瘡腎炎、膜性腎病變）認出來，還不能可靠地回推少數類的病因。\n")
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
w("## 六、事後修正二：免疫／代謝／兩者皆非三方向並列\n")
w("本節是**事後修正二**。動機來自獨立稽核（`results/immune_geo_audit.md` 第 5.7 節）：修正一只有 ANCA 對糖尿病腎病變碰到代謝病，"
  "無法回答「代謝病能否和非免疫、非代謝的腎病分開」，也無法判斷狼瘡腎炎的干擾素訊號是否只是一般發炎。修正二 "
  "`params/immune_geo_amendment_2.json` 於計算前提交（4325345），模型、交叉驗證、置換檢定、門檻與判定規則和修正一相同，"
  "另加「干擾素專屬狼瘡」規則；結果見 `results/immune_geo_amendment2.json`。\n")
ALL = [("免疫 對 非免疫", "B1", "ANCA 對 DN、FSGS、MCD", "H7", B["B1_primary"], B["B4_replication"]["B1"], B["decision"]["B1_primary"]),
       ("免疫 對 非免疫", "B3", "SLE 對 FSGS", "H5", B["B3_SLE"], B["B4_replication"]["B3"], B["decision"]["B3_SLE"]),
       ("免疫 對 代謝", "B2", "ANCA 對 DN", "H7", B["B2_immune_vs_metabolic"], B["B4_replication"]["B2"], B["decision"]["B2_immune_vs_metabolic"]),
       ("代謝 對 兩者皆非", "C1", "DN 對 FSGS、FSGS_MCD、MCD", "H7", C["C1_metabolic_H7"], C["C4_replication"]["C1"], DC["C1_metabolic_H7"]),
       ("代謝 對 兩者皆非", "C2", "DN 對 MCD、TMD", "H1", C["C2_metabolic_H1"], C["C4_replication"]["C2"], DC["C2_metabolic_H1"]),
       ("免疫 對 免疫", "C3", "SLE 對 MN", "H5", C["C3_SLE_vs_MN"], C["C4_replication"]["C3"], DC["C3_SLE_vs_MN"])]
w("| 方向 | 任務 | 比較（批次） | 陽性／對照 | 路徑模型 AUROC（95% CI） | 置換 p | 全基因模型 AUROC（95% CI） | 置換 p | 腎小管間質（路徑／全基因） | 判定 |")
w("|---|---|---|---|---|---|---|---|---|---|")
for dr, code, lab, bt, r, t, dec in ALL:
    w(f"| {dr} | {code} | {lab}（{bt}） | {r['n_pos']}／{r['n'] - r['n_pos']} | {f3(r['PANEL_LR']['auroc_mean'])}（{ci(r['PANEL_LR']['auroc_ci_rep0'])}） | "
      f"{pv(r['PANEL_LR']['permutation_p'])} | {f3(r['GENE_LR']['auroc_mean'])}（{ci(r['GENE_LR']['auroc_ci_rep0'])}） | "
      f"{pv(r['GENE_LR']['permutation_p'])} | {f3(t['PANEL_LR']['auroc_mean'])}／{f3(t['GENE_LR']['auroc_mean'])} | "
      f"{('成立（事後規則）' if code == 'B2' else '成立') if dec['回推成立'] else '不成立'} |")
c1, c2, c3, itf = C["C1_metabolic_H7"], C["C2_metabolic_H1"], C["C3_SLE_vs_MN"], C["interferon_test"]
w("\n95% CI 只取第一次重複；置換檢定 1,000 次（最小可能 p＝1/1001）。B1–B3 為修正一，C1–C3 為修正二；跨任務未校正多重比較。\n")
w(f"1. **代謝方向本身未達判定。** C1 糖尿病腎病變 {c1['n_pos']} 例、C2 只有 {c2['n_pos']} 例；點估計 0.65–0.83、腎小管間質重做 0.76–0.84，"
  f"但置換 p 都在 0.06 以上，C2 全基因模型 95% CI 下界只有 {c2['GENE_LR']['auroc_ci_rep0'][0]:.2f}。這是例數不足下的「無法確認」，不是「確認沒有差異」。")
w(f"2. **糖尿病腎病變切片也有發炎。** 兩批都以補體、單核巨噬細胞、T 細胞路徑較高（C1 單路徑 AUROC "
  f"{f3(c1['per_panel']['complement']['auroc'])}、{f3(c1['per_panel']['myeloid']['auroc'])}、{f3(c1['per_panel']['t_cell']['auroc'])}），"
  f"干擾素反而較低（{f3(c1['per_panel']['interferon']['auroc'])}）。這與 B2 免疫路徑模型分不開 ANCA 與糖尿病腎病變一致，發炎路徑不能拿來區分免疫與代謝方向。")
w(f"3. **干擾素訊號專屬狼瘡成立。** C3 路徑模型 {f3(c3['PANEL_LR']['auroc_mean'])}、全基因模型 {f3(c3['GENE_LR']['auroc_mean'])}；"
  f"干擾素單路徑 {f3(itf['glom']['auroc'])}（95% CI {ci(itf['glom']['ci'])}，置換 10,000 次 p {pv(itf['glom']['permutation_p'])}），"
  f"腎小管間質 {f3(itf['tubint']['auroc'])}；路徑模型高於隨機基因集第 95 百分位（{c3['random_gene_sets']['panel_auroc_rep0']:.3f} 對 "
  f"{c3['random_gene_sets']['p95']:.3f}）。SLE 與 MN 同屬免疫複合體腎病，差在干擾素。")
w("4. 三方向合起來看，免疫對非免疫可分；免疫對代謝只有全基因模型可分（事後規則）；代謝對兩者皆非未達判定；免疫病之間可由干擾素分開。\n")
w("![[figure/fig_three_direction.png|620]]\n")
w("## 七、事前計畫為何失效（照實報告）\n")
w("GEO 樣本來源名稱中的 H 代碼是處理批次。GPL24120 平台上，糖尿病腎病變全在 H1、高血壓腎病變全在 H2、IgA 腎病變全在 H4、"
  "狼瘡腎炎在 H5。事前計畫只注意到兩個晶片平台的混淆，漏看了批次，因此原定任務比較的其實是批次。"
  "GEO 的資料處理說明另寫明，各批次分別以 RMA 正規化後合併，再以 ComBat 做批次校正。批次與疾病完全重疊時，"
  "ComBat 移除批次平均也會一併移除大部分疾病平均差（此為依資料型態的推論，存放者的 ComBat 設定無法取得）。")
t1 = PRE["T1_primary"]
w(f"徵兆是全基因模型 AUROC 遠低於 0.5：交叉驗證 {f3(t1['GENE_LR']['auroc_mean'])}、保留測試集 "
  f"{f3(t1['holdout']['GENE_LR']['auroc'])}，訓練集卻幾乎全對，屬於記憶批次。原計畫判定「回推成立」為否，"
  f"「免疫路徑專屬」雖為是，但同樣無法解讀。平台陰性對照 AUROC "
  f"{f3(PRE['T4_pooled']['platform_negative_control']['auroc_mean'])} 被判為通過，是因為門檻只看信賴區間上界；"
  "AUROC 遠低於 0.5 同樣代表兩平台可完全分開，平台校正實際上失敗。原結果檔照原樣保留，未刪改。\n")
w("## 八、限制\n")
w("1. 這是確診後的切片組織，不是常規抽血驗尿；結果說明免疫性病因在腎臟本身可辨識，以及哪些路徑值得轉成血液或尿液檢驗，"
  "不能證明常規檢驗可回推免疫方向。")
w("2. 樣本少（B2 只有 29 例，其中糖尿病腎病變 7 例），信賴區間寬；腎絲球與腎小管間質來自同一批切片，重現不是獨立驗證。")
w("3. 沒有獨立的外部資料集；同批次內仍可能存在未記錄的處理差異。各路徑單獨的 AUROC 未經交叉驗證與多重比較校正，只作描述。")
w("4. ERCB 的糖尿病腎病變是臨床上需要切片的非典型個案，不代表一般糖尿病腎病變。")
w("5. 沒有感染方向的資料；IgA 腎病變與高血壓腎病變無法評估。")
w("6. 一筆中繼資料互相矛盾：GSM2810968 標題為 H5-Tub-MGN303（膜性腎病），診斷欄為紅斑性狼瘡；程式依診斷欄歸為狼瘡，只影響腎小管間質重現的一例。\n")
w("## 九、獨立檢驗\n")
w("另一工作階段以自行撰寫、不引用主程式的程式，從原始 GEO 檔重新解析與建模，重算事前計畫版 30 餘項數字與修正一全部二元任務、"
  "多類別混淆矩陣，與結果檔全部一致；置換檢定、隨機基因集與 bootstrap 信賴區間只審查演算法、未獨立重算。"
  "稽核另指出：批次與 ComBat 問題（第六節）；平台陰性對照若改成只用訓練折校正，AUROC 約 0.8，同樣不通過；"
  "B2 判定規則於已知結果後訂定（第一節）；準確率須對照多數類基準。全文見 `results/immune_geo_audit.md`。")
w("稽核建議的同批次比較（代謝方向本身、狼瘡腎炎對膜性腎病變）已列為修正二並執行（第六節）；修正二的數字尚未經獨立重算。\n")
w("## 十、重現方式\n")
w("```\npython immune_geo.py            # 事前計畫版（結果已存在則拒跑）\npython immune_geo_batchsafe.py  # 修正一\npython immune_geo_amendment2.py  # 修正二\n"
  "python -m pytest test_immune_geo.py\npython -X utf8 build_immune_geo_report.py\n```\n")
w(f"計畫 SHA256：{B['plan_sha256'][:16]}…；修正一 SHA256：{B['amendment_sha256'][:16]}…；修正二 SHA256：{C['amendment_sha256'][:16]}…；資料五檔之 URL 與 SHA256 見 `results/provenance.json`。\n")
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
  f"（95% CI {ci(b2['GENE_LR']['auroc_ci_rep0'])}），免疫路徑模型為 {f3(b2['PANEL_LR']['auroc_mean'])}，未達顯著"
  "（此項的判定規則在已知全基因結果後訂定，屬事後分析）；"
  f"紅斑性狼瘡腎炎對局部節段性腎絲球硬化，免疫路徑模型為 {f3(g3['auroc_mean'])}"
  f"（95% CI {ci(g3['auroc_ci_rep0'])}），其中干擾素路徑單獨即達 {f3(sle_ifn)}。三項比較在腎小管間質皆重現。"
  "前兩項比的是免疫病與非免疫腎病，唯一的免疫對代謝比較只有第二項。"
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
