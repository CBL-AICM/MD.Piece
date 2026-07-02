"""rewards router 端點整合測試（本地 SQLite fallback）。

驗證意圖（鐵則 9）：純規則已有 test_rewards_rules.py 覆蓋，但 router 層的組裝
（_gather_activity 解包、餘額換算、兌換寫入、後台狀態轉換、台灣日界）先前完全沒有
端點測試——正因如此 PR #593 把 _gather_activity 從 3-tuple 改 2-tuple 時，catalog/redeem
兩處漏改的解包錯誤（每次呼叫必 500）能一路上線。這些測試就是要在那類漂移時亮紅燈：

  - /catalog、/redeem 不得因解包/組裝錯誤 500（迴歸鎖）。
  - 餘額檢查真的擋下超額兌換、放行付得起的兌換，並寫入一筆 requested。
  - 打卡日以「台灣（+8）日曆日」計，UTC 前一晚 23:30 要算成隔天。
  - 後台各狀態計數反映全表，不受 status 過濾 / limit 截斷影響。
  - 兌換狀態轉換單向：已核發不能再退回（409），避免併發覆蓋。

執行：pytest tests/integration/test_rewards_router.py
"""

import os
import tempfile

import pytest

os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)
os.environ.pop("VERCEL", None)

_TMP_DB = tempfile.NamedTemporaryFile(prefix="rewardstest_", suffix=".db", delete=False)
_TMP_DB.close()

import backend.db as db_mod  # noqa: E402

db_mod.DB_PATH = _TMP_DB.name
db_mod.SUPABASE_URL = ""
db_mod.SUPABASE_KEY = ""
db_mod._client = None  # type: ignore[attr-defined]
db_mod._init_db()

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.security import create_access_token  # noqa: E402

client = TestClient(app)
PID = "rw-test-patient"
DOCTOR_TOKEN = create_access_token({"id": "rw-doc", "username": "doc", "role": "doctor"})
DOCTOR_HDR = {"Authorization": f"Bearer {DOCTOR_TOKEN}"}


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
    for t in ("symptom_entries", "vital_entries", "emotions",
              "medication_logs", "reward_redemptions"):
        try:
            conn.execute(f"DELETE FROM {t}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    yield


def _seed_symptom(day_utc, pid=PID):
    """在 symptom_entries 塞一筆，recorded_at 為 UTC ISO（含時間）。"""
    db_mod.get_supabase().table("symptom_entries").insert({
        "patient_id": pid,
        "category_id": "test",
        "recorded_at": day_utc,
    }).execute()


def _seed_active_days(n, pid=PID):
    """塞 n 個「不相鄰」的活躍日（避免連續里程碑加分），每日 earned=PER_ACTIVE_DAY。
    用 UTC 中午（+8 後仍同日）避免日界干擾。實際點數由 API 斷言，不在此回傳。"""
    for i in range(n):
        day = 1 + i * 2  # 1,3,5,... 不相鄰
        _seed_symptom(f"2026-06-{day:02d}T04:00:00", pid)


# ── 迴歸：catalog / redeem 不得 500（PR #593 解包漏改的正是這兩支）──

def test_catalog_with_patient_id_returns_200_not_500():
    # 為什麼：這是「獎勵頁整頁載入失敗」的根因端點；帶 patient_id 曾必 500。
    _seed_symptom("2026-06-01T04:00:00")
    r = client.get(f"/rewards/catalog?patient_id={PID}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "catalog" in body and isinstance(body["catalog"], list)
    assert body["catalog"], "catalog 不該為空（CATALOG 有預設品項）"


def test_summary_returns_points_shape():
    _seed_symptom("2026-06-01T04:00:00")
    r = client.get(f"/rewards/summary?patient_id={PID}")
    assert r.status_code == 200, r.text
    pts = r.json().get("points") or {}
    assert set(("earned", "spent", "available")) <= set(pts)


# ── 餘額檢查與兌換寫入 ─────────────────────────────────────

def test_redeem_rejects_when_insufficient():
    # 為什麼：餘額不足必須擋下，否則帳本超支、院方多發實品。
    _seed_symptom("2026-06-01T04:00:00")  # 只有 10 點
    r = client.post("/rewards/redeem", json={"patient_id": PID, "reward_id": "health-kit"})  # 需 200
    assert r.status_code == 400, r.text
    assert "點數不足" in r.json().get("detail", "")


def test_redeem_succeeds_and_records_redemption():
    # 為什麼：付得起就該成功、寫入一筆 requested，並讓 available 依實扣減。
    _seed_active_days(5)  # 5 個不相鄰活躍日 → earned=50，剛好付得起 edu-booklet(50)
    r = client.post("/rewards/redeem", json={"patient_id": PID, "reward_id": "edu-booklet"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "requested"
    assert body["available_after"] == 0  # 50 - 50

    # 兌換後餘額真的扣掉、且出現在兌換紀錄
    summ = client.get(f"/rewards/summary?patient_id={PID}").json()
    assert summ["points"]["spent"] == 50
    assert summ["points"]["available"] == 0
    reds = client.get(f"/rewards/redemptions?patient_id={PID}").json()["redemptions"]
    assert len(reds) == 1 and reds[0]["reward_id"] == "edu-booklet"


# ── 台灣日界（+8）─────────────────────────────────────────

def test_checkin_day_uses_taiwan_calendar_day():
    # 為什麼：時間戳存 UTC，但打卡日要以台灣日曆日計。
    # UTC 2026-06-30 23:30 == 台灣 2026-07-01 07:30 → 應算在 07-01。
    _seed_symptom("2026-06-30T23:30:00")
    summ = client.get(f"/rewards/summary?patient_id={PID}").json()
    ledger_dates = [e.get("date") for e in summ.get("ledger", [])]
    assert "2026-07-01" in ledger_dates
    assert "2026-06-30" not in ledger_dates


# ── 後台：計數反映全表，狀態轉換單向 ──────────────────────

def _make_redemption(status="requested", pid=PID, reward_id="edu-booklet", cost=50):
    db_mod.get_supabase().table("reward_redemptions").insert({
        "patient_id": pid, "reward_id": reward_id, "reward_name": "x",
        "cost": cost, "status": status,
    }).execute()


def test_admin_counts_reflect_whole_table_not_filtered_page():
    # 為什麼：帶 status 過濾時，其他狀態的計數不該被歸零。
    _make_redemption("requested")
    _make_redemption("requested")
    _make_redemption("fulfilled")
    _make_redemption("cancelled")
    r = client.get("/rewards/admin/redemptions?status=requested", headers=DOCTOR_HDR)
    assert r.status_code == 200, r.text
    body = r.json()
    # 列表被過濾成只有 requested，但計數要看全表
    assert all(x["status"] == "requested" for x in body["redemptions"])
    assert body["counts"]["requested"] == 2
    assert body["counts"]["fulfilled"] == 1
    assert body["counts"]["cancelled"] == 1


def test_fulfilled_cannot_be_cancelled():
    # 為什麼：已核發（實品已發）不得再退回退點，避免併發覆蓋造成雙拿。
    _seed_active_days(5)
    rid = client.post("/rewards/redeem", json={"patient_id": PID, "reward_id": "edu-booklet"}).json()["id"]
    assert client.post(f"/rewards/admin/redemptions/{rid}/fulfill", headers=DOCTOR_HDR).status_code == 200
    conflict = client.post(f"/rewards/admin/redemptions/{rid}/cancel", headers=DOCTOR_HDR)
    assert conflict.status_code == 409, conflict.text


def test_admin_requires_doctor_role():
    # 為什麼：後台發放僅限醫護；病患 token 不得存取。
    patient_token = create_access_token({"id": PID, "role": "patient"})
    r = client.get("/rewards/admin/redemptions", headers={"Authorization": f"Bearer {patient_token}"})
    assert r.status_code == 403, r.text
