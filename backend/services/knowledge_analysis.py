"""慢性病知識理解度分析服務

分析不同慢性病類別在六大知識維度上的理解程度差異，
提供跨疾病比較、缺口分析、衛教優先順序建議。
"""

from backend.utils.icd10 import (
    ICD10_MAP,
    CHRONIC_DISEASE_CATEGORIES,
    KNOWLEDGE_DIMENSIONS,
    COMPREHENSION_LEVELS,
    KNOWLEDGE_BASELINE,
    get_disease_name,
    get_category_for_code,
)


def get_disease_profile(icd10_code: str) -> dict | None:
    """取得單一疾病的知識理解度剖面"""
    prefix = icd10_code[:3]
    if prefix not in KNOWLEDGE_BASELINE:
        return None

    baseline = KNOWLEDGE_BASELINE[prefix]
    dimensions = []
    total_mean = 0
    total_gap = 0
    worst_dimension = None
    worst_gap = 0

    for dim_key, dim_label in KNOWLEDGE_DIMENSIONS.items():
        data = baseline.get(dim_key, {"mean": 0, "gap": 4.0})
        total_mean += data["mean"]
        total_gap += data["gap"]
        if data["gap"] > worst_gap:
            worst_gap = data["gap"]
            worst_dimension = dim_key
        dimensions.append({
            "dimension": dim_key,
            "label": dim_label,
            "mean_score": data["mean"],
            "gap": data["gap"],
            "level": _score_to_level(data["mean"]),
        })

    n = len(KNOWLEDGE_DIMENSIONS)
    return {
        "icd10": prefix,
        "disease_name": get_disease_name(prefix),
        "category": get_category_for_code(prefix),
        "overall_mean": round(total_mean / n, 2),
        "overall_gap": round(total_gap / n, 2),
        "worst_dimension": worst_dimension,
        "worst_dimension_label": KNOWLEDGE_DIMENSIONS.get(worst_dimension, ""),
        "dimensions": dimensions,
    }


def compare_across_diseases(icd10_codes: list[str] | None = None) -> dict:
    """跨疾病知識理解度比較

    若未指定 codes，則比較所有有基準數據的疾病。
    """
    codes = icd10_codes or list(KNOWLEDGE_BASELINE.keys())
    profiles = []
    for code in codes:
        p = get_disease_profile(code)
        if p:
            profiles.append(p)

    profiles.sort(key=lambda x: x["overall_mean"])

    # 按維度聚合
    dimension_summary = {}
    for dim_key in KNOWLEDGE_DIMENSIONS:
        scores = [
            p["dimensions"][i]["mean_score"]
            for p in profiles
            for i, d in enumerate(p["dimensions"])
            if d["dimension"] == dim_key
        ]
        if scores:
            dimension_summary[dim_key] = {
                "label": KNOWLEDGE_DIMENSIONS[dim_key],
                "avg": round(sum(scores) / len(scores), 2),
                "min": min(scores),
                "max": max(scores),
                "range": round(max(scores) - min(scores), 2),
            }

    return {
        "disease_profiles": profiles,
        "dimension_summary": dimension_summary,
        "total_diseases": len(profiles),
    }


def compare_by_category() -> dict:
    """按慢性病分類群組比較知識理解度"""
    category_results = {}

    for cat_name, codes in CHRONIC_DISEASE_CATEGORIES.items():
        cat_profiles = []
        for code in codes:
            p = get_disease_profile(code)
            if p:
                cat_profiles.append(p)

        if not cat_profiles:
            continue

        # 計算該分類的平均值
        cat_mean = round(
            sum(p["overall_mean"] for p in cat_profiles) / len(cat_profiles), 2
        )
        cat_gap = round(
            sum(p["overall_gap"] for p in cat_profiles) / len(cat_profiles), 2
        )

        # 找出該分類中各維度的平均
        dim_avgs = {}
        for dim_key in KNOWLEDGE_DIMENSIONS:
            dim_scores = []
            for p in cat_profiles:
                for d in p["dimensions"]:
                    if d["dimension"] == dim_key:
                        dim_scores.append(d["mean_score"])
            if dim_scores:
                dim_avgs[dim_key] = round(sum(dim_scores) / len(dim_scores), 2)

        category_results[cat_name] = {
            "diseases_count": len(cat_profiles),
            "overall_mean": cat_mean,
            "overall_gap": cat_gap,
            "dimension_averages": dim_avgs,
            "diseases": [
                {"icd10": p["icd10"], "name": p["disease_name"], "mean": p["overall_mean"]}
                for p in cat_profiles
            ],
        }

    # 按平均理解度排序
    sorted_categories = dict(
        sorted(category_results.items(), key=lambda x: x[1]["overall_mean"])
    )

    return {
        "categories": sorted_categories,
        "total_categories": len(sorted_categories),
    }


def get_education_priorities(top_n: int = 5) -> dict:
    """找出最需要加強衛教的疾病×維度組合"""
    gaps = []
    for code, baseline in KNOWLEDGE_BASELINE.items():
        for dim_key, data in baseline.items():
            gaps.append({
                "icd10": code,
                "disease_name": get_disease_name(code),
                "category": get_category_for_code(code),
                "dimension": dim_key,
                "dimension_label": KNOWLEDGE_DIMENSIONS.get(dim_key, ""),
                "current_score": data["mean"],
                "gap": data["gap"],
                "level": _score_to_level(data["mean"]),
            })

    gaps.sort(key=lambda x: x["gap"], reverse=True)

    return {
        "priorities": gaps[:top_n],
        "total_gaps_analyzed": len(gaps),
        "recommendation": _generate_recommendation(gaps[:top_n]),
    }


def get_comprehension_distribution() -> dict:
    """統計各理解程度等級的分佈"""
    distribution = {level: 0 for level in COMPREHENSION_LEVELS.values()}
    total = 0

    for baseline in KNOWLEDGE_BASELINE.values():
        for data in baseline.values():
            level_label = _score_to_level(data["mean"])
            distribution[level_label] = distribution.get(level_label, 0) + 1
            total += 1

    # 轉為百分比
    pct = {}
    for level_label, count in distribution.items():
        pct[level_label] = {
            "count": count,
            "percentage": round(count / total * 100, 1) if total > 0 else 0,
        }

    return {"distribution": pct, "total_data_points": total}


def _score_to_level(score: float) -> str:
    """將分數轉為理解程度等級"""
    if score < 0.5:
        return COMPREHENSION_LEVELS[0]
    elif score < 1.5:
        return COMPREHENSION_LEVELS[1]
    elif score < 2.5:
        return COMPREHENSION_LEVELS[2]
    elif score < 3.5:
        return COMPREHENSION_LEVELS[3]
    else:
        return COMPREHENSION_LEVELS[4]


def _generate_recommendation(top_gaps: list[dict]) -> str:
    """根據缺口分析生成衛教建議"""
    if not top_gaps:
        return "目前無足夠數據進行建議。"

    lines = ["根據知識缺口分析，建議優先加強以下衛教內容："]
    for i, g in enumerate(top_gaps, 1):
        lines.append(
            f"{i}. {g['disease_name']}的「{g['dimension_label']}」"
            f"（目前平均 {g['current_score']}/4，缺口 {g['gap']}）"
        )

    return "\n".join(lines)
