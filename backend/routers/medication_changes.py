from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import MedicationChangeCreate

router = APIRouter()


@router.get("/")
def list_changes(
    patient_id: str | None = None,
    medication_id: str | None = None,
):
    sb = get_supabase()
    q = sb.table("medication_changes").select("*")
    if patient_id:
        q = q.eq("patient_id", patient_id)
    if medication_id:
        q = q.eq("medication_id", medication_id)
    result = q.order("effective_date", desc=True).execute()
    return {"changes": result.data}


@router.post("/")
def create_change(body: MedicationChangeCreate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    valid_types = {"start", "stop", "dose_up", "dose_down", "switch", "frequency", "other"}
    if data["change_type"] not in valid_types:
        raise HTTPException(status_code=400, detail=f"change_type 必須為 {valid_types}")
    result = sb.table("medication_changes").insert(data).execute()
    return result.data[0]


@router.delete("/{change_id}")
def delete_change(change_id: str):
    sb = get_supabase()
    result = sb.table("medication_changes").delete().eq("id", change_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到調藥紀錄")
    return {"message": "已刪除", "id": change_id}
