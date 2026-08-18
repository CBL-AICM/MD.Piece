# SLE 狼瘡腎炎減藥翻轉預警（模型核心與呈現介面）

依 `docs/ClaudeCode_全案建置指示_v1.md`（上游 `docs/核心規格書_SLE版_v1.md`）分四階段建置。

```bash
cd experiments/sle_taper
python -m pytest tests -q          # 十項單元測試（可單獨執行）
python run.py --phase 1            # 參數骨架＋校準三步＋四道閘門 → results/phase1.json、results/assumptions.md
python run.py --verify [--quick]   # 第六部驗收清單（模型端）
```

- `params/thresholds.json`：全案唯一數值真相（value / source / status；pending_extraction 以 placeholder 佔位並三處標示）
- `params/cohort.json`：世代生成設定（基線特徵分布、易感度連結、型別結構、觀測預設）
- `src/`：seeding、m0_params、m1_generator（生成層＋觀測層）、m2_risk、m4_predict、m6_arms、calibrate、gates
- 亂數一律經 `seeding.module_rng(master_seed, module, sub)`；不用 `np.random` 全域介面
