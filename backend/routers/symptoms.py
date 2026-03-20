import json
from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import SymptomAnalysisRequest
from backend.services.ai_analyzer import analyze_symptoms

router = APIRouter()

# 症狀記錄 - 五層遞進問卷、人體輪廓圖、拍照記錄


@router.get("/")
def get_symptoms(patient_id: str):
    return {"symptoms": []}

@router.post("/")
def create_symptom(patient_id: str, body_part: str, severity: int, description: str = ""):
    return {"status": "recorded"}

@router.get("/infection-check")
def check_infection(patient_id: str):
    # 每日感染篩查：發燒、呼吸道、泌尿道、皮膚、腸胃道
    return {"infection_flag": False}

@router.get("/advice")
def get_advice(symptom: str):
    """簡單症狀建議（保留向後相容）。"""
    advice = SYMPTOM_ADVICE.get(symptom.lower(), "建議就醫，請諮詢醫師")
    return {"symptom": symptom, "advice": advice}


@router.post("/analyze")
async def analyze(body: SymptomAnalysisRequest):
    """AI 症狀分析。"""
    if not body.symptoms:
        raise HTTPException(status_code=400, detail="請提供至少一個症狀")

    # 如果有 patient_id，取得病患資料作為參考
    patient_info = None
    if body.patient_id:
        sb = get_supabase()
        result = sb.table("patients").select("name,age,gender").eq("id", body.patient_id).execute()
        if result.data:
            patient_info = result.data[0]

    # 呼叫 AI 分析
    ai_result = await analyze_symptoms(
        symptoms=body.symptoms,
        patient_age=patient_info.get("age") if patient_info else None,
        patient_gender=patient_info.get("gender") if patient_info else None,
    )

    # 記錄到 symptoms_log
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
    """取得病患的症狀分析歷史。"""
    sb = get_supabase()
    result = sb.table("symptoms_log").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()
    return {"history": result.data}
