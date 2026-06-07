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
import os
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
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

_TRIGGER_TYPES = {"event", "time", "elapsed"}


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
    if tc["type"] == "elapsed" and not (tc.get("day") or tc.get("threshold")):
        raise HTTPException(status_code=400, detail="elapsed 規則需提供 day（入組第幾天 / 累積記錄天數）")
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

def _evaluate(sb, pid: str, event_dicts: list) -> list:
    """核心事件評估（純程式碼，規則 5）：match 命中 + 未在 cooldown + 未超過每日上限 → 建 delivery。

    供 /evaluate 端點與 events ingest hook 共用。event_dicts: [{event_type,event_name,target}]。
    """
    rules = _load_rules(sb, None, "event")
    if not rules:
        return []
    now = _now()
    today = now.date().isoformat()
    created = []
    for evd in event_dicts:
        for rule in rules:
            tc = rule["trigger_config"]
            if not _matches(tc.get("match") or {}, evd):
                continue
            prior = _deliveries_for(sb, rule["id"], pid)
            cd = tc.get("cooldown_min")
            if cd:
                last = max((_parse(p.get("scheduled_at")) or _parse(p.get("created_at")) for p in prior),
                           default=None)
                if last and (now - last) < timedelta(minutes=int(cd)):
                    continue
            cap = tc.get("max_per_day")
            if cap:
                today_n = sum(1 for p in prior if str(p.get("scheduled_at") or "")[:10] == today)
                if today_n >= int(cap):
                    continue
            # delay_min：里程碑事件（如「回診結束」）隔一段時間再推（對齊 FU48）。
            # deliver_window：當天窗內隨機時點 → 日常「不定時」感，不一發生就跳出。
            delay = int(tc.get("delay_min") or 0)
            base = now + timedelta(minutes=delay)
            sched = _scheduled_at(base, tc)
            d = _make_delivery(sb, rule, pid, "event", sched, {"event": evd, "delay_min": delay})
            created.append({"id": d.get("id"), "rule_id": rule["id"],
                            "survey_key": rule["survey_key"], "scheduled_at": sched})
    return created


@router.post("/evaluate")
def evaluate_events(body: EvaluateBody, me: dict = Depends(current_user)):
    """比對使用者剛發生的事件 → 觸發 event 規則並建立 delivery。本人或 doctor 可呼叫。"""
    pid = body.patient_id
    if me.get("id") != pid and me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="只能評估自己的事件")
    created = _evaluate(get_supabase(), pid, [e.model_dump() for e in body.events])
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


def _scheduled_at(base: datetime, tc: dict) -> str:
    """推送時點：有 deliver_window 就在當天該窗內隨機（不定時感），否則用 base 本身。"""
    win = tc.get("deliver_window")
    if win:
        s = _rand_time(win, base.date().isoformat())
        if s:
            return s
    return base.isoformat(timespec="seconds")


def _deliveries_user_on(sb, pid: str, date: str) -> list:
    """某受試者某日的全部 delivery（跨規則）— 供「每日 ≤1 份」節流。"""
    try:
        rows = sb.table("ema_deliveries").select("*").eq("user_id", pid).execute().data or []
    except Exception:
        rows = []
    return [r for r in rows if str(r.get("scheduled_at") or "")[:10] == date]


def _enroll_progress(sb, pid: str, on_date: str):
    """回傳 (入組第幾天 day_index, 累積記錄天數 record_days)；以最早活動日為入組日。

    活動來源：survey_responses + app_events（記錄/作答即視為活躍）。供 elapsed 觸發判斷
    「記錄一段時間」。純程式碼彙整（規則 5）。
    """
    days = []
    for tbl, col, dcols in (("survey_responses", "patient_id", ("created_at",)),
                            ("app_events", "user_id", ("occurred_at", "created_at"))):
        try:
            rows = sb.table(tbl).select("*").eq(col, pid).execute().data or []
        except Exception:
            rows = []
        for r in rows:
            for dc in dcols:
                if r.get(dc):
                    days.append(str(r[dc])[:10])
                    break
    if not days:
        return None, 0
    first = min(days)
    record_days = len(set(days))
    try:
        idx = (datetime.fromisoformat(on_date).date() - datetime.fromisoformat(first).date()).days + 1
    except ValueError:
        idx = None
    return idx, record_days


def _run_schedule(sb, study: Optional[str], participant_ids: list, day: str) -> int:
    """time + elapsed 規則 → 當日推送（純程式碼）。每人每日 ≤1 份、里程碑一次性、冪等。

    供 /schedule 端點與 /cron/run 共用。
    """
    rules = _load_rules(sb, study, "time") + _load_rules(sb, study, "elapsed")
    created = 0
    for rule in rules:
        tc = rule["trigger_config"]
        ttype = tc.get("type")
        cap = tc.get("respect_daily_cap", True)
        for pid in participant_ids:
            if cap and _deliveries_user_on(sb, pid, day):       # 日常 ≤1 份/日
                continue

            if ttype == "time":
                prior = _deliveries_for(sb, rule["id"], pid)
                done = {(_json(p.get("context")) or {}).get("window")
                        for p in prior if str(p.get("scheduled_at") or "")[:10] == day}
                for wi, w in enumerate(tc.get("windows") or []):
                    if wi in done:
                        continue
                    sched = _rand_time(w, day)
                    if not sched:
                        continue
                    _make_delivery(sb, rule, pid, "time", sched, {"window": wi})
                    created += 1
                    if cap:
                        break                                    # 每日只發一份

            elif ttype == "elapsed":
                if _deliveries_for(sb, rule["id"], pid):         # 里程碑：發過就不再發
                    continue
                on = tc.get("on", "enrollment_day")
                thr = int(tc.get("day") or tc.get("threshold") or 0)
                idx, rec = _enroll_progress(sb, pid, day)
                reached = ((on == "enrollment_day" and idx == thr) or
                           (on == "record_days" and rec >= thr))
                if not reached:
                    continue
                base = datetime.fromisoformat(day + "T00:00:00")
                sched = _scheduled_at(base, tc)
                _make_delivery(sb, rule, pid, "elapsed", sched,
                               {"on": on, "threshold": thr, "day_index": idx, "record_days": rec})
                created += 1
    return created


@router.post("/schedule")
def schedule_time(body: ScheduleBody, me: dict = Depends(current_user)):
    """每日排程（限 doctor / cron）：把 time（每日窗）與 elapsed（入組/記錄里程碑）轉成當日推送。

    日常不定時：每人每日至多 1 份、時點隨機、里程碑一次性。冪等可重跑。
    """
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅研究者 / 排程可建立推送")
    sb = get_supabase()
    day = (body.date or _now().date().isoformat())
    n = _run_schedule(sb, body.study, body.participant_ids, day)
    return {"date": day, "scheduled": n}


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

def _run_dispatch(sb, send_push: bool = True) -> dict:
    """選「已到時間、未送過、未過期」的 pending → 寫站內通知(App內通道) + 發 Web Push，標 shown。

    實際 Web Push 重用 reminders._send_webpush（push_subscriptions + VAPID）；無 VAPID 時
    優雅退化為只寫站內通知（規則 12：缺憑證時 loud-degrade，不假裝送出）。
    """
    try:
        rows = sb.table("ema_deliveries").select("*").eq("status", "pending").execute().data or []
    except Exception:
        rows = []
    _expire_overdue(sb, rows)
    now = _now()
    sender = None
    if send_push:
        try:
            from backend.routers import reminders as _rem
            sender = _rem._send_webpush
        except Exception as e:
            logger.info(f"ema dispatch: push sender unavailable: {e}")
    sent, pushed, push_fail = 0, 0, 0
    payloads = []
    for r in rows:
        if r.get("status") != "pending" or r.get("shown_at"):
            continue
        sched = _parse(r.get("scheduled_at"))
        if sched and sched > now:
            continue
        uid = r["user_id"]
        payload = {"title": "有一份簡短問卷想請您填", "body": "約 20–30 秒，謝謝您",
                   "url": f"/?ema_delivery={r['id']}", "tag": f"ema-{r['id']}"}
        try:                                   # 站內通知 = App 內通道（站內通知中心會顯示）
            sb.table("notification_inbox").insert({
                "patient_id": uid, "reminder_id": None, "title": payload["title"],
                "body": payload["body"], "url": payload["url"],
                "reminder_type": "survey", "delivered_via": "push" if sender else "inbox",
            }).execute()
        except Exception as e:
            logger.info(f"ema inbox insert failed: {e}")
        if sender:                             # Web Push fan-out
            try:
                subs = sb.table("push_subscriptions").select("*").eq("patient_id", uid).execute().data or []
            except Exception:
                subs = []
            for sub in subs:
                ok, _err = sender(sub, payload)
                pushed += 1 if ok else 0
                push_fail += 0 if ok else 1
        sb.table("ema_deliveries").update(
            {"shown_at": now.isoformat(timespec="seconds")}).eq("id", r["id"]).execute()
        sent += 1
        payloads.append({"delivery_id": r["id"], "user_id": uid, "survey_key": r["survey_key"]})
    return {"dispatched": sent, "pushed": pushed, "push_failed": push_fail, "payloads": payloads}


@router.post("/dispatch")
def dispatch(me: dict = Depends(current_user)):
    """派送到期待送（限 doctor / cron）：寫站內通知 + 發 Web Push，標 shown 防重複。"""
    if me.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="僅研究者 / 排程可派送")
    return _run_dispatch(get_supabase(), send_push=True)


def _study_participants(sb, study: Optional[str]) -> list:
    """蒐集受試者 id：有 survey_responses 或 app_events 的使用者（供 cron 自動排程）。

    n 小（可行性研究 10–12 人），直接 union 全表 id；規模化再改 distinct 查詢。
    """
    ids = set()
    for tbl, col in (("survey_responses", "patient_id"), ("app_events", "user_id")):
        try:
            rows = sb.table(tbl).select("*").execute().data or []
        except Exception:
            rows = []
        for r in rows:
            if r.get(col):
                ids.add(r[col])
    return sorted(ids)


@router.get("/cron/run")
def cron_run(study: Optional[str] = Query(None),
             authorization: Optional[str] = Header(default=None),
             x_cron_token: Optional[str] = Header(default=None, alias="X-Cron-Token")):
    """每日 cron 入口：當日 time/elapsed 排程 + 派送到期。沿用 reminders 的 CRON_SECRET/CRON_TOKEN 驗證。

    Vercel 原生 Cron 發 GET 並帶 Authorization: Bearer ${CRON_SECRET}；外部排程可帶 X-Cron-Token。
    兩個 env 皆未設時開放（本地 / 尚未設定時可手動觸發）。
    """
    cron_secret = os.getenv("CRON_SECRET")
    cron_token = os.getenv("CRON_TOKEN")
    if cron_secret or cron_token:
        ok = ((cron_secret and authorization == f"Bearer {cron_secret}")
              or (cron_token and x_cron_token == cron_token))
        if not ok:
            raise HTTPException(status_code=401, detail="invalid cron auth")
    sb = get_supabase()
    day = _now().date().isoformat()
    participants = _study_participants(sb, study)
    scheduled = _run_schedule(sb, study, participants, day)
    disp = _run_dispatch(sb, send_push=True)
    return {"date": day, "participants": len(participants), "scheduled": scheduled, **disp}
