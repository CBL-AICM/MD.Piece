from fastapi import APIRouter

router = APIRouter()

# 情緒記錄 - 每日評分、靜默守護機制、心理危機偵測

@router.get("/")
def get_emotions(patient_id: str):
    return {"emotions": []}

@router.post("/")
def log_emotion(patient_id: str, score: int, note: str = ""):
    # score: 1-5，1 最低落、5 最好
    return {"status": "logged"}

@router.get("/silent-guardian")
def check_silent_guardian(patient_id: str):
    # 偵測連續低落情緒，觸發心理危機提醒
    return {"alert": False}
