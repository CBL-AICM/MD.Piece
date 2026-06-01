"""sleep router 整合測試（規格 §7 驗收 #1, #3, #4, #6）— 本地 SQLite fallback。

驗證意圖（鐵則 9）：
  - ingest pipeline 端到端寫入一筆 auto session、指標合理。
  - 三種 source 都能寫入並正確標記。
  - 手動修正 auto 紀錄 → is_edited=true、原值保留在 sleep_edits、指標重算。
  - 趨勢彙整與 CSV 匯出可運作。
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest

os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)
os.environ.pop("VERCEL", None)

_TMP_DB = tempfile.NamedTemporaryFile(prefix="sleeptest_", suffix=".db", delete=False)
_TMP_DB.close()

import backend.db as db_mod  # noqa: E402

db_mod.DB_PATH = _TMP_DB.name
db_mod.SUPABASE_URL = ""
db_mod.SUPABASE_KEY = ""
db_mod._client = None  # type: ignore[attr-defined]
db_mod._init_db()

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

USER = "sleep-test-1"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_db():
    import sqlite3
    db_mod.DB_PATH = _TMP_DB.name
    db_mod.SUPABASE_URL = ""
    db_mod.SUPABASE_KEY = ""
    db_mod._client = None  # type: ignore[attr-defined]
    db_mod._init_db()
    db_mod.get_supabase()
    conn = sqlite3.connect(_TMP_DB.name)
    conn.execute("DELETE FROM sleep_sessions")
    conn.execute("DELETE FROM sleep_edits")
    conn.commit()
    conn.close()
    yield


# 測試睡眠資料一律以「昨晚」為基準：list/export/trend 端點預設只回近 30 天，
# 早期寫死 2026-05-01 在跨月後會悄悄掉出時間窗而誤判失敗（規則 9）。端點的窗
# 邏輯本身正確（有明確的 days 參數），故修測試、不動端點。同檔 test_trend_aggregates
# 早已用相對日期，這裡統一沿用同一寫法（規則 7）。
_LAST_NIGHT = (datetime.utcnow() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def _gen_epochs(start_iso_hour=23, mins=480, activity=0.0):
    base = _LAST_NIGHT.replace(hour=start_iso_hour)
    return [
        {"timestamp": (base + timedelta(minutes=i)).isoformat(), "activity_count": activity}
        for i in range(mins)
    ]


# ── 驗收 #1：ingest pipeline 端到端 ───────────────────────

def test_ingest_pipeline_creates_auto_session():
    r = client.post("/sleep/ingest", json={"user_id": USER, "epochs": _gen_epochs()})
    assert r.status_code == 200, r.text
    session = r.json()["session"]
    assert session is not None
    assert session["source"] == "auto"
    assert session["total_sleep_minutes"] > 400
    assert 0.0 <= session["sleep_efficiency"] <= 1.0
    assert session["classifier"] == "cole_kripke"


def test_ingest_daytime_signal_no_session():
    """白天訊號不在夜間時段 → 不產生 session（規格 §3.2）。"""
    r = client.post("/sleep/ingest", json={"user_id": USER, "epochs": _gen_epochs(start_iso_hour=13)})
    assert r.status_code == 200
    assert r.json()["session"] is None


# ── 驗收 #3：三種來源 + 修正保留原值 ──────────────────────

def test_three_sources_write_with_correct_tag():
    bed = _LAST_NIGHT.replace(hour=23)
    for src in ("manual", "imported"):
        r = client.post("/sleep/sessions", json={
            "user_id": USER, "source": src,
            "bed_time": bed.isoformat(),
            "sleep_onset": (bed + timedelta(minutes=20)).isoformat(),
            "wake_time": (bed + timedelta(hours=8)).isoformat(),
        })
        assert r.status_code == 200, r.text
        assert r.json()["source"] == src
        assert r.json()["is_edited"] in (False, 0)
    # auto 來自 ingest
    client.post("/sleep/ingest", json={"user_id": USER, "epochs": _gen_epochs()})
    sources = {s["source"] for s in client.get("/sleep/sessions", params={"user_id": USER}).json()["sessions"]}
    assert sources == {"manual", "imported", "auto"}


def test_create_session_rejects_bad_time_order():
    r = client.post("/sleep/sessions", json={
        "user_id": USER, "source": "manual",
        "bed_time": "2026-05-01T23:00:00",
        "sleep_onset": "2026-05-01T22:00:00",  # onset 早於 bed → 不合法
        "wake_time": "2026-05-02T07:00:00",
    })
    assert r.status_code == 400


def test_edit_sets_is_edited_and_preserves_original():
    """修正 auto 紀錄：is_edited=true、原值留在 sleep_edits、指標重算（規格 §4）。"""
    ing = client.post("/sleep/ingest", json={"user_id": USER, "epochs": _gen_epochs()})
    sid = ing.json()["session"]["id"]
    orig_onset = ing.json()["session"]["sleep_onset"]

    # 把入睡時間往後改 1 小時（相對於這筆紀錄的就寢時間，避免寫死日期）
    bed_dt = datetime.fromisoformat(ing.json()["session"]["bed_time"])
    edited = client.put(f"/sleep/sessions/{sid}", json={
        "sleep_onset": (bed_dt + timedelta(hours=1)).isoformat(),
    })
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["is_edited"] in (True, 1)
    assert body["sleep_onset"] != orig_onset

    # 原值應保留在 sleep_edits log
    import sqlite3
    conn = sqlite3.connect(_TMP_DB.name)
    rows = conn.execute("SELECT previous_values FROM sleep_edits WHERE session_id=?", (sid,)).fetchall()
    conn.close()
    assert len(rows) == 1
    assert orig_onset in rows[0][0]   # 原 onset 被保存


# ── 驗收 #4 / #6：趨勢 + 匯出 ─────────────────────────────

def test_trend_aggregates():
    # 用「昨晚」的時間點，確保落在近 7 天視窗內（trend 依現在時間往回算）
    last_night = datetime.utcnow() - timedelta(days=1)
    bed = last_night.replace(hour=23, minute=0, second=0, microsecond=0)
    onset = bed + timedelta(minutes=20)
    wake = bed + timedelta(hours=8)
    client.post("/sleep/sessions", json={
        "user_id": USER, "source": "manual",
        "bed_time": bed.isoformat(),
        "sleep_onset": onset.isoformat(),
        "wake_time": wake.isoformat(),
    })
    r = client.get("/sleep/trend", params={"user_id": USER, "days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["avg_total_sleep_minutes"] is not None
    assert len(body["points"]) == 1


def test_export_csv():
    bed = _LAST_NIGHT.replace(hour=23)
    client.post("/sleep/sessions", json={
        "user_id": USER, "source": "manual",
        "bed_time": bed.isoformat(),
        "sleep_onset": (bed + timedelta(minutes=20)).isoformat(),
        "wake_time": (bed + timedelta(hours=8)).isoformat(),
    })
    r = client.get("/sleep/export.csv", params={"user_id": USER})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    text = r.text
    assert "total_sleep_minutes" in text   # 表頭
    assert "manual" in text                # 資料列
    # 設計邊界：匯出純資料，不得有診斷/評語字眼
    for banned in ("診斷", "風險", "睡得很糟", "建議就醫"):
        assert banned not in text
