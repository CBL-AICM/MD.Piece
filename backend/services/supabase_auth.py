"""
Supabase Auth 隱型 provisioning — Phase 2.1–2.2（遷移計畫 §10）

把現有自管 scrypt 帳號**隱型**對應到 Supabase Auth user，整個藏在
feature flag `AUTH_SUPABASE_ENABLED` 後、**預設 off**。flag off 時
本模組的接入點完全不執行（is_enabled() 回 False），對前端零行為變更。

設計原則：
- import 安全：模組載入不連網、不建 client（admin client 延遲初始化）。
- provisioning 失敗**不可**讓既有使用者登入失敗 → 呼叫端 catch 後只記 log。
- 需要 admin 權限，用獨立的 SUPABASE_SERVICE_ROLE_KEY（不重用 SUPABASE_KEY；
  把 SUPABASE_KEY 切成 service_role 是 PR 2 的事）。

⚠️ 對真實 Supabase Auth 的網路行為尚未在 CI 驗證，需在 Supabase
   preview branch 設好 service_role key 後實測（見 §10.6）。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# placeholder email 網域：Supabase Auth 需要 email，但本專案用 username 登入，
# 故用 user.id 組一個不可寄達的內部 email；不做 email 驗證（§8 決策）。
_EMAIL_DOMAIN = "mdpiece.internal"

_admin = None  # 延遲初始化的 admin client


def is_enabled() -> bool:
    """總開關。預設 off：未設或設為 0/false/no 皆視為關閉。"""
    return os.getenv("AUTH_SUPABASE_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")


def _placeholder_email(user_id: str) -> str:
    return f"{user_id}@{_EMAIL_DOMAIN}"


def _admin_client():
    """延遲建立 service_role admin client；缺 key 則 fail-loud。"""
    global _admin
    if _admin is not None:
        return _admin
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError(
            "AUTH_SUPABASE_ENABLED=on 但缺 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY"
        )
    from supabase import create_client  # 延遲 import，避免影響無 supabase 套件的環境
    _admin = create_client(url, key)
    return _admin


def provision_user(user_id: str, password: str) -> str | None:
    """
    確保 Supabase Auth 內有對應這個 user 的帳號，回傳其 supabase uid。
    冪等：email 已存在時改為更新密碼、回既有 uid。
    任何失敗都 raise，由呼叫端決定如何處理（登入流程會 catch 成 log）。
    """
    client = _admin_client()
    email = _placeholder_email(user_id)
    try:
        res = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        uid = getattr(getattr(res, "user", None), "id", None)
        if not uid:
            raise RuntimeError("create_user 未回傳 user.id")
        return uid
    except Exception as e:  # noqa: BLE001 — 視為「可能已存在」再走查找更新路徑
        existing = _find_user_by_email(client, email)
        if existing is None:
            raise
        # 已存在 → 同步本次密碼（雙寫期保持兩邊密碼一致）
        client.auth.admin.update_user_by_id(existing, {"password": password})
        logger.info("provision_user: %s 已存在於 Supabase Auth，已更新密碼", email)
        return existing


def sync_password(supabase_user_id: str, password: str) -> None:
    """改密碼 / 重設密碼成功後，把新密碼同步到 Supabase Auth（§8 決策）。"""
    client = _admin_client()
    client.auth.admin.update_user_by_id(supabase_user_id, {"password": password})


def _find_user_by_email(client, email: str) -> str | None:
    """用 admin list_users 找 email 對應的 uid；找不到回 None。"""
    try:
        users = client.auth.admin.list_users()
    except Exception:  # noqa: BLE001
        return None
    # supabase-py 版本差異：可能回 list 或帶 .users 的物件
    items = getattr(users, "users", users) or []
    for u in items:
        if getattr(u, "email", None) == email:
            return getattr(u, "id", None)
    return None
