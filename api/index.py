import sys
import os

# Ensure project root is on the path so "backend.xxx" imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import (
    patients, doctors, symptoms,
    education, emotions, medications,
    reports, triage, xiaohe,
    records, research, auth,
    doctor_notes, medication_changes, alerts, labs,
)

app = FastAPI(title="MD.Piece API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
app.include_router(symptoms.router, prefix="/symptoms", tags=["symptoms"])
app.include_router(education.router, prefix="/education", tags=["education"])
app.include_router(emotions.router, prefix="/emotions", tags=["emotions"])
app.include_router(medications.router, prefix="/medications", tags=["medications"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(triage.router, prefix="/triage", tags=["triage"])
app.include_router(xiaohe.router, prefix="/xiaohe", tags=["xiaohe"])
app.include_router(records.router, prefix="/records", tags=["records"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(doctor_notes.router, prefix="/doctor-notes", tags=["doctor-notes"])
app.include_router(medication_changes.router, prefix="/medication-changes", tags=["medication-changes"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(labs.router, prefix="/labs", tags=["labs"])


@app.get("/api")
def root():
    return {"message": "MD.Piece API is running", "version": "1.0.0"}
