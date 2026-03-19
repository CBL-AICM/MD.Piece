import json
from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import SymptomAnalysisRequest
from backend.services.ai_analyzer import analyze_symptoms

router = APIRouter()

SYMPTOM_ADVICE = {
    "fever": "請多喝水、休息，若超過38.5°C請就醫",
    "headache": "可服用止痛藥，若持續超過24小時請就醫",
    "chest pain": "請立即就醫或撥打119",
    "cough": "多休息、補充水分，持續超過一週請就醫",
}


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
