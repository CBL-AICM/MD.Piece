"""生理紀錄（vital signs）— 患者端會把每筆數值同步到後端，
醫師端依 patient_id 讀取、做摺線圖。"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase

router = APIRouter()


class VitalSignCreate(BaseModel):
    patient_id: str
    metric_id: str            # weight / bp / glucose / heart / ... 或 custom-xxx
    metric_name: str          # 顯示名稱（中文）
    unit: Optional[str] = None
    value: float
    value2: Optional[float] = None   # 雙值（如血壓）
    notes: Optional[str] = None
    recorded_at: Optional[str] = None  # ISO 字串；省略時用 now


@router.post("/")
def create_vital(body: VitalSignCreate):
    sb = get_supabase()
    payload = body.model_dump(exclude_none=True)
    if "recorded_at" not in payload or not payload["recorded_at"]:
        payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
    try:
        result = sb.table("vital_signs").insert(payload).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"儲存生理紀錄失敗：{e}")
    return result.data[0] if result.data else payload


@router.get("/")
def list_vitals(
    patient_id: str = Query(...),
    metric_id: Optional[str] = Query(None),
    days: int = Query(180, ge=1, le=3650),
):
    """列出某位患者的生理紀錄。預設取近 180 天。"""
    sb = get_supabase()
    query = sb.table("vital_signs").select("*").eq("patient_id", patient_id)
    if metric_id:
        query = query.eq("metric_id", metric_id)
    try:
        result = query.order("recorded_at", desc=False).execute()
    except Exception:
        return {"vitals": []}
    return {"vitals": result.data or []}


@router.delete("/{vital_id}")
def delete_vital(vital_id: str):
    sb = get_supabase()
    try:
        result = sb.table("vital_signs").delete().eq("id", vital_id).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"刪除失敗：{e}")
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該紀錄")
    return {"ok": True, "id": vital_id}
