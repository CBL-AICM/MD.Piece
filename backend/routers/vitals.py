"""
生理數據與檢驗數值
- 病患端：血壓、血糖、體重等日常記錄
- 醫師端：檢驗數值上傳 + 患者白話翻譯（不顯示原始數字）
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.utils.lab_translator import LAB_REFERENCE, translate_value

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 資料模型 ──────────────────────────────────────────────


class VitalCreate(BaseModel):
    patient_id: str
    code: str  # BP_systolic / BP_diastolic / FBS / weight ...
    value: float
    note: str | None = None
    measured_at: str | None = None


class LabValueCreate(BaseModel):
    patient_id: str
    code: str  # CRP / HbA1c / LDL ...
    value: float
    measured_at: str | None = None
    source: str = "doctor_input"  # doctor_input / patient_input / hospital_sync


# ── Schema 自我建表（避免靠額外的 migration） ────────────


def _ensure_table(sb):
    try:
        from backend.db import _get_conn
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vitals (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                code TEXT NOT NULL,
                value REAL,
                note TEXT,
                measured_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lab_values (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                code TEXT NOT NULL,
                value REAL,
                measured_at TEXT,
                source TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"_ensure_table skipped (likely Supabase): {e}")


# ── 病患端：日常生理記錄 ─────────────────────────────────


@router.post("/")
def log_vital(body: VitalCreate):
    """病患記錄一筆生理數據（血壓、血糖、體重…）"""
    sb = get_supabase()
    _ensure_table(sb)
    data = body.model_dump(exclude_none=True)
    data["measured_at"] = data.get("measured_at") or datetime.now(timezone.utc).isoformat()
    result = sb.table("vitals").insert(data).execute()
    return result.data[0] if result.data else data


@router.get("/")
def list_vitals(patient_id: str = Query(...), code: str | None = None, days: int = 30):
    sb = get_supabase()
    _ensure_table(sb)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = sb.table("vitals").select("*").eq("patient_id", patient_id).gte("measured_at", since).order("measured_at", desc=True)
    if code:
        q = q.eq("code", code)
    return {"vitals": q.execute().data or []}


# ── 醫師端：檢驗數值上傳 + 患者白話翻譯 ─────────────────


@router.post("/lab")
def upload_lab_value(body: LabValueCreate):
    sb = get_supabase()
    _ensure_table(sb)
    data = body.model_dump(exclude_none=True)
    data["measured_at"] = data.get("measured_at") or datetime.now(timezone.utc).isoformat()
    result = sb.table("lab_values").insert(data).execute()
    return result.data[0] if result.data else data


@router.get("/lab/{patient_id}")
def list_lab_values(patient_id: str, code: str | None = None):
    sb = get_supabase()
    _ensure_table(sb)
    q = sb.table("lab_values").select("*").eq("patient_id", patient_id).order("measured_at", desc=True)
    if code:
        q = q.eq("code", code)
    return {"lab_values": q.execute().data or []}


@router.get("/lab/{patient_id}/translated")
def get_translated_labs(patient_id: str):
    """
    病患端用：檢驗數值的白話翻譯。
    一律不回傳原始數字，只回傳「level + 訊息」。
    """
    sb = get_supabase()
    _ensure_table(sb)
    rows = (
        sb.table("lab_values")
        .select("*")
        .eq("patient_id", patient_id)
        .order("measured_at", desc=True)
        .execute()
        .data
        or []
    )

    by_code: dict[str, list[dict]] = {}
    for r in rows:
        by_code.setdefault(r["code"], []).append(r)

    translated = []
    for code, items in by_code.items():
        items.sort(key=lambda x: x.get("measured_at", ""), reverse=True)
        latest = items[0]
        prev = items[1]["value"] if len(items) > 1 else None
        translation = translate_value(code, latest["value"], prev)
        translated.append({
            "code": code,
            "measured_at": latest.get("measured_at"),
            **translation,
        })

    # 依類別歸檔，方便前端顯示
    by_category: dict[str, list[dict]] = {}
    for t in translated:
        by_category.setdefault(t.get("category", "其他"), []).append(t)

    return {
        "patient_id": patient_id,
        "translated": translated,
        "by_category": by_category,
        "reassurance": "這些指標醫師都已經看過了，會在下次回診時跟你說明",
    }


@router.get("/lab-codes")
def list_lab_codes():
    """列出所有支援白話翻譯的檢驗項目"""
    return {
        "codes": [
            {"code": k, **{kk: vv for kk, vv in v.items() if kk != "normal_max" and kk != "normal_min"}}
            for k, v in LAB_REFERENCE.items()
        ]
    }


# ── 直接翻譯（不存資料庫，給臨時試算用）────────────────


class TranslateRequest(BaseModel):
    code: str
    value: float
    previous: float | None = None


@router.post("/translate")
def translate_one(body: TranslateRequest):
    return translate_value(body.code, body.value, body.previous)
