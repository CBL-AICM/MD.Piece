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

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel

from backend.db import get_supabase
from backend.security import current_user_optional, enforce_patient_scope
from backend.services import wearable_sync
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
def ingest(body: IngestRequest, me: dict | None = Depends(current_user_optional)):
    """跑判睡 pipeline，輸出並存入一筆 auto SleepSession。"""
    enforce_patient_scope(body.user_id, me)
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
def create_session(body: SleepSessionCreate, me: dict | None = Depends(current_user_optional)):
    enforce_patient_scope(body.user_id, me)
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
    me: dict | None = Depends(current_user_optional),
):
    enforce_patient_scope(user_id, me)
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
def today(user_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    """今日睡眠卡：回傳最近一筆 session（規格 §5.1）。"""
    enforce_patient_scope(user_id, me)
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
def edit_session(session_id: str, body: SleepSessionEdit, me: dict | None = Depends(current_user_optional)):
    """手動修正一筆紀錄：保留原值於 sleep_edits log、is_edited=true、重算指標。"""
    sb = get_supabase()
    existing = sb.table("sleep_sessions").select("*").eq("id", session_id).limit(1).execute().data
    if not existing:
        raise HTTPException(status_code=404, detail="找不到該睡眠紀錄")
    old = existing[0]
    enforce_patient_scope(old.get("user_id"), me)

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
def delete_session(session_id: str, me: dict | None = Depends(current_user_optional)):
    sb = get_supabase()
    existing = sb.table("sleep_sessions").select("user_id").eq("id", session_id).limit(1).execute().data
    if existing:
        enforce_patient_scope(existing[0].get("user_id"), me)
    sb.table("sleep_sessions").delete().eq("id", session_id).execute()
    return {"deleted": session_id}


# ── 穿戴裝置雲端同步（廠商 OAuth，參考實作：Fitbit）──────────
#
# source=imported 的真正來源：使用者授權後，後端用廠商雲端 API 拉睡眠紀錄。
# OAuth token 是機密，只存後端 wearable_connections 表、絕不回給前端。
# 真正要上線需在部署環境設 FITBIT_CLIENT_ID / FITBIT_CLIENT_SECRET（規則 12）。


class SyncRequest(BaseModel):
    user_id: str
    days: int = 7


def _get_connection(sb, user_id: str, provider: str):
    try:
        rows = (
            sb.table("wearable_connections").select("*")
            .eq("user_id", user_id).eq("provider", provider)
            .limit(1).execute().data or []
        )
        return rows[0] if rows else None
    except Exception as e:
        logger.info(f"get wearable connection: {e}")
        return None


def _upsert_connection(sb, user_id: str, provider: str, tok: dict):
    """有則更新、無則新增（query builder 無 upsert，這裡手動做）。"""
    existing = _get_connection(sb, user_id, provider)
    payload = {
        "user_id": user_id,
        "provider": provider,
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "scope": tok.get("scope"),
        "expires_at": tok.get("expires_at"),
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing:
        sb.table("wearable_connections").update(payload).eq("id", existing["id"]).execute()
    else:
        sb.table("wearable_connections").insert(payload).execute()


def _token_expired(exp_iso: Optional[str]) -> bool:
    if not exp_iso:
        return True
    try:
        exp = datetime.fromisoformat(exp_iso)
    except ValueError:
        return True
    now = datetime.now(exp.tzinfo) if exp.tzinfo else datetime.utcnow()
    return now >= exp - timedelta(seconds=60)


@router.get("/providers")
def list_providers():
    """前端據此顯示可連接的穿戴裝置與其是否已備好金鑰。"""
    return {
        "providers": [
            {
                "id": wearable_sync.PROVIDER,
                "name": "Fitbit",
                "configured": wearable_sync.is_configured(),
            }
        ]
    }


@router.get("/connections")
def list_connections(user_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    """使用者已連接哪些 provider（只回 provider 與時間，不外流 token）。"""
    enforce_patient_scope(user_id, me)
    sb = get_supabase()
    try:
        rows = (
            sb.table("wearable_connections").select("*")
            .eq("user_id", user_id).execute().data or []
        )
    except Exception:
        rows = []
    return {
        "connections": [
            {"provider": r.get("provider"), "updated_at": r.get("updated_at")}
            for r in rows
        ]
    }


@router.get("/connect/fitbit/start")
def fitbit_start(user_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    """回傳 Fitbit 授權頁 URL；未設定金鑰時 loud-fail（規則 12）。"""
    enforce_patient_scope(user_id, me)
    if not wearable_sync.is_configured():
        raise HTTPException(
            status_code=503,
            detail="尚未設定 Fitbit 連接（缺 FITBIT_CLIENT_ID / FITBIT_CLIENT_SECRET）。"
                   "請於部署環境補上後再試。",
        )
    return {"authorize_url": wearable_sync.build_authorize_url(user_id)}


@router.get("/connect/fitbit/callback")
def fitbit_callback(code: str = Query(""), state: str = Query("")):
    """Fitbit 導回：驗 state → 授權碼換 token → 存連線 → 導回前端。"""
    if not wearable_sync.is_configured():
        return RedirectResponse(url="/?sleep_connect=error")
    user_id = wearable_sync.parse_state(state)
    if not user_id or not code:
        return RedirectResponse(url="/?sleep_connect=error")
    try:
        tok = wearable_sync.exchange_code(code)
        _upsert_connection(get_supabase(), user_id, wearable_sync.PROVIDER, tok)
    except Exception as e:
        logger.error(f"fitbit callback failed: {e}")
        return RedirectResponse(url="/?sleep_connect=error")
    return RedirectResponse(url="/?sleep_connect=ok")


@router.post("/sync/fitbit")
def fitbit_sync(body: SyncRequest, me: dict | None = Depends(current_user_optional)):
    """拉近 N 天 Fitbit 睡眠紀錄，映射成 imported session 存後台（去重）。"""
    enforce_patient_scope(body.user_id, me)
    if not wearable_sync.is_configured():
        raise HTTPException(status_code=503, detail="尚未設定 Fitbit 連接，無法同步。")
    sb = get_supabase()
    conn = _get_connection(sb, body.user_id, wearable_sync.PROVIDER)
    if not conn:
        raise HTTPException(status_code=400, detail="尚未連接 Fitbit，請先完成授權。")

    access_token = conn.get("access_token")
    if _token_expired(conn.get("expires_at")):
        if not conn.get("refresh_token"):
            raise HTTPException(status_code=401, detail="Fitbit 授權已過期，請重新連接。")
        try:
            tok = wearable_sync.refresh(conn["refresh_token"])
            _upsert_connection(sb, body.user_id, wearable_sync.PROVIDER, tok)
            access_token = tok["access_token"]
        except Exception as e:
            logger.error(f"fitbit refresh failed: {e}")
            raise HTTPException(status_code=401, detail="Fitbit 重新授權失敗，請重新連接。")

    days = max(1, min(int(body.days or 7), 100))
    end_d = datetime.utcnow().date()
    start_d = end_d - timedelta(days=days)
    try:
        logs = wearable_sync.fetch_sleep(access_token, start_d.isoformat(), end_d.isoformat())
    except Exception as e:
        logger.error(f"fitbit fetch failed: {e}")
        raise HTTPException(status_code=502, detail="向 Fitbit 取得睡眠資料失敗，請稍後再試。")

    # 去重：已匯入過（同分鐘 bed_time）的就跳過，避免重覆同步灌入重複列。
    since = (datetime.utcnow() - timedelta(days=days + 1)).isoformat()
    existing = (
        sb.table("sleep_sessions").select("*")
        .eq("user_id", body.user_id).gte("bed_time", since).execute().data or []
    )
    seen = {(r.get("bed_time") or "")[:16] for r in existing if r.get("source") == "imported"}

    synced = 0
    skipped = 0
    for log in logs:
        row = wearable_sync.map_fitbit_sleep_to_session(log, body.user_id)
        if row["bed_time"][:16] in seen:
            skipped += 1
            continue
        try:
            sb.table("sleep_sessions").insert(row).execute()
            seen.add(row["bed_time"][:16])
            synced += 1
        except Exception as e:
            logger.warning(f"insert imported session skipped: {e}")
    return {"synced": synced, "skipped": skipped, "provider": wearable_sync.PROVIDER}


@router.delete("/connections/{provider}")
def disconnect(provider: str, user_id: str = Query(...), me: dict | None = Depends(current_user_optional)):
    """中斷某 provider 連線（刪 token；已匯入的睡眠紀錄保留）。"""
    enforce_patient_scope(user_id, me)
    sb = get_supabase()
    try:
        sb.table("wearable_connections").delete().eq("user_id", user_id).eq("provider", provider).execute()
    except Exception as e:
        logger.info(f"disconnect: {e}")
    return {"disconnected": provider}


# ── 趨勢（規格 §5.3）──────────────────────────────────────

@router.get("/trend")
def trend(user_id: str = Query(...), days: int = Query(7, ge=1, le=90),
          me: dict | None = Depends(current_user_optional)):
    """近 N 天睡眠時數 / 效率折線資料 + 平均。純彙整，不做判讀。"""
    enforce_patient_scope(user_id, me)
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
def export_csv(user_id: str = Query(...), days: int = Query(30, ge=1, le=365),
               me: dict | None = Depends(current_user_optional)):
    """匯出 CSV 供患者回診提供給醫護。純資料，無任何評語。"""
    enforce_patient_scope(user_id, me)
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
