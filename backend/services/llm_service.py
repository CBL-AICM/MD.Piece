import base64
import json
import logging
import httpx

logger = logging.getLogger(__name__)

# 本地 LLM 服務（Ollama）
# 零成本、零隱私風險，所有資料不出本機
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告、藥袋辨識

OLLAMA_BASE = "http://localhost:11434"
TEXT_MODEL = "qwen2.5:7b"
VISION_MODEL = "llava:7b"


def call_claude(system_prompt: str, user_message: str) -> str:
    """文字生成（相容原 claude_service 簽名）"""
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": TEXT_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def recognize_medicine_bag(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    用本地 Vision 模型辨識藥袋照片，提取藥物資訊。

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

    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": VISION_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": "請辨識這張藥袋上的藥物資訊。",
                    "images": [image_base64],
                },
            ],
        },
        timeout=120.0,
    )
    resp.raise_for_status()

    raw = resp.json()["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Medicine bag recognition returned non-JSON: {raw[:200]}")
        return {"medications": [], "raw_text": raw}
