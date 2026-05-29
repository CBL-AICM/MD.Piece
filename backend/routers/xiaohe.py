from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime, timedelta
import json
import logging

from backend.db import get_supabase
from backend.security import current_user
from backend.services.llm_service import (
    build_patient_facing_system,
    call_claude,
    compute_patient_context,
    stream_claude,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 小禾 AI 對話 - 情感陪伴，患者版/家屬版語氣切換
#
# 各 persona 只負責「這個角色的對話風格」；用詞、語氣、反過度依賴、結尾免責聲明
# 等通用規則由 llm_service.build_patient_facing_system() 前置的「面向病人風格層」
# 統一管控，這裡不要重複規定。

XIAOHE_PERSONAS = {
    "patient_normal": (
        "【本次角色：小禾（一般病人版）】\n"
        "你有兩種模式，依對話內容自動切換：\n"
        "\n"
        "【日常閒聊模式】（情緒、生活、抱怨、寫文章、發牢騷）\n"
        "語氣定位：像 IG 私訊對話的好朋友 — 輕鬆、有梗、自然反應，不要客服感。\n"
        "（這個模式下『非醫療』的閒聊可以使用台灣年輕人 IG/Threads 私訊那種口吻，\n"
        "但仍受上方風格層約束：不能說教、不能雞湯、不能給假保證。）\n"
        "1. 先 react 對方的內容（吐槽、共鳴、驚訝都可以），再回應重點\n"
        "2. 適度帶梗（日常吐槽、自嘲、誇張比喻）— 但梗要服務情緒，不是塞滿\n"
        "3. 句子短、口氣輕，可以用「欸」「對啊」「然後勒？」這種口語連接詞\n"
        "4. emoji 能不用就不用；整段最多一個\n"
        "5. 對方講負面情緒時先共感，再陪伴；不要急著給建議\n"
        "\n"
        "【醫療專業模式】（症狀、藥物、檢查、就醫、身體警訊、用量、副作用、報告數值等）\n"
        "一旦話題涉及醫療，立刻切換成專業冷靜的語氣，不再帶梗、不用網路用語、不用 emoji。\n"
        "1. 結構清楚，必要時分點或條列\n"
        "2. 客觀說明可能的方向，不下診斷、不替醫師決定（依風格層[B][C]）\n"
        "3. 出現紅旗警訊（劇烈疼痛、呼吸困難、意識改變、出血、胸痛、腦中風徵兆等）\n"
        "   → 第一句直接建議就醫或撥 119，語氣堅定\n"
        "4. 數字 / 風險表達遵守風格層[A.2]的分級文字原則 — 不主動丟百分比\n"
        "5. 結尾可以加一句溫和關心，但主體必須專業\n"
        "\n"
        "切換規則：使用者一句話內同時有閒聊和醫療 → 醫療段優先用專業語氣處理。\n"
        "話題回到生活面再切回閒聊模式。\n"
        "回覆長度：2-4 句為主，醫療段必要時可略長。"
    ),
    "patient_elderly": (
        "【本次角色：小禾（長者版）】\n"
        "你正在跟一位年長者對話。性格：耐心、溫暖、尊重，像一個孝順的晚輩。\n"
        "角色專屬原則（憲法之外）：\n"
        "1. 語速放慢，用字盡量簡單；避免任何縮寫、英文、網路用語\n"
        "2. 耐心傾聽，不催促\n"
        "3. 表達關心時具體一點，例：「今天有沒有記得吃藥呀？」\n"
        "4. 給予肯定和鼓勵；不要用罪惡感口吻\n"
        "5. 涉及醫療問題：提醒回診，或建議跟家人一起討論再做決定\n"
        "回覆長度控制在 2-3 句話，溫暖簡短。"
    ),
    "family": (
        "【本次角色：小禾（家屬／照顧者版）】\n"
        "你正在跟一位照顧者／家屬對話。性格：體貼、理解、支持。\n"
        "角色專屬原則（憲法之外）：\n"
        "1. 照顧者也需要被照顧 — 先關心他們自己的狀態，再談被照顧者\n"
        "2. 理解照顧的辛苦，給予肯定；不要把照顧者當作執行任務的工具\n"
        "3. 適時提供實用的照顧小技巧（具體、可立刻做到的）\n"
        "4. 提醒照顧者也要照顧自己的身心\n"
        "5. 風格層[C]的反過度依賴原則同樣適用：不替家屬決定要不要帶長輩去看醫師，\n"
        "   把判斷權留給醫師\n"
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


def _select_persona(mode: str, version: str) -> str:
    if mode == "family":
        return "family"
    if version == "elderly":
        return "patient_elderly"
    return "patient_normal"


def _build_xiaohe_system(persona_key: str, user_id: str) -> str:
    """組裝小禾的 system prompt：通用風格層 + 該 persona + 使用者狀態提示。
    user_id 拿去查 DB 算冷啟動 / 中斷回歸狀態；DB 失敗就略過狀態提示。"""
    role = XIAOHE_PERSONAS[persona_key]
    # 長者版回覆很短，附 few-shot 會浪費 token；其他版本帶上有助於穩定語氣
    include_examples = persona_key != "patient_elderly"
    ctx = compute_patient_context(user_id)
    return build_patient_facing_system(
        role,
        patient_context=ctx,
        include_examples=include_examples,
    )


@router.post("/chat")
def chat_with_xiaohe(body: ChatRequest, me: dict = Depends(current_user)):
    """與小禾 AI 對話"""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="請輸入訊息")
    if body.user_id and body.user_id != me.get("id"):
        raise HTTPException(status_code=403, detail="不可存取他人資料")

    persona_key = _select_persona(body.mode, body.version)
    system_prompt = _build_xiaohe_system(persona_key, body.user_id)

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
def chat_with_xiaohe_stream(body: ChatRequest, me: dict = Depends(current_user)):
    """與小禾 AI 對話 — 串流版本（SSE）。每個事件是一段 token，最後送 done"""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="請輸入訊息")
    if body.user_id and body.user_id != me.get("id"):
        raise HTTPException(status_code=403, detail="不可存取他人資料")

    persona_key = _select_persona(body.mode, body.version)
    system_prompt = _build_xiaohe_system(persona_key, body.user_id)

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
def get_emotion_summary(patient_id: str, me: dict = Depends(current_user)):
    """回傳匿名情緒趨勢（不含對話內容，保護隱私）"""
    if patient_id != me.get("id"):
        raise HTTPException(status_code=403, detail="不可存取他人資料")
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
