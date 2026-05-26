"""Memo 後端持久化。

原本 memo 只活在 localStorage（換瀏覽器就消失、診前報告看不到），
這個 router 提供 CRUD + upsert（用 client_id 去重）讓前端可以雙向同步。

Supabase 表：public.memos
  - id          uuid primary key
  - patient_id  text not null
  - kind        text default 'text'    -- 'text' | 'photo'
  - content     text                   -- 文字內容
  - photo_data  text                   -- dataURL（可選）
  - for_doctor  boolean                -- 是否要給醫師看
  - client_id   text                   -- 前端產生的 m_xxx ID，用來去重 / 一次性 migrate
  - created_at, updated_at
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


class MemoIn(BaseModel):
    patient_id: str
    kind: str = "text"            # 'text' | 'photo'
    content: str = ""
    photo_data: Optional[str] = None
    for_doctor: bool = False
    client_id: Optional[str] = None  # 前端 m_xxx，用來去重


class MemoUpdate(BaseModel):
    kind: Optional[str] = None
    content: Optional[str] = None
    photo_data: Optional[str] = None
    for_doctor: Optional[bool] = None


def _serialize(row: dict) -> dict:
    """後端 row → 前端期望的扁平 shape（沿用既有 localStorage 結構）。"""
    return {
        "id": row.get("id"),
        "client_id": row.get("client_id"),
        "type": row.get("kind") or "text",
        "text": row.get("content") or "",
        "photo": row.get("photo_data"),
        "forDoctor": bool(row.get("for_doctor")),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


@router.get("/")
def list_memos(
    patient_id: str = Query(...),
    limit: int = Query(500, ge=1, le=2000),
):
    """列出某位 patient 的所有 memo，最新優先。"""
    sb = get_supabase()
    result = (
        sb.table("memos").select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = result.data or []
    return {"memos": [_serialize(r) for r in rows], "count": len(rows)}


@router.post("/")
def create_memo(body: MemoIn):
    """建立或 upsert 一則 memo。若 client_id 已存在則 update，否則 insert。"""
    if not body.content and not body.photo_data:
        raise HTTPException(status_code=400, detail="memo 必須有文字或照片")
    sb = get_supabase()
    payload = {
        "patient_id": body.patient_id,
        "kind": body.kind,
        "content": body.content,
        "photo_data": body.photo_data,
        "for_doctor": bool(body.for_doctor),
        "client_id": body.client_id,
    }

    # 若帶 client_id，先看是否已存在 → 走 update（前端 sync 流程會重送）
    if body.client_id:
        existing = (
            sb.table("memos").select("id")
            .eq("patient_id", body.patient_id)
            .eq("client_id", body.client_id)
            .limit(1).execute().data or []
        )
        if existing:
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            result = (
                sb.table("memos").update(payload)
                .eq("id", existing[0]["id"]).execute()
            )
            return _serialize(result.data[0]) if result.data else {"id": existing[0]["id"]}

    result = sb.table("memos").insert(payload).execute()
    return _serialize(result.data[0]) if result.data else {}


@router.patch("/{memo_id}")
def update_memo(memo_id: str, body: MemoUpdate):
    """更新指定 memo 的部分欄位。"""
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新欄位")
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    sb = get_supabase()
    result = sb.table("memos").update(data).eq("id", memo_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該 memo")
    return _serialize(result.data[0])


@router.delete("/{memo_id}")
def delete_memo(memo_id: str):
    sb = get_supabase()
    result = sb.table("memos").delete().eq("id", memo_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該 memo")
    return {"message": "已刪除", "id": memo_id}


class MemoSyncIn(BaseModel):
    patient_id: str
    memos: List[MemoIn]


@router.post("/sync")
def sync_memos(body: MemoSyncIn):
    """一次性 migrate：把 localStorage 既有的 memo 全部 upsert 到後端。
    用 client_id 去重，所以重複呼叫安全。"""
    sb = get_supabase()
    pushed = 0
    skipped = 0
    for m in body.memos:
        if not m.content and not m.photo_data:
            skipped += 1
            continue
        payload = {
            "patient_id": body.patient_id,
            "kind": m.kind,
            "content": m.content,
            "photo_data": m.photo_data,
            "for_doctor": bool(m.for_doctor),
            "client_id": m.client_id,
        }
        try:
            if m.client_id:
                existing = (
                    sb.table("memos").select("id")
                    .eq("patient_id", body.patient_id)
                    .eq("client_id", m.client_id)
                    .limit(1).execute().data or []
                )
                if existing:
                    skipped += 1
                    continue
            sb.table("memos").insert(payload).execute()
            pushed += 1
        except Exception as e:
            logger.warning(f"memo sync 失敗 (client_id={m.client_id}): {e}")
            skipped += 1
    return {"pushed": pushed, "skipped": skipped, "total": len(body.memos)}
