import base64
import json
import logging
import os
import httpx

logger = logging.getLogger(__name__)

# 多 provider LLM 服務
# - 本地開發：LLM_PROVIDER=ollama（預設）→ 零成本、資料不出本機
# - 雲端部署：LLM_PROVIDER=groq → 免費額度大、速度快，無需自架 GPU
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告、藥袋辨識、檢驗值解讀

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _call_ollama(system_prompt: str, user_message: str, history=None) -> str:
    msgs = [{"role": "system", "content": system_prompt}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user_message})
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": TEXT_MODEL,
            "stream": False,
            "messages": msgs,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _call_groq(system_prompt: str, user_message: str, history=None) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set; cannot use Groq provider")
    msgs = [{"role": "system", "content": system_prompt}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user_message})
    resp = httpx.post(
        f"{GROQ_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": msgs,
            "temperature": 0.4,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_claude(system_prompt: str, user_message: str, history=None) -> str:
    """文字生成（相容原 claude_service 簽名）— 依 LLM_PROVIDER 自動切換 provider

    history: 可選，[{role: 'user'|'assistant', content: str}, ...] 多輪歷史
    """
    if LLM_PROVIDER == "groq":
        return _call_groq(system_prompt, user_message, history)
    return _call_ollama(system_prompt, user_message, history)


# === Streaming =================================================================

def _stream_ollama(system_prompt: str, user_message: str, history=None):
    msgs = [{"role": "system", "content": system_prompt}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user_message})
    with httpx.stream(
        "POST",
        f"{OLLAMA_BASE}/api/chat",
        json={"model": TEXT_MODEL, "stream": True, "messages": msgs},
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk = (obj.get("message") or {}).get("content") or ""
            if chunk:
                yield chunk
            if obj.get("done"):
                break


def _stream_groq(system_prompt: str, user_message: str, history=None):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set; cannot use Groq provider")
    msgs = [{"role": "system", "content": system_prompt}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user_message})
    with httpx.stream(
        "POST",
        f"{GROQ_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": msgs,
            "temperature": 0.4,
            "stream": True,
        },
        timeout=60.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            # OpenAI 風格 SSE：以 "data: " 開頭
            if line.startswith("data: "):
                payload = line[len("data: "):].strip()
                if payload == "[DONE]":
                    break
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = (choices[0].get("delta") or {}).get("content") or ""
                if delta:
                    yield delta


def stream_claude(system_prompt: str, user_message: str, history=None):
    """串流文字生成（產生純文字片段的 generator）"""
    if LLM_PROVIDER == "groq":
        yield from _stream_groq(system_prompt, user_message, history)
    else:
        yield from _stream_ollama(system_prompt, user_message, history)


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
        result = json.loads(raw)
        result["raw_text"] = raw
        return result
    except json.JSONDecodeError:
        logger.warning(f"Medicine bag recognition returned non-JSON: {raw[:200]}")
        return {"medications": [], "raw_text": raw}
