# OCR API Contract

## 1. 目的

定義拍攝模組與 OCR 服務之間的資料交換格式，讓 Web、Flutter 或後端服務能使用同一套契約進行串接。

## 2. 建議架構

- 前端負責拍攝、初步狀態顯示與提交影像
- 影像處理服務負責裁切、透視校正、增強與品質評估
- OCR 服務負責文字辨識與信心分數輸出

## 3. API 一覽

建議至少提供以下端點：

- `POST /api/capture/evaluate`
- `POST /api/ocr/recognize`
- `POST /api/ocr/confirm`

## 4. `POST /api/capture/evaluate`

### 用途

對單張影像做品質檢查，判斷是否適合送 OCR。

### Request

```json
{
  "imageBase64": "data:image/jpeg;base64,...",
  "mode": "document",
  "client": {
    "platform": "web",
    "appVersion": "0.1.0"
  }
}
```

### Response

```json
{
  "captureState": "ready",
  "documentDetected": true,
  "insideFrame": true,
  "blurScore": 144.1,
  "brightnessScore": 0.71,
  "glareDetected": false,
  "tiltAngle": 2.6,
  "issues": [],
  "message": "已對準，可拍攝"
}
```

## 5. `POST /api/ocr/recognize`

### 用途

接收拍攝完成的影像，執行前處理與 OCR，回傳辨識結果。

### Request

```json
{
  "imageBase64": "data:image/jpeg;base64,...",
  "mode": "document",
  "options": {
    "preprocess": true,
    "languageHints": ["zh-TW", "en"],
    "returnBlocks": true
  }
}
```

### Response

```json
{
  "requestId": "ocr_20260415_001",
  "success": true,
  "confidence": 0.93,
  "normalizedImageUrl": "/artifacts/ocr_20260415_001/normalized.jpg",
  "text": "範例文字內容",
  "lines": [
    {
      "text": "範例文字內容",
      "confidence": 0.93,
      "boundingBox": [24, 40, 420, 68]
    }
  ],
  "warnings": []
}
```

## 6. `POST /api/ocr/confirm`

### 用途

當使用者確認 OCR 結果可用時，回存結果或送至後續流程。

### Request

```json
{
  "requestId": "ocr_20260415_001",
  "accepted": true,
  "editedText": "使用者修正後文字"
}
```

### Response

```json
{
  "success": true,
  "status": "stored"
}
```

## 7. 錯誤格式

```json
{
  "success": false,
  "error": {
    "code": "IMAGE_TOO_BLURRY",
    "message": "畫面太模糊，請重新拍攝"
  }
}
```

## 8. 錯誤代碼建議

- `DOCUMENT_NOT_FOUND`
- `DOCUMENT_OUT_OF_FRAME`
- `IMAGE_TOO_BLURRY`
- `IMAGE_TOO_DARK`
- `GLARE_DETECTED`
- `OCR_LOW_CONFIDENCE`
- `UNSUPPORTED_IMAGE_FORMAT`
- `INTERNAL_PROCESSING_ERROR`

## 9. 前端整合建議

1. 預覽時可選擇性呼叫 `capture/evaluate`
2. 拍攝完成後呼叫 `ocr/recognize`
3. 顯示文字與信心分數
4. 使用者確認後呼叫 `ocr/confirm`

## 10. 安全與效能建議

- 影像大小建議壓縮至合理範圍再上傳
- 建議限制最大檔案大小
- 若資料含個資，傳輸需使用 HTTPS
- 可針對 OCR API 記錄 request id 與耗時
- 避免長期保存原始影像，除非有明確需求
