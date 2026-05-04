from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from backend.db import get_supabase

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
    """記錄今日情緒；若連續低落則自動建立警示。"""
    if body.score < 1 or body.score > 5:
        raise HTTPException(status_code=400, detail="score 必須在 1-5 之間")
    sb = get_supabase()
    data = {
        "patient_id": body.patient_id,
        "score": body.score,
        "note": body.note,
    }
    result = sb.table("emotions").insert(data).execute()

    # ── 自動警示：近 7 天 score<=2 達 3 天 → 建立 low_mood 警示 ─────
    try:
        if body.score <= 2:
            since = (datetime.utcnow() - timedelta(days=7)).isoformat()
            recent = (
                sb.table("emotions").select("score,created_at")
                .eq("patient_id", body.patient_id).gte("created_at", since)
                .execute().data or []
            )
            low_count = sum(1 for r in recent if (r.get("score") or 5) <= 2)
            if low_count >= 3:
                # 24 小時內已有相同 alert 就不重複
                day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
                existing = (
                    sb.table("alerts").select("id")
                    .eq("patient_id", body.patient_id)
                    .eq("alert_type", "low_mood")
                    .eq("resolved", 0)
                    .gte("created_at", day_ago)
                    .limit(1).execute().data or []
                )
                if not existing:
                    sb.table("alerts").insert({
                        "patient_id": body.patient_id,
                        "alert_type": "low_mood",
                        "severity": "medium" if low_count == 3 else "high",
                        "title": f"連續情緒低落（近 7 天 {low_count} 天 ≤ 2 分）",
                        "detail": "建議於下次回診評估心理狀態，必要時轉介心理諮商。",
                        "acknowledged": 0,
                        "resolved": 0,
                    }).execute()
    except Exception:
        # 警示寫失敗不影響情緒紀錄主流程
        pass

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
