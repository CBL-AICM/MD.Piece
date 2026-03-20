# ICD-10 代碼對應表 - 用於個人化衛教推送

ICD10_MAP = {
    "M06": "類風濕性關節炎",
    "E11": "第二型糖尿病",
    "I10": "原發性高血壓",
    "J45": "氣喘",
    "K50": "克隆氏症",
    # TODO: 持續擴充
}

def get_disease_name(icd10_code: str) -> str:
    prefix = icd10_code[:3]
    return ICD10_MAP.get(prefix, "未知疾病")
