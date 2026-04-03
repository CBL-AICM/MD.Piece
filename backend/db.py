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


class _MockResult:
    def __init__(self):
        self.data = []

class _MockQuery:
    def select(self, *a, **k): return self
    def insert(self, *a, **k): return self
    def update(self, *a, **k): return self
    def delete(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def neq(self, *a, **k): return self
    def gte(self, *a, **k): return self
    def lte(self, *a, **k): return self
    def ilike(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self): return _MockResult()

class _MockSupabase:
    def table(self, name): return _MockQuery()


def get_supabase():
    """取得 Supabase client 單例。無憑證時回傳 Mock（空資料）。"""
    global _client
    if _client is None:
        if _supabase_available and SUPABASE_URL and SUPABASE_KEY:
            _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        else:
            logger.warning("資料庫未設定，使用 Mock 模式（空資料）")
            _client = _MockSupabase()
    return _client
