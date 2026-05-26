"""
個人檔案 / 慢性病 / 緊急聯絡人 — per-user 持久化（Issue #131）

原本只存 localStorage，使用者反映「清快取 / 換瀏覽器就不見」。本 router
把資料同步到 Supabase patient_profiles 表，UPSERT 模式：一個 user_id
對應一筆 profile，全欄位可選（漸進式填寫）。

Phase 1a 起：強制帶 Authorization: Bearer <jwt>，且 path 上的 user_id
必須等於 token 的 sub —— 不能 PUT 別人的 profile（封 P0 越權漏洞，Issue #388）。
"""

import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.db import _SCHEMAS, get_supabase
from backend.models import PatientProfileUpsert
from backend.security import current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Anchored allowlist for user_id（與其他 router 一致）
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _safe_id(value: str, label: str = "user_id") -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"{label} 格式不合法")
    return value


def _validate_date(s):
    """空字串 / None 都當成「沒填」。"""
    if not s:
        return None
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="birthday 格式錯誤，需為 YYYY-MM-DD")
    return s


# SQLite fallback schema（Supabase 由 docs/migration_patient_profiles.sql 建立）
_SCHEMAS.setdefault(
    "patient_profiles",
    """
        CREATE TABLE IF NOT EXISTS patient_profiles (
            user_id TEXT PRIMARY KEY,
            gender TEXT,
            birthday TEXT,
            blood TEXT,
            height_cm REAL,
            weight_kg REAL,
            allergies TEXT,
            conditions TEXT,
            current_disease TEXT,
            meds TEXT,
            doctor_name TEXT,
            hospital TEXT,
            emergency_name TEXT,
            emergency_phone TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
)


def _enforce_self(user_id: str, me: dict) -> str:
    """確認 path 上的 user_id 就是 token 持有者。Phase 1a 不允許跨人讀寫。"""
    uid = _safe_id(user_id)
    if me.get("id") != uid:
        raise HTTPException(status_code=403, detail="不可存取他人個人檔案")
    return uid


@router.get("/{user_id}")
def get_profile(user_id: str, me: dict = Depends(current_user)):
    """取得個人檔案。沒有就回 404（前端會 fallback 到空表單）。"""
    uid = _enforce_self(user_id, me)
    sb = get_supabase()
    result = sb.table("patient_profiles").select("*").eq("user_id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="尚未建立個人檔案")
    return result.data[0]


@router.put("/{user_id}")
def upsert_profile(user_id: str, body: PatientProfileUpsert, me: dict = Depends(current_user)):
    """完整覆寫個人檔案（UPSERT）。沒有就建、有就改。"""
    uid = _enforce_self(user_id, me)
    payload = body.model_dump(exclude_unset=False)
    payload["birthday"] = _validate_date(payload.get("birthday"))
    payload["user_id"] = uid
    payload["updated_at"] = datetime.utcnow().isoformat()

    # supabase-py 在 Vercel runtime 上若丟非 HTTPException 例外，會被 Starlette
    # ServerErrorMiddleware 吞成 plain-text 500，前端就看不到 root cause、production
    # logs 也只有「Internal Server Error」。手動 catch + log + 回 JSON 502
    # 讓前端 toast 拿得到原因、後端 logs 有 stack trace（rear-stage-sync-failure）。
    try:
        sb = get_supabase()
        result = sb.table("patient_profiles").upsert(payload, on_conflict="user_id").execute()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("patient_profiles upsert failed for user_id=%s", uid)
        raise HTTPException(
            status_code=502,
            detail=f"後端儲存失敗：{type(exc).__name__}: {str(exc)[:200]}",
        )
    if not result.data:
        raise HTTPException(status_code=500, detail="儲存個人檔案失敗")
    return result.data[0]
