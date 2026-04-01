from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class ResearchRequest(BaseModel):
    """醫療研究請求"""
    topic: str
    report_type: Optional[str] = "research_report"
    max_sources: Optional[int] = 10


class SourceCollectRequest(BaseModel):
    """蒐集來源請求"""
    topic: str
    max_sources: Optional[int] = 10


@router.post("/research")
async def research_topic(req: ResearchRequest):
    """
    使用 GPT-Researcher 對醫療主題進行深度研究。

    report_type 可選：
    - research_report：完整研究報告（預設）
    - outline_report：大綱式報告
    - resource_report：來源彙整報告
    """
    from backend.services.gpt_researcher_service import research_medical_topic

    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="研究主題不可為空")

    valid_types = {"research_report", "outline_report", "resource_report"}
    if req.report_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"report_type 必須為: {', '.join(valid_types)}",
        )

    try:
        result = await research_medical_topic(
            topic=req.topic,
            report_type=req.report_type,
            max_sources=req.max_sources,
        )
    except Exception:
        logger.error("GPT-Researcher research failed for topic '%s'", req.topic)
        raise HTTPException(status_code=500, detail="研究執行失敗，請確認 OPENAI_API_KEY 與 TAVILY_API_KEY 已正確設定。")

    return {
        "topic": result.get("topic", req.topic),
        "report": result.get("report", ""),
        "sources": result.get("sources", []),
        "report_type": result.get("report_type", req.report_type),
        "source_count": result.get("source_count", 0),
    }


@router.post("/sources")
async def collect_sources(req: SourceCollectRequest):
    """
    蒐集醫療主題的相關來源（URL、標題、摘錄），
    可作為 Stanford STORM 文章生成的原始素材。
    """
    from backend.services.gpt_researcher_service import collect_medical_sources

    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="研究主題不可為空")

    try:
        result = await collect_medical_sources(
            topic=req.topic,
            max_sources=req.max_sources,
        )
    except Exception:
        logger.error("GPT-Researcher sources failed for topic '%s'", req.topic)
        raise HTTPException(status_code=500, detail="來源蒐集失敗，請確認 OPENAI_API_KEY 與 TAVILY_API_KEY 已正確設定。")

    return {
        "topic": result.get("topic", req.topic),
        "sources": result.get("sources", []),
        "source_count": result.get("source_count", 0),
    }


@router.get("/health")
async def health_check():
    """檢查 GPT-Researcher 是否已安裝並可用。"""
    try:
        import gpt_researcher  # noqa: F401
        return {"status": "ok", "gpt_researcher": "installed"}
    except ImportError:
        return {
            "status": "unavailable",
            "gpt_researcher": "not installed",
            "hint": "pip install gpt-researcher",
        }
