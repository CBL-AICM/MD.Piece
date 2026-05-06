"""
診斷 endpoints — 用來找出 production LLM provider 哪個通哪個不通。

`GET /debug/llm` 會逐一打每個 vision / text provider 一個極短的測試請求，
回傳結構化結果（model 名、成功與否、錯誤訊息）。

不需要 patient_id / auth — 回傳的不是任何使用者資料。
"""
import os
import time

from fastapi import APIRouter

from backend.services import llm_service

router = APIRouter()


def _safe_call(label: str, fn):
    """呼叫 fn() 並包成 dict（包含耗時、是否成功、錯誤訊息）"""
    t0 = time.time()
    try:
        result = fn()
        return {
            "ok": True,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "preview": (result or "")[:120].strip(),
        }
    except Exception as e:
        return {
            "ok": False,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "error_type": type(e).__name__,
            "error": str(e)[:300],
        }


@router.get("/llm")
def diagnose_llm():
    """逐一測試每個 LLM provider，回報哪個通哪個不通。"""
    env = {
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "(unset, default ollama)"),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "(unset, default http://localhost:11434)"),
        "ANTHROPIC_API_KEY_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", "(unset)"),
        "ANTHROPIC_VISION_MODEL": os.getenv("ANTHROPIC_VISION_MODEL", "(unset)"),
        "GROQ_API_KEY_set": bool(os.getenv("GROQ_API_KEY")),
        "GROQ_MODEL": os.getenv("GROQ_MODEL", "(unset)"),
        "GROQ_VISION_MODEL": os.getenv("GROQ_VISION_MODEL", "(unset)"),
        "GOOGLE_VISION_API_KEY_set": bool(os.getenv("GOOGLE_VISION_API_KEY")),
        "anthropic_client_initialized": llm_service._anthropic_client is not None,
    }

    test_system = "你是 OK 機器人，只回兩個字: OK"
    test_user = "請回 OK"

    # Text providers — 直接打底層函式，跳過 fallback chain，可以個別看每個成敗
    text_results = {
        "ollama": _safe_call("ollama-text", lambda: llm_service._call_ollama(test_system, test_user)),
        "anthropic": _safe_call("anthropic-text", lambda: llm_service._call_anthropic(test_system, test_user)),
        "groq": _safe_call("groq-text", lambda: llm_service._call_groq(test_system, test_user)),
    }

    # 整條 fallback chain 跑 call_claude 一次（看真實使用者會碰到什麼）
    chain_result = _safe_call("call_claude", lambda: llm_service.call_claude(test_system, test_user))
    chain_result["chain"] = llm_service._fallback_chain(
        llm_service.LLM_PROVIDER if llm_service.LLM_PROVIDER in llm_service._PROVIDERS else "ollama"
    )

    return {
        "env": env,
        "text_providers": text_results,
        "call_claude_via_chain": chain_result,
    }
