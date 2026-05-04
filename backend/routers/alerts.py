import os
from fastapi import APIRouter, Header, HTTPException
from datetime import datetime, timedelta, timezone
from backend.db import get_supabase
from backend.models import AlertCreate, AlertUpdate

router = APIRouter()

VALID_TYPES = {
    "er_visit", "missed_medication", "self_discontinued",
    "infection", "low_mood", "psych_crisis", "other",
}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
CHECKIN_INTERVAL_DAYS = 3


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


@router.post("/scan-checkins")
def scan_checkins(
    interval_days: int = CHECKIN_INTERVAL_DAYS,
    x_cron_token: str | None = Header(default=None, alias="X-Cron-Token"),
):
    """
    排程入口：掃描所有有開立藥物的病患，把超過 interval_days 沒任何 medication_logs/effects
    的人寫入 alerts（type=missed_medication, severity=medium）。
    為避免重覆寫入，同一病患若已有 24 小時內未 resolve 的 missed_medication alert 則跳過。

    若設了環境變數 CRON_TOKEN，呼叫時須帶 X-Cron-Token header。
    回傳掃描統計與本次新建的 alert 數。
    """
    expected = os.getenv("CRON_TOKEN")
    if expected and x_cron_token != expected:
        raise HTTPException(status_code=401, detail="invalid cron token")
    if interval_days < 1 or interval_days > 30:
        raise HTTPException(status_code=400, detail="interval_days 必須在 1-30 之間")

    sb = get_supabase()
    now = datetime.now(timezone.utc)
    threshold_iso = (now - timedelta(days=interval_days)).isoformat()
    dedupe_iso = (now - timedelta(hours=24)).isoformat()

    meds = sb.table("medications").select("patient_id, active").execute().data or []
    patient_ids = sorted({m["patient_id"] for m in meds if m.get("active", 1) and m.get("patient_id")})

    created = []
    skipped_recent_alert = 0
    not_due = 0

    for pid in patient_ids:
        last_log = (
            sb.table("medication_logs").select("taken_at").eq("patient_id", pid)
            .order("taken_at", desc=True).limit(1).execute().data or []
        )
        last_eff = (
            sb.table("medication_effects").select("recorded_at").eq("patient_id", pid)
            .order("recorded_at", desc=True).limit(1).execute().data or []
        )
        candidates = []
        if last_log:
            candidates.append(last_log[0].get("taken_at"))
        if last_eff:
            candidates.append(last_eff[0].get("recorded_at"))
        candidates = [c for c in candidates if c]
        last_iso = max(candidates) if candidates else None

        if last_iso and last_iso > threshold_iso:
            not_due += 1
            continue

        existing = (
            sb.table("alerts").select("id, created_at, resolved")
            .eq("patient_id", pid).eq("alert_type", "missed_medication")
            .gte("created_at", dedupe_iso).execute().data or []
        )
        if any(not a.get("resolved") for a in existing):
            skipped_recent_alert += 1
            continue

        days_since = "未曾回報"
        if last_iso:
            try:
                last_dt = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
                days_since = f"{round((now - last_dt).total_seconds() / 86400, 1)} 天"
            except ValueError:
                pass

        alert = {
            "patient_id": pid,
            "alert_type": "missed_medication",
            "severity": "medium",
            "title": f"超過 {interval_days} 天未回報服藥",
            "detail": f"距離上次服藥/療效紀錄已 {days_since}，建議主動關懷。",
            "source": "cron:scan-checkins",
        }
        try:
            inserted = sb.table("alerts").insert(alert).execute().data
            if inserted:
                created.append(inserted[0])
        except Exception:
            continue

    return {
        "scanned_patients": len(patient_ids),
        "created_alerts": len(created),
        "skipped_recent_alert": skipped_recent_alert,
        "not_due": not_due,
        "interval_days": interval_days,
        "ran_at": now.isoformat(),
    }
