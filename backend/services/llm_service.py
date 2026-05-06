import base64
import json
import logging
import os
import time
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

# Google Cloud Vision OCR — 中文小字辨識準度遠高於 LLM vision，月 1000 次免費
# 申請流程：GCP Console → APIs & Services → 啟用 Cloud Vision API → 建立 API Key
# 沒設定就略過，自動 fallback 到原本的 LLM vision chain
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY", "")
GOOGLE_VISION_URL = "https://vision.googleapis.com/v1/images:annotate"

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

    # 遇到 429 (rate limit) 自動 retry：指數退避 1.5s → 3s → 6s
    # Groq free tier 偶爾突發限流，等一下就會通；retry 後再失敗才丟給 fallback chain
    delays = [1.5, 3.0]  # 兩次 retry 機會
    for attempt in range(len(delays) + 1):
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
        if resp.status_code == 429 and attempt < len(delays):
            wait = delays[attempt]
            # 優先用 server 給的 retry-after，沒有就 fallback 到 exponential backoff
            ra = resp.headers.get("retry-after")
            if ra:
                try:
                    wait = max(float(ra), wait)
                except ValueError:
                    pass
            logger.warning(f"Groq 429 rate-limited，等 {wait}s 後第 {attempt + 1} 次 retry")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    # 理論上走不到（最後一輪 raise_for_status 會 raise）
    raise RuntimeError("Groq retry 全部用完仍 rate-limited")


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
    "  - name        藥名（**完全照抄影像上看得到的字**；中英並列時可寫成「中文（English）」格式，"
    "                  例：布洛芬（Ibuprofen）；只有英文時直接寫英文，不要硬翻中文；"
    "                  **絕對不要從訓練記憶裡補上類似的藥名**）\n"
    "  - dosage      單次劑量（例：500mg、1 顆、5ml）\n"
    "  - frequency   服用頻率（原文照抄；例：一天三次、每 8 小時一次、需要時服用、早晚、QD、BID、TID、QID、Q8H、PRN）\n"
    "  - usage       用法/服用時機（例：飯前、飯後、睡前、空腹、口服、外用）\n"
    "  - duration    療程天數（例：7 天、長期服用；若無資訊留 null）\n"
    "  - category    藥物類別（降血壓藥、降血糖藥、降血脂藥、止痛藥、抗生素、"
    "                  胃藥、抗凝血藥、利尿劑、氣管擴張劑、抗憂鬱藥、其他）\n"
    "  - purpose     用途（例：控制血糖、緩解頭痛；單據沒寫就 null，不要瞎猜）\n"
    "  - instructions 注意事項（**僅限影像上可清楚讀到的警語**；讀不清楚就 null，"
    "                  絕對不要把模糊或亂碼字塞進這個欄位）\n"
    "  - hospital    醫院/診所/藥局名稱（從抬頭、印章、條碼區判讀；若無留 null）\n"
    "  - prescribed_date 開立日期（YYYY-MM-DD；若只有民國年請換算成西元年；若無留 null）\n\n"
    "回覆必須是純 JSON（不要 markdown code block，不要任何前後說明文字），結構：\n"
    '{"medications": [{"name": "...", "dosage": "...", "frequency": "...", '
    '"usage": "...", "duration": "...", "category": "...", "purpose": "...", '
    '"instructions": "...", "hospital": "...", "prescribed_date": "..."}]}\n\n'
    "規則（醫療場景：錯誤藥名比空欄位嚴重得多，請嚴格遵守）：\n"
    "- 每個欄位都必須存在（即使值為 null）\n"
    "- **看不清楚的欄位 → 一律填 null，不要猜、不要從訓練資料補字**\n"
    "- 一張藥單常包含多種藥（每行一筆），**請逐筆分開列出，不要漏掉任何一行**\n"
    "- 即使只能辨識出藥名一個欄位，也請列出來（其他欄位用 null）\n"
    "- frequency 請保留原文（例如「一天三次」「每 8 小時」「早晚」「BID」），系統會自動歸類時段\n"
    "- **照片若是側躺、倒立、模糊**：請先想像旋轉到正向再讀；若旋轉後仍讀不出藥名，"
    "  請回傳空 medications 陣列，**不要硬湊一個藥名**（例如不要把模糊字補成 Prednisolone、Aspirin 等常見藥）\n"
    "- **抗幻覺自檢**：你給出的 name 必須是影像上實際出現的字串。"
    "  輸出前請反問自己「這個藥名我是真的看到，還是聯想出來的？」如果是後者，請改回空陣列\n"
    "- 只有當影像上至少能讀到一個合理藥名才回傳；風景、人臉、空白紙張、或文字完全無法閱讀的情況都回空陣列"
)

_MED_BAG_USER_PROMPT = (
    "請辨識這張照片（可能是藥袋、藥單、處方箋或領藥明細）上的所有藥物資訊，"
    "**逐筆**分開列出。即使只看得到藥名也請列出，不要回傳空陣列。"
)


def _vision_ollama(image_base64: str, media_type: str) -> str:
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": VISION_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": _MED_BAG_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _MED_BAG_USER_PROMPT,
                    "images": [image_base64],
                },
            ],
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _vision_anthropic(image_base64: str, media_type: str) -> str:
    if _anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY 未設定或 anthropic SDK 未安裝")
    msg = _anthropic_client.messages.create(
        model=ANTHROPIC_VISION_MODEL,
        max_tokens=ANTHROPIC_VISION_MAX_TOKENS,
        # OCR 需要穩定輸出（同一張藥單每次都要解到一樣的欄位），降低 temperature
        temperature=0.2,
        system=_MED_BAG_SYSTEM_PROMPT,
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
                    {"type": "text", "text": _MED_BAG_USER_PROMPT},
                ],
            }
        ],
    )
    return (msg.content[0].text or "").strip()


def _vision_groq(image_base64: str, media_type: str) -> str:
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
                        {"type": "text", "text": _MED_BAG_SYSTEM_PROMPT + "\n\n" + _MED_BAG_USER_PROMPT},
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


# 從 OCR 純文字抽結構化欄位的 prompt（給 text LLM 用，預設走 Haiku 4.5 省成本）
_EXTRACT_FROM_OCR_PROMPT = (
    "你是台灣處方資訊抽取助手。輸入是 OCR 從藥袋／藥單／處方箋讀出的原始文字"
    "（可能有錯字、缺字、版面亂、夾雜雜訊）。請從這段文字抽取所有藥物，整理成 JSON：\n\n"
    "標準欄位：\n"
    "  - name        藥名（保留原文；中英並列時用「中文（English）」格式；只有英文就直接寫英文）\n"
    "  - dosage      單次劑量（例：500mg、1 顆、5ml）\n"
    "  - frequency   服用頻率（原文照抄；例：一天三次、每 8 小時、需要時、QD、BID、TID、Q8H、PRN）\n"
    "  - usage       用法/服用時機（飯前、飯後、睡前、空腹、口服、外用）\n"
    "  - duration    療程天數（7 天、長期；無資訊 null）\n"
    "  - category    藥物類別（降血壓藥、降血糖藥、止痛藥、抗生素、胃藥…其他）\n"
    "  - purpose     用途（無寫就 null，不要瞎猜）\n"
    "  - instructions 注意事項\n"
    "  - hospital    醫院/診所/藥局名稱（從抬頭判讀；無就 null）\n"
    "  - prescribed_date 開立日期（YYYY-MM-DD；民國年要換算成西元年；無就 null）\n\n"
    "回覆**必須是純 JSON**，不要 markdown code block、不要前後說明文字：\n"
    '{"medications": [{"name": "...", "dosage": "...", "frequency": "...", '
    '"usage": "...", "duration": "...", "category": "...", "purpose": "...", '
    '"instructions": "...", "hospital": "...", "prescribed_date": "..."}]}\n\n'
    "規則：\n"
    "- 每個欄位都必須存在（無資料用 null）\n"
    "- 一張藥單常有多筆藥，**逐筆分開列出，不要漏掉任何一行**\n"
    "- 即使只能抽出藥名一個欄位也要列出（其他欄位 null）；**寧可不完整，不要回空陣列**\n"
    "- 整段 OCR 完全沒有看起來像藥名的字眼才回空陣列"
)


def extract_medications_from_ocr_text(ocr_text: str) -> dict:
    """從外部來源（前端 Tesseract.js / Google Vision …）拿到的 OCR 純文字
    抽結構化 medications JSON。回傳格式同 recognize_medicine_bag，
    這樣 router 可以共用後續處理邏輯。"""
    errors: list[dict] = []
    try:
        raw = call_claude(_EXTRACT_FROM_OCR_PROMPT, ocr_text)
    except Exception as e:
        logger.error(f"extract_medications_from_ocr_text 失敗：{e}")
        errors.append({"provider": "extract", "error": f"{type(e).__name__}: {e}"})
        return {
            "medications": [],
            "raw_text": ocr_text,
            "provider": None,
            "errors": errors,
        }
    parsed = _parse_med_bag_json(raw)
    parsed["raw_text"] = ocr_text  # 回 OCR 純文字（不是 JSON）給前端 debug
    parsed["provider"] = "client_ocr"
    if not parsed.get("medications"):
        errors.append({"provider": "extract", "error": "no medications extracted"})
    parsed["errors"] = errors
    return parsed


def _google_vision_ocr(image_base64: str) -> str:
    """Google Cloud Vision DOCUMENT_TEXT_DETECTION — 對中文小字 / 表格的 OCR 準度
    遠高於任何 LLM vision model。需設定 GOOGLE_VISION_API_KEY。
    回傳 OCR 純文字（按版面排序）。"""
    if not GOOGLE_VISION_API_KEY:
        raise RuntimeError("GOOGLE_VISION_API_KEY 未設定")
    resp = httpx.post(
        f"{GOOGLE_VISION_URL}?key={GOOGLE_VISION_API_KEY}",
        json={
            "requests": [
                {
                    "image": {"content": image_base64},
                    # DOCUMENT_TEXT_DETECTION 對藥單這種密集表格文件比 TEXT_DETECTION 準
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                    # 提示語言：繁中 + 英文（藥名常英文）
                    "imageContext": {"languageHints": ["zh-Hant", "en"]},
                }
            ]
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    responses = data.get("responses") or []
    if not responses:
        return ""
    # 個別 request 的錯誤會包在 response 裡（HTTP 200 但邏輯錯誤）
    err = responses[0].get("error")
    if err:
        raise RuntimeError(f"Google Vision API error: {err.get('message') or err}")
    annotation = responses[0].get("fullTextAnnotation") or {}
    return (annotation.get("text") or "").strip()


def recognize_medicine_bag(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    辨識藥袋／藥單／處方箋照片，提取藥物資訊。

    優先順序：
      1. **Google Cloud Vision OCR + LLM 抽欄位**（中文小字準度最高，需 GOOGLE_VISION_API_KEY）
      2. Fallback：原本的 LLM vision 一段式（anthropic / groq / ollama）

    本地開發用 Ollama；雲端部署優先 Google Vision（OCR 準），
    Anthropic / Groq 作為 LLM vision 備援。

    回傳: {
        "medications": [{"name": ..., "dosage": ..., "frequency": ..., ...}],
        "raw_text": "<OCR / vision 的原始輸出>",
        "provider": "<實際成功的 provider>",  # google_vision / anthropic / groq / ollama / None
        "errors":   [{"provider": "...", "error": "..."}],
    }
    """
    errors: list[dict] = []

    # Stage 1: Google Vision OCR → text LLM 抽欄位（最準的路徑）
    if GOOGLE_VISION_API_KEY:
        try:
            ocr_text = _google_vision_ocr(image_base64)
        except Exception as e:
            errors.append({"provider": "google_vision", "error": f"{type(e).__name__}: {e}"})
            logger.warning(f"Google Vision OCR 失敗：{e}")
            ocr_text = ""

        if ocr_text and len(ocr_text.strip()) >= 20:
            try:
                extract_raw = call_claude(_EXTRACT_FROM_OCR_PROMPT, ocr_text)
                parsed = _parse_med_bag_json(extract_raw)
                # 回傳 OCR 純文字當 raw_text（給前端 debug 看得懂）
                parsed["raw_text"] = ocr_text
                if parsed.get("medications"):
                    parsed["provider"] = "google_vision"
                    parsed["errors"] = errors
                    return parsed
                errors.append({"provider": "google_vision+extract", "error": "no medications extracted from ocr"})
            except Exception as e:
                errors.append({"provider": "google_vision+extract", "error": f"{type(e).__name__}: {e}"})
                logger.warning(f"從 OCR 抽欄位失敗：{e}")
        elif ocr_text is not None:
            errors.append({"provider": "google_vision", "error": f"ocr too short ({len(ocr_text or '')} chars)"})

    # Stage 2 (fallback): 原本的 LLM vision 一段式 chain
    chain = _vision_fallback_chain(LLM_PROVIDER if LLM_PROVIDER in _VISION_PROVIDERS else "ollama")
    last_raw = ""

    for name in chain:
        fn = _VISION_PROVIDERS.get(name)
        if fn is None:
            continue
        try:
            raw = fn(image_base64, media_type)
        except Exception as e:
            errors.append({"provider": name, "error": f"{type(e).__name__}: {e}"})
            logger.warning(f"Vision provider {name} 失敗：{e}")
            continue

        last_raw = raw
        parsed = _parse_med_bag_json(raw)
        if parsed.get("medications"):
            parsed["provider"] = name
            parsed["errors"] = errors
            return parsed
        # 成功收到回應但沒辨識出藥物 → 試下一個 provider，可能其他模型 OCR 較強
        errors.append({"provider": name, "error": "no medications recognized"})

    return {
        "medications": [],
        "raw_text": last_raw,
        "provider": None,
        "errors": errors,
    }
