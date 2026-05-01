import json
import logging
import os
import re
import httpx

logger = logging.getLogger(__name__)

# 本地 LLM 服務（Ollama）
# 零成本、零隱私風險，所有資料不出本機
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告、藥袋辨識

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")

# 視覺模型在 CPU 上常需要 3-5 分鐘冷啟 + 推論
VISION_TIMEOUT_S = float(os.getenv("OLLAMA_VISION_TIMEOUT", "300"))
TEXT_TIMEOUT_S = float(os.getenv("OLLAMA_TEXT_TIMEOUT", "180"))


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
        timeout=TEXT_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str) -> dict | None:
    """
    從 LLM 輸出抽出第一個合法 JSON 物件。容忍：
    - markdown code fence（含 ```json）
    - JSON 前後夾雜的說明文字
    - JSON 截斷（嘗試找平衡的第一個 { ... }）
    """
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
    # 平衡括號掃描
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


def recognize_medicine_bag(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    用本地 Vision 模型辨識藥袋照片，提取藥物資訊。
    回傳: { "medications": [...], "raw_text": "...", "error": "..." (optional) }
    """
    if not image_base64:
        return {"medications": [], "raw_text": "", "error": "empty_image"}

    # 防呆：誤把整個 data URI 傳進來，剝掉 prefix
    if image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[-1]

    system = (
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

    payload = {
        "model": VISION_MODEL,
        "stream": False,
        "format": "json",  # Ollama JSON mode（支援的模型會強制輸出合法 JSON）
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "請仔細閱讀這張藥袋的所有文字（中英文都看），把每一包藥都寫成 JSON。",
                "images": [image_base64],
            },
        ],
    }

    last_err: Exception | None = None
    raw_text = ""
    for attempt in range(2):  # timeout 重試一次（容忍冷啟動）
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE}/api/chat",
                json=payload,
                timeout=VISION_TIMEOUT_S,
            )
            resp.raise_for_status()
            raw_text = (resp.json().get("message") or {}).get("content", "").strip()
            break
        except (httpx.TimeoutException, httpx.ReadTimeout) as e:
            logger.warning(f"recognize_medicine_bag attempt {attempt + 1} timeout: {e}")
            last_err = e
        except Exception as e:
            logger.error(f"recognize_medicine_bag attempt {attempt + 1} failed: {e}")
            last_err = e
            break

    if not raw_text:
        return {
            "medications": [],
            "raw_text": "",
            "error": f"{type(last_err).__name__}: {last_err}" if last_err else "no_response",
        }

    parsed = _extract_json(raw_text)
    if not parsed:
        logger.warning(f"recognize_medicine_bag non-JSON output: {raw_text[:300]}")
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

    return {"medications": cleaned, "raw_text": raw_text}
