"""
睡眠紀錄模組 router — 純記錄工具（record-only）。

依《睡眠紀錄模組 開發規格》：
  - 三種資料來源並存：auto（pipeline）/ manual（補登修正）/ imported（外部匯入）
  - 手動修正既有 auto 紀錄 → is_edited=true，保留原值於 sleep_edits log（供研究端比對）
  - 患者端介面：今日卡 / 單晚時間軸 / 趨勢 / 修正 所需資料
  - 匯出：CSV（PDF 由前端用既有 previsitOpenPrint 產生）

設計邊界（務必遵守）：不下診斷、不給醫療建議、不做風險警示、不用情緒性評語。
本 router 只做確定性記錄與計算（規則 5），完全不呼叫 LLM。
"""

import csv
import io
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.db import get_supabase
from backend.utils.sleep_pipeline import (
    Epoch,
    SleepConfig,
    compute_metrics_from_times,
    run_pipeline,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_SOURCE = {"auto", "manual", "imported"}


# ── Models ────────────────────────────────────────────────

class SleepSessionCreate(BaseModel):
    """手動補登 / 外部匯入一筆睡眠紀錄。"""
    user_id: str
    bed_time: str               # ISO datetime
    sleep_onset: str
    wake_time: str
    out_of_bed_time: Optional[str] = None
    waso_minutes: int = 0
    awakenings_count: int = 0
    source: str = "manual"      # manual | imported


class SleepSessionEdit(BaseModel):
    """手動修正既有紀錄的時間點（規格 §5.4）。"""
    bed_time: Optional[str] = None
    sleep_onset: Optional[str] = None
    wake_time: Optional[str] = None
    out_of_bed_time: Optional[str] = None
    waso_minutes: Optional[int] = None
    awakenings_count: Optional[int] = None


class EpochIn(BaseModel):
    timestamp: str
    activity_count: float
    heart_rate: Optional[float] = None


class IngestRequest(BaseModel):
    """自動偵測：餵入原始 epoch 序列，跑 pipeline 產生一筆 auto session。"""
    user_id: str
    epochs: List[EpochIn]
    night_start_hour: Optional[int] = None
    night_end_hour: Optional[int] = None
    short_wake_threshold_min: Optional[int] = None
    classifier: Optional[str] = None


def _parse_dt(s: Optional[str], label: str):
    if not s:
        raise HTTPException(status_code=400, detail=f"{label} 必填")
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label} 格式需為 ISO datetime")


# ── 自動偵測 ingest（pipeline）────────────────────────────

@router.post("/ingest")
def ingest(body: IngestRequest):
    """跑判睡 pipeline，輸出並存入一筆 auto SleepSession。"""
    if not body.epochs:
        raise HTTPException(status_code=400, detail="epochs 不可為空")
    cfg = SleepConfig()
    if body.night_start_hour is not None:
        cfg.night_start_hour = body.night_start_hour
    if body.night_end_hour is not None:
        cfg.night_end_hour = body.night_end_hour
    if body.short_wake_threshold_min is not None:
        cfg.short_wake_threshold_min = body.short_wake_threshold_min
    if body.classifier:
        cfg.classifier = body.classifier

    epochs = [
        Epoch(
            timestamp=_parse_dt(e.timestamp, "epoch.timestamp"),
            activity_count=float(e.activity_count),
            heart_rate=e.heart_rate,
        )
        for e in body.epochs
    ]
    session = run_pipeline(epochs, body.user_id, cfg=cfg)
    if session is None:
        return {"session": None, "detail": "這段訊號在夜間時段內沒有偵測到睡眠"}

    sb = get_supabase()
    try:
        result = sb.table("sleep_sessions").insert(session).execute()
        saved = result.data[0] if result.data else session
    except Exception as e:
        logger.error(f"ingest insert failed: {e}")
        raise HTTPException(status_code=400, detail="睡眠紀錄寫入失敗")
    return {"session": saved}


# ── 手動補登 / 外部匯入 ───────────────────────────────────

@router.post("/sessions")
def create_session(body: SleepSessionCreate):
    if body.source not in {"manual", "imported"}:
        raise HTTPException(status_code=400, detail="source 只能是 manual 或 imported")
    bed = _parse_dt(body.bed_time, "bed_time")
    onset = _parse_dt(body.sleep_onset, "sleep_onset")
    wake = _parse_dt(body.wake_time, "wake_time")
    oob = _parse_dt(body.out_of_bed_time, "out_of_bed_time") if body.out_of_bed_time else None
    if not (bed <= onset <= wake):
        raise HTTPException(status_code=400, detail="時間順序需為 bed_time ≤ sleep_onset ≤ wake_time")

    metrics = compute_metrics_from_times(
        bed, onset, wake,
        waso_minutes=body.waso_minutes,
        awakenings_count=body.awakenings_count,
        out_of_bed_time=oob,
    )
    row = {
        "user_id": body.user_id,
        "bed_time": bed.isoformat(),
        "sleep_onset": onset.isoformat(),
        "wake_time": wake.isoformat(),
        "out_of_bed_time": oob.isoformat() if oob else None,
        "source": body.source,
        "is_edited": False,
        **metrics,
    }
    sb = get_supabase()
    try:
        result = sb.table("sleep_sessions").insert(row).execute()
    except Exception as e:
        logger.error(f"create sleep session failed: {e}")
        raise HTTPException(status_code=400, detail="睡眠紀錄寫入失敗")
    return result.data[0] if result.data else row


@router.get("/sessions")
def list_sessions(
    user_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(120, ge=1, le=500),
):
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    try:
        rows = (
            sb.table("sleep_sessions").select("*")
            .eq("user_id", user_id)
            .gte("bed_time", since)
            .order("bed_time", desc=True)
            .execute().data or []
        )
    except Exception as e:
        logger.info(f"list sleep sessions: {e}")
        rows = []
    return {"sessions": rows[:limit]}


@router.get("/today")
def today(user_id: str = Query(...)):
    """今日睡眠卡：回傳最近一筆 session（規格 §5.1）。"""
    sb = get_supabase()
    try:
        rows = (
            sb.table("sleep_sessions").select("*")
            .eq("user_id", user_id)
            .order("bed_time", desc=True)
            .limit(1)
            .execute().data or []
        )
    except Exception:
        rows = []
    return {"session": rows[0] if rows else None}


@router.put("/sessions/{session_id}")
def edit_session(session_id: str, body: SleepSessionEdit):
    """手動修正一筆紀錄：保留原值於 sleep_edits log、is_edited=true、重算指標。"""
    sb = get_supabase()
    existing = sb.table("sleep_sessions").select("*").eq("id", session_id).limit(1).execute().data
    if not existing:
        raise HTTPException(status_code=404, detail="找不到該睡眠紀錄")
    old = existing[0]

    bed = _parse_dt(body.bed_time, "bed_time") if body.bed_time else _parse_dt(old["bed_time"], "bed_time")
    onset = _parse_dt(body.sleep_onset, "sleep_onset") if body.sleep_onset else _parse_dt(old["sleep_onset"], "sleep_onset")
    wake = _parse_dt(body.wake_time, "wake_time") if body.wake_time else _parse_dt(old["wake_time"], "wake_time")
    oob = None
    oob_src = body.out_of_bed_time if body.out_of_bed_time is not None else old.get("out_of_bed_time")
    if oob_src:
        oob = _parse_dt(oob_src, "out_of_bed_time")
    if not (bed <= onset <= wake):
        raise HTTPException(status_code=400, detail="時間順序需為 bed_time ≤ sleep_onset ≤ wake_time")

    waso = body.waso_minutes if body.waso_minutes is not None else old.get("waso_minutes", 0)
    awk = body.awakenings_count if body.awakenings_count is not None else old.get("awakenings_count", 0)
    metrics = compute_metrics_from_times(bed, onset, wake, waso_minutes=waso, awakenings_count=awk, out_of_bed_time=oob)

    # 保留原值於 log（供研究端比對 auto vs 修正的差異，規格 §4）
    try:
        sb.table("sleep_edits").insert({
            "session_id": session_id,
            "user_id": old.get("user_id"),
            "previous_values": json.dumps(old, ensure_ascii=False, default=str),
            "edited_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        logger.warning(f"sleep_edits log skipped: {e}")

    update = {
        "bed_time": bed.isoformat(),
        "sleep_onset": onset.isoformat(),
        "wake_time": wake.isoformat(),
        "out_of_bed_time": oob.isoformat() if oob else None,
        "is_edited": True,
        "updated_at": datetime.utcnow().isoformat(),
        **metrics,
    }
    result = sb.table("sleep_sessions").update(update).eq("id", session_id).execute()
    return result.data[0] if result.data else {**old, **update}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    sb = get_supabase()
    sb.table("sleep_sessions").delete().eq("id", session_id).execute()
    return {"deleted": session_id}


# ── 趨勢（規格 §5.3）──────────────────────────────────────

@router.get("/trend")
def trend(user_id: str = Query(...), days: int = Query(7, ge=1, le=90)):
    """近 N 天睡眠時數 / 效率折線資料 + 平均。純彙整，不做判讀。"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    try:
        rows = (
            sb.table("sleep_sessions").select("*")
            .eq("user_id", user_id)
            .gte("bed_time", since)
            .order("bed_time", desc=False)
            .execute().data or []
        )
    except Exception:
        rows = []

    points = [
        {
            "date": (r.get("wake_time") or r.get("bed_time") or "")[:10],
            "total_sleep_minutes": r.get("total_sleep_minutes"),
            "sleep_efficiency": r.get("sleep_efficiency"),
        }
        for r in rows
    ]
    tsm = [p["total_sleep_minutes"] for p in points if p["total_sleep_minutes"] is not None]
    eff = [p["sleep_efficiency"] for p in points if p["sleep_efficiency"] is not None]
    return {
        "days": days,
        "points": points,
        "avg_total_sleep_minutes": round(sum(tsm) / len(tsm)) if tsm else None,
        "avg_sleep_efficiency": round(sum(eff) / len(eff), 4) if eff else None,
        "count": len(points),
    }


# ── 匯出（規格 §5.6）──────────────────────────────────────

@router.get("/export.csv")
def export_csv(user_id: str = Query(...), days: int = Query(30, ge=1, le=365)):
    """匯出 CSV 供患者回診提供給醫護。純資料，無任何評語。"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    try:
        rows = (
            sb.table("sleep_sessions").select("*")
            .eq("user_id", user_id)
            .gte("bed_time", since)
            .order("bed_time", desc=True)
            .execute().data or []
        )
    except Exception:
        rows = []

    buf = io.StringIO()
    cols = [
        "bed_time", "sleep_onset", "wake_time", "out_of_bed_time",
        "total_sleep_minutes", "time_in_bed_minutes", "sleep_efficiency",
        "waso_minutes", "awakenings_count", "source", "is_edited",
    ]
    writer = csv.writer(buf)
    writer.writerow(cols)
    for r in rows:
        writer.writerow([r.get(c, "") for c in cols])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sleep_export_{user_id[:8]}.csv"'},
    )
