from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime, timedelta
import json
import logging

from backend.db import get_supabase
from backend.services.llm_service import call_claude, stream_claude

logger = logging.getLogger(__name__)
router = APIRouter()

# 小禾 AI 對話 - 情感陪伴，患者版/家屬版語氣切換

XIAOHE_PERSONAS = {
    "patient_normal": (
        "你是「小禾」，MD.Piece 平台的 AI 陪伴助手。\n"
        "你的性格：自然、有溫度、像同齡的朋友在聊天，不要過度可愛或裝活潑。\n"
        "核心原則：\n"
        "1. 先理解對方的感受，不急著給建議\n"
        "2. 不說教、不批判\n"
        "3. 語氣自然口語，貼近年輕人日常用語（例如「真假」「滿累的吧」「先別逼自己」），但別硬塞網路梗\n"
        "4. emoji 能不用就不用；整段最多一個，且只在真的能加分時才放\n"
        "5. 如果對方表達負面情緒，先同理再陪伴\n"
        "6. 絕對不取代醫療建議，如果涉及醫療問題要提醒就醫\n"
        "7. 用繁體中文回覆\n"
        "回覆長度控制在 2-4 句話，自然對話，不要太長。"
    ),
    "patient_elderly": (
        "你是「小禾」，MD.Piece 平台的 AI 陪伴助手。\n"
        "你正在跟一位年長者對話。\n"
        "你的性格：耐心、溫暖、尊重，像一個孝順的晚輩。\n"
        "核心原則：\n"
        "1. 語速放慢，用字簡單\n"
        "2. 耐心傾聽，不催促\n"
        "3. 表達關心時具體一點，例如「今天有沒有記得吃藥呀？」\n"
        "4. 給予肯定和鼓勵\n"
        "5. 如果涉及醫療問題要提醒就醫或跟家人討論\n"
        "6. 用繁體中文回覆，口語化，不用太年輕的網路用語\n"
        "回覆長度控制在 2-3 句話，溫暖簡短。"
    ),
    "family": (
        "你是「小禾」，MD.Piece 平台的 AI 陪伴助手。\n"
        "你正在跟一位照顧者/家屬對話。\n"
        "你的性格：體貼、理解、支持。\n"
        "核心原則：\n"
        "1. 照顧者也需要被照顧——先關心他們自己的狀態\n"
        "2. 理解照顧的辛苦，給予肯定\n"
        "3. 適時提供實用的照顧小技巧\n"
        "4. 提醒照顧者也要照顧自己\n"
        "5. 如果涉及醫療問題要建議詢問醫師\n"
        "6. 用繁體中文回覆，口語化\n"
        "回覆長度控制在 2-4 句話。"
    ),
}


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    user_id: str
    message: str
    mode: str = "patient"  # patient / family
    version: str = "normal"  # normal / elderly
    history: Optional[List[ChatTurn]] = None  # 最近幾輪對話（不含本則）


@router.post("/chat")
def chat_with_xiaohe(body: ChatRequest):
    """與小禾 AI 對話"""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="請輸入訊息")

    # 選擇 persona
    if body.mode == "family":
        persona_key = "family"
    elif body.version == "elderly":
        persona_key = "patient_elderly"
    else:
        persona_key = "patient_normal"

    system_prompt = XIAOHE_PERSONAS[persona_key]

    # 把 history 限制在最近 12 輪，避免 token 爆掉
    hist = None
    if body.history:
        hist = [{"role": t.role, "content": t.content} for t in body.history[-12:]]

    try:
        reply = call_claude(system_prompt, body.message, history=hist)
    except Exception as e:
        logger.error(f"Xiaohe chat failed: {e}")
        reply = "抱歉，小禾現在有點忙，等一下再聊好嗎？如果你有任何不舒服，記得跟醫師說喔！"

    return {
        "reply": reply,
        "mode": body.mode,
        "version": body.version,
    }


@router.post("/chat/stream")
def chat_with_xiaohe_stream(body: ChatRequest):
    """與小禾 AI 對話 — 串流版本（SSE）。每個事件是一段 token，最後送 done"""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="請輸入訊息")

    if body.mode == "family":
        persona_key = "family"
    elif body.version == "elderly":
        persona_key = "patient_elderly"
    else:
        persona_key = "patient_normal"
    system_prompt = XIAOHE_PERSONAS[persona_key]

    hist = None
    if body.history:
        hist = [{"role": t.role, "content": t.content} for t in body.history[-12:]]

    def event_gen():
        try:
            for chunk in stream_claude(system_prompt, body.message, history=hist):
                yield "data: " + json.dumps({"delta": chunk}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"done": True}) + "\n\n"
        except Exception as e:
            logger.error(f"Xiaohe chat stream failed: {e}")
            fallback = "抱歉，小禾現在有點忙，等一下再聊好嗎？"
            yield "data: " + json.dumps({"delta": fallback}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"done": True, "error": str(e)}) + "\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # 關閉 nginx buffering
        },
    )


@router.get("/emotion-summary/{patient_id}")
def get_emotion_summary(patient_id: str):
    """回傳匿名情緒趨勢（不含對話內容，保護隱私）"""
    sb = get_supabase()
    since = (datetime.utcnow() - timedelta(days=30)).isoformat()
    result = sb.table("emotions").select("*").eq("patient_id", patient_id).gte("created_at", since).order("created_at").execute()
    records = result.data or []

    trend = [
        {"date": r.get("created_at", "")[:10], "score": r.get("score")}
        for r in records
    ]

    scores = [r.get("score", 0) for r in records if r.get("score")]
    avg = round(sum(scores) / len(scores), 1) if scores else None

    return {
        "trend": trend,
        "average": avg,
        "count": len(records),
    }
