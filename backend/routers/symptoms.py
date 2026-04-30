import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.models import SymptomAnalysisRequest
from backend.services.ai_analyzer import analyze_symptoms
from backend.services.llm_service import call_claude
from backend.utils.symptom_questionnaire import (
    BODY_PARTS,
    SYMPTOM_TYPES,
    CHANGE_PATTERNS,
    OVERALL_OPTIONS,
    get_questionnaire_schema,
    calculate_severity_index,
    to_structured_summary,
)

logger = logging.getLogger(__name__)
router = APIRouter()

SYMPTOM_ADVICE = {
    "fever": "多休息、補充水分。若體溫超過 38.5°C 持續超過 3 天，請就醫。",
    "headache": "注意休息，避免強光刺激。若頭痛劇烈或伴隨嘔吐，請立即就醫。",
    "cough": "多喝溫水，避免刺激性食物。若咳嗽超過 2 週或咳血，請就醫。",
    "chest pain": "請立即就醫，排除心臟相關問題。撥打 119 緊急電話。",
    "sore throat": "多喝水、避免辛辣食物。若伴隨高燒或吞嚥困難，請就醫。",
    "nausea": "少量多餐，避免油膩食物。若持續嘔吐或脫水，請就醫。",
    "dizziness": "先坐下或躺下休息，避免突然站起。反覆發作請就醫。",
    "fatigue": "確保充足睡眠與均衡飲食。若持續疲勞超過 2 週，建議就醫檢查。",
    "stomach pain": "避免辛辣油膩飲食。若劇烈疼痛或伴隨發燒，請就醫。",
    "shortness of breath": "請立即就醫。若伴隨胸痛或嘴唇發紫，請撥打 119。",
}


# ── 五層遞進問卷 ────────────────────────────────────────────


class FiveLayerSubmission(BaseModel):
    patient_id: str
    overall_feeling: str  # good / ok / uncomfortable / bad
    body_locations: list[str] = []
    symptom_types: list[str] = []
    free_text: str | None = ""
    severity: int | None = None  # 0-10
    change_pattern: str | None = None  # sudden / gradual_worse / same / improving


@router.get("/questionnaire")
def get_questionnaire():
    """前端用：五層遞進問卷的完整 schema（人體輪廓圖座標、症狀選項、滑桿錨點）"""
    return get_questionnaire_schema()


@router.post("/questionnaire/submit")
def submit_questionnaire(body: FiveLayerSubmission):
    """
    送出五層問卷：
    1. 計算嚴重度指數（0-10）
    2. 結構化中文摘要
    3. 自由文字交給 LLM 結構化（如有）
    4. 寫入 symptoms_log 供基準線、報告、分流使用
    """
    submission = body.model_dump()
    severity_index = calculate_severity_index(submission)
    summary = to_structured_summary(submission)

    # 自由描述 → LLM 結構化（萃取症狀關鍵字）
    extracted = []
    if body.free_text and len(body.free_text.strip()) > 4:
        try:
            extracted = _extract_symptoms_from_text(body.free_text)
        except Exception as e:
            logger.warning(f"Free-text extraction failed: {e}")

    # 寫入 symptoms_log
    sb = get_supabase()
    structured_payload = {
        **submission,
        "severity_index": severity_index,
        "summary": summary,
        "extracted_keywords": extracted,
    }

    sb.table("symptoms_log").insert({
        "patient_id": body.patient_id,
        "symptoms": _build_symptom_tags(submission, extracted),
        "ai_response": json.dumps(structured_payload, ensure_ascii=False),
    }).execute()

    return {
        "patient_id": body.patient_id,
        "severity_index": severity_index,
        "summary": summary,
        "extracted_keywords": extracted,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_symptoms_from_text(text: str) -> list[str]:
    """請 LLM 從自由文字萃取出標準化症狀關鍵字"""
    system = (
        "你是醫療資訊結構化助手。從患者的自由描述中萃取出 1-5 個簡短的症狀關鍵字。\n"
        "規則：\n"
        "- 只回傳 JSON 陣列，沒有 markdown\n"
        "- 每個關鍵字 2-6 個字\n"
        "- 用繁體中文\n"
        "範例輸入：「早上起床膝蓋很僵硬，走樓梯會痛，下午比較好」\n"
        "範例輸出：[\"晨僵\",\"膝蓋疼痛\",\"上下樓梯痛\"]"
    )
    raw = call_claude(system, text).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else []


def _build_symptom_tags(submission: dict, extracted: list[str]) -> list[str]:
    tags = []
    for t_key in submission.get("symptom_types", []):
        label = next((t["label"] for t in SYMPTOM_TYPES if t["key"] == t_key), None)
        if label:
            tags.append(label)
    all_parts = BODY_PARTS["front"] + BODY_PARTS["back"]
    for loc in submission.get("body_locations", []):
        label = next((b["label"] for b in all_parts if b["key"] == loc), None)
        if label:
            tags.append(label)
    tags.extend(extracted)
    return tags


# ── 人體輪廓圖熱點資料（給醫師端與報告） ─────────────────


@router.get("/heatmap/{patient_id}")
def body_part_heatmap(patient_id: str, days: int = Query(30)):
    """
    身體部位熱點圖：依時間範圍統計各部位被點選次數。
    醫師端用於「30 天身體部位熱點圖」視覺化。
    """
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        sb.table("symptoms_log")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
    )
    rows = result.data or []

    counts: dict[str, int] = {}
    severities: dict[str, list[float]] = {}
    for r in rows:
        ai = r.get("ai_response")
        if isinstance(ai, str):
            try:
                ai = json.loads(ai)
            except Exception:
                continue
        if not isinstance(ai, dict):
            continue
        sev = ai.get("severity_index", 0) or 0
        for loc in ai.get("body_locations", []) or []:
            counts[loc] = counts.get(loc, 0) + 1
            severities.setdefault(loc, []).append(sev)

    all_parts = {b["key"]: b for b in BODY_PARTS["front"] + BODY_PARTS["back"]}
    heatmap = []
    for key, count in counts.items():
        meta = all_parts.get(key)
        if not meta:
            continue
        sev_list = severities.get(key, [])
        heatmap.append({
            "key": key,
            "label": meta["label"],
            "count": count,
            "avg_severity": round(sum(sev_list) / len(sev_list), 1) if sev_list else 0,
            "max_severity": max(sev_list) if sev_list else 0,
        })
    heatmap.sort(key=lambda x: x["count"], reverse=True)

    return {
        "patient_id": patient_id,
        "days": days,
        "heatmap": heatmap,
        "total_records": len(rows),
    }


# ── 既有 API（保留向後相容） ──────────────────────────────


@router.get("/")
def get_symptoms(patient_id: str):
    sb = get_supabase()
    result = (
        sb.table("symptoms_log")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(30)
        .execute()
    )
    return {"symptoms": result.data}


@router.get("/infection-check")
def check_infection(patient_id: str):
    """
    每日感染篩查：發燒、呼吸道、泌尿道、皮膚、腸胃道。
    回傳是否觸發感染旗標供分流引擎參考。
    """
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    rows = (
        sb.table("symptoms_log")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    flag_keywords = {
        "fever": ["發燒", "高燒", "燒"],
        "respiratory": ["咳嗽", "喘", "呼吸"],
        "urinary": ["尿", "頻尿", "解尿痛"],
        "skin": ["紅腫", "傷口", "化膿"],
        "gi": ["腹瀉", "嘔吐", "腹痛"],
    }
    triggered: dict[str, bool] = {k: False for k in flag_keywords}
    for r in rows:
        text = json.dumps(r, ensure_ascii=False)
        for cat, kws in flag_keywords.items():
            if any(kw in text for kw in kws):
                triggered[cat] = True
    return {"infection_flag": any(triggered.values()), "categories": triggered}


@router.get("/advice")
def get_advice(symptom: str):
    advice = SYMPTOM_ADVICE.get(symptom.lower(), "建議就醫，請諮詢醫師")
    return {"symptom": symptom, "advice": advice}


@router.post("/analyze")
async def analyze(body: SymptomAnalysisRequest):
    """既有 AI 症狀分析（保留向後相容）"""
    if not body.symptoms:
        raise HTTPException(status_code=400, detail="請提供至少一個症狀")

    patient_info = None
    if body.patient_id:
        sb = get_supabase()
        result = sb.table("patients").select("name,age,gender").eq("id", body.patient_id).execute()
        if result.data:
            patient_info = result.data[0]

    ai_result = await analyze_symptoms(
        symptoms=body.symptoms,
        patient_age=patient_info.get("age") if patient_info else None,
        patient_gender=patient_info.get("gender") if patient_info else None,
    )

    if body.patient_id:
        sb = get_supabase()
        sb.table("symptoms_log").insert({
            "patient_id": body.patient_id,
            "symptoms": body.symptoms,
            "ai_response": ai_result,
        }).execute()

    return ai_result


@router.get("/history/{patient_id}")
def get_symptom_history(patient_id: str):
    """取得病患的症狀分析歷史"""
    sb = get_supabase()
    result = (
        sb.table("symptoms_log")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"history": result.data}
