import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import get_supabase
from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()

# 小禾陪伴 - 情緒對話 + 靜默守護心理危機偵測

XIAOHE_PERSONAS = {
    "patient_normal": (
        "你是「小禾」，MD.Piece 平台的 AI 陪伴角色。\n"
        "對話設計原則（嚴格遵守）：\n"
        "1. 先理解感受，不急著給建議；不說教、不批判\n"
        "2. 不強迫對方行動；不推銷外部資源\n"
        "3. 用輕鬆親切的語氣，適時用 emoji；繁體中文，口語化\n"
        "4. 涉及醫療問題僅輕輕提醒「可以跟醫師說喔」，不取代醫師\n"
        "5. 回覆 2-4 句話，自然對話"
    ),
    "patient_elderly": (
        "你是「小禾」，正在跟一位年長者對話。\n"
        "原則：耐心、溫暖、尊重；用字簡單、語速放慢；給予肯定；\n"
        "涉及醫療提醒就醫或跟家人討論；2-3 句話。"
    ),
    "family": (
        "你是「小禾」，正在跟一位照顧者/家屬對話。\n"
        "原則：照顧者也需要被照顧，先關心他們；理解辛苦並肯定；\n"
        "適時提供實用照顧小技巧；2-4 句話。"
    ),
}

# 靜默守護關鍵字 — 不展示給患者，只用於後台累積評分
CRISIS_PATTERNS = {
    "suicidal_ideation": [
        r"想死", r"不想活", r"結束自己", r"結束生命", r"消失就好",
        r"離開這個世界", r"自殺", r"了結", r"輕生",
    ],
    "self_harm": [r"傷害自己", r"割自己", r"打自己"],
    "hopelessness": [r"沒有希望", r"沒有意義", r"撐不下去", r"撐不住", r"放棄了"],
    "isolation": [r"沒人在乎", r"沒有人懂", r"孤單", r"一個人面對"],
}

# 累積觸發門檻
CRISIS_THRESHOLD = 3  # 30 天內累積 3 次以上 → 心理危機提醒
CRITICAL_THRESHOLD = 5  # 5 次以上 → critical 等級


class ChatRequest(BaseModel):
    user_id: str
    message: str
    mode: str = "patient"  # patient / family
    version: str = "normal"  # normal / elderly


@router.post("/chat")
def chat_with_xiaohe(body: ChatRequest):
    """與小禾 AI 對話。對話內容不傳醫師端，僅靜默累積危機評分。"""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="請輸入訊息")

    # 偵測危機關鍵字（靜默，不告訴使用者）
    crisis_tags = _detect_crisis(body.message)

    # 選擇 persona
    if body.mode == "family":
        persona_key = "family"
    elif body.version == "elderly":
        persona_key = "patient_elderly"
    else:
        persona_key = "patient_normal"

    system_prompt = XIAOHE_PERSONAS[persona_key]

    # 若偵測到危機，補強系統提示但仍不推資源
    if crisis_tags:
        system_prompt += (
            "\n\n（內部提示：剛才的訊息出現了負面情緒。請更溫柔地陪伴，"
            "先承認他的感受，不要說『去找專業協助』或推送資源。"
            "在對話最後，可以輕聲問一句『你願意跟我多說一點嗎？』）"
        )

    try:
        reply = call_claude(system_prompt, body.message)
    except Exception as e:
        logger.error(f"Xiaohe chat failed: {e}")
        reply = "嗯⋯⋯我有聽到。今天怎麼了，願意再跟我說多一點嗎？"

    # 寫入對話紀錄（reply 公開、user_message 加密處理留待 Supabase RLS）
    sb = get_supabase()
    try:
        sb.table("xiaohe_conversations").insert({
            "user_id": body.user_id,
            "user_message": body.message,
            "reply": reply,
            "mode": body.mode,
            "version": body.version,
        }).execute()
    except Exception as e:
        logger.warning(f"Persist conversation failed: {e}")

    # 靜默守護：累積評分達門檻 → 寫入匿名 alert（不含對話內容）
    if crisis_tags:
        _maybe_create_crisis_alert(sb, body.user_id, crisis_tags)

    return {
        "reply": reply,
        "mode": body.mode,
        "version": body.version,
    }


def _detect_crisis(text: str) -> list[str]:
    """從訊息內容偵測危機分類；回傳觸發到的標籤"""
    hits = []
    for tag, patterns in CRISIS_PATTERNS.items():
        for p in patterns:
            if re.search(p, text):
                hits.append(tag)
                break
    return hits


def _maybe_create_crisis_alert(sb, user_id: str, tags: list[str]):
    """累積最近 30 天的危機觸發次數，達門檻才寫入醫師端 alert（匿名、不含對話）"""
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    convs = (
        sb.table("xiaohe_conversations")
        .select("*")
        .eq("user_id", user_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    crisis_count = 0
    for c in convs:
        msg = c.get("user_message", "") or ""
        if _detect_crisis(msg):
            crisis_count += 1
    crisis_count += 1  # 加上本次

    if crisis_count < CRISIS_THRESHOLD:
        return

    severity = "critical" if crisis_count >= CRITICAL_THRESHOLD else "high"
    title = "靜默守護觸發：心理狀態建議評估"

    try:
        # 避免重複寫入：檢查 24 小時內是否已有同一患者的 psych_crisis alert
        recent = (
            sb.table("alerts")
            .select("*")
            .eq("patient_id", user_id)
            .eq("alert_type", "psych_crisis")
            .execute()
            .data
            or []
        )
        latest = max(recent, key=lambda a: a.get("created_at", ""), default=None)
        if latest:
            created = latest.get("created_at", "")
            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - ts < timedelta(hours=24):
                    return
            except Exception:
                pass

        sb.table("alerts").insert({
            "patient_id": user_id,
            "alert_type": "psych_crisis",
            "severity": severity,
            "title": title,
            "detail": "近 30 天累積偵測到心理風險訊號，建議於下次回診評估心理狀態。詳細內容受隱私保護不顯示。",
            "metadata": {"crisis_count_30d": crisis_count, "categories": list(set(tags))},
            "source": "xiaohe_silent_guardian",
        }).execute()
    except Exception as e:
        logger.warning(f"Create crisis alert failed: {e}")


@router.get("/emotion-summary/{patient_id}")
def get_emotion_summary(patient_id: str):
    """匿名情緒趨勢（不含對話內容）"""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    result = (
        sb.table("emotions")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .order("created_at")
        .execute()
    )
    records = result.data or []

    trend = [
        {"date": r.get("created_at", "")[:10], "score": r.get("score")}
        for r in records
    ]
    scores = [r.get("score", 0) for r in records if r.get("score")]
    avg = round(sum(scores) / len(scores), 1) if scores else None

    return {"trend": trend, "average": avg, "count": len(records)}


@router.get("/silent-guardian/{patient_id}")
def silent_guardian_status(patient_id: str):
    """
    醫師端用：取得靜默守護的累積指標（不含任何對話內容）。
    僅回傳累積次數與分類分佈。
    """
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    convs = (
        sb.table("xiaohe_conversations")
        .select("user_message,created_at")
        .eq("user_id", patient_id)
        .gte("created_at", since)
        .execute()
        .data
        or []
    )
    category_counts: dict[str, int] = {}
    crisis_count = 0
    for c in convs:
        tags = _detect_crisis(c.get("user_message", "") or "")
        if tags:
            crisis_count += 1
            for t in tags:
                category_counts[t] = category_counts.get(t, 0) + 1

    if crisis_count >= CRITICAL_THRESHOLD:
        level = "critical"
    elif crisis_count >= CRISIS_THRESHOLD:
        level = "warning"
    else:
        level = "stable"

    return {
        "patient_id": patient_id,
        "crisis_count_30d": crisis_count,
        "level": level,
        "categories": category_counts,
        "message": (
            "建議下次回診評估心理狀態" if level != "stable"
            else "近 30 天無顯著心理風險訊號"
        ),
    }
