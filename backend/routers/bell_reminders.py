"""
鈴聲提醒擴充：
- /bell-prefs                       — 每位病患針對每種提醒類型的鈴聲偏好
- /bell-sounds                      — 病患自訂上傳鈴聲的 metadata（音檔本身存 Supabase Storage）
- /measurement-requests             — 醫師主動要求病患量測（血壓 / 血糖 等）

設計理由：
- bell prefs 拆成獨立 router，不污染既有 reminders.py。
- measurement_requests 對應「醫師端按鈕 → 立即推送 → 病患量完回填」整段流程；
  收到請求時會同步建立一筆 once-shot reminder，讓既有 /reminders/dispatch 機制把
  Web Push + inbox 一起處理掉，不必另寫派發邏輯。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.db import _SCHEMAS, get_supabase
from backend.models import (
    BellPrefUpsert,
    BellSoundCreate,
    MeasurementRequestComplete,
    MeasurementRequestCreate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── SQLite fallback schema ────────────────────────────────

_SCHEMAS.setdefault(
    "patient_bell_prefs",
    """
        CREATE TABLE IF NOT EXISTS patient_bell_prefs (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            bell_sound TEXT NOT NULL DEFAULT 'gentle',
            volume INTEGER NOT NULL DEFAULT 70,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(patient_id, kind)
        )""",
)

_SCHEMAS.setdefault(
    "measurement_requests",
    """
        CREATE TABLE IF NOT EXISTS measurement_requests (
            id TEXT PRIMARY KEY,
            doctor_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            measure_type TEXT NOT NULL,
            note TEXT,
            requested_at TEXT NOT NULL,
            due_by TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            result_value TEXT,
            result_recorded_at TEXT,
            reminder_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
)

_SCHEMAS.setdefault(
    "bell_sounds",
    """
        CREATE TABLE IF NOT EXISTS bell_sounds (
            id TEXT PRIMARY KEY,
            owner_patient_id TEXT NOT NULL,
            name TEXT NOT NULL,
            file_url TEXT NOT NULL,
            duration_sec REAL,
            file_size_bytes INTEGER,
            mime_type TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
)

VALID_KINDS = {
    "medication", "appointment", "lab", "measurement", "doctor_request", "custom",
}
VALID_MEASURE_TYPES = {"bp", "glucose", "heart_rate", "weight", "temperature"}
VALID_STATUSES = {"pending", "done", "expired", "cancelled"}

# 預設合成鈴聲 id（由前端 bell.js 用 Web Audio 合成；後端只儲存 id 字串）
PRESET_BELL_IDS = {"gentle", "chime", "alert", "soft", "urgent"}

MEASURE_TYPE_LABELS = {
    "bp": "血壓",
    "glucose": "血糖",
    "heart_rate": "心率",
    "weight": "體重",
    "temperature": "體溫",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ─── Bell preferences ─────────────────────────────────────

@router.get("/bell-prefs")
def list_bell_prefs(patient_id: str = Query(...)):
    """列出該病患所有鈴聲偏好；缺項由前端用預設值補。"""
    sb = get_supabase()
    rows = (
        sb.table("patient_bell_prefs")
        .select("*")
        .eq("patient_id", patient_id)
        .execute()
        .data
    ) or []
    for r in rows:
        if isinstance(r.get("enabled"), int):
            r["enabled"] = bool(r["enabled"])
    return {"prefs": rows}


@router.put("/bell-prefs")
def upsert_bell_pref(body: BellPrefUpsert):
    if body.kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"kind 無效，需為 {VALID_KINDS}")
    if not (0 <= body.volume <= 100):
        raise HTTPException(status_code=400, detail="volume 必須在 0–100 之間")

    sb = get_supabase()
    payload = {
        "patient_id": body.patient_id,
        "kind": body.kind,
        "bell_sound": body.bell_sound or "gentle",
        "volume": body.volume,
        "enabled": 1 if body.enabled else 0,
        "updated_at": _now_iso(),
    }
    existing = (
        sb.table("patient_bell_prefs")
        .select("id")
        .eq("patient_id", body.patient_id)
        .eq("kind", body.kind)
        .execute()
        .data
    )
    if existing:
        sb.table("patient_bell_prefs").update(payload).eq("id", existing[0]["id"]).execute()
        return {"updated": True, "id": existing[0]["id"]}
    result = sb.table("patient_bell_prefs").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="寫入偏好失敗")
    return {"created": True, "id": result.data[0].get("id")}


# ─── Custom bell sound metadata ───────────────────────────

@router.get("/bell-sounds")
def list_bell_sounds(patient_id: str = Query(...)):
    sb = get_supabase()
    rows = (
        sb.table("bell_sounds")
        .select("*")
        .eq("owner_patient_id", patient_id)
        .order("created_at", desc=True)
        .execute()
        .data
    ) or []
    return {"sounds": rows, "presets": sorted(PRESET_BELL_IDS)}


@router.post("/bell-sounds")
def create_bell_sound(body: BellSoundCreate):
    if body.duration_sec is not None and body.duration_sec > 10:
        raise HTTPException(status_code=400, detail="鈴聲長度不可超過 10 秒")
    if body.file_size_bytes is not None and body.file_size_bytes > 512 * 1024:
        raise HTTPException(status_code=400, detail="鈴聲檔案不可超過 512KB")
    sb = get_supabase()
    payload = body.model_dump()
    result = sb.table("bell_sounds").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="鈴聲寫入失敗")
    return result.data[0]


@router.delete("/bell-sounds/{sound_id}")
def delete_bell_sound(sound_id: str):
    sb = get_supabase()
    result = sb.table("bell_sounds").delete().eq("id", sound_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到鈴聲")
    return {"deleted": True, "id": sound_id}


# ─── Measurement requests（醫師端要件測） ───────────────────

def _create_reminder_for_request(sb, req_row):
    """為一筆 measurement_request 同步建立 once-shot reminder，讓 dispatch 機制把
    Web Push + inbox 一次處理掉。回傳 reminder_id。"""
    measure_label = MEASURE_TYPE_LABELS.get(req_row["measure_type"], req_row["measure_type"])
    title = f"醫師請您量{measure_label}"
    body_lines = [f"醫師希望您現在量一下{measure_label}。"]
    if req_row.get("note"):
        body_lines.append(req_row["note"])
    reminder_payload = {
        "patient_id": req_row["patient_id"],
        "reminder_type": "measurement",
        "title": title,
        "body": "\n".join(body_lines),
        "source_id": req_row["id"],
        "url": f"/?page=measurement&type={req_row['measure_type']}&request={req_row['id']}",
        "frequency": "once",
        "scheduled_at": req_row["requested_at"],
        "next_fire_at": req_row["requested_at"],
        "active": 1,
        "priority": "high",
        "source": "doctor",
    }
    result = sb.table("reminders").insert(reminder_payload).execute()
    if not result.data:
        return None
    return result.data[0].get("id")


@router.post("/measurement-requests")
def create_measurement_request(body: MeasurementRequestCreate):
    if body.measure_type not in VALID_MEASURE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"measure_type 無效，需為 {sorted(VALID_MEASURE_TYPES)}",
        )

    now = datetime.now(timezone.utc)
    due_by = None
    if body.due_in_minutes:
        if body.due_in_minutes <= 0 or body.due_in_minutes > 60 * 24:
            raise HTTPException(status_code=400, detail="due_in_minutes 需介於 1–1440")
        due_by = (now + timedelta(minutes=body.due_in_minutes)).isoformat()

    sb = get_supabase()
    req_payload = {
        "doctor_id": body.doctor_id,
        "patient_id": body.patient_id,
        "measure_type": body.measure_type,
        "note": body.note,
        "requested_at": now.isoformat(),
        "due_by": due_by,
        "status": "pending",
    }
    result = sb.table("measurement_requests").insert(req_payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="建立要件測請求失敗")
    row = result.data[0]

    reminder_id = _create_reminder_for_request(sb, row)
    if reminder_id:
        try:
            sb.table("measurement_requests").update({"reminder_id": reminder_id}) \
                .eq("id", row["id"]).execute()
            row["reminder_id"] = reminder_id
        except Exception as exc:
            logger.warning("link reminder failed: %s", type(exc).__name__)

    # 立刻派發一次（讓病患馬上收到 push，不必等下一輪 cron）
    try:
        from backend.routers.reminders import dispatch_due_reminders  # noqa: WPS433
        dispatch_due_reminders(patient_id=body.patient_id, limit=10, x_cron_token=None)
    except Exception as exc:
        logger.warning("immediate dispatch failed: %s", type(exc).__name__)

    return row


@router.get("/measurement-requests")
def list_measurement_requests(
    patient_id: str | None = Query(default=None),
    doctor_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = 50,
):
    if not patient_id and not doctor_id:
        raise HTTPException(status_code=400, detail="須指定 patient_id 或 doctor_id")
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status 無效，需為 {VALID_STATUSES}")

    sb = get_supabase()
    q = sb.table("measurement_requests").select("*")
    if patient_id:
        q = q.eq("patient_id", patient_id)
    if doctor_id:
        q = q.eq("doctor_id", doctor_id)
    if status:
        q = q.eq("status", status)
    rows = q.order("requested_at", desc=True).limit(min(limit, 200)).execute().data or []
    return {"items": rows}


@router.put("/measurement-requests/{req_id}/complete")
def complete_measurement_request(req_id: str, body: MeasurementRequestComplete):
    sb = get_supabase()
    existing = sb.table("measurement_requests").select("*").eq("id", req_id).execute().data
    if not existing:
        raise HTTPException(status_code=404, detail="找不到請求")
    if existing[0].get("status") not in (None, "pending"):
        raise HTTPException(status_code=400, detail="此請求已處理過")

    now_iso = _now_iso()
    updates = {
        "status": "done",
        "result_value": body.result_value,
        "result_recorded_at": now_iso,
        "updated_at": now_iso,
    }
    sb.table("measurement_requests").update(updates).eq("id", req_id).execute()

    # 病患量完後，發一筆站內通知給醫師
    row = existing[0]
    label = MEASURE_TYPE_LABELS.get(row["measure_type"], row["measure_type"])
    try:
        sb.table("notification_inbox").insert({
            "patient_id": row["doctor_id"],  # 借用 inbox 同表，patient_id 欄位這裡擺醫師 id
            "reminder_id": row.get("reminder_id"),
            "title": f"病患已回報{label}",
            "body": body.result_value or "（無數值，僅回報完成）",
            "url": f"/?page=patients&pid={row['patient_id']}",
            "reminder_type": "doctor_request",
            "delivered_via": "inbox",
        }).execute()
    except Exception as exc:
        logger.warning("doctor inbox notify failed: %s", type(exc).__name__)

    return {"ok": True, "id": req_id, "status": "done"}


@router.delete("/measurement-requests/{req_id}")
def cancel_measurement_request(req_id: str):
    sb = get_supabase()
    sb.table("measurement_requests").update({
        "status": "cancelled",
        "updated_at": _now_iso(),
    }).eq("id", req_id).execute()
    return {"ok": True, "id": req_id, "status": "cancelled"}
