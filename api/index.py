import sys
import os
import logging

# Ensure project root is on the path so "backend.xxx" imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import (
    patients, symptoms,
    education, emotions, medications,
    reports, triage, xiaohe,
    records, research, auth,
    medication_changes, alerts, labs, diet,
    drug_search, diseases, reminders, bell_reminders,
    admissions, timeline, profile, follow_ups,
    inpatient,
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
app.include_router(symptoms.router, prefix="/symptoms", tags=["symptoms"])
app.include_router(education.router, prefix="/education", tags=["education"])
app.include_router(emotions.router, prefix="/emotions", tags=["emotions"])
app.include_router(medications.router, prefix="/medications", tags=["medications"])
app.include_router(drug_search.router, prefix="/drug-search", tags=["drug-search"])
app.include_router(diseases.router, prefix="/diseases", tags=["diseases"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(triage.router, prefix="/triage", tags=["triage"])
app.include_router(xiaohe.router, prefix="/xiaohe", tags=["xiaohe"])
app.include_router(records.router, prefix="/records", tags=["records"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(medication_changes.router, prefix="/medication-changes", tags=["medication-changes"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(labs.router, prefix="/labs", tags=["labs"])
app.include_router(diet.router, prefix="/diet", tags=["diet"])
# bell_reminders 註冊順序必須在 reminders 之前：reminders.router 有 /{reminder_id}
# 這條 catch-all path，若 bell_reminders 排在後面，/reminders/bell-prefs、
# /reminders/measurement-plan、/reminders/measurement-requests 等具體路徑會被它蓋掉。
app.include_router(bell_reminders.router, prefix="/reminders", tags=["reminders"])
app.include_router(reminders.router, prefix="/reminders", tags=["reminders"])
app.include_router(admissions.router, prefix="/admissions", tags=["admissions"])
app.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(follow_ups.router, prefix="/follow-ups", tags=["follow-ups"])
app.include_router(inpatient.router, prefix="/inpatient", tags=["inpatient"])


@app.get("/api")
def root():
    return {"message": "MD.Piece API is running", "version": "1.0.0"}


@app.get("/health/llm")
def health_llm(probe: int = 0):
    """LLM provider 健檢：列出主 provider、fallback chain、各 provider 連線狀態。
    用於排查「報告產不出來」「小禾沒回應」等 LLM-bound 端點失敗。

    /health/llm        → 只看 key 是否設定（快，~10ms）
    /health/llm?probe=1 → 實際發 1 個 token 的 ping 確認 key 真的能用
                          （慢，每 provider 1~3s；可分辨「key 設了但失效」）
    """
    import httpx
    from backend.services import llm_service
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
        status["anthropic"] = "ready" if llm_service._anthropic_client else "no_key_or_sdk"
    if "groq" in chain:
        status["groq"] = "ready" if llm_service.GROQ_API_KEY else "no_key"
    if "gemini" in chain:
        status["gemini"] = "ready" if llm_service.GEMINI_API_KEY else "no_key"

    if probe:
        # 真實 ping：丟個 1~2 token 的小請求，確認 key 真的能呼叫成功
        # 失敗訊息直接返回，方便 ops 一秒看出是 rate-limit / 401 / quota / 過期
        probe_results = {}
        for name in ("anthropic", "gemini", "groq", "ollama"):
            if name not in chain:
                continue
            fn = llm_service._PROVIDERS.get(name)
            if fn is None:
                probe_results[name] = "not_implemented"
                continue
            try:
                r = fn("回一個字", "1", max_tokens=2, timeout=5.0)
                probe_results[name] = "ok" if (r and isinstance(r, str)) else "empty_response"
            except Exception as e:
                probe_results[name] = f"fail: {type(e).__name__}: {str(e)[:200]}"
        status["_probe"] = probe_results

    return {
        "primary": llm_service.LLM_PROVIDER,
        "fallback_chain": chain,
        "status": status,
    }
