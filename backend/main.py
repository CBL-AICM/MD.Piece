import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from backend.routers import (
    patients, doctors, symptoms,
    education, emotions, medications,
    records, reports, research, triage, xiaohe, auth,
    doctor_notes, medication_changes, alerts,
)
from backend.db import get_supabase
from backend.services.auth_service import hash_password

logger = logging.getLogger(__name__)

app = FastAPI(title="MD.Piece API", version="1.0.0")


@app.on_event("startup")
def _seed_initial_doctor():
    """若資料庫沒有任何 doctor 帳號，依環境變數建立一組初始醫師帳號。"""
    username = os.getenv("INITIAL_DOCTOR_USERNAME", "doctor")
    password = os.getenv("INITIAL_DOCTOR_PASSWORD", "mdpiece2026")
    nickname = os.getenv("INITIAL_DOCTOR_NICKNAME", "測試醫師")
    try:
        sb = get_supabase()
        existing = sb.table("users").select("*").eq("username", username).execute().data
        if existing:
            return
        any_doctor = sb.table("users").select("*").eq("role", "doctor").execute().data
        if any_doctor:
            return
        sb.table("users").insert({
            "username": username,
            "password_hash": hash_password(password),
            "nickname": nickname,
            "role": "doctor",
            "is_active": 1,
        }).execute()
        logger.warning(
            "已建立初始醫師帳號 username=%s（正式環境請用環境變數覆寫並更換密碼）",
            username,
        )
    except Exception as e:
        logger.exception("seed initial doctor failed: %s", e)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
app.include_router(records.router, prefix="/records", tags=["records"])
app.include_router(symptoms.router, prefix="/symptoms", tags=["symptoms"])
app.include_router(education.router, prefix="/education", tags=["education"])
app.include_router(emotions.router, prefix="/emotions", tags=["emotions"])
app.include_router(medications.router, prefix="/medications", tags=["medications"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(triage.router, prefix="/triage", tags=["triage"])
app.include_router(xiaohe.router, prefix="/xiaohe", tags=["xiaohe"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(doctor_notes.router, prefix="/doctor-notes", tags=["doctor-notes"])
app.include_router(medication_changes.router, prefix="/medication-changes", tags=["medication-changes"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

# Serve frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
