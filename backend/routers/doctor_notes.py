from fastapi import APIRouter, HTTPException, Header
from backend.db import get_supabase
from backend.models import DoctorNoteCreate, DoctorNoteUpdate

router = APIRouter()


def _resolve_user(user_id: str | None):
    """讀 X-User-Id header 對應的 user 物件；user_id 為空則回 None。"""
    if not user_id:
        return None
    try:
        sb = get_supabase()
        r = sb.table("users").select("id,role").eq("id", user_id).execute()
        if r.data:
            return r.data[0]
    except Exception:
        pass
    return None


def _require_doctor_or_patient_push(user_id: str | None, body_tags: list | None):
    """
    寫入規則：
    - 如果 tags 含 patient_push：呼叫者必須是 patient 角色
    - 否則：呼叫者必須是 doctor 角色
    - 如果沒帶 X-User-Id（向後相容）：放行但不檢查（之後可逐步收緊）
    """
    if not user_id:
        return
    user = _resolve_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="X-User-Id 對應的使用者不存在")
    is_patient_push = isinstance(body_tags, list) and "patient_push" in body_tags
    if is_patient_push:
        if user.get("role") != "patient":
            raise HTTPException(status_code=403, detail="只有患者可以建立 patient_push 紀錄")
    else:
        if user.get("role") != "doctor":
            raise HTTPException(status_code=403, detail="只有醫師可以建立／編輯醫師備註")


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
def create_note(body: DoctorNoteCreate, x_user_id: str | None = Header(default=None)):
    _require_doctor_or_patient_push(x_user_id, body.tags)
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = sb.table("doctor_notes").insert(data).execute()
    return result.data[0]


@router.put("/{note_id}")
def update_note(note_id: str, body: DoctorNoteUpdate, x_user_id: str | None = Header(default=None)):
    _require_doctor_or_patient_push(x_user_id, body.tags or [])
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
def delete_note(note_id: str, x_user_id: str | None = Header(default=None)):
    # 刪除走 doctor 角色（patient_push 由患者本人刪可以另外設計）
    _require_doctor_or_patient_push(x_user_id, [])
    sb = get_supabase()
    result = sb.table("doctor_notes").delete().eq("id", note_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到備註")
    return {"message": "備註已刪除", "id": note_id}
