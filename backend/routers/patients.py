"""
病患資料 — Phase 1b：強制 JWT 驗證 + 「只能存取自己」（Issue #388）

`patient_id` 在本系統中等同 `user.id`（frontend `getStablePatientId()` 取
登入使用者的 id；demo 模式才會用獨立 UUID）。所以這個 router 是 self-service
而非 doctor portal —— 全部端點都鎖死 caller == 資料擁有者。

GET / 原本回所有人資料，是 P0 隱私洩漏；改成只回自己那筆。
"""

import re

from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_supabase
from backend.models import PatientCreate, PatientUpdate
from backend.security import current_user

router = APIRouter()

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _safe_id(value: str, label: str = "patient_id") -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"{label} 格式不合法")
    return value


def _enforce_self(patient_id: str, me: dict) -> str:
    """patient_id 必須等於 token 的 sub。"""
    pid = _safe_id(patient_id)
    if me.get("id") != pid:
        raise HTTPException(status_code=403, detail="不可存取他人病患資料")
    return pid


@router.get("/")
def get_patients(me: dict = Depends(current_user)):
    """只回 caller 自己那一筆（包裝成 list 維持原本回傳結構）。"""
    sb = get_supabase()
    result = sb.table("patients").select("*").eq("id", me["id"]).execute()
    return {"patients": result.data}


@router.get("/{patient_id}")
def get_patient(patient_id: str, me: dict = Depends(current_user)):
    pid = _enforce_self(patient_id, me)
    sb = get_supabase()
    result = sb.table("patients").select("*").eq("id", pid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return result.data[0]


@router.post("/")
def create_patient(body: PatientCreate, me: dict = Depends(current_user)):
    """建立自己的病患資料；id 強制由 token 帶入，不接受 body 偽造。"""
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    data["id"] = me["id"]
    result = sb.table("patients").insert(data).execute()
    return result.data[0]


@router.put("/{patient_id}")
def update_patient(patient_id: str, body: PatientUpdate, me: dict = Depends(current_user)):
    pid = _enforce_self(patient_id, me)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    result = sb.table("patients").update(data).eq("id", pid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return result.data[0]


@router.delete("/{patient_id}")
def delete_patient(patient_id: str, me: dict = Depends(current_user)):
    pid = _enforce_self(patient_id, me)
    sb = get_supabase()
    result = sb.table("patients").delete().eq("id", pid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return {"message": "病患已刪除", "id": pid}
