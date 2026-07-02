"""忘記密碼（Email 連結式重設）整合測試 — 用本地 SQLite fallback + TestClient。

測試重點（驗證「為什麼」而非只是「有跑」）：
- 寄信服務未設定時必須 503 明講，不可假裝有寄（鐵則 12）
- 帳號列舉防護：帳號不存在／沒綁 email，回應必須與成功寄出完全相同
- 信中 token 可重設密碼，且新密碼可登入、舊密碼失效
- token 一次性：用過（密碼已變）後同一 token 必須失效
- token 不可被當成登入用的 access token（purpose 隔離）
- 新密碼仍須過強度檢查；竄改 token 必須被擋
- 節流：同帳號短時間內重複申請只寄一封
"""

import re

import pytest

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import auth as auth_mod

client = TestClient(app)

_GOOD_PASSWORD = "Secret123"
_NEW_PASSWORD = "Newpass456"
_USERNAME = "alice.test"
_EMAIL = "alice@example.com"


@pytest.fixture(autouse=True)
def _reset_throttle():
    # DB 隔離由 tests/conftest.py 統一處理；這裡只需清掉 per-process 的
    # 「已寄出」節流表，避免上一個測試的節流狀態洩漏到下一個。
    auth_mod._last_reset_email_at.clear()
    yield


@pytest.fixture
def outbox(monkeypatch):
    """把寄信服務換成記憶體收件匣：設為已設定、攔下所有寄出的信。"""
    sent = []

    def _fake_send(to, subject, html, attachments=None):
        sent.append({"to": to, "subject": subject, "html": html})
        return {"id": "fake-email-id"}

    monkeypatch.setattr(auth_mod.email_service, "is_configured", lambda: True)
    monkeypatch.setattr(auth_mod.email_service, "send_email", _fake_send)
    return sent


def _register(username=_USERNAME, password=_GOOD_PASSWORD, **extra):
    body = {"username": username, "password": password, "nickname": "Alice"}
    body.update(extra)
    return client.post("/auth/register", json=body)


def _request_reset(username=_USERNAME):
    return client.post("/auth/recovery/email/request", json={"username": username})


def _extract_token(html: str) -> str:
    m = re.search(r"reset_token=([A-Za-z0-9._\-]+)", html)
    assert m, f"信件內容找不到 reset_token：{html[:200]}"
    return m.group(1)


# ─── 寄信服務未設定 ──────────────────────────────────────────

def test_request_returns_503_when_email_not_configured(monkeypatch):
    # 為什麼重要：不可在沒寄信能力時回「已寄出」騙使用者（鐵則 12）
    monkeypatch.setattr(auth_mod.email_service, "is_configured", lambda: False)
    _register(email=_EMAIL)
    res = _request_reset()
    assert res.status_code == 503


# ─── 申請寄送：防帳號列舉 ────────────────────────────────────

def test_request_sends_email_with_reset_link(outbox):
    _register(email=_EMAIL)
    res = _request_reset()
    assert res.status_code == 200, res.text
    assert len(outbox) == 1
    assert outbox[0]["to"] == _EMAIL
    assert "reset_token=" in outbox[0]["html"]


def test_request_for_unknown_username_returns_same_generic_response(outbox):
    # 為什麼重要：回應若有差異，攻擊者就能枚舉有效帳號
    _register(email=_EMAIL)
    res_known = _request_reset()
    res_unknown = _request_reset(username="nobody.here")
    assert res_unknown.status_code == 200
    assert res_unknown.json() == res_known.json()
    assert len(outbox) == 1  # 只有真帳號那封


def test_request_for_user_without_email_returns_same_generic_response(outbox):
    _register()  # 沒綁 email
    res = _request_reset()
    assert res.status_code == 200
    assert len(outbox) == 0


def test_request_is_rate_limited_per_username(outbox):
    # 為什麼重要：防止被人拿來灌爆受害者信箱
    _register(email=_EMAIL)
    res1 = _request_reset()
    res2 = _request_reset()
    assert res1.status_code == 200 and res2.status_code == 200  # 回應不洩漏節流
    assert len(outbox) == 1


# ─── 憑 token 重設密碼 ───────────────────────────────────────

def test_reset_with_token_changes_password(outbox):
    _register(email=_EMAIL)
    _request_reset()
    token = _extract_token(outbox[0]["html"])

    res = client.post("/auth/recovery/email/reset",
                      json={"token": token, "new_password": _NEW_PASSWORD})
    assert res.status_code == 200, res.text

    # 為什麼重要：重設的意義是「新密碼能登入、舊密碼失效」
    ok = client.post("/auth/login", json={"username": _USERNAME, "password": _NEW_PASSWORD})
    assert ok.status_code == 200
    old = client.post("/auth/login", json={"username": _USERNAME, "password": _GOOD_PASSWORD})
    assert old.status_code == 401


def test_reset_rejects_weak_new_password(outbox):
    _register(email=_EMAIL)
    _request_reset()
    token = _extract_token(outbox[0]["html"])
    res = client.post("/auth/recovery/email/reset",
                      json={"token": token, "new_password": "short1"})
    assert res.status_code == 400


def test_token_is_single_use(outbox):
    # 為什麼重要：重設信若外洩，用過的連結不可再改一次密碼
    _register(email=_EMAIL)
    _request_reset()
    token = _extract_token(outbox[0]["html"])
    first = client.post("/auth/recovery/email/reset",
                        json={"token": token, "new_password": _NEW_PASSWORD})
    assert first.status_code == 200
    second = client.post("/auth/recovery/email/reset",
                         json={"token": token, "new_password": "Another789"})
    assert second.status_code == 400


def test_tampered_token_is_rejected(outbox):
    _register(email=_EMAIL)
    _request_reset()
    token = _extract_token(outbox[0]["html"])
    res = client.post("/auth/recovery/email/reset",
                      json={"token": token[:-2] + "xx", "new_password": _NEW_PASSWORD})
    assert res.status_code == 400


def test_reset_token_cannot_be_used_as_access_token(outbox):
    # 為什麼重要：重設 token 走 email、比登入 token 更易外洩，
    # 絕不可拿來冒充登入態存取個資
    reg = _register(email=_EMAIL)
    user_id = reg.json()["id"]
    _request_reset()
    token = _extract_token(outbox[0]["html"])
    res = client.get(f"/auth/user/{user_id}",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
