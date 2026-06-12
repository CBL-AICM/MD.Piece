"""
月經紀錄 router — 個人化縱向分析的一部分。

以「使用者自己的週期基線」呈現變化，不做診斷、不判定正常/異常。
涵蓋：
  - 經期（cycles）：起訖日、經血量、症狀、備註
  - 每日紀錄（daily）：基礎體溫 BBT、排卵試紙、避孕藥服用
  - 摘要（summary）：平均週期長度、平均經期天數、上次經期、預估下次經期

規則 5：週期長度、平均、預估下次都是確定性算術 → 純程式碼，不丟 LLM。
法規紅線：預估下次經期明確標「僅為估算、非醫學預測」；不對週期長短下「正常/異常」判斷。
"""

import json
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.security import current_user_optional, enforce_patient_scope

logger = logging.getLogger(__name__)
router = APIRouter()

DISCLAIMER = (
    "本功能僅記錄與整理你自己的週期資料，不做醫療診斷，也不判斷「正常 / 異常」；"
    "如有疑慮請諮詢您的醫師。"
)
ESTIMATE_NOTE = "此為依你過往紀錄推算的估計值，僅供參考、非醫學預測；週期長短因人而異。"

_ALLOWED_FLOW = {"light", "medium", "heavy"}
_ALLOWED_OVU = {"positive", "negative", "peak"}


# ── Models ────────────────────────────────────────────────

class CycleCreate(BaseModel):
    patient_id: str
    start_date: str                      # YYYY-MM-DD（經期第一天）
    end_date: Optional[str] = None       # YYYY-MM-DD（經期最後一天）
    flow: Optional[str] = None           # light | medium | heavy
    symptoms: list[str] = []             # 經痛 / 情緒 / 頭痛 ...
    note: Optional[str] = None


class CycleUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    flow: Optional[str] = None
    symptoms: Optional[list[str]] = None
    note: Optional[str] = None


class DailyUpsert(BaseModel):
    patient_id: str
    date: str                            # YYYY-MM-DD
    bbt_c: Optional[float] = None        # 基礎體溫（攝氏）
    ovulation_test: Optional[str] = None # positive | negative | peak
    pill_taken: Optional[bool] = None    # 今天避孕藥是否已服用
    note: Optional[str] = None


# ── helpers ───────────────────────────────────────────────

def _parse_date(s: Optional[str], label: str = "日期") -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label} 格式需為 YYYY-MM-DD")


def _decode_symptoms(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except Exception:
        return [s for s in str(raw).split(",") if s.strip()]


def _row_out(r: dict) -> dict:
    r = dict(r)
    r["symptoms"] = _decode_symptoms(r.get("symptoms"))
    return r


# ── 經期 cycles CRUD ──────────────────────────────────────

def _assert_owns_cycle(sb, cycle_id: str, me: dict | None) -> dict:
    """以 cycle_id 改/刪時的擁有權檢查：已登入則該筆 patient_id 必須是自己。"""
    res = sb.table("menstrual_cycles").select("*").eq("id", cycle_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="找不到該經期紀錄")
    enforce_patient_scope(res.data[0].get("patient_id"), me)
    return res.data[0]


@router.get("/cycles")
def list_cycles(patient_id: str = Query(...), limit: int = Query(60, ge=1, le=300),
                me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    rows = (
        sb.table("menstrual_cycles").select("*")
        .eq("patient_id", patient_id)
        .order("start_date", desc=True)
        .execute().data or []
    )
    return {"cycles": [_row_out(r) for r in rows[:limit]]}


@router.post("/cycles")
def create_cycle(body: CycleCreate, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(body.patient_id, me)
    start = _parse_date(body.start_date, "start_date")
    end = _parse_date(body.end_date, "end_date")
    if start is None:
        raise HTTPException(status_code=400, detail="start_date 必填")
    if end and end < start:
        raise HTTPException(status_code=400, detail="end_date 不可早於 start_date")
    if body.flow and body.flow not in _ALLOWED_FLOW:
        raise HTTPException(status_code=400, detail=f"flow 必須是 {_ALLOWED_FLOW} 之一")
    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat() if end else None,
        "flow": body.flow,
        "symptoms": json.dumps(body.symptoms or [], ensure_ascii=False),
        "note": body.note,
    }
    data = {k: v for k, v in data.items() if v is not None}
    try:
        result = sb.table("menstrual_cycles").insert(data).execute()
    except Exception as e:
        logger.error(f"create cycle failed: {e}")
        raise HTTPException(status_code=400, detail="新增經期紀錄失敗")
    return _row_out(result.data[0]) if result.data else data


@router.put("/cycles/{cycle_id}")
def update_cycle(cycle_id: str, body: CycleUpdate, me: dict | None = Depends(current_user_optional)):
    _assert_owns_cycle(get_supabase(), cycle_id, me)
    data: dict = {}
    if body.start_date is not None:
        data["start_date"] = _parse_date(body.start_date, "start_date").isoformat()
    if body.end_date is not None:
        data["end_date"] = _parse_date(body.end_date, "end_date").isoformat() if body.end_date else None
    if body.flow is not None:
        if body.flow and body.flow not in _ALLOWED_FLOW:
            raise HTTPException(status_code=400, detail=f"flow 必須是 {_ALLOWED_FLOW} 之一")
        data["flow"] = body.flow
    if body.symptoms is not None:
        data["symptoms"] = json.dumps(body.symptoms, ensure_ascii=False)
    if body.note is not None:
        data["note"] = body.note
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    sb = get_supabase()
    result = sb.table("menstrual_cycles").update(data).eq("id", cycle_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到該經期紀錄")
    return _row_out(result.data[0])


@router.delete("/cycles/{cycle_id}")
def delete_cycle(cycle_id: str, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    _assert_owns_cycle(sb, cycle_id, me)
    sb.table("menstrual_cycles").delete().eq("id", cycle_id).execute()
    return {"deleted": cycle_id}


# ── 每日紀錄（BBT / 排卵 / 避孕藥）upsert by date ──────────

@router.get("/daily")
def list_daily(patient_id: str = Query(...), days: int = Query(60, ge=1, le=400),
               me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    rows = (
        sb.table("menstrual_daily").select("*")
        .eq("patient_id", patient_id)
        .order("date", desc=True)
        .execute().data or []
    )
    return {"daily": rows[:days]}


@router.post("/daily")
def upsert_daily(body: DailyUpsert, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(body.patient_id, me)
    d = _parse_date(body.date, "date")
    if d is None:
        raise HTTPException(status_code=400, detail="date 必填")
    if body.ovulation_test and body.ovulation_test not in _ALLOWED_OVU:
        raise HTTPException(status_code=400, detail=f"ovulation_test 必須是 {_ALLOWED_OVU} 之一")
    sb = get_supabase()
    fields = {
        "bbt_c": body.bbt_c,
        "ovulation_test": body.ovulation_test,
        "pill_taken": (1 if body.pill_taken else 0) if body.pill_taken is not None else None,
        "note": body.note,
    }
    fields = {k: v for k, v in fields.items() if v is not None}

    # 以 (patient_id, date) 為鍵做 upsert（不依賴 DB 的 ON CONFLICT，手動查再更新）。
    existing = (
        sb.table("menstrual_daily").select("id")
        .eq("patient_id", body.patient_id).eq("date", d.isoformat())
        .limit(1).execute().data or []
    )
    if existing:
        if fields:
            sb.table("menstrual_daily").update(fields).eq("id", existing[0]["id"]).execute()
        return {"id": existing[0]["id"], "date": d.isoformat(), **fields, "_upserted": "updated"}
    row = {"patient_id": body.patient_id, "date": d.isoformat(), **fields}
    try:
        result = sb.table("menstrual_daily").insert(row).execute()
    except Exception as e:
        logger.error(f"upsert daily failed: {e}")
        raise HTTPException(status_code=400, detail="儲存每日紀錄失敗")
    return {**(result.data[0] if result.data else row), "_upserted": "created"}


# ── 摘要（純程式碼推算，標明僅供估算）─────────────────────

@router.get("/summary")
def summary(patient_id: str = Query(...), window: int = Query(6, ge=2, le=24),
            me: dict | None = Depends(current_user_optional)):
    """以使用者自己的紀錄推算：平均週期、平均經期、上次經期、預估下次。

    規則 5：全部是確定性算術。預估下次明確標 estimate=True + ESTIMATE_NOTE。
    不做任何「正常/異常」判斷（法規紅線）。
    """
    enforce_patient_scope(patient_id, me)
    sb = get_supabase()
    rows = (
        sb.table("menstrual_cycles").select("*")
        .eq("patient_id", patient_id)
        .execute().data or []
    )
    starts = sorted(
        [d for d in (_safe_date(r.get("start_date")) for r in rows) if d]
    )
    # 經期長度（有 end_date 才算）
    period_lengths = []
    for r in rows:
        s = _safe_date(r.get("start_date"))
        e = _safe_date(r.get("end_date"))
        if s and e and e >= s:
            period_lengths.append((e - s).days + 1)

    # 週期長度 = 相鄰兩次經期起始日的天數差（取最近 window 個）
    cycle_lengths = [(starts[i + 1] - starts[i]).days for i in range(len(starts) - 1)]
    recent_cycle_lengths = cycle_lengths[-window:]

    avg_cycle = round(sum(recent_cycle_lengths) / len(recent_cycle_lengths)) if recent_cycle_lengths else None
    avg_period = round(sum(period_lengths) / len(period_lengths)) if period_lengths else None
    last_start = starts[-1] if starts else None

    estimated_next = None
    days_until = None
    if last_start and avg_cycle:
        nxt = last_start.fromordinal(last_start.toordinal() + avg_cycle)
        estimated_next = nxt.isoformat()
        days_until = (nxt - date.today()).days

    return {
        "cycle_count": len(starts),
        "avg_cycle_length": avg_cycle,        # 天，None 表示資料不足（<2 次）
        "avg_period_length": avg_period,      # 天，None 表示沒有完整起訖
        "last_start": last_start.isoformat() if last_start else None,
        "recent_cycle_lengths": recent_cycle_lengths,
        "estimated_next_start": estimated_next,
        "days_until_next": days_until,
        "estimate": estimated_next is not None,
        "estimate_note": ESTIMATE_NOTE,
        "disclaimer": DISCLAIMER,
    }


def _safe_date(s):
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None
