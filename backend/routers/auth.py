import hashlib
import os
import re

from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_supabase
from backend.models import PasswordChange, UserCreate, UserLogin, UserUpdate
from backend.security import create_access_token, current_user

router = APIRouter()

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _enforce_self(user_id: str, me: dict) -> str:
    """user_id path 必須等於 token 的 sub。"""
    if not isinstance(user_id, str) or not _ID_RE.fullmatch(user_id):
        raise HTTPException(status_code=400, detail="user_id 格式不合法")
    if me.get("id") != user_id:
        raise HTTPException(status_code=403, detail="不可存取他人帳號")
    return user_id


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
    payload["role"] = "patient"
    payload["password_hash"] = _hash_password(body.password)

    result = sb.table("users").insert(payload).execute()
    user = _public_user(result.data[0])
    # Phase 1a：附 access_token，前端存起來打後續 API
    return {**user, "access_token": create_access_token(user)}


@router.post("/login")
def login(body: UserLogin):
    sb = get_supabase()
    result = sb.table("users").select("*").eq("username", body.username).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="此帳號尚未註冊")
    user_row = result.data[0]
    if not _verify_password(body.password, user_row.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="密碼錯誤")
    user = _public_user(user_row)
    return {**user, "access_token": create_access_token(user)}


@router.get("/user/{user_id}")
def get_user(user_id: str, me: dict = Depends(current_user)):
    uid = _enforce_self(user_id, me)
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return _public_user(result.data[0])


@router.patch("/user/{user_id}")
def update_user(user_id: str, body: UserUpdate, me: dict = Depends(current_user)):
    uid = _enforce_self(user_id, me)
    sb = get_supabase()
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="沒有要更新的欄位")
    result = sb.table("users").update(payload).eq("id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return _public_user(result.data[0])


@router.post("/user/{user_id}/password")
def change_password(user_id: str, body: PasswordChange, me: dict = Depends(current_user)):
    uid = _enforce_self(user_id, me)
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密碼至少 6 個字元")
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    user = result.data[0]
    if not _verify_password(body.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="目前密碼錯誤")
    sb.table("users").update({"password_hash": _hash_password(body.new_password)}).eq("id", uid).execute()
    return {"ok": True}
