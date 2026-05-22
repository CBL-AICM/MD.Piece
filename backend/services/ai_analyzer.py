"""症狀分析 — 給定症狀清單，呼叫 LLM 回傳結構化建議。

走 backend.services.llm_service.call_claude（預設 Ollama，雲端 fallback Groq / Anthropic），
可以避免單獨依賴 ANTHROPIC_API_KEY；任一 provider 通就能用。
"""
import json
import logging

from backend.services.llm_service import build_patient_facing_system, call_claude

logger = logging.getLogger(__name__)


_SYMPTOM_ANALYSIS_ROLE = (
    "【本次任務：症狀初步分析】\n"
    "病人會描述他的症狀，請給結構化的初步分析。conditions / advice / disclaimer 都是\n"
    "病人會直接讀到的文字 — 嚴格遵守上方風格層 [A][B][C]，特別是：\n"
    "  - 不直接放英文病名 / 拉丁學名 / 縮寫；必要時用括號加白話翻譯，\n"
    "    例：「胃食道逆流（俗稱火燒心，胃酸跑到食道）」\n"
    "  - 不用「鑑別診斷」「主訴」「次發性」這類醫療術語；改用「可能的原因」「最常見的情況」\n"
    "  - 病名後面用一句話解釋它是什麼\n"
    "  - 不用統計術語（盛行率、相對風險…）；改用「常見」「比較少見」這類詞\n"
    "  - 不替醫師下診斷（風格層 [C.9]）— conditions 是「可能的原因」，永遠建議就醫確認\n\n"
    "請以**純 JSON**回覆（不要 markdown code block、不要前後說明），結構：\n"
    "{\n"
    '  "conditions": [{"name": "可能原因（白話）", "likelihood": "高/中/低", "description": "用一句話告訴使用者這是什麼、為什麼會這樣"}],\n'
    '  "recommended_department": "建議看哪一科",\n'
    '  "urgency": "low/medium/high/emergency",\n'
    '  "advice": "建議怎麼做（繁體中文白話，2-4 句；遵守風格層）",\n'
    '  "disclaimer": "此回覆由 AI 整理，僅供參考；實際診療請依您的主治醫師為準。"\n'
    "}\n\n"
    "情境專屬規則：\n"
    "- conditions 至少列 1-3 種可能原因，由高到低排序；每一個都附 description 短句解釋\n"
    "- 出現胸痛、呼吸困難、意識改變、嚴重出血等紅旗症狀時 urgency=emergency\n"
    "- 持續發燒 > 39°C、嚴重疼痛、神經症狀為 high\n"
    "- 一般感冒、輕微不適為 low\n"
    "- recommended_department 給一般民眾聽得懂的科別（家醫科 / 內科 / 心臟科 / 腸胃科 / 神經內科 / 急診…）\n"
    "- advice 給可以馬上做的事：要先觀察什麼、什麼時候該掛號、在家可以怎麼緩解"
)


_SYSTEM_PROMPT = build_patient_facing_system(
    _SYMPTOM_ANALYSIS_ROLE,
    patient_context=None,
    include_examples=False,
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
