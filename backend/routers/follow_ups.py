"""
回診排程（follow-up appointments）。

一個病患可以有多筆未來回診（不同科別／醫院／時段），與 medical_records
（過去的就診紀錄）解耦。前端有獨立「回診排程」頁，Pieces 頁與首頁
chip 只顯示「最近一筆未完成的回診」。
"""

import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.db import _SCHEMAS, get_supabase
from backend.models import FollowUpCreate, FollowUpUpdate

router = APIRouter()

VALID_SESSIONS = {"am", "pm"}
VALID_STATUSES = {"scheduled", "completed", "missed", "cancelled"}

# Anchored allowlist for path / query string IDs — UUID 與 legacy demo-pid
# 都落在這個字元集內。明確 fullmatch 是給 CodeQL 看的 sanitizer barrier：
# db.py 的查詢都用 parameterized placeholder（?），值不會拼進 SQL，但
# 靜態分析難以追過那層 indirection，所以這裡 fail-closed 把不合格 id 擋掉。
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _safe_id(value: str, label: str = "id") -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"{label} 格式不合法")
    return value

# SQLite fallback schema（Supabase 由 docs/migration_follow_ups.sql 建立）
_SCHEMAS.setdefault(
    "follow_ups",
    """
        CREATE TABLE IF NOT EXISTS follow_ups (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            session TEXT,
            department TEXT,
            hospital TEXT,
            doctor_name TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )""",
)


def _validate_session(s):
    if s is None or s == "":
        return None
    s = str(s).lower()
    if s not in VALID_SESSIONS:
        raise HTTPException(status_code=400, detail=f"session 無效，需為 {VALID_SESSIONS} 或空")
    return s


def _validate_status(s):
    if s not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status 無效，需為 {VALID_STATUSES}")
    return s


def _validate_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="scheduled_date 格式錯誤，需為 YYYY-MM-DD")
    return s


@router.post("/")
def create_follow_up(body: FollowUpCreate):
    pid = _safe_id(body.patient_id, "patient_id")
    data = {
        "patient_id": pid,
        "scheduled_date": _validate_date(body.scheduled_date),
        "session": _validate_session(body.session),
        "department": body.department,
        "hospital": body.hospital,
        "doctor_name": body.doctor_name,
        "status": _validate_status(body.status),
        "notes": body.notes,
    }
    sb = get_supabase()
    result = sb.table("follow_ups").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="建立回診失敗")
    return result.data[0]


@router.get("/")
def list_follow_ups(
    patient_id: str = Query(...),
    status: str | None = None,
    upcoming_only: bool = False,
):
    pid = _safe_id(patient_id, "patient_id")
    sb = get_supabase()
    q = sb.table("follow_ups").select("*").eq("patient_id", pid)
    if status:
        q = q.eq("status", _validate_status(status))
    if upcoming_only:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        q = q.gte("scheduled_date", today).eq("status", "scheduled")
    result = q.order("scheduled_date", desc=False).execute()
    return {"follow_ups": result.data or []}


@router.get("/nearest")
def get_nearest_follow_up(patient_id: str = Query(...)):
    """回傳最近一筆未來且狀態為 scheduled 的回診；沒有則 follow_up=None。"""
    pid = _safe_id(patient_id, "patient_id")
    sb = get_supabase()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = (
        sb.table("follow_ups")
        .select("*")
        .eq("patient_id", pid)
        .eq("status", "scheduled")
        .gte("scheduled_date", today)
        .order("scheduled_date", desc=False)
        .limit(1)
        .execute()
    )
    return {"follow_up": (result.data[0] if result.data else None)}


@router.get("/{follow_up_id}")
def get_follow_up(follow_up_id: str):
    fid = _safe_id(follow_up_id, "follow_up_id")
    sb = get_supabase()
    result = sb.table("follow_ups").select("*").eq("id", fid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到回診")
    return result.data[0]


@router.put("/{follow_up_id}")
def update_follow_up(follow_up_id: str, body: FollowUpUpdate):
    fid = _safe_id(follow_up_id, "follow_up_id")
    updates = body.model_dump(exclude_none=True)
    if "scheduled_date" in updates:
        updates["scheduled_date"] = _validate_date(updates["scheduled_date"])
    if "session" in updates:
        updates["session"] = _validate_session(updates["session"])
    if "status" in updates:
        updates["status"] = _validate_status(updates["status"])
    if not updates:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    sb = get_supabase()
    result = sb.table("follow_ups").update(updates).eq("id", fid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到回診")
    return result.data[0]


@router.delete("/{follow_up_id}")
def delete_follow_up(follow_up_id: str):
    fid = _safe_id(follow_up_id, "follow_up_id")
    sb = get_supabase()
    result = sb.table("follow_ups").delete().eq("id", fid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到回診")
    return {"message": "已刪除", "id": fid}
