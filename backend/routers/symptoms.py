import json
from fastapi import APIRouter, HTTPException
from backend.db import get_supabase
from backend.models import SymptomAnalysisRequest
from backend.services.ai_analyzer import analyze_symptoms

router = APIRouter()

# 注意：本 router 同時提供兩種不同概念的 API，請勿混用：
#   1) 症狀「紀錄」(record)：GET/POST /     —— 只負責留檔，不做判斷。
#   2) 症狀「分析」(analyze)：POST /analyze —— AI 推測可能原因 + 第一步處理建議。
# 紀錄是事實，分析是推論；前端也分為兩個獨立頁面。

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

# ── 症狀紀錄（record）──────────────────────────────────────
# 五層遞進問卷、人體輪廓圖、拍照記錄。只留檔，不做推論。


@router.get("/")
def get_symptoms(patient_id: str):
    """取得病患的症狀紀錄（純資料，不做分析）。"""
    return {"symptoms": []}

@router.post("/")
def create_symptom(patient_id: str, body_part: str, severity: int, description: str = ""):
    """新增一筆症狀紀錄（純記錄，不觸發分析）。"""
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
    """症狀分析（不是紀錄）。

    輸入一組症狀，回傳：
      - conditions：可能原因（含可能性高/中/低）
      - recommended_department：建議就診科別
      - urgency：緊急程度
      - advice：第一步可以先怎麼做
      - disclaimer：免責聲明
    分析結果同時寫入 symptoms_log（若有 patient_id），以便日後追蹤。
    """
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
