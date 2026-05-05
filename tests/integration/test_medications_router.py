"""medications router 整合測試 — 用本地 SQLite fallback。

測試 GET /medications/ 回傳的 schedule 標籤、
POST /medications/log 在「每 X 小時」型藥物上的 4 小時間隔阻擋，
以及 GET /medications/can-take 的安全預覽。
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

# 以本地 SQLite 跑測試：在 import db 前清空 Supabase 環境變數
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)
os.environ.pop("VERCEL", None)
os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)

# 用獨立 DB 檔避免汙染專案根目錄
_TMP_DB = tempfile.NamedTemporaryFile(prefix="medstest_", suffix=".db", delete=False)
_TMP_DB.close()
os.environ["SQLITE_DB_PATH"] = _TMP_DB.name

# 為了讓 db.py 用我們指定的路徑，在 import 之前先 patch
import backend.db as db_mod  # noqa: E402

db_mod.DB_PATH = _TMP_DB.name
# 蓋掉模組級 Supabase 預設值，否則 get_supabase() 會走 Supabase / httpx 分支，
# 不會呼叫 _init_db()，後續 DELETE 就會撞到「table 不存在」。
db_mod.SUPABASE_URL = ""
db_mod.SUPABASE_KEY = ""
db_mod._client = None  # type: ignore[attr-defined]
db_mod._init_db()

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)

PATIENT_ID = "test-patient-123"


@pytest.fixture(autouse=True)
def _reset_db():
    """每個測試前清空 medications + medication_logs，避免互相影響。"""
    sb = db_mod.get_supabase()
    # SqliteSupabase 沒有 delete-all，用底層 sqlite3 清空
    import sqlite3

    conn = sqlite3.connect(_TMP_DB.name)
    conn.execute("DELETE FROM medication_logs")
    conn.execute("DELETE FROM medications")
    conn.execute("DELETE FROM patients")
    conn.commit()
    conn.close()
    yield


def _make_med(name: str, frequency: str) -> str:
    r = client.post(
        "/medications/",
        json={"patient_id": PATIENT_ID, "name": name, "frequency": frequency},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_get_medications_includes_schedule_slots():
    _make_med("普拿疼", "一天三次飯後")
    _make_med("安眠藥", "睡前")
    _make_med("止痛藥", "每 6 小時")

    r = client.get("/medications/", params={"patient_id": PATIENT_ID})
    assert r.status_code == 200
    meds = r.json()["medications"]
    by_name = {m["name"]: m for m in meds}

    assert by_name["普拿疼"]["slots"] == ["morning", "noon", "evening"]
    assert by_name["普拿疼"]["is_other"] is False
    assert by_name["安眠藥"]["slots"] == ["evening"]
    assert by_name["止痛藥"]["is_other"] is True
    assert by_name["止痛藥"]["interval_hours"] == 6
    assert by_name["止痛藥"]["bucket"] == "other"


def test_log_fixed_slot_is_never_blocked():
    """早 / 中 / 晚 的固定時段藥不該被 4 小時規則擋住。"""
    med_id = _make_med("普拿疼", "一天三次")
    # 連續打卡兩次，第二次也要成功
    for _ in range(2):
        r = client.post(
            "/medications/log",
            json={"patient_id": PATIENT_ID, "medication_id": med_id, "taken": True},
        )
        assert r.status_code == 200, r.text


def test_log_interval_med_blocks_within_4_hours():
    med_id = _make_med("止痛藥", "每 6 小時")

    r = client.post(
        "/medications/log",
        json={"patient_id": PATIENT_ID, "medication_id": med_id, "taken": True},
    )
    assert r.status_code == 200

    r2 = client.post(
        "/medications/log",
        json={"patient_id": PATIENT_ID, "medication_id": med_id, "taken": True},
    )
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["code"] == "dose_too_soon"
    assert "風險" in detail["message"]
    assert detail["safety"]["allowed"] is False


def test_log_interval_med_force_overrides_block():
    med_id = _make_med("止痛藥", "每 6 小時")
    client.post(
        "/medications/log",
        json={"patient_id": PATIENT_ID, "medication_id": med_id, "taken": True},
    )
    # 加上 force=True → 即使在 4 小時內也允許寫入
    r = client.post(
        "/medications/log",
        json={
            "patient_id": PATIENT_ID,
            "medication_id": med_id,
            "taken": True,
            "force": True,
        },
    )
    assert r.status_code == 200, r.text
    assert "safety" in r.json()  # 即便允許，也要回傳安全資訊讓前端可記錄


def test_log_skip_is_never_blocked():
    """跳過服藥（taken=False）不該觸發 4 小時規則。"""
    med_id = _make_med("止痛藥", "每 6 小時")
    client.post(
        "/medications/log",
        json={"patient_id": PATIENT_ID, "medication_id": med_id, "taken": True},
    )
    r = client.post(
        "/medications/log",
        json={
            "patient_id": PATIENT_ID,
            "medication_id": med_id,
            "taken": False,
            "skip_reason": "忘記了",
        },
    )
    assert r.status_code == 200, r.text


def test_can_take_endpoint_returns_safety_and_schedule():
    med_id = _make_med("止痛藥", "每 6 小時")
    r = client.get(
        "/medications/can-take",
        params={"patient_id": PATIENT_ID, "medication_id": med_id},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["schedule"]["is_other"] is True
    assert body["schedule"]["interval_hours"] == 6
    assert body["safety"]["allowed"] is True  # 沒有任何紀錄
    assert body["name"] == "止痛藥"

    # 打卡後再查 → 應該被擋
    client.post(
        "/medications/log",
        json={"patient_id": PATIENT_ID, "medication_id": med_id, "taken": True},
    )
    r2 = client.get(
        "/medications/can-take",
        params={"patient_id": PATIENT_ID, "medication_id": med_id},
    )
    body2 = r2.json()
    assert body2["safety"]["allowed"] is False
    assert body2["safety"]["level"] == "block"
