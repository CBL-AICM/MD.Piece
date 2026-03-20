# 規則引擎 - 第一層分流（不走 LLM，直接判斷急診）

EMERGENCY_SYMPTOMS = [
    "胸痛", "呼吸困難", "意識不清", "大量出血",
    "嚴重過敏", "中風症狀", "心跳異常"
]

IMMUNOSUPPRESSED_FEVER_THRESHOLD = 38.0  # 免疫抑制患者發燒門檻（°C）

def check_emergency(symptoms: list[str], is_immunosuppressed: bool, temperature: float = 0) -> bool:
    """第一層：規則引擎判斷是否直接升級急診警示"""
    for s in symptoms:
        if s in EMERGENCY_SYMPTOMS:
            return True
    if is_immunosuppressed and temperature >= IMMUNOSUPPRESSED_FEVER_THRESHOLD:
        return True
    return False
