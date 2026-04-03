from fastapi import APIRouter, Query

from backend.models import MedicationCreate, MedicationLogEntry

router = APIRouter()

# 用藥管理 - 日誌記錄、生理時間錨點提醒、停藥原因記錄


@router.get("/")
def get_medications(patient_id: str = Query(...)):
    return {"medications": []}


@router.post("/")
def create_medication(body: MedicationCreate):
    # timing: morning / after_meal / bedtime
    return {"status": "added", "name": body.name, "timing": body.timing}


@router.post("/log")
def log_medication_taken(body: MedicationLogEntry):
    return {"status": "logged", "taken": body.taken}
