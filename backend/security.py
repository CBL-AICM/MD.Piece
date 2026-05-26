"""
JWT 認證 — Phase 1a 基礎建設（Issue #388）

設計目的：在改 Supabase Auth 之前，先把後端從「URL path 帶 user_id、零驗證」
升級成「Authorization: Bearer <jwt>、由 token 決定身份」，把 P0 越權漏洞堵住。

JWT 設計：
- HS256 + 7 天到期
- payload: {sub: user_id, username, role, exp, iat}
- secret 從環境變數 JWT_SECRET 讀；缺則 fail-loud（不用 dev 預設，避免 prod 誤上）

提供：
- create_access_token(user) — login / register 成功時呼叫
- current_user (Depends) — router 用，拿到 dict {id, username, role}
- current_user_optional — 過渡期用，沒帶 token 也不報錯（給尚未遷移的 router 用）
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_ALGO = "HS256"
_DEFAULT_TTL_DAYS = 7


def _secret() -> str:
    s = os.environ.get("JWT_SECRET", "").strip()
    if not s:
        # Fail loud — production 缺 secret 直接 500，比預設值悄悄上線安全
        raise RuntimeError(
            "JWT_SECRET 環境變數未設定。請在 Vercel / .env 設定一個 >=32 字元的隨機字串。"
        )
    if len(s) < 16:
        raise RuntimeError("JWT_SECRET 長度過短（< 16 字元）")
    return s


def create_access_token(user: dict, ttl_days: int = _DEFAULT_TTL_DAYS) -> str:
    """為登入成功的 user 產 JWT。user 必須有 id；username/role 缺則略過。"""
    if not isinstance(user, dict) or not user.get("id"):
        raise ValueError("create_access_token 需要 user dict 含 id 欄位")
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=ttl_days)).timestamp()),
    }
    if user.get("username"):
        payload["username"] = user["username"]
    if user.get("role"):
        payload["role"] = user["role"]
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登入已過期，請重新登入",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認證 token 無效",
            headers={"WWW-Authenticate": "Bearer"},
        )


_bearer_required = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer_required),
) -> dict:
    """強制驗證 token；router 用這個就能拿到登入態 user。"""
    payload = _decode(creds.credentials)
    return {
        "id": payload["sub"],
        "username": payload.get("username"),
        "role": payload.get("role"),
    }


def current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Optional[dict]:
    """過渡期用：沒帶 token 也不報錯，回 None。
    給尚未遷移的舊 router、能讀但要記名的 endpoint 用。"""
    if not creds:
        return None
    try:
        payload = _decode(creds.credentials)
    except HTTPException:
        return None
    return {
        "id": payload["sub"],
        "username": payload.get("username"),
        "role": payload.get("role"),
    }
