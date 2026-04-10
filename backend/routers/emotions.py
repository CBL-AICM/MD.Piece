import statistics
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase

router = APIRouter()

# 情緒記錄 - 每日評分、靜默守護機制、心理危機偵測

SILENT_GUARDIAN_THRESHOLD = 3  # 連續幾筆低落才觸發警示
LOW_EMOTION_SCORE = 2          # <= 此分數視為「低落」


class EmotionLog(BaseModel):
    patient_id: str
    score: int          # 1-5, 1 最低落, 5 最好
    note: str = ""


# ── CRUD ─────────────────────────────────────────────────────


@router.get("/")
def get_emotions(
    patient_id: str = Query(...),
    days: int = Query(30, description="查詢最近幾天"),
):
    """取得患者的情緒記錄"""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .execute()
    )
    return {"emotions": result.data}


@router.post("/")
def log_emotion(body: EmotionLog):
    """記錄每日情緒（1-5 分）"""
    if body.score < 1 or body.score > 5:
        raise HTTPException(status_code=400, detail="score 必須在 1-5 之間")

    sb = get_supabase()
    data = {"patient_id": body.patient_id, "score": body.score, "note": body.note}
    result = sb.table("emotions").insert(data).execute()

    response = result.data[0] if result.data else data

    # 插入後立即檢查靜默守護者
    guardian = _check_silent_guardian(sb, body.patient_id)
    if guardian["alert"]:
        response["silent_guardian_alert"] = guardian

    return response


# ── 靜默守護者 ───────────────────────────────────────────────


@router.get("/silent-guardian")
def check_silent_guardian(patient_id: str = Query(...)):
    """靜默守護者：偵測連續低落情緒，觸發心理危機提醒"""
    sb = get_supabase()
    return _check_silent_guardian(sb, patient_id)


def _check_silent_guardian(sb, patient_id: str) -> dict:
    """內部：檢查最近連續低落筆數"""
    result = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(SILENT_GUARDIAN_THRESHOLD)
        .execute()
    )
    records = result.data or []

    if len(records) < SILENT_GUARDIAN_THRESHOLD:
        return {
            "alert": False,
            "consecutive_low": len([r for r in records if r.get("score", 5) <= LOW_EMOTION_SCORE]),
            "message": "資料不足，尚無法判斷",
        }

    consecutive_low = 0
    for record in records:
        if record.get("score", 5) <= LOW_EMOTION_SCORE:
            consecutive_low += 1
        else:
            break

    if consecutive_low >= SILENT_GUARDIAN_THRESHOLD:
        return {
            "alert": True,
            "level": "warning",
            "consecutive_low": consecutive_low,
            "message": (
                f"注意：此患者已連續 {consecutive_low} 次記錄低落情緒"
                f"（<= {LOW_EMOTION_SCORE} 分），建議關注心理狀態。"
            ),
            "suggestion": "建議安排心理諮商或聯繫關懷人員",
        }

    return {
        "alert": False,
        "consecutive_low": consecutive_low,
        "message": "目前情緒狀態穩定",
    }


# ── 統計 ─────────────────────────────────────────────────────


@router.get("/stats")
def emotion_stats(
    patient_id: str = Query(...),
    days: int = Query(30),
):
    """情緒統計：平均值、趨勢、分佈"""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .order("created_at")
        .execute()
    )
    records = result.data or []

    if not records:
        return {"summary": {"count": 0, "days": days}, "trend": [], "distribution": {}}

    scores = [r["score"] for r in records if "score" in r]
    distribution = {i: scores.count(i) for i in range(1, 6)}

    return {
        "summary": {
            "count": len(scores),
            "mean": round(statistics.mean(scores), 1) if scores else 0,
            "median": statistics.median(scores) if scores else 0,
            "min": min(scores) if scores else 0,
            "max": max(scores) if scores else 0,
            "days": days,
        },
        "trend": [
            {
                "date": r.get("created_at", "")[:10],
                "score": r.get("score"),
                "note": r.get("note", ""),
            }
            for r in records
        ],
        "distribution": distribution,
    }
