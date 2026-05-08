"""drug_search router 整合測試 — 用本地 SQLite fallback + monkey-patch LLM。

測試重點：
- GET /drug-search/?q=… 第一次呼叫會走 lookup_drug_info，命中後寫入 drug_reference
- 第二次呼叫同樣的字串會直接從快取回，不再呼叫 LLM
- 別名（aliases）也能命中快取
- LLM 表示無法辨識時，回 matched=false 且不寫快取
- /drug-search/from-medication/{id} 用個人用藥的 name 做查詢
"""

import os
import sys
import tempfile

import pytest

# 以本地 SQLite 跑測試：在 import db 前清空 Supabase 環境變數
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)
os.environ.pop("VERCEL", None)
os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)

_TMP_DB = tempfile.NamedTemporaryFile(prefix="drugsearchtest_", suffix=".db", delete=False)
_TMP_DB.close()
os.environ["SQLITE_DB_PATH"] = _TMP_DB.name

import backend.db as db_mod  # noqa: E402

db_mod.DB_PATH = _TMP_DB.name
db_mod.SUPABASE_URL = ""
db_mod.SUPABASE_KEY = ""
db_mod._client = None  # type: ignore[attr-defined]
db_mod._init_db()

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.routers import drug_search as drug_search_module  # noqa: E402

client = TestClient(app)

PATIENT_ID = "drug-search-test-patient"


@pytest.fixture(autouse=True)
def _reset_db():
    """每個測試前：把 db 指回本 module 的 SQLite 檔，再清空相關表。

    多個測試檔同時跑時，後 import 的 test_*.py 會把 db_mod.DB_PATH 蓋成自己的暫存檔，
    這個 fixture 在每個 drug_search 測試啟動時把 DB_PATH 拉回這裡，避免讀寫到別檔。
    """
    import sqlite3

    db_mod.DB_PATH = _TMP_DB.name
    db_mod.SUPABASE_URL = ""
    db_mod.SUPABASE_KEY = ""
    db_mod._client = None  # type: ignore[attr-defined]
    db_mod._init_db()  # 確保 schema 存在

    conn = sqlite3.connect(_TMP_DB.name)
    conn.execute("DELETE FROM drug_reference")
    conn.execute("DELETE FROM medications")
    conn.execute("DELETE FROM patients")
    conn.commit()
    conn.close()
    yield


def _fake_acetaminophen(name: str) -> dict:
    """假的 lookup_drug_info：所有非「未知」字串都當 acetaminophen 處理。"""
    if "未知" in name or "unknownxyz" in name.lower():
        return {
            "matched": False,
            "name_zh": None,
            "name_en": None,
            "aliases": [],
            "category": None,
            "indication": None,
            "usage": None,
            "side_effects": {"common": [], "serious": []},
            "risks": {"contraindications": [], "warnings": [], "interactions": []},
            "education": None,
            "disclaimer": "無法辨識此藥名，請確認拼字或聯絡藥師。",
        }
    return {
        "matched": True,
        "name_zh": "乙醯胺酚",
        "name_en": "Acetaminophen",
        "aliases": ["普拿疼", "Tylenol"],
        "category": "止痛藥",
        "indication": "緩解輕度至中度疼痛、退燒",
        "usage": "依醫師指示，常見成人每 4~6 小時一次，一天不超過 4g。",
        "side_effects": {
            "common": ["輕微噁心", "皮膚搔癢"],
            "serious": ["嚴重皮疹", "呼吸困難（過敏反應）", "肝指數異常"],
        },
        "risks": {
            "contraindications": ["嚴重肝功能不全患者"],
            "warnings": ["一天總劑量勿超過 4g", "服用期間避免飲酒"],
            "interactions": ["Warfarin（增加出血風險）"],
        },
        "education": "若連續服用超過 3 天疼痛仍未改善，請回診。",
        "disclaimer": "此資訊由 AI 整理，僅供衛教參考。",
    }


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch):
    """把 lookup_drug_info 換掉，測試不依賴外部 LLM。"""
    calls = {"n": 0, "names": []}

    def _spy(name):
        calls["n"] += 1
        calls["names"].append(name)
        return _fake_acetaminophen(name)

    monkeypatch.setattr(drug_search_module, "lookup_drug_info", _spy)
    return calls


def test_search_drug_first_query_hits_llm_and_caches(_patch_llm):
    r = client.get("/drug-search/?q=普拿疼")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] is True
    assert data["name_zh"] == "乙醯胺酚"
    assert data["name_en"] == "Acetaminophen"
    assert "嚴重皮疹" in data["side_effects"]["serious"]
    assert data["cached"] is False
    assert _patch_llm["n"] == 1


def test_search_drug_second_query_hits_cache(_patch_llm):
    r1 = client.get("/drug-search/?q=普拿疼")
    assert r1.status_code == 200
    assert _patch_llm["n"] == 1

    # 第二次：完全一樣的字串 → 快取命中，不再叫 LLM
    r2 = client.get("/drug-search/?q=普拿疼")
    assert r2.status_code == 200
    data = r2.json()
    assert data["matched"] is True
    assert data["cached"] is True
    assert _patch_llm["n"] == 1, "cached query must not call LLM"
    # query_count 應該被 +1
    assert data["query_count"] >= 2


def test_search_drug_alias_hits_cache(_patch_llm):
    """用 name_zh 進來，再用 alias 查 → 應該命中同一筆快取。"""
    r1 = client.get("/drug-search/?q=Acetaminophen")
    assert r1.status_code == 200
    assert _patch_llm["n"] == 1

    # Tylenol 在假回傳的 aliases 裡
    r2 = client.get("/drug-search/?q=Tylenol")
    assert r2.status_code == 200
    data = r2.json()
    assert data["cached"] is True
    assert _patch_llm["n"] == 1, "alias must hit cache, not LLM"


def test_search_drug_unknown_does_not_cache(_patch_llm):
    r = client.get("/drug-search/?q=未知藥名XYZ")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is False
    assert _patch_llm["n"] == 1

    # 再查一次同樣的「未知」字串：因為沒寫快取，會再叫 LLM
    r2 = client.get("/drug-search/?q=未知藥名XYZ")
    assert r2.status_code == 200
    assert r2.json()["matched"] is False
    assert _patch_llm["n"] == 2


def test_search_drug_refresh_skips_cache(_patch_llm):
    client.get("/drug-search/?q=普拿疼")
    assert _patch_llm["n"] == 1
    # refresh=true 會強制重新整理
    r = client.get("/drug-search/?q=普拿疼&refresh=true")
    assert r.status_code == 200
    assert _patch_llm["n"] == 2


def test_get_single_drug_by_id(_patch_llm):
    r1 = client.get("/drug-search/?q=普拿疼")
    drug_id = r1.json()["id"]
    r2 = client.get(f"/drug-search/{drug_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == drug_id
    assert data["name_zh"] == "乙醯胺酚"


def test_get_single_drug_404(_patch_llm):
    r = client.get("/drug-search/00000000-not-exist")
    assert r.status_code == 404


def test_search_from_medication(_patch_llm):
    """從個人用藥清單一筆 medication_id 查 → 用 name 走快取邏輯。"""
    rmed = client.post(
        "/medications/",
        json={
            "patient_id": PATIENT_ID,
            "name": "普拿疼",
            "dosage": "500mg",
            "frequency": "一天三次",
        },
    )
    assert rmed.status_code == 200
    med_id = rmed.json()["id"]

    r = client.get(f"/drug-search/from-medication/{med_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is True
    assert data["name_zh"] == "乙醯胺酚"


def test_search_from_medication_404(_patch_llm):
    r = client.get("/drug-search/from-medication/no-such-id")
    assert r.status_code == 404


def test_trending_list_orders_by_query_count(_patch_llm):
    # 普拿疼查 3 次，Lipitor 查 1 次（假 LLM 不論輸入都回乙醯胺酚，所以實際上會 alias 命中）
    # 為了製造兩筆不同的 row，我們直接操作 SQLite
    sb = db_mod.get_supabase()
    sb.table("drug_reference").insert({
        "id": "drug-a", "name_zh": "藥A", "name_en": "DrugA", "query_count": 5,
    }).execute()
    sb.table("drug_reference").insert({
        "id": "drug-b", "name_zh": "藥B", "name_en": "DrugB", "query_count": 12,
    }).execute()

    r = client.get("/drug-search/trending/list?limit=10")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 2
    # B 應該排在 A 前面
    a_idx = next(i for i, it in enumerate(items) if it["id"] == "drug-a")
    b_idx = next(i for i, it in enumerate(items) if it["id"] == "drug-b")
    assert b_idx < a_idx
