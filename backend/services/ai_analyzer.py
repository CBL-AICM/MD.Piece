import os
import json
import anthropic


async def analyze_symptoms(
    symptoms: list[str],
    patient_age: int | None = None,
    patient_gender: str | None = None,
) -> dict:
    """使用 Claude API 分析症狀，回傳結構化結果。"""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _fallback_analysis(symptoms)

    client = anthropic.Anthropic(api_key=api_key)

    patient_context = ""
    if patient_age or patient_gender:
        parts = []
        if patient_age:
            parts.append(f"年齡：{patient_age}歲")
        if patient_gender:
            parts.append(f"性別：{patient_gender}")
        patient_context = f"\n病患資訊：{', '.join(parts)}"

    system_prompt = """你是一個醫療輔助 AI，負責根據症狀提供初步分析建議。
重要：你的分析僅供參考，不構成醫療診斷。請務必建議使用者就醫。

請以 JSON 格式回覆，包含以下欄位：
{
  "conditions": [{"name": "可能病因", "likelihood": "高/中/低"}],
  "recommended_department": "建議就診科別",
  "urgency": "low/medium/high/emergency",
  "advice": "具體建議（繁體中文）",
  "disclaimer": "免責聲明"
}

只回覆 JSON，不要加其他文字。"""

    user_message = f"症狀：{', '.join(symptoms)}{patient_context}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text
        result = json.loads(text)
        return result
    except (json.JSONDecodeError, Exception):
        return _fallback_analysis(symptoms)


def _fallback_analysis(symptoms: list[str]) -> dict:
    """當 AI 不可用時的備用分析。"""
    urgency_keywords = {
        "chest pain": "emergency",
        "胸痛": "emergency",
        "breathing difficulty": "high",
        "呼吸困難": "high",
        "high fever": "high",
        "高燒": "high",
    }

    urgency = "low"
    for symptom in symptoms:
        s = symptom.lower()
        if s in urgency_keywords:
            urgency = urgency_keywords[s]
            break
        for kw, urg in urgency_keywords.items():
            if kw in s:
                urgency = urg
                break

    return {
        "conditions": [{"name": "需要醫師評估", "likelihood": "N/A"}],
        "recommended_department": "家醫科",
        "urgency": urgency,
        "advice": f"您描述了以下症狀：{', '.join(symptoms)}。建議儘速就醫，由醫師進行專業評估。",
        "disclaimer": "此為系統基本建議，非 AI 分析結果。請設定 ANTHROPIC_API_KEY 以啟用 AI 分析功能。",
    }
