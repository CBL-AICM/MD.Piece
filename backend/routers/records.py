from fastapi import APIRouter, Depends, HTTPException, Query
from backend.db import get_supabase
from backend.models import MedicalRecordCreate, MedicalRecordUpdate
from backend.security import current_user

router = APIRouter()


def _owned_record(record_id, me):
    """讀出病歷並確認屬於 caller；否則 404。"""
    sb = get_supabase()
    result = sb.table("medical_records").select("*").eq("id", record_id).execute()
    row = result.data[0] if result.data else None
    if not row or row.get("patient_id") != me.get("id"):
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return sb, row


@router.get("/")
def get_records(
    patient_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    diagnosis: str | None = Query(None),
    me: dict = Depends(current_user),
):
    """列出病歷，支援篩選。一律只回 caller 自己的病歷。"""
    if patient_id and patient_id != me.get("id"):
        raise HTTPException(status_code=403, detail="不可存取他人資料")
    sb = get_supabase()
    query = sb.table("medical_records").select("*, patients(name)")

    query = query.eq("patient_id", me["id"])
    if date_from:
        query = query.gte("visit_date", date_from)
    if date_to:
        query = query.lte("visit_date", date_to)
    if diagnosis:
        query = query.ilike("diagnosis", f"%{diagnosis}%")

    result = query.order("visit_date", desc=True).execute()
    return {"records": result.data}


@router.get("/{record_id}")
def get_record(record_id: str, me: dict = Depends(current_user)):
    _sb, row = _owned_record(record_id, me)
    return row


@router.post("/")
def create_record(body: MedicalRecordCreate, me: dict = Depends(current_user)):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    data["patient_id"] = me["id"]  # 不信任 body 的 patient_id，鎖定為 caller
    if "visit_date" in data and data["visit_date"]:
        data["visit_date"] = data["visit_date"].isoformat()
    result = sb.table("medical_records").insert(data).execute()
    return result.data[0]


@router.put("/{record_id}")
def update_record(record_id: str, body: MedicalRecordUpdate, me: dict = Depends(current_user)):
    sb, _row = _owned_record(record_id, me)
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    data.pop("patient_id", None)  # 不允許改 owner
    if "visit_date" in data and data["visit_date"]:
        data["visit_date"] = data["visit_date"].isoformat()
    result = sb.table("medical_records").update(data).eq("id", record_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return result.data[0]


@router.delete("/{record_id}")
def delete_record(record_id: str, me: dict = Depends(current_user)):
    sb, _row = _owned_record(record_id, me)
    result = sb.table("medical_records").delete().eq("id", record_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return {"message": "病歷已刪除", "id": record_id}


@router.get("/patient/{patient_id}")
def get_patient_records(patient_id: str, me: dict = Depends(current_user)):
    """取得某位病患的所有就診紀錄（限本人）。"""
    if patient_id != me.get("id"):
        raise HTTPException(status_code=403, detail="不可存取他人資料")
    sb = get_supabase()
    result = sb.table("medical_records").select("*").eq("patient_id", patient_id).order("visit_date", desc=True).execute()
    return {"records": result.data}
