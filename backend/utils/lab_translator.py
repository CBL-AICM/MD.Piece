"""
檢驗數值白話翻譯。
原則：強調醫師已知悉並處理，讓患者安心而非獨自承擔資訊壓力。
"""

# 常見檢驗項目與正常範圍（成人參考值；性別差異另行調整）
LAB_REFERENCE = {
    "CRP": {
        "name": "發炎指數 CRP",
        "unit": "mg/L",
        "normal_max": 5,
        "category": "inflammation",
        "casual_name": "身體發炎程度",
    },
    "ESR": {
        "name": "發炎沉降速率 ESR",
        "unit": "mm/hr",
        "normal_max": 20,
        "category": "inflammation",
        "casual_name": "身體發炎程度",
    },
    "HbA1c": {
        "name": "糖化血色素 HbA1c",
        "unit": "%",
        "normal_max": 6.5,
        "category": "diabetes",
        "casual_name": "近三個月的血糖控制",
    },
    "FBS": {
        "name": "空腹血糖",
        "unit": "mg/dL",
        "normal_min": 70,
        "normal_max": 100,
        "category": "diabetes",
        "casual_name": "空腹血糖",
    },
    "LDL": {
        "name": "低密度膽固醇 LDL",
        "unit": "mg/dL",
        "normal_max": 100,
        "category": "lipid",
        "casual_name": "壞膽固醇",
    },
    "HDL": {
        "name": "高密度膽固醇 HDL",
        "unit": "mg/dL",
        "normal_min": 40,
        "category": "lipid",
        "casual_name": "好膽固醇",
    },
    "TG": {
        "name": "三酸甘油脂 TG",
        "unit": "mg/dL",
        "normal_max": 150,
        "category": "lipid",
        "casual_name": "血脂",
    },
    "Cr": {
        "name": "肌酸酐 Creatinine",
        "unit": "mg/dL",
        "normal_min": 0.6,
        "normal_max": 1.3,
        "category": "kidney",
        "casual_name": "腎臟代謝指標",
    },
    "eGFR": {
        "name": "腎絲球過濾率 eGFR",
        "unit": "mL/min/1.73m²",
        "normal_min": 90,
        "category": "kidney",
        "casual_name": "腎臟過濾能力",
    },
    "ALT": {
        "name": "肝功能 ALT (GPT)",
        "unit": "U/L",
        "normal_max": 40,
        "category": "liver",
        "casual_name": "肝臟健康狀況",
    },
    "AST": {
        "name": "肝功能 AST (GOT)",
        "unit": "U/L",
        "normal_max": 40,
        "category": "liver",
        "casual_name": "肝臟健康狀況",
    },
    "BP_systolic": {
        "name": "收縮壓",
        "unit": "mmHg",
        "normal_min": 90,
        "normal_max": 130,
        "category": "vital",
        "casual_name": "上壓（心臟收縮的壓力）",
    },
    "BP_diastolic": {
        "name": "舒張壓",
        "unit": "mmHg",
        "normal_min": 60,
        "normal_max": 85,
        "category": "vital",
        "casual_name": "下壓（心臟放鬆時的壓力）",
    },
}


def translate_value(code: str, value: float, previous: float | None = None) -> dict:
    """
    將原始檢驗數值翻譯成患者友善的白話文。
    一律不顯示數字、不報警；強調醫師已知悉。
    """
    ref = LAB_REFERENCE.get(code)
    if not ref:
        return {
            "code": code,
            "casual_name": code,
            "level": "unknown",
            "message": "這個指標醫師會在回診時跟你說明",
            "trend": None,
        }

    level = _classify_level(value, ref)
    trend = _classify_trend(value, previous, ref) if previous is not None else None
    message = _compose_message(ref, level, trend)

    return {
        "code": code,
        "casual_name": ref["casual_name"],
        "level": level,
        "trend": trend,
        "message": message,
        "category": ref["category"],
    }


def _classify_level(value: float, ref: dict) -> str:
    """slightly_low / normal / slightly_high / high — 分四級，避免過度警示"""
    nmin = ref.get("normal_min")
    nmax = ref.get("normal_max")
    if nmax is not None and value > nmax:
        if value > nmax * 1.5:
            return "high"
        return "slightly_high"
    if nmin is not None and value < nmin:
        if value < nmin * 0.7:
            return "low"
        return "slightly_low"
    return "normal"


def _classify_trend(value: float, prev: float, ref: dict) -> str:
    """compare to previous: improved / stable / worsened"""
    if prev == 0:
        return "stable"
    diff_pct = (value - prev) / abs(prev)
    if abs(diff_pct) < 0.1:
        return "stable"
    nmax = ref.get("normal_max")
    nmin = ref.get("normal_min")
    if nmax is not None:
        # 數值越高越糟（CRP、HbA1c…）
        return "worsened" if value > prev else "improved"
    if nmin is not None:
        # 數值越低越糟（HDL、eGFR）
        return "worsened" if value < prev else "improved"
    return "stable"


def _compose_message(ref: dict, level: str, trend: str | None) -> str:
    name = ref["casual_name"]

    base = {
        "normal": f"你的{name}在正常範圍，醫師覺得很穩定",
        "slightly_high": f"你的{name}比上次高了一些，這可能跟最近的狀況有關係，醫師已經注意到",
        "slightly_low": f"你的{name}比上次低了一些，醫師會留意觀察",
        "high": f"你的{name}比較需要注意，醫師會幫你想辦法調整",
        "low": f"你的{name}偏低，醫師會幫你調整",
        "unknown": f"你的{name}醫師會在回診時跟你說明",
    }
    msg = base.get(level, base["unknown"])

    if trend == "improved":
        msg += "，最近有改善的趨勢"
    elif trend == "worsened":
        msg += "，最近有些起伏"

    return msg
