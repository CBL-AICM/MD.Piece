import anthropic
import base64
import json
import logging

logger = logging.getLogger(__name__)

# Claude API 呼叫服務
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告、藥袋辨識

client = anthropic.Anthropic()  # 讀取 ANTHROPIC_API_KEY


def call_claude(system_prompt: str, user_message: str) -> str:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    return message.content[0].text


def recognize_medicine_bag(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    用 Claude Vision 辨識藥袋照片，提取藥物資訊。

    回傳: {
        "medications": [
            {"name": "藥名", "dosage": "劑量", "frequency": "頻率",
             "category": "類別", "purpose": "用途", "instructions": "注意事項"}
        ]
    }
    """
    system = (
        "你是藥袋辨識助手。請仔細閱讀藥袋照片上的所有文字，提取藥物資訊。\n"
        "回覆必須是純 JSON 格式（不要 markdown code block），結構如下：\n"
        '{"medications": [{"name": "藥名", "dosage": "劑量如 500mg", '
        '"frequency": "服用頻率如 每日三次飯後", "category": "藥物類別如 降血糖藥", '
        '"purpose": "用途如 控制血糖", "instructions": "注意事項如 避免空腹服用"}]}\n\n'
        "規則：\n"
        "- 藥名用中文通用名，括號附英文學名\n"
        "- 如果看不清楚某欄位，填 null\n"
        "- 如果照片中有多種藥物，全部列出\n"
        "- category 使用常見分類：降血壓藥、降血糖藥、降血脂藥、止痛藥、抗生素、"
        "胃藥、抗凝血藥、利尿劑、氣管擴張劑、抗憂鬱藥、其他"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": "請辨識這張藥袋上的藥物資訊。"},
            ],
        }],
    )

    raw = message.content[0].text.strip()
    # 清除可能的 markdown code block 包裹
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        result = json.loads(raw)
        result["raw_text"] = raw
        return result
    except json.JSONDecodeError:
        logger.warning(f"Medicine bag recognition returned non-JSON: {raw[:200]}")
        return {"medications": [], "raw_text": raw}
