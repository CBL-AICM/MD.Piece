from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import DoctorCreate, DoctorUpdate

router = APIRouter()


@router.get("/")
def get_doctors():
    supabase_client = get_supabase()
    db_result = supabase_client.table("doctors").select("*").order("created_at", desc=True).execute()
    return {"doctors": db_result.data}


@router.get("/{doctor_id}")
def get_doctor(doctor_id: str):
    supabase_client = get_supabase()
    db_result = supabase_client.table("doctors").select("*").eq("id", doctor_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該醫師")
    return db_result.data[0]


@router.post("/")
def create_doctor(doctor_input: DoctorCreate):
    supabase_client = get_supabase()
    doctor_fields = doctor_input.model_dump(exclude_none=True)
    db_result = supabase_client.table("doctors").insert(doctor_fields).execute()
    return db_result.data[0]


@router.put("/{doctor_id}")
def update_doctor(doctor_id: str, doctor_update: DoctorUpdate):
    supabase_client = get_supabase()
    update_fields = doctor_update.model_dump(exclude_none=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    db_result = supabase_client.table("doctors").update(update_fields).eq("id", doctor_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該醫師")
    return db_result.data[0]


@router.delete("/{doctor_id}")
def delete_doctor(doctor_id: str):
    supabase_client = get_supabase()
    db_result = supabase_client.table("doctors").delete().eq("id", doctor_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該醫師")
    return {"message": "醫師已刪除", "id": doctor_id}
