"""diseases router 整合測試 — 用本地 SQLite fallback + monkey-patch LLM / PubMed。

測試重點：
- GET /diseases/?q=… 第一次走 lookup_disease_info + pubmed_search，命中後寫入 disease_reference
- 第二次同樣字串直接走快取，不再呼叫 LLM
- 別名（aliases）也能命中快取
- LLM 表示無法辨識時，回 matched=false 且不寫快取
- POST /diseases/chat 在脈絡下追問，回覆含 references 與 disclaimer
- GET /diseases/from-symptom/{id}?disease=xxx 直接走 search 流程
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

_TMP_DB = tempfile.NamedTemporaryFile(prefix="diseasetest_", suffix=".db", delete=False)
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
from backend.routers import diseases as diseases_module  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_db():
    """每個測試前把 db 指回本檔的 SQLite，並清空 disease_reference / symptoms_log。"""
    import sqlite3

    db_mod.DB_PATH = _TMP_DB.name
    db_mod.SUPABASE_URL = ""
    db_mod.SUPABASE_KEY = ""
    db_mod._client = None  # type: ignore[attr-defined]
    db_mod._init_db()

    conn = sqlite3.connect(_TMP_DB.name)
    conn.execute("DELETE FROM disease_reference")
    try:
        conn.execute("DELETE FROM symptoms_log")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    yield


def _fake_t2dm(name: str) -> dict:
    """假的 lookup_disease_info：所有非「未知」字串都當第二型糖尿病處理。"""
    if "未知" in name or "unknownxyz" in name.lower():
        return {
            "matched": False,
            "name_zh": None,
            "name_en": None,
            "aliases": [],
            "icd10_code": None,
            "icd10_category": None,
            "overview": None,
            "causes": [],
            "symptoms": {"common": [], "warning": []},
            "common_medications": [],
            "treatments": [],
            "complications": [],
            "prognosis": None,
            "self_care": [],
            "red_flags": [],
            "disclaimer": "無法辨識此疾病名，請確認拼字。",
        }
    return {
        "matched": True,
        "name_zh": "第二型糖尿病",
        "name_en": "Type 2 Diabetes Mellitus",
        "aliases": ["T2DM", "糖尿病第二型"],
        "icd10_code": "E11",
        "icd10_category": "內分泌與代謝疾病",
        "overview": "胰島素阻抗造成的慢性血糖偏高，可以靠飲食、運動、藥物穩定控制。",
        "causes": ["遺傳", "肥胖", "缺乏運動"],
        "symptoms": {
            "common": ["多渴", "多尿", "疲倦"],
            "warning": ["意識模糊", "酮酸中毒徵兆"],
        },
        "common_medications": [
            {"name": "Metformin", "drug_class": "雙胍類", "purpose": "降低肝臟糖質新生"},
        ],
        "treatments": ["飲食控制", "規律運動", "胰島素治療（晚期）"],
        "complications": ["糖尿病腎病變", "視網膜病變", "周邊神經病變"],
        "prognosis": "規律治療下大多數人可以維持與一般人相近的生活品質。",
        "self_care": ["每天監測血糖", "每年眼科檢查", "戒菸"],
        "red_flags": ["昏迷", "持續嘔吐", "酮酸中毒"],
        "disclaimer": "此資訊由 AI 整理，僅供衛教參考。",
    }


_FAKE_PUBMED = [
    {
        "pmid": "12345678",
        "title": "Recent advances in T2DM management",
        "authors": "Smith J 等",
        "year": "2024",
        "journal": "NEJM",
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    }
]


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch):
    """換掉 lookup_disease_info / pubmed_search / disease_chat，測試不依賴外部服務。"""
    calls = {"info": 0, "pubmed": 0, "chat": 0}

    def _info(name):
        calls["info"] += 1
        return _fake_t2dm(name)

    def _pubmed(query, max_results=3):
        calls["pubmed"] += 1
        return list(_FAKE_PUBMED[:max_results])

    def _chat(context, message, history=None):
        calls["chat"] += 1
        return f"關於{context.get('name_zh') or context.get('name_en')}：{message[:30]} … 回覆內容。"

    monkeypatch.setattr(diseases_module, "lookup_disease_info", _info)
    monkeypatch.setattr(diseases_module, "pubmed_search", _pubmed)
    monkeypatch.setattr(diseases_module, "disease_chat", _chat)
    return calls


def test_search_disease_first_query_hits_llm_and_caches(_patch_llm):
    r = client.get("/diseases/?q=糖尿病")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] is True
    assert data["name_zh"] == "第二型糖尿病"
    assert data["icd10_code"] == "E11"
    assert "Metformin" in data["common_medications"][0]["name"]
    assert data["references"] and data["references"][0]["pmid"] == "12345678"
    assert data["disclaimer"]
    assert data["cached"] is False
    assert _patch_llm["info"] == 1
    assert _patch_llm["pubmed"] == 1


def test_search_disease_second_query_hits_cache(_patch_llm):
    r1 = client.get("/diseases/?q=糖尿病")
    assert r1.status_code == 200
    assert _patch_llm["info"] == 1

    r2 = client.get("/diseases/?q=糖尿病")
    assert r2.status_code == 200
    data = r2.json()
    assert data["matched"] is True
    assert data["cached"] is True
    assert data["references"] and data["references"][0]["pmid"] == "12345678"
    assert _patch_llm["info"] == 1, "cached query must not call LLM"
    assert _patch_llm["pubmed"] == 1, "cached query must not call PubMed"
    assert data["query_count"] >= 2


def test_search_disease_alias_hits_cache(_patch_llm):
    r1 = client.get("/diseases/?q=糖尿病")
    assert r1.status_code == 200

    # 別名命中
    r2 = client.get("/diseases/?q=T2DM")
    assert r2.status_code == 200
    data = r2.json()
    assert data["matched"] is True
    assert data["cached"] is True
    assert _patch_llm["info"] == 1, "alias hit must not call LLM"


def test_search_disease_unknown_does_not_cache(_patch_llm):
    r = client.get("/diseases/?q=未知疾病abc")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is False
    assert "disclaimer" in data
    # 不會寫快取，所以 trending 還是空
    r2 = client.get("/diseases/trending/list")
    assert r2.json()["items"] == []


def test_disease_chat_uses_cached_context(_patch_llm):
    # 先建立快取
    r = client.get("/diseases/?q=糖尿病")
    assert r.status_code == 200
    disease_id = r.json()["id"]

    chat = client.post(
        "/diseases/chat",
        json={
            "disease_id": disease_id,
            "message": "我這個年紀該多久回診一次？",
        },
    )
    assert chat.status_code == 200, chat.text
    data = chat.json()
    assert data["disease_name"] == "第二型糖尿病"
    assert "第二型糖尿病" in data["reply"] or "Type 2" in data["reply"]
    assert data["references"] and data["references"][0]["pmid"] == "12345678"
    assert data["disclaimer"]
    assert _patch_llm["chat"] == 1


def test_disease_chat_lazy_creates_when_no_cache(_patch_llm):
    # 沒先 search，直接走 chat 並指定 disease_query — 後端會 lazy 建立快取
    chat = client.post(
        "/diseases/chat",
        json={
            "disease_query": "糖尿病",
            "message": "可以喝咖啡嗎？",
        },
    )
    assert chat.status_code == 200, chat.text
    data = chat.json()
    assert data["disease_name"] == "第二型糖尿病"
    # lazy 建立時也要拉 PubMed
    assert _patch_llm["pubmed"] == 1


def test_from_symptom_with_explicit_disease_param(_patch_llm):
    r = client.get("/diseases/from-symptom/anything?disease=糖尿病")
    assert r.status_code == 200
    data = r.json()
    assert data["matched"] is True
    assert data["name_zh"] == "第二型糖尿病"


def test_trending_after_two_queries(_patch_llm):
    client.get("/diseases/?q=糖尿病")
    client.get("/diseases/?q=糖尿病")  # 第二次走快取
    r = client.get("/diseases/trending/list")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["name_zh"] == "第二型糖尿病"
    assert items[0]["query_count"] >= 2
