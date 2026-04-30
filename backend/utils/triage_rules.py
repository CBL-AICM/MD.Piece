"""
規則引擎 — 第一層分流。
觸發條件：神經系統警訊、心肺急症、大量出血、免疫抑制+發燒。
"""

EMERGENCY_SYMPTOMS = [
    # 神經系統
    "中風症狀", "意識不清", "突然劇烈頭痛", "口齒不清", "肢體無力", "癲癇發作",
    # 心肺
    "胸痛", "壓胸", "呼吸困難", "心跳異常", "嘴唇發紫",
    # 出血
    "大量出血", "吐血", "便血", "咳血",
    # 過敏
    "嚴重過敏", "喉嚨腫脹", "全身蕁麻疹",
    # 其他
    "高燒不退", "脫水", "持續嘔吐",
]

IMMUNOSUPPRESSED_FEVER_THRESHOLD = 38.0  # 免疫抑制患者發燒門檻（°C）


def check_emergency(symptoms: list[str], is_immunosuppressed: bool, temperature: float = 0) -> bool:
    """第一層：規則引擎判斷是否直接升級急診警示"""
    for s in symptoms or []:
        if s in EMERGENCY_SYMPTOMS:
            return True
    if is_immunosuppressed and temperature and temperature >= IMMUNOSUPPRESSED_FEVER_THRESHOLD:
        return True
    return False
