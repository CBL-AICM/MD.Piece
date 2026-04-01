import json
from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import SymptomAnalysisRequest
from backend.services.ai_analyzer import analyze_symptoms

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
async def analyze(symptom_request: SymptomAnalysisRequest):
    """AI 症狀分析。"""
    if not symptom_request.symptoms:
        raise HTTPException(status_code=400, detail="請提供至少一個症狀")

    # 如果有 patient_id，取得病患資料作為參考
    patient_info = None
    if symptom_request.patient_id:
        supabase_client = get_supabase()
        db_result = supabase_client.table("patients").select("name,age,gender").eq("id", symptom_request.patient_id).execute()
        if db_result.data:
            patient_info = db_result.data[0]

    # 呼叫 AI 分析
    ai_analysis_result = await analyze_symptoms(
        symptoms=symptom_request.symptoms,
        patient_age=patient_info.get("age") if patient_info else None,
        patient_gender=patient_info.get("gender") if patient_info else None,
    )

    # 記錄到 symptoms_log
    if symptom_request.patient_id:
        supabase_client = get_supabase()
        supabase_client.table("symptoms_log").insert({
            "patient_id": symptom_request.patient_id,
            "symptoms": symptom_request.symptoms,
            "ai_response": ai_analysis_result,
        }).execute()

    return ai_analysis_result


@router.get("/history/{patient_id}")
def get_symptom_history(patient_id: str):
    """取得病患的症狀分析歷史。"""
    supabase_client = get_supabase()
    db_result = supabase_client.table("symptoms_log").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()
    return {"history": db_result.data}
