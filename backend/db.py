import logging
import os

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
    _supabase_available = True
except BaseException:
    _supabase_available = False
    Client = None
    logger.warning("supabase 套件無法載入，資料庫功能將不可用")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_client = None


def get_supabase():
    """取得 Supabase client 單例。"""
    global _client
    if _client is None:
        if not _supabase_available:
            raise RuntimeError("supabase 套件無法載入")
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL 和 SUPABASE_KEY 環境變數未設定")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
