"""Phase 2.1–2.2 隱型 provision 整合測試（遷移計畫 §10.5）。

驗證「接入 auth.py 的邏輯」，Supabase Auth 本身用 mock 取代（不連網）：
- flag off：login/register 完全不呼叫 provision（零行為變更）
- flag on：首次登入/註冊 provision 一次、寫回 supabase_user_id、二次不再建（冪等）
- provision 失敗不擋登入/註冊（既有使用者不能因為遷移而進不來）
- 改密碼/重設成功後，若已綁定則同步密碼
- 回應不外洩 supabase_user_id
"""

import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import supabase_auth

client = TestClient(app)

_GOOD_PASSWORD = "Secret123"
_USERNAME = "provuser.test"


class _Spy:
    """記錄 provision_user / sync_password 的呼叫，供 monkeypatch 注入。"""
    def __init__(self, provision_result="sb-uid-123", provision_raises=False):
        self.provision_calls = []
        self.sync_calls = []
        self._result = provision_result
        self._raises = provision_raises

    def provision_user(self, user_id, password):
        self.provision_calls.append((user_id, password))
        if self._raises:
            raise RuntimeError("supabase down")
        return self._result

    def sync_password(self, supabase_user_id, password):
        self.sync_calls.append((supabase_user_id, password))


def _patch(monkeypatch, enabled, spy):
    monkeypatch.setattr(supabase_auth, "is_enabled", lambda: enabled)
    monkeypatch.setattr(supabase_auth, "provision_user", spy.provision_user)
    monkeypatch.setattr(supabase_auth, "sync_password", spy.sync_password)


def _register(**extra):
    body = {"username": _USERNAME, "password": _GOOD_PASSWORD, "nickname": "Prov"}
    body.update(extra)
    return client.post("/auth/register", json=body)


def test_flag_off_never_provisions(monkeypatch):
    """為什麼重要：flag off 時必須對既有行為零影響。"""
    spy = _Spy()
    _patch(monkeypatch, False, spy)
    assert _register().status_code == 200
    assert client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD}).status_code == 200
    assert spy.provision_calls == []


def test_flag_on_provisions_once_and_is_idempotent(monkeypatch):
    spy = _Spy(provision_result="sb-uid-abc")
    _patch(monkeypatch, True, spy)
    # 註冊即 provision 一次，且用本次明文密碼 + 正確 user id
    reg = _register()
    assert reg.status_code == 200
    uid = reg.json()["id"]
    assert spy.provision_calls == [(uid, _GOOD_PASSWORD)]
    # 再次登入：已綁定（supabase_user_id 已寫回）→ 不再 provision（冪等）
    assert client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD}).status_code == 200
    assert len(spy.provision_calls) == 1


def test_provision_failure_does_not_block(monkeypatch):
    """provision 拋例外時，註冊與登入都仍要成功。"""
    spy = _Spy(provision_raises=True)
    _patch(monkeypatch, True, spy)
    assert _register().status_code == 200          # 失敗被吞、不擋註冊
    assert len(spy.provision_calls) == 1
    # 未寫回 supabase_user_id → 下次登入會再試 provision，且仍成功
    assert client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD}).status_code == 200
    assert len(spy.provision_calls) == 2


def test_change_password_syncs_when_bound(monkeypatch):
    spy = _Spy(provision_result="sb-uid-xyz")
    _patch(monkeypatch, True, spy)
    reg = _register()
    uid = reg.json()["id"]
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    res = client.post(f"/auth/user/{uid}/password", headers=h,
                      json={"current_password": _GOOD_PASSWORD, "new_password": "Newpass123"})
    assert res.status_code == 200
    assert spy.sync_calls == [("sb-uid-xyz", "Newpass123")]


def test_response_never_leaks_supabase_user_id(monkeypatch):
    spy = _Spy(provision_result="sb-uid-secret")
    _patch(monkeypatch, True, spy)
    reg = _register()
    assert "supabase_user_id" not in reg.json()
    login = client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD})
    assert "supabase_user_id" not in login.json()
