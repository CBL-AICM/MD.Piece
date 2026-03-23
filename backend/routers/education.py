from fastapi import APIRouter, Query
from typing import Optional

from backend.services.knowledge_analysis import (
    get_disease_profile,
    compare_across_diseases,
    compare_by_category,
    get_education_priorities,
    get_comprehension_distribution,
)
from backend.utils.icd10 import (
    KNOWLEDGE_DIMENSIONS,
    COMPREHENSION_LEVELS,
    CHRONIC_DISEASE_CATEGORIES,
)

router = APIRouter()

# 慢性病衛教 - 靜態卡片文章、ICD-10 個人化衛教


@router.get("/articles")
def get_articles(icd10_code: str = ""):
    # 回傳靜態衛教文章（不使用 LLM，確保內容品質可控）
    return {"articles": []}


@router.get("/idle-hints")
def get_idle_hints():
    # 小禾閒置暗示句子池（20-30 句）
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
