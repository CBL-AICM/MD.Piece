# 安裝與設定說明

## 環境需求

- Python 3.10+
- Node.js 18+（若使用前端建置工具）

## 快速開始

### 1. 複製專案

```bash
git clone <repo-url>
cd md.piece
```

### 2. 後端設定

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn main:app --reload
```

### 3. 前端

直接開啟 `frontend/index.html`，或透過後端靜態檔案服務。

## 環境變數

請參考 `.env.example` 填入所需設定。
