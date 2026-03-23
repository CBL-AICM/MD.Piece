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
    # 消化系統疾病
    "K50": "克隆氏症",
    "K51": "潰瘍性結腸炎",
    "K74": "肝纖維化與肝硬化",
    # 肌肉骨骼系統疾病
    "M06": "類風濕性關節炎",
    "M05": "血清陽性類風濕性關節炎",
    "M81": "骨質疏鬆症",
    # 泌尿系統疾病
    "N18": "慢性腎臟病",
    # 神經系統疾病
    "G20": "巴金森氏症",
    "G35": "多發性硬化症",
    "G30": "阿茲海默症",
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
    "呼吸系統疾病": ["J45", "J44"],
    "消化系統疾病": ["K50", "K51", "K74"],
    "肌肉骨骼疾病": ["M06", "M05", "M81"],
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
