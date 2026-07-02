"""跨帳號資料隔離整合測試（Issue：不同帳號看到同一筆資料）。

驗證 enforce_patient_scope 在已遷移的日常紀錄 router 上的行為：
- 已登入帳號 A 不可讀寫帳號 B 的資料（→ 403）。這是 bug 的核心：少了這層，
  A 帶著 B 的 patient_id 就能看 B 的紀錄。
- 已登入帳號存取自己的資料正常（→ 200）。
- demo 匿名（不帶 token）維持可用（→ 200），不因加驗證而被擋掉。
- GET /records/ 不帶 patient_id 時不再回「全部病患」的病歷（舊 P0 洩漏）。

用本地 SQLite fallback（與 test_medications_router 同模式）。
"""

import pytest

import backend.db as db_mod
from fastapi.testclient import TestClient

from backend.main import app
from backend.security import create_access_token

PATIENT_A = "patient-aaa-1111"
PATIENT_B = "patient-bbb-2222"

_TOKEN_A = create_access_token({"id": PATIENT_A, "username": "alice", "role": "patient"})
_AUTH_A = {"Authorization": f"Bearer {_TOKEN_A}"}

# 預設無 token 的 client（demo 匿名）；要帶 A 的身分時各別傳 headers。
client = TestClient(app)


def test_logged_in_cannot_read_other_account_vitals():
    """A 登入後帶 B 的 patient_id 讀生理紀錄 → 403。

    若拿掉 enforce_patient_scope，這裡會變 200 並回傳 B 的資料 —— 正是回報的
    「不同帳號看到同一筆」。所以這個 403 直接編碼了 bug 的修復意圖。
    """
    r = client.get("/vitals/", params={"patient_id": PATIENT_B}, headers=_AUTH_A)
    assert r.status_code == 403, r.text


def test_logged_in_cannot_write_other_account_emotion():
    """A 不可用 B 的 patient_id 寫情緒紀錄 → 403（避免竄改他人資料）。"""
    r = client.post(
        "/emotions/",
        json={"patient_id": PATIENT_B, "score": 1, "note": "x"},
        headers=_AUTH_A,
    )
    assert r.status_code == 403, r.text


def test_logged_in_can_access_own_data():
    """A 存取自己的 patient_id → 正常（200）。"""
    r = client.get("/vitals/", params={"patient_id": PATIENT_A}, headers=_AUTH_A)
    assert r.status_code == 200, r.text
    assert "entries" in r.json()

    r2 = client.post(
        "/memos/",
        json={"patient_id": PATIENT_A, "client_id": "m1", "content": "hi"},
        headers=_AUTH_A,
    )
    assert r2.status_code == 200, r2.text


def test_demo_anonymous_still_allowed():
    """不帶 token 的 demo 匿名使用者照常讀寫（產品保留匿名可用）。"""
    r = client.get("/vitals/", params={"patient_id": "demo-device-uuid"})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "path, params",
    [
        ("/timeline", {"patient_id": PATIENT_B}),
        ("/reminders/", {"patient_id": PATIENT_B}),
        ("/reminders/inbox/list", {"patient_id": PATIENT_B}),
        ("/follow-ups/", {"patient_id": PATIENT_B}),
        ("/sleep/sessions", {"user_id": PATIENT_B}),
        ("/diet/records/" + PATIENT_B, {}),
        ("/menstrual/cycles", {"patient_id": PATIENT_B}),
        ("/admissions/", {"patient_id": PATIENT_B}),
        ("/inpatient/bedside", {"patient_id": PATIENT_B}),
    ],
)
def test_cross_account_get_blocked_across_routers(path, params):
    """同一套 enforce_patient_scope 套用到的各 router：A 帶 B 的 id 一律 403。

    這把「逐 router 補上的隔離」鎖住——任何一個 router 漏接 me / enforce，
    對應的參數化案例就會掉到 200 而失敗。
    """
    r = client.get(path, params=params, headers=_AUTH_A)
    assert r.status_code == 403, f"{path} 應擋下跨帳號存取，得到 {r.status_code}: {r.text}"


def test_medication_changes_without_patient_id_does_not_leak_all():
    """medication_changes 與 records 同款：demo 不帶 patient_id → 回空，不回全表。"""
    r = client.get("/medication-changes/")
    assert r.status_code == 200, r.text
    assert r.json()["changes"] == []


def test_records_without_patient_id_does_not_leak_all():
    """舊 P0：GET /records/ 不帶 patient_id 會回所有病患的病歷。修復後：
    - demo 不帶 patient_id → 回空，不洩漏全表。
    - A 登入 → 只回自己那位的病歷，看不到 B 的。
    """
    sb = db_mod.get_supabase()
    # medical_records.patient_id 有 FK 指向 patients，先補兩位病患列。
    sb.table("patients").insert({"id": PATIENT_A, "name": "A", "age": 0}).execute()
    sb.table("patients").insert({"id": PATIENT_B, "name": "B", "age": 0}).execute()
    sb.table("medical_records").insert(
        {"patient_id": PATIENT_A, "diagnosis": "A 的診斷"}
    ).execute()
    sb.table("medical_records").insert(
        {"patient_id": PATIENT_B, "diagnosis": "B 的診斷"}
    ).execute()

    # demo 無 token、無 patient_id → 不得回全表
    r_demo = client.get("/records/")
    assert r_demo.status_code == 200, r_demo.text
    assert r_demo.json()["records"] == []

    # A 登入 → 只看得到 A 的病歷
    r_a = client.get("/records/", headers=_AUTH_A)
    assert r_a.status_code == 200, r_a.text
    diagnoses = [rec.get("diagnosis") for rec in r_a.json()["records"]]
    assert "A 的診斷" in diagnoses
    assert "B 的診斷" not in diagnoses


def test_cannot_read_or_delete_other_account_record_by_id():
    """單筆病歷（by record_id）也要擋跨帳號：A 不可用 B 的 record_id 讀/刪（IDOR）。"""
    sb = db_mod.get_supabase()
    sb.table("patients").insert({"id": PATIENT_A, "name": "A", "age": 0}).execute()
    sb.table("patients").insert({"id": PATIENT_B, "name": "B", "age": 0}).execute()
    rec_b = sb.table("medical_records").insert(
        {"patient_id": PATIENT_B, "diagnosis": "B 的病歷"}
    ).execute().data[0]

    r_get = client.get(f"/records/{rec_b['id']}", headers=_AUTH_A)
    assert r_get.status_code == 403, r_get.text

    r_del = client.delete(f"/records/{rec_b['id']}", headers=_AUTH_A)
    assert r_del.status_code == 403, r_del.text

    # B 的病歷仍在（沒被 A 刪掉）
    still = sb.table("medical_records").select("id").eq("id", rec_b["id"]).execute().data
    assert still, "B 的病歷不應被 A 刪除"
