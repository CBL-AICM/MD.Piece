import anthropic
import base64
import json
import logging
import re

logger = logging.getLogger(__name__)

# Claude API 呼叫服務
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告、藥袋辨識

client = anthropic.Anthropic()  # 讀取 ANTHROPIC_API_KEY

VISION_MODEL = "claude-haiku-4-5-20251001"


def call_claude(system_prompt: str, user_message: str) -> str:
    message = client.messages.create(
        model=VISION_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    return message.content[0].text


def _image_content_block(image_base64: str, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type or "image/jpeg",
            "data": image_base64,
        },
    }


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        # 去掉首行 ```xxx 和結尾 ```
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return raw


def _coerce_meds_payload(parsed) -> list:
    """把模型回傳的各種結構都收斂成 list[dict]。"""
    if isinstance(parsed, dict):
        meds = parsed.get("medications")
        if isinstance(meds, list):
            return meds
        # 單筆 dict 也接受
        if "name" in parsed:
            return [parsed]
        return []
    if isinstance(parsed, list):
        return parsed
    return []


def _normalize_med(med: dict) -> dict:
    """補齊欄位，避免前端拿到 undefined。"""
    keys = ("name", "dosage", "frequency", "usage", "duration",
            "category", "purpose", "instructions", "hospital", "prescribed_date")
    return {k: (med.get(k) if isinstance(med, dict) else None) for k in keys}


def _extract_drug_names_fallback(image_base64: str, media_type: str) -> list:
    """
    第二階段：放棄結構化抽取，只請模型把所有看到的藥名列出來，純文字一行一個。
    比起一次硬抽 10 個欄位，這個成功率高很多 — 即使藥袋拍得歪/糊也常能認出藥名。
    """
    system = (
        "你是藥袋藥名擷取助手。請只列出你在圖片上看到的所有藥物名稱，"
        "中文藥名與英文學名都要列（同一個藥若兩種都有，用「中文名（English）」格式合併）。\n"
        "規則：\n"
        "- 一行一個藥名，不要編號、不要 bullet、不要解釋、不要 JSON、不要 markdown\n"
        "- 不要列劑量、頻率、醫院名、病人姓名\n"
        "- 看不清楚的字用 ? 代替（例：Amox?cillin），不要省略整行\n"
        "- 如果完全看不到任何藥名，只回覆一個字：NONE"
    )
    message = client.messages.create(
        model=VISION_MODEL,
        max_tokens=512,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                _image_content_block(image_base64, media_type),
                {"type": "text", "text": "請列出這張圖上所有藥名。"},
            ],
        }],
    )
    raw = message.content[0].text.strip()
    if raw.upper().startswith("NONE"):
        return []

    names = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 去掉常見的 bullet / 編號前綴
        line = re.sub(r"^[\s\-\*•·\d\.\)、]+", "", line).strip()
        # 排除明顯不是藥名的雜訊行（純數字、單字符、過長句子）
        if not line or len(line) > 80:
            continue
        if re.fullmatch(r"[\d\W_]+", line):
            continue
        names.append(line)

    # 去重但保留順序
    seen = set()
    unique = []
    for n in names:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    return unique


def recognize_medicine_bag(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """
    用 Claude Vision 辨識藥袋照片。

    流程：
      1. 第一階段：請模型輸出標準 JSON（10 欄位）
      2. 若 JSON parse 失敗或抽不到任何藥 → 第二階段：只擷取藥名清單
      3. 第二階段也失敗 → 回傳空清單，前端走手動輸入

    回傳: {"medications": [...], "raw_text": "...", "stage": "json"|"names"|"empty"}
    """
    media_type = media_type or "image/jpeg"

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
        "- 寧可缺欄位，不要填入錯誤資訊\n"
        "- 只要能看到藥名就一定要列出（其他欄位可以全 null），不要因為資訊不足而整筆放棄"
    )

    raw_first = ""
    try:
        message = client.messages.create(
            model=VISION_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    _image_content_block(image_base64, media_type),
                    {"type": "text", "text": "請辨識這張藥袋上的藥物資訊。"},
                ],
            }],
        )
        raw_first = _strip_code_fence(message.content[0].text)
        parsed = json.loads(raw_first)
        meds = [_normalize_med(m) for m in _coerce_meds_payload(parsed) if isinstance(m, dict)]
        # 過濾掉沒有藥名的筆
        meds = [m for m in meds if (m.get("name") or "").strip()]
        if meds:
            return {"medications": meds, "raw_text": raw_first, "stage": "json"}
        logger.info("Stage 1 (JSON) returned 0 medications, falling back to name extraction.")
    except json.JSONDecodeError:
        logger.warning(f"Stage 1 (JSON) parse failed, raw: {raw_first[:200]}")
    except Exception as e:
        logger.warning(f"Stage 1 (JSON) call failed: {e}")

    # 第二階段：只抓藥名
    try:
        names = _extract_drug_names_fallback(image_base64, media_type)
    except Exception as e:
        logger.error(f"Stage 2 (name extraction) failed: {e}")
        names = []

    if names:
        meds = [_normalize_med({"name": n}) for n in names]
        return {
            "medications": meds,
            "raw_text": raw_first or "\n".join(names),
            "stage": "names",
        }

    return {"medications": [], "raw_text": raw_first, "stage": "empty"}
