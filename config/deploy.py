# 部署設定
import os

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", 8000))
WORKERS = int(os.getenv("WORKERS", 1))
RELOAD = os.getenv("APP_ENV", "development") == "development"
