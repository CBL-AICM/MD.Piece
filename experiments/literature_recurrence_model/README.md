# 文獻錨定的慢性病復發預測 × 3,200 位虛擬患者

延續 `claude/chronic-disease-recurrence-prediction-212dbc` 的研究目的（長期紀錄能否預測復發與復發時間），
但**不使用任何公開資料庫的個人層級資料**：真實世界的資訊只來自 PubMed 摘要中的族群層級數字。

## 交付物

| 檔案 | 內容 |
|---|---|
| `docs/research/literature_recurrence_model/說明書_中文_*.docx`／`.pdf` | 中文科展說明書（APA，29 頁） |
| `docs/research/literature_recurrence_model/Report_EN_*.docx`／`.pdf` | 英文版說明書（29 頁） |
| `outputs/figures/fig01–13_{zh,en}.png` | 全部研究圖表（中英各一套） |
| `outputs/references_used.csv` | 53 筆參考文獻（APA）＋每篇為什麼用、用了哪一部分 |
| `outputs/literature_check.csv` | 43 個文獻數字逐筆對照 PubMed 摘要的查核結果 |
| `outputs/新數據_校準後3200人患者表.csv` | 文獻校準後的新數據（每人一列） |
| `outputs/原始虛擬3200人患者表.csv` | 原始虛擬患者（對照） |
| `outputs/results.json`、`outputs/plot_data/*.csv` | 所有數字與每張圖的繪圖資料 |

PDF 為 LibreOffice 轉出的預覽，因環境沒有新細明體／Times New Roman，以 Noto Serif CJK TC／Liberation Serif 代替；
docx 內指定的字型為新細明體與 Times New Roman 12 pt。

## 重現

```bash
git archive origin/claude/train-ai-model-0NYvq md_piece diseases | tar -x -C $SIM_DIR
PYTHONPATH=$SIM_DIR python experiments/literature_recurrence_model/simulate_cohort.py $SIM_DIR $SIMDATA   # 約 3 分鐘
python experiments/literature_recurrence_model/run.py $SIMDATA                                            # 約 5 分鐘
python experiments/literature_recurrence_model/figures.py [字型資料夾]
python experiments/literature_recurrence_model/references.py
python experiments/literature_recurrence_model/verify_literature.py <PubMed 摘要快取>                      # 需先下載摘要
python experiments/literature_recurrence_model/build_report.py
```

`lit_notes.md` 是逐篇閱讀摘要時的原始擷取筆記；`literature.py` 是整理後實際進入分析的數字。
