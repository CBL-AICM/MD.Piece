import hashlib
import os
import re

from fastapi import APIRouter, HTTPException

from backend.db import get_supabase
from backend.models import PasswordChange, UserCreate, UserLogin, UserUpdate

router = APIRouter()

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(digest_hex) // 2,
    )
    return digest.hex() == digest_hex


def _public_user(row: dict) -> dict:
    out = dict(row)
    out.pop("password_hash", None)
    return out


@router.post("/register")
def register(body: UserCreate):
    if body.role not in ("doctor", "patient"):
        raise HTTPException(status_code=400, detail="角色必須是 doctor 或 patient")
    if not _USERNAME_RE.match(body.username):
        raise HTTPException(status_code=400, detail="帳號格式不正確（3-32 字元，限英數字 _ . -）")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密碼至少 6 個字元")

    sb = get_supabase()
    existing = sb.table("users").select("id").eq("username", body.username).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="此帳號已被註冊")

    payload = body.model_dump(exclude_none=True)
    payload.pop("password", None)
    payload["password_hash"] = _hash_password(body.password)

    result = sb.table("users").insert(payload).execute()
    return _public_user(result.data[0])


@router.post("/login")
def login(body: UserLogin):
    sb = get_supabase()
    result = sb.table("users").select("*").eq("username", body.username).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    user = result.data[0]
    if not _verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    return _public_user(user)


@router.get("/user/{user_id}")
def get_user(user_id: str):
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return _public_user(result.data[0])


@router.patch("/user/{user_id}")
def update_user(user_id: str, body: UserUpdate):
    sb = get_supabase()
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="沒有要更新的欄位")
    result = sb.table("users").update(payload).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return _public_user(result.data[0])


@router.post("/user/{user_id}/password")
def change_password(user_id: str, body: PasswordChange):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密碼至少 6 個字元")
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    user = result.data[0]
    if not _verify_password(body.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="目前密碼錯誤")
    sb.table("users").update({"password_hash": _hash_password(body.new_password)}).eq("id", user_id).execute()
    return {"ok": True}


@router.get("/users")
def list_users():
    sb = get_supabase()
    result = sb.table("users").select("*").order("created_at", desc=True).execute()
    return {"users": [_public_user(u) for u in result.data]}
