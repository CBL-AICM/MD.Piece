from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import logging

from backend.db import get_supabase
from backend.utils.triage_rules import check_emergency, EMERGENCY_SYMPTOMS
from backend.utils.baseline import calculate_baseline
from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()

# 雙層 AI 分流 - 規則引擎 + LLM 個人化基準線判斷


class TriageRequest(BaseModel):
    patient_id: str
    symptoms: list[str] = []
    temperature: float = 0
    is_immunosuppressed: bool = False
    pain_score: int | None = None
    emotion_score: int | None = None
    medication_taken: bool | None = None
    notes: str = ""


@router.post("/evaluate")
def evaluate_triage(body: TriageRequest):
    """
    雙層分流評估：
    第一層：規則引擎（急診清單觸發 → 直接 Emergency）
    第二層：LLM 依個人基準線判斷 Stable / Follow-up / Emergency
    """
    # 第一層：規則引擎
    is_emergency = check_emergency(
        symptoms=body.symptoms,
        is_immunosuppressed=body.is_immunosuppressed,
        temperature=body.temperature,
    )

    if is_emergency:
        triggered = [s for s in body.symptoms if s in EMERGENCY_SYMPTOMS]
        return {
            "result": "emergency",
            "layer": 1,
            "message": "偵測到緊急症狀，請立即就醫或撥打 119！",
            "triggered_symptoms": triggered,
            "temperature_alert": body.temperature >= 38.0 and body.is_immunosuppressed,
        }

    # 第二層：LLM 基準線比對
    sb = get_supabase()

    # 取得病患資訊
    patient_result = sb.table("patients").select("*").eq("id", body.patient_id).execute()
    patient = patient_result.data[0] if patient_result.data else {}

    # 組合今日數據
    today_data = {
        "symptoms": body.symptoms,
        "temperature": body.temperature,
        "pain_score": body.pain_score,
        "emotion_score": body.emotion_score,
        "medication_taken": body.medication_taken,
        "notes": body.notes,
    }

    system_prompt = (
        "你是 MD.Piece 的分流判斷助手。根據病患今日回報的數據，判斷其健康狀態。\n"
        "回覆格式必須是以下三種之一：\n"
        "- stable：今天狀況穩定，繼續按時服藥\n"
        "- follow_up：建議近期回診追蹤\n"
        "- emergency：建議立即就醫\n\n"
        "回覆格式：先寫判斷結果（stable/follow_up/emergency），換行後寫一句簡短說明。\n"
        "語氣溫暖、不恐嚇，用繁體中文。"
    )

    parts = [
        f"病患：{patient.get('name', '未知')}，{patient.get('age', '未知')}歲",
        "今日回報：",
        f"- 症狀：{', '.join(body.symptoms) if body.symptoms else '無特殊症狀'}",
    ]
    if body.temperature:
        parts.append(f"- 體溫：{body.temperature}°C")
    if body.pain_score is not None:
        parts.append(f"- 疼痛分數：{body.pain_score}/10")
    if body.emotion_score is not None:
        parts.append(f"- 情緒分數：{body.emotion_score}/5")
    med_status = "是" if body.medication_taken else "否" if body.medication_taken is not None else "未回報"
    parts.append(f"- 今日是否服藥：{med_status}")
    if body.notes:
        parts.append(f"- 備註：{body.notes}")
    user_message = "\n".join(parts)

    try:
        llm_response = call_claude(system_prompt, user_message)
        lines = llm_response.strip().split("\n", 1)
        result_tag = lines[0].strip().lower()

        if result_tag not in ("stable", "follow_up", "emergency"):
            result_tag = "stable"
        message = lines[1].strip() if len(lines) > 1 else "狀況評估完成"
    except Exception as e:
        logger.error(f"Triage LLM call failed: {e}")
        result_tag = "stable"
        message = "AI 分流暫時無法使用，根據您回報的症狀暫判為穩定，如有不適請就醫。"

    return {
        "result": result_tag,
        "layer": 2,
        "message": message,
        "today_data": today_data,
    }


@router.get("/baseline/{patient_id}")
def get_baseline(patient_id: str):
    """取得個人化基準線：根據近兩週情緒與服藥紀錄計算"""
    sb = get_supabase()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=14)).isoformat()

    # 取得情緒紀錄
    emotions = sb.table("emotions").select("*").eq("patient_id", patient_id).gte("created_at", since).execute().data or []

    # 取得服藥紀錄
    med_logs = sb.table("medication_logs").select("*").eq("patient_id", patient_id).gte("taken_at", since).execute().data or []

    # 組合成 baseline 計算格式
    records = []
    for e in emotions:
        records.append({
            "emotion": e.get("score", 3),
            "pain": 0,
            "medication_rate": 1.0,
        })

    if med_logs:
        total = len(med_logs)
        taken = sum(1 for l in med_logs if l.get("taken"))
        med_rate = taken / total if total else 1.0
        for r in records:
            r["medication_rate"] = med_rate

    baseline = calculate_baseline(records)

    return {
        "baseline": baseline,
        "data_points": len(records),
        "period_days": 14,
    }


@router.get("/emergency-symptoms")
def list_emergency_symptoms():
    """列出所有觸發急診的症狀清單"""
    return {"symptoms": EMERGENCY_SYMPTOMS}
