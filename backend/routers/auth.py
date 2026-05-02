import os
from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_supabase
from backend.dependencies import get_current_user
from backend.models import LoginRequest, RegisterRequest, TokenResponse, UserCreate
from backend.services.auth_service import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter()

VALID_ROLES = {"doctor", "patient"}


def _public_user(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "nickname": row.get("nickname"),
        "role": row.get("role"),
        "avatar_color": row.get("avatar_color"),
        "linked_doctor_id": row.get("linked_doctor_id"),
        "linked_patient_id": row.get("linked_patient_id"),
        "is_active": row.get("is_active", 1),
        "created_at": row.get("created_at"),
    }


def _allow_doctor_self_register() -> bool:
    return os.getenv("ALLOW_DOCTOR_SELF_REGISTER", "true").lower() in ("1", "true", "yes")


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="role 必須是 doctor 或 patient")
    if body.role == "doctor" and not _allow_doctor_self_register():
        raise HTTPException(status_code=403, detail="醫師註冊已關閉，請聯絡管理者")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密碼至少 6 碼")

    sb = get_supabase()
    existing = sb.table("users").select("*").eq("username", body.username).execute().data
    if existing:
        raise HTTPException(status_code=409, detail="帳號已被使用")

    data = {
        "username": body.username,
        "password_hash": hash_password(body.password),
        "nickname": body.nickname,
        "role": body.role,
        "avatar_color": body.avatar_color,
        "linked_doctor_id": body.linked_doctor_id,
        "linked_patient_id": body.linked_patient_id,
        "is_active": 1,
    }
    data = {k: v for k, v in data.items() if v is not None}
    result = sb.table("users").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="註冊失敗")
    user = result.data[0]
    token = create_access_token(user["id"], user["role"], user["username"])
    return TokenResponse(access_token=token, user=_public_user(user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    sb = get_supabase()
    rows = sb.table("users").select("*").eq("username", body.username).execute().data
    if not rows:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    user = rows[0]
    if not verify_password(body.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    if user.get("is_active") == 0:
        raise HTTPException(status_code=403, detail="帳號已停用")
    token = create_access_token(user["id"], user["role"], user["username"])
    return TokenResponse(access_token=token, user=_public_user(user))


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return _public_user(user)


# ─── Legacy / admin endpoints ─────────────────────────────────

@router.get("/user/{user_id}")
def get_user(user_id: str):
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return _public_user(result.data[0])


@router.get("/users")
def list_users():
    sb = get_supabase()
    result = sb.table("users").select("*").order("created_at", desc=True).execute()
    return {"users": [_public_user(u) for u in result.data]}


@router.post("/legacy-register")
def legacy_register(body: UserCreate):
    """No-password register (legacy patient flow). Will be removed."""
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="角色必須是 doctor 或 patient")
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = sb.table("users").insert(data).execute()
    return _public_user(result.data[0])
