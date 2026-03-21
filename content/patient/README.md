# Patient 端內容設計

此資料夾用於管理 MD.Piece 平台 **病患端** 的內容稿件與設計文件。

## 資料夾結構

```
content/patient/
├── README.md           # 本說明文件
├── onboarding/         # 新手引導流程內容
├── education/          # 衛教資訊內容
├── symptoms/           # 症狀相關文案
├── medications/        # 藥物說明文案
├── emotions/           # 情緒追蹤相關文案
├── notifications/      # 通知與提醒文案
└── ui-copy/            # 一般 UI 文案（按鈕、提示、錯誤訊息等）
```

## 使用方式

- 每個子資料夾對應一個功能模組
- 文案以 Markdown 撰寫，方便版本控管與協作
- 檔名格式建議：`功能名稱-描述.md`（例如 `symptom-input-guide.md`）
