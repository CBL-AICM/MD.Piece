from fastapi import APIRouter, Depends, HTTPException, Query
from backend.db import get_supabase
from backend.models import MedicalRecordCreate, MedicalRecordUpdate
from backend.security import current_user_optional, enforce_patient_scope

router = APIRouter()


def _assert_owns_record(sb, record_id: str, me) -> dict:
    """以 record_id 操作病歷時的擁有權檢查：已登入則該筆 patient_id 必須是自己。"""
    res = sb.table("medical_records").select("*").eq("id", record_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    enforce_patient_scope(res.data[0].get("patient_id"), me)
    return res.data[0]


@router.get("/")
def get_records(
    patient_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    diagnosis: str | None = Query(None),
    me: dict | None = Depends(current_user_optional),
):
    """列出病歷，支援篩選。

    原本 patient_id 省略時會回「所有病患」的病歷（P0 跨帳號洩漏）。改為：
    - 已登入：一律只回自己（patient_id 強制為 token.sub，忽略前端值）。
    - demo 未登入：必須帶 patient_id，否則回空（絕不回全表）。
    """
    if isinstance(me, dict):
        patient_id = me["id"]
    if not patient_id:
        return {"records": []}

    sb = get_supabase()
    query = sb.table("medical_records").select("*, patients(name)").eq("patient_id", patient_id)

    if date_from:
        query = query.gte("visit_date", date_from)
    if date_to:
        query = query.lte("visit_date", date_to)
    if diagnosis:
        query = query.ilike("diagnosis", f"%{diagnosis}%")

    result = query.order("visit_date", desc=True).execute()
    return {"records": result.data}


@router.get("/{record_id}")
def get_record(record_id: str, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    _assert_owns_record(sb, record_id, me)
    result = sb.table("medical_records").select("*, patients(name, age, gender)").eq("id", record_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return result.data[0]


@router.post("/")
def create_record(body: MedicalRecordCreate, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(body.patient_id, me)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if "visit_date" in data and data["visit_date"]:
        data["visit_date"] = data["visit_date"].isoformat()
    result = sb.table("medical_records").insert(data).execute()
    return result.data[0]


@router.put("/{record_id}")
def update_record(record_id: str, body: MedicalRecordUpdate, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    _assert_owns_record(sb, record_id, me)
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    if "visit_date" in data and data["visit_date"]:
        data["visit_date"] = data["visit_date"].isoformat()
    result = sb.table("medical_records").update(data).eq("id", record_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return result.data[0]


@router.delete("/{record_id}")
def delete_record(record_id: str, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    _assert_owns_record(sb, record_id, me)
    result = sb.table("medical_records").delete().eq("id", record_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病歷")
    return {"message": "病歷已刪除", "id": record_id}


@router.get("/patient/{patient_id}")
def get_patient_records(patient_id: str, me: dict | None = Depends(current_user_optional)):
    """取得某位病患的所有就診紀錄。"""
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    result = sb.table("medical_records").select("*").eq("patient_id", patient_id).order("visit_date", desc=True).execute()
    return {"records": result.data}
