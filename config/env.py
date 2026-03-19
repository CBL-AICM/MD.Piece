# 環境變數設定
import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development")
APP_PORT = int(os.getenv("APP_PORT", 8000))
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-key")
