import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from backend.db import get_supabase
from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)
router = APIRouter()

CHECKLIST_SYSTEM_PROMPT = (
    "你是 MD.Piece 平台的問診準備助手。\n"
    "根據患者近期的症狀記錄、情緒狀態和用藥情形，\n"
    "列出這次回診時最需要跟醫師確認的三件事。\n\n"
    "規則：\n"
    "1. 只列三件，依重要性排序\n"
    "2. 每件事用一句話描述，讓患者可以直接照著問\n"
    "3. 語氣親切，像朋友提醒你看醫生前要問什麼\n"
    "4. 使用繁體中文\n"
    "5. 回覆格式：純 JSON 陣列，每個元素是一個字串，不要 markdown\n"
    '範例：["最近頭痛頻率增加，需要調整止痛藥嗎？","情緒持續低落，是否需要心理支持？","新藥的副作用（胃不舒服）正常嗎？"]'
)

# 三十天整合報告 - LLM 生成臨床摘要、供醫師回診前使用

@router.get("/{patient_id}/monthly")
def get_monthly_report(patient_id: str):
    # 觸發 Claude Haiku 生成 30 天整合文字摘要
    return {"report": None, "generated_at": None}


@router.get("/{patient_id}/checklist")
def get_consultation_checklist(patient_id: str):
    """建議問診清單：根據近期數據，生成這次最需要確認的三件事"""
    sb = get_supabase()

    # 收集患者近期資料
    symptoms_result = sb.table("symptoms_log").select("*").eq("patient_id", patient_id).order("created_at", desc=True).limit(10).execute()
    emotions_result = sb.table("emotions").select("*").eq("patient_id", patient_id).order("created_at", desc=True).limit(10).execute()
    medications_result = sb.table("medications").select("*").eq("patient_id", patient_id).eq("active", 1).execute()

    symptoms_data = symptoms_result.data or []
    emotions_data = emotions_result.data or []
    medications_data = medications_result.data or []

    # 如果完全沒有資料，回傳預設清單
    if not symptoms_data and not emotions_data and not medications_data:
        return {
            "patient_id": patient_id,
            "checklist": [
                "目前身體整體感覺如何？有沒有新的不舒服？",
                "目前的藥有沒有按時吃？有沒有什麼困難？",
                "生活和心情上有沒有需要醫師幫忙的地方？",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "default",
        }

    # 組裝 user prompt
    parts = []
    if symptoms_data:
        symptom_texts = []
        for s in symptoms_data:
            symptoms = s.get("symptoms", [])
            if isinstance(symptoms, list):
                symptom_texts.append("、".join(symptoms))
            elif isinstance(symptoms, str):
                symptom_texts.append(symptoms)
        if symptom_texts:
            parts.append(f"近期症狀記錄：{'; '.join(symptom_texts)}")

    if emotions_data:
        scores = [str(e.get("score", "?")) for e in emotions_data]
        notes = [e.get("note", "") for e in emotions_data if e.get("note")]
        parts.append(f"近期情緒評分（1-5）：{', '.join(scores)}")
        if notes:
            parts.append(f"情緒備註：{'; '.join(notes[:5])}")

    if medications_data:
        med_names = [m.get("name", "未知藥物") for m in medications_data]
        parts.append(f"目前用藥：{', '.join(med_names)}")

    user_message = "以下是這位患者的近期健康數據：\n" + "\n".join(parts)

    try:
        import json
        raw = call_claude(CHECKLIST_SYSTEM_PROMPT, user_message)
        # 清除可能的 markdown code block 包裹
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        checklist = json.loads(raw)
        if not isinstance(checklist, list):
            raise ValueError("Expected a JSON array")
    except Exception as e:
        logger.warning(f"Claude checklist parsing failed: {e}")
        checklist = [
            "請跟醫師討論近期的症狀變化",
            "確認目前的用藥是否需要調整",
            "聊聊最近的生活和心情狀況",
        ]

    return {
        "patient_id": patient_id,
        "checklist": checklist[:3],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "ai",
    }
