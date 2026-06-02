"""email_service（Resend 寄信）單元測試。

鎖住為什麼重要（規則 9）：
- 沒設 RESEND_API_KEY 時 is_configured() 為 False、send_email() 必須 raise，
  不能靜默假裝寄出（鐵則 12）。
- 有 key 時送出的 payload 結構正確（from/to/subject/attachments + Bearer 標頭）。
- Resend 回 4xx 時要 raise，呼叫端才能轉成清楚錯誤。
這裡用 mock httpx，不會真的對外寄信。
"""
import importlib
from unittest.mock import MagicMock

import pytest

import backend.services.email_service as es


def _reload():
    importlib.reload(es)
    return es


def test_not_configured_without_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    m = _reload()
    assert m.is_configured() is False


def test_send_raises_without_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    m = _reload()
    with pytest.raises(RuntimeError):
        m.send_email("a@b.com", "s", "<p>x</p>")


def test_send_builds_payload_and_returns_id(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    m = _reload()
    captured = {}

    class Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"id": "email_123"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return Resp()

    m.httpx = MagicMock()
    m.httpx.post = fake_post

    out = m.send_email(
        "u@e.com", "主旨", "<p>hi</p>",
        attachments=[{"filename": "r.pdf", "content": "QQ=="}],
    )
    assert out == {"id": "email_123"}
    assert captured["json"]["to"] == ["u@e.com"]
    assert captured["json"]["subject"] == "主旨"
    assert captured["json"]["attachments"][0]["filename"] == "r.pdf"
    assert captured["headers"]["Authorization"] == "Bearer re_test"


def test_send_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    m = _reload()

    class Resp:
        status_code = 422
        text = "bad request"

        def json(self):
            return {}

    m.httpx = MagicMock()
    m.httpx.post = lambda *a, **k: Resp()
    with pytest.raises(RuntimeError):
        m.send_email("u@e.com", "s", "<p>x</p>")
