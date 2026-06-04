"""名人健康新聞：用 LLM 從 RSS 抽取「名人 × 疾病 × 事件性質」，
做病人友善的軟性框架，並關聯到既有衛教文章。

設計守則（違反就是踩雷，必讀）：
1. 只用「公開報導且當事人或經紀公司確認」— LLM 會過濾揣測性報導
2. 「病逝」單獨報導 → 改用「他生前推動 OO 觀念」的倡議框架
3. 一定附原始新聞連結（憲法第 2 條：可解釋）
4. 帶有「→ 相關衛教」按鈕，把流量導回 education_content
5. 結果快取 24h；LLM 失敗或解析失敗就回 []，不擋整個 daily 頁面
6. 預過濾（健康關鍵字、來源黑名單、揣測詞）省 LLM token
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from backend.services import education_content
from backend.services.llm_service import call_claude
from backend.utils.icd10 import ICD10_MAP

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 24 * 3600
MAX_STORIES = 4
# 單次 daily 請求最多跑 LLM 的新聞則數，避免 cold start（serverless 沒 warm cache）
# 時 latency 飆到不可接受。預過濾後通常 5 則內就能撈到 1–2 個名人故事；
# subsequent warm 請求會吃 link-key 快取，幾乎不會撞到這個 cap。
MAX_LLM_CALLS_PER_REQUEST = 5

# 預過濾：只有提到健康關鍵字的新聞才送 LLM，省 token
_HEALTH_KEYWORDS = (
    "癌", "腫瘤", "化療", "放療", "手術", "確診", "罹",
    "病逝", "病情", "治療", "抗病", "中風", "心臟病",
    "糖尿病", "高血壓", "失智", "憂鬱", "焦慮", "病魔",
    "病榻", "康復", "痊癒", "罹病", "罹癌", "分享病情",
    "肺炎", "腎臟", "腎臟病", "洗腎", "肝硬化", "癲癇",
    "硬化症", "巴金森", "帕金森", "漸凍",
)

# 來源黑名單：官方公告不會有名人，連看都不用看
_SKIP_SOURCE_HINTS = ("mohw.gov.tw", "cdc.gov.tw", "nhi.gov.tw", "hpa.gov.tw")

# 揣測詞：包含這些一律不送 LLM（LLM 還會再過一次，雙保險）
_RUMOR_KEYWORDS = ("傳出", "驚傳", "疑似", "傳言")

# link -> {extracted_at, story or None}
_cache: dict[str, dict] = {}


_EXTRACT_PROMPT = """你是嚴謹的醫療新聞編輯。下面是一則新聞，請判斷它是否屬於「具名公眾人物 × 慢性病或公衛議題」的衛教延伸題材。

新聞標題：{title}
新聞摘要：{summary}

判斷準則：
- 必須提到具名公眾人物（藝人、政治人物、運動員、企業家、作家）
- 該人物的健康狀況需在報導中明確且公開（揣測詞「疑似」「傳出」「驚傳」一律不算）
- 涉及疾病應為慢性病或公衛議題，可對接衛教文章

如果三項都符合，回 JSON：
{{
  "is_celebrity_health": true,
  "person": "人物姓名（用台灣慣用譯名）",
  "disease_keyword": "疾病關鍵字（中文，使用台灣常見講法）",
  "event_type": "確診 | 治療中 | 康復 | 倡議推廣",
  "soft_framing": "80 字以內的同理引導句。事件若為『病逝』一律改框成『他生前推動的 OO 觀念』，禁止恐嚇式語氣，禁止假保證"
}}

否則回：
{{"is_celebrity_health": false}}

請只回 JSON，不要任何說明文字。"""


def _parse_json(raw: str) -> dict | None:
    """容錯把 LLM 輸出當 JSON 解析。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not text.startswith("{"):
        l, r = text.find("{"), text.rfind("}")
        if l != -1 and r > l:
            text = text[l : r + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _should_consider(item: dict) -> bool:
    """便宜過濾：明顯不可能命中的，連 LLM 都不要叫。"""
    link = (item.get("link") or "").lower()
    if any(h in link for h in _SKIP_SOURCE_HINTS):
        return False
    source = (item.get("source") or "").lower()
    if any(h in source for h in _SKIP_SOURCE_HINTS):
        return False
    text = (item.get("title") or "") + " " + (item.get("summary") or "")
    if not any(k in text for k in _HEALTH_KEYWORDS):
        return False
    if any(r in text for r in _RUMOR_KEYWORDS):
        return False
    return True


def _build_reverse_icd10_map() -> dict[str, str]:
    """疾病中文名 → ICD-10 prefix，給 LLM 抽出的 disease_keyword 反查衛教文章。"""
    reverse: dict[str, str] = {}
    for code, name in ICD10_MAP.items():
        reverse[name] = code
        # 抓括號前的主名 (e.g. "腦梗塞（中風）" → "腦梗塞" + "中風")
        m = re.match(r"^(.*?)（(.+?)）", name)
        if m:
            reverse[m.group(1).strip()] = code
            reverse[m.group(2).strip()] = code
    # 常見別名手動補
    aliases = {
        "糖尿病": "E11", "高血糖": "E11",
        "高血壓": "I10",
        "心肌梗塞": "I25", "冠心病": "I25", "心臟病": "I25",
        "中風": "I63", "腦中風": "I63", "腦梗塞": "I63",
        "氣喘": "J45",
        "肺阻塞": "J44", "COPD": "J44",
        "失智": "G30", "失智症": "G30", "阿茲海默": "G30", "阿茲海默症": "G30",
        "巴金森": "G20", "帕金森": "G20", "巴金森氏症": "G20",
        "漸凍人": "G12", "漸凍症": "G12",
        "癲癇": "G40",
        "偏頭痛": "G43",
        "憂鬱": "F32", "憂鬱症": "F32", "重鬱症": "F32",
        "焦慮症": "F41", "恐慌症": "F41",
        "乳癌": "C50",
        "肺癌": "C34", "肺腺癌": "C34",
        "大腸癌": "C18", "結腸癌": "C18", "直腸癌": "C18",
        "腎臟病": "N18", "腎衰竭": "N18", "洗腎": "N18", "慢性腎臟病": "N18",
        "紅斑性狼瘡": "M32", "狼瘡": "M32", "SLE": "M32",
        "類風濕": "M06", "類風濕性關節炎": "M06",
        "痛風": "M10",
        "骨鬆": "M81", "骨質疏鬆": "M81",
        "硬皮症": "M34",
        "重症肌無力": "G70",
        "甲狀腺亢進": "E05", "甲亢": "E05",
        "甲狀腺低下": "E03",
    }
    reverse.update(aliases)
    return reverse


_REVERSE_ICD10 = _build_reverse_icd10_map()


def _map_disease_to_icd10(keyword: str) -> str | None:
    """疾病關鍵字 → ICD-10 三碼前綴。先精確、再子字串。"""
    if not keyword:
        return None
    if keyword in _REVERSE_ICD10:
        return _REVERSE_ICD10[keyword]
    for name, code in _REVERSE_ICD10.items():
        if name and (name in keyword or keyword in name):
            return code
    return None


def _related_articles(icd10_prefix: str | None, limit: int = 3) -> list[dict]:
    if not icd10_prefix:
        return []
    arts = education_content.list_articles(icd10=icd10_prefix)
    arts.sort(key=lambda a: (not a.featured, a.dimension or "z", a.slug))
    return [a.to_card() for a in arts[:limit]]


def _extract_one(item: dict) -> dict | None:
    """對單則新聞跑一次 LLM 抽取；非名人健康類回 None。"""
    title = (item.get("title") or "").strip()
    summary = (item.get("summary") or "").strip()
    if not title:
        return None

    prompt = _EXTRACT_PROMPT.format(title=title, summary=summary or "(無摘要)")
    try:
        raw = call_claude(
            "你是嚴謹的醫療新聞編輯，只回 JSON。",
            prompt,
            max_tokens=400,
        )
    except Exception as e:
        logger.warning("celebrity_health: LLM 抽取失敗 %s", e)
        return None

    parsed = _parse_json(raw)
    if not parsed or not parsed.get("is_celebrity_health"):
        return None

    person = (parsed.get("person") or "").strip()
    disease_keyword = (parsed.get("disease_keyword") or "").strip()
    event_type = (parsed.get("event_type") or "").strip()
    soft_framing = (parsed.get("soft_framing") or "").strip()
    if not person or not disease_keyword or not soft_framing:
        return None

    icd10 = _map_disease_to_icd10(disease_keyword)
    return {
        "person": person,
        "disease_keyword": disease_keyword,
        "icd10_prefix": icd10,
        "disease_name": ICD10_MAP.get(icd10) if icd10 else None,
        "event_type": event_type,
        "soft_framing": soft_framing,
        "source_title": title,
        "source_summary": summary,
        "source_link": item.get("link") or "",
        "source_published": item.get("published") or "",
        "source_feed": item.get("source") or "",
        "related_articles": _related_articles(icd10),
    }


def extract_celebrity_stories(news_items: list[dict], limit: int = MAX_STORIES) -> list[dict]:
    """從新聞列表中找出名人健康故事，附軟性框架與相關衛教文章。

    流程：
    1. 預過濾（黑名單、健康關鍵字、揣測詞）
    2. 24h link-key 快取命中直接用
    3. 沒命中才跑 LLM 抽取，並把結果（含負結果）寫回快取
    4. 單次請求最多跑 ``MAX_LLM_CALLS_PER_REQUEST`` 次 LLM
    """
    if os.getenv("CELEBRITY_HEALTH_ENABLED", "true").lower() in ("0", "false", "off", "no"):
        return []

    stories: list[dict] = []
    now = time.time()
    llm_calls = 0

    for item in news_items:
        if len(stories) >= limit:
            break

        link = item.get("link") or ""

        if link:
            cached = _cache.get(link)
            if cached and (now - cached["extracted_at"]) < CACHE_TTL_SECONDS:
                if cached["story"]:
                    stories.append(cached["story"])
                continue

        if not _should_consider(item):
            if link:
                _cache[link] = {"extracted_at": now, "story": None}
            continue

        if llm_calls >= MAX_LLM_CALLS_PER_REQUEST:
            break
        llm_calls += 1

        story = _extract_one(item)
        if link:
            _cache[link] = {"extracted_at": now, "story": story}
        if story:
            stories.append(story)

    return stories


def reset_cache() -> None:
    _cache.clear()
