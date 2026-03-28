"""
STORM 研究文章生成 API 路由

提供 STORM（全自動）與 Co-STORM（人機協作）兩種模式的端點。
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()

# 非同步任務狀態追蹤
_task_status: dict = {}


# ── Request / Response Models ─────────────────────────


class StormResearchRequest(BaseModel):
    """STORM 全自動研究請求"""
    topic: str
    search_engine: Optional[str] = None
    search_top_k: int = 3
    max_conv_turn: int = 3
    max_perspective: int = 3
    do_polish: bool = True


class CoStormCreateRequest(BaseModel):
    """Co-STORM 建立會話請求"""
    topic: str
    session_id: Optional[str] = None
    search_engine: Optional[str] = None
    search_top_k: int = 3


class CoStormStepRequest(BaseModel):
    """Co-STORM 對話步驟請求"""
    user_utterance: Optional[str] = None


# ── STORM 全自動研究 ─────────────────────────────────


def _run_storm_task(task_id: str, request: StormResearchRequest):
    """背景執行 STORM 研究任務。"""
    from backend.services.storm_service import run_storm_research

    try:
        _task_status[task_id]["status"] = "running"
        result = run_storm_research(
            topic=request.topic,
            search_engine=request.search_engine,
            search_top_k=request.search_top_k,
            max_conv_turn=request.max_conv_turn,
            max_perspective=request.max_perspective,
            do_polish=request.do_polish,
        )
        _task_status[task_id]["status"] = "completed"
        _task_status[task_id]["result"] = result
    except Exception as e:
        logger.error(f"STORM 研究失敗 [{task_id}]: {e}")
        _task_status[task_id]["status"] = "failed"
        _task_status[task_id]["error"] = str(e)


@router.post("/research")
def start_research(request: StormResearchRequest, background_tasks: BackgroundTasks):
    """
    啟動 STORM 全自動研究（非同步）。

    STORM 會針對指定主題進行多輪搜尋與多專家對話模擬，
    最終產出含引用的結構化衛教文章。

    回傳 task_id，可用 GET /storm/research/{task_id} 查詢進度。
    """
    task_id = str(uuid.uuid4())[:8]
    _task_status[task_id] = {
        "status": "queued",
        "topic": request.topic,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(_run_storm_task, task_id, request)
    return {
        "task_id": task_id,
        "topic": request.topic,
        "status": "queued",
        "message": "STORM 研究已排入佇列，使用 GET /storm/research/{task_id} 查詢進度",
    }


@router.get("/research/{task_id}")
def get_research_status(task_id: str):
    """查詢 STORM 研究任務狀態與結果。"""
    task = _task_status.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"找不到任務：{task_id}")
    return task


@router.get("/research")
def list_research_tasks():
    """列出所有 STORM 研究任務。"""
    return {
        "tasks": [
            {"task_id": tid, "topic": t["topic"], "status": t["status"]}
            for tid, t in _task_status.items()
        ]
    }


# ── Co-STORM 協作式研究 ──────────────────────────────


@router.post("/costorm/sessions")
def create_costorm_session(request: CoStormCreateRequest):
    """
    建立 Co-STORM 協作研究會話。

    醫師可與 AI 專家群進行多輪對話，共同策展醫療知識。
    """
    from backend.services.storm_service import create_costorm_session

    try:
        return create_costorm_session(
            topic=request.topic,
            session_id=request.session_id,
            search_engine=request.search_engine,
            search_top_k=request.search_top_k,
        )
    except Exception as e:
        logger.error(f"Co-STORM 會話建立失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/costorm/sessions/{session_id}/step")
def costorm_step(session_id: str, request: CoStormStepRequest):
    """
    推進 Co-STORM 一個對話步驟。

    若提供 user_utterance，醫師的輸入會被納入對話；
    若不提供，AI 專家會自主進行下一輪討論。
    """
    from backend.services.storm_service import costorm_step as _step

    try:
        return _step(session_id=session_id, user_utterance=request.user_utterance)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Co-STORM step 失敗 [{session_id}]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/costorm/sessions/{session_id}/report")
def costorm_generate_report(session_id: str):
    """生成 Co-STORM 最終研究報告。"""
    from backend.services.storm_service import costorm_generate_report as _report

    try:
        return _report(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Co-STORM 報告生成失敗 [{session_id}]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/costorm/sessions/{session_id}")
def close_costorm_session(session_id: str):
    """關閉並清理 Co-STORM 會話。"""
    from backend.services.storm_service import costorm_close_session

    try:
        return costorm_close_session(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
