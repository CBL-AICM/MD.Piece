import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_supabase
from backend.models import (
    PasswordChange,
    RecoveryQuestionRequest,
    RecoveryReset,
    RecoverySet,
    UserCreate,
    UserLogin,
    UserUpdate,
)
from backend.security import create_access_token, current_user
from backend.services import supabase_auth as sb_auth

logger = logging.getLogger(__name__)

router = APIRouter()

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# 網域標籤用不含「.」的字元類，避免 `[^@\s]+\.[^@\s]+` 的重疊歧義導致
# 多項式回溯（ReDoS）；此寫法為線性匹配。
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")

# 登入／重設防暴力破解：連續失敗達上限就鎖一段時間。
# serverless 不能用記憶體計數，故狀態存在 users 表（failed_login_count / locked_until）。
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15

# 太常見、極易被猜中的密碼黑名單（小集合即可擋掉大宗）。
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789",
    "1234567890", "qwerty123", "11111111", "00000000", "abc12345",
    "iloveyou", "admin123", "letmein1",
}


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


# 帳號不存在時也跑一次 scrypt，讓「帳號不存在」與「密碼錯」耗時相近，
# 不讓攻擊者用回應時間差來枚舉有效帳號（搭配統一錯誤訊息）。
_DUMMY_HASH = _hash_password("timing-equalizer-not-a-real-password")


def _validate_password(password: str, username: str | None = None) -> tuple[bool, str]:
    """共用密碼強度檢查；回 (是否通過, 錯誤訊息)。前端 app.js 有對應的同規則檢查。"""
    if len(password) < 8:
        return False, "密碼至少 8 個字元"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return False, "密碼需同時包含英文字母與數字"
    if username and password.lower() == username.lower():
        return False, "密碼不可與帳號相同"
    if password.lower() in _COMMON_PASSWORDS:
        return False, "這組密碼太常見，容易被猜中，請換一組"
    return True, ""


def _normalize_answer(answer: str) -> str:
    """安全問題答案正規化：去頭尾空白 + 轉小寫，避免大小寫／空白造成驗證失敗。"""
    return (answer or "").strip().lower()


def _public_user(row: dict) -> dict:
    """回給前端前，移除所有敏感／內部欄位。"""
    out = dict(row)
    for k in ("password_hash", "recovery_answer_hash", "recovery_question",
              "failed_login_count", "locked_until", "supabase_user_id"):
        out.pop(k, None)
    return out


def _maybe_provision(sb, user_id: str, password: str, existing_supabase_id) -> None:
    """flag on 且尚未綁定時，隱型建立 Supabase Auth user 並寫回 supabase_user_id。
    任何失敗都只記 log，絕不讓登入／註冊流程失敗（§10.4）。"""
    if not sb_auth.is_enabled() or existing_supabase_id:
        return
    try:
        uid = sb_auth.provision_user(user_id, password)
        if uid:
            sb.table("users").update({"supabase_user_id": uid}).eq("id", user_id).execute()
    except Exception:  # noqa: BLE001
        logger.exception("Supabase Auth provision 失敗（不影響登入）: user_id=%s", user_id)


def _maybe_sync_password(supabase_user_id, password: str) -> None:
    """改密碼／重設成功後，若已綁定 Supabase Auth 則同步密碼；失敗只記 log。"""
    if not sb_auth.is_enabled() or not supabase_user_id:
        return
    try:
        sb_auth.sync_password(supabase_user_id, password)
    except Exception:  # noqa: BLE001
        logger.exception("Supabase Auth 密碼同步失敗（本地已更新）: %s", supabase_user_id)


def _parse_locked_until(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _remaining_lockout(user_row: dict, now: datetime) -> int:
    """若帳號仍在鎖定中，回剩餘分鐘數（無條件進位、至少 1）；否則回 0。"""
    locked_until = _parse_locked_until(user_row.get("locked_until"))
    if locked_until and locked_until > now:
        return max(1, int((locked_until - now).total_seconds() // 60) + 1)
    return 0


def _register_failed_attempt(sb, user_row: dict, now: datetime) -> None:
    """累計一次失敗；達上限就上鎖並歸零計數。"""
    count = (user_row.get("failed_login_count") or 0) + 1
    update = {"failed_login_count": count}
    if count >= _MAX_FAILED_ATTEMPTS:
        update["failed_login_count"] = 0
        update["locked_until"] = (now + timedelta(minutes=_LOCKOUT_MINUTES)).isoformat()
    sb.table("users").update(update).eq("id", user_row["id"]).execute()


def _clear_failed_attempts(sb, user_id: str) -> None:
    sb.table("users").update({"failed_login_count": 0, "locked_until": None}).eq("id", user_id).execute()


@router.post("/register")
def register(body: UserCreate):
    if not _USERNAME_RE.match(body.username):
        raise HTTPException(status_code=400, detail="帳號格式不正確（3-32 字元，限英數字 _ . -）")
    ok, msg = _validate_password(body.password, body.username)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # email 為選填；空白視同未填，有填則做基本格式檢查後存起來。
    if body.email is not None:
        body.email = body.email.strip() or None
    if body.email and not _EMAIL_RE.match(body.email):
        raise HTTPException(status_code=400, detail="email 格式不正確")

    sb = get_supabase()
    existing = sb.table("users").select("id").eq("username", body.username).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="此帳號已被註冊")

    payload = body.model_dump(exclude_none=True)
    payload.pop("password", None)
    payload["role"] = "patient"
    payload["password_hash"] = _hash_password(body.password)

    # 可選的安全問題：兩者都給才算數，答案以 scrypt 雜湊存放。
    answer = payload.pop("recovery_answer", None)
    question = payload.get("recovery_question")
    if question and answer:
        payload["recovery_answer_hash"] = _hash_password(_normalize_answer(answer))
    else:
        payload.pop("recovery_question", None)

    result = sb.table("users").insert(payload).execute()
    user = _public_user(result.data[0])
    # Phase 2：隱型 provision Supabase Auth（flag off 時不執行）
    _maybe_provision(sb, user["id"], body.password, result.data[0].get("supabase_user_id"))
    # Phase 1a：附 access_token，前端存起來打後續 API
    return {**user, "access_token": create_access_token(user)}


@router.post("/login")
def login(body: UserLogin):
    sb = get_supabase()
    now = datetime.now(tz=timezone.utc)
    result = sb.table("users").select("*").eq("username", body.username).execute()
    if not result.data:
        # 帳號不存在也跑一次雜湊，避免時間差洩漏；錯誤訊息與密碼錯一致，防帳號列舉。
        _verify_password(body.password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    user_row = result.data[0]
    remaining = _remaining_lockout(user_row, now)
    if remaining:
        raise HTTPException(status_code=429, detail=f"登入嘗試過多，請於 {remaining} 分鐘後再試")

    if not _verify_password(body.password, user_row.get("password_hash", "")):
        _register_failed_attempt(sb, user_row, now)
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    _clear_failed_attempts(sb, user_row["id"])
    # Phase 2：第一次登入時隱型 provision（flag off 時不執行）
    _maybe_provision(sb, user_row["id"], body.password, user_row.get("supabase_user_id"))
    user = _public_user(user_row)
    return {**user, "access_token": create_access_token(user)}


@router.get("/user/{user_id}")
def get_user(user_id: str, me: dict = Depends(current_user)):
    uid = _enforce_self(user_id, me)
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    user = _public_user(result.data[0])
    # 本人查自己（已過 _enforce_self）：回傳是否設過安全問題與題目本身，
    # 供帳號設定頁顯示／預填；答案雜湊仍不外洩。
    user["has_recovery"] = bool(result.data[0].get("recovery_answer_hash"))
    user["recovery_question"] = result.data[0].get("recovery_question") or ""
    return user


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
    sb = get_supabase()
    result = sb.table("users").select("*").eq("id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    user = result.data[0]
    if not _verify_password(body.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="目前密碼錯誤")
    ok, msg = _validate_password(body.new_password, user.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    sb.table("users").update({"password_hash": _hash_password(body.new_password)}).eq("id", uid).execute()
    _maybe_sync_password(user.get("supabase_user_id"), body.new_password)
    return {"ok": True}


@router.post("/user/{user_id}/recovery")
def set_recovery(user_id: str, body: RecoverySet, me: dict = Depends(current_user)):
    """已登入時設定／更新安全問題（忘記密碼自助重設用）。"""
    uid = _enforce_self(user_id, me)
    question = (body.question or "").strip()
    answer = _normalize_answer(body.answer)
    if len(question) < 2:
        raise HTTPException(status_code=400, detail="請輸入安全問題")
    if not answer:
        raise HTTPException(status_code=400, detail="請輸入安全問題答案")
    sb = get_supabase()
    result = sb.table("users").update({
        "recovery_question": question,
        "recovery_answer_hash": _hash_password(answer),
    }).eq("id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到使用者")
    return {"ok": True}


@router.post("/recovery/question")
def recovery_question(body: RecoveryQuestionRequest):
    """忘記密碼第一步：用帳號查回安全問題（未設定則無法自助重設）。"""
    sb = get_supabase()
    result = sb.table("users").select("recovery_question, recovery_answer_hash").eq(
        "username", body.username).execute()
    if not result.data or not result.data[0].get("recovery_answer_hash"):
        raise HTTPException(status_code=404, detail="此帳號未設定安全問題，無法自助重設，請聯絡管理員")
    return {"question": result.data[0].get("recovery_question") or ""}


@router.post("/recovery/reset")
def recovery_reset(body: RecoveryReset):
    """忘記密碼第二步：答對安全問題即可重設密碼。沿用登入鎖定機制防猜答案。"""
    sb = get_supabase()
    now = datetime.now(tz=timezone.utc)
    result = sb.table("users").select("*").eq("username", body.username).execute()
    if not result.data:
        _verify_password(body.answer, _DUMMY_HASH)
        raise HTTPException(status_code=400, detail="帳號或安全問題答案錯誤")

    user_row = result.data[0]
    if not user_row.get("recovery_answer_hash"):
        raise HTTPException(status_code=400, detail="此帳號未設定安全問題，無法自助重設，請聯絡管理員")

    remaining = _remaining_lockout(user_row, now)
    if remaining:
        raise HTTPException(status_code=429, detail=f"嘗試過多，請於 {remaining} 分鐘後再試")

    if not _verify_password(_normalize_answer(body.answer), user_row["recovery_answer_hash"]):
        _register_failed_attempt(sb, user_row, now)
        raise HTTPException(status_code=400, detail="帳號或安全問題答案錯誤")

    ok, msg = _validate_password(body.new_password, user_row.get("username"))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    sb.table("users").update({
        "password_hash": _hash_password(body.new_password),
        "failed_login_count": 0,
        "locked_until": None,
    }).eq("id", user_row["id"]).execute()
    _maybe_sync_password(user_row.get("supabase_user_id"), body.new_password)
    return {"ok": True}
