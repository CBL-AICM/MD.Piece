import json
import logging
import os
import re
import httpx

logger = logging.getLogger(__name__)

# 雙後端設計：
# - 線上（Vercel）：設 ANTHROPIC_API_KEY → 走 Claude API（vision + text 都跑）
# - 本機開發：未設 KEY → 走 Ollama（llava + qwen2.5）
# 兩者皆失敗時上層 router 已有 fallback 訊息，不會噴 500

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
USE_CLAUDE = bool(ANTHROPIC_API_KEY)

# Claude 模型（線上預設）
CLAUDE_VISION_MODEL = os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")
CLAUDE_TEXT_MODEL = os.getenv("ANTHROPIC_TEXT_MODEL", "claude-haiku-4-5-20251001")

# Ollama（本機 fallback）
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")
VISION_TIMEOUT_S = float(os.getenv("OLLAMA_VISION_TIMEOUT", "300"))
TEXT_TIMEOUT_S = float(os.getenv("OLLAMA_TEXT_TIMEOUT", "180"))

# Lazy import — anthropic 是線上才需要的相依
_anthropic_client = None


def _get_claude():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


# ── 共用：JSON 抽取（容忍 markdown / 前後說明 / 平衡括號） ──

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str) -> dict | None:
    if not raw:
        return None
    s = raw.strip()
    s = re.sub(r"```(?:json|JSON)?\s*", "", s)
    s = s.replace("```", "")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    m = _JSON_OBJ_RE.search(s)
    if not m:
        return None
    candidate = m.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    start = candidate.find("{")
    depth = 0
    for i in range(start, len(candidate)):
        ch = candidate[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(candidate[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# ── 文字生成 ──────────────────────────────────────────────

def call_claude(system_prompt: str, user_message: str) -> str:
    """文字生成（保留原函式名以相容呼叫端）。Claude 優先，否則 Ollama。"""
    if USE_CLAUDE:
        try:
            client = _get_claude()
            resp = client.messages.create(
                model=CLAUDE_TEXT_MODEL,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user_message}],
            )
            return "".join(b.text for b in resp.content if hasattr(b, "text"))
        except Exception as e:
            logger.error(f"Claude text call failed, falling back to Ollama: {e}")
            # 落到 Ollama 路徑

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
        timeout=TEXT_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


# ── 藥袋辨識（vision） ────────────────────────────────────

_RECOGNIZE_SYSTEM = (
    "你是台灣藥袋 OCR 助手。仔細閱讀照片中所有中英文文字，把每一包藥物資訊抽成 JSON。\n"
    "台灣各家醫院（台大、榮總、長庚、亞東、診所）藥袋版型不同，但都包含藥名、劑量、頻率。\n\n"
    "輸出唯一一個 JSON 物件（不要 markdown、不要任何說明）：\n"
    '{"medications":[{"name":"...","dosage":"...","frequency":"...",'
    '"usage":"...","duration":"...","category":"...","purpose":"...",'
    '"instructions":"...","hospital":"...","prescribed_date":"..."}]}\n\n'
    "欄位說明：\n"
    "- name: 中文通用名為主，附英文學名，例：布洛芬 (Ibuprofen)\n"
    "- dosage: 單次劑量，例：500mg / 1 顆 / 5ml\n"
    "- frequency: 服用頻率，例：一天三次 / 每 8 小時 / 需要時\n"
    "- usage: 飯前 / 飯後 / 睡前 / 空腹\n"
    "- duration: 療程，例：7 天 / 長期\n"
    "- category: 降血壓藥 / 降血糖藥 / 止痛藥 / 抗生素 / 胃藥 / 其他\n"
    "- purpose: 用途，例：控制血糖、緩解頭痛\n"
    "- instructions: 注意事項\n"
    "- hospital: 醫院名稱\n"
    "- prescribed_date: YYYY-MM-DD\n"
    "- 看不清楚或缺字 → 用 null，不要瞎猜\n"
    "- 一張藥袋可能多包藥，逐包分開列出"
)


def _recognize_via_claude(image_base64: str, media_type: str) -> dict:
    client = _get_claude()
    resp = client.messages.create(
        model=CLAUDE_VISION_MODEL,
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": _RECOGNIZE_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type or "image/jpeg",
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": "請仔細閱讀這張藥袋的所有文字（中英文都看），把每一包藥都寫成 JSON。"},
            ],
        }],
    )
    raw = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    return raw


def _recognize_via_ollama(image_base64: str) -> str:
    payload = {
        "model": VISION_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": _RECOGNIZE_SYSTEM},
            {
                "role": "user",
                "content": "請仔細閱讀這張藥袋的所有文字（中英文都看），把每一包藥都寫成 JSON。",
                "images": [image_base64],
            },
        ],
    }
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE}/api/chat",
                json=payload,
                timeout=VISION_TIMEOUT_S,
            )
            resp.raise_for_status()
            return (resp.json().get("message") or {}).get("content", "").strip()
        except (httpx.TimeoutException, httpx.ReadTimeout) as e:
            logger.warning(f"ollama recognize attempt {attempt + 1} timeout: {e}")
            last_err = e
        except Exception as e:
            logger.error(f"ollama recognize attempt {attempt + 1} failed: {e}")
            last_err = e
            break
    raise last_err if last_err else RuntimeError("ollama recognize failed")


def recognize_medicine_bag(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    Claude 線上 / Ollama 本機 自動切換。
    回傳: { "medications": [...], "raw_text": "...", "error": "..." (optional) }
    """
    if not image_base64:
        return {"medications": [], "raw_text": "", "error": "empty_image"}
    if image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[-1]

    raw_text = ""
    err: Exception | None = None
    backend_used = ""

    if USE_CLAUDE:
        try:
            raw_text = _recognize_via_claude(image_base64, media_type)
            backend_used = "claude"
        except Exception as e:
            logger.error(f"Claude vision failed: {e}")
            err = e
    else:
        try:
            raw_text = _recognize_via_ollama(image_base64)
            backend_used = "ollama"
        except Exception as e:
            err = e

    if not raw_text:
        return {
            "medications": [],
            "raw_text": "",
            "error": f"{type(err).__name__}: {err}" if err else "no_response",
        }

    parsed = _extract_json(raw_text)
    if not parsed:
        logger.warning(f"recognize non-JSON output ({backend_used}): {raw_text[:300]}")
        return {"medications": [], "raw_text": raw_text, "error": "json_parse_failed"}

    meds = parsed.get("medications") or []
    if not isinstance(meds, list):
        meds = []

    cleaned = []
    for m in meds:
        if not isinstance(m, dict):
            continue
        name = m.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        cleaned.append(m)

    return {"medications": cleaned, "raw_text": raw_text, "backend": backend_used}
