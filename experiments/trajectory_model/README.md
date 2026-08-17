# 疾病軌跡模型（模擬與分析流程）

依 `疾病軌跡模型_建置提示詞_v1.md` 與 `規格決定書_v1.md`（2026-08-17）實作。
檢驗 H1（風險層內多種軌跡型態）、H2（軌跡資訊改變的是對象與時機而非排序）、H3（預警的型態依賴）。

## 執行

```bash
cd experiments/trajectory_model
python -m pytest tests -q            # 17 個單元測試（含 FADE 等價、洩漏防護、統計定義）
python run.py --quick                # 煙霧測試：n=400、1 seed、少量置換（約 1.5 分鐘）
python -u run.py --jobs 12 --out results   # 完整格點：n=3000、5 seed、6 變體（數十分鐘～數小時，視 CPU）
```

輸出：`results/results.json`（所有數值結果，含每個參數組合、每個 seed、聚合的平均／範圍）、
`results/figures/fig1–fig5*.png`（黑白灰）。

## 檔案

| 檔案 | 模組 | 內容 |
|---|---|---|
| `params.json` | 零 | 外部參數檔：每列附 `source`；`derived_from` 為 `assumption`／`calibrated_*` 者啟動時列印 |
| `fade_components.py` | — | 自 FADE `fade_sim.py` 逐字複製的元件（決定書 §10）；僅 `simulate_S0` 加 `tau` 參數 |
| `cohort.py` | 一 | 生成器（甲：OU 有色雜訊線性型；乙：雙穩態 SDE 複用 `simulate_S0`）、x↔eGFR 刻度、校準（§1 Δμ、§3 κ）|
| `risk.py` | 二 | 基線 logistic 風險分數（pilot 世代配適一次）、五／十分位分層 |
| `clustering.py` | 三 | 方法 A（多項式係數 → GMM）／B（特徵 → k-means）；BIC＋bootstrap 穩定度選 K；時間打亂置換檢定；對生成器標籤的 ARI/NMI |
| `prediction.py` | 四 | 靜態 vs 地標動態；C 指數／Brier；淨重新分類（絕對＋相對閾值）；介入時點位移（每 90 天）|
| `warning.py` | 五 | 滾動 AR(1)/SD（= FADE 定義，向量化）；逐前綴 Kendall τ；區塊置換共同虛無分布＋同質性檢核；雙尾警報規則；提前期／偽警報；趨勢外推比較基準 |
| `figures.py` | — | 五張圖 |
| `run.py` | — | 單一入口；格點與變體；平行；聚合；洩漏警訊 |
| `tests/` | — | 每個模組至少一個測試，每個測試註明它守住哪條方法學規則 |

## 決定書 → 程式對照（重點）

- §2 刻度：`cohort.derived_scale`——健康穩態 x_L(μ_start) ↔ eGFR 90、摺疊點 −1/√3 ↔ 60、事件門檻 = eGFR 15 映射後的固定 x 值，兩型共用；`t_crit` 與 `t_event` 分開記錄，另記 `t_depart` 與「下墜時間」（eGFR 60→15）。
- §4 甲型 OU：`cohort.simulate_linear`；`tau_ou` 預設自動取 τ/λ₀ 使兩型 lag-1 自相關理論值相同；每組設定都回報兩型基線 AR(1)。
- §5 τ：`fade_components.simulate_S0(tau=...)`；格點 14/30/60。
- §6 退出：`make_cohort(dropout=True)` 複用 `apply_S2` 的退出邏輯（語意 = 停止記錄，結果事件仍已知）；只跑模組四。
- §7 高風險：`prediction._high` 絕對（≥ 事件率）與相對（前 20%）兩種都報。
- §8 位移：`prediction.run_prediction` 的 `timing`：每 90 天地標、直方圖＋累積分布（圖 4）。
- §9 虛無分布：`warning.build_null` 200 人 × 100 次區塊置換合併；KS 檢核高／低變異兩群，p<0.05 分層。
- §10 複用：`fade_components.py`；`tests/test_fade_equiv.py` 證明 `simulate_S0`（τ=1）逐位元相同、滾動指標與 `resilience_tau` 給出相同 τ。

## 實作中發現、需你裁決的事項（詳見 PR／回報）

1. **§1 翻轉時程反推在 τ=14/30 不可達**：雜訊誘發的提早逃逸使 t_event − t_crit 的中位數對任何漂移速率都 ≤ 約 90 天（`results.json → calibration.*.delta_mu.scan`）。τ=60 可達（Δμ 中位 1.04 → 180 天）。不可達時退回 FADE 等價 Δμ 分布（`fade_default_fallback`），3／12 個月兩格改為 Δμ×0.5／×2 敏感度變體並明說。
2. **§1 起始水準 vs §3 C 指數目標互相矛盾**：O'Hare 各類別的起始水準是「透析前兩年」的水準，照字面線性型 5 年事件率 ≈ 99%、靜態 C ≈ 0.97，§3 的 0.65–0.75 校準不可能達成。已加 `linear_classes.linear_start_mode`：預設 `kdigo_g2_g4_uniform`（起始 eGFR 均勻取自 15–90，標為假設），`ohare_ranges` 為字面版可切換。
3. **模組四洩漏警訊會觸發**：動態 C 指數在 365／730 天地標增益 > 0.05。資料流經測試證明只用 X[:, :L]（`test_landmark_features_cannot_see_the_future`）；增益來自結局本身是同一序列跨門檻，近期水準／斜率是合法的近端訊號——這是生成器的性質，不是發現，也不是洩漏。
4. **警報規則雙尾**：依禁止事項 5，AR(1) 與 SD 的 τ 落在雙尾 95% 區間外才警報，因此「下降」也會觸發；`first_alarm_direction` 記錄首次警報時兩指標方向，供判讀。
5. **時間打亂置換檢定的意義**：置換保留每條序列的水準與總變異，p 值只回答「分群是否由時間形狀驅動」；只靠起始水準分開的群 p 不顯著。
6. **趨勢外推比較基準**（H3 後半，我加的）：至少 90 天歷史才評估（`trend_min_history_days`，假設）；CSD 警報規則本身未動。
7. **k-means 的資訊準則**：常見的等向 k-means BIC 在純高斯雜訊上會一路選到 k_max（測試抓到），改用分割的分類似然 BIC（完整共變異數）；GMM 方法 A 的多項式係數改用正交基底、不做 z 分數（否則純雜訊高次項被放大、沿雜訊維度切群）。

## 誠實提醒

合成資料上的相對比較；絕對數值不構成臨床主張。
