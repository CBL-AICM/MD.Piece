from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import logging

from backend.services.knowledge_analysis import (
    get_disease_profile,
    compare_across_diseases,
    compare_by_category,
    get_education_priorities,
    get_comprehension_distribution,
)
from backend.services.llm_service import call_claude
from backend.services import education_content
from backend.services import news_feed
from backend.utils.icd10 import (
    ICD10_MAP,
    KNOWLEDGE_DIMENSIONS,
    COMPREHENSION_LEVELS,
    CHRONIC_DISEASE_CATEGORIES,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 六大維度衛教 prompt 模板 ──────────────────────────────

DIMENSION_PROMPTS = {
    "disease_awareness": (
        "請用最溫暖、最淺顯易懂的方式，向一位剛被診斷為「{disease}」的患者說明：\n"
        "1. 這個疾病是什麼？用生活化的比喻讓他理解\n"
        "2. 目前主流的治療方式有哪些？成功率如何？\n"
        "3. 大概的治療費用範圍（台灣健保涵蓋哪些）\n"
        "4. 治療風險——但請強調現代醫學已經大幅降低這些風險\n\n"
        "語氣要求：像一位溫柔的朋友在跟你聊天，不要用嚇人的醫學術語。"
        "讓患者感受到「這是可以被好好管理的」。給予治癒的期待與信心。"
    ),
    "symptom_recognition": (
        "請用簡單易懂的方式，教一位「{disease}」患者如何辨認自己的症狀：\n"
        "1. 這個病常見的症狀有哪些？用身體感受來描述\n"
        "2. 哪些是「正常反應」不需要太擔心？\n"
        "3. 哪些訊號代表需要多注意？\n"
        "4. 簡單的自我觀察小技巧\n\n"
        "語氣要求：不要讓患者變得焦慮。重點是「了解自己的身體」，"
        "像是學會聽懂身體的語言，而不是時時刻刻在擔心。"
    ),
    "medication_knowledge": (
        "請用最親切的方式，向一位「{disease}」患者說明用藥知識：\n"
        "1. 常用的藥物有哪些？每種藥在做什麼？用簡單比喻\n"
        "2. 可能的副作用——但強調大部分人都能適應\n"
        "3. 吃藥的注意事項（飯前飯後、不能配什麼）\n"
        "4. 「吃這些藥不可怕」——為什麼按時服藥是保護自己\n\n"
        "語氣要求：很多患者害怕吃藥。請讓他們理解藥物是「幫助身體的好朋友」，"
        "不是負擔。用鼓勵的口吻。"
    ),
    "self_management": (
        "請用輕鬆實用的方式，教一位「{disease}」患者如何調整生活：\n"
        "1. 飲食上可以怎麼調整？給具體的建議，不要只說「少吃」\n"
        "2. 運動建議——適合什麼運動？一天多久？\n"
        "3. 作息與壓力管理的小技巧\n"
        "4. 日常生活中簡單就能做到的好習慣\n\n"
        "語氣要求：不是在「限制」生活，而是在「升級」生活品質。"
        "讓患者覺得這些改變是輕鬆的、可以一步步來的。"
    ),
    "emergency_response": (
        "請用清楚但不恐嚇的方式，教一位「{disease}」患者什麼時候需要緊急就醫：\n"
        "1. 哪些症狀出現時應該立刻去急診？（列出明確的警訊）\n"
        "2. 哪些情況可以先觀察、隔天看門診？\n"
        "3. 緊急時的簡單應對步驟\n"
        "4. 平時可以準備什麼（緊急聯絡卡、藥物清單）\n\n"
        "語氣要求：這是「安全準備」不是「等著出事」。"
        "像教防災知識一樣，知道了反而更安心。"
    ),
    "complication_awareness": (
        "請用溫和誠實的方式，向一位「{disease}」患者說明長期可能的併發症：\n"
        "1. 如果沒有好好管理，長期可能影響哪些器官？\n"
        "2. 但是——好好管理的話，這些風險可以大幅降低多少？\n"
        "3. 定期追蹤檢查的建議（多久檢查一次、查什麼）\n"
        "4. 給予希望：現代醫學讓這個疾病的預後越來越好\n\n"
        "語氣要求：誠實但不嚇人。重點是「知道風險，才能避開風險」。"
        "結尾一定要給予正面力量和信心。讓患者知道：好好管理，"
        "生活品質可以跟一般人一樣好。"
    ),
}

SYSTEM_PROMPT = (
    "你是 MD.Piece 平台的衛教助手，專門為慢性病患者提供溫暖、易懂的健康教育。\n"
    "你的核心原則：\n"
    "1. 安撫為先——患者已經夠擔心了，你的任務是讓他們安心\n"
    "2. 淺顯易懂——用生活化的語言，避免專業術語；如果必須用，要立刻解釋\n"
    "3. 給予希望——每篇文章都要讓患者感受到「這是可以管理好的」\n"
    "4. 實用具體——給可以立刻行動的建議，不是空泛的「多注意」\n"
    "5. 台灣情境——使用台灣的醫療體系、健保制度、飲食習慣作為背景\n\n"
    "回覆格式：使用 Markdown，用標題分段，適當加入 emoji 讓文章更親切。"
    "長度控制在 800-1200 字之間。"
)


class EducationRequest(BaseModel):
    icd10_code: Optional[str] = None
    dimension: Optional[str] = None
    topic: Optional[str] = None


# ── 衛教文章生成（Claude API）────────────────────────────


GENERIC_TOPIC_PROMPT = (
    "請以 MD.Piece 衛教助手的身分，為一位患者撰寫主題為「{topic}」的衛教文章。\n\n"
    "撰稿要求：\n"
    "1. 用最溫暖、最淺顯易懂的語氣，像朋友在跟你聊天\n"
    "2. 必要的醫學名詞要立刻用括號或比喻解釋\n"
    "3. 結構清楚：先講「這是什麼」，再講「為什麼重要」，最後給「可以怎麼做」\n"
    "4. 重點放在安心與實用——讓患者讀完覺得「我知道該做什麼了」\n"
    "5. 適當使用 emoji 讓文章更親切\n"
    "6. 用台灣的醫療制度、健保、飲食習慣作為背景\n"
    "7. 文末提醒：詳細治療仍以主治醫師判斷為準\n\n"
    "回覆格式：使用 Markdown，分段加標題，長度控制在 600–1000 字。"
)


@router.post("/generate")
def generate_education(body: EducationRequest):
    """生成衛教文章。

    兩種模式（自動切換）：
    1. ICD-10 + 六大維度：套用該維度的細緻 prompt 模板
    2. 自由主題（topic）：給非疾病類的章節用，用通用 prompt
    """
    # 模式 1：ICD-10 + dimension
    if body.icd10_code and body.dimension and body.dimension in DIMENSION_PROMPTS:
        prefix = body.icd10_code[:3]
        disease_name = ICD10_MAP.get(prefix)
        if not disease_name:
            raise HTTPException(status_code=400, detail=f"不支援的 ICD-10 代碼: {body.icd10_code}")

        prompt_template = DIMENSION_PROMPTS[body.dimension]
        user_message = prompt_template.format(disease=disease_name)

        try:
            content = call_claude(SYSTEM_PROMPT, user_message)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise HTTPException(status_code=500, detail="衛教內容生成失敗，請稍後再試")

        return {
            "icd10_code": prefix,
            "disease_name": disease_name,
            "dimension": body.dimension,
            "dimension_label": KNOWLEDGE_DIMENSIONS[body.dimension],
            "content": content,
        }

    # 模式 2：自由主題（用於 SLE、RA、營養、急救等非疾病百科的書本章節）
    topic = body.topic or body.dimension
    if not topic:
        raise HTTPException(
            status_code=400,
            detail="請提供 icd10_code+dimension（疾病百科）或 topic（一般章節）",
        )

    user_message = GENERIC_TOPIC_PROMPT.format(topic=topic)
    try:
        content = call_claude(SYSTEM_PROMPT, user_message)
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise HTTPException(status_code=500, detail="衛教內容生成失敗，請稍後再試")

    return {
        "topic": topic,
        "content": content,
    }


@router.get("/dimensions")
def list_education_dimensions():
    """列出六大衛教維度"""
    return {
        "dimensions": [
            {"key": k, "label": v} for k, v in KNOWLEDGE_DIMENSIONS.items()
        ]
    }


@router.get("/diseases")
def list_supported_diseases():
    """列出所有支援衛教的疾病"""
    diseases = []
    for code, name in ICD10_MAP.items():
        category = None
        for cat, codes in CHRONIC_DISEASE_CATEGORIES.items():
            if code in codes:
                category = cat
                break
        diseases.append({"icd10": code, "name": name, "category": category or "未分類"})
    return {"diseases": diseases}


# ── 原有靜態衛教 ────────────────────────────────────────


@router.get("/articles")
def get_articles(
    icd10_code: str = "",
    dimension: str = "",
    tag: str = "",
    featured: bool = False,
):
    """列出 content/education/ 下的 Markdown 文章（卡片版，不含 body）"""
    items = education_content.list_articles(
        icd10=icd10_code or None,
        dimension=dimension or None,
        tag=tag or None,
        featured_only=featured,
    )
    return {"articles": [a.to_card() for a in items]}


@router.get("/articles/featured")
def get_featured_articles(limit: int = 5):
    """首頁推送：精選文章（標記 featured: true 的）"""
    items = education_content.list_articles(featured_only=True)
    return {"articles": [a.to_card() for a in items[:limit]]}


DAILY_CATEGORIES = ("disease", "quick_tip", "news")

# 沒標 category 的舊文章依 slug 前綴自動歸類，避免每日故事池子太小造成重複。
_QUICK_TIP_PREFIXES = (
    "symptoms-", "emergency-", "medications-", "labs-",
    "hydration-", "nutrition-", "exercise-", "sleep-", "prevent-",
)


def _auto_category(article) -> str:
    cat = (article.category or "").lower()
    if cat in DAILY_CATEGORIES:
        return cat
    slug = (article.slug or "").lower()
    for prefix in _QUICK_TIP_PREFIXES:
        if slug.startswith(prefix):
            return "quick_tip"
    return "disease"


@router.get("/articles/daily")
def get_daily_article(days: int = 7):
    """每日故事：每天依分類各推一篇（疾病故事 / 健康快訊 / 最新資訊），加上近 N 天歷程與外部新聞。

    - 三個分類各自輪播；若某分類沒有文章，該欄位回 null。
    - news 分類除了 markdown 文章，另外從 RSS 補幾則最新醫療資訊。
    - 同一天回傳同一組，不需要儲存狀態。
    """
    from datetime import date, timedelta

    all_articles = education_content.list_articles()
    if not all_articles:
        return {
            "today": {c: None for c in DAILY_CATEGORIES},
            "archive": [],
            "news_feed": news_feed.fetch_news(limit=6),
        }

    by_category: dict[str, list] = {c: [] for c in DAILY_CATEGORIES}
    for a in all_articles:
        by_category[_auto_category(a)].append(a)

    for cat in by_category:
        by_category[cat].sort(key=lambda a: a.slug)

    def pick_for(cat: str, d: "date"):
        pool = by_category.get(cat) or []
        if not pool:
            return None
        return pool[d.toordinal() % len(pool)]

    feed_items = news_feed.fetch_news(limit=6)

    def news_card_from_feed(d: "date", offset: int = 0) -> Optional[dict]:
        """把 RSS item 包成 article-shaped dict，當作那天的 news 故事。"""
        if not feed_items:
            return None
        item = feed_items[offset % len(feed_items)]
        title = item.get("title") or "（最新公告）"
        summary = item.get("summary") or ""
        link = item.get("link") or ""
        body_lines = [summary] if summary else []
        if link:
            body_lines.append("\n[原文連結]({}）".format(link).replace("）", ")"))
        return {
            "slug": "news-feed-" + d.isoformat() + "-" + str(offset),
            "title": title,
            "summary": summary[:140],
            "category": "news",
            "tags": ["衛福部公告"],
            "sources": [link] if link else [],
            "body": "\n\n".join(body_lines).strip(),
            "pushed_on": d.isoformat(),
            "external_link": link,
        }

    today = date.today()
    today_picks: dict[str, Any] = {}
    for cat in DAILY_CATEGORIES:
        a = pick_for(cat, today)
        if a is None:
            # news 分類沒有 markdown 文章時，退回今日 RSS 第一則
            if cat == "news":
                today_picks[cat] = news_card_from_feed(today, today.toordinal())
            else:
                today_picks[cat] = None
            continue
        full = a.to_full()
        full["pushed_on"] = today.isoformat()
        today_picks[cat] = full

    days = max(1, min(days, 30))
    archive = []
    for i in range(1, days):
        d = today - timedelta(days=i)
        day_entry = {"date": d.isoformat(), "items": {}}
        for cat in DAILY_CATEGORIES:
            a = pick_for(cat, d)
            if a is None:
                if cat == "news":
                    # 歷程的 news 也用 RSS 後續項目佔位（offset = i）
                    day_entry["items"][cat] = news_card_from_feed(d, i)
                else:
                    day_entry["items"][cat] = None
            else:
                card = a.to_card()
                card["pushed_on"] = d.isoformat()
                day_entry["items"][cat] = card
        archive.append(day_entry)

    return {
        "today": today_picks,
        "archive": archive,
        "news_feed": feed_items,
    }


@router.get("/articles/{slug}")
def get_article(slug: str):
    """取得完整文章內容（含 Markdown body 與來源清單）"""
    article = education_content.get_article(slug)
    if not article:
        raise HTTPException(status_code=404, detail=f"找不到文章: {slug}")
    return article.to_full()


@router.post("/articles/reload")
def reload_articles():
    """強制重新讀取 Markdown 檔（部署後不需手動呼叫，重啟即可）"""
    count = education_content.reload_articles()
    return {"reloaded": count}


@router.get("/idle-hints")
def get_idle_hints():
    return {"hints": []}


# ── 慢性病知識理解度分析 ──────────────────────────────


@router.get("/knowledge-analysis/dimensions")
def list_dimensions():
    """列出所有知識維度與理解程度等級定義"""
    return {
        "dimensions": KNOWLEDGE_DIMENSIONS,
        "comprehension_levels": COMPREHENSION_LEVELS,
        "categories": list(CHRONIC_DISEASE_CATEGORIES.keys()),
    }


@router.get("/knowledge-analysis/disease/{icd10_code}")
def analyze_disease(icd10_code: str):
    """取得單一慢性病的知識理解度剖面"""
    profile = get_disease_profile(icd10_code)
    if not profile:
        return {"error": f"無 {icd10_code} 的基準數據", "available_codes": _available_codes()}
    return profile


@router.get("/knowledge-analysis/compare")
def compare_diseases(
    codes: Optional[str] = Query(None, description="ICD-10 代碼，逗號分隔（空白=全部）"),
):
    """跨慢性病知識理解度比較"""
    code_list = None
    if codes:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
    return compare_across_diseases(code_list)


@router.get("/knowledge-analysis/by-category")
def analyze_by_category():
    """按疾病分類群組比較知識理解度差異"""
    return compare_by_category()


@router.get("/knowledge-analysis/priorities")
def education_priorities(
    top_n: int = Query(10, description="顯示前 N 個最需加強的衛教項目"),
):
    """找出最需要加強衛教的疾病×維度組合（缺口最大者優先）"""
    return get_education_priorities(top_n)


@router.get("/knowledge-analysis/distribution")
def comprehension_distribution():
    """各理解程度等級的整體分佈統計"""
    return get_comprehension_distribution()


def _available_codes():
    from backend.utils.icd10 import KNOWLEDGE_BASELINE
    return list(KNOWLEDGE_BASELINE.keys())
