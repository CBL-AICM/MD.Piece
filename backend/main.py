import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import (
    patients,
    doctors,
    symptoms,
    records,
    research,
    triage,
    education,
    emotions,
    medications,
    xiaohe,
    reports,
)

app = FastAPI(title="MD.Piece API", version="2.0.0")

# ─── CORS ─────────────────────────────────────────────────
_env = os.getenv("APP_ENV", "development")
_cors_env = os.getenv("CORS_ORIGINS", "")

if _cors_env:
    _origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
elif _env == "production":
    _origins = ["https://mdpiece.life"]
else:
    _origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
app.include_router(symptoms.router, prefix="/symptoms", tags=["symptoms"])
app.include_router(records.router, prefix="/records", tags=["records"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(triage.router, prefix="/triage", tags=["triage"])
app.include_router(education.router, prefix="/education", tags=["education"])
app.include_router(emotions.router, prefix="/emotions", tags=["emotions"])
app.include_router(medications.router, prefix="/medications", tags=["medications"])
app.include_router(xiaohe.router, prefix="/xiaohe", tags=["xiaohe"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])


@app.get("/")
def root():
    return {"message": "MD.Piece API is running", "version": "2.0.0"}
