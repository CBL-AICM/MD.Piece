import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import get_supabase
from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()

# 小禾 AI 對話 — Claude Haiku 情感陪伴，患者版/家屬版語氣切換

XIAOHE_SYSTEM = {
    "patient": {
        "normal": (
            "你是「小禾」，MD.Piece 平台上的 AI 情緒支持夥伴。\n"
            "你像一位溫暖的朋友，陪伴正在經歷健康困擾的患者。\n\n"
            "核心原則：\n"
            "1. 先理解感受 — 患者說什麼，你先回應他的情緒，不急著給建議\n"
            "2. 不說教 — 不要說「你應該」「你必須」\n"
            "3. 不給醫療建議 — 你不是醫生，遇到醫療問題引導諮詢醫師\n"
            "4. 語氣活潑俏皮但真誠 — 像好朋友聊天，適當用顏文字\n"
            "5. 尊重隱私 — 不主動追問敏感細節\n\n"
            "回覆簡短溫暖（50-150 字），不要長篇大論。使用繁體中文。"
        ),
        "elderly": (
            "你是「小禾」，MD.Piece 平台上的 AI 情緒支持夥伴。\n"
            "你正在陪伴一位長輩，要特別耐心、溫暖。\n\n"
            "核心原則：\n"
            "1. 說話慢慢來，用詞簡單，句子短\n"
            "2. 像孫子孫女跟阿公阿嬤聊天一樣親切\n"
            "3. 多用肯定和鼓勵的話\n"
            "4. 不說教，不催促\n"
            "5. 遇到醫療問題，溫柔提醒他們問醫生\n\n"
            "回覆簡短（30-100 字），不要用太多符號或顏文字。使用繁體中文。"
        ),
    },
    "family": {
        "normal": (
            "你是「小禾」，MD.Piece 平台上的 AI 情緒支持夥伴。\n"
            "你正在陪伴一位照顧者（家屬），他們承受著很大的壓力。\n\n"
            "核心原則：\n"
            "1. 理解照顧者的疲憊和壓力 — 照顧別人的人也需要被照顧\n"
            "2. 不要說「辛苦了但你要堅強」— 允許他們脆弱\n"
            "3. 適時提醒他們也要照顧自己\n"
            "4. 語氣溫暖支持，像一位懂你的朋友\n"
            "5. 遇到醫療問題，引導諮詢醫療團隊\n\n"
            "回覆簡短溫暖（50-150 字）。使用繁體中文。"
        ),
        "elderly": (
            "你是「小禾」，MD.Piece 平台上的 AI 情緒支持夥伴。\n"
            "你正在陪伴一位年長的照顧者，他們可能也有健康上的負擔。\n\n"
            "核心原則：\n"
            "1. 說話要慢、要清楚、要溫柔\n"
            "2. 理解他們照顧家人的辛苦\n"
            "3. 提醒他們自己的健康也很重要\n"
            "4. 多給予肯定和感謝\n"
            "5. 用詞簡單，不要太多術語\n\n"
            "回覆簡短（30-100 字），溫暖耐心。使用繁體中文。"
        ),
    },
}

FALLBACK_REPLY = "抱歉，小禾現在有點累了，等一下再聊好嗎？"


class ChatRequest(BaseModel):
    user_id: str
    message: str
    mode: str = "patient"     # patient / family
    version: str = "normal"   # normal / elderly


# ── 對話 ─────────────────────────────────────────────────────


@router.post("/chat")
def chat_with_xiaohe(body: ChatRequest):
    """小禾對話：根據模式與版本切換語氣"""
    if body.mode not in ("patient", "family"):
        raise HTTPException(status_code=400, detail="mode 必須是 patient 或 family")
    if body.version not in ("normal", "elderly"):
        raise HTTPException(status_code=400, detail="version 必須是 normal 或 elderly")

    system_prompt = XIAOHE_SYSTEM[body.mode][body.version]
    sb = get_supabase()

    # 取最近對話歷史作為上下文（最多 6 輪）
    history = (
        sb.table("xiaohe_conversations")
        .select("*")
        .eq("user_id", body.user_id)
        .order("created_at", desc=True)
        .limit(6)
        .execute()
    )

    context_parts = []
    if history.data:
        for msg in reversed(history.data):
            context_parts.append(f"使用者：{msg.get('user_message', '')}")
            context_parts.append(f"小禾：{msg.get('reply', '')}")

    user_message = body.message
    if context_parts:
        user_message = (
            "（以下是最近的對話紀錄，幫助你理解脈絡）\n"
            + "\n".join(context_parts)
            + f"\n\n使用者：{body.message}"
        )

    try:
        reply = call_claude(system_prompt, user_message)
    except Exception as e:
        logger.error(f"Xiaohe chat error: {e}")
        reply = FALLBACK_REPLY

    # 儲存對話紀錄
    sb.table("xiaohe_conversations").insert({
        "user_id": body.user_id,
        "user_message": body.message,
        "reply": reply,
        "mode": body.mode,
        "version": body.version,
    }).execute()

    return {"reply": reply, "mode": body.mode, "version": body.version}


# ── 情緒摘要（隱私保護：只回傳趨勢，不含對話內容）────────


@router.get("/emotion-summary/{patient_id}")
def get_emotion_summary(patient_id: str):
    """回傳匿名情緒趨勢（不含對話內容，保護隱私）"""
    sb = get_supabase()
    emotions = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(14)
        .execute()
    )

    records = emotions.data or []
    if not records:
        return {"trend": [], "summary": "尚無情緒記錄", "average_score": None}

    trend = [
        {"date": r.get("created_at", "")[:10], "score": r.get("score")}
        for r in reversed(records)
    ]

    scores = [r.get("score", 3) for r in records]
    avg = sum(scores) / len(scores)

    if avg >= 4:
        summary = "近期情緒狀態良好，持續保持"
    elif avg >= 3:
        summary = "情緒大致穩定，偶有波動屬正常"
    elif avg >= 2:
        summary = "近期情緒偏低落，建議多留意"
    else:
        summary = "情緒持續低落，建議尋求專業支持"

    return {"trend": trend, "summary": summary, "average_score": round(avg, 1)}


# ── 對話歷史 ─────────────────────────────────────────────────


@router.get("/history/{user_id}")
def get_chat_history(
    user_id: str,
    limit: int = Query(20, description="最近幾筆對話"),
):
    """取得小禾對話歷史"""
    sb = get_supabase()
    result = (
        sb.table("xiaohe_conversations")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"conversations": result.data or []}
