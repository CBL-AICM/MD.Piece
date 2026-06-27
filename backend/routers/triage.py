from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import logging

from backend.db import get_supabase
from backend.security import current_user_optional, enforce_patient_scope
from backend.utils.triage_rules import check_emergency, matched_emergency_symptoms
from backend.utils.baseline import calculate_baseline
from backend.services.llm_service import (
    build_patient_facing_system,
    call_claude,
    compute_patient_context,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Severity color mapping ──────────────────────────────────
# 對應台灣分級醫療 5 級，前端用 data-severity attribute + CSS var(--sev-*)
# 詳見 docs/research/ui_color_research.md §4
SEVERITY_COLOR_MAP = {
    "emergency": "er",         # 急診（紅，用點不用面）
    "follow_up": "regional",   # 區域醫院（深海軍）
    "stable":    "self",       # 自我照護（綠）
}


def severity_color_for(result_tag: str) -> str:
    """把 triage 結果對應到 severity token 名稱。
    回傳值前端會掛到 data-severity，CSS 解析為 var(--sev-<name>)。
    """
    return SEVERITY_COLOR_MAP.get(result_tag, "self")


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
def evaluate_triage(body: TriageRequest, me: dict | None = Depends(current_user_optional)):
    """
    雙層分流評估：
    第一層：規則引擎（急診清單觸發 → 直接 Emergency）
    第二層：LLM 依個人基準線判斷 Stable / Follow-up / Emergency
    """
    # 已登入時只能評估自己的 patient_id（demo 匿名放行，比照 symptoms.py）
    enforce_patient_scope(body.patient_id, me)

    # 第一層：規則引擎
    is_emergency = check_emergency(
        symptoms=body.symptoms,
        is_immunosuppressed=body.is_immunosuppressed,
        temperature=body.temperature,
    )

    if is_emergency:
        triggered = matched_emergency_symptoms(body.symptoms)
        return {
            "result": "emergency",
            "severity_color": severity_color_for("emergency"),
            "layer": 1,
            "message": "偵測到緊急症狀，請立即就醫或撥打 119！",
            "triggered_symptoms": triggered,
            "temperature_alert": body.temperature >= 38.0 and body.is_immunosuppressed,
        }

    # 第二層：LLM 基準線比對
    sb = get_supabase()

    # 取得病患資訊（只取分流 prompt 用得到的欄位，不撈整列）
    patient_result = sb.table("patients").select("name,age").eq("id", body.patient_id).execute()
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

    # 風格層管「對病人講話的口吻」；這裡只描述「這次任務要產出什麼結構」。
    triage_role = (
        "【本次任務：分流判斷】\n"
        "根據病患今日回報的數據，判斷分流結果，輸出固定格式。\n\n"
        "輸出格式（嚴格遵守）：\n"
        "  第 1 行：判斷標籤，只能是以下三種之一（小寫、不含其他字）：\n"
        "    - stable      ：跟平常差不多，照原本方式繼續\n"
        "    - follow_up   ：這幾天的訊號比較需要醫師看一下，建議近期回診\n"
        "    - emergency   ：請現在就到急診 / 撥 119\n"
        "  第 2 行起：一段給病人看的白話說明（1~2 句）。\n\n"
        "說明文字一律遵守風格層 [A][B][C] 的所有規則，特別是：\n"
        "  - 不要丟百分比 / 分數 / 風險指數\n"
        "  - 不要說「你今天又…」「你沒有…」這種審判口吻\n"
        "  - 不要說「沒事啦放心」這類假保證\n"
        "  - follow_up / emergency 時要明確「請醫師看」，不要替醫師判斷可以不用看"
    )
    patient_ctx = compute_patient_context(body.patient_id)
    system_prompt = build_patient_facing_system(
        triage_role,
        patient_context=patient_ctx,
        include_examples=False,  # 輸出格式很固定，example 反而會誤導
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

    # 失敗（LLM 例外 / tag 無法解析）時的安全收斂：醫療場景不可假綠燈，
    # 一律保守降到 follow_up（建議回診）並標記 degraded，讓前端/病人知道
    # 這不是完整分流結論，而非沿用 LLM 任意輸出當權威說明。
    DEGRADED_MESSAGE = "目前暫時無法完整分流，這不是完整評估結果；若您感到不適，請就醫由醫師判斷。"
    degraded = False
    try:
        llm_response = call_claude(system_prompt, user_message)
        lines = llm_response.strip().split("\n", 1)
        result_tag = lines[0].strip().lower()

        if result_tag not in ("stable", "follow_up", "emergency"):
            logger.error(f"Triage LLM 回傳非法 tag，保守降為 follow_up：{result_tag!r}")
            result_tag = "follow_up"
            degraded = True
            message = DEGRADED_MESSAGE
        else:
            message = lines[1].strip() if len(lines) > 1 else "狀況評估完成"
    except Exception as e:
        logger.error(f"Triage LLM call failed: {e}")
        result_tag = "follow_up"
        degraded = True
        message = DEGRADED_MESSAGE

    return {
        "result": result_tag,
        "severity_color": severity_color_for(result_tag),
        "layer": 2,
        "message": message,
        "degraded": degraded,
        "today_data": today_data,
    }


@router.get("/baseline/{patient_id}")
def get_baseline(patient_id: str, me: dict | None = Depends(current_user_optional)):
    """取得個人化基準線：根據近兩週情緒與服藥紀錄計算"""
    # 已登入時只能讀自己的基準線（demo 匿名放行，比照 symptoms.py）
    enforce_patient_scope(patient_id, me)
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
