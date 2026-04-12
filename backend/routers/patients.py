from datetime import datetime, timedelta, timezone

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


@router.get("/{patient_id}/overview")
def get_patient_overview(patient_id: str):
    """Comprehensive patient data for doctor portal view"""
    sb = get_supabase()

    patient_result = sb.table("patients").select("*").eq("id", patient_id).execute()
    if not patient_result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    patient = patient_result.data[0]

    since_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    symptoms_result = (
        sb.table("symptoms_log").select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True).limit(10).execute()
    )
    emotions_result = (
        sb.table("emotions").select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True).limit(7).execute()
    )
    meds_result = sb.table("medications").select("*").eq("patient_id", patient_id).execute()
    records_result = (
        sb.table("medical_records")
        .select("*, doctors(name, specialty)")
        .eq("patient_id", patient_id)
        .order("visit_date", desc=True).limit(5).execute()
    )
    symptom_30d_result = (
        sb.table("symptoms_log").select("id")
        .eq("patient_id", patient_id).gte("created_at", since_30d).execute()
    )

    emotions_data = emotions_result.data or []
    scores = [e["score"] for e in emotions_data if e.get("score") is not None]
    avg_emotion = round(sum(scores) / len(scores), 1) if scores else None

    all_meds = meds_result.data or []
    active_meds = [m for m in all_meds if m.get("active") not in (0, False)]

    return {
        "patient": patient,
        "recent_symptoms": symptoms_result.data or [],
        "recent_emotions": emotions_result.data or [],
        "avg_emotion_score": avg_emotion,
        "active_medications": active_meds,
        "medication_count": len(active_meds),
        "recent_records": records_result.data or [],
        "symptom_count_30d": len(symptom_30d_result.data or []),
    }


@router.delete("/{patient_id}")
def delete_patient(patient_id: str):
    sb = get_supabase()
    result = sb.table("patients").delete().eq("id", patient_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該病患")
    return {"message": "病患已刪除", "id": patient_id}
