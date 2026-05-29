"""auth router 整合測試 — 用本地 SQLite fallback + TestClient。

測試重點（驗證「為什麼」而非只是「有跑」）：
- 註冊：弱密碼（太短／缺數字／與帳號相同／太常見）必須被擋；帳號格式錯被擋
- 回應絕不外洩 password_hash / recovery_answer_hash / locked_until 等敏感欄位
- 帳號列舉防護：「帳號不存在」與「密碼錯」必須回完全相同的 401 訊息
- 暴力破解防護：連續失敗達上限後鎖定（429）；成功登入會清掉失敗計數
- 改密碼：舊密碼錯 401、新密碼太弱 400
- 忘記密碼（安全問題）：設定→查問題→答對可重設並用新密碼登入；答錯被擋且套用鎖定
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
os.environ["JWT_SECRET"] = "test-secret-at-least-16-chars-long-xxxx"

_TMP_DB = tempfile.NamedTemporaryFile(prefix="authtest_", suffix=".db", delete=False)
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

client = TestClient(app)

# 後端帳號驗證用 _USERNAME_RE 不允許全數字以外的格式，但允許英數混合。
_GOOD_PASSWORD = "Secret123"
_USERNAME = "alice.test"


@pytest.fixture(autouse=True)
def _reset_db():
    import sqlite3

    db_mod.DB_PATH = _TMP_DB.name
    db_mod.SUPABASE_URL = ""
    db_mod.SUPABASE_KEY = ""
    db_mod._client = None  # type: ignore[attr-defined]
    db_mod._init_db()

    conn = sqlite3.connect(_TMP_DB.name)
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    yield


def _register(username=_USERNAME, password=_GOOD_PASSWORD, **extra):
    body = {"username": username, "password": password, "nickname": "Alice"}
    body.update(extra)
    return client.post("/auth/register", json=body)


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ─── 註冊：密碼強度 ─────────────────────────────────────────

def test_register_success_returns_token_and_hides_secrets():
    res = _register()
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["access_token"]
    assert data["username"] == _USERNAME
    assert data["role"] == "patient"  # 後端強制 patient
    # 為什麼重要：敏感欄位絕不能回給前端
    for leaked in ("password_hash", "recovery_answer_hash", "failed_login_count", "locked_until"):
        assert leaked not in data


@pytest.mark.parametrize("pw,reason", [
    ("Short1", "少於 8 字元應被擋"),
    ("alllettersonly", "缺數字應被擋"),
    ("12345678", "缺英文字母 + 太常見應被擋"),
    ("password1", "常見密碼應被擋"),
])
def test_register_rejects_weak_passwords(pw, reason):
    res = _register(password=pw)
    assert res.status_code == 400, f"{reason}: {res.text}"


def test_register_rejects_password_equal_to_username():
    # 為什麼重要：密碼=帳號等於沒設密碼
    res = _register(username="bob12345", password="bob12345")
    assert res.status_code == 400


def test_register_rejects_bad_username_format():
    res = _register(username="a b!")  # 含空白與驚嘆號
    assert res.status_code == 400


def test_register_duplicate_username_conflicts():
    assert _register().status_code == 200
    res = _register(password="Another123")
    assert res.status_code == 409


# ─── 登入：帳號列舉 + 鎖定 ──────────────────────────────────

def test_login_success():
    _register()
    res = client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD})
    assert res.status_code == 200, res.text
    assert res.json()["access_token"]


def test_login_wrong_password_and_unknown_user_are_indistinguishable():
    """帳號列舉防護：兩種失敗必須回完全相同的 status 與 detail。"""
    _register()
    wrong = client.post("/auth/login", json={"username": _USERNAME, "password": "WrongPass9"})
    unknown = client.post("/auth/login", json={"username": "nobody_here", "password": "WrongPass9"})
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]
    assert wrong.json()["detail"] == "帳號或密碼錯誤"


def test_login_locks_out_after_repeated_failures():
    """連續 5 次密碼錯後上鎖：即使密碼正確也回 429。"""
    _register()
    for _ in range(5):
        r = client.post("/auth/login", json={"username": _USERNAME, "password": "WrongPass9"})
        assert r.status_code == 401
    # 第 6 次即使密碼正確也應被鎖定
    locked = client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD})
    assert locked.status_code == 429


def test_successful_login_clears_failed_counter():
    """為什麼重要：偶爾打錯不該累積到永久接近鎖定；成功登入應歸零計數。"""
    _register()
    for _ in range(4):
        client.post("/auth/login", json={"username": _USERNAME, "password": "WrongPass9"})
    # 第 5 次用正確密碼成功（counter 歸零）
    assert client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD}).status_code == 200
    # 計數已歸零，再打錯 4 次仍不該被鎖
    for _ in range(4):
        r = client.post("/auth/login", json={"username": _USERNAME, "password": "WrongPass9"})
        assert r.status_code == 401  # 還沒到上限


# ─── 改密碼 ─────────────────────────────────────────────────

def test_change_password_flow():
    token = _register().json()["access_token"]
    uid = client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD}).json()["id"]
    h = _auth_headers(token)

    # 舊密碼錯 → 401
    assert client.post(f"/auth/user/{uid}/password", headers=h,
                       json={"current_password": "nope9999", "new_password": "Brandnew1"}).status_code == 401
    # 新密碼太弱 → 400
    assert client.post(f"/auth/user/{uid}/password", headers=h,
                       json={"current_password": _GOOD_PASSWORD, "new_password": "weak"}).status_code == 400
    # 正常改 → 200，且可用新密碼登入
    assert client.post(f"/auth/user/{uid}/password", headers=h,
                       json={"current_password": _GOOD_PASSWORD, "new_password": "Brandnew1"}).status_code == 200
    assert client.post("/auth/login", json={"username": _USERNAME, "password": "Brandnew1"}).status_code == 200


def test_change_password_rejects_other_user():
    """越權防護：不能改別人的密碼。"""
    token = _register().json()["access_token"]
    h = _auth_headers(token)
    assert client.post("/auth/user/someone-else/password", headers=h,
                       json={"current_password": _GOOD_PASSWORD, "new_password": "Brandnew1"}).status_code == 403


# ─── 忘記密碼（安全問題）────────────────────────────────────

def test_recovery_full_flow():
    """設定安全問題 → 查問題 → 答對重設 → 用新密碼登入。"""
    reg = _register(recovery_question="第一隻寵物的名字？", recovery_answer="小白")
    token = reg.json()["access_token"]
    uid = reg.json()["id"]

    # 查問題
    q = client.post("/auth/recovery/question", json={"username": _USERNAME})
    assert q.status_code == 200, q.text
    assert q.json()["question"] == "第一隻寵物的名字？"

    # 答錯 → 400
    assert client.post("/auth/recovery/reset", json={
        "username": _USERNAME, "answer": "錯的", "new_password": "Resetpw123"}).status_code == 400

    # 答對（大小寫／空白不敏感）→ 200，並可用新密碼登入
    ok = client.post("/auth/recovery/reset", json={
        "username": _USERNAME, "answer": "  小白 ", "new_password": "Resetpw123"})
    assert ok.status_code == 200, ok.text
    assert client.post("/auth/login", json={"username": _USERNAME, "password": "Resetpw123"}).status_code == 200


def test_recovery_question_404_when_not_set():
    """未設定安全問題者不能自助重設。"""
    _register()  # 沒帶 recovery
    assert client.post("/auth/recovery/question", json={"username": _USERNAME}).status_code == 404
    assert client.post("/auth/recovery/reset", json={
        "username": _USERNAME, "answer": "x", "new_password": "Resetpw123"}).status_code == 400


def test_set_recovery_via_account_and_get_user_exposure():
    """已登入者可設定安全問題；get_user 回 has_recovery + 題目，但不外洩答案雜湊。"""
    reg = _register()
    token = reg.json()["access_token"]
    uid = reg.json()["id"]
    h = _auth_headers(token)

    # 設定前：未設定
    before = client.get(f"/auth/user/{uid}", headers=h).json()
    assert before["has_recovery"] is False
    assert "recovery_answer_hash" not in before

    # 設定安全問題
    assert client.post(f"/auth/user/{uid}/recovery", headers=h,
                       json={"question": "母親的姓？", "answer": "陳"}).status_code == 200

    after = client.get(f"/auth/user/{uid}", headers=h).json()
    assert after["has_recovery"] is True
    assert after["recovery_question"] == "母親的姓？"
    assert "recovery_answer_hash" not in after  # 答案雜湊絕不外洩

    # 設定後即可走忘記密碼流程
    assert client.post("/auth/recovery/reset", json={
        "username": _USERNAME, "answer": "陳", "new_password": "Resetpw123"}).status_code == 200


def test_recovery_reset_enforces_password_strength():
    _register(recovery_question="顏色？", recovery_answer="藍")
    res = client.post("/auth/recovery/reset", json={
        "username": _USERNAME, "answer": "藍", "new_password": "weak"})
    assert res.status_code == 400
