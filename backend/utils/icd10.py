# ICD-10 代碼對應表 - 用於個人化衛教推送與知識理解度分析

ICD10_MAP = {
    # 內分泌與代謝疾病
    "E11": "第二型糖尿病",
    "E10": "第一型糖尿病",
    "E78": "高脂血症",
    "E03": "甲狀腺功能低下",
    "E05": "甲狀腺功能亢進",
    # 循環系統疾病
    "I10": "原發性高血壓",
    "I25": "慢性缺血性心臟病",
    "I50": "心臟衰竭",
    "I48": "心房顫動",
    "I63": "腦梗塞（中風）",
    # 呼吸系統疾病
    "J45": "氣喘",
    "J44": "慢性阻塞性肺病（COPD）",
    "J30": "過敏性鼻炎",
    # 消化系統疾病
    "K50": "克隆氏症",
    "K51": "潰瘍性結腸炎",
    "K74": "肝纖維化與肝硬化",
    "K90": "乳糜瀉（麩質不耐）",
    # 肌肉骨骼與自體免疫疾病
    "M06": "類風濕性關節炎",
    "M05": "血清陽性類風濕性關節炎",
    "M81": "骨質疏鬆症",
    "M32": "系統性紅斑性狼瘡（SLE）",
    "M35": "修格蘭氏症候群（乾燥症）",
    "M45": "僵直性脊椎炎",
    "M34": "全身性硬化症（硬皮症）",
    "M33": "皮肌炎與多發性肌炎",
    "M31": "巨細胞動脈炎與其他血管炎",
    # 皮膚與過敏疾病
    "L40": "乾癬（牛皮癬）",
    "L20": "異位性皮膚炎",
    "L50": "蕁麻疹",
    # 泌尿系統疾病
    "N18": "慢性腎臟病",
    # 神經系統疾病
    "G20": "巴金森氏症",
    "G35": "多發性硬化症",
    "G30": "阿茲海默症",
    "G70": "重症肌無力",
    # 血液 / 免疫
    "D69": "免疫性血小板減少紫斑症（ITP）",
    # 精神疾病
    "F32": "重鬱症",
    "F41": "焦慮症",
    # 腫瘤（慢性追蹤）
    "C50": "乳癌",
    "C34": "肺癌",
    "C18": "大腸癌",
}

# 慢性病分類群組 — 用於知識理解度比較分析
CHRONIC_DISEASE_CATEGORIES = {
    "代謝疾病": ["E11", "E10", "E78", "E03", "E05"],
    "心血管疾病": ["I10", "I25", "I50", "I48", "I63"],
    "呼吸系統疾病": ["J45", "J44", "J30"],
    "消化系統疾病": ["K50", "K51", "K74", "K90"],
    "肌肉骨骼疾病": ["M06", "M05", "M81"],
    "自體免疫疾病": ["M32", "M35", "M45", "M34", "M33", "M31", "G70", "D69"],
    "皮膚與過敏疾病": ["L40", "L20", "L50", "J30"],
    "腎臟疾病": ["N18"],
    "神經退化疾病": ["G20", "G35", "G30"],
    "精神疾病": ["F32", "F41"],
    "腫瘤追蹤": ["C50", "C34", "C18"],
}

# 知識理解度維度定義
# 每個維度代表病患對疾病的不同面向理解程度
KNOWLEDGE_DIMENSIONS = {
    "disease_awareness": "疾病認知（知道自己得了什麼病）",
    "symptom_recognition": "症狀辨識（能辨別異常症狀）",
    "medication_knowledge": "用藥知識（知道藥物作用與副作用）",
    "self_management": "自我管理（飲食、運動、生活型態）",
    "emergency_response": "緊急應變（知道何時該就醫）",
    "complication_awareness": "併發症認知（了解長期風險）",
}

# 理解程度等級
COMPREHENSION_LEVELS = {
    0: "完全不了解",
    1: "聽過但不清楚",
    2: "基本了解",
    3: "清楚理解並能說明",
    4: "能自主應用與教導他人",
}

# 各慢性病的知識理解度基準數據（基於文獻與臨床經驗的預設值）
# 結構: {icd10: {dimension: {"mean": 平均理解度, "gap": 理想值與實際值差距}}}
KNOWLEDGE_BASELINE = {
    "E11": {
        "disease_awareness": {"mean": 2.8, "gap": 1.2},
        "symptom_recognition": {"mean": 2.1, "gap": 1.9},
        "medication_knowledge": {"mean": 2.5, "gap": 1.5},
        "self_management": {"mean": 2.0, "gap": 2.0},
        "emergency_response": {"mean": 1.8, "gap": 2.2},
        "complication_awareness": {"mean": 1.5, "gap": 2.5},
    },
    "I10": {
        "disease_awareness": {"mean": 3.0, "gap": 1.0},
        "symptom_recognition": {"mean": 1.6, "gap": 2.4},
        "medication_knowledge": {"mean": 2.3, "gap": 1.7},
        "self_management": {"mean": 2.2, "gap": 1.8},
        "emergency_response": {"mean": 1.9, "gap": 2.1},
        "complication_awareness": {"mean": 1.4, "gap": 2.6},
    },
    "J45": {
        "disease_awareness": {"mean": 3.2, "gap": 0.8},
        "symptom_recognition": {"mean": 2.8, "gap": 1.2},
        "medication_knowledge": {"mean": 2.0, "gap": 2.0},
        "self_management": {"mean": 2.5, "gap": 1.5},
        "emergency_response": {"mean": 2.6, "gap": 1.4},
        "complication_awareness": {"mean": 1.8, "gap": 2.2},
    },
    "J44": {
        "disease_awareness": {"mean": 2.2, "gap": 1.8},
        "symptom_recognition": {"mean": 2.0, "gap": 2.0},
        "medication_knowledge": {"mean": 1.8, "gap": 2.2},
        "self_management": {"mean": 1.5, "gap": 2.5},
        "emergency_response": {"mean": 1.7, "gap": 2.3},
        "complication_awareness": {"mean": 1.2, "gap": 2.8},
    },
    "N18": {
        "disease_awareness": {"mean": 2.0, "gap": 2.0},
        "symptom_recognition": {"mean": 1.5, "gap": 2.5},
        "medication_knowledge": {"mean": 2.1, "gap": 1.9},
        "self_management": {"mean": 1.8, "gap": 2.2},
        "emergency_response": {"mean": 1.6, "gap": 2.4},
        "complication_awareness": {"mean": 1.3, "gap": 2.7},
    },
    "I50": {
        "disease_awareness": {"mean": 2.3, "gap": 1.7},
        "symptom_recognition": {"mean": 2.2, "gap": 1.8},
        "medication_knowledge": {"mean": 2.0, "gap": 2.0},
        "self_management": {"mean": 1.7, "gap": 2.3},
        "emergency_response": {"mean": 2.1, "gap": 1.9},
        "complication_awareness": {"mean": 1.4, "gap": 2.6},
    },
    "M06": {
        "disease_awareness": {"mean": 2.5, "gap": 1.5},
        "symptom_recognition": {"mean": 2.6, "gap": 1.4},
        "medication_knowledge": {"mean": 2.2, "gap": 1.8},
        "self_management": {"mean": 2.3, "gap": 1.7},
        "emergency_response": {"mean": 1.5, "gap": 2.5},
        "complication_awareness": {"mean": 1.6, "gap": 2.4},
    },
    "G20": {
        "disease_awareness": {"mean": 2.4, "gap": 1.6},
        "symptom_recognition": {"mean": 2.3, "gap": 1.7},
        "medication_knowledge": {"mean": 2.1, "gap": 1.9},
        "self_management": {"mean": 1.6, "gap": 2.4},
        "emergency_response": {"mean": 1.4, "gap": 2.6},
        "complication_awareness": {"mean": 1.3, "gap": 2.7},
    },
    "F32": {
        "disease_awareness": {"mean": 1.8, "gap": 2.2},
        "symptom_recognition": {"mean": 1.5, "gap": 2.5},
        "medication_knowledge": {"mean": 1.7, "gap": 2.3},
        "self_management": {"mean": 1.4, "gap": 2.6},
        "emergency_response": {"mean": 1.2, "gap": 2.8},
        "complication_awareness": {"mean": 1.0, "gap": 3.0},
    },
    "C50": {
        "disease_awareness": {"mean": 3.1, "gap": 0.9},
        "symptom_recognition": {"mean": 2.5, "gap": 1.5},
        "medication_knowledge": {"mean": 2.3, "gap": 1.7},
        "self_management": {"mean": 2.0, "gap": 2.0},
        "emergency_response": {"mean": 2.2, "gap": 1.8},
        "complication_awareness": {"mean": 2.0, "gap": 2.0},
    },
}


def get_disease_name(icd10_code: str) -> str:
    prefix = icd10_code[:3]
    return ICD10_MAP.get(prefix, "未知疾病")


def get_category_for_code(icd10_code: str) -> str:
    """取得 ICD-10 代碼所屬的慢性病分類"""
    prefix = icd10_code[:3]
    for category, codes in CHRONIC_DISEASE_CATEGORIES.items():
        if prefix in codes:
            return category
    return "未分類"


# 共病關聯圖 — 臨床上常一起出現的慢性病
# 用於患者登錄主疾病後，自動推送「容易合併出現」的相關疾病衛教
# key 為主疾病 ICD-10 prefix，value 為臨床高度相關的疾病列表
COMORBIDITY_MAP: dict[str, list[str]] = {
    # 第二型糖尿病 — 三高、腎病變、心血管、視網膜病變
    "E11": ["I10", "E78", "N18", "I25", "I63"],
    "E10": ["I10", "E78", "N18", "I25"],
    "E78": ["I10", "I25", "E11", "I63"],
    "E03": ["E78", "F32"],
    "E05": ["I48", "F41"],
    # 高血壓 — 糖尿病、腎病變、心血管疾病、中風
    "I10": ["E11", "E78", "I25", "I50", "I63", "N18"],
    "I25": ["I10", "E11", "E78", "I50", "I48"],
    "I50": ["I10", "I25", "I48", "N18", "E11"],
    "I48": ["I10", "I50", "I25", "I63"],
    "I63": ["I10", "I48", "E11", "E78", "I25"],
    # 氣喘、COPD — 互相鑑別、合併情形多；過敏三聯徵：J45 / J30 / L20 / L50 常合併
    "J45": ["J44", "F41", "J30", "L20", "L50"],
    "J44": ["J45", "I50", "I25", "I10"],
    # 發炎性腸道疾病、肝硬化、乳糜瀉
    "K50": ["K51", "M06", "M45"],
    "K51": ["K50", "M06", "M45"],
    "K74": ["E11", "E78", "M34"],
    "K90": ["E03", "M32", "E10"],
    # 類風濕、骨鬆 — 好發族群重疊、共用治療概念
    "M06": ["M05", "M35", "M81", "M32", "F32"],
    "M05": ["M06", "M35", "M81"],
    "M81": ["M06", "M32", "E03", "F32"],
    # 自體免疫疾病 — 互相重疊（SLE 與乾燥症常合併、與 RA 重疊；硬皮症 / 皮肌炎與肺臟、腎臟相關）
    "M32": ["M35", "M06", "N18", "F32", "M81"],
    "M35": ["M32", "M06", "F32"],
    "M45": ["K50", "K51", "L40", "M06"],
    "M34": ["I50", "N18", "K74", "F32"],
    "M33": ["M32", "C50", "C34", "F32"],
    "M31": ["F32", "M32"],
    "G70": ["E03", "E05", "F32"],
    "D69": ["M32", "F32"],
    # 皮膚與過敏 — 過敏三聯徵（atopic march）：氣喘、過敏性鼻炎、異位性皮膚炎、蕁麻疹常合併
    "L40": ["M45", "F32", "E78", "I25"],
    "L20": ["J45", "J30", "L50", "F41"],
    "L50": ["J30", "L20", "J45"],
    "J30": ["J45", "L20", "L50"],
    # 腎病變 — 糖尿病、高血壓、心衰
    "N18": ["E11", "I10", "I50", "E78", "M32"],
    # 神經退化 — 憂鬱、骨鬆、跌倒風險
    "G20": ["F32", "M81"],
    "G35": ["F32", "F41"],
    "G30": ["F32", "I10"],
    # 精神疾病 — 互相共病
    "F32": ["F41", "G30"],
    "F41": ["F32"],
    # 腫瘤追蹤 — 治療後常見併發三高與心血管問題
    "C50": ["F32", "M81"],
    "C34": ["J44", "F32", "M33"],
    "C18": ["F32", "E11"],
}


def get_related_icd10_codes(
    icd10_codes: list[str],
    *,
    include_same_category: bool = True,
    max_per_code: int = 5,
) -> list[str]:
    """根據病患已登錄的疾病列表，回傳臨床上相關的疾病 ICD-10 prefix。

    取自兩個來源：
    1. COMORBIDITY_MAP：每個主疾病各取前 ``max_per_code`` 個共病
    2. 同分類疾病（``include_same_category=True`` 時）：補上同 CHRONIC_DISEASE_CATEGORIES 群組的其他疾病

    結果會去除：
    - 病患已登錄的疾病
    - 不在 ICD10_MAP 內的代碼
    - 重複的代碼（保留首次出現順序）
    """
    if not icd10_codes:
        return []

    own = {code[:3].upper() for code in icd10_codes if code}
    seen: set[str] = set()
    ordered: list[str] = []

    def _add(code: str) -> None:
        prefix = code[:3].upper()
        if prefix in own or prefix in seen:
            return
        if prefix not in ICD10_MAP:
            return
        seen.add(prefix)
        ordered.append(prefix)

    for raw in icd10_codes:
        prefix = raw[:3].upper() if raw else ""
        if not prefix:
            continue
        for related in COMORBIDITY_MAP.get(prefix, [])[:max_per_code]:
            _add(related)
        if include_same_category:
            for cat_codes in CHRONIC_DISEASE_CATEGORIES.values():
                if prefix in cat_codes:
                    for sibling in cat_codes:
                        _add(sibling)
                    break

    return ordered
