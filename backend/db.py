import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_client: Client | None = None


def get_supabase() -> Client:
    """取得 Supabase client 單例。"""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL 和 SUPABASE_KEY 環境變數未設定")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
