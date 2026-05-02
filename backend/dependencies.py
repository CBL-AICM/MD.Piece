"""FastAPI dependencies for auth gating."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.db import get_supabase
from backend.services.auth_service import decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少認證 token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(creds.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 無效或已過期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="token payload 缺少 sub")

    sb = get_supabase()
    rows = sb.table("users").select("*").eq("id", user_id).execute().data
    if not rows:
        raise HTTPException(status_code=401, detail="使用者不存在")
    user = rows[0]
    if user.get("is_active") == 0:
        raise HTTPException(status_code=403, detail="帳號已停用")
    return user


def require_doctor(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="此操作限醫師身份")
    return user


def require_patient(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "patient":
        raise HTTPException(status_code=403, detail="此操作限病患身份")
    return user
