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
    get_related_icd10_codes,
    get_category_for_code,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── i18n: 衛教路由的雙語字串 ─────────────────────────────
# 所有面向使用者的字串（prompts、錯誤訊息、維度標籤、共病推送理由）
# 都收在這裡，由 ?lang= 決定回哪一份。frontend i18n 字典只負責 UI 文案；
# 後端產出的內容（衛教文章、API 訊息、Claude prompt）改由這份 LANG_PACK 提供。

DEFAULT_LANG = "zh-TW"
SUPPORTED_LANGS = ("zh-TW", "en")


def _normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return DEFAULT_LANG
    if lang in SUPPORTED_LANGS:
        return lang
    base = lang.split("-")[0].lower()
    if base == "en":
        return "en"
    if base == "zh":
        return "zh-TW"
    return DEFAULT_LANG


# ── 六大維度衛教 prompt 模板 ──────────────────────────────

DIMENSION_PROMPTS = {
    "zh-TW": {
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
    },
    "en": {
        "disease_awareness": (
            "Speak warmly and in plain language to a patient newly diagnosed with \"{disease}\":\n"
            "1. What is this condition? Use an everyday analogy so it clicks.\n"
            "2. What are today's mainstream treatments and how well do they work?\n"
            "3. Roughly what does treatment cost (and what does Taiwan's NHI cover)?\n"
            "4. Treatment risks — but underline how much modern medicine has reduced them.\n\n"
            "Tone: a gentle friend chatting with them; avoid scary medical jargon. "
            "Leave them feeling \"this can be managed well.\" Offer hope and confidence."
        ),
        "symptom_recognition": (
            "In plain language, teach a patient with \"{disease}\" how to recognize their own symptoms:\n"
            "1. What are the common symptoms? Describe them as bodily sensations.\n"
            "2. Which are \"normal\" and don't need worry?\n"
            "3. Which signals deserve closer attention?\n"
            "4. Simple self-observation tips.\n\n"
            "Tone: don't make them anxious. The point is \"learn your body's language,\" "
            "not constant worry."
        ),
        "medication_knowledge": (
            "Walk a patient with \"{disease}\" through their medications, gently:\n"
            "1. What drugs are commonly used and what does each one do? Use simple analogies.\n"
            "2. Possible side effects — but emphasize most people adjust fine.\n"
            "3. How to take them (with/without food, what to avoid combining).\n"
            "4. \"These meds aren't scary\" — why on-time dosing is self-protection.\n\n"
            "Tone: many patients fear medication. Help them see meds as \"helpful friends to the body,\" "
            "not a burden. Be encouraging."
        ),
        "self_management": (
            "Give a patient with \"{disease}\" practical, easy-going lifestyle guidance:\n"
            "1. Diet tweaks — be specific, don't just say \"eat less.\"\n"
            "2. Exercise — what kind, how long per day?\n"
            "3. Sleep and stress-management tips.\n"
            "4. Simple daily habits that anyone can adopt.\n\n"
            "Tone: it's not about \"restricting\" life, it's about \"upgrading\" quality of life. "
            "Make these changes feel light and gradual."
        ),
        "emergency_response": (
            "Clearly (but without scare-tactics) teach a patient with \"{disease}\" when to seek urgent care:\n"
            "1. Which symptoms mean go to the ER right now? (List concrete red flags.)\n"
            "2. Which can wait and see a clinic the next day?\n"
            "3. Simple emergency response steps.\n"
            "4. What to prepare in advance (emergency card, medication list).\n\n"
            "Tone: this is \"safety preparedness,\" not \"waiting for trouble.\" "
            "Like disaster-prep knowledge — knowing actually makes you calmer."
        ),
        "complication_awareness": (
            "Gently and honestly explain potential long-term complications of \"{disease}\":\n"
            "1. If poorly managed, which organs could be affected long term?\n"
            "2. But — with good management, how much do these risks drop?\n"
            "3. Routine follow-up suggestions (how often, what to check).\n"
            "4. Hope: modern medicine keeps improving the prognosis of this condition.\n\n"
            "Tone: honest but not frightening. The point is \"know the risk to avoid the risk.\" "
            "Always end on positive empowerment and confidence — well-managed, "
            "their quality of life can be as good as anyone else's."
        ),
    },
}

SYSTEM_PROMPT = {
    "zh-TW": (
        "你是 MD.Piece 平台的衛教助手，專門為慢性病患者提供溫暖、易懂的健康教育。\n"
        "你的核心原則：\n"
        "1. 安撫為先——患者已經夠擔心了，你的任務是讓他們安心\n"
        "2. 淺顯易懂——用生活化的語言，避免專業術語；如果必須用，要立刻解釋\n"
        "3. 給予希望——每篇文章都要讓患者感受到「這是可以管理好的」\n"
        "4. 實用具體——給可以立刻行動的建議，不是空泛的「多注意」\n"
        "5. 台灣情境——使用台灣的醫療體系、健保制度、飲食習慣作為背景\n\n"
        "回覆格式：使用 Markdown，用標題分段，適當加入 emoji 讓文章更親切。"
        "長度控制在 800-1200 字之間。"
    ),
    "en": (
        "You are the health-education assistant of the MD.Piece platform, "
        "providing warm, easy-to-understand education for chronic-illness patients.\n"
        "Core principles:\n"
        "1. Reassure first — patients are already worried; your job is to settle them.\n"
        "2. Plain language — everyday wording, avoid jargon; if needed, define it on the spot.\n"
        "3. Offer hope — each article should leave the patient feeling \"this is manageable.\"\n"
        "4. Practical and concrete — actionable advice, not vague \"be careful.\"\n"
        "5. Taiwan context — use Taiwan's medical system, NHI coverage, and dietary habits as background.\n\n"
        "Format: Markdown with headings; use emoji sparingly to keep the tone warm. "
        "Aim for 800–1200 words."
    ),
}


class EducationRequest(BaseModel):
    icd10_code: Optional[str] = None
    dimension: Optional[str] = None
    topic: Optional[str] = None
    lang: Optional[str] = None


# ── 衛教文章生成（Claude API）────────────────────────────


GENERIC_TOPIC_PROMPT = {
    "zh-TW": (
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
    ),
    "en": (
        "As the MD.Piece health-education assistant, write a patient-facing article on \"{topic}\".\n\n"
        "Requirements:\n"
        "1. Warm, plain-language tone — like a friend chatting with them.\n"
        "2. Define any necessary medical term inline (in parentheses or via an analogy).\n"
        "3. Clear structure: \"what it is\" → \"why it matters\" → \"what you can do.\"\n"
        "4. Focus on reassurance and practicality — the reader should walk away thinking \"I know what to do now.\"\n"
        "5. Use emoji sparingly to keep the tone friendly.\n"
        "6. Use Taiwan's medical system, NHI coverage, and dietary norms as the background.\n"
        "7. End with the reminder: specific treatment decisions still rest with the patient's attending physician.\n\n"
        "Format: Markdown with section headings, 600–1000 words."
    ),
}

# 路由錯誤訊息與其他面向使用者的字串
MESSAGES = {
    "zh-TW": {
        "unknown_icd10": "不支援的 ICD-10 代碼: {code}",
        "claude_failed": "衛教內容生成失敗，請稍後再試",
        "missing_payload": "請提供 icd10_code+dimension（疾病百科）或 topic（一般章節）",
        "article_not_found": "找不到文章: {slug}",
        "baseline_missing": "無 {code} 的基準數據",
        "uncategorized": "未分類",
        "unknown_disease": "未知疾病",
        "reason_comorbidity": "與「{name}」常一起出現的共病",
        "reason_same_category": "同屬「{category}」的相關疾病",
        "reason_default": "建議一併了解的相關疾病",
    },
    "en": {
        "unknown_icd10": "Unsupported ICD-10 code: {code}",
        "claude_failed": "Failed to generate health-education content, please try again later",
        "missing_payload": "Please provide either icd10_code+dimension (disease entry) or topic (general chapter)",
        "article_not_found": "Article not found: {slug}",
        "baseline_missing": "No baseline data for {code}",
        "uncategorized": "Uncategorized",
        "unknown_disease": "Unknown condition",
        "reason_comorbidity": "Often co-occurs with \"{name}\"",
        "reason_same_category": "Related condition in the \"{category}\" group",
        "reason_default": "A related condition worth knowing about",
    },
}

# 知識維度標籤（KNOWLEDGE_DIMENSIONS）的英文對照
DIMENSION_LABELS_EN = {
    "disease_awareness": "Disease awareness (knowing your diagnosis)",
    "symptom_recognition": "Symptom recognition (spotting abnormal signs)",
    "medication_knowledge": "Medication knowledge (effects and side effects)",
    "self_management": "Self-management (diet, exercise, lifestyle)",
    "emergency_response": "Emergency response (when to seek care)",
    "complication_awareness": "Complication awareness (long-term risks)",
}

# 慢性病分類群組（CHRONIC_DISEASE_CATEGORIES）的英文對照
CATEGORY_LABELS_EN = {
    "代謝疾病": "Metabolic diseases",
    "心血管疾病": "Cardiovascular diseases",
    "呼吸系統疾病": "Respiratory diseases",
    "消化系統疾病": "Digestive diseases",
    "肌肉骨骼疾病": "Musculoskeletal diseases",
    "腎臟疾病": "Kidney diseases",
    "神經退化疾病": "Neurodegenerative diseases",
    "精神疾病": "Mental health",
    "腫瘤追蹤": "Oncology follow-up",
}

COMPREHENSION_LEVELS_EN = {
    0: "No understanding",
    1: "Heard of it but unclear",
    2: "Basic understanding",
    3: "Clear understanding, can explain",
    4: "Can apply independently and teach others",
}


def _msg(lang: str, key: str, **kwargs) -> str:
    pack = MESSAGES.get(lang) or MESSAGES[DEFAULT_LANG]
    template = pack.get(key) or MESSAGES[DEFAULT_LANG][key]
    return template.format(**kwargs) if kwargs else template


def _localize_dimensions(lang: str) -> dict[str, str]:
    if lang == "en":
        return dict(DIMENSION_LABELS_EN)
    return dict(KNOWLEDGE_DIMENSIONS)


def _localize_category(category: Optional[str], lang: str) -> Optional[str]:
    if not category:
        return None
    if lang == "en":
        return CATEGORY_LABELS_EN.get(category, category)
    return category


def _localize_comprehension(lang: str) -> dict[int, str]:
    if lang == "en":
        return dict(COMPREHENSION_LEVELS_EN)
    return dict(COMPREHENSION_LEVELS)


@router.post("/generate")
def generate_education(body: EducationRequest):
    """生成衛教文章。

    兩種模式（自動切換）：
    1. ICD-10 + 六大維度：套用該維度的細緻 prompt 模板
    2. 自由主題（topic）：給非疾病類的章節用，用通用 prompt
    """
    lang = _normalize_lang(body.lang)
    sys_prompt = SYSTEM_PROMPT[lang]
    dim_prompts = DIMENSION_PROMPTS[lang]

    # 模式 1：ICD-10 + dimension
    if body.icd10_code and body.dimension and body.dimension in dim_prompts:
        prefix = body.icd10_code[:3]
        disease_name = ICD10_MAP.get(prefix)
        if not disease_name:
            raise HTTPException(
                status_code=400,
                detail=_msg(lang, "unknown_icd10", code=body.icd10_code),
            )

        user_message = dim_prompts[body.dimension].format(disease=disease_name)

        try:
            content = call_claude(sys_prompt, user_message)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise HTTPException(status_code=500, detail=_msg(lang, "claude_failed"))

        return {
            "icd10_code": prefix,
            "disease_name": disease_name,
            "dimension": body.dimension,
            "dimension_label": _localize_dimensions(lang)[body.dimension],
            "lang": lang,
            "content": content,
        }

    # 模式 2：自由主題（用於 SLE、RA、營養、急救等非疾病百科的書本章節）
    topic = body.topic or body.dimension
    if not topic:
        raise HTTPException(status_code=400, detail=_msg(lang, "missing_payload"))

    user_message = GENERIC_TOPIC_PROMPT[lang].format(topic=topic)
    try:
        content = call_claude(sys_prompt, user_message)
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise HTTPException(status_code=500, detail=_msg(lang, "claude_failed"))

    return {
        "topic": topic,
        "lang": lang,
        "content": content,
    }


@router.get("/dimensions")
def list_education_dimensions(lang: str = Query(DEFAULT_LANG)):
    """列出六大衛教維度"""
    L = _normalize_lang(lang)
    labels = _localize_dimensions(L)
    return {
        "lang": L,
        "dimensions": [
            {"key": k, "label": labels.get(k, KNOWLEDGE_DIMENSIONS[k])}
            for k in KNOWLEDGE_DIMENSIONS.keys()
        ],
    }


@router.get("/diseases")
def list_supported_diseases(lang: str = Query(DEFAULT_LANG)):
    """列出所有支援衛教的疾病"""
    L = _normalize_lang(lang)
    diseases = []
    for code, name in ICD10_MAP.items():
        category = None
        for cat, codes in CHRONIC_DISEASE_CATEGORIES.items():
            if code in codes:
                category = cat
                break
        diseases.append({
            "icd10": code,
            "name": name,
            "category": _localize_category(category, L) or _msg(L, "uncategorized"),
        })
    return {"lang": L, "diseases": diseases}


@router.get("/related")
def list_related_diseases(
    codes: str = Query("", description="病患已登錄的 ICD-10 代碼，逗號分隔"),
    limit: int = Query(6, ge=1, le=20, description="最多回傳幾個相關疾病"),
    lang: str = Query(DEFAULT_LANG),
):
    """病患登錄主疾病後，自動推送臨床上常見的相關疾病與其衛教文章。

    產生規則：
    1. 從 COMORBIDITY_MAP 取共病（如糖尿病 → 高血壓、腎病變、心血管）
    2. 從 CHRONIC_DISEASE_CATEGORIES 取同分類疾病
    3. 排除病患已登錄的疾病、保留首次出現順序

    每個相關疾病會附上 content/education/ 內已審稿的文章卡片，
    讓前端可以直接顯示「為您推送的相關衛教」。
    """
    L = _normalize_lang(lang)
    own = [c.strip() for c in (codes or "").split(",") if c.strip()]
    related_prefixes = get_related_icd10_codes(own)[:limit]

    own_prefixes = {c[:3].upper() for c in own}
    items: list[dict[str, Any]] = []
    for prefix in related_prefixes:
        articles = education_content.list_articles(icd10=prefix, lang=L)
        articles.sort(key=lambda a: (not a.featured, a.dimension or "z", a.slug))
        items.append({
            "icd10": prefix,
            "name": ICD10_MAP.get(prefix, _msg(L, "unknown_disease")),
            "category": _localize_category(get_category_for_code(prefix), L),
            "reason": _related_reason(prefix, own, L),
            "articles": [a.to_card() for a in articles[:3]],
            "article_count": len(articles),
        })

    return {
        "lang": L,
        "source_codes": sorted(own_prefixes),
        "count": len(items),
        "items": items,
    }


def _related_reason(related_prefix: str, source_codes: list[str], lang: str) -> str:
    """簡短說明這個疾病為何被推送（共病 / 同分類）。"""
    from backend.utils.icd10 import COMORBIDITY_MAP

    for raw in source_codes:
        src = raw[:3].upper()
        if related_prefix in COMORBIDITY_MAP.get(src, []):
            src_name = ICD10_MAP.get(src, src)
            return _msg(lang, "reason_comorbidity", name=src_name)
    related_cat = get_category_for_code(related_prefix)
    if related_cat and related_cat != "未分類":
        return _msg(lang, "reason_same_category", category=_localize_category(related_cat, lang))
    return _msg(lang, "reason_default")


# ── 原有靜態衛教 ────────────────────────────────────────


@router.get("/articles")
def get_articles(
    icd10_code: str = "",
    dimension: str = "",
    tag: str = "",
    featured: bool = False,
    lang: str = DEFAULT_LANG,
):
    """列出 content/education/ 下的 Markdown 文章（卡片版，不含 body）"""
    L = _normalize_lang(lang)
    items = education_content.list_articles(
        icd10=icd10_code or None,
        dimension=dimension or None,
        tag=tag or None,
        featured_only=featured,
        lang=L,
    )
    return {"lang": L, "articles": [a.to_card() for a in items]}


@router.get("/articles/featured")
def get_featured_articles(limit: int = 5, lang: str = DEFAULT_LANG):
    """首頁推送：精選文章（標記 featured: true 的）"""
    L = _normalize_lang(lang)
    items = education_content.list_articles(featured_only=True, lang=L)
    return {"lang": L, "articles": [a.to_card() for a in items[:limit]]}


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
def get_daily_article(days: int = 7, lang: str = DEFAULT_LANG):
    """每日故事：每天依分類各推一篇（疾病故事 / 健康快訊 / 最新資訊），加上近 N 天歷程與外部新聞。

    - 三個分類各自輪播；若某分類沒有文章，該欄位回 null。
    - news 分類除了 markdown 文章，另外從 RSS 補幾則最新醫療資訊。
    - 同一天回傳同一組，不需要儲存狀態。
    """
    from datetime import date, timedelta

    L = _normalize_lang(lang)
    all_articles = education_content.list_articles(lang=L)
    if not all_articles:
        return {
            "lang": L,
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
        "lang": L,
        "today": today_picks,
        "archive": archive,
        "news_feed": feed_items,
    }


@router.get("/articles/{slug}")
def get_article(slug: str, lang: str = DEFAULT_LANG):
    """取得完整文章內容（含 Markdown body 與來源清單）"""
    L = _normalize_lang(lang)
    article = education_content.get_article(slug, lang=L)
    if not article:
        raise HTTPException(status_code=404, detail=_msg(L, "article_not_found", slug=slug))
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
def list_dimensions(lang: str = Query(DEFAULT_LANG)):
    """列出所有知識維度與理解程度等級定義"""
    L = _normalize_lang(lang)
    if L == "en":
        categories = [CATEGORY_LABELS_EN.get(c, c) for c in CHRONIC_DISEASE_CATEGORIES.keys()]
    else:
        categories = list(CHRONIC_DISEASE_CATEGORIES.keys())
    return {
        "lang": L,
        "dimensions": _localize_dimensions(L),
        "comprehension_levels": _localize_comprehension(L),
        "categories": categories,
    }


@router.get("/knowledge-analysis/disease/{icd10_code}")
def analyze_disease(icd10_code: str, lang: str = Query(DEFAULT_LANG)):
    """取得單一慢性病的知識理解度剖面"""
    L = _normalize_lang(lang)
    profile = get_disease_profile(icd10_code)
    if not profile:
        return {
            "error": _msg(L, "baseline_missing", code=icd10_code),
            "available_codes": _available_codes(),
        }
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
