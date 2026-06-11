# MD.Piece — Fly.io 容器映像
# 單一程序同時提供 FastAPI 後端與前端靜態檔（backend.main:app）。
FROM python:3.12-slim

# pywebpush → http-ece / cryptography 編譯所需的最小系統相依
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先裝相依（利用 Docker layer 快取，requirements 沒變就不重裝）
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 只複製執行期真正需要的目錄（避免把 ChatDev / 資料集 / 研究檔塞進映像）
COPY backend/ ./backend/
COPY frontend/ ./frontend/

ENV PORT=8000 \
    APP_ENV=production \
    PYTHONUNBUFFERED=1
EXPOSE 8000

# backend.main:app 已內建前端靜態檔服務（StaticFiles）與所有 API router
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
