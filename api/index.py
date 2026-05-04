import sys
import os
import logging

# Ensure project root is on the path so "backend.xxx" imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import (
    patients, doctors, symptoms,
    education, emotions, medications,
    reports, triage, xiaohe,
    records, research, auth,
    doctor_notes, medication_changes, alerts, labs,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="MD.Piece API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    """
    把 db.py 在缺 Supabase 憑證時 raise 的 RuntimeError 翻成 503，
    並附上人類看得懂的訊息，避免使用者看到沒頭沒尾的「Internal Server Error」。
    """
    msg = str(exc)
    is_db_offline = ("SUPABASE_URL" in msg) or ("Supabase" in msg) or ("Serverless" in msg)
    if is_db_offline:
        logger.warning(f"DB offline at {request.url.path}: {msg}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "db_offline",
                "detail": "資料庫尚未連線（後端缺少 SUPABASE_URL / SUPABASE_KEY 環境變數）。"
                          "請聯絡管理者於 Vercel 後台補上憑證後重試。",
                "path": request.url.path,
            },
        )
    # 不是 DB 相關的 RuntimeError 就照原本流程拋
    raise exc

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
