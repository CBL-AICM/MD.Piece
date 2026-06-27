"""全域測試夾具：消除整合測試的「跨檔順序脆弱性」。

背景：每支 tests/integration/test_*.py 都在 module import 時把自己的暫存 SQLite
路徑寫進 backend.db 的「共用模組全域」DB_PATH / _client，並呼叫 _init_db()。
由於 DB_PATH / _client 是共用全域，pytest 收集階段會把所有檔案都 import 一遍，
最後 DB_PATH 只會停在「最後被 import 的檔案」的暫存檔；執行階段時，沒有自帶
autouse `_reset_db` 夾具的檔案就會讀到別人的暫存 DB，導致測試結果隨「跑哪些檔案、
什麼順序」而變（單跑會過、手挑子集會偶爾掛）。

這支 autouse 夾具在「每個測試開始前」把 DB_PATH 重新釘回該測試所屬 module 自己
宣告的 `_TMP_DB`，並重置 client 快取——等同於把每支檔案還原成「單獨執行」時的
隔離狀態，與收集順序無關。對沒有 `_TMP_DB` 的測試（多數 unit 測試）完全不介入，
只會修正、不會改變既有行為。
"""

import os

import pytest

# 在「任何 test module 被 import」之前固定 JWT_SECRET（conftest 早於 test 檔載入）。
# 多支整合測試在 import 時就用當下的 secret 簽 JWT；若 secret 隨「哪個檔先 import」
# 而變（部分 auth 檔會在 import 時設 JWT_SECRET），跨檔子集就會出現「A 帶有效 token
# 卻被當匿名 → 跨帳號 403 變 200」的順序性失敗。固定成與 auth 測試相同的值即一致。
os.environ["JWT_SECRET"] = "test-secret-at-least-16-chars-long-xxxx"

import backend.db as _db


@pytest.fixture(autouse=True)
def _pin_module_db(request):
    """把 backend.db.DB_PATH 釘回目前測試 module 自己的暫存 DB（若有宣告）。"""
    tmp = getattr(request.module, "_TMP_DB", None)
    if tmp is not None and getattr(tmp, "name", None):
        _db.DB_PATH = tmp.name
        _db._client = None  # 強制下次 get_supabase() 依新 DB_PATH 重新連線
        _db._init_db()
    yield
