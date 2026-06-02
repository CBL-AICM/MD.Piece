"""生理量測（vitals）— 血壓、體重、血糖、BMI 等病患自記數值。

原本只存在前端 localStorage（mdpiece_vitals_entries），從不上傳。
對應 Supabase `vital_entries` 表，以 (patient_id, client_id) 幂等 upsert。
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from backend.db import get_supabase

router = APIRouter()


class VitalUpsert(BaseModel):
    patient_id: str
    client_id: str
    metric_id: str = ""
    value: float | None = None
    value2: float | None = None      # 雙值指標（如血壓舒張壓）
    context: str | None = None       # 情境，如「飯後」「早上」
    method: str | None = None
    notes: str = ""
    recorded_at: str | None = None


def _public(row: dict) -> dict:
    """DB 列 → 前端 vital entry 形狀（與 localStorage 內結構一致）。"""
    return {
        "id": row.get("client_id") or row.get("id"),
        "metricId": row.get("metric_id") or "",
        "value": row.get("value"),
        "value2": row.get("value2"),
        "context": row.get("context"),
        "method": row.get("method"),
        "notes": row.get("notes") or "",
        "recordedAt": row.get("recorded_at"),
    }


@router.get("/")
def list_vitals(patient_id: str = Query(...)):
    sb = get_supabase()
    res = (
        sb.table("vital_entries")
        .select("*")
        .eq("patient_id", patient_id)
        .order("recorded_at", desc=True)
        .execute()
    )
    return {"entries": [_public(r) for r in (res.data or [])]}


@router.post("/")
def upsert_vital(body: VitalUpsert):
    sb = get_supabase()
    existing = (
        sb.table("vital_entries")
        .select("id")
        .eq("patient_id", body.patient_id)
        .eq("client_id", body.client_id)
        .execute()
    )
    fields = {
        "metric_id": body.metric_id,
        "value": body.value,
        "value2": body.value2,
        "context": body.context,
        "method": body.method,
        "notes": body.notes,
    }
    if existing.data:
        (
            sb.table("vital_entries")
            .update(fields)
            .eq("patient_id", body.patient_id)
            .eq("client_id", body.client_id)
            .execute()
        )
    else:
        payload = {"patient_id": body.patient_id, "client_id": body.client_id, **fields}
        if body.recorded_at:
            payload["recorded_at"] = body.recorded_at
        sb.table("vital_entries").insert(payload).execute()
    return {"status": "ok", "client_id": body.client_id}


@router.delete("/{patient_id}/{client_id}")
def delete_vital(patient_id: str, client_id: str):
    sb = get_supabase()
    (
        sb.table("vital_entries")
        .delete()
        .eq("patient_id", patient_id)
        .eq("client_id", client_id)
        .execute()
    )
    return {"deleted": client_id}
