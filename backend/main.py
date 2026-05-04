from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from backend.routers import (
    patients, doctors, symptoms,
    education, emotions, medications,
    records, reports, research, triage, xiaohe, auth,
    doctor_notes, medication_changes, alerts, labs,
)
from backend.services import llm_service

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
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(doctor_notes.router, prefix="/doctor-notes", tags=["doctor-notes"])
app.include_router(medication_changes.router, prefix="/medication-changes", tags=["medication-changes"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(labs.router, prefix="/labs", tags=["labs"])

@app.get("/health/llm")
def health_llm():
    """檢查 LLM provider 連線狀態與目前的 fallback chain。"""
    import httpx
    chain = llm_service._fallback_chain(
        llm_service.LLM_PROVIDER if llm_service.LLM_PROVIDER in llm_service._PROVIDERS else "ollama"
    )
    status = {}
    if "ollama" in chain:
        try:
            r = httpx.get(f"{llm_service.OLLAMA_BASE}/api/tags", timeout=2.0)
            status["ollama"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as e:
            status["ollama"] = f"down ({type(e).__name__})"
    if "anthropic" in chain:
        status["anthropic"] = "ready" if llm_service._anthropic_client else "no_key"
    if "groq" in chain:
        status["groq"] = "ready" if llm_service.GROQ_API_KEY else "no_key"
    return {
        "primary": llm_service.LLM_PROVIDER,
        "fallback_chain": chain,
        "status": status,
    }


# Serve frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
