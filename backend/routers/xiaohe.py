from fastapi import APIRouter

router = APIRouter()

# 小禾 AI 對話 - Claude Haiku 情感陪伴，患者版/家屬版語氣切換

@router.post("/chat")
def chat_with_xiaohe(user_id: str, message: str, mode: str = "patient", version: str = "normal"):
    # mode: patient / family
    # version: normal（活潑俏皮）/ elderly（耐心溫暖）
    # 原則：先理解感受、不說教、不給建議
    return {"reply": ""}

@router.get("/emotion-summary/{patient_id}")
def get_emotion_summary(patient_id: str):
    # 回傳匿名情緒趨勢（不含對話內容，保護隱私）
    return {"trend": []}
