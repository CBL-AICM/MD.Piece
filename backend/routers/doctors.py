from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import DoctorCreate, DoctorUpdate

router = APIRouter()


@router.get("/")
def get_doctors():
    sb = get_supabase()
    result = sb.table("doctors").select("*").order("created_at", desc=True).execute()
    return {"doctors": result.data}


@router.get("/{doctor_id}")
def get_doctor(doctor_id: str):
    sb = get_supabase()
    result = sb.table("doctors").select("*").eq("id", doctor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該醫師")
    return result.data[0]


@router.post("/")
def create_doctor(body: DoctorCreate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = sb.table("doctors").insert(data).execute()
    return result.data[0]


@router.put("/{doctor_id}")
def update_doctor(doctor_id: str, body: DoctorUpdate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    result = sb.table("doctors").update(data).eq("id", doctor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該醫師")
    return result.data[0]


@router.delete("/{doctor_id}")
def delete_doctor(doctor_id: str):
    sb = get_supabase()
    result = sb.table("doctors").delete().eq("id", doctor_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該醫師")
    return {"message": "醫師已刪除", "id": doctor_id}
