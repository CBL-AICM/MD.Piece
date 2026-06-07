"""
EMA（生態瞬時評估）觸發引擎 — 把問卷融合進 App，依時間窗（不定時）與使用情境（app_events
事件）推送問卷，結果走既有 surveys 引擎回後端。觸發規則由研究者後台 config 定義（data-driven）。

定位與重用（規則 2：不重造）：
  - 問卷內容：沿用 surveys 引擎（短微問卷或完整量表都是一份 survey）。
  - 使用情境：沿用 app_events（events.py）的事件當事件觸發來源。
  - 推送通道：ema_deliveries 佇列同時服務「Web Push」與「App 內補彈」兩通道。
      · App 內：GET /ema/pending（前端開 App 時拉待作答）。
      · Web Push：POST /ema/dispatch（cron）選到期待送 → 走既有 push 基礎建設發送。
  - 結果回收：前端用既有 POST /surveys/{key}/responses 作答後，呼叫 complete 連結 response。

設計鐵則：
  - 規則 5：何時觸發、是否在 cooldown / 超過每日上限 → 全是確定性判斷，純程式碼，不丟 LLM。
  - 規則 12：規則格式不合法明確 400；越權明確 403。
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import _SCHEMAS, get_supabase
from backend.security import current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# SQLite fallback schema（沿用 reminders.py 的 setdefault 注入慣例，不動 db.py 行號）。
# Supabase 上對應表由 docs/migration_ema.sql 建立。
_SCHEMAS.setdefault("ema_rules", """
    CREATE TABLE IF NOT EXISTS ema_rules (
        id TEXT PRIMARY KEY,
        study TEXT,
        name TEXT NOT NULL,
        survey_key TEXT NOT NULL,
        trigger_config TEXT NOT NULL,
        expires_after_min INTEGER DEFAULT 120,
        active INTEGER DEFAULT 1,
        created_by TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
_SCHEMAS.setdefault("ema_deliveries", """
    CREATE TABLE IF NOT EXISTS ema_deliveries (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        rule_id TEXT,
        survey_key TEXT NOT NULL,
        trigger_type TEXT,
        status TEXT DEFAULT 'pending',
        context TEXT,
        scheduled_at TEXT,
        shown_at TEXT,
        completed_at TEXT,
        response_id TEXT,
        expires_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

_TRIGGER_TYPES = {"event", "time"}


# ── Models ────────────────────────────────────────────────

class RuleCreate(BaseModel):
    name: str
    survey_key: str
    trigger_config: dict          # {type, match/windows, cooldown_min, max_per_day, per_window}
    study: Optional[str] = None
    expires_after_min: int = 120


class EventProbe(BaseModel):
    event_type: str
    event_name: Optional[str] = None
    target: Optional[str] = None


class EvaluateBody(BaseModel):
    patient_id: str
    events: list[EventProbe]


class ScheduleBody(BaseModel):
    study: Optional[str] = None
    participant_ids: list[str]
    date: Optional[str] = None     # YYYY-MM-DD；預設今天


class CompleteBody(BaseModel):
    response_id: Optional[str] = None


# ── Helpers（純程式碼；規則 5）────────────────────────────

def _json(v):
    import json
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return v
    return v


def _now() -> datetime:
    return datetime.now()                              # 本地時間（研究施測以本地為準）


def _parse(s) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)[:19])
    except ValueError:
        return None


def _load_rules(sb, study: Optional[str], ttype: Optional[str]) -> list:
    try:
        rows = sb.table("ema_rules").select("*").execute().data or []
    except Exception as e:
        logger.info(f"ema rules load failed: {e}")
        return []
    out = []
    for r in rows:
        if not r.get("active", 1):
            continue
        tc = _json(r.get("trigger_config")) or {}
        if study is not None and r.get("study") != study:
            continue
        if ttype is not None and tc.get("type") != ttype:
            continue
        out.append({**r, "trigger_config": tc})
    return out


def _deliveries_for(sb, rule_id: str, user_id: str) -> list:
    try:
        rows = (sb.table("ema_deliveries").select("*")
                .eq("rule_id", rule_id).eq("user_id", user_id).execute().data or [])
    except Exception:
        rows = []
    return rows


def _matches(match: dict, ev: dict) -> bool:
    """事件規則比對：match 指定的欄位都要與事件相等（未指定的欄位不限）。"""
    for k in ("event_type", "event_name", "target"):
        want = match.get(k)
        if want is not None and ev.get(k) != want:
            return False
    return True


def _make_delivery(sb, rule, user_id, trigger_type, scheduled_at, context):
    exp = _parse(scheduled_at)
    expires_at = ((exp or _now()) + timedelta(minutes=int(rule.get("expires_after_min") or 120))).isoformat(timespec="seconds")
    row = {
        "user_id": user_id, "rule_id": rule.get("id"), "survey_key": rule.get("survey_key"),
        "trigger_type": trigger_type, "status": "pending", "context": context,
        "scheduled_at": scheduled_at, "expires_at": expires_at,
    }
    saved = sb.table("ema_deliveries").insert(row).execute()
    return saved.data[0] if saved.data else row


def _expire_overdue(sb, rows: list):
    """把已過 expires_at 的 pending 標 expired（lazy expiry）。"""
    now = _now()
    for r in rows:
        if r.get("status") == "pending":
            exp = _parse(r.get("expires_at"))
            if exp and exp < now:
                try:
                    sb.table("ema_deliveries").update({"status": "expired"}).eq("id", r["id"]).execute()
                    r["status"] = "expired"
                except Exception:
                    pass


# ── 規則 CRUD（研究者後台；config 驅動）────────────────────

@router.post("/rules")
def create_rule(body: RuleCreate, me: dict = Depends(current_user)):
    """定義一條 EMA 觸發規則（限 doctor）。"""
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅研究者可建立 EMA 規則")
    tc = body.trigger_config or {}
    if tc.get("type") not in _TRIGGER_TYPES:
        raise HTTPException(status_code=400, detail=f"trigger_config.type 需為 {_TRIGGER_TYPES}")
    if tc["type"] == "event" and not (tc.get("match") or {}):
        raise HTTPException(status_code=400, detail="event 規則需提供 match（event_type/name/target）")
    if tc["type"] == "time" and not (tc.get("windows") or []):
        raise HTTPException(status_code=400, detail="time 規則需提供 windows（[{start,end}]）")
    sb = get_supabase()
    if not sb.table("surveys").select("key").eq("key", body.survey_key).limit(1).execute().data:
        raise HTTPException(status_code=400, detail=f"survey_key 不存在：{body.survey_key}")
    row = {
        "study": body.study, "name": body.name, "survey_key": body.survey_key,
        "trigger_config": tc, "expires_after_min": body.expires_after_min,
        "active": 1, "created_by": me.get("id"),
    }
    try:
        saved = sb.table("ema_rules").insert(row).execute()
    except Exception as e:
        logger.error(f"create ema rule failed: {e}")
        raise HTTPException(status_code=400, detail=f"建立規則失敗：{e}")
    out = dict(saved.data[0]) if saved.data else row
    out["trigger_config"] = _json(out.get("trigger_config"))
    return out


@router.get("/rules")
def list_rules(study: Optional[str] = Query(None), me: dict = Depends(current_user)):
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅研究者可檢視 EMA 規則")
    return {"rules": _load_rules(get_supabase(), study, None)}


@router.delete("/rules/{rule_id}")
def deactivate_rule(rule_id: str, me: dict = Depends(current_user)):
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅研究者可停用 EMA 規則")
    sb = get_supabase()
    sb.table("ema_rules").update({"active": 0}).eq("id", rule_id).execute()
    return {"id": rule_id, "active": 0}


# ── 事件觸發（event-contingent；依使用情境）─────────────────

@router.post("/evaluate")
def evaluate_events(body: EvaluateBody, me: dict = Depends(current_user)):
    """比對使用者剛發生的事件 → 觸發 event 規則並建立 delivery。本人或 doctor 可呼叫。

    確定性判斷（規則 5）：match 命中 + 未在 cooldown + 未超過每日上限 → 建 delivery。
    """
    pid = body.patient_id
    if me.get("id") != pid and me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="只能評估自己的事件")
    sb = get_supabase()
    rules = _load_rules(sb, None, "event")
    now = _now()
    today = now.date().isoformat()
    created = []
    for ev in body.events:
        evd = ev.model_dump()
        for rule in rules:
            tc = rule["trigger_config"]
            if not _matches(tc.get("match") or {}, evd):
                continue
            prior = _deliveries_for(sb, rule["id"], pid)
            # cooldown：距上次此規則 delivery 不足 cooldown_min 就跳過
            cd = tc.get("cooldown_min")
            if cd:
                last = max((_parse(p.get("scheduled_at")) or _parse(p.get("created_at")) for p in prior),
                           default=None)
                if last and (now - last) < timedelta(minutes=int(cd)):
                    continue
            # 每日上限
            cap = tc.get("max_per_day")
            if cap:
                today_n = sum(1 for p in prior if str(p.get("scheduled_at") or "")[:10] == today)
                if today_n >= int(cap):
                    continue
            d = _make_delivery(sb, rule, pid, "event",
                               now.isoformat(timespec="seconds"), {"event": evd})
            created.append({"id": d.get("id"), "rule_id": rule["id"], "survey_key": rule["survey_key"]})
    return {"patient_id": pid, "created": created, "count": len(created)}


# ── 時間觸發（signal-contingent；不定時隨機窗）──────────────

def _rand_time(window: dict, day: str) -> Optional[str]:
    try:
        sh, sm = map(int, str(window["start"]).split(":"))
        eh, em = map(int, str(window["end"]).split(":"))
    except (KeyError, ValueError):
        return None
    lo, hi = sh * 60 + sm, eh * 60 + em
    if hi < lo:
        return None
    t = random.randint(lo, hi)
    return f"{day}T{t // 60:02d}:{t % 60:02d}:00"


@router.post("/schedule")
def schedule_time(body: ScheduleBody, me: dict = Depends(current_user)):
    """為時間規則 × 受試者產生當日隨機推送時點（限 doctor / cron）。冪等：同規則+人+窗+日不重排。"""
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅研究者 / 排程可建立時間推送")
    sb = get_supabase()
    day = (body.date or _now().date().isoformat())
    rules = _load_rules(sb, body.study, "time")
    created = 0
    for rule in rules:
        tc = rule["trigger_config"]
        windows = tc.get("windows") or []
        per = int(tc.get("per_window") or 1)
        for pid in body.participant_ids:
            prior = _deliveries_for(sb, rule["id"], pid)
            done_windows = {(_json(p.get("context")) or {}).get("window")
                            for p in prior if str(p.get("scheduled_at") or "")[:10] == day}
            for wi, w in enumerate(windows):
                if wi in done_windows:                  # 冪等：該窗當日已排過
                    continue
                for _ in range(per):
                    sched = _rand_time(w, day)
                    if not sched:
                        continue
                    _make_delivery(sb, rule, pid, "time", sched, {"window": wi, "window_def": w})
                    created += 1
    return {"date": day, "scheduled": created}


# ── App 內通道：拉待作答 ─────────────────────────────────

@router.get("/pending")
def pending(patient_id: Optional[str] = Query(None), me: dict = Depends(current_user)):
    """回傳該使用者「現在該作答」的 EMA（scheduled_at 已到、未過期、未完成）。本人或 doctor。"""
    pid = patient_id or me.get("id")
    if me.get("id") != pid and me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="只能檢視自己的待作答 EMA")
    sb = get_supabase()
    try:
        rows = sb.table("ema_deliveries").select("*").eq("user_id", pid).execute().data or []
    except Exception as e:
        logger.info(f"ema pending fetch failed: {e}")
        rows = []
    _expire_overdue(sb, rows)
    now = _now()
    out = []
    for r in rows:
        if r.get("status") != "pending":
            continue
        sched = _parse(r.get("scheduled_at"))
        if sched and sched > now:                       # 還沒到推送時間
            continue
        out.append({"id": r["id"], "survey_key": r["survey_key"],
                    "trigger_type": r.get("trigger_type"),
                    "scheduled_at": r.get("scheduled_at"), "context": _json(r.get("context"))})
    out.sort(key=lambda x: x.get("scheduled_at") or "")
    return {"patient_id": pid, "pending": out, "count": len(out)}


@router.post("/deliveries/{delivery_id}/complete")
def complete_delivery(delivery_id: str, body: CompleteBody, me: dict = Depends(current_user)):
    """作答完成後連結 response 並標記完成。"""
    sb = get_supabase()
    rows = sb.table("ema_deliveries").select("*").eq("id", delivery_id).limit(1).execute().data or []
    if not rows:
        raise HTTPException(status_code=404, detail="找不到該 EMA 推送")
    d = rows[0]
    if me.get("id") != d.get("user_id") and me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="只能完成自己的 EMA")
    sb.table("ema_deliveries").update({
        "status": "completed", "completed_at": _now().isoformat(timespec="seconds"),
        "response_id": body.response_id,
    }).eq("id", delivery_id).execute()
    return {"id": delivery_id, "status": "completed", "response_id": body.response_id}


# ── Web Push 通道：cron 選到期待送 ──────────────────────────

@router.post("/dispatch")
def dispatch(me: dict = Depends(current_user)):
    """選出「已到推送時間、未送過、未過期」的 pending，回傳推送 payload 並標 shown_at（限 doctor/cron）。

    實際 Web Push 發送重用既有 reminders 基礎建設（push_subscriptions + VAPID）：
    本端點產生 payload 與標記，避免重複 push；發送串接見 reminders.py 的 dispatch 管線。
    """
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅研究者 / 排程可派送")
    sb = get_supabase()
    try:
        rows = sb.table("ema_deliveries").select("*").eq("status", "pending").execute().data or []
    except Exception:
        rows = []
    _expire_overdue(sb, rows)
    now = _now()
    payloads = []
    for r in rows:
        if r.get("status") != "pending" or r.get("shown_at"):
            continue
        sched = _parse(r.get("scheduled_at"))
        if sched and sched > now:
            continue
        sb.table("ema_deliveries").update({
            "shown_at": now.isoformat(timespec="seconds")
        }).eq("id", r["id"]).execute()
        payloads.append({
            "delivery_id": r["id"], "user_id": r["user_id"], "survey_key": r["survey_key"],
            "title": "有一份簡短問卷想請您填", "url": f"/?ema_delivery={r['id']}",
        })
    return {"dispatched": len(payloads), "payloads": payloads,
            "note": "Web Push 實際發送重用 reminders 的 push_subscriptions + VAPID 管線。"}
