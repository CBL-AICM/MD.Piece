import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import get_supabase
from backend.services.llm_service import call_claude
from backend.utils.baseline import (
    build_baseline_from_db,
    compare_to_baseline,
    ESCALATION_DAYS,
)
from backend.utils.triage_rules import EMERGENCY_SYMPTOMS, check_emergency

logger = logging.getLogger(__name__)
router = APIRouter()

# 雙層 AI 分流 - 規則引擎 + LLM 個人化基準線判斷


class TriageRequest(BaseModel):
    patient_id: str
    symptoms: list[str] = []
    body_locations: list[str] = []
    severity_index: float | None = None  # 五層問卷算出來的嚴重度
    temperature: float = 0
    is_immunosuppressed: bool = False
    pain_score: int | None = None
    emotion_score: int | None = None
    medication_taken: bool | None = None
    notes: str = ""
    has_known_trigger: bool = False  # 患者自報「有明確誘因」（天氣、活動）→ 降低警戒


PATIENT_FRIENDLY_TEMPLATES = {
    "stable": "今天狀況穩定，繼續按時服藥，照常生活就好",
    "follow_up": "建議下次回診時告訴醫師最近的變化，或考慮提早預約",
    "emergency": "請立刻前往急診，或撥打 119",
}


@router.post("/evaluate")
def evaluate_triage(body: TriageRequest):
    """
    雙層分流評估：
    第一層：規則引擎（急診清單觸發 → 直接 Emergency）
    第二層：LLM 依個人基準線判斷 Stable / Follow-up / Emergency
    """
    # 第一層：規則引擎（包含免疫抑制+發燒）
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
            "patient_message": "請立刻前往急診，或撥打 119！",
            "doctor_message": f"觸發急診規則：{', '.join(triggered) if triggered else '免疫抑制+發燒'}",
            "triggered_symptoms": triggered,
            "temperature_alert": body.temperature >= 38.0 and body.is_immunosuppressed,
        }

    # 第二層：個人基準線比對 + LLM
    sb = get_supabase()

    # 病患資料
    patient_result = sb.table("patients").select("*").eq("id", body.patient_id).execute()
    patient = patient_result.data[0] if patient_result.data else {}

    # 計算個人基準線（前 14 天）
    baseline_data = build_baseline_from_db(sb, body.patient_id, days=14)
    baseline = baseline_data["baseline"]
    today = {
        "pain": body.severity_index if body.severity_index is not None else body.pain_score,
        "emotion": body.emotion_score,
        "locations": body.body_locations,
    }
    deviation = compare_to_baseline(today, baseline)

    # 連續惡化天數（升級邏輯：單次異常先觀察、ESCALATION_DAYS 才升級）
    streak_days = _consecutive_worsening_days(baseline_data["records"], body.severity_index)

    # 規則優先：偏離超過 2σ 且連續惡化 → 自動 follow-up
    auto_followup = False
    if deviation.get("deviation_pain") and deviation["deviation_pain"] >= 2 and streak_days >= ESCALATION_DAYS:
        auto_followup = True
    if deviation.get("new_locations"):
        auto_followup = True

    # 已知誘因 → 降低警戒
    if body.has_known_trigger and not auto_followup:
        result_tag = "stable"
        return {
            "result": result_tag,
            "layer": 2,
            "patient_message": "今天的不舒服看起來跟你提到的誘因有關，先觀察、好好休息",
            "doctor_message": "患者自報有已知誘因，當前數據未顯著偏離基準",
            "baseline": baseline,
            "deviation": deviation,
            "streak_days": streak_days,
        }

    # LLM 判斷
    system_prompt = (
        "你是 MD.Piece 的分流判斷助手。\n"
        "根據患者今日數據與其個人歷史基準線，判斷該回報為以下何者：\n"
        "- stable：今天狀況穩定，繼續按時服藥\n"
        "- follow_up：建議近期回診追蹤\n"
        "- emergency：建議立即就醫\n\n"
        "判斷重點：\n"
        "1. 以個人基準線為準，不比族群正常值\n"
        "2. 單次異常先觀察、連續 3 天以上才升級\n"
        "3. 出現從未有過的部位（new_locations）→ 至少 follow_up\n"
        "4. 偏離基準 2 個標準差以上 → 至少 follow_up\n"
        "5. 急診僅在生命徵象明確異常時觸發\n\n"
        "回覆格式：第一行只寫 stable / follow_up / emergency；"
        "第二行寫一句給患者的白話說明，溫暖、不恐嚇，繁體中文。"
    )

    user_message = _build_user_prompt(patient, body, baseline, deviation, streak_days)

    try:
        llm_response = call_claude(system_prompt, user_message)
        lines = llm_response.strip().split("\n", 1)
        result_tag = lines[0].strip().lower().replace("-", "_")
        if result_tag not in ("stable", "follow_up", "emergency"):
            result_tag = "follow_up" if auto_followup else "stable"
        message = lines[1].strip() if len(lines) > 1 else PATIENT_FRIENDLY_TEMPLATES[result_tag]
    except Exception as e:
        logger.error(f"Triage LLM call failed: {e}")
        result_tag = "follow_up" if auto_followup else "stable"
        message = PATIENT_FRIENDLY_TEMPLATES[result_tag]

    if auto_followup and result_tag == "stable":
        result_tag = "follow_up"
        message = PATIENT_FRIENDLY_TEMPLATES[result_tag]

    return {
        "result": result_tag,
        "layer": 2,
        "patient_message": message,
        "doctor_message": _build_doctor_explanation(deviation, streak_days, auto_followup),
        "baseline": baseline,
        "deviation": deviation,
        "streak_days": streak_days,
    }


def _consecutive_worsening_days(records: list[dict], today_severity: float | None) -> int:
    """從 records 末尾往前算：連續超過基準均值的天數"""
    pains = [r.get("pain") for r in records if r.get("pain") is not None]
    if not pains:
        return 0
    mean = sum(pains) / len(pains)
    streak = 0
    # 倒序檢查近期是否惡化
    for p in reversed(pains):
        if p > mean:
            streak += 1
        else:
            break
    if today_severity is not None and today_severity > mean:
        streak += 1
    return streak


def _build_user_prompt(patient, body, baseline, deviation, streak):
    parts = [
        f"病患：{patient.get('name', '匿名')}，{patient.get('age', '?')} 歲",
        "",
        "今日回報：",
        f"- 症狀：{', '.join(body.symptoms) if body.symptoms else '無特殊症狀'}",
        f"- 不適部位：{', '.join(body.body_locations) if body.body_locations else '無'}",
    ]
    if body.severity_index is not None:
        parts.append(f"- 嚴重度指數（0-10）：{body.severity_index}")
    if body.temperature:
        parts.append(f"- 體溫：{body.temperature}°C")
    if body.emotion_score is not None:
        parts.append(f"- 情緒：{body.emotion_score}/5")
    med = "是" if body.medication_taken else "否" if body.medication_taken is not None else "未回報"
    parts.append(f"- 今日服藥：{med}")
    if body.notes:
        parts.append(f"- 備註：{body.notes}")

    parts.append("")
    parts.append("個人基準線（近 14 天）：")
    parts.append(f"- 嚴重度均值：{baseline.get('pain_mean')}（標準差 {baseline.get('pain_stdev')}）")
    parts.append(f"- 情緒均值：{baseline.get('emotion_mean')}")
    parts.append(f"- 服藥率：{baseline.get('medication_rate_mean')}")
    parts.append(f"- 已知部位：{', '.join(baseline.get('known_locations', [])) or '無'}")

    parts.append("")
    parts.append("與基準線比較：")
    parts.append(f"- 嚴重度偏離：{deviation.get('deviation_pain')} 個標準差")
    parts.append(f"- 新出現部位：{', '.join(deviation.get('new_locations', [])) or '無'}")
    parts.append(f"- 情緒下降：{deviation.get('emotion_drop')}")
    parts.append(f"- 連續惡化天數：{streak}")
    parts.append(f"- 已知誘因：{'是' if body.has_known_trigger else '否'}")
    return "\n".join(parts)


def _build_doctor_explanation(deviation, streak, auto_followup):
    bits = []
    if deviation.get("deviation_pain") and deviation["deviation_pain"] >= 1:
        bits.append(f"嚴重度偏離 {deviation['deviation_pain']}σ")
    if deviation.get("new_locations"):
        bits.append(f"新部位：{','.join(deviation['new_locations'])}")
    if deviation.get("emotion_drop") and deviation["emotion_drop"] >= 1:
        bits.append(f"情緒較基準低 {deviation['emotion_drop']}")
    if streak >= ESCALATION_DAYS:
        bits.append(f"連續惡化 {streak} 天")
    if auto_followup:
        bits.append("規則自動升級 follow_up")
    return "；".join(bits) if bits else "未顯著偏離基準"


@router.get("/baseline/{patient_id}")
def get_baseline(patient_id: str, days: int = 14):
    """取得個人化基準線"""
    sb = get_supabase()
    return build_baseline_from_db(sb, patient_id, days=days)


@router.get("/emergency-symptoms")
def list_emergency_symptoms():
    return {"symptoms": EMERGENCY_SYMPTOMS}
