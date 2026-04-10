import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import get_supabase
from backend.services.llm_service import call_claude
from backend.utils.baseline import calculate_baseline
from backend.utils.triage_rules import EMERGENCY_SYMPTOMS, check_emergency

logger = logging.getLogger(__name__)
router = APIRouter()

# 雙層 AI 分流：規則引擎 + LLM 個人化基準線判斷

TRIAGE_SYSTEM_PROMPT = (
    "你是 MD.Piece 平台的智慧分診助手。\n"
    "根據患者今日的症狀數據和個人化基準線，判斷患者狀態。\n\n"
    "判斷等級：\n"
    "- stable：狀況穩定，繼續按時服藥和追蹤\n"
    "- follow_up：有偏離基準的趨勢，建議提早回診\n"
    "- emergency：需要立即就醫（此等級通常由規則引擎處理）\n\n"
    "回覆必須是純 JSON 格式（不要 markdown code block）：\n"
    '{"result": "stable/follow_up/emergency", '
    '"message": "給患者的一句話說明（繁體中文、溫暖語氣）", '
    '"details": "給醫療人員的專業判斷依據（簡潔）", '
    '"concerns": ["需要關注的項目"]}\n\n'
    "判斷原則：\n"
    "1. 今日數據在基準線正常範圍 -> stable\n"
    "2. 疼痛、情緒、服藥率偏離基準 1 個標準差以上 -> follow_up\n"
    "3. 語氣溫暖，不要嚇患者\n"
    "4. 偏保守 — 寧可提早回診，不要漏掉警訊"
)


class TriageRequest(BaseModel):
    patient_id: str
    symptoms: list[str] = []
    pain_score: int | None = None       # 1-10
    temperature: float | None = None    # 體溫 (°C)
    is_immunosuppressed: bool = False
    emotion_score: int | None = None    # 1-5
    medication_taken: bool | None = None


# ── 分診評估 ─────────────────────────────────────────────────


@router.post("/evaluate")
def evaluate_triage(body: TriageRequest):
    """雙層分診評估：規則引擎 → LLM 個人化判斷"""

    # ── 第一層：規則引擎 — 急診直接攔截 ──
    temp = body.temperature or 0
    if check_emergency(body.symptoms, body.is_immunosuppressed, temp):
        matched = [s for s in body.symptoms if s in EMERGENCY_SYMPTOMS]
        return {
            "result": "emergency",
            "layer": "rule_engine",
            "message": "偵測到緊急症狀，請立即就醫或撥打 119！",
            "details": f"觸發急診規則：{', '.join(matched) if matched else '免疫抑制合併發燒'}",
            "concerns": matched or ["免疫抑制合併發燒"],
        }

    # ── 第二層：LLM + 個人化基準線 ──
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

    emotion_records = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", body.patient_id)
        .gte("created_at", since)
        .order("created_at")
        .execute()
    )
    med_logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", body.patient_id)
        .gte("taken_at", since)
        .execute()
    )

    emotion_data = emotion_records.data or []
    med_data = med_logs.data or []

    # 建立基準線數據
    baseline_records = []
    total_meds = len(med_data) if med_data else 0
    taken_meds = sum(1 for m in med_data if m.get("taken"))
    med_rate = taken_meds / total_meds if total_meds else 1.0

    for e in emotion_data:
        record = {"emotion": e.get("score", 3), "medication_rate": med_rate}
        if body.pain_score is not None:
            record["pain"] = body.pain_score
        baseline_records.append(record)

    baseline = calculate_baseline(baseline_records) if baseline_records else {}

    # 組合今日數據摘要
    today_parts = ["患者今日狀態："]
    today_parts.append(f"- 症狀：{', '.join(body.symptoms) if body.symptoms else '無特別症狀'}")
    if body.pain_score is not None:
        today_parts.append(f"- 疼痛評分：{body.pain_score}/10")
    if body.temperature:
        today_parts.append(f"- 體溫：{body.temperature} C")
    if body.emotion_score is not None:
        today_parts.append(f"- 情緒評分：{body.emotion_score}/5")
    if body.medication_taken is not None:
        today_parts.append(f"- 今日服藥：{'已服藥' if body.medication_taken else '未服藥'}")

    if baseline:
        today_parts.append("\n個人化基準線（近兩週平均）：")
        if baseline.get("pain_mean") is not None:
            today_parts.append(
                f"- 疼痛平均：{baseline['pain_mean']:.1f}"
                f"（標準差 {baseline['pain_stdev']:.1f}）"
            )
        if baseline.get("emotion_mean") is not None:
            today_parts.append(f"- 情緒平均：{baseline['emotion_mean']:.1f}")
        if baseline.get("medication_rate_mean") is not None:
            today_parts.append(f"- 服藥率平均：{baseline['medication_rate_mean']:.0%}")
    else:
        today_parts.append("\n（尚無足夠的歷史數據建立基準線）")

    today_summary = "\n".join(today_parts)

    try:
        raw = call_claude(TRIAGE_SYSTEM_PROMPT, today_summary)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        llm_result = json.loads(raw)
    except Exception as e:
        logger.warning(f"Triage LLM failed: {e}")
        llm_result = {
            "result": "stable",
            "message": "系統暫時無法進行 AI 分析，建議您依平時狀態判斷。如有不適請聯繫醫師。",
            "details": f"LLM 分析失敗：{e}",
            "concerns": [],
        }

    llm_result["layer"] = "llm_baseline"
    llm_result["baseline"] = baseline
    return llm_result


# ── 基準線查詢 ───────────────────────────────────────────────


@router.get("/baseline/{patient_id}")
def get_baseline(patient_id: str):
    """取得個人化基準線：前兩週症狀 / 服藥 / 情緒平均值"""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

    emotions = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
    )
    med_logs = (
        sb.table("medication_logs")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("taken_at", since)
        .execute()
    )

    emotion_data = emotions.data or []
    med_data = med_logs.data or []

    baseline_records = []
    total = len(med_data) if med_data else 0
    taken = sum(1 for m in med_data if m.get("taken"))

    for e in emotion_data:
        record = {"emotion": e.get("score", 3)}
        if total:
            record["medication_rate"] = taken / total
        baseline_records.append(record)

    baseline = calculate_baseline(baseline_records) if baseline_records else {}

    return {
        "patient_id": patient_id,
        "baseline": baseline,
        "data_points": {
            "emotion_records": len(emotion_data),
            "medication_logs": len(med_data),
        },
        "period": "14 days",
    }
