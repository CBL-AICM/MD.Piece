from fastapi import APIRouter

router = APIRouter()

SYMPTOM_ADVICE = {
    "fever": "請多喝水、休息，若超過38.5°C請就醫",
    "headache": "可服用止痛藥，若持續超過24小時請就醫",
    "chest pain": "請立即就醫或撥打119",
    "cough": "多休息、補充水分，持續超過一週請就醫",
}

@router.get("/advice")
def get_advice(symptom: str):
    advice = SYMPTOM_ADVICE.get(symptom.lower(), "建議就醫，請諮詢醫師")
    return {"symptom": symptom, "advice": advice}
