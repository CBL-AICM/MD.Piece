from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import PatientCreate, PatientUpdate

router = APIRouter()


@router.get("/")
def get_patients():
    supabase_client = get_supabase()
    db_result = supabase_client.table("patients").select("*").order("created_at", desc=True).execute()
    return {"patients": db_result.data}


@router.get("/{patient_id}")
def get_patient(patient_id: str):
    supabase_client = get_supabase()
    db_result = supabase_client.table("patients").select("*").eq("id", patient_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return db_result.data[0]


@router.post("/")
def create_patient(patient_input: PatientCreate):
    supabase_client = get_supabase()
    patient_fields = patient_input.model_dump(exclude_none=True)
    db_result = supabase_client.table("patients").insert(patient_fields).execute()
    return db_result.data[0]


@router.put("/{patient_id}")
def update_patient(patient_id: str, patient_update: PatientUpdate):
    supabase_client = get_supabase()
    update_fields = patient_update.model_dump(exclude_none=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    db_result = supabase_client.table("patients").update(update_fields).eq("id", patient_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return db_result.data[0]


@router.delete("/{patient_id}")
def delete_patient(patient_id: str):
    supabase_client = get_supabase()
    db_result = supabase_client.table("patients").delete().eq("id", patient_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return {"message": "病患已刪除", "id": patient_id}
