# E2E tests — 藥單 / 藥袋拍照辨識 pipeline

驗證 `frontend Tesseract.js OCR → POST /medications/recognize → backend Haiku 抽欄位` 整條路的回歸測試。

## 為什麼要這個？

藥單辨識牽涉前端 Tesseract.js + 後端 LLM，純 unit test 蓋不到。
這條 E2E 直接用合成藥單跑完整流程，驗證：

1. Tesseract.js 對中文藥單能 OCR 出可用文字
2. `/medications/recognize` 帶 `ocr_text` 走 client_ocr 路徑
3. Haiku 能從 OCR 文字抽出 ≥ 1 筆 medication

## 使用

### 一次性安裝

```bash
# Tesseract.js（裝在 tests/e2e/ 自己的 package.json，不污染前端）
cd tests/e2e && npm install

# Pillow + 中文字型（產生合成藥單圖片）
pip install pillow
sudo apt install fonts-wqy-zenhei  # Ubuntu/Debian
```

### 產生合成藥單 fixture

```bash
python3 tests/e2e/fixtures/generate_rx_images.py
```

產出 6 張：

- `rx_allergy_4drugs.jpg` — A4 處方箋，4 種藥（過敏 / 抗生素 / 止痛 / 抗組織胺）
- `rx_cardio_3drugs.jpg`  — A4 處方箋，3 種藥（心血管）
- `rx_cold_3drugs.jpg`    — A4 處方箋，3 種藥（感冒）
- `bag_metformin.jpg`     — 藥袋，Metformin
- `bag_antibiotic.jpg`    — 藥袋，Amoxicillin
- `bag_painkiller.jpg`    — 藥袋，Ibuprofen (PRN)

### 跑測試

```bash
# 對 production
node tests/e2e/run_rx_recognition.mjs

# 對本機 backend
API_BASE=http://localhost:8000 node tests/e2e/run_rx_recognition.mjs

# 跑指定圖檔
node tests/e2e/run_rx_recognition.mjs path/to/foo.jpg
```

成功標準：每張圖回 HTTP 200 且抽出 ≥ 1 筆 medication。任何失敗會 exit 1。

## 預期表現（截至 PR #186）

| Image | OCR ms | API ms | Meds |
|-------|--------|--------|------|
| rx_allergy_4drugs    | ~2000 | ~6000 | 4/4 |
| rx_cardio_3drugs     | ~800  | ~1200 | 3/3 |
| rx_cold_3drugs       | ~800  | ~1200 | 3/3 |
| bag_metformin        | ~2500 | ~1000 | 1/1 |
| bag_antibiotic       | ~1400 | ~1200 | 1/1 |
| bag_painkiller       | ~1200 | ~900  | 1/1 |

合計 6 張 / 13 種藥 / ~20 秒。

## 已知限制

- 合成藥單字體 / 版面比真實照片乾淨很多，所以 Tesseract OCR 命中率很高；真實藥單（傾斜、反光、皺摺、低光）會更差，新 pipeline 在這種情境會自動 fallback 到後端 LLM vision
- 偶爾會把相似中文字 OCR 錯（例：一/三、莫/英），所以前端 UI 把每筆藥顯示成可編輯卡片，使用者點「加入」前可校對

## 劣化測試

`fixtures/degrade_images.py` 從乾淨 fixtures 產出 4 個劣化等級（輕度 → 極差）的變體，
模擬真實手機拍照（縮小、傾斜、低對比、模糊、雜訊、低 JPEG quality）：

```bash
python3 tests/e2e/fixtures/generate_rx_images.py   # 先產 base
python3 tests/e2e/fixtures/degrade_images.py       # 再產劣化變體
```

劣化檔名含 `_d1_light` ~ `_d4_extreme`，runner 對這類檔案不會把失敗算進 exit code（只記錄結果做觀察）。

## 控制 rate limit

每張圖之間預設 sleep 2s 避免打爆 backend Haiku API：

```bash
DELAY_MS=4000 node tests/e2e/run_rx_recognition.mjs   # 慢一點
DELAY_MS=0    node tests/e2e/run_rx_recognition.mjs   # 不 sleep（會打爆）
```

跑全套 18 張圖時間：~1 分鐘（含 worker init 和 sleep）。
