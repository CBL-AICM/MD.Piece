from fastapi import APIRouter, Depends, HTTPException
from backend.db import get_supabase
from backend.models import MedicationChangeCreate
from backend.security import current_user_optional, enforce_patient_scope

router = APIRouter()


@router.get("/")
def list_changes(
    patient_id: str | None = None,
    medication_id: str | None = None,
    me: dict | None = Depends(current_user_optional),
):
    # 已登入：一律鎖定自己（忽略前端 patient_id，避免越權）；
    # demo 未登入：必須帶 patient_id，否則回空——絕不回全表（舊 P0：省略時回所有人）。
    if isinstance(me, dict):
        patient_id = me["id"]
    if not patient_id:
        return {"changes": []}
    sb = get_supabase()
    q = sb.table("medication_changes").select("*").eq("patient_id", patient_id)
    if medication_id:
        q = q.eq("medication_id", medication_id)
    result = q.order("effective_date", desc=True).execute()
    return {"changes": result.data}


@router.post("/")
def create_change(body: MedicationChangeCreate, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(getattr(body, "patient_id", None), me)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    valid_types = {"start", "stop", "dose_up", "dose_down", "switch", "frequency", "other"}
    if data["change_type"] not in valid_types:
        raise HTTPException(status_code=400, detail=f"change_type 必須為 {valid_types}")
    result = sb.table("medication_changes").insert(data).execute()
    return result.data[0]


@router.delete("/{change_id}")
def delete_change(change_id: str, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    existing = sb.table("medication_changes").select("patient_id").eq("id", change_id).limit(1).execute().data
    if existing:
        enforce_patient_scope(existing[0].get("patient_id"), me)
    result = sb.table("medication_changes").delete().eq("id", change_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到調藥紀錄")
    return {"message": "已刪除", "id": change_id}
