try:
    import anthropic
    _anthropic_available = True
except ImportError:
    anthropic = None
    _anthropic_available = False

import base64
import json
import logging

logger = logging.getLogger(__name__)

# Claude API 呼叫服務
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告、藥袋辨識

client = anthropic.Anthropic() if _anthropic_available else None  # 讀取 ANTHROPIC_API_KEY


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
        "你是藥袋辨識助手。台灣各家醫院（台大、榮總、長庚、亞東、診所…）藥袋版型各不相同，"
        "你的任務是**不管版型為何**，從照片的文字中萃取出以下「標準欄位」：\n\n"
        "標準欄位：\n"
        "  - name        藥名（中文通用名為主，括號附英文學名，例：布洛芬（Ibuprofen））\n"
        "  - dosage      單次劑量（例：500mg、1 顆、5ml）\n"
        "  - frequency   服用頻率（例：一天三次、每 8 小時一次、需要時服用）\n"
        "  - usage       用法/服用時機（例：飯前、飯後、睡前、空腹）\n"
        "  - duration    療程天數（例：7 天、長期服用；若無資訊留 null）\n"
        "  - category    藥物類別（降血壓藥、降血糖藥、降血脂藥、止痛藥、抗生素、"
        "胃藥、抗凝血藥、利尿劑、氣管擴張劑、抗憂鬱藥、其他）\n"
        "  - purpose     用途（例：控制血糖、緩解頭痛）\n"
        "  - instructions 注意事項（例：避免空腹、服藥期間不要喝酒）\n"
        "  - hospital    醫院/診所名稱（若藥袋上有；否則 null）\n"
        "  - prescribed_date 開立日期（YYYY-MM-DD；若無資訊留 null）\n\n"
        "回覆必須是純 JSON（不要 markdown code block），結構：\n"
        '{"medications": [{"name": "...", "dosage": "...", "frequency": "...", '
        '"usage": "...", "duration": "...", "category": "...", "purpose": "...", '
        '"instructions": "...", "hospital": "...", "prescribed_date": "..."}]}\n\n'
        "規則：\n"
        "- 每個欄位都必須存在（即使值為 null）\n"
        "- 看不清楚或藥袋沒寫的欄位 → 填 null，不要瞎猜\n"
        "- 一張藥袋可能包含多包藥物，**請逐包分開列出**\n"
        "- 寧可缺欄位，不要填入錯誤資訊"
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
