"""
個人檔案 / 慢性病 / 緊急聯絡人 — per-user 持久化（Issue #131）

原本只存 localStorage，使用者反映「清快取 / 換瀏覽器就不見」。本 router
把資料同步到 Supabase patient_profiles 表，UPSERT 模式：一個 user_id
對應一筆 profile，全欄位可選（漸進式填寫）。

存取控制：本專案用 backend 自有 username+scrypt 而非 Supabase Auth，
所以這邊不走 RLS by auth.uid()，由 backend layer 保證 user_id 來自登入態。
前端帶 user_id 即可，未來改 Supabase Auth 再加 policy。
"""

import re
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.db import _SCHEMAS, get_supabase
from backend.models import PatientProfileUpsert

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


@router.get("/{user_id}")
def get_profile(user_id: str):
    """取得個人檔案。沒有就回 404（前端會 fallback 到 localStorage 或空表單）。"""
    uid = _safe_id(user_id)
    sb = get_supabase()
    result = sb.table("patient_profiles").select("*").eq("user_id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="尚未建立個人檔案")
    return result.data[0]


@router.put("/{user_id}")
def upsert_profile(user_id: str, body: PatientProfileUpsert):
    """完整覆寫個人檔案（UPSERT）。沒有就建、有就改。"""
    uid = _safe_id(user_id)
    payload = body.model_dump(exclude_unset=False)
    # birthday 空字串 → None 並驗證格式
    payload["birthday"] = _validate_date(payload.get("birthday"))
    payload["user_id"] = uid
    payload["updated_at"] = datetime.utcnow().isoformat()

    sb = get_supabase()
    # Supabase python client 的 upsert 需要 conflict 欄位
    result = sb.table("patient_profiles").upsert(payload, on_conflict="user_id").execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="儲存個人檔案失敗")
    return result.data[0]
