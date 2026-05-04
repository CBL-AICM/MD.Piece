from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, date

from backend.db import get_supabase

SCORE_EMOJI = {1: "😢", 2: "😟", 3: "😐", 4: "🙂", 5: "😄"}

router = APIRouter()

# 情緒記錄 - 每日評分、靜默守護機制、心理危機偵測


class EmotionLog(BaseModel):
    patient_id: str
    score: int  # 1-5，1 最低落、5 最好
    note: str = ""


@router.get("/")
def get_emotions(
    patient_id: str = Query(...),
    days: int = Query(30, description="查詢最近幾天"),
):
    """取得病患的情緒紀錄"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = sb.table("emotions").select("*").eq("patient_id", patient_id).gte("created_at", since).order("created_at", desc=True).execute()
    return {"emotions": result.data}


@router.post("/")
def log_emotion(body: EmotionLog):
    """記錄今日情緒"""
    if body.score < 1 or body.score > 5:
        raise HTTPException(status_code=400, detail="score 必須在 1-5 之間")
    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "score": body.score,
        "note": body.note,
    }
    result = sb.table("emotions").insert(data).execute()
    return result.data[0]


@router.get("/silent-guardian")
def check_silent_guardian(patient_id: str = Query(...)):
    """
    靜默守護：偵測連續低落情緒，觸發心理危機提醒。
    規則：最近 7 天中有 3 天以上 score <= 2 → 觸發警示
    """
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()
    result = sb.table("emotions").select("*").eq("patient_id", patient_id).gte("created_at", since).order("created_at", desc=True).execute()
    records = result.data or []

    low_count = sum(1 for r in records if r.get("score", 5) <= 2)
    alert = low_count >= 3

    return {
        "alert": alert,
        "low_days": low_count,
        "total_records": len(records),
        "message": "偵測到連續低落情緒，建議關懷此病患" if alert else "情緒狀態正常",
    }


@router.get("/daily")
def get_daily_mood(
    patient_id: str = Query(...),
    days: int = Query(30, ge=1, le=365, description="查詢最近幾天"),
):
    """
    每日心情彙整：將同一天的多筆紀錄聚合為一筆，便於日曆/時間軸顯示。

    每日回傳：日期、平均分數（四捨五入）、最高/最低分數、表情符號、
    當日最後一則 note、紀錄筆數。缺漏的日期不會補零。
    """
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .order("created_at")
        .execute()
    )
    records = result.data or []

    by_day: dict[str, list[dict]] = {}
    for r in records:
        day = (r.get("created_at") or "")[:10]
        if not day:
            continue
        by_day.setdefault(day, []).append(r)

    daily = []
    for day in sorted(by_day.keys()):
        items = by_day[day]
        scores = [it.get("score") for it in items if it.get("score") is not None]
        if not scores:
            continue
        avg = round(sum(scores) / len(scores), 1)
        last_note = next(
            (it.get("note") for it in reversed(items) if it.get("note")), ""
        )
        daily.append({
            "date": day,
            "average_score": avg,
            "max_score": max(scores),
            "min_score": min(scores),
            "emoji": SCORE_EMOJI.get(round(avg), "😐"),
            "note": last_note,
            "count": len(items),
        })

    all_scores = [s for d in daily for s in [d["average_score"]]]
    overall_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else None

    return {
        "patient_id": patient_id,
        "days": days,
        "daily": daily,
        "days_logged": len(daily),
        "overall_average": overall_avg,
    }


@router.get("/trend")
def get_emotion_trend(
    patient_id: str = Query(...),
    days: int = Query(30),
):
    """取得情緒趨勢資料（用於圖表）"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    result = sb.table("emotions").select("*").eq("patient_id", patient_id).gte("created_at", since).order("created_at").execute()
    records = result.data or []

    trend = [
        {
            "date": r.get("created_at", "")[:10],
            "score": r.get("score"),
        }
        for r in records
    ]

    scores = [r.get("score", 0) for r in records if r.get("score")]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    return {
        "trend": trend,
        "average_score": avg_score,
        "total_records": len(records),
        "days": days,
    }
