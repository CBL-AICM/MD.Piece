"""病患備忘（memo）— 文字／照片小紙條，可標記「給醫師看」。

對應 Supabase `memos` 表，以 (patient_id, client_id) 做幂等 upsert：
前端本機既有的 memo 可補傳、編輯會覆蓋、重複送不會產生多筆。
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from backend.db import get_supabase

router = APIRouter()


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
def list_memos(patient_id: str = Query(...)):
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
def upsert_memo(body: MemoUpsert):
    sb = get_supabase()
    existing = (
        sb.table("memos")
        .select("id")
        .eq("patient_id", body.patient_id)
        .eq("client_id", body.client_id)
        .execute()
    )
    fields = {
        "kind": body.kind,
        "content": body.content,
        "photo_data": body.photo_data,
        "for_doctor": body.for_doctor,
    }
    if existing.data:
        # 已存在 → 只覆蓋內容，保留原本的 created_at
        (
            sb.table("memos")
            .update(fields)
            .eq("patient_id", body.patient_id)
            .eq("client_id", body.client_id)
            .execute()
        )
    else:
        payload = {"patient_id": body.patient_id, "client_id": body.client_id, **fields}
        if body.created_at:
            payload["created_at"] = body.created_at
        sb.table("memos").insert(payload).execute()
    return {"status": "ok", "client_id": body.client_id}


@router.delete("/{patient_id}/{client_id}")
def delete_memo(patient_id: str, client_id: str):
    sb = get_supabase()
    (
        sb.table("memos")
        .delete()
        .eq("patient_id", patient_id)
        .eq("client_id", client_id)
        .execute()
    )
    return {"deleted": client_id}
