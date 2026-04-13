from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from backend.db import get_supabase
from backend.models import AlertCreate, AlertUpdate

router = APIRouter()

VALID_TYPES = {
    "er_visit", "missed_medication", "self_discontinued",
    "infection", "low_mood", "psych_crisis", "other",
}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


@router.get("/")
def list_alerts(
    patient_id: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    resolved: bool | None = None,
):
    sb = get_supabase()
    q = sb.table("alerts").select("*")
    if patient_id:
        q = q.eq("patient_id", patient_id)
    if severity:
        q = q.eq("severity", severity)
    if acknowledged is not None:
        q = q.eq("acknowledged", 1 if acknowledged else 0)
    if resolved is not None:
        q = q.eq("resolved", 1 if resolved else 0)
    result = q.order("created_at", desc=True).execute()
    return {"alerts": result.data}


@router.get("/{alert_id}")
def get_alert(alert_id: str):
    sb = get_supabase()
    result = sb.table("alerts").select("*").eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到警示")
    return result.data[0]


@router.post("/")
def create_alert(body: AlertCreate):
    if body.alert_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"alert_type 無效，需為 {VALID_TYPES}")
    if body.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"severity 無效，需為 {VALID_SEVERITIES}")
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = sb.table("alerts").insert(data).execute()
    return result.data[0]


@router.put("/{alert_id}")
def update_alert(alert_id: str, body: AlertUpdate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if "acknowledged" in data:
        data["acknowledged"] = 1 if data["acknowledged"] else 0
        if data["acknowledged"]:
            data["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    if "resolved" in data:
        data["resolved"] = 1 if data["resolved"] else 0
        if data["resolved"]:
            data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    result = sb.table("alerts").update(data).eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到警示")
    return result.data[0]


@router.delete("/{alert_id}")
def delete_alert(alert_id: str):
    sb = get_supabase()
    result = sb.table("alerts").delete().eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到警示")
    return {"message": "已刪除", "id": alert_id}
