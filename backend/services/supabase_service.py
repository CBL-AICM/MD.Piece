import os
from dotenv import load_dotenv

load_dotenv()

# Supabase 資料庫連線服務（延遲初始化）

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_supabase_client = None


def _get_client():
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return None
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


class _SupabaseProxy:
    """Proxy that lazily initializes Supabase client on first use."""

    def __getattr__(self, attribute_name):
        initialized_client = _get_client()
        if initialized_client is None:
            raise RuntimeError(
                "SUPABASE_URL 和 SUPABASE_KEY 環境變數未設定。"
                "請複製 .env.example 為 .env 並填入實際值。"
            )
        return getattr(initialized_client, attribute_name)


supabase = _SupabaseProxy()
