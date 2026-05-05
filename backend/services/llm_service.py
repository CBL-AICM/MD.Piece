import base64
import json
import logging
import os
import httpx

logger = logging.getLogger(__name__)

# 多 provider LLM 服務
# - 本地開發：LLM_PROVIDER=ollama（預設）→ 零成本、資料不出本機
# - 雲端部署：LLM_PROVIDER=groq → 免費額度大、速度快，無需自架 GPU
# - 雲端 fallback：LLM_PROVIDER=anthropic → 用 Claude API（需要 ANTHROPIC_API_KEY）
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告、藥袋辨識、檢驗值解讀
#
# auto-fallback：若主 provider（預設 ollama）連不上 / 失敗，會自動降級到
#   1) anthropic（若有 ANTHROPIC_API_KEY）
#   2) groq（若有 GROQ_API_KEY）
# 這樣 Vercel serverless（沒辦法跑 Ollama）也能正常運作。

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Groq 目前的 multi-modal 模型；藥袋辨識用視覺模型
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
# 藥單 / 藥袋的中文小字 OCR：Haiku 4.5 力氣不夠（會回空陣列），預設改用 Sonnet 4.6
# 文字任務（白話解讀、小禾對話、報告生成）仍用 Haiku 省成本
ANTHROPIC_VISION_MODEL = os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1024"))
# 藥袋辨識需要更長的 token 額度（一張藥袋常有 3~6 包藥）
ANTHROPIC_VISION_MAX_TOKENS = int(os.getenv("ANTHROPIC_VISION_MAX_TOKENS", "2048"))

try:
    import anthropic as _anthropic_sdk
    _anthropic_client = _anthropic_sdk.Anthropic() if ANTHROPIC_API_KEY else None
except Exception as e:  # ImportError 或 client 初始化失敗
    logger.warning(f"Anthropic SDK 未啟用：{e}")
    _anthropic_sdk = None
    _anthropic_client = None


# ==============================================================================
# Non-streaming providers
# ==============================================================================

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


def _call_anthropic(system_prompt: str, user_message: str, history=None) -> str:
    if _anthropic_client is None:
        raise RuntimeError(
            "ANTHROPIC_API_KEY 未設定或 anthropic SDK 未安裝；無法使用 Anthropic provider"
        )
    msgs = list(history) if history else []
    msgs.append({"role": "user", "content": user_message})
    msg = _anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        system=system_prompt,
        messages=msgs,
    )
    return msg.content[0].text


_PROVIDERS = {
    "ollama": _call_ollama,
    "groq": _call_groq,
    "anthropic": _call_anthropic,
}


def _fallback_chain(primary: str):
    """主 provider 之後可用的備援順序（依 API key 是否存在過濾）。"""
    chain = [primary]
    if _anthropic_client is not None and "anthropic" not in chain:
        chain.append("anthropic")
    if GROQ_API_KEY and "groq" not in chain:
        chain.append("groq")
    if "ollama" not in chain:
        chain.append("ollama")
    return chain


def call_claude(system_prompt: str, user_message: str, history=None) -> str:
    """文字生成（相容原 claude_service 簽名）— 依 LLM_PROVIDER 自動切換 provider，
    主 provider 失敗時自動降級到下一個可用的（anthropic → groq → ollama）。

    history: 可選，[{role: 'user'|'assistant', content: str}, ...] 多輪歷史
    """
    chain = _fallback_chain(LLM_PROVIDER if LLM_PROVIDER in _PROVIDERS else "ollama")
    last_err = None
    for name in chain:
        fn = _PROVIDERS.get(name)
        if fn is None:
            continue
        try:
            return fn(system_prompt, user_message, history)
        except Exception as e:
            last_err = e
            logger.warning(f"LLM provider {name} 失敗，嘗試下一個：{e}")
            continue
    raise RuntimeError(f"所有 LLM provider 都失敗，最後錯誤：{last_err}")


# ==============================================================================
# Streaming providers
# ==============================================================================

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


def _stream_anthropic(system_prompt: str, user_message: str, history=None):
    if _anthropic_client is None:
        raise RuntimeError(
            "ANTHROPIC_API_KEY 未設定或 anthropic SDK 未安裝；無法使用 Anthropic provider"
        )
    msgs = list(history) if history else []
    msgs.append({"role": "user", "content": user_message})
    with _anthropic_client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        system=system_prompt,
        messages=msgs,
    ) as stream:
        for text in stream.text_stream:
            if text:
                yield text


_STREAM_PROVIDERS = {
    "ollama": _stream_ollama,
    "groq": _stream_groq,
    "anthropic": _stream_anthropic,
}


def stream_claude(system_prompt: str, user_message: str, history=None):
    """串流文字生成（產生純文字片段的 generator）；主 provider 失敗時自動降級。"""
    chain = _fallback_chain(LLM_PROVIDER if LLM_PROVIDER in _STREAM_PROVIDERS else "ollama")
    last_err = None
    for name in chain:
        fn = _STREAM_PROVIDERS.get(name)
        if fn is None:
            continue
        try:
            # 用 list-iter 包裝以便偵測第一個 yield 之前的錯誤
            gen = fn(system_prompt, user_message, history)
            yield from gen
            return
        except Exception as e:
            last_err = e
            logger.warning(f"LLM stream provider {name} 失敗，嘗試下一個：{e}")
            continue
    raise RuntimeError(f"所有 LLM stream provider 都失敗，最後錯誤：{last_err}")


_MED_BAG_SYSTEM_PROMPT = (
    "你是台灣處方資訊辨識助手。輸入照片可能是下列任一種：\n"
    "  (a) 藥袋（單包藥的外袋）\n"
    "  (b) 藥單 / 處方箋 / 領藥明細（A4 或長條表格，常見於台大、榮總、長庚、亞東、"
    "      馬偕、各地區醫院、診所、社區藥局；典型欄位：藥品名稱 / 劑量 / 用法 / 數量 / 天數）\n"
    "  (c) 出院帶藥清單、慢箋、回診指示單\n\n"
    "**不管版型為何**、**不管是藥袋還是藥單**，請從照片裡所有可見文字萃取出以下「標準欄位」：\n\n"
    "標準欄位：\n"
    "  - name        藥名（盡量保留原文藥名；中英並列時可寫成「中文（English）」格式，"
    "                  例：布洛芬（Ibuprofen）；只有英文時直接寫英文，不要硬翻中文）\n"
    "  - dosage      單次劑量（例：500mg、1 顆、5ml）\n"
    "  - frequency   服用頻率（原文照抄；例：一天三次、每 8 小時一次、需要時服用、早晚、QD、BID、TID、QID、Q8H、PRN）\n"
    "  - usage       用法/服用時機（例：飯前、飯後、睡前、空腹、口服、外用）\n"
    "  - duration    療程天數（例：7 天、長期服用；若無資訊留 null）\n"
    "  - category    藥物類別（降血壓藥、降血糖藥、降血脂藥、止痛藥、抗生素、"
    "                  胃藥、抗凝血藥、利尿劑、氣管擴張劑、抗憂鬱藥、其他）\n"
    "  - purpose     用途（例：控制血糖、緩解頭痛；單據沒寫就 null，不要瞎猜）\n"
    "  - instructions 注意事項（例：避免空腹、服藥期間不要喝酒）\n"
    "  - hospital    醫院/診所/藥局名稱（從抬頭、印章、條碼區判讀；若無留 null）\n"
    "  - prescribed_date 開立日期（YYYY-MM-DD；若只有民國年請換算成西元年；若無留 null）\n\n"
    "回覆必須是純 JSON（不要 markdown code block，不要任何前後說明文字），結構：\n"
    '{"medications": [{"name": "...", "dosage": "...", "frequency": "...", '
    '"usage": "...", "duration": "...", "category": "...", "purpose": "...", '
    '"instructions": "...", "hospital": "...", "prescribed_date": "..."}]}\n\n'
    "規則：\n"
    "- 每個欄位都必須存在（即使值為 null）\n"
    "- 看不清楚或單據沒寫的欄位 → 填 null，不要瞎猜\n"
    "- 一張藥單常包含多種藥（每行一筆），**請逐筆分開列出，不要漏掉任何一行**\n"
    "- 即使只能辨識出藥名一個欄位，也請列出來（其他欄位用 null）；**寧可不完整，也不要回傳空陣列**\n"
    "- frequency 請保留原文（例如「一天三次」「每 8 小時」「早晚」「BID」），系統會自動歸類時段\n"
    "- 寧可缺欄位，不要填入錯誤資訊\n"
    "- 即便照片不完整、模糊、有反光、傾斜、被手指遮住一部分，也請盡量從可見字元辨識，"
    "  **絕對不要因為照片不完美就回傳空陣列**；至少把任何看得到的藥名先列出來\n"
    "- 只有「整張完全沒有任何藥品資訊」（例如拍到風景、人臉、空白紙張）才回傳空 medications 陣列"
)

_MED_BAG_USER_PROMPT = (
    "請辨識這張照片（可能是藥袋、藥單、處方箋或領藥明細）上的所有藥物資訊，"
    "**逐筆**分開列出。即使只看得到藥名也請列出，不要回傳空陣列。"
)

# ── 兩段式辨識用的 prompt ───────────────────────────────────────
# 一段式（影像 → 結構化 JSON）對小字 OCR 力氣不夠：模型要同時做 OCR + 欄位歸納，
# 常常顧著 JSON 結構就漏掉內文。改成兩段式：
#   Stage 1: vision LLM 純粹做 OCR，把所有可見文字逐字讀出來
#   Stage 2: text LLM（可用便宜的 Haiku）從 OCR 文字抽結構化 JSON
# 這樣 stage 1 不用分心想 JSON、stage 2 不用視覺，分工清楚精度高很多

_OCR_SYSTEM_PROMPT = (
    "你是 OCR 助手。請把照片裡所有可見的文字（中文、英文、數字、符號）逐字讀出來。\n\n"
    "規則：\n"
    "- 不要解讀、不要翻譯、不要分類，**純粹照抄**文字\n"
    "- 看不清楚的字用 ? 代替（不要瞎猜）\n"
    "- 保留原本的版面結構：段落、條列、表格欄位之間用空格 / 換行區隔\n"
    "- 表格的每一列當作一行，欄位之間用 | 分隔\n"
    "- 即使整張照片很糊、有反光、傾斜，也請盡量讀出能看到的字\n"
    "- 有藥品名稱、劑量、用法時請務必讀出（這是最重要的資訊）"
)

_OCR_USER_PROMPT = (
    "請把這張照片裡所有看得到的文字逐字讀出來，保留版面結構。"
    "特別注意藥品名稱、劑量（mg / 顆 / ml）、頻率（一天 X 次 / Q8H / BID）、用法（飯前 / 飯後）。"
)

_EXTRACT_SYSTEM_PROMPT = (
    "你是台灣處方資訊抽取助手。輸入是 OCR 從藥袋 / 藥單 / 處方箋讀出的原始文字（可能有錯字、缺字、版面亂）。\n"
    "請從這段文字中**抽取出所有藥物**，依下列「標準欄位」整理成 JSON：\n\n"
    "標準欄位：\n"
    "  - name        藥名（保留原文；中英並列時用「中文（English）」格式）\n"
    "  - dosage      單次劑量（例：500mg、1 顆、5ml）\n"
    "  - frequency   服用頻率（原文照抄；例：一天三次、每 8 小時、需要時、QD、BID、TID、Q8H、PRN）\n"
    "  - usage       用法/服用時機（飯前、飯後、睡前、空腹、口服、外用）\n"
    "  - duration    療程天數（7 天、長期；無資訊 null）\n"
    "  - category    藥物類別（降血壓藥、降血糖藥、止痛藥、抗生素、胃藥…其他）\n"
    "  - purpose     用途（控制血糖、緩解頭痛；無寫就 null）\n"
    "  - instructions 注意事項（避免空腹、不要喝酒…）\n"
    "  - hospital    醫院/診所/藥局名稱（從抬頭判讀；無就 null）\n"
    "  - prescribed_date 開立日期（YYYY-MM-DD；民國年要換算成西元年；無就 null）\n\n"
    "回覆**必須是純 JSON**（不要 markdown code block、不要前後說明文字）：\n"
    '{"medications": [{"name": "...", "dosage": "...", "frequency": "...", '
    '"usage": "...", "duration": "...", "category": "...", "purpose": "...", '
    '"instructions": "...", "hospital": "...", "prescribed_date": "..."}]}\n\n'
    "規則：\n"
    "- 每個欄位都必須存在（即使值為 null）\n"
    "- 一張藥單常有多筆藥（每行一筆），**逐筆分開列出，不要漏掉任何一行**\n"
    "- 即使只能抽出藥名一個欄位，也要列出來（其他欄位用 null）\n"
    "- **絕對不要回傳空陣列**，除非 OCR 文字完全沒有任何看起來像藥品的字眼\n"
    "- 看不清楚或文字有 ? 的欄位 → 填 null，不要瞎猜"
)


def _vision_ollama(
    image_base64: str,
    media_type: str,
    system_prompt: str = _MED_BAG_SYSTEM_PROMPT,
    user_prompt: str = _MED_BAG_USER_PROMPT,
) -> str:
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": VISION_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [image_base64],
                },
            ],
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _vision_anthropic(
    image_base64: str,
    media_type: str,
    system_prompt: str = _MED_BAG_SYSTEM_PROMPT,
    user_prompt: str = _MED_BAG_USER_PROMPT,
) -> str:
    if _anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY 未設定或 anthropic SDK 未安裝")
    msg = _anthropic_client.messages.create(
        model=ANTHROPIC_VISION_MODEL,
        max_tokens=ANTHROPIC_VISION_MAX_TOKENS,
        # OCR 需要穩定輸出（同一張藥單每次都要解到一樣的欄位），降低 temperature
        temperature=0.2,
        system=system_prompt,
        messages=[
            {
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
                    {"type": "text", "text": user_prompt},
                ],
            }
        ],
    )
    return (msg.content[0].text or "").strip()


def _vision_groq(
    image_base64: str,
    media_type: str,
    system_prompt: str = _MED_BAG_SYSTEM_PROMPT,
    user_prompt: str = _MED_BAG_USER_PROMPT,
) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY 未設定")
    data_url = f"data:{media_type or 'image/jpeg'};base64,{image_base64}"
    # Groq vision 模型不支援 system role；把指令塞到 user message
    resp = httpx.post(
        f"{GROQ_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt + "\n\n" + user_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return (resp.json()["choices"][0]["message"]["content"] or "").strip()


_VISION_PROVIDERS = {
    "ollama": _vision_ollama,
    "anthropic": _vision_anthropic,
    "groq": _vision_groq,
}


def _vision_fallback_chain(primary: str) -> list[str]:
    """藥袋辨識的 provider 排序：

    主 provider 優先，雲端 provider（anthropic/groq）一定會被加入備援，
    Ollama 放最後（雲端部署常常沒裝 Ollama，最後嘗試也合理）。
    """
    chain = []
    if primary in _VISION_PROVIDERS:
        chain.append(primary)
    if _anthropic_client is not None and "anthropic" not in chain:
        chain.append("anthropic")
    if GROQ_API_KEY and "groq" not in chain:
        chain.append("groq")
    if "ollama" not in chain:
        chain.append("ollama")
    return chain


def _parse_med_bag_json(raw: str) -> dict:
    """容錯地把模型輸出的字串轉成 JSON。

    處理：去掉 markdown code fence、抽出第一個 `{...}` 區塊、修剪後再 json.loads。
    若仍解析失敗，回傳空 medications 陣列但保留 raw_text 給前端 debug。
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        # ``` json\n{...}\n``` → 抽掉首尾的 fence
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    # 有時模型會在 JSON 前後寫敘述文字，抓第一個 { 到最後一個 }
    if not text.startswith("{"):
        l = text.find("{")
        r = text.rfind("}")
        if l != -1 and r != -1 and r > l:
            text = text[l : r + 1]

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Medicine bag recognition returned non-JSON: {raw[:200]}")
        return {"medications": [], "raw_text": raw}

    if not isinstance(result, dict):
        return {"medications": [], "raw_text": raw}
    meds = result.get("medications")
    if not isinstance(meds, list):
        meds = []
    result["medications"] = meds
    result["raw_text"] = raw
    return result


def _run_ocr_stage(image_base64: str, media_type: str) -> tuple[str, str | None, list[dict]]:
    """Stage 1：純 OCR — 用 vision LLM 把照片所有文字逐字讀出來。

    回傳 (ocr_text, provider_name, errors)。ocr_text 為空字串代表所有 provider 都失敗。
    """
    chain = _vision_fallback_chain(LLM_PROVIDER if LLM_PROVIDER in _VISION_PROVIDERS else "ollama")
    errors: list[dict] = []

    for name in chain:
        fn = _VISION_PROVIDERS.get(name)
        if fn is None:
            continue
        try:
            ocr_text = fn(image_base64, media_type, _OCR_SYSTEM_PROMPT, _OCR_USER_PROMPT)
        except Exception as e:
            errors.append({"provider": name, "error": f"{type(e).__name__}: {e}"})
            logger.warning(f"OCR provider {name} 失敗：{e}")
            continue

        # OCR 結果太短當作沒抓到（例如模型回 "我看不清楚"）
        if ocr_text and len(ocr_text.strip()) >= 20:
            return ocr_text, name, errors
        errors.append({"provider": name, "error": f"ocr_text too short ({len(ocr_text or '')} chars)"})

    return "", None, errors


def _extract_medications_from_text(ocr_text: str) -> dict:
    """Stage 2：把 OCR 文字餵給 text LLM，抽出結構化 medications JSON。

    用 call_claude（會走 LLM_PROVIDER fallback chain，預設 Haiku 4.5 — 純文字任務便宜又快）。
    """
    raw = call_claude(_EXTRACT_SYSTEM_PROMPT, ocr_text)
    return _parse_med_bag_json(raw)


def recognize_medicine_bag(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    辨識藥袋 / 藥單 / 處方箋照片，提取藥物資訊。

    兩段式 pipeline：
      Stage 1 — Vision LLM 純做 OCR（把所有可見文字逐字讀出）
      Stage 2 — Text LLM 從 OCR 文字抽結構化 JSON

    這樣 stage 1 不用分心想 JSON、stage 2 不用視覺，分工清楚精度比一段式高很多。
    Vision provider 依 LLM_PROVIDER 為主，雲端 provider 自動接力（適合 Vercel
    serverless 沒法跑 Ollama 的場景）。

    回傳: {
        "medications": [{"name": ..., "dosage": ..., "frequency": ..., ...}],
        "raw_text": "<stage 1 的 OCR 文字>",
        "provider": "<實際成功的 OCR provider>",  # 失敗時 None
        "errors":   [{"provider": "...", "error": "..."}],
    }
    """
    # Stage 1：OCR
    ocr_text, ocr_provider, ocr_errors = _run_ocr_stage(image_base64, media_type)

    if not ocr_text:
        return {
            "medications": [],
            "raw_text": "",
            "provider": None,
            "errors": ocr_errors,
        }

    # Stage 2：從 OCR 文字抽 JSON
    try:
        extracted = _extract_medications_from_text(ocr_text)
    except Exception as e:
        logger.error(f"Stage 2 extraction 失敗：{e}")
        return {
            "medications": [],
            "raw_text": ocr_text,
            "provider": ocr_provider,
            "errors": ocr_errors + [{"provider": "extract", "error": f"{type(e).__name__}: {e}"}],
        }

    meds = extracted.get("medications") or []
    errors = list(ocr_errors)
    if not meds:
        errors.append({"provider": "extract", "error": "no medications extracted from ocr text"})

    return {
        "medications": meds,
        "raw_text": ocr_text,  # 回 OCR 文字（不是 JSON 字串）給前端 debug
        "provider": ocr_provider,
        "errors": errors,
    }
