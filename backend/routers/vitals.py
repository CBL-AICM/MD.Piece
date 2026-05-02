"""
生理紀錄（Vitals）— 患者自記身高、體重、BMI、血壓、血糖、心率、體溫等
數據，並支援患者自訂指標。資料最終會匯整給醫師端參考。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 預設指標：metric_type → (label, unit) ─────────────────
DEFAULT_METRICS = {
    "height": {"label": "身高", "unit": "cm"},
    "weight": {"label": "體重", "unit": "kg"},
    "bmi": {"label": "BMI", "unit": "kg/m²"},
    "blood_pressure": {"label": "血壓", "unit": "mmHg"},   # value=收縮、value2=舒張
    "blood_sugar": {"label": "血糖", "unit": "mg/dL"},
    "heart_rate": {"label": "心率", "unit": "bpm"},
    "body_temperature": {"label": "體溫", "unit": "°C"},
    "oxygen_saturation": {"label": "血氧", "unit": "%"},
    "waist": {"label": "腰圍", "unit": "cm"},
}


def _ensure_patient_exists(sb, patient_id: str) -> None:
    """避免 vitals.patient_id FK 失敗：找不到時用 users.nickname 建 stub。"""
    try:
        existing = sb.table("patients").select("id").eq("id", patient_id).limit(1).execute()
        if existing.data:
            return
        name = "訪客"
        try:
            u = sb.table("users").select("nickname").eq("id", patient_id).limit(1).execute()
            if u.data and u.data[0].get("nickname"):
                name = u.data[0]["nickname"]
        except Exception:
            pass
        sb.table("patients").insert({"id": patient_id, "name": name}).execute()
    except Exception as e:
        logger.warning(f"ensure_patient_exists skipped for {patient_id}: {e}")


# ── Models ────────────────────────────────────────────────

class VitalCreate(BaseModel):
    patient_id: str
    metric_type: str            # 預設指標 id 或 "custom"
    label: Optional[str] = None  # custom 時必填；其他可省略（用預設）
    value: float
    value2: Optional[float] = None  # 血壓舒張 / 自訂第二值
    unit: Optional[str] = None
    notes: Optional[str] = None
    recorded_at: Optional[str] = None  # ISO 字串；未提供則使用現在


# ── 紀錄 CRUD ─────────────────────────────────────────────

@router.post("/")
def create_vital(body: VitalCreate):
    """新增一筆生理數值紀錄"""
    if not body.metric_type:
        raise HTTPException(status_code=400, detail="metric_type 必填")
    if body.metric_type == "custom" and not body.label:
        raise HTTPException(status_code=400, detail="自訂指標需要 label")
    if body.value is None:
        raise HTTPException(status_code=400, detail="value 必填")

    meta = DEFAULT_METRICS.get(body.metric_type, {})
    label = body.label or meta.get("label") or body.metric_type
    unit = body.unit or meta.get("unit")

    sb = get_supabase()
    _ensure_patient_exists(sb, body.patient_id)

    data = {
        "patient_id": body.patient_id,
        "metric_type": body.metric_type,
        "label": label,
        "value": body.value,
        "value2": body.value2,
        "unit": unit,
        "notes": body.notes,
        "recorded_at": body.recorded_at or datetime.utcnow().isoformat(),
    }
    result = sb.table("vitals").insert(data).execute()
    return result.data[0] if result.data else data


@router.get("/")
def list_vitals(
    patient_id: str = Query(...),
    metric_type: Optional[str] = Query(None),
    days: int = Query(90, description="查詢最近幾天，預設 90"),
):
    """取得患者的生理紀錄；可依 metric_type 過濾。"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    q = sb.table("vitals").select("*").eq("patient_id", patient_id).gte("recorded_at", since)
    if metric_type:
        q = q.eq("metric_type", metric_type)
    result = q.order("recorded_at", desc=True).execute()
    return {"vitals": result.data or []}


@router.delete("/{vital_id}")
def delete_vital(vital_id: str):
    """刪除一筆紀錄"""
    sb = get_supabase()
    sb.table("vitals").delete().eq("id", vital_id).execute()
    return {"status": "deleted", "id": vital_id}


@router.get("/summary")
def get_summary(patient_id: str = Query(...)):
    """每個 metric_type 的最新一筆值（給患者首頁/卡片使用）。"""
    sb = get_supabase()
    result = sb.table("vitals").select("*").eq("patient_id", patient_id).order("recorded_at", desc=True).execute()
    rows = result.data or []
    latest: dict = {}
    for r in rows:
        mt = r.get("metric_type")
        if mt and mt not in latest:
            latest[mt] = r
    return {"latest": latest, "total_records": len(rows)}


@router.get("/doctor/{patient_id}")
def get_for_doctor(patient_id: str, days: int = Query(30)):
    """
    醫師端視圖：依 metric_type 分組整理趨勢與最近數值。
    回傳 { metric_type: { label, unit, latest, count, series: [...] } }
    """
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = sb.table("vitals").select("*").eq("patient_id", patient_id).gte("recorded_at", since).order("recorded_at").execute()
    rows = result.data or []

    grouped: dict = {}
    for r in rows:
        mt = r.get("metric_type") or "custom"
        # 自訂指標以 label 細分（醫師端會看到不同的自訂值）
        key = mt if mt != "custom" else f"custom:{r.get('label') or '自訂'}"
        g = grouped.setdefault(key, {
            "metric_type": mt,
            "label": r.get("label"),
            "unit": r.get("unit"),
            "series": [],
            "count": 0,
        })
        g["series"].append({
            "recorded_at": r.get("recorded_at"),
            "value": r.get("value"),
            "value2": r.get("value2"),
            "notes": r.get("notes"),
        })
        g["count"] += 1
        g["latest"] = g["series"][-1]

    return {
        "patient_id": patient_id,
        "days": days,
        "metrics": grouped,
        "total_records": len(rows),
    }


@router.get("/metrics")
def list_default_metrics():
    """前端用：取得預設指標清單（label / unit）。"""
    return {"metrics": DEFAULT_METRICS}
