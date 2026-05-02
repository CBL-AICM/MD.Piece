"""
Memo router — 患者隨手記。
記錄想跟醫師說的話、回診期間發生的事、可附照片，
並能在回診前彙整成「診前報告」。
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from backend.db import get_supabase
from backend.models import MemoCreate, MemoUpdate
from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()


PREVISIT_SYSTEM_PROMPT = (
    "你是 MD.Piece 平台的診前報告助手。\n"
    "病人在這次回診間，把想跟醫師說的事、發生過的狀況用便條記下來了，\n"
    "你要把這些零散的便條整理成一份簡潔、有條理的『診前報告』，\n"
    "讓醫師在門診前 30 秒就能掌握重點。\n\n"
    "報告結構（使用 Markdown）：\n"
    "1. **這次最想跟醫師說的事**（最多 3 點，依重要性排序）\n"
    "2. **這段期間發生的狀況**（依時間順序，用條列描述）\n"
    "3. **附照片紀錄**（若有，描述照片標題與日期）\n"
    "4. **建議追問** —— 病人沒明說但值得醫師主動問的點\n\n"
    "規則：\n"
    "- 用繁體中文，語氣專業但親切\n"
    "- 不要憑空增添病人沒寫的內容\n"
    "- 若便條太少，誠實註明「資料不足」\n"
    "- 不要使用程式碼區塊"
)


# ─── List / 查詢 ────────────────────────────────────────────

@router.get("/")
def list_memos(
    patient_id: str,
    since: str | None = None,
    for_doctor: bool | None = None,
    limit: int = 100,
):
    """列出某位患者的 memo。可用 since 過濾日期、for_doctor 篩想跟醫師說的。"""
    sb = get_supabase()
    q = sb.table("memos").select("*").eq("patient_id", patient_id)
    if since:
        q = q.gte("created_at", since)
    if for_doctor is not None:
        q = q.eq("for_doctor", 1 if for_doctor else 0)
    result = q.order("created_at", desc=True).limit(limit).execute()
    return {"memos": result.data}


@router.get("/{memo_id}")
def get_memo(memo_id: str):
    sb = get_supabase()
    result = sb.table("memos").select("*").eq("id", memo_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到這則 memo")
    return result.data[0]


# ─── Create / Update / Delete ───────────────────────────────

@router.post("/")
def create_memo(body: MemoCreate):
    if not body.content and not body.photo_data:
        raise HTTPException(status_code=400, detail="memo 至少要有文字或照片")

    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    # bool → int for SQLite
    if "for_doctor" in data:
        data["for_doctor"] = 1 if data["for_doctor"] else 0
    if isinstance(data.get("event_date"), datetime):
        data["event_date"] = data["event_date"].isoformat()

    result = sb.table("memos").insert(data).execute()
    return result.data[0]


@router.put("/{memo_id}")
def update_memo(memo_id: str, body: MemoUpdate):
    sb = get_supabase()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="沒有提供更新資料")
    if "for_doctor" in data:
        data["for_doctor"] = 1 if data["for_doctor"] else 0
    if isinstance(data.get("event_date"), datetime):
        data["event_date"] = data["event_date"].isoformat()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = sb.table("memos").update(data).eq("id", memo_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到這則 memo")
    return result.data[0]


@router.delete("/{memo_id}")
def delete_memo(memo_id: str):
    sb = get_supabase()
    result = sb.table("memos").delete().eq("id", memo_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="找不到這則 memo")
    return {"message": "memo 已刪除", "id": memo_id}


# ─── 診前報告 ───────────────────────────────────────────────

@router.get("/{patient_id}/previsit-report")
def previsit_report(patient_id: str, days: int = 30):
    """
    根據近 N 天（預設 30 天）的 memo，產出一份診前報告給醫師看。
    會把『想跟醫師說』的條目放到最上面，發生事件依時序整理。
    """
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    result = (
        sb.table("memos")
        .select("*")
        .eq("patient_id", patient_id)
        .gte("created_at", since)
        .order("created_at")
        .execute()
    )
    memos = result.data or []

    if not memos:
        return {
            "patient_id": patient_id,
            "report": f"近 {days} 天沒有任何 memo 紀錄，沒有可整理的內容。",
            "memo_count": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "no_data",
        }

    # 區分「想跟醫師說的」與「自己留存的紀錄」
    for_doctor_items = []
    other_items = []
    photo_items = []

    for m in memos:
        date = (m.get("event_date") or m.get("created_at") or "")[:10]
        content = (m.get("content") or "").strip()
        caption = (m.get("photo_caption") or "").strip()
        has_photo = bool(m.get("photo_data"))

        line_parts = [f"[{date}]"]
        if content:
            line_parts.append(content)
        if caption:
            line_parts.append(f"（照片：{caption}）")
        elif has_photo:
            line_parts.append("（附照片）")
        line = " ".join(line_parts)

        if int(m.get("for_doctor", 1) or 0) == 1:
            for_doctor_items.append(line)
        else:
            other_items.append(line)

        if has_photo:
            photo_items.append(f"[{date}] {caption or '無說明'}")

    parts = [f"報告期間：近 {days} 天，共 {len(memos)} 則 memo\n"]
    if for_doctor_items:
        parts.append("【想跟醫師說的事】")
        parts.extend(f"- {x}" for x in for_doctor_items)
    if other_items:
        parts.append("\n【期間發生的紀錄】")
        parts.extend(f"- {x}" for x in other_items)
    if photo_items:
        parts.append("\n【附照片】")
        parts.extend(f"- {x}" for x in photo_items)

    user_message = "\n".join(parts)

    try:
        report_text = call_claude(PREVISIT_SYSTEM_PROMPT, user_message)
    except Exception as e:
        logger.warning(f"Pre-visit report AI generation failed: {e}")
        # AI 不可用 → 回傳純整理版（仍有用）
        report_text = "# 診前報告（原始整理）\n\n" + user_message

    # 標記為已納入報告
    try:
        for m in memos:
            sb.table("memos").update({"included_in_report": 1}).eq("id", m["id"]).execute()
    except Exception as e:
        logger.warning(f"Mark memos as included failed: {e}")

    return {
        "patient_id": patient_id,
        "report": report_text,
        "memo_count": len(memos),
        "for_doctor_count": len(for_doctor_items),
        "photo_count": len(photo_items),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "ai" if "AI" not in report_text[:30] else "fallback",
    }
