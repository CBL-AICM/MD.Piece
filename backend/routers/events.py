"""
App 事件日誌（app_events）— codebook v3「使用行為 / 遺失與錯誤事件」的 TEL 收集與聚合。

定位：通用事件日誌（一列一事件），前端埋點透過 `POST /events` 批次代寫（後端 service_role），
後端再以**純程式碼**把事件聚合成 codebook 的衍生變項（規則 5：聚合是確定性任務，不丟 LLM）。
資料表見 docs/migration_app_events.sql；事件目錄見 docs/research/app_events_schema.md。

事件流：
  1. POST /events           批次寫入事件（限登入；user_id 由 token 決定，不信前端帶的身份）
  2. GET  /events/agg       聚合成使用行為 / 錯誤事件衍生變項（本人或 doctor）

設計鐵則：
  - 規則 5：聚合（streak / 完成率 / 錯誤數）純程式碼。
  - 規則 12：型別不合法明確 400；寫入失敗 loud-fail，不靜默吞。
  - 隱私：身份一律取自 token；metadata 不存原始作答 / 姓名（由前端負責去識別化）。
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.security import current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# 允許的事件大類（與 app_events_schema.md 目錄一致）。
# visit：臨床里程碑（如「回診結束」visit/completed），供 EMA event 規則延遲推 post-visit 問卷。
_EVENT_TYPES = {"session", "screen", "feature", "reminder", "error", "crash",
                "api", "data", "edit", "push", "visit"}
_MAX_BATCH = 200


# ── Models ────────────────────────────────────────────────

class EventIn(BaseModel):
    event_type: str
    event_name: Optional[str] = None
    target: Optional[str] = None
    value: Optional[float] = None
    metadata: Optional[dict] = None
    occurred_at: Optional[str] = None   # 前端帶事件實際發生時間（ISO）；支援離線補送
    session_id: Optional[str] = None


class EventBatch(BaseModel):
    events: list[EventIn]


# ── Endpoints ─────────────────────────────────────────────

@router.post("")
def ingest_events(body: EventBatch, me: dict = Depends(current_user)):
    """批次寫入事件（限登入）。user_id 取自 token，忽略前端任何身份欄位（防越權）。"""
    events = body.events or []
    if not events:
        raise HTTPException(status_code=400, detail="events 需為非空陣列")
    if len(events) > _MAX_BATCH:
        raise HTTPException(status_code=400, detail=f"單批最多 {_MAX_BATCH} 筆")
    for e in events:
        if e.event_type not in _EVENT_TYPES:
            raise HTTPException(status_code=400, detail=f"event_type 需為 {_EVENT_TYPES}")

    sb = get_supabase()
    rows = [{
        "user_id": me.get("id"),
        "session_id": e.session_id,
        "event_type": e.event_type,
        "event_name": e.event_name,
        "target": e.target,
        "value": e.value,
        "metadata": e.metadata,
        "occurred_at": (e.occurred_at or "").strip() or None,
    } for e in events]

    saved = 0
    try:
        for row in rows:                 # 逐筆 insert（相容 SQLite shim 與 PostgREST shim）
            sb.table("app_events").insert(row).execute()
            saved += 1
    except Exception as ex:
        logger.error(f"ingest_events failed after {saved}/{len(rows)}: {ex}")
        # 規則 12：部分成功也要 loud，回報實際寫入數，不假裝全成功。
        raise HTTPException(status_code=400, detail=f"事件寫入失敗（已寫 {saved}/{len(rows)} 筆）：{ex}")

    return {"ingested": saved, "_persisted": True}


# ── 聚合（純程式碼；規則 5）──────────────────────────────────

def _day(s) -> Optional[str]:
    return str(s)[:10] if s else None


def _streaks(dates: list) -> tuple:
    """回傳 (最長連續天數, 目前連續天數)。dates 為已排序的 date 物件。"""
    longest = cur = 0
    prev = None
    for d in dates:
        cur = cur + 1 if (prev is not None and (d - prev).days == 1) else 1
        longest = max(longest, cur)
        prev = d
    return longest, cur


# 系統推送、非使用者主動操作的事件 — 不計入「活躍天數 / 連續天數」（規則 9：活躍＝使用者有用）。
_SYSTEM_EVENTS = {("reminder", "sent"), ("push", "received"), ("push", "sent")}


def _aggregate(rows: list) -> dict:
    """把 app_events 列聚合成 codebook 使用行為 / 錯誤事件衍生變項。"""
    def has(t, n=None):
        return [r for r in rows if r.get("event_type") == t and (n is None or r.get("event_name") == n)]

    # 時間戳優先用 occurred_at，缺則 created_at
    def ts(r):
        return r.get("occurred_at") or r.get("created_at") or ""

    # 活躍天數只算「使用者主動」事件，排除系統推送（reminder:sent / push:received）。
    day_set = {_day(ts(r)) for r in rows
               if (r.get("event_type"), r.get("event_name")) not in _SYSTEM_EVENTS}
    day_set.discard(None)
    parsed = []
    for d in sorted(day_set):
        try:
            parsed.append(datetime.strptime(d, "%Y-%m-%d").date())
        except ValueError:
            pass
    longest, current = _streaks(parsed)
    span = (parsed[-1] - parsed[0]).days + 1 if parsed else 0

    sessions = has("session", "start")
    reminders_sent = len(has("reminder", "sent"))
    reminders_resp = len(has("reminder", "responded"))
    push_recv = len(has("push", "received"))
    push_open = len(has("push", "opened"))
    session_secs = sum(r["value"] for r in rows
                       if r.get("event_type") == "session"
                       and r.get("event_name") in ("end", "duration")
                       and isinstance(r.get("value"), (int, float)))
    feature_targets = {r.get("target") for r in rows
                       if r.get("event_type") in ("feature", "screen") and r.get("target")}

    return {
        "usage": {
            "total_events": len(rows),
            "total_sessions": len(sessions),
            "total_active_days": len(parsed),
            "span_days": span,
            "active_days_rate": round(len(parsed) / span, 3) if span else None,
            "longest_streak_days": longest,
            "current_streak_days": current,
            "total_time_in_app_min": round(session_secs / 60, 1) if session_secs else 0,
            "feature_breadth_used": len(feature_targets),
            "screen_views": len(has("screen")),
            "feature_uses": len(has("feature")),
            "reminder_response_rate": round(reminders_resp / reminders_sent, 3) if reminders_sent else None,
            "push_received_count": push_recv,
            "push_opened_count": push_open,
        },
        "errors": {
            "app_crash_count": len(has("crash")),
            "app_error_count": len(has("error")),
            "api_request_failures": len(has("api", "failure")),
            "sync_failure_count": len(has("api", "sync_failure")),
            "session_timeout_count": len(has("session", "timeout")),
            "login_failure_count": len(has("session", "login_fail")),
            "offline_event_count": len(has("session", "offline")),
            "correction_edit_count": len(has("edit", "correction")),
        },
    }


@router.get("/agg")
def events_aggregate(
    patient_id: Optional[str] = Query(None, description="預設為自己；doctor 可查他人"),
    me: dict = Depends(current_user),
):
    """聚合使用行為 / 錯誤事件衍生變項（本人或 doctor）。只回聚合，不回個別事件。"""
    pid = patient_id or me.get("id")
    if me.get("id") != pid and me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="只能檢視自己的事件聚合")
    sb = get_supabase()
    try:
        rows = sb.table("app_events").select("*").eq("user_id", pid).execute().data or []
    except Exception as ex:
        logger.info(f"events agg fetch failed: {ex}")
        rows = []
    agg = _aggregate(rows)
    return {"patient_id": pid, "event_count": len(rows), **agg}
