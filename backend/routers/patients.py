from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import PatientCreate, PatientUpdate

router = APIRouter()


@router.get("/")
def get_patients():
    sb = get_supabase()
    result = sb.table("patients").select("*").order("created_at", desc=True).execute()
    return {"patients": result.data}


@router.get("/{patient_id}")
def get_patient(patient_id: str):
    sb = get_supabase()
    result = sb.table("patients").select("*").eq("id", patient_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return result.data[0]


@router.post("/")
def create_patient(body: PatientCreate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = sb.table("patients").insert(data).execute()
    return result.data[0]


@router.put("/{patient_id}")
def update_patient(patient_id: str, body: PatientUpdate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    result = sb.table("patients").update(data).eq("id", patient_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return result.data[0]


@router.delete("/{patient_id}")
def delete_patient(patient_id: str):
    sb = get_supabase()
    result = sb.table("patients").delete().eq("id", patient_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return {"message": "病患已刪除", "id": patient_id}
