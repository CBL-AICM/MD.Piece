from fastapi import APIRouter, HTTPException, Query
from backend.db import get_supabase
from backend.models import MedicalRecordCreate, MedicalRecordUpdate

router = APIRouter()


@router.get("/")
def get_records(
    patient_id: str | None = Query(None),
    doctor_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    diagnosis: str | None = Query(None),
):
    """列出病歷，支援篩選。"""
    supabase_client = get_supabase()
    query = supabase_client.table("medical_records").select("*, patients(name), doctors(name)")

    if patient_id:
        query = query.eq("patient_id", patient_id)
    if doctor_id:
        query = query.eq("doctor_id", doctor_id)
    if date_from:
        query = query.gte("visit_date", date_from)
    if date_to:
        query = query.lte("visit_date", date_to)
    if diagnosis:
        query = query.ilike("diagnosis", f"%{diagnosis}%")

    db_result = query.order("visit_date", desc=True).execute()
    return {"records": db_result.data}


@router.get("/{record_id}")
def get_record(record_id: str):
    supabase_client = get_supabase()
    db_result = supabase_client.table("medical_records").select("*, patients(name, age, gender), doctors(name, specialty)").eq("id", record_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return db_result.data[0]


@router.post("/")
def create_record(record_input: MedicalRecordCreate):
    supabase_client = get_supabase()
    record_fields = record_input.model_dump(exclude_none=True)
    if "visit_date" in record_fields and record_fields["visit_date"]:
        record_fields["visit_date"] = record_fields["visit_date"].isoformat()
    db_result = supabase_client.table("medical_records").insert(record_fields).execute()
    return db_result.data[0]


@router.put("/{record_id}")
def update_record(record_id: str, record_update: MedicalRecordUpdate):
    supabase_client = get_supabase()
    update_fields = record_update.model_dump(exclude_none=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    if "visit_date" in update_fields and update_fields["visit_date"]:
        update_fields["visit_date"] = update_fields["visit_date"].isoformat()
    db_result = supabase_client.table("medical_records").update(update_fields).eq("id", record_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return db_result.data[0]


@router.delete("/{record_id}")
def delete_record(record_id: str):
    supabase_client = get_supabase()
    db_result = supabase_client.table("medical_records").delete().eq("id", record_id).execute()
    if not db_result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return {"message": "病歷已刪除", "id": record_id}


@router.get("/patient/{patient_id}")
def get_patient_records(patient_id: str):
    """取得某位病患的所有就診紀錄。"""
    supabase_client = get_supabase()
    db_result = supabase_client.table("medical_records").select("*, doctors(name, specialty)").eq("patient_id", patient_id).order("visit_date", desc=True).execute()
    return {"records": db_result.data}
