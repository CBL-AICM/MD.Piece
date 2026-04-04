from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from backend.routers import (
    patients, doctors, symptoms,
    education, emotions, medications,
    records, reports, research, triage, xiaohe,
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
app.include_router(records.router, prefix="/records", tags=["records"])
app.include_router(symptoms.router, prefix="/symptoms", tags=["symptoms"])
app.include_router(education.router, prefix="/education", tags=["education"])
app.include_router(emotions.router, prefix="/emotions", tags=["emotions"])
app.include_router(medications.router, prefix="/medications", tags=["medications"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(triage.router, prefix="/triage", tags=["triage"])
app.include_router(xiaohe.router, prefix="/xiaohe", tags=["xiaohe"])

# Serve frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
