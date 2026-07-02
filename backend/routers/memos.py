"""病患備忘（memo）— 文字／照片小紙條，可標記「給醫師看」。

對應 Supabase `memos` 表，以 (patient_id, client_id) 做幂等 upsert：
前端本機既有的 memo 可補傳、編輯會覆蓋、重複送不會產生多筆。
"""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from backend.db import get_supabase
from backend.security import current_user_optional, enforce_patient_scope

router = APIRouter()

# 前端 client_id 形如 "m_<timestamp>_<base36>"；限制字元集避免惡意 id 流入
# 前端 onclick 內插（stored XSS 的縱深防禦）。
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class MemoUpsert(BaseModel):
    patient_id: str
    client_id: str            # 前端產生的 id，做去重／覆蓋的鍵
    kind: str = "text"        # "text" | "photo"
    content: str = ""
    photo_data: str | None = None
    for_doctor: bool = False
    created_at: str | None = None


def _public(row: dict) -> dict:
    """DB 列 → 前端 memo 形狀（與 localStorage 內現有結構一致）。"""
    return {
        "id": row.get("client_id") or row.get("id"),
        "type": row.get("kind") or "text",
        "text": row.get("content") or "",
        "photo": row.get("photo_data"),
        "forDoctor": bool(row.get("for_doctor")),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


@router.get("/")
def list_memos(patient_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    res = (
        sb.table("memos")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"memos": [_public(r) for r in (res.data or [])]}


@router.post("/")
def upsert_memo(body: MemoUpsert, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(body.patient_id, me)
    if not _CLIENT_ID_RE.match(body.client_id):
        raise HTTPException(status_code=400, detail="client_id 格式不合法")
    sb = get_supabase()
    # 原子 upsert（unique index (patient_id, client_id)）：避免先查再寫的競態撞
    # unique index 回 500。updated_at 一律以伺服器時間覆蓋；created_at 由前端帶原值，
    # 更新時覆蓋同值無害、新增時保留本機建立時間。
    payload = {
        "patient_id": body.patient_id,
        "client_id": body.client_id,
        "kind": body.kind,
        "content": body.content,
        "photo_data": body.photo_data,
        "for_doctor": body.for_doctor,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.created_at:
        payload["created_at"] = body.created_at
    sb.table("memos").upsert(payload, on_conflict="patient_id,client_id").execute()
    return {"status": "ok", "client_id": body.client_id}


@router.delete("/{patient_id}/{client_id}")
def delete_memo(patient_id: str, client_id: str, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    (
        sb.table("memos")
        .delete()
        .eq("patient_id", patient_id)
        .eq("client_id", client_id)
        .execute()
    )
    return {"deleted": client_id}
