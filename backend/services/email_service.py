"""寄信服務 — 透過 Resend REST API（用 httpx，不另加 SDK 依賴）。

設計：
- RESEND_API_KEY 未設定時 is_configured() 為 False、send_email() 直接 raise，
  絕不靜默假裝成功（鐵則 12）。
- 寄件人預設用 Resend 測試寄件人 onboarding@resend.dev：不必先驗證網域即可寄，
  但 Resend 測試模式下只會送到「你 Resend 帳號自己的 email」。要寄給任意收件人，
  需在 Resend 驗證自有網域，並把 EMAIL_FROM 設成該網域的寄件地址。
"""
import logging
import os

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:  # httpx 經 supabase 依賴鏈通常已可用；保險起見容錯
    httpx = None

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "MD.Piece <onboarding@resend.dev>")
_RESEND_ENDPOINT = "https://api.resend.com/emails"


def is_configured() -> bool:
    """是否具備寄信能力（有 key 且 httpx 可用）。"""
    return bool(RESEND_API_KEY) and httpx is not None


def send_email(to: str, subject: str, html: str, attachments=None) -> dict:
    """寄一封信。

    attachments: list of {"filename": str, "content": <base64 字串>}（Resend 格式）。
    成功回傳 Resend 的 JSON（含 id）；任何失敗都 raise RuntimeError。
    """
    if httpx is None:
        raise RuntimeError("httpx 不可用，無法寄信")
    if not RESEND_API_KEY:
        raise RuntimeError("未設定 RESEND_API_KEY，無法寄信")

    payload = {"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html}
    if attachments:
        payload["attachments"] = attachments

    resp = httpx.post(
        _RESEND_ENDPOINT,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Resend 寄信失敗（HTTP {resp.status_code}）：{resp.text[:300]}")
    return resp.json()
