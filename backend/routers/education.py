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
from backend.services.llm_service import build_patient_facing_system, call_claude
from backend.services import celebrity_health, education_content, news_feed
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

EDUCATION_ROLE_PROMPT = (
    "【本次任務：撰寫衛教文章】\n"
    "你正在為慢性病患者撰寫一篇衛教文章。讀者是病人本人或家屬。\n\n"
    "情境專屬原則（憲法之外）：\n"
    "1. 給予希望 — 每篇都要讓病人感受到「這是可以管理好的」；\n"
    "   但仍受風格層 [B.6] 約束：不要說「絕對沒事」「保證不會復發」這類假保證\n"
    "2. 實用具體 — 給可以立刻行動的建議，不是空泛的「多注意」\n"
    "3. 台灣情境 — 用台灣的醫療體系、健保制度、飲食習慣作為背景\n"
    "4. **必附 IF > 5 同儕審查文獻** — 文末固定加一段「## 📚 參考來源」，\n"
    "   其中至少 3 條為 Impact Factor > 5 的同儕審查期刊文章；\n"
    "   可再附 2–3 條台灣或國際指引補充\n\n"
    "回覆格式：使用 Markdown，用標題分段，適當加入 emoji 讓文章更親切。\n"
    "長度控制在 800–1200 字之間（不含參考來源）。\n\n"
    "## ⚠️ 文獻來源強制規範（極為重要）\n"
    "MD.Piece 是醫療平台，所有衛教文必須有可驗證的高品質實證。請遵守：\n\n"
    "**A. 強制門檻**：每篇文章至少 3 條 peer-reviewed 期刊文章，期刊 Impact Factor > 5。\n\n"
    "**B. 可接受的高 IF 期刊（IF > 5，僅列常用）**：\n"
    "- 一般醫學：NEJM (IF=158.5)、Lancet (IF=98.4)、JAMA (IF=63.1)、BMJ (IF=93.6)、"
    "Annals of Internal Medicine (IF=19.6)、Nature Medicine (IF=58.7)\n"
    "- 心血管：Circulation (IF=37.8)、European Heart Journal (IF=37.6)、JACC (IF=21.7)、"
    "Hypertension (IF=7.7)、Stroke (IF=7.8)\n"
    "- 內分泌：Lancet Diabetes Endocrinol (IF=44.0)、Diabetes Care (IF=16.2)、Diabetologia (IF=8.4)\n"
    "- 呼吸：Lancet Respir Med (IF=76.2)、AJRCCM (IF=24.7)、Chest (IF=9.6)\n"
    "- 神經：Lancet Neurology (IF=48.0)、JAMA Neurology (IF=20.4)、Neurology (IF=7.7)\n"
    "- 腫瘤：Lancet Oncology (IF=51.1)、JAMA Oncology (IF=22.5)\n"
    "- 腎臟/肝膽：Kidney International (IF=14.8)、JASN (IF=13.6)、Gut (IF=23.0)、Hepatology (IF=12.9)\n"
    "- 系統性回顧：Cochrane Database of Systematic Reviews (IF=8.4)\n\n"
    "**C. 每條格式（嚴格遵守，方便系統解析 IF）**：\n"
    "`- 作者 et al. (YYYY). 文章標題. 期刊名 (IF=XX.X). doi:10.xxxx/yyyy`\n\n"
    "範例：\n"
    "`- Whelton PK, et al. (2018). 2017 ACC/AHA Hypertension Guideline. Hypertension (IF=7.7). doi:10.1161/HYP.0000000000000065`\n\n"
    "**D. 補充指引（不取代 peer-reviewed 文獻，可額外列出）**：\n"
    "可引用台灣衛福部、國健署、健保署、台灣各醫學會、WHO、CDC、Mayo Clinic、UpToDate、NIH MedlinePlus 的指引，"
    "格式：`- 組織：指引主題（YYYY 年版本）`。\n\n"
    "**E. 嚴格禁止**：\n"
    "- ❌ 不要編造 DOI、PMID、不存在的期刊名\n"
    "- ❌ 不要把指引當作 peer-reviewed 文獻計算 IF 門檻\n"
    "- ❌ 不確定 IF 數值就只列你確定的高 IF 期刊（如 NEJM、Lancet 一定 > 5）\n"
    "- ❌ 不要省略 IF 註記——前端會檢查 IF 徽章是否齊備\n\n"
    "本文末尾加一行小字：「※ 詳細治療仍以主治醫師判斷為準，本文僅供衛教參考」。"
)


# 風格層 + 上面的 role prompt 組成 system；不接 patient_context（衛教文章是內容
# 生成，不是個別病人的對話回應），also 跳過 few-shot（example 是「對話式」的）。
SYSTEM_PROMPT = build_patient_facing_system(
    EDUCATION_ROLE_PROMPT,
    patient_context=None,
    include_examples=False,
)


class EducationRequest(BaseModel):
    icd10_code: Optional[str] = None
    dimension: Optional[str] = None
    topic: Optional[str] = None


# ── 衛教文章生成（Claude API）────────────────────────────


GENERIC_TOPIC_PROMPT = (
    "請以 MD.Piece 衛教助手的身分，為一位病人撰寫主題為「{topic}」的衛教文章。\n\n"
    "撰稿要求：\n"
    "1. 用溫暖、淺顯易懂的語氣（語氣 / 用詞 / 假保證等規則遵照系統前置的風格層）\n"
    "2. 必要的醫學名詞要立刻用括號或比喻解釋\n"
    "3. 結構清楚：先講「這是什麼」，再講「為什麼重要」，最後給「可以怎麼做」\n"
    "4. 重點放在安心與實用 — 讓病人讀完覺得「我知道該做什麼了」\n"
    "5. 適當使用 emoji 讓文章更親切\n"
    "6. 用台灣的醫療制度、健保、飲食習慣作為背景\n"
    "7. 文末提醒：詳細治療仍以主治醫師判斷為準\n"
    "8. **必加** 一段「## 📚 參考來源」 — 遵守系統 prompt 中的「文獻來源強制規範」：\n"
    "   - 至少 3 條 Impact Factor > 5 的同儕審查期刊文章\n"
    "   - 格式：`- 作者 et al. (YYYY). 標題. 期刊 (IF=XX.X). doi:...`\n"
    "   - 可額外附 2–3 條台灣／國際指引補充\n"
    "   - **嚴禁編造 DOI、期刊名或 IF 數值**\n\n"
    "回覆格式：使用 Markdown，分段加標題，長度控制在 600–1000 字（不含參考來源）。"
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


@router.get("/related")
def list_related_diseases(
    codes: str = Query("", description="病患已登錄的 ICD-10 代碼，逗號分隔"),
    limit: int = Query(6, ge=1, le=20, description="最多回傳幾個相關疾病"),
):
    """病患登錄主疾病後，自動推送臨床上常見的相關疾病與其衛教文章。

    產生規則：
    1. 從 COMORBIDITY_MAP 取共病（如糖尿病 → 高血壓、腎病變、心血管）
    2. 從 CHRONIC_DISEASE_CATEGORIES 取同分類疾病
    3. 排除病患已登錄的疾病、保留首次出現順序

    每個相關疾病會附上 content/education/ 內已審稿的文章卡片，
    讓前端可以直接顯示「為您推送的相關衛教」。
    """
    own = [c.strip() for c in (codes or "").split(",") if c.strip()]
    related_prefixes = get_related_icd10_codes(own)[:limit]

    own_prefixes = {c[:3].upper() for c in own}
    items: list[dict[str, Any]] = []
    for prefix in related_prefixes:
        articles = education_content.list_articles(icd10=prefix)
        articles.sort(key=lambda a: (not a.featured, a.dimension or "z", a.slug))
        items.append({
            "icd10": prefix,
            "name": ICD10_MAP.get(prefix, "未知疾病"),
            "category": get_category_for_code(prefix),
            "reason": _related_reason(prefix, own),
            "articles": [a.to_card() for a in articles[:3]],
            "article_count": len(articles),
        })

    return {
        "source_codes": sorted(own_prefixes),
        "count": len(items),
        "items": items,
    }


def _related_reason(related_prefix: str, source_codes: list[str]) -> str:
    """簡短說明這個疾病為何被推送（共病 / 同分類）。"""
    from backend.utils.icd10 import COMORBIDITY_MAP

    for raw in source_codes:
        src = raw[:3].upper()
        if related_prefix in COMORBIDITY_MAP.get(src, []):
            src_name = ICD10_MAP.get(src, src)
            return f"與「{src_name}」常一起出現的共病"
    related_cat = get_category_for_code(related_prefix)
    if related_cat and related_cat != "未分類":
        return f"同屬「{related_cat}」的相關疾病"
    return "建議一併了解的相關疾病"


@router.get("/my-diseases")
def list_my_diseases(
    codes: str = Query("", description="病患已登錄的 ICD-10 代碼，逗號分隔"),
    articles_per_disease: int = Query(6, ge=1, le=20),
):
    """為「我的疾病書架」與「我的疾病衛教文章」提供資料。

    對病患已登錄的每個疾病各回傳：
    - 疾病基本資料（icd10、名稱、分類）
    - 該疾病在 content/education/ 下的所有衛教文章卡片（依精選 / 維度 / slug 排序）
    - 六大維度的覆蓋情形（哪些維度已有審稿過的文章）

    比 /related 直接很多——這個只看「自己的疾病」，不做共病推論。
    """
    own = [c.strip() for c in (codes or "").split(",") if c.strip()]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    for raw in own:
        prefix = raw[:3].upper()
        if not prefix or prefix in seen:
            continue
        seen.add(prefix)

        articles = education_content.list_articles(icd10=prefix)
        articles.sort(key=lambda a: (not a.featured, a.dimension or "z", a.slug))

        covered_dims = sorted({a.dimension for a in articles if a.dimension})
        items.append({
            "icd10": prefix,
            "name": ICD10_MAP.get(prefix, "未知疾病"),
            "category": get_category_for_code(prefix),
            "is_supported": prefix in ICD10_MAP,
            "articles": [a.to_card() for a in articles[:articles_per_disease]],
            "article_count": len(articles),
            "covered_dimensions": covered_dims,
            "all_dimensions": list(KNOWLEDGE_DIMENSIONS.keys()),
        })

    return {
        "source_codes": [it["icd10"] for it in items],
        "count": len(items),
        "items": items,
    }


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
def get_featured_articles(limit: int = 6):
    """首頁今日精選：每天用日期 ordinal 在精選池子中輪播一輪，確保每天看到的文章組合都不同。

    池子順序：
    1. 標記 `featured: true` 的文章（人工挑選，最高優先）
    2. 若精選池子小於 `limit`，用「有 reviewed_at 且有 sources」的高品質審稿文章補齊
    3. 仍不足時才退回任意 markdown 文章
    """
    from datetime import date

    primary = education_content.list_articles(featured_only=True)
    primary.sort(key=lambda a: a.slug)

    if len(primary) < max(limit * 2, 8):
        # 精選池子不夠 → 拉「審稿過 + 有來源」的文章湊滿 rotation pool
        fallback = [
            a for a in education_content.list_articles()
            if (not a.featured) and a.reviewed_at and a.sources
        ]
        fallback.sort(key=lambda a: a.slug)
        seen = {a.slug for a in primary}
        for a in fallback:
            if a.slug not in seen:
                primary.append(a)
                seen.add(a.slug)

    if not primary:
        return {"articles": [], "rotation_date": date.today().isoformat(), "pool_size": 0}

    today = date.today()
    n = len(primary)
    start = today.toordinal() % n
    take = min(limit, n)
    rotated = [primary[(start + i) % n] for i in range(take)]
    return {
        "articles": [a.to_card() for a in rotated],
        "rotation_date": today.isoformat(),
        "pool_size": n,
    }


DAILY_CATEGORIES = ("disease", "quick_tip", "news")

# 沒標 category 的舊文章依 slug 前綴自動歸類，避免每日故事池子太小造成重複。
_QUICK_TIP_PREFIXES = (
    "symptoms-", "emergency-", "medications-", "labs-",
    "hydration-", "nutrition-", "exercise-", "sleep-", "prevent-",
    "tips-", "diet-", "self-", "story-",
)
# slug 含這些關鍵字也歸入 quick_tip／衛教快訊
_QUICK_TIP_KEYWORDS = (
    "-tips", "-story", "-diet", "-myth", "-self", "-warning",
    "-seven-hours", "burnout", "follow", "diary", "goal",
)


def _auto_category(article) -> str:
    cat = (article.category or "").lower()
    if cat in DAILY_CATEGORIES:
        return cat
    slug = (article.slug or "").lower()
    for prefix in _QUICK_TIP_PREFIXES:
        if slug.startswith(prefix):
            return "quick_tip"
    for kw in _QUICK_TIP_KEYWORDS:
        if kw in slug:
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
        feed_items = news_feed.fetch_news(limit=6)
        celebrity_pool = news_feed.fetch_news(limit=50)
        return {
            "today": {c: None for c in DAILY_CATEGORIES},
            "archive": [],
            "news_feed": feed_items,
            "celebrity_stories": celebrity_health.extract_celebrity_stories(celebrity_pool),
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
        n = len(pool)
        # 用一個跟池大小互質的步幅，加上 category 的 hash 偏移，
        # 讓三個分類在連續幾天看起來不像「整齊向後位移」。
        stride = 7 if n % 7 != 0 else 11 if n % 11 != 0 else 1
        cat_offset = sum(ord(c) for c in cat) % n
        idx = (d.toordinal() * stride + cat_offset) % n
        return pool[idx]

    feed_items = news_feed.fetch_news(limit=6)
    # 給名人健康抽取一個比較大的池子（共用快取，不會多 fetch）；
    # 顯示用的 news_feed 還是用 6 則，避免畫面被新聞塞爆。
    celebrity_pool = news_feed.fetch_news(limit=50)

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
        "celebrity_stories": celebrity_health.extract_celebrity_stories(celebrity_pool),
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
