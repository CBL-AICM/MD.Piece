from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import logging

from backend.db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()

# 生理紀錄 — 體溫/血壓/心率/血糖/血氧/體重/疼痛指數/呼吸頻率

# ── 生理指標定義 ─────────────────────────────────────────────

VITAL_TYPES = {
    "temperature": {
        "name": "體溫",
        "unit": "°C",
        "normal_min": 36.0,
        "normal_max": 37.5,
        "critical_min": 35.0,
        "critical_max": 39.5,
    },
    "blood_pressure": {
        "name": "血壓",
        "unit": "mmHg",
        # value = 收縮壓, value2 = 舒張壓
        "normal_min": 90,   # 收縮壓下限
        "normal_max": 140,  # 收縮壓上限
        "normal_min2": 60,  # 舒張壓下限
        "normal_max2": 90,  # 舒張壓上限
        "critical_min": 70,
        "critical_max": 180,
        "critical_min2": 40,
        "critical_max2": 120,
    },
    "heart_rate": {
        "name": "心率",
        "unit": "bpm",
        "normal_min": 60,
        "normal_max": 100,
        "critical_min": 40,
        "critical_max": 150,
    },
    "blood_sugar": {
        "name": "血糖",
        "unit": "mg/dL",
        # context: fasting / postprandial
        "normal_min": 70,
        "normal_max": 100,  # 空腹參考值
        "critical_min": 54,
        "critical_max": 250,
    },
    "spo2": {
        "name": "血氧",
        "unit": "%",
        "normal_min": 95,
        "normal_max": 100,
        "critical_min": 90,
        "critical_max": 100,
    },
    "weight": {
        "name": "體重",
        "unit": "kg",
        # 無固定正常範圍，用基線比較
    },
    "pain_score": {
        "name": "疼痛指數",
        "unit": "分",
        "normal_min": 0,
        "normal_max": 3,
        "critical_min": 0,
        "critical_max": 10,
    },
    "respiratory_rate": {
        "name": "呼吸頻率",
        "unit": "次/分",
        "normal_min": 12,
        "normal_max": 20,
        "critical_min": 8,
        "critical_max": 30,
    },
}

# 血糖的進階參考值（依 context 區分）
BLOOD_SUGAR_RANGES = {
    "fasting": {"normal_min": 70, "normal_max": 100, "name": "空腹"},
    "postprandial": {"normal_min": 70, "normal_max": 140, "name": "飯後2小時"},
    "random": {"normal_min": 70, "normal_max": 200, "name": "隨機"},
}


# ── Models ────────────────────────────────────────────────

class VitalCreate(BaseModel):
    patient_id: str
    type: str          # temperature, blood_pressure, heart_rate, ...
    value: float
    value2: float | None = None   # 血壓舒張壓
    unit: str | None = None       # 可自動帶入
    context: str | None = None    # fasting/postprandial/resting/...
    notes: str | None = None
    measured_at: str | None = None


class VitalBatchCreate(BaseModel):
    """一次記錄多項生理指標"""
    patient_id: str
    records: list[VitalCreate]


# ── 輔助函式 ─────────────────────────────────────────────────

def _check_abnormal(vital_type: str, value: float, value2: float | None = None, context: str | None = None):
    """
    判斷生理數值是否異常，回傳 alert level:
    - "normal": 正常
    - "warning": 偏高/偏低，但未達危急
    - "critical": 危急值，需立即處理
    """
    spec = VITAL_TYPES.get(vital_type)
    if not spec:
        return {"level": "normal", "message": ""}

    # 血糖依 context 使用不同參考範圍
    if vital_type == "blood_sugar" and context in BLOOD_SUGAR_RANGES:
        sugar_range = BLOOD_SUGAR_RANGES[context]
        spec = {**spec, "normal_min": sugar_range["normal_min"], "normal_max": sugar_range["normal_max"]}

    # 體重沒有固定正常範圍
    if vital_type == "weight":
        return {"level": "normal", "message": ""}

    normal_min = spec.get("normal_min")
    normal_max = spec.get("normal_max")
    critical_min = spec.get("critical_min")
    critical_max = spec.get("critical_max")

    alerts = []

    # 主數值檢查
    if critical_min is not None and value < critical_min:
        alerts.append({"level": "critical", "message": f"{spec['name']} {value}{spec.get('unit','')} 極低，請立即就醫"})
    elif critical_max is not None and value > critical_max:
        alerts.append({"level": "critical", "message": f"{spec['name']} {value}{spec.get('unit','')} 極高，請立即就醫"})
    elif normal_min is not None and value < normal_min:
        alerts.append({"level": "warning", "message": f"{spec['name']} {value}{spec.get('unit','')} 偏低"})
    elif normal_max is not None and value > normal_max:
        alerts.append({"level": "warning", "message": f"{spec['name']} {value}{spec.get('unit','')} 偏高"})

    # 血壓舒張壓額外檢查
    if vital_type == "blood_pressure" and value2 is not None:
        c_min2 = spec.get("critical_min2")
        c_max2 = spec.get("critical_max2")
        n_min2 = spec.get("normal_min2")
        n_max2 = spec.get("normal_max2")
        if c_min2 is not None and value2 < c_min2:
            alerts.append({"level": "critical", "message": f"舒張壓 {value2}mmHg 極低，請立即就醫"})
        elif c_max2 is not None and value2 > c_max2:
            alerts.append({"level": "critical", "message": f"舒張壓 {value2}mmHg 極高，請立即就醫"})
        elif n_min2 is not None and value2 < n_min2:
            alerts.append({"level": "warning", "message": f"舒張壓 {value2}mmHg 偏低"})
        elif n_max2 is not None and value2 > n_max2:
            alerts.append({"level": "warning", "message": f"舒張壓 {value2}mmHg 偏高"})

    if not alerts:
        return {"level": "normal", "message": ""}

    # 取最嚴重的
    has_critical = any(a["level"] == "critical" for a in alerts)
    level = "critical" if has_critical else "warning"
    messages = [a["message"] for a in alerts]
    return {"level": level, "message": "；".join(messages)}


def _format_vital_display(record: dict) -> str:
    """格式化生理數值的顯示文字"""
    vtype = record.get("type", "")
    value = record.get("value")
    value2 = record.get("value2")
    spec = VITAL_TYPES.get(vtype, {})
    unit = record.get("unit") or spec.get("unit", "")

    if vtype == "blood_pressure" and value2 is not None:
        return f"{int(value)}/{int(value2)} {unit}"
    elif vtype in ("temperature",):
        return f"{value} {unit}"
    elif vtype in ("spo2",):
        return f"{value}%"
    else:
        return f"{value} {unit}" if unit else str(value)


# ── CRUD ─────────────────────────────────────────────────────

@router.get("/types")
def get_vital_types():
    """取得所有支援的生理指標類型及參考值"""
    return {"types": VITAL_TYPES, "blood_sugar_ranges": BLOOD_SUGAR_RANGES}


@router.post("/")
def create_vital(body: VitalCreate):
    """記錄一筆生理數值"""
    if body.type not in VITAL_TYPES:
        raise HTTPException(status_code=400, detail=f"不支援的生理指標類型：{body.type}，支援：{', '.join(VITAL_TYPES.keys())}")

    if body.type == "blood_pressure" and body.value2 is None:
        raise HTTPException(status_code=400, detail="血壓需同時提供收縮壓 (value) 與舒張壓 (value2)")

    spec = VITAL_TYPES[body.type]
    unit = body.unit or spec.get("unit", "")

    # 異常值檢查
    alert = _check_abnormal(body.type, body.value, body.value2, body.context)

    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "type": body.type,
        "value": body.value,
        "value2": body.value2,
        "unit": unit,
        "context": body.context,
        "notes": body.notes,
        "measured_at": body.measured_at or datetime.utcnow().isoformat(),
    }
    result = sb.table("vitals").insert(data).execute()
    record = result.data[0]
    record["alert"] = alert
    record["display"] = _format_vital_display(record)
    return record


@router.post("/batch")
def create_vitals_batch(body: VitalBatchCreate):
    """一次記錄多項生理指標（例如量血壓同時記體溫）"""
    results = []
    alerts = []
    for rec in body.records:
        rec.patient_id = body.patient_id
        try:
            saved = create_vital(rec)
            results.append(saved)
            if saved.get("alert", {}).get("level") != "normal":
                alerts.append(saved["alert"])
        except HTTPException as e:
            results.append({"error": e.detail, "type": rec.type})

    return {
        "saved": len([r for r in results if "error" not in r]),
        "errors": len([r for r in results if "error" in r]),
        "records": results,
        "alerts": alerts,
    }


@router.get("/")
def get_vitals(
    patient_id: str = Query(...),
    vital_type: Optional[str] = Query(None, alias="type", description="篩選指標類型"),
    days: int = Query(30, description="查詢最近幾天"),
):
    """取得病患的生理紀錄"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    query = sb.table("vitals").select("*").eq("patient_id", patient_id).gte("measured_at", since).order("measured_at", desc=True)
    if vital_type:
        query = query.eq("type", vital_type)
    result = query.execute()

    records = result.data or []
    for r in records:
        r["display"] = _format_vital_display(r)

    return {"vitals": records, "count": len(records), "days": days}


@router.get("/latest")
def get_latest_vitals(patient_id: str = Query(...)):
    """
    取得每種生理指標的最新一筆，組成「生理看板」。
    用於首頁 dashboard 顯示。
    """
    sb = get_supabase()
    # 取最近 30 天的所有紀錄，然後分組取最新
    since = (datetime.utcnow() - timedelta(days=30)).isoformat()
    result = sb.table("vitals").select("*").eq("patient_id", patient_id).gte("measured_at", since).order("measured_at", desc=True).execute()
    records = result.data or []

    latest = {}
    for r in records:
        vtype = r.get("type")
        if vtype and vtype not in latest:
            alert = _check_abnormal(vtype, r.get("value", 0), r.get("value2"), r.get("context"))
            r["alert"] = alert
            r["display"] = _format_vital_display(r)
            r["type_name"] = VITAL_TYPES.get(vtype, {}).get("name", vtype)
            latest[vtype] = r

    return {"latest": latest, "types_recorded": list(latest.keys())}


@router.delete("/{vital_id}")
def delete_vital(vital_id: str):
    """刪除一筆生理紀錄"""
    sb = get_supabase()
    result = sb.table("vitals").delete().eq("id", vital_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該筆紀錄")
    return {"message": "已刪除", "id": vital_id}


# ── 趨勢與統計 ──────────────────────────────────────────────

@router.get("/trend")
def get_vital_trend(
    patient_id: str = Query(...),
    vital_type: str = Query(..., alias="type"),
    days: int = Query(30),
):
    """取得單項生理指標的趨勢資料（用於折線圖）"""
    if vital_type not in VITAL_TYPES:
        raise HTTPException(status_code=400, detail=f"不支援的類型：{vital_type}")

    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = sb.table("vitals").select("*").eq("patient_id", patient_id).eq("type", vital_type).gte("measured_at", since).order("measured_at").execute()
    records = result.data or []

    spec = VITAL_TYPES[vital_type]
    values = [r.get("value", 0) for r in records]

    trend = []
    for r in records:
        point = {
            "date": r.get("measured_at", "")[:10],
            "time": r.get("measured_at", "")[11:16],
            "value": r.get("value"),
            "display": _format_vital_display(r),
            "context": r.get("context"),
        }
        if vital_type == "blood_pressure":
            point["value2"] = r.get("value2")
        trend.append(point)

    stats = {}
    if values:
        stats = {
            "min": min(values),
            "max": max(values),
            "avg": round(sum(values) / len(values), 1),
            "count": len(values),
        }
        if vital_type == "blood_pressure":
            values2 = [r.get("value2", 0) for r in records if r.get("value2") is not None]
            if values2:
                stats["min2"] = min(values2)
                stats["max2"] = max(values2)
                stats["avg2"] = round(sum(values2) / len(values2), 1)

    return {
        "type": vital_type,
        "type_name": spec.get("name", vital_type),
        "unit": spec.get("unit", ""),
        "reference": {
            "normal_min": spec.get("normal_min"),
            "normal_max": spec.get("normal_max"),
        },
        "trend": trend,
        "stats": stats,
        "days": days,
    }


@router.get("/stats")
def get_vitals_summary(
    patient_id: str = Query(...),
    days: int = Query(30),
):
    """
    取得所有生理指標的統計摘要，用於整體健康報告。
    """
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = sb.table("vitals").select("*").eq("patient_id", patient_id).gte("measured_at", since).order("measured_at").execute()
    records = result.data or []

    # 按 type 分組
    grouped = {}
    for r in records:
        vtype = r.get("type")
        if vtype not in grouped:
            grouped[vtype] = []
        grouped[vtype].append(r)

    summary = {}
    total_alerts = {"warning": 0, "critical": 0}

    for vtype, recs in grouped.items():
        spec = VITAL_TYPES.get(vtype, {})
        values = [r.get("value", 0) for r in recs]

        type_summary = {
            "type_name": spec.get("name", vtype),
            "unit": spec.get("unit", ""),
            "count": len(recs),
            "min": min(values),
            "max": max(values),
            "avg": round(sum(values) / len(values), 1),
            "latest": _format_vital_display(recs[-1]),
            "latest_at": recs[-1].get("measured_at"),
        }

        # 異常次數統計
        abnormal_count = 0
        for r in recs:
            alert = _check_abnormal(vtype, r.get("value", 0), r.get("value2"), r.get("context"))
            if alert["level"] != "normal":
                abnormal_count += 1
                total_alerts[alert["level"]] = total_alerts.get(alert["level"], 0) + 1
        type_summary["abnormal_count"] = abnormal_count

        if vtype == "blood_pressure":
            values2 = [r.get("value2", 0) for r in recs if r.get("value2") is not None]
            if values2:
                type_summary["avg2"] = round(sum(values2) / len(values2), 1)

        summary[vtype] = type_summary

    return {
        "summary": summary,
        "total_records": len(records),
        "total_alerts": total_alerts,
        "days": days,
    }


# ── 異常值警示 ──────────────────────────────────────────────

@router.get("/alerts")
def get_vital_alerts(
    patient_id: str = Query(...),
    days: int = Query(7, description="檢查最近幾天"),
):
    """
    掃描最近的生理紀錄，列出所有異常值。
    用於推送通知或回診提醒。
    """
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = sb.table("vitals").select("*").eq("patient_id", patient_id).gte("measured_at", since).order("measured_at", desc=True).execute()
    records = result.data or []

    alerts = []
    for r in records:
        vtype = r.get("type", "")
        alert = _check_abnormal(vtype, r.get("value", 0), r.get("value2"), r.get("context"))
        if alert["level"] != "normal":
            spec = VITAL_TYPES.get(vtype, {})
            alerts.append({
                "id": r.get("id"),
                "type": vtype,
                "type_name": spec.get("name", vtype),
                "display": _format_vital_display(r),
                "measured_at": r.get("measured_at"),
                "level": alert["level"],
                "message": alert["message"],
            })

    return {
        "alerts": alerts,
        "warning_count": sum(1 for a in alerts if a["level"] == "warning"),
        "critical_count": sum(1 for a in alerts if a["level"] == "critical"),
        "days": days,
    }
