from fastapi import APIRouter

router = APIRouter()

# 用藥管理 - 日誌記錄、生理時間錨點提醒、停藥原因記錄

@router.get("/")
def get_medications(patient_id: str):
    return {"medications": []}

@router.post("/")
def create_medication(patient_id: str, name: str, dosage: str, timing: str):
    # timing: morning / after_meal / bedtime
    return {"status": "added"}

@router.post("/log")
def log_medication_taken(patient_id: str, medication_id: str, taken: bool, skip_reason: str = ""):
    return {"status": "logged"}
