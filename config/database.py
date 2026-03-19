# 資料庫設定
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./md_piece.db")
