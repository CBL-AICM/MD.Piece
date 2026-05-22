import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

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

def _call_ollama(system_prompt: str, user_message: str, history=None, max_tokens: int | None = None) -> str:
    msgs = [{"role": "system", "content": system_prompt}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user_message})
    payload: dict = {
        "model": TEXT_MODEL,
        "stream": False,
        "messages": msgs,
    }
    if max_tokens:
        payload["options"] = {"num_predict": int(max_tokens)}
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json=payload,
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _call_groq(system_prompt: str, user_message: str, history=None, max_tokens: int | None = None) -> str:
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
        body: dict = {
            "model": GROQ_MODEL,
            "messages": msgs,
            "temperature": 0.4,
        }
        if max_tokens:
            body["max_tokens"] = int(max_tokens)
        resp = httpx.post(
            f"{GROQ_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=body,
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


def _call_anthropic(system_prompt: str, user_message: str, history=None, max_tokens: int | None = None) -> str:
    if _anthropic_client is None:
        raise RuntimeError(
            "ANTHROPIC_API_KEY 未設定或 anthropic SDK 未安裝；無法使用 Anthropic provider"
        )
    msgs = list(history) if history else []
    msgs.append({"role": "user", "content": user_message})
    msg = _anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=int(max_tokens) if max_tokens else ANTHROPIC_MAX_TOKENS,
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


def call_claude(system_prompt: str, user_message: str, history=None, max_tokens: int | None = None) -> str:
    """文字生成（相容原 claude_service 簽名）— 依 LLM_PROVIDER 自動切換 provider，
    主 provider 失敗時自動降級到下一個可用的（anthropic → groq → ollama）。

    history: 可選，[{role: 'user'|'assistant', content: str}, ...] 多輪歷史
    max_tokens: 可選，覆寫該次呼叫的回應長度上限（避免結構化 JSON 被截斷）。
                未指定時用 ANTHROPIC_MAX_TOKENS 預設值（1024）。
    """
    chain = _fallback_chain(LLM_PROVIDER if LLM_PROVIDER in _PROVIDERS else "ollama")
    last_err = None
    for name in chain:
        fn = _PROVIDERS.get(name)
        if fn is None:
            continue
        try:
            return fn(system_prompt, user_message, history, max_tokens=max_tokens)
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


# ==============================================================================
# 面向病人的「語氣 + 詞彙」風格層
# ------------------------------------------------------------------------------
# 凡是 LLM 輸出會直接被「病人 / 家屬」讀到的 prompt，都應該前置這份風格層。
# OCR / 結構化抽欄位 / 給醫師看的報告 prompt 不需要加（會浪費 token、也可能干擾結構）。
#
# 用法：
#   from backend.services.llm_service import (
#       build_patient_facing_system, compute_patient_context,
#   )
#   ctx = compute_patient_context(patient_id)      # 可選；DB 失敗會回 None
#   system = build_patient_facing_system(MY_ROLE_PROMPT, patient_context=ctx)
#   reply  = call_claude(system, user_msg)
# ==============================================================================

PATIENT_FACING_STYLE_PROMPT = (
    "【MD.Piece 對病人說話的鐵則 — 違反任何一條都算錯誤輸出】\n\n"
    "[A. 用詞]\n"
    "1. 一律繁體中文 + 台灣生活口語。專業詞要翻成大家聽得懂的話。\n"
    "   不准用：outcome、復發風險、變異度、預測區間、依從性、預後、急性發作、代償、\n"
    "   惡化曲線、置信區間、p 值、相對風險、絕對風險。\n"
    "   改用：「最近幾天的情況」「跟你以前比起來」「身體給的訊號」「最近不太穩」\n"
    "   「按時吃藥的狀況」「之後可能怎麼樣」。\n"
    "2. 不主動丟百分比、機率、分數給病人。\n"
    "   不准：「復發風險 38%」「依從性 72%」「分數 6/10」「健康分數 87 分」。\n"
    "   改用分級文字：\n"
    "     穩定          ── 目前看起來跟平常差不多，照原本方式繼續就好\n"
    "     需注意        ── 最近這幾天的情況跟你以前比起來不太一樣，建議多留意\n"
    "     建議盡快回診  ── 這個訊號比較需要醫師看一下，建議近期就回診\n"
    "     緊急          ── 請現在就到急診 / 撥 119，不要等\n"
    "   只有當使用者**主動要求數字**才補，並一定要附一句白話解釋。\n"
    "3. 全 app 用詞統一：\n"
    "   - 紀錄（不用「日誌」「資料」）\n"
    "   - 對病人講話一律叫「藥」（欄位標頭才可用「藥物」）\n"
    "   - 「症狀」或「不舒服」二選一，整段保持一致\n"
    "   - 一般情況「回診」；急性情況「就醫」\n"
    "   - 一般情況「醫師」；提到特定那位才用「主治醫師」\n\n"
    "[B. 語氣]\n"
    "4. 你是「陪伴者」，不是老師、不是裁判。\n"
    "   不准：「你今天又沒記錄」「你的數值不合格」「你做錯了」「你應該要…」\n"
    "   「你忘了…」「你沒有按時…」。\n"
    "   改用：「今天還沒看到紀錄喔，有空再補上就好」\n"
    "   「最近這幾天有幾次沒對到時間，要不要我幫你重新調提醒？」\n"
    "5. 壞消息要「平穩 + 給方向」。不准輕描淡寫、也不准用嚇人字眼。\n"
    "   不准：「沒事啦放心」「別擔心一定沒事」「應該還好吧」\n"
    "         「情況很糟」「很危險」「再不處理會出事」。\n"
    "   改用：「這週的趨勢需要留意，建議你回診時跟醫師提這件事」。\n"
    "6. 不給假保證。不准「一定不會」「絕對沒事」「保證會好」「不會復發」。\n"
    "7. 不確定 / 超出 AI 能判斷的範圍 → 一律明白說「這個要請你的醫師判斷」。\n"
    "8. 不替病人下決定（要不要停藥、要不要去急診、要不要做哪個檢查）。\n"
    "   你能做的：整理資訊、幫他想到要問醫師什麼、提醒紅旗訊號。\n\n"
    "[C. 反過度依賴 + 角色澄清]\n"
    "9. 系統是「協助病人去看醫師」，不是「代替醫師」。\n"
    "   不准：「看起來沒事，不用回診」「應該不用看醫生」「這個我可以幫你判斷」。\n"
    "   改用：「目前看起來穩定，下次原訂回診時再讓醫師確認就好」\n"
    "         「這個我沒辦法幫你判斷，要請醫師看一下」\n"
    "         「你可以把這份紀錄帶去給醫師，會更清楚」。\n"
    "   遇到「我需要回診嗎？」── 永遠偏向「建議與醫師討論」，不替醫師說「不用」。\n"
    "10. 含「分析」「趨勢」「可能」「建議」的回覆，要在那段話**裡面**自然帶一句\n"
    "    澄清（不是只靠最後的免責聲明）：\n"
    "    例：「這是根據你的紀錄整理出來的觀察，**不是診斷**，要請醫師確認。」\n"
    "    用平穩、自然的方式融進句子裡，不要用警示框口吻。\n\n"
    "[D. 結尾免責聲明]\n"
    "11. 面向病人的「文字回覆」結尾必須帶一行：\n"
    "    「此回覆由 AI 整理，僅供參考；實際診療請依您的主治醫師為準。」\n"
    "    回覆是純 JSON / 結構化欄位時，這條免責聲明放在指定欄位裡（例如 disclaimer）。\n"
)


PATIENT_FACING_GLOSSARY = (
    "【詞彙對照表 — 病人看得到的文字必須遵守】\n"
    "醫療術語              → 病人語\n"
    "outcome / 預後        → 之後可能怎麼樣\n"
    "復發風險升高          → 最近這幾天的狀況跟你以前比較不穩\n"
    "變異度大              → 數值起伏比較大\n"
    "預測區間              → 大概的範圍\n"
    "依從性 / adherence    → 按時吃藥的狀況\n"
    "急性發作              → 突然不舒服\n"
    "代償                  → 身體在撐\n"
    "惡化                  → 變得比較嚴重\n"
    "穩定                  → 跟平常差不多\n"
    "監測                  → 追蹤、注意\n"
    "評估                  → 看看狀況\n"
    "高風險                → 比較需要注意\n"
    "低風險                → 看起來還算穩定\n"
)


PATIENT_FACING_EXAMPLES = (
    "【正確 vs 錯誤示範】\n\n"
    "情境 A：病人這 3 天血壓比平常高一點\n"
    "✗「您的血壓變異度增加，復發風險為中度偏高（約 32%），請注意。」\n"
    "✓「這 3 天的血壓比你平常高一點，雖然還沒到很嚴重，但建議下次回診時跟醫師提一下，\n"
    "  看要不要調整。」\n\n"
    "情境 B：病人連續兩天沒記錄\n"
    "✗「您今天又沒有記錄了，請按時填寫。」\n"
    "✗「太棒了！其實不記錄也沒關係，不用太在意。」\n"
    "✓「這兩天還沒看到紀錄喔，有空再補上就好。如果是提醒時間不順，要不要我幫你調整一下？」\n\n"
    "情境 C：病人問「我會不會復發？」\n"
    "✗「放心，一定不會復發的。」\n"
    "✗「根據資料，您 12 個月內復發機率約 18%。」\n"
    "✓「會不會復發要請你的醫師根據完整檢查判斷，我這邊沒辦法幫你下結論。我可以做的是幫你\n"
    "  整理最近的紀錄，下次回診時拿給醫師看，會比較有幫助。」\n\n"
    "情境 D：紅旗症狀（胸痛 + 喘）\n"
    "✗「您的症狀分數較高，建議評估。」\n"
    "✓「胸痛加上喘不過氣，這個情況請現在就到急診，或撥 119，不要等。其他狀況我們之後再慢慢看。」\n\n"
    "情境 E：使用者剛註冊第 1 天，記了一筆血壓 138/88\n"
    "✗「資料不足，無法分析。請繼續累積至少 14 天的紀錄。」\n"
    "✓「138/88 我幫你記下來了。這個數字算偏高一點，但單一次不代表什麼，要看接下來幾天的變化。\n"
    "  下次量的時候再記一筆，我們慢慢看出你的規律。」\n\n"
    "情境 F：使用者 5 天沒記錄後打開 app\n"
    "✗「您已經 5 天沒有紀錄了！請保持每日記錄習慣。」\n"
    "✓「嗨，又見面了。今天想記點什麼嗎？簡單一筆就好。」\n\n"
    "情境 G：連續記錄一個月後\n"
    "✗「您本週共記錄 23 次。請繼續保持。」\n"
    "✓「這個月你記了 87 次，比上個月多很多。因為這樣，我才看得出你下午 3 點前後血壓偏高的規律──\n"
    "  這個觀察下次回診時可以跟醫師提，看是不是要調整服藥時間。」\n\n"
    "情境 H：病人問「最近都還可以，是不是不用回診了？」\n"
    "✗「看起來穩定，可以不用回診。」\n"
    "✓「這幾週紀錄看起來算穩定，這是好消息。不過要不要調整回診時間，還是要請醫師判斷，\n"
    "  我這邊沒辦法替醫師決定。原訂的回診建議還是照常去比較好。」\n\n"
    "情境 I：病人問「那我這個是不是高血壓前期？」\n"
    "✗「根據您的紀錄，符合高血壓前期定義。」\n"
    "✓「你最近的數值有一些偏高的跡象，但『是不是高血壓前期』要請醫師看完整檢查才能判斷，\n"
    "  這是診斷層級的判斷，不是我能幫你下的。我可以做的是把這份紀錄整理好，下次回診時直接給醫師看。」\n"
)


@dataclass
class PatientContext:
    """病人在 app 上的使用狀態 — 用來決定 LLM 該用哪種陪伴節奏。

    - record_count        : 全部紀錄（症狀 + 情緒 + 服藥 + 飲食）的總筆數
    - days_since_first    : 距離第一筆紀錄的天數（None = 完全沒紀錄）
    - days_since_last     : 距離最近一筆紀錄的天數（None = 完全沒紀錄）

    任一欄位為 None 都代表「資料未知」，呼叫端應視為「沒有額外狀態提示」。
    """

    record_count: int = 0
    days_since_first: Optional[int] = None
    days_since_last: Optional[int] = None


def _parse_iso_ts(s: Optional[str]) -> Optional[datetime]:
    """Best-effort 把 Supabase / SQLite 拿回來的 timestamp 字串轉成 aware datetime。
    失敗就回 None — 拿來算 days 時會被略過。"""
    if not s or not isinstance(s, str):
        return None
    try:
        # Supabase 常見格式："2024-..Z" / "2024-..+00:00" / "2024-...123456+00:00"
        ts = s.replace("Z", "+00:00")
        # 沒有 tz 資訊就當 UTC
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def compute_patient_context(patient_id: Optional[str]) -> Optional[PatientContext]:
    """從 DB 算出病人目前的使用狀態（紀錄筆數、首筆/末筆時間）。

    - 沒給 patient_id → None
    - DB 連不上或所有表都失敗 → None（呼叫端視為「狀態未知」）
    - 任何單一表失敗 → 忽略，繼續算其他表（best-effort）

    刻意只挑 timestamp 欄位避免抓回大資料。"""
    if not patient_id:
        return None

    try:
        from backend.db import get_supabase
    except Exception:
        return None

    try:
        sb = get_supabase()
    except Exception as e:
        logger.warning("compute_patient_context: 無法取得 supabase client：%s", e)
        return None

    # (table, timestamp_column)
    sources = [
        ("symptoms_log", "created_at"),
        ("emotions", "created_at"),
        ("medication_logs", "taken_at"),
        ("diet_records", "eaten_at"),
    ]

    total = 0
    first_dt: Optional[datetime] = None
    last_dt: Optional[datetime] = None
    any_success = False

    for table, ts_col in sources:
        try:
            rows = (
                sb.table(table)
                .select(ts_col)
                .eq("patient_id", patient_id)
                .execute()
                .data
                or []
            )
        except Exception as e:
            logger.debug("compute_patient_context: %s 查詢失敗（略過）：%s", table, e)
            continue
        any_success = True
        total += len(rows)
        for r in rows:
            dt = _parse_iso_ts(r.get(ts_col))
            if dt is None:
                continue
            if first_dt is None or dt < first_dt:
                first_dt = dt
            if last_dt is None or dt > last_dt:
                last_dt = dt

    if not any_success:
        return None

    now = datetime.now(timezone.utc)
    days_first = (now - first_dt).days if first_dt else None
    days_last = (now - last_dt).days if last_dt else None

    return PatientContext(
        record_count=total,
        days_since_first=days_first,
        days_since_last=days_last,
    )


def _patient_state_hint(ctx: Optional[PatientContext]) -> str:
    """依使用狀態回傳一段塞進 system prompt 的「對話節奏提示」。

    四種狀態：
      - none        : 完全沒紀錄（剛註冊或所有紀錄都被刪）
      - cold_start  : 紀錄 < 5 筆 或 距離首筆 < 14 天
      - returning   : 距離上次紀錄 ≥ 3 天（中斷後回來）
      - long_term   : 其他（不額外提示）

    none / cold_start / returning 才回傳提示；long_term 回空字串。"""
    if ctx is None:
        return ""

    if ctx.record_count == 0:
        return (
            "【目前使用者狀態：尚無任何紀錄】\n"
            "- 絕對不要說「資料不足無法分析」「請繼續累積資料」這類話。\n"
            "- 把使用者「正在跟你說的這件事 / 剛記下的這一筆」當成有意義的內容，\n"
            "  先複述、肯定、整理。\n"
            "- 給一個「下一步可以做什麼」的小邀請（不是任務、不是命令）。\n"
            "- 不要塞「健康分數 / 風險指數 / 預測曲線」這類需要長期資料才有意義的東西。\n"
        )

    is_cold = (ctx.record_count < 5) or (
        ctx.days_since_first is not None and ctx.days_since_first < 14
    )
    if is_cold:
        return (
            f"【目前使用者狀態：冷啟動（紀錄共 {ctx.record_count} 筆，"
            f"距首次紀錄 {ctx.days_since_first if ctx.days_since_first is not None else '?'} 天）】\n"
            "- 絕對不要說「資料不足」「請繼續累積資料」。\n"
            "- 把單一筆紀錄本身當成有意義 — 跟基準值比、跟前一筆比、給一句白話衛教即可。\n"
            "- 不要呈現「趨勢」「風險分數」「預測」等需要長期資料的結論。\n"
            "- 可以提一句「等你再記幾次，我們就能一起看出你的規律」這類邀請。\n"
        )

    if ctx.days_since_last is not None and ctx.days_since_last >= 3:
        return (
            f"【目前使用者狀態：中斷回歸（上一筆紀錄是 {ctx.days_since_last} 天前）】\n"
            "- 第一句絕對不准是檢討。禁止：「你已經 X 天沒記錄」「中斷了 X 次」\n"
            "  「請保持紀錄習慣」。\n"
            "- 正確口吻：「嗨，又見面了」「回來啦，要不要先簡單記一下現在的感覺？」\n"
            "  「沒記錄的這幾天沒關係，從今天開始就好」。\n"
            "- 生成 summary 時自動跳過空白區間，不要強調缺漏；如果無法跳過，\n"
            "  也用淡淡的「這段期間沒有紀錄」帶過，不要醒目化。\n"
        )

    # long-term active 使用者 — 給「努力↔成果連結」的鼓勵提示
    return (
        f"【目前使用者狀態：長期使用者（共 {ctx.record_count} 筆紀錄）】\n"
        "- 適當把「使用者持續紀錄的行為」跟「具體看得到的好處」綁在一起，\n"
        "  例：「因為你連續記了血壓，這次回診時可以直接拿這份趨勢給醫師看，會比口頭描述清楚很多。」\n"
        "- 不要只說「請繼續保持」這種空話。\n"
    )


def build_patient_facing_system(
    role_prompt: str,
    *,
    patient_context: Optional[PatientContext] = None,
    include_examples: bool = True,
) -> str:
    """組裝「面向病人」的完整 system prompt。

    層次（順序固定，模型先讀到的權重最高）：
      1. 風格憲法（用詞 / 語氣 / 反過度依賴 / 角色澄清）
      2. 詞彙對照表
      3. 使用者狀態提示（依 patient_context 動態產生；不適用就跳過）
      4. 該角色 / 該情境的專屬 prompt（role_prompt）
      5. few-shot 範例（短對話可以 include_examples=False 省 token）

    role_prompt 一律放在憲法之後 — 個別 prompt 不要再去重複規定語氣，
    把專屬內容（例如「你是小禾」「請列出三件事」「請輸出 JSON」）寫在裡面就好。"""
    parts: list[str] = [PATIENT_FACING_STYLE_PROMPT, PATIENT_FACING_GLOSSARY]

    hint = _patient_state_hint(patient_context)
    if hint:
        parts.append(hint)

    parts.append(role_prompt)

    if include_examples:
        parts.append(PATIENT_FACING_EXAMPLES)

    return "\n\n".join(parts)


_MED_BAG_SYSTEM_PROMPT = (
    "你是台灣藥物資訊辨識助手。輸入照片可能是下列任一種：\n"
    "  (a) 藥袋（單包藥的外袋）\n"
    "  (b) 藥單 / 處方箋 / 領藥明細（A4 或長條表格，常見於台大、榮總、長庚、亞東、"
    "      馬偕、各地區醫院、診所、社區藥局；典型欄位：藥品名稱 / 劑量 / 用法 / 數量 / 天數）\n"
    "  (c) 出院帶藥清單、慢箋、回診指示單\n"
    "  (d) 藥盒 / 藥品包裝盒 / 商品藥外盒（例如普拿疼、Panadol、Tylenol、Strepsils 之類市售 OTC，"
    "      或藥廠原裝處方藥外盒；通常正反面會印商品名 + 學名 + 劑量規格 + 廠商；"
    "      可能整個盒面都是英文，也可能中英並列）\n"
    "  (e) 藥罐 / 藥瓶上的標籤 / 鋁箔背板（blister pack）：上面通常會印藥名、規格、批號\n\n"
    "**不管是哪一種版型、不管是處方藥還是市售藥**，請從照片裡所有可見文字萃取出以下「標準欄位」：\n\n"
    "標準欄位：\n"
    "  - name        藥名（**完全照抄影像上看得到的字**。"
    "                  優先抓「藥品學名（generic name / INN）」，例如 Acetaminophen、Ibuprofen、Atorvastatin；"
    "                  若藥盒只看得到「商品名 / 品牌名」（例如 Panadol、普拿疼、Tylenol、Lipitor），"
    "                  也要把商品名抓出來——藥物百科系統會用商品名再去查學名。"
    "                  中英並列時可寫成「中文（English）」格式，例：布洛芬（Ibuprofen）；"
    "                  只有英文時直接寫英文，不要硬翻中文；"
    "                  **絕對不要從訓練記憶裡補上類似的藥名**）\n"
    "  - dosage      單次劑量或單顆規格（例：500mg、1 顆、5ml；藥盒上常以「500mg/錠」「100mg/cap」呈現）\n"
    "  - frequency   服用頻率（原文照抄；例：一天三次、每 8 小時一次、需要時服用、早晚、QD、BID、TID、QID、Q8H、PRN；"
    "                  若是藥盒沒寫服用頻率就留 null）\n"
    "  - usage       用法/服用時機（例：飯前、飯後、睡前、空腹、口服、外用、含服、舌下）\n"
    "  - duration    療程天數（例：7 天、長期服用；若無資訊留 null）\n"
    "  - category    藥物類別（降血壓藥、降血糖藥、降血脂藥、止痛藥、退燒藥、感冒藥、咳嗽藥、"
    "                  抗生素、胃藥、抗凝血藥、利尿劑、氣管擴張劑、抗組織胺、抗憂鬱藥、維他命/保健、其他）\n"
    "  - purpose     用途（例：控制血糖、緩解頭痛、退燒、止咳；藥盒/藥袋上有寫適應症就抓，沒寫就 null，不要瞎猜）\n"
    "  - instructions 注意事項（**僅限影像上可清楚讀到的警語**；讀不清楚就 null，"
    "                  絕對不要把模糊或亂碼字塞進這個欄位）\n"
    "  - hospital    醫院/診所/藥局名稱（從抬頭、印章、條碼區判讀；藥盒通常沒有，留 null）\n"
    "  - prescribed_date 開立日期（YYYY-MM-DD；若只有民國年請換算成西元年；藥盒通常沒有，留 null）\n\n"
    "回覆必須是純 JSON（不要 markdown code block，不要任何前後說明文字），結構：\n"
    '{"medications": [{"name": "...", "dosage": "...", "frequency": "...", '
    '"usage": "...", "duration": "...", "category": "...", "purpose": "...", '
    '"instructions": "...", "hospital": "...", "prescribed_date": "..."}]}\n\n'
    "規則（醫療場景：錯誤藥名比空欄位嚴重得多，請嚴格遵守）：\n"
    "- 每個欄位都必須存在（即使值為 null）\n"
    "- **看不清楚的欄位 → 一律填 null，不要猜、不要從訓練資料補字**\n"
    "- 一張藥單常包含多種藥（每行一筆），**請逐筆分開列出，不要漏掉任何一行**；\n"
    "  藥盒通常只有 1 種藥，正反面看到的同一個藥名只算一筆\n"
    "- **只要影像上看得到任何藥名（不管是學名還是商品名、不管是處方藥還是市售 OTC），"
    "  一定要列出來**。即使其他欄位（劑量、頻率…）通通 null，也要回傳這一筆，"
    "  讓藥物百科可以用這個名字查詢——這是這個系統最重要的鐵則\n"
    "- **OCR / 視覺辨識亂碼處理（重要）**：\n"
    "    台灣藥盒常把中文字印很小、用花俏字體或反光金箔，OCR / 模型容易把中文辨成"
    "    語意不通的怪字串（例：把「希樂葆 200 毫克膜衣錠」誤辨成「蔡萊疫疫特徊 200 欢克徊合汗」）。"
    "    此時請依下列原則決定 name：\n"
    "      1. 如果在亂碼旁邊同時看到**乾淨可讀的英文（或拉丁字）藥名**（例：Celecoxib、Atorvastatin、Panadol），"
    "         **只把英文藥名寫進 name**，**不要把亂碼中文也串進去**。\n"
    "      2. 如果中文部分明顯不是 OCR 亂碼、是真實可讀的藥名（例：「布洛芬」「希樂葆」），"
    "         才用「中文（English）」並列格式。\n"
    "      3. 如果只有亂碼中文、沒有可信的英文藥名，name 留 null（**不要把亂碼當藥名**）。\n"
    "      4. 「亂碼」的判定基準：字串裡含有**明顯不會出現在藥名中的怪字組合**"
    "         （例如「徊合汗」「欢克」「疫疫」這種非標準詞彙、或夾雜罕見字），"
    "         或同一段話讀起來語意完全不通。寧可漏字、不要塞亂碼\n"
    "- frequency 請保留原文（例如「一天三次」「每 8 小時」「早晚」「BID」），系統會自動歸類時段\n"
    "- **照片若是側躺、倒立、模糊**：請先想像旋轉到正向再讀；若旋轉後仍完全讀不出任何文字，"
    "  才回傳空 medications 陣列。**不要硬湊一個藥名**（例如不要把模糊字補成 Prednisolone、Aspirin 等常見藥）\n"
    "- **抗幻覺自檢**：你給出的 name 必須是影像上實際出現的字串。"
    "  輸出前請反問自己「這個藥名我是真的看到，還是聯想出來的？」如果是後者，請改回空陣列\n"
    "- 風景、人臉、食物、空白紙張、或文字完全無法閱讀的情況才回空陣列；"
    "  只要看到合理的藥名（例如盒面印著「PANADOL 500mg」就算成立），就要回傳"
)

_MED_BAG_USER_PROMPT = (
    "請辨識這張照片（可能是藥袋、藥單、處方箋、領藥明細、藥盒/藥品外盒、藥罐標籤、或鋁箔背板）"
    "上的所有藥物資訊，**逐筆**分開列出。"
    "**只要看得到藥名（不管是商品名還是學名）就一定要列出**，"
    "即使其他欄位都 null 也要回傳，不要回空陣列。"
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
    "你是台灣藥物資訊抽取助手。輸入是 OCR 從以下任一種照片讀出的原始文字"
    "（可能有錯字、缺字、版面亂、夾雜雜訊）：\n"
    "  (a) 藥袋／藥單／處方箋／領藥明細\n"
    "  (b) 藥盒／藥品外盒／商品藥包裝（例如普拿疼、Panadol、Tylenol、Strepsils；"
    "      盒面通常會印商品名 + 學名 + 規格，可能整個都是英文）\n"
    "  (c) 藥罐標籤、鋁箔背板\n\n"
    "請從這段文字抽取所有藥物，整理成 JSON：\n\n"
    "標準欄位：\n"
    "  - name        藥名（保留原文；中英並列時用「中文（English）」格式；只有英文就直接寫英文。"
    "                  學名（generic name）優先；若只看得到商品名／品牌名（Panadol、普拿疼、Lipitor 等）"
    "                  也要抓出來，藥物百科會用商品名再去查學名）\n"
    "  - dosage      單次劑量或單顆規格（例：500mg、1 顆、5ml、500mg／錠）\n"
    "  - frequency   服用頻率（原文照抄；例：一天三次、每 8 小時、需要時、QD、BID、TID、Q8H、PRN；"
    "                  藥盒沒寫頻率就 null）\n"
    "  - usage       用法/服用時機（飯前、飯後、睡前、空腹、口服、外用、含服、舌下）\n"
    "  - duration    療程天數（7 天、長期；無資訊 null）\n"
    "  - category    藥物類別（降血壓藥、降血糖藥、止痛藥、退燒藥、感冒藥、抗生素、胃藥、"
    "                  抗組織胺、維他命／保健…其他）\n"
    "  - purpose     用途（無寫就 null，不要瞎猜）\n"
    "  - instructions 注意事項\n"
    "  - hospital    醫院/診所/藥局名稱（從抬頭判讀；藥盒通常沒有，留 null）\n"
    "  - prescribed_date 開立日期（YYYY-MM-DD；民國年要換算成西元年；藥盒通常沒有，留 null）\n\n"
    "回覆**必須是純 JSON**，不要 markdown code block、不要前後說明文字：\n"
    '{"medications": [{"name": "...", "dosage": "...", "frequency": "...", '
    '"usage": "...", "duration": "...", "category": "...", "purpose": "...", '
    '"instructions": "...", "hospital": "...", "prescribed_date": "..."}]}\n\n'
    "規則：\n"
    "- 每個欄位都必須存在（無資料用 null）\n"
    "- 一張藥單常有多筆藥，**逐筆分開列出，不要漏掉任何一行**；"
    "  藥盒通常只有 1 種藥，盒子正反面看到同一個藥名只算一筆\n"
    "- **只要 OCR 文字裡看得到任何藥名（學名或商品名都算），一定要列出來**——"
    "  即使其他欄位通通 null 也要回傳這一筆，這樣藥物百科才查得到。寧可不完整，不要回空陣列\n"
    "- **OCR 亂碼清理（重要）**：藥盒上的中文常被 OCR 辨成語意不通的怪字組合"
    "  （例：把「希樂葆 200 毫克膜衣錠」誤辨成「蔡萊疫疫特徊 200 欢克徊合汗」）。"
    "  此時請依下列原則決定 name：\n"
    "    1. 若亂碼附近有完整、可信的英文／拉丁藥名（celecoxib、acetaminophen、Lipitor…），"
    "       **只把英文藥名寫進 name**，不要把亂碼中文也串進去。\n"
    "    2. 若中文部分讀起來是真實藥名（布洛芬、希樂葆…）就照寫；"
    "       明顯不通的怪字組合（「徊合汗」「欢克」「疫疫」等）一律當亂碼丟棄。\n"
    "    3. 若整段只剩亂碼、沒有可信英文藥名，name 留 null（不要把亂碼當藥名硬塞）\n"
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


# ── 檢驗報告照片辨識 ────────────────────────────────────────
# 從一張檢驗報告照片，一次抽出所有項目並判讀正常/異常。
# 走法跟 medicine bag 一樣：Google Vision OCR（最準）→ LLM vision fallback。

_LAB_REPORT_EXTRACT_PROMPT = (
    "你是台灣檢驗報告判讀助手。輸入是一張檢驗報告（OCR 後的純文字）。\n"
    "請從文字中抽出所有檢驗項目，並依台灣常見成人參考範圍判讀每個項目。\n\n"
    "每個項目要包含：\n"
    "  - name          項目名稱（中英並列；只有英文就直接寫英文）\n"
    "  - value         數值（保留原樣字串，可含 < > ＋ 陽 陰）\n"
    "  - unit          單位（沒有就 null）\n"
    "  - normal_range  常見成人參考範圍文字（不確定的罕見項目寫「不確定」）\n"
    "  - status        low | normal | high | critical | unknown\n"
    "  - meaning       這個指標代表什麼（白話一兩句）\n"
    "  - advice        生活面建議（飲食、運動、追蹤頻率），具體可行\n"
    "  - see_doctor    true / false；數值嚴重異常或可能急症（例如鉀過高、血糖極低、肝指數爆高）就 true\n\n"
    "規則：\n"
    "1. 報告抬頭、患者基本資料、機構名稱不算項目，請忽略\n"
    "2. 一份報告通常有 5～30 個項目，**請逐項列出，不要只挑幾個**\n"
    "3. 數值跟參考範圍同一行就一起讀；報告若已標註 H/L 也納入判讀\n"
    "4. 不下診斷、不開藥、不取代醫師判讀\n"
    "5. 罕見項目寧可 status=unknown 也不要瞎掰\n\n"
    "回覆**必須是純 JSON**，不要 markdown code block、不要前後說明：\n"
    '{"items": [{"name":"...","value":"...","unit":"...","normal_range":"...",'
    '"status":"...","meaning":"...","advice":"...","see_doctor":false}]}\n'
    "全部使用繁體中文。"
)

_LAB_REPORT_VISION_USER_PROMPT = (
    "這是一張檢驗報告。請按照系統提示，把所有項目逐一抽出並判讀，"
    "回傳純 JSON。"
)


def _vision_lab_report_anthropic(image_base64: str, media_type: str) -> str:
    if _anthropic_client is None:
        raise RuntimeError("ANTHROPIC_API_KEY 未設定或 anthropic SDK 未安裝")
    msg = _anthropic_client.messages.create(
        model=ANTHROPIC_VISION_MODEL,
        max_tokens=ANTHROPIC_VISION_MAX_TOKENS,
        temperature=0.2,
        system=_LAB_REPORT_EXTRACT_PROMPT,
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
                    {"type": "text", "text": _LAB_REPORT_VISION_USER_PROMPT},
                ],
            }
        ],
    )
    return (msg.content[0].text or "").strip()


def _vision_lab_report_groq(image_base64: str, media_type: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY 未設定")
    data_url = f"data:{media_type or 'image/jpeg'};base64,{image_base64}"
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
                        {"type": "text", "text": _LAB_REPORT_EXTRACT_PROMPT + "\n\n" + _LAB_REPORT_VISION_USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return (resp.json()["choices"][0]["message"]["content"] or "").strip()


_LAB_VISION_PROVIDERS = {
    "anthropic": _vision_lab_report_anthropic,
    "groq": _vision_lab_report_groq,
}


def _parse_lab_items_json(raw: str) -> list[dict]:
    """容錯解析 LLM 回的檢驗報告 JSON。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not text.startswith("{") and not text.startswith("["):
        l = text.find("{")
        r = text.rfind("}")
        if l != -1 and r != -1 and r > l:
            text = text[l : r + 1]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Lab report parse non-JSON: {raw[:200]}")
        return []
    items = result.get("items") if isinstance(result, dict) else result
    return items if isinstance(items, list) else []


# ── 藥物百科查詢 ────────────────────────────────────────────
# 給藥物搜尋功能用：給定藥名（中/英文/商品名），請 LLM 整理副作用、風險、用法、衛教。
# 結果會被 backend/routers/drug_search.py 寫進 drug_reference 表做快取，
# 之後同一個藥就不會再呼叫 LLM。

_DRUG_INFO_PROMPT = (
    "你是 MD.Piece 平台的藥物資訊衛教助手，協助一般民眾理解他/她正在服用或將要服用的藥物。\n\n"
    "輸入：使用者查詢的藥名（可能是中文、英文、學名或商品名，可能拼字不完全正確）。\n"
    "任務：辨識這個藥是什麼，整理出基礎衛教資訊。\n\n"
    "回覆**必須是純 JSON**（不要 markdown code block、不要前後說明文字），結構如下：\n"
    "{\n"
    '  "matched": true | false,\n'
    '  "name_zh": "中文通用名（學名為主，括號附常見商品名；找不到中文翻譯就 null）",\n'
    '  "name_en": "英文學名（INN / generic name）",\n'
    '  "aliases": ["商品名 1", "商品名 2", "別名…"],\n'
    '  "category": "藥物分類（降血壓藥、降血糖藥、止痛藥、抗生素、胃藥、抗凝血藥、其他…）",\n'
    '  "indication": "臨床適應症 — 一般用來治療什麼？用一兩句話說明",\n'
    '  "usage": "用法用量 — 一般成人怎麼服用？飯前飯後？常見頻率？特殊提醒（嚼碎/整顆吞）",\n'
    '  "side_effects": {\n'
    '    "common": ["常見副作用 1（多數人會適應）", "常見副作用 2", "..."],\n'
    '    "serious": ["嚴重但少見的副作用 1（出現要立刻就醫）", "..."]\n'
    "  },\n"
    '  "risks": {\n'
    '    "contraindications": ["哪些人不可以用 / 禁忌症"],\n'
    '    "warnings": ["重要警語"],\n'
    '    "interactions": ["常見藥物或食物交互作用"]\n'
    "  },\n"
    '  "education": "基礎衛教 — 用親切的口吻提醒使用者怎麼安全、有效地使用這個藥；包括漏服怎麼辦、儲存方式、何時該回診。150~300 字",\n'
    '  "disclaimer": "此資訊由 AI 整理，僅供衛教參考，個別用藥請以醫師處方與藥師說明為準。"\n'
    "}\n\n"
    "規則（醫療場景，安全優先）：\n"
    "1. 若**完全不認識**這個藥（看起來不像任何已知藥物）：matched=false，其餘欄位填 null 或空陣列，"
    '   並在 disclaimer 註明「無法辨識此藥名，請確認拼字或聯絡藥師」\n'
    "2. 拼字接近但不完全相同：合理推測（例如 \"acetamenophen\" → acetaminophen），"
    "   並在 aliases 把使用者輸入也列進去\n"
    "3. **不要瞎猜劑量數字**；usage 用一般描述（「依醫師指示，常見每 6~8 小時一次」），"
    "   不要寫死「500mg」這種具體數字\n"
    "4. **嚴重副作用一定要列**：過敏反應、呼吸困難、嚴重皮疹、肝/腎指數異常、"
    "   黑便或血便、心律不整 — 出現任一即需立刻就醫\n"
    "5. 全部使用繁體中文（除了藥名英文部分）\n"
    "6. 不下個人化處方建議；不取代醫師判斷"
)


def lookup_drug_info(drug_name: str) -> dict:
    """查詢藥物的基礎衛教資訊（副作用、風險、用法、衛教）。

    讓 LLM 從藥名（中/英文/商品名）整理出結構化的藥物百科欄位。
    呼叫端應將結果存進 drug_reference 表做快取，避免重複呼叫。

    回傳 dict 結構見 _DRUG_INFO_PROMPT。若 LLM 完全無法辨識，
    matched=False；若 JSON 解析失敗，回傳 matched=False 並把原始輸出
    放在 raw_text 供 debug。
    """
    user_message = f"請查詢這個藥物：「{drug_name}」"
    # 藥物百科 JSON 包含 6 個列表 + 150~300 字衛教，預設 1024 token 會被截斷
    # （結果就是回到使用者眼前的「未命名」空卡片），這裡放寬到 2048 才夠裝完整結構
    try:
        raw = call_claude(_DRUG_INFO_PROMPT, user_message, max_tokens=2048)
    except Exception as e:
        # 例外細節只進 server log，不放進回傳 dict（避免 stack-trace 流到 client）
        logger.error("lookup_drug_info LLM 失敗：%s", type(e).__name__)
        return {
            "matched": False,
            "name_zh": None,
            "name_en": None,
            "aliases": [],
            "category": None,
            "indication": None,
            "usage": None,
            "side_effects": {"common": [], "serious": []},
            "risks": {"contraindications": [], "warnings": [], "interactions": []},
            "education": None,
            "disclaimer": "藥物資訊查詢服務暫時無法使用，請稍後再試。",
        }

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not text.startswith("{"):
        l = text.find("{")
        r = text.rfind("}")
        if l != -1 and r != -1 and r > l:
            text = text[l : r + 1]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # 只把原始輸出留在 log 給維運看；不回傳到 client
        logger.warning("lookup_drug_info 回傳非 JSON：%s", (raw or "")[:200])
        return {
            "matched": False,
            "name_zh": None,
            "name_en": None,
            "aliases": [],
            "category": None,
            "indication": None,
            "usage": None,
            "side_effects": {"common": [], "serious": []},
            "risks": {"contraindications": [], "warnings": [], "interactions": []},
            "education": None,
            "disclaimer": "AI 回覆解析失敗，請改用更具體的藥名重試。",
        }

    # 補齊欄位（LLM 偶爾會漏）
    result.setdefault("matched", bool(result.get("name_zh") or result.get("name_en")))
    result.setdefault("aliases", [])
    if not isinstance(result.get("aliases"), list):
        result["aliases"] = []
    result.setdefault("side_effects", {})
    if not isinstance(result["side_effects"], dict):
        result["side_effects"] = {}
    result["side_effects"].setdefault("common", [])
    result["side_effects"].setdefault("serious", [])
    result.setdefault("risks", {})
    if not isinstance(result["risks"], dict):
        result["risks"] = {}
    result["risks"].setdefault("contraindications", [])
    result["risks"].setdefault("warnings", [])
    result["risks"].setdefault("interactions", [])
    result.setdefault(
        "disclaimer",
        "此資訊由 AI 整理，僅供衛教參考，個別用藥請以醫師處方與藥師說明為準。",
    )

    # 防呆：LLM 偶爾會回 matched=true 但所有欄位都空（小模型對結構化輸出失敗、
    # 或被截斷後勉強生成的殘骸）— 這時前端會看到「未命名」+ 全 (無資料) 的廢卡片。
    # 寧可降為 matched=false 讓前端顯示明確的「無法辨識」，也不要把無用資料寫進快取。
    if result.get("matched"):
        has_name = bool(result.get("name_zh") or result.get("name_en"))
        risks = result["risks"]
        side = result["side_effects"]
        has_content = any([
            result.get("indication"),
            result.get("usage"),
            result.get("category"),
            result.get("education"),
            side.get("common"),
            side.get("serious"),
            risks.get("contraindications"),
            risks.get("warnings"),
            risks.get("interactions"),
        ])
        if not has_name or not has_content:
            logger.warning(
                "lookup_drug_info matched=true 但內容為空（query=%s, has_name=%s, has_content=%s）"
                "— 視為無法辨識",
                drug_name, has_name, has_content,
            )
            result["matched"] = False
            result["disclaimer"] = (
                "AI 整理藥物資訊時資料不完整，請改用更具體或正確拼寫的藥名再試一次。"
            )

    return result


def recognize_lab_report(image_base64: str, media_type: str = "image/jpeg") -> dict:
    """辨識檢驗報告照片，一次抽出所有項目並判讀。

    優先順序：
      1. Google Cloud Vision OCR + text LLM 抽欄位 + 判讀（中文小字最準）
      2. Fallback：LLM vision 一段式（anthropic / groq）

    回傳: {
        "items": [{"name", "value", "unit", "normal_range",
                   "status", "meaning", "advice", "see_doctor"}, ...],
        "raw_text": "<OCR 純文字或 vision 原始輸出>",
        "provider": "google_vision | anthropic | groq | None",
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
                extract_raw = call_claude(_LAB_REPORT_EXTRACT_PROMPT, ocr_text)
                items = _parse_lab_items_json(extract_raw)
                if items:
                    return {
                        "items": items,
                        "raw_text": ocr_text,
                        "provider": "google_vision",
                        "errors": errors,
                    }
                errors.append({"provider": "google_vision+extract", "error": "no items extracted from ocr"})
            except Exception as e:
                errors.append({"provider": "google_vision+extract", "error": f"{type(e).__name__}: {e}"})
                logger.warning(f"從 OCR 抽檢驗項目失敗：{e}")
        elif ocr_text is not None:
            errors.append({"provider": "google_vision", "error": f"ocr too short ({len(ocr_text or '')} chars)"})

    # Stage 2 (fallback): LLM vision 一段式
    chain = []
    if _anthropic_client is not None:
        chain.append("anthropic")
    if GROQ_API_KEY:
        chain.append("groq")

    last_raw = ""
    for name in chain:
        fn = _LAB_VISION_PROVIDERS.get(name)
        if fn is None:
            continue
        try:
            raw = fn(image_base64, media_type)
        except Exception as e:
            errors.append({"provider": name, "error": f"{type(e).__name__}: {e}"})
            logger.warning(f"Lab vision provider {name} 失敗：{e}")
            continue
        last_raw = raw
        items = _parse_lab_items_json(raw)
        if items:
            return {
                "items": items,
                "raw_text": raw,
                "provider": name,
                "errors": errors,
            }
        errors.append({"provider": name, "error": "no lab items recognized"})

    return {
        "items": [],
        "raw_text": last_raw,
        "provider": None,
        "errors": errors,
    }


# ── 疾病百科查詢 ────────────────────────────────────────────
# 給疾病搜尋功能用：給定疾病名（中/英文），請 LLM 整理疾病資訊、用藥、風險、未來發展。
# 結果會被 backend/routers/diseases.py 寫進 disease_reference 表做快取。
# 文獻來源由 PubMed E-utilities REST API 即時取回（前 3 篇近期文獻），確保「文獻來源」非幻覺。

_DISEASE_INFO_PROMPT = (
    "你是 MD.Piece 平台的疾病衛教助手，協助一般民眾理解某個疾病。\n\n"
    "輸入：使用者查詢的疾病名稱（可能是中文、英文，可能不完全精確）。\n"
    "任務：辨識這是什麼疾病，整理出完整的衛教資訊。\n\n"
    "回覆**必須是純 JSON**（不要 markdown code block、不要前後說明文字），結構如下：\n"
    "{\n"
    '  "matched": true | false,\n'
    '  "name_zh": "中文通用名（找不到中文翻譯就 null）",\n'
    '  "name_en": "英文名稱",\n'
    '  "aliases": ["別名 1", "別名 2"],\n'
    '  "icd10_code": "最相關的 ICD-10 代碼（找不到就 null）",\n'
    '  "icd10_category": "ICD-10 分類（如：循環系統疾病、內分泌與代謝疾病）",\n'
    '  "overview": "200~350 字 — 這是什麼病？用生活化的比喻讓一般民眾能理解；包含好發族群、盛行率粗略概念",\n'
    '  "causes": ["主要病因或風險因子 1", "風險因子 2", "..."],\n'
    '  "symptoms": {\n'
    '    "common": ["常見症狀 1", "常見症狀 2"],\n'
    '    "warning": ["警訊症狀 1（需立刻就醫）", "..."]\n'
    "  },\n"
    '  "common_medications": [\n'
    '    {"name": "藥物學名（中/英）", "drug_class": "藥物分類", "purpose": "在這個病裡的角色（一句話）"}\n'
    "  ],\n"
    '  "treatments": ["非藥物治療 1（手術、復健、生活介入等）", "..."],\n'
    '  "complications": ["長期未控制可能的併發症 1", "..."],\n'
    '  "prognosis": "150~250 字 — 未來發展與預後：自然病程、是否可逆、好好治療的話通常結果如何、需要多久追蹤一次",\n'
    '  "self_care": ["飲食建議", "運動建議", "追蹤頻率", "其他自我管理小技巧"],\n'
    '  "red_flags": ["何時應立刻就醫的明確訊號 1", "..."],\n'
    '  "disclaimer": "此資訊由 AI 整理，僅供衛教參考，不能取代醫師診斷與個別處方。實際治療請以您的主治醫師建議為準。"\n'
    "}\n\n"
    "規則（醫療場景，安全優先）：\n"
    "1. 若**完全不認識**這個疾病：matched=false，其餘欄位填 null 或空陣列，"
    '   disclaimer 註明「無法辨識此疾病名，請確認拼字或聯絡專業醫療人員」\n'
    "2. 拼字接近但不完全相同：合理推測（例如「糖尿病第二型」→ 第二型糖尿病），把使用者輸入也列進 aliases\n"
    "3. **絕對不要瞎猜具體數字**（例如：「30% 的人會中風」），用範圍或定性描述\n"
    "4. **嚴重併發症與警訊一定要列**，但語氣要平實，不恐嚇\n"
    "5. 用藥只列**藥物分類層級**或常見學名，不寫劑量、不寫個人化用法\n"
    "6. 全部繁體中文（藥物學名英文可保留）\n"
    "7. 不下個人化處方建議；不取代醫師判斷；最後一定要保留 disclaimer 欄位"
)


def _empty_disease_info(disclaimer: str) -> dict:
    return {
        "matched": False,
        "name_zh": None,
        "name_en": None,
        "aliases": [],
        "icd10_code": None,
        "icd10_category": None,
        "overview": None,
        "causes": [],
        "symptoms": {"common": [], "warning": []},
        "common_medications": [],
        "treatments": [],
        "complications": [],
        "prognosis": None,
        "self_care": [],
        "red_flags": [],
        "disclaimer": disclaimer,
    }


def lookup_disease_info(disease_name: str) -> dict:
    """查詢疾病的衛教資訊（資訊、用藥、風險、未來發展）。

    讓 LLM 整理結構化的疾病百科欄位。
    呼叫端應將結果存進 disease_reference 表做快取。

    回傳 dict 結構見 _DISEASE_INFO_PROMPT。
    """
    user_message = f"請查詢這個疾病：「{disease_name}」"
    try:
        # 疾病百科 JSON 比藥物大（含 prognosis、self_care、treatments），給 2560 token 比較保險
        raw = call_claude(_DISEASE_INFO_PROMPT, user_message, max_tokens=2560)
    except Exception as e:
        logger.error("lookup_disease_info LLM 失敗：%s", type(e).__name__)
        return _empty_disease_info("疾病資訊查詢服務暫時無法使用，請稍後再試。")

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not text.startswith("{"):
        l = text.find("{")
        r = text.rfind("}")
        if l != -1 and r != -1 and r > l:
            text = text[l : r + 1]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("lookup_disease_info 回傳非 JSON：%s", (raw or "")[:200])
        return _empty_disease_info("AI 回覆解析失敗，請改用更具體的疾病名稱重試。")

    # 補齊欄位
    result.setdefault("matched", bool(result.get("name_zh") or result.get("name_en")))
    for k in ("aliases", "causes", "common_medications", "treatments",
              "complications", "self_care", "red_flags"):
        if not isinstance(result.get(k), list):
            result[k] = []
    if not isinstance(result.get("symptoms"), dict):
        result["symptoms"] = {}
    result["symptoms"].setdefault("common", [])
    result["symptoms"].setdefault("warning", [])
    if not isinstance(result["symptoms"]["common"], list):
        result["symptoms"]["common"] = []
    if not isinstance(result["symptoms"]["warning"], list):
        result["symptoms"]["warning"] = []
    result.setdefault(
        "disclaimer",
        "此資訊由 AI 整理，僅供衛教參考，不能取代醫師診斷與個別處方。實際治療請以您的主治醫師建議為準。",
    )

    # 防呆：matched=true 但實質欄位都空 → 視為無法辨識
    if result.get("matched"):
        has_name = bool(result.get("name_zh") or result.get("name_en"))
        has_content = any([
            result.get("overview"),
            result.get("prognosis"),
            result.get("causes"),
            result["symptoms"].get("common") or result["symptoms"].get("warning"),
            result.get("common_medications"),
            result.get("treatments"),
            result.get("complications"),
            result.get("self_care"),
            result.get("red_flags"),
        ])
        if not has_name or not has_content:
            logger.warning(
                "lookup_disease_info matched=true 但內容為空（query=%s）— 視為無法辨識",
                disease_name,
            )
            result["matched"] = False
            result["disclaimer"] = (
                "AI 整理疾病資訊時資料不完整，請改用更具體或正確拼寫的疾病名稱再試一次。"
            )

    return result


# ── PubMed 文獻檢索 ─────────────────────────────────────────
# 給疾病百科用的「文獻來源」：呼叫 NCBI E-utilities，依疾病英文名找近年 review。
# 失敗就回傳空 list，不影響主流程。

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def pubmed_search(query: str, max_results: int = 3) -> list[dict]:
    """從 PubMed 查近 5 年的 review，回傳 [{title, authors, year, pmid, url, journal}].

    呼叫失敗（離線、限流、解析錯誤）時回傳空 list。
    """
    if not query or not query.strip():
        return []
    try:
        # 步驟 1：esearch 拿 PMID 列表
        params = {
            "db": "pubmed",
            "term": f"{query.strip()}[Title/Abstract] AND review[Publication Type]",
            "retmax": str(max(1, min(max_results, 10))),
            "retmode": "json",
            "sort": "pub_date",
            "datetype": "pdat",
            "reldate": "1825",  # 近 5 年（365 * 5）
        }
        r = httpx.get(PUBMED_ESEARCH, params=params, timeout=8.0)
        if r.status_code != 200:
            return []
        ids = (r.json().get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return []

        # 步驟 2：esummary 拿 metadata
        sr = httpx.get(
            PUBMED_ESUMMARY,
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            timeout=8.0,
        )
        if sr.status_code != 200:
            return []
        result = sr.json().get("result") or {}
        out = []
        for pmid in ids:
            meta = result.get(pmid) or {}
            if not meta:
                continue
            authors = meta.get("authors") or []
            first_author = (authors[0].get("name") if authors else "") or ""
            year = (meta.get("pubdate") or "")[:4]
            out.append({
                "pmid": pmid,
                "title": meta.get("title") or "",
                "authors": first_author + (" 等" if len(authors) > 1 else ""),
                "year": year,
                "journal": meta.get("source") or "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return out
    except Exception as e:
        logger.warning("pubmed_search 失敗（%s），回傳空 list", type(e).__name__)
        return []


# ── 疾病問答（在已查詢的疾病脈絡下追問） ──────────────────────
# 前端「對話式」UI 會在使用者點開某個疾病後，繼續問追加問題。
# 把已快取的 disease 結構塞進 system prompt 當脈絡，回答更聚焦。

_DISEASE_CHAT_ROLE = (
    "【本次對話情境】\n"
    "你是 MD.Piece 平台的疾病衛教助手，正在跟一位民眾針對「{disease_name}」這個疾病做進一步討論。\n"
    "目前你已經整理過這個疾病的基礎資料（下方 JSON 即為脈絡），請以這份資料為基礎回答使用者的追問。\n\n"
    "【脈絡資料】\n{context_json}\n\n"
    "情境專屬規則（憲法之外）：\n"
    "1. 回覆長度 80~250 字為主，過長要分段\n"
    "2. 若使用者問的是脈絡資料**沒涵蓋**的細節（例如某個少見副作用、某個地區的盛行率）：\n"
    "   可以根據常識補充，但要明確說「這是一般性說明，個案請問醫師」\n"
    "3. 若涉及具體用藥劑量、檢驗數值判讀、是否該停藥 — 一律回「請與您的主治醫師確認」\n"
    "4. 若使用者描述的症狀符合 red_flags（緊急訊號）：第一句直接建議就醫或撥 119\n"
    "5. 不要捏造文獻；如果引用研究，只能說「相關研究顯示」這類概略陳述"
)


def disease_chat(
    disease_context: dict,
    user_message: str,
    history: list | None = None,
    patient_context: Optional[PatientContext] = None,
) -> str:
    """在已知疾病脈絡下回答追問。disease_context 是 disease_reference 的 row（dict）。"""
    name = disease_context.get("name_zh") or disease_context.get("name_en") or "該疾病"
    # 只挑必要欄位塞進 prompt，避免 token 爆掉（references 不需要進對話脈絡）
    slim = {k: disease_context.get(k) for k in (
        "name_zh", "name_en", "icd10_code", "overview",
        "causes", "symptoms", "common_medications", "treatments",
        "complications", "prognosis", "self_care", "red_flags",
    )}
    role = _DISEASE_CHAT_ROLE.format(
        disease_name=name,
        context_json=json.dumps(slim, ensure_ascii=False),
    )
    # 對話式追問用 examples 幫助穩定語氣；單則回覆短，token 預算夠
    system = build_patient_facing_system(role, patient_context=patient_context)
    return call_claude(system, user_message, history=history, max_tokens=900)

