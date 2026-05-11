"""
提醒（reminders）+ Web Push + 站內通知（inbox）。

設計：
- reminders 表存使用者的提醒設定（吃藥 / 回診 / 檢查 / 自訂）。
- push_subscriptions 表存裝置的 Web Push endpoint。
- notification_inbox 表存實際派發過的提醒（站內通知中心讀取來源）。
- /reminders/dispatch 為 cron 入口，掃描到期 reminders →
  寫 inbox + 發 Web Push（若有 VAPID 憑證）。
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Query

from backend.db import get_supabase
from backend.models import (
    InboxUpdate,
    PushSubscriptionCreate,
    ReminderCreate,
    ReminderUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_TYPES = {"medication", "appointment", "lab", "custom"}
VALID_FREQUENCIES = {"once", "daily", "weekly", "monthly"}

# 已知的 Web Push 供應商。endpoint 必須屬於其中之一才允許寫入，
# 避免惡意 client 註冊任意 URL 把 backend 當 SSRF gadget。
ALLOWED_PUSH_HOSTS = (
    "fcm.googleapis.com",                # Chrome / Edge / Android
    "android.googleapis.com",            # Legacy GCM (fallback)
    "updates.push.services.mozilla.com", # Firefox
    "web.push.apple.com",                # Safari (iOS 16.4+ / macOS Ventura+)
    "notify.windows.com",                # Edge legacy / Windows
    "wns2-by3p.notify.windows.com",
)

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CONTACT_EMAIL = os.getenv("VAPID_CONTACT_EMAIL", "mailto:admin@mdpiece.life")

try:
    from pywebpush import WebPushException, webpush  # type: ignore
    _webpush_available = True
except ImportError:
    _webpush_available = False
    webpush = None
    WebPushException = Exception


# ─── Helpers ───────────────────────────────────────────────

def _parse_iso(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _days_of_week_to_str(days):
    if not days:
        return None
    return json.dumps(sorted({int(d) for d in days if 0 <= int(d) <= 6}))


def _days_of_week_from_str(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _compute_next_fire(frequency, current_fire, time_of_day, days_of_week):
    """根據 frequency 與目前 next_fire_at，算出下一次該發送的 UTC 時間。
    回傳 None 代表此 reminder 不會再發（once 已發過）。
    """
    if frequency == "once":
        return None

    now = datetime.now(timezone.utc)
    base = current_fire if current_fire and current_fire > now else now

    if frequency == "daily":
        return base + timedelta(days=1)

    if frequency == "weekly":
        days = sorted(_days_of_week_from_str(days_of_week))
        if not days:
            return base + timedelta(days=7)
        candidate = base + timedelta(days=1)
        for _ in range(8):
            # Python: Mon=0..Sun=6（與我們約定一致）
            if candidate.weekday() in days:
                return candidate
            candidate += timedelta(days=1)
        return base + timedelta(days=7)

    if frequency == "monthly":
        year, month = base.year, base.month + 1
        if month > 12:
            year += 1
            month = 1
        day = min(base.day, 28)
        return base.replace(year=year, month=month, day=day)

    return None


def _normalize_reminder_row(row):
    """SQLite 透過 _deserialize_row 已會把 JSON 字串轉回 list；
    Supabase 走 REST 時則拿到 TEXT 原字串，這裡確保兩者一致。"""
    if not row:
        return row
    if "days_of_week" in row and isinstance(row["days_of_week"], str):
        row["days_of_week"] = _days_of_week_from_str(row["days_of_week"])
    if "active" in row and isinstance(row["active"], int):
        row["active"] = bool(row["active"])
    return row


# ─── Reminders CRUD ────────────────────────────────────────

@router.post("/")
def create_reminder(body: ReminderCreate):
    if body.reminder_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"reminder_type 無效，需為 {VALID_TYPES}")
    if body.frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail=f"frequency 無效，需為 {VALID_FREQUENCIES}")

    scheduled = body.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)

    data = {
        "patient_id": body.patient_id,
        "reminder_type": body.reminder_type,
        "title": body.title,
        "body": body.body,
        "source_id": body.source_id,
        "url": body.url,
        "frequency": body.frequency,
        "time_of_day": body.time_of_day,
        "days_of_week": _days_of_week_to_str(body.days_of_week),
        "scheduled_at": scheduled.isoformat(),
        "next_fire_at": scheduled.isoformat(),
        "active": 1 if body.active else 0,
    }
    sb = get_supabase()
    result = sb.table("reminders").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="建立提醒失敗")
    return _normalize_reminder_row(result.data[0])


@router.get("/")
def list_reminders(
    patient_id: str = Query(...),
    active: bool | None = None,
    reminder_type: str | None = None,
):
    sb = get_supabase()
    q = sb.table("reminders").select("*").eq("patient_id", patient_id)
    if active is not None:
        q = q.eq("active", 1 if active else 0)
    if reminder_type:
        if reminder_type not in VALID_TYPES:
            raise HTTPException(status_code=400, detail="reminder_type 無效")
        q = q.eq("reminder_type", reminder_type)
    result = q.order("next_fire_at", desc=False).execute()
    rows = [_normalize_reminder_row(r) for r in (result.data or [])]
    return {"reminders": rows}


@router.get("/{reminder_id}")
def get_reminder(reminder_id: str):
    sb = get_supabase()
    result = sb.table("reminders").select("*").eq("id", reminder_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到提醒")
    return _normalize_reminder_row(result.data[0])


@router.put("/{reminder_id}")
def update_reminder(reminder_id: str, body: ReminderUpdate):
    sb = get_supabase()
    existing = sb.table("reminders").select("*").eq("id", reminder_id).execute().data
    if not existing:
        raise HTTPException(status_code=404, detail="找不到提醒")

    updates = body.model_dump(exclude_none=True)
    if "frequency" in updates and updates["frequency"] not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="frequency 無效")
    if "days_of_week" in updates:
        updates["days_of_week"] = _days_of_week_to_str(updates["days_of_week"])
    if "scheduled_at" in updates:
        sched = updates["scheduled_at"]
        if sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)
        updates["scheduled_at"] = sched.isoformat()
        updates["next_fire_at"] = sched.isoformat()
    if "active" in updates:
        updates["active"] = 1 if updates["active"] else 0
    if not updates:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = sb.table("reminders").update(updates).eq("id", reminder_id).execute()
    return _normalize_reminder_row(result.data[0]) if result.data else {}


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: str):
    sb = get_supabase()
    # 先把 inbox 中的 reminder_id 設為 NULL，避免 FK 衝突；保留通知歷史。
    try:
        sb.table("notification_inbox").update({"reminder_id": None}).eq("reminder_id", reminder_id).execute()
    except Exception as exc:
        logger.warning("inbox detach failed: %s", type(exc).__name__)
    result = sb.table("reminders").delete().eq("id", reminder_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到提醒")
    return {"message": "已刪除", "id": reminder_id}


# ─── Push subscription ────────────────────────────────────

@router.get("/push/config")
def push_config():
    """前端訂閱 Web Push 時需要 VAPID 公鑰；若未設定回傳空字串表停用。"""
    return {
        "vapid_public_key": VAPID_PUBLIC_KEY,
        "webpush_enabled": bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY and _webpush_available),
    }


@router.post("/push/subscribe")
def push_subscribe(body: PushSubscriptionCreate):
    # 驗證 endpoint 必須是 HTTPS 且屬於已知的 Web Push 供應商（防 SSRF）。
    from urllib.parse import urlparse
    parsed = urlparse(body.endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=400, detail="endpoint 必須為 https URL")
    host = parsed.hostname.lower()
    if not any(host == h or host.endswith("." + h) for h in ALLOWED_PUSH_HOSTS):
        raise HTTPException(
            status_code=400,
            detail=f"endpoint host '{host}' 不在允許清單；目前僅接受標準 Web Push 供應商。",
        )

    sb = get_supabase()
    # 同一 endpoint 已存在則覆寫綁定的 patient_id（同裝置換帳號的情境）
    existing = sb.table("push_subscriptions").select("id").eq("endpoint", body.endpoint).execute().data
    payload = {
        "patient_id": body.patient_id,
        "endpoint": body.endpoint,
        "p256dh": body.p256dh,
        "auth": body.auth,
        "user_agent": body.user_agent,
    }
    if existing:
        sb.table("push_subscriptions").update(payload).eq("endpoint", body.endpoint).execute()
        return {"updated": True, "endpoint": body.endpoint}
    result = sb.table("push_subscriptions").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="訂閱寫入失敗")
    return {"created": True, "id": result.data[0].get("id"), "endpoint": body.endpoint}


@router.delete("/push/subscribe")
def push_unsubscribe(endpoint: str = Query(...)):
    sb = get_supabase()
    sb.table("push_subscriptions").delete().eq("endpoint", endpoint).execute()
    return {"message": "已取消訂閱", "endpoint": endpoint}


# ─── Inbox (站內通知) ──────────────────────────────────────

@router.get("/inbox/list")
def inbox_list(
    patient_id: str = Query(...),
    unread_only: bool = False,
    limit: int = 50,
):
    sb = get_supabase()
    q = sb.table("notification_inbox").select("*").eq("patient_id", patient_id)
    if unread_only:
        q = q.eq("read", 0)
    rows = q.order("created_at", desc=True).limit(min(limit, 200)).execute().data or []
    unread = sum(1 for r in rows if not r.get("read"))
    return {"items": rows, "unread": unread}


@router.put("/inbox/{item_id}")
def inbox_mark(item_id: str, body: InboxUpdate):
    sb = get_supabase()
    updates = {
        "read": 1 if body.read else 0,
        "read_at": datetime.now(timezone.utc).isoformat() if body.read else None,
    }
    result = sb.table("notification_inbox").update(updates).eq("id", item_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到通知")
    return result.data[0]


@router.post("/inbox/read-all")
def inbox_read_all(patient_id: str = Query(...)):
    sb = get_supabase()
    sb.table("notification_inbox").update({
        "read": 1,
        "read_at": datetime.now(timezone.utc).isoformat(),
    }).eq("patient_id", patient_id).eq("read", 0).execute()
    return {"message": "已全部標為已讀"}


# ─── Dispatch（cron 入口） ────────────────────────────────

def _endpoint_is_safe(endpoint):
    """檢查 endpoint 是否為 https 且屬於 ALLOWED_PUSH_HOSTS。
    雖然 push_subscribe 已驗證過，但這裡作為 sink 級的二次防線：
    避免 DB 直接被插入或 client 改 schema 後造成 SSRF。"""
    from urllib.parse import urlparse
    if not isinstance(endpoint, str) or not endpoint:
        return False
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return any(host == h or host.endswith("." + h) for h in ALLOWED_PUSH_HOSTS)


def _send_webpush(subscription_row, payload):
    """送一封 Web Push；回傳 (ok, error_str)。"""
    if not (VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY and _webpush_available):
        return False, "vapid_not_configured"
    endpoint = subscription_row.get("endpoint")
    if not _endpoint_is_safe(endpoint):
        return False, "endpoint_rejected"
    try:
        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": subscription_row["p256dh"],
                    "auth": subscription_row["auth"],
                },
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_CONTACT_EMAIL},
        )
        return True, None
    except WebPushException as e:  # type: ignore[misc]
        code = getattr(getattr(e, "response", None), "status_code", None)
        return False, f"webpush_failed:{code or type(e).__name__}"
    except Exception as e:
        return False, f"exception:{type(e).__name__}"


@router.post("/dispatch")
def dispatch_due_reminders(
    patient_id: str | None = Query(default=None),
    limit: int = 200,
    x_cron_token: str | None = Header(default=None, alias="X-Cron-Token"),
):
    """掃描已到期的 reminders：寫入 inbox + Web Push。

    - 若設了環境變數 CRON_TOKEN，呼叫時須帶 X-Cron-Token header。
    - 帶 patient_id 時只派發該病患的（前端登入後可呼叫，無需 token）。
    """
    expected = os.getenv("CRON_TOKEN")
    if expected and not patient_id and x_cron_token != expected:
        raise HTTPException(status_code=401, detail="invalid cron token")

    sb = get_supabase()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    q = sb.table("reminders").select("*").eq("active", 1).lte("next_fire_at", now_iso)
    if patient_id:
        q = q.eq("patient_id", patient_id)
    due = (q.order("next_fire_at", desc=False).limit(min(limit, 500)).execute().data) or []

    dispatched = 0
    push_ok = 0
    push_fail = 0
    deactivated = 0
    stale_endpoints = []

    for r in due:
        r = _normalize_reminder_row(r)
        inbox_row = {
            "patient_id": r["patient_id"],
            "reminder_id": r["id"],
            "title": r.get("title") or "提醒",
            "body": r.get("body"),
            "url": r.get("url"),
            "reminder_type": r.get("reminder_type"),
            "delivered_via": "inbox",
        }
        try:
            sb.table("notification_inbox").insert(inbox_row).execute()
        except Exception as exc:
            logger.warning("inbox insert failed: %s", type(exc).__name__)
            continue
        dispatched += 1

        # Web Push fan-out
        subs = (
            sb.table("push_subscriptions").select("*").eq("patient_id", r["patient_id"]).execute().data
        ) or []
        any_push_ok = False
        for sub in subs:
            ok, err = _send_webpush(sub, {
                "title": r.get("title") or "提醒",
                "body": r.get("body") or "",
                "url": r.get("url") or "/",
                "tag": f"reminder-{r['id']}",
                "reminder_id": r["id"],
                "reminder_type": r.get("reminder_type"),
            })
            if ok:
                push_ok += 1
                any_push_ok = True
            else:
                push_fail += 1
                if err and ("404" in err or "410" in err):
                    # endpoint 已失效，移除避免下次重試
                    stale_endpoints.append(sub["endpoint"])
        if any_push_ok:
            # 標記 inbox 已透過 push 通知（最後一筆是剛插入的）
            try:
                sb.table("notification_inbox").update({"delivered_via": "inbox+push"}) \
                    .eq("reminder_id", r["id"]).eq("patient_id", r["patient_id"]) \
                    .gte("created_at", now_iso).execute()
            except Exception:
                pass

        # 更新 reminder 的下次觸發時間 / 關閉一次性的
        current_fire = _parse_iso(r.get("next_fire_at")) or now
        next_fire = _compute_next_fire(
            r.get("frequency", "once"),
            current_fire,
            r.get("time_of_day"),
            r.get("days_of_week"),
        )
        updates = {"last_sent_at": now_iso, "updated_at": now_iso}
        if next_fire is None:
            updates["active"] = 0
            deactivated += 1
        else:
            updates["next_fire_at"] = next_fire.isoformat()
        try:
            sb.table("reminders").update(updates).eq("id", r["id"]).execute()
        except Exception as exc:
            logger.warning("reminder update failed: %s", type(exc).__name__)

    for ep in set(stale_endpoints):
        try:
            sb.table("push_subscriptions").delete().eq("endpoint", ep).execute()
        except Exception:
            pass

    return {
        "scanned": len(due),
        "dispatched": dispatched,
        "push_ok": push_ok,
        "push_fail": push_fail,
        "deactivated_once": deactivated,
        "removed_stale_endpoints": len(set(stale_endpoints)),
        "ran_at": now_iso,
    }
