"""症狀分析 — 給定症狀清單，呼叫 LLM 回傳結構化建議。

走 backend.services.llm_service.call_claude（預設 Ollama，雲端 fallback Groq / Anthropic），
可以避免單獨依賴 ANTHROPIC_API_KEY；任一 provider 通就能用。
"""
import json
import logging

from backend.services.llm_service import call_claude

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "你是醫療輔助 AI，根據病患描述的症狀提供初步分析與建議。\n"
    "重要：你的分析僅供參考，不構成醫療診斷。請務必建議使用者就醫。\n\n"
    "請以**純 JSON**回覆（不要 markdown code block、不要前後說明），結構：\n"
    "{\n"
    '  "conditions": [{"name": "可能病因", "likelihood": "高/中/低"}],\n'
    '  "recommended_department": "建議就診科別",\n'
    '  "urgency": "low/medium/high/emergency",\n'
    '  "advice": "具體建議（繁體中文，2-4 句）",\n'
    '  "disclaimer": "免責聲明"\n'
    "}\n\n"
    "規則：\n"
    "- conditions 至少列 1-3 種可能病因，由高到低排序\n"
    "- 出現胸痛、呼吸困難、意識改變、嚴重出血等紅旗症狀時 urgency=emergency\n"
    "- 持續發燒 > 39°C、嚴重疼痛、神經症狀為 high\n"
    "- 一般感冒、輕微不適為 low\n"
    "- recommended_department 給具體科別（家醫科 / 內科 / 心臟科 / 神經內科 / 急診…）\n"
    "- advice 直接、可執行（先做什麼、何時該就醫、自我照護建議）\n"
    "- disclaimer 簡短提醒這是參考非診斷"
)


def _parse_json(raw: str) -> dict | None:
    """容錯把 LLM 輸出當 JSON 解析。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not text.startswith("{"):
        l = text.find("{")
        r = text.rfind("}")
        if l != -1 and r != -1 and r > l:
            text = text[l : r + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Symptom analysis non-JSON: {raw[:200]}")
        return None


async def analyze_symptoms(
    symptoms: list[str],
    patient_age: int | None = None,
    patient_gender: str | None = None,
) -> dict:
    """呼叫 LLM 分析症狀。任一 LLM provider 通就回 AI 結果，全失敗才走規則式 fallback。"""
    parts = [f"症狀：{', '.join(symptoms)}"]
    if patient_age:
        parts.append(f"年齡：{patient_age} 歲")
    if patient_gender:
        parts.append(f"性別：{patient_gender}")
    user_message = "\n".join(parts)

    try:
        raw = call_claude(_SYSTEM_PROMPT, user_message)
    except Exception as e:
        logger.warning(f"call_claude 全部失敗：{e}")
        return _fallback_analysis(symptoms)

    parsed = _parse_json(raw)
    if not parsed:
        return _fallback_analysis(symptoms)

    # Sanity check 必填欄位，缺的補預設
    parsed.setdefault("conditions", [])
    parsed.setdefault("recommended_department", "家醫科")
    parsed.setdefault("urgency", "low")
    parsed.setdefault("advice", "建議就醫，由醫師評估。")
    parsed.setdefault("disclaimer", "此分析僅供參考，不構成醫療診斷。如有不適請立即就醫。")
    return parsed


def _fallback_analysis(symptoms: list[str]) -> dict:
    """LLM 全部失敗時的規則式 fallback（保底，使用者體驗不會 0 結果）。"""
    urgency_keywords = {
        "chest pain": "emergency", "胸痛": "emergency",
        "breathing difficulty": "high", "呼吸困難": "high",
        "high fever": "high", "高燒": "high",
        "意識": "emergency", "癱瘓": "emergency",
        "出血": "high",
    }
    urgency = "low"
    for symptom in symptoms:
        s = (symptom or "").lower()
        for kw, urg in urgency_keywords.items():
            if kw in s:
                urgency = urg
                break

    return {
        "conditions": [{"name": "需要醫師評估", "likelihood": "未知"}],
        "recommended_department": "家醫科",
        "urgency": urgency,
        "advice": f"您描述了：{', '.join(symptoms)}。建議儘速就醫，由醫師進行專業評估。",
        "disclaimer": "AI 分析服務暫時無法使用，此為系統規則式回覆；請以醫師意見為準。",
    }
