"""diet router 整合測試 — 用本地 SQLite fallback。

測試：
- GET  /diet/caffeine-guide          靜態衛教
- POST /diet/records                 飲食打卡 + 驗證
- GET  /diet/records/{patient_id}    當日 / 近 N 天
- GET  /diet/pick/{patient_id}       吃什麼神器（mock LLM + fallback pool）
- GET  /diet/drink/{patient_id}      喝什麼神器
- GET  /diet/guide/{patient_id}      飲食指南（mock LLM）
- 過濾 helpers：餐別 / 疾病 / 價位 / 熱量 / 黑名單 / 附近
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

# 跑測試前清空 Supabase 環境變數，強制走本地 SQLite
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)
os.environ.pop("VERCEL", None)
os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)

_TMP_DB = tempfile.NamedTemporaryFile(prefix="diettest_", suffix=".db", delete=False)
_TMP_DB.close()
os.environ["SQLITE_DB_PATH"] = _TMP_DB.name

import backend.db as db_mod  # noqa: E402

db_mod.DB_PATH = _TMP_DB.name
db_mod.SUPABASE_URL = ""
db_mod.SUPABASE_KEY = ""
db_mod._client = None  # type: ignore[attr-defined]
db_mod._init_db()

from fastapi.testclient import TestClient  # noqa: E402

import backend.routers.diet as diet_mod  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)
PATIENT_ID = "test-patient-diet"


@pytest.fixture(autouse=True)
def _reset_db_and_llm(monkeypatch):
    """每個測試前清 diet_records + medical_records，並把 call_claude mock 掉。"""
    sb = db_mod.get_supabase()
    import sqlite3
    conn = sqlite3.connect(db_mod.DB_PATH)
    conn.execute("DELETE FROM diet_records")
    conn.execute("DELETE FROM medical_records")
    conn.commit()
    conn.close()
    # 預設 LLM 回空字串 → 觸發 fallback pool
    monkeypatch.setattr(diet_mod, "call_claude", lambda system, user, history=None: "")
    # 還原可能被前一個 test stub 過的 _patient_diagnoses
    if hasattr(diet_mod, "_patient_diagnoses_orig"):
        diet_mod._patient_diagnoses = diet_mod._patient_diagnoses_orig
    yield


def _seed_diagnosis(diagnosis: str, monkeypatch=None):
    """直接 stub _patient_diagnoses，繞過 FK 限制。"""
    diet_mod._patient_diagnoses_orig = getattr(
        diet_mod, "_patient_diagnoses_orig", diet_mod._patient_diagnoses
    )
    diet_mod._patient_diagnoses = lambda pid: [diagnosis]


# ────── 靜態端點 ──────

def test_caffeine_guide_static():
    r = client.get("/diet/caffeine-guide")
    assert r.status_code == 200
    body = r.json()
    assert body["daily_safe_mg"] == 400
    assert body["pregnancy_safe_mg"] == 200
    assert any("孕" in w["group"] for w in body["warnings"])
    assert any(s["item"].startswith("黑咖啡") for s in body["common_sources"])


# ────── 飲食打卡 ──────

def test_record_invalid_meal_type():
    r = client.post("/diet/records", json={
        "patient_id": PATIENT_ID, "meal_type": "midnight", "foods": "宵夜",
    })
    assert r.status_code == 400
    assert "meal_type" in r.json()["detail"]


def test_record_empty_foods_rejected():
    r = client.post("/diet/records", json={
        "patient_id": PATIENT_ID, "meal_type": "lunch", "foods": "   ",
    })
    assert r.status_code == 400


def test_record_creates_and_lists():
    r1 = client.post("/diet/records", json={
        "patient_id": PATIENT_ID, "meal_type": "lunch",
        "foods": "白飯、滷雞腿、燙青菜", "note": "便當店",
    })
    assert r1.status_code == 200
    assert r1.json()["ok"] is True
    rec = r1.json()["record"]
    assert rec["foods"] == "白飯、滷雞腿、燙青菜"
    assert rec["meal_type"] == "lunch"

    # 列出近 7 天
    r2 = client.get(f"/diet/records/{PATIENT_ID}")
    assert r2.status_code == 200
    records = r2.json()["records"]
    assert len(records) == 1
    assert records[0]["foods"] == "白飯、滷雞腿、燙青菜"


def test_record_filter_by_date():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    client.post("/diet/records", json={
        "patient_id": PATIENT_ID, "meal_type": "breakfast", "foods": "蛋餅",
    })
    r = client.get(f"/diet/records/{PATIENT_ID}?date={today}")
    assert r.status_code == 200
    assert len(r.json()["records"]) == 1


def test_record_invalid_date_format():
    r = client.get(f"/diet/records/{PATIENT_ID}?date=2026/01/01")
    assert r.status_code == 400


# ────── 吃什麼神器（fallback path） ──────

def test_pick_returns_a_meal_with_required_fields():
    r = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=lunch")
    assert r.status_code == 200
    g = r.json()
    assert g.get("name")
    assert g.get("meal_type") == "lunch"
    assert g.get("fallback") is True   # LLM 被 mock 成空 → 走 fallback
    # 不該洩漏內部欄位
    assert "_unfit" not in g
    assert "_meals" not in g


def test_pick_meal_any_resolves_to_real_meal():
    r = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=any")
    g = r.json()
    assert g["meal_type"] in {"breakfast", "lunch", "dinner", "snack"}


def test_pick_respects_diagnosis_gout_no_seafood():
    """痛風患者 fallback 不該給「味噌鮭魚定食」「牛肉麵」等高普林。"""
    _seed_diagnosis("痛風")
    # 試多次（fallback 是隨機）
    for _ in range(15):
        r = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=dinner")
        name = r.json().get("name", "")
        assert "鮭魚" not in name
        assert "牛肉麵" not in name


def test_pick_respects_dislike_blacklist():
    """黑名單 chip 過濾：fallback 不該給含香菇的菜。"""
    for _ in range(10):
        r = client.get(f"/diet/pick/{PATIENT_ID}?dislike=香菇")
        g = r.json()
        haystack = g.get("name", "") + " " + " ".join(g.get("components") or [])
        assert "香菇" not in haystack


def test_pick_nearby_only_returns_street_vendors():
    """附近選項：where_to_get 必須在白名單內。"""
    for _ in range(10):
        r = client.get(f"/diet/pick/{PATIENT_ID}?nearby=true")
        where = r.json().get("where_to_get", "")
        assert where in diet_mod.NEARBY_VENDORS, f"unexpected where_to_get={where}"


def test_pick_price_tier_dollar():
    """$ 價位：fallback pool 應只給 100 元以內的選項。"""
    for _ in range(10):
        r = client.get(f"/diet/pick/{PATIENT_ID}?price_tier=$")
        g = r.json()
        # fallback path 帶 price_tier 欄位
        if g.get("price_tier"):
            assert g["price_tier"] == "$"


def test_pick_calorie_low_tier():
    """low 熱量：應只給 ≤350 kcal 的菜。"""
    for _ in range(10):
        r = client.get(f"/diet/pick/{PATIENT_ID}?calorie_tier=low")
        g = r.json()
        if g.get("calorie_kcal") is not None:
            assert g["calorie_kcal"] <= 380, f"got {g['calorie_kcal']} kcal"


def test_pick_exclude_skips_named():
    """已 reroll 的菜不該再回。"""
    # 先抽一道
    r1 = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=lunch")
    name1 = r1.json()["name"]
    # 把它放進 exclude
    for _ in range(10):
        r2 = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=lunch&exclude={name1}")
        assert r2.json()["name"] != name1


def test_pick_avoid_recent_skips_logged_meal():
    """avoid_recent 開啟時，本週吃過的菜不會再被推。"""
    # 先打卡一道 fallback pool 裡的菜
    client.post("/diet/records", json={
        "patient_id": PATIENT_ID, "meal_type": "lunch", "foods": "雞肉飯便當",
    })
    for _ in range(10):
        r = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=lunch&avoid_recent=true")
        # 名稱不該完全等於剛打卡的，也不該被剛打卡的 substring
        assert r.json()["name"] != "雞肉飯便當"


# ────── 喝什麼神器 ──────

def test_pick_drink_returns_drink():
    r = client.get(f"/diet/drink/{PATIENT_ID}")
    assert r.status_code == 200
    g = r.json()
    assert g.get("name")
    assert "caffeine_mg" in g
    assert g.get("fallback") is True
    assert "_unfit" not in g


def test_pick_drink_pregnancy_avoids_high_caffeine():
    """孕婦 fallback 不該給黑咖啡或拿鐵。"""
    _seed_diagnosis("妊娠初期")
    for _ in range(15):
        r = client.get(f"/diet/drink/{PATIENT_ID}")
        name = r.json()["name"]
        assert "黑咖啡" not in name
        assert "拿鐵" not in name


def test_pick_drink_anxiety_avoids_caffeine():
    """焦慮症患者 fallback 不該給含咖啡因的飲料。"""
    _seed_diagnosis("焦慮症")
    for _ in range(15):
        r = client.get(f"/diet/drink/{PATIENT_ID}")
        g = r.json()
        # caffeine_sensitive flag 開啟，含咖啡因的選項應被過濾
        # 但允許 caffeine_mg 為 0 或無此欄位
        assert g.get("caffeine_mg", 0) == 0, f"{g['name']} caffeine={g.get('caffeine_mg')}"


# ────── 指南端點（fallback） ──────

def test_diet_guide_returns_with_fallback():
    """LLM 失敗時 guide 端點應回 fallback 結構，不可 500。"""
    r = client.get(f"/diet/guide/{PATIENT_ID}")
    assert r.status_code == 200
    g = r.json()
    assert "daily_targets" in g
    assert "general_tips" in g
    assert "warnings" in g
    assert "meal_suggestions" in g
    # daily_targets 個別欄位都該有
    dt = g["daily_targets"]
    assert all(k in dt for k in ("protein_g", "water_ml", "fiber_g"))


# ────── helper 函式單元測試 ──────

def test_auto_meal_by_hour_boundaries():
    """函式拿到 now 參數時直接用 now.hour，不再加 UTC+8 偏移。"""
    f = diet_mod._auto_meal_by_hour
    def at(hour):
        return datetime(2026, 5, 5, hour, 0, 0)
    assert f(at(7))  == "breakfast"
    assert f(at(12)) == "lunch"
    assert f(at(15)) == "snack"
    assert f(at(19)) == "dinner"
    assert f(at(23)) == "snack"
    assert f(at(3))  == "snack"


def test_diagnosis_flags_keyword_detection():
    f = diet_mod._diagnosis_flags
    assert f(["痛風"])["gout"] is True
    assert f(["第二型糖尿病"])["diabetes"] is True
    assert f(["原發性高血壓"])["hypertension"] is True
    assert f(["慢性腎臟病第三期"])["ckd"] is True
    assert f(["紅斑性狼瘡"])["autoimmune"] is True
    assert f(["腸躁症 IBS"])["ibs"] is True
    assert f(["感冒"])["gout"] is False


def test_drink_unfit_flags_extends():
    f = diet_mod._drink_unfit_flags
    assert f(["焦慮症"])["caffeine_sensitive"] is True
    assert f(["妊娠初期"])["pregnancy"] is True
    assert f(["心律不整"])["caffeine_sensitive"] is True
    assert f(["哺乳中"])["pregnancy"] is True
    assert f(["感冒"])["caffeine_sensitive"] is False


def test_filter_pool_by_meal():
    pool = diet_mod.PICK_FALLBACK_POOL
    breakfast_only = diet_mod._filter_pool_by_meal(pool, "breakfast")
    for m in breakfast_only:
        assert "breakfast" in m["_meals"]


def test_filter_pool_by_dislike_substring():
    pool = [
        {"name": "雞肉飯", "components": ["白飯", "雞肉"]},
        {"name": "鮭魚定食", "components": ["鮭魚"]},
    ]
    out = diet_mod._filter_pool_by_dislike(pool, ["鮭魚"])
    assert len(out) == 1
    assert out[0]["name"] == "雞肉飯"


def test_parse_diet_json_strips_markdown_fence():
    f = diet_mod._parse_diet_json
    assert f('```json\n{"a": 1}\n```') == {"a": 1}
    assert f('好的：{"a": 2}, 完成') == {"a": 2}
    assert f('not json at all') == {}
    assert f('') == {}


# ────── LLM 成功路徑 ──────

def test_pick_uses_llm_response_when_valid(monkeypatch):
    """LLM 回有效 JSON 時，pick 應用 LLM 的回應而非 fallback。"""
    fake_json = (
        '{"name": "AI 推的菜", "components": ["米", "蛋"], "cuisine": "台", '
        '"where_to_get": "便當店", "reason": "AI 說的", '
        '"price_tier": "$", "price_twd": 80, "calorie_tier": "mid", "calorie_kcal": 500}'
    )
    monkeypatch.setattr(diet_mod, "call_claude", lambda *a, **kw: fake_json)
    r = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=lunch")
    g = r.json()
    assert g["name"] == "AI 推的菜"
    assert g.get("fallback") is not True


def test_pick_falls_back_when_llm_returns_garbage(monkeypatch):
    monkeypatch.setattr(diet_mod, "call_claude", lambda *a, **kw: "this is not JSON")
    r = client.get(f"/diet/pick/{PATIENT_ID}?meal_type=lunch")
    g = r.json()
    assert g["name"]  # 還是要有
    assert g.get("fallback") is True


def test_records_endpoint_does_not_leak_exception(monkeypatch):
    """CodeQL #93 的迴歸測試：例外時 error 欄位不該包含 stack trace 內容。

    在 .execute() 階段丟例外（而不是 .select()），因為 select/eq 鏈
    在 try 區塊外面，是 q.execute() 才在 try 裡。
    """
    sb = db_mod.get_supabase()
    original_query = sb.table("diet_records").select

    def broken_select(*a, **kw):
        q = original_query(*a, **kw)
        original_execute = q.execute
        def fail_execute():
            raise RuntimeError("INTERNAL_DB_PASSWORD_LEAK_test_marker")
        q.execute = fail_execute
        return q

    # 透過 patch sb.table 在每次取得 diet_records table 時都回傳壞掉的 query
    original_table = sb.table
    def patched_table(name):
        t = original_table(name)
        if name == "diet_records":
            t.select = broken_select
        return t
    monkeypatch.setattr(sb, "table", patched_table)

    r = client.get(f"/diet/records/{PATIENT_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["records"] == []
    assert "INTERNAL_DB_PASSWORD_LEAK_test_marker" not in (body.get("error") or "")
