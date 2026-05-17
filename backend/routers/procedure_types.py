"""
自訂處置類型 router — 給住院模式首頁「今日治療」Timeline 用。

內建處置目錄 `_IP_EXAM_TYPES`（前端 app.js）涵蓋常見的檢查 / 注射輸液 / 護理處置；
本 router 提供「使用者自己的類型」的 CRUD，存到 Supabase（custom_procedure_types 表）。

- per-patient（不綁特定 admission，可跨多次入院重用）
- key 在同一個 patient 下唯一；前端排程 (exam record) 仍以 key 引用
- 內建 + 自訂合併後一起顯示在 composer 的 <select>，依 category 分組
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import logging
import re

from backend.db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


_ALLOWED_CATEGORIES = {"exam", "treatment", "nursing"}
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class CustomProcedureTypeCreate(BaseModel):
    patient_id: str
    key: str = Field(..., description="識別字串；小寫字母開頭，可含底線 / 數字；同一位患者下唯一")
    label: str
    icon: str = "clipboard-list"
    category: str = "exam"
    default_prep: Optional[str] = ""
    description: Optional[str] = ""


class CustomProcedureTypeUpdate(BaseModel):
    label: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    default_prep: Optional[str] = None
    description: Optional[str] = None


def _validate_key(key: str) -> str:
    key = (key or "").strip().lower()
    if not _KEY_RE.match(key):
        raise HTTPException(
            status_code=400,
            detail="key 必須是小寫英文開頭，可含字母 / 數字 / 底線，最長 32 字元",
        )
    return key


def _validate_category(category: str) -> str:
    if category not in _ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"category 必須是 {sorted(_ALLOWED_CATEGORIES)} 其中之一",
        )
    return category


@router.get("/")
def list_custom_types(patient_id: str = Query(...)):
    """列出該患者所有自訂處置類型。"""
    sb = get_supabase()
    result = (
        sb.table("custom_procedure_types")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=False)
        .execute()
    )
    return {"types": result.data or []}


@router.post("/")
def create_custom_type(body: CustomProcedureTypeCreate):
    """新增一筆自訂處置類型。"""
    key = _validate_key(body.key)
    category = _validate_category(body.category)
    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label 不可為空")
    if len(label) > 40:
        raise HTTPException(status_code=400, detail="label 最長 40 字")

    sb = get_supabase()

    existing = (
        sb.table("custom_procedure_types")
        .select("id")
        .eq("patient_id", body.patient_id)
        .eq("key", key)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail=f"key '{key}' 已存在，請換一個")

    data = {
        "patient_id": body.patient_id,
        "key": key,
        "label": label,
        "icon": (body.icon or "clipboard-list").strip() or "clipboard-list",
        "category": category,
        "default_prep": (body.default_prep or "").strip(),
        "description": (body.description or "").strip(),
    }
    try:
        result = sb.table("custom_procedure_types").insert(data).execute()
    except Exception as e:
        logger.error(f"Create custom procedure type failed: {e}")
        raise HTTPException(status_code=400, detail="新增自訂處置類型失敗")
    if not result.data:
        raise HTTPException(status_code=400, detail="新增失敗（資料庫未回傳資料）")
    return result.data[0]


@router.put("/{type_id}")
def update_custom_type(type_id: str, body: CustomProcedureTypeUpdate):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    if "category" in data:
        data["category"] = _validate_category(data["category"])
    if "label" in data:
        label = data["label"].strip()
        if not label:
            raise HTTPException(status_code=400, detail="label 不可為空")
        if len(label) > 40:
            raise HTTPException(status_code=400, detail="label 最長 40 字")
        data["label"] = label
    if "icon" in data:
        data["icon"] = data["icon"].strip() or "clipboard-list"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    sb = get_supabase()
    result = (
        sb.table("custom_procedure_types").update(data).eq("id", type_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該自訂處置類型")
    return result.data[0]


@router.delete("/{type_id}")
def delete_custom_type(type_id: str):
    sb = get_supabase()
    result = sb.table("custom_procedure_types").delete().eq("id", type_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該自訂處置類型")
    return {"deleted": result.data[0]}
