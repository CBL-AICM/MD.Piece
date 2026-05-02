from fastapi import APIRouter, Depends, HTTPException
from backend.db import get_supabase
from backend.dependencies import require_doctor
from backend.models import DoctorNoteCreate, DoctorNoteUpdate

router = APIRouter()


@router.get("/")
def list_notes(patient_id: str | None = None, doctor_id: str | None = None):
    sb = get_supabase()
    q = sb.table("doctor_notes").select("*")
    if patient_id:
        q = q.eq("patient_id", patient_id)
    if doctor_id:
        q = q.eq("doctor_id", doctor_id)
    result = q.order("created_at", desc=True).execute()
    return {"notes": result.data}


@router.get("/{note_id}")
def get_note(note_id: str):
    sb = get_supabase()
    result = sb.table("doctor_notes").select("*").eq("id", note_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到備註")
    return result.data[0]


@router.post("/")
def create_note(body: DoctorNoteCreate, user: dict = Depends(require_doctor)):
    if not body.doctor_id and user.get("linked_doctor_id"):
        body.doctor_id = user["linked_doctor_id"]
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = sb.table("doctor_notes").insert(data).execute()
    return result.data[0]


@router.put("/{note_id}")
def update_note(note_id: str, body: DoctorNoteUpdate, _user: dict = Depends(require_doctor)):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    from datetime import datetime, timezone
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = sb.table("doctor_notes").update(data).eq("id", note_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到備註")
    return result.data[0]


@router.delete("/{note_id}")
def delete_note(note_id: str, _user: dict = Depends(require_doctor)):
    sb = get_supabase()
    result = sb.table("doctor_notes").delete().eq("id", note_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到備註")
    return {"message": "備註已刪除", "id": note_id}
