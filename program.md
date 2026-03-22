# MD.Piece AutoResearch Program

基於 [karpathy/autoresearch](https://github.com/karpathy/autoresearch) 的自動實驗循環指令。

## 前置條件

- 已 clone autoresearch 並完成 `uv run prepare.py`
- 有 NVIDIA GPU（Colab T4+ 或本地 GPU）
- MD.Piece 後端 API 運行中（用於回傳結果）

## 自動實驗循環

AI Agent 請按以下步驟執行：

### 1. 環境設定

```bash
cd autoresearch
git checkout -b autoresearch/mdpiece-$(date +%Y%m%d-%H%M)
```

### 2. 建立 Baseline

```bash
uv run train.py > run.log 2>&1
```

從 `run.log` 提取 `val_bpb` 作為 baseline。

### 3. 實驗循環（無限重複）

每次迭代：

1. **假設**：提出一個改進 `train.py` 的假設（架構、超參數、優化器等）
2. **修改**：編輯 `train.py`，只改一個變數
3. **提交**：`git commit -am "hypothesis: <描述>"`
4. **執行**：`uv run train.py > run.log 2>&1`（約 5 分鐘）
5. **評估**：從 `run.log` 提取 `val_bpb`
6. **決策**：
   - 如果 `val_bpb` 改善 → 保留 commit，記錄為 `kept`
   - 如果 `val_bpb` 退步或崩潰 → `git reset --hard HEAD~1`，記錄為 `reverted`
7. **記錄**：追加到 `results.tsv`，格式：
   ```
   name\tval_bpb\ttrain_loss\tsteps\tduration\tkept\tdescription\ttimestamp
   ```
8. **回傳**：POST 結果到 MD.Piece API
   ```bash
   curl -X POST http://localhost:8000/research/ \
     -H "Content-Type: application/json" \
     -d '{"name":"exp-name","val_bpb":1.234,"kept":true,"notes":"描述"}'
   ```

### 4. 改進方向建議

- 調整 `DEPTH`、`ASPECT_RATIO`
- 修改學習率（`LR`, `MUON_LR`）
- 改變 batch size（`TOTAL_BATCH_SIZE`）
- 嘗試不同 attention 模式
- 調整 warmup/warmdown 步數
- 優化器參數調整
- 殘差連接 lambda 值

### 5. 批次匯入

訓練結束後，可將 `results.tsv` 上傳到 MD.Piece：

```bash
curl -X POST http://localhost:8000/research/batch \
  -F "file=@results.tsv"
```
