# 規則引擎 - 第一層分流（不走 LLM，直接判斷急診）
#
# 設計（鐵則 5）：致命紅旗的偵測是「確定性安全閘」，必須由純程式碼把關，不可
# 交給機率性的 LLM。病人自填症狀是自由文字（「胸悶」「喘不過氣」「突然講不出話」），
# 舊版用「字串完全相等」比對形同虛設——除非恰好填「胸痛」二字才會觸發，否則一律
# falls through 到第二層 LLM。改為「同義詞 + 子字串」比對，讓口語也能觸發。
#
# 方向選擇：安全閘寧可過度觸發（誤報→多跑一趟急診）也不可漏報（missed red flag），
# 故子字串比對偏寬是刻意的取捨。

# canonical 急診類別 -> 同義詞 / 口語關鍵字（比對前統一去空白、轉小寫）。
_EMERGENCY_SYNONYMS: dict[str, list[str]] = {
    "胸痛": [
        "胸痛", "胸口痛", "胸悶", "胸口悶", "胸口緊", "胸口壓", "胸口悶痛",
        "心絞痛", "chestpain",
    ],
    "呼吸困難": [
        "呼吸困難", "喘不過氣", "喘不過來", "呼吸急促", "呼吸很喘", "吸不到氣",
        "呼吸不順", "無法呼吸", "快不能呼吸", "difficultybreathing",
        "shortnessofbreath", "can'tbreathe", "cannotbreathe",
    ],
    "意識不清": [
        "意識不清", "意識模糊", "昏迷", "昏倒", "暈倒", "失去意識", "叫不醒",
        "神智不清", "unconscious", "passedout",
    ],
    "大量出血": [
        "大量出血", "出血不止", "血流不止", "大出血", "噴血", "heavybleeding",
        "hemorrhage",
    ],
    "嚴重過敏": [
        "嚴重過敏", "過敏性休克", "全身起疹", "喉嚨腫", "臉腫", "呼吸道腫",
        "anaphylaxis",
    ],
    "中風症狀": [
        "中風", "臉歪", "嘴歪", "半邊無力", "單側無力", "口齒不清", "講話不清",
        "突然講不出話", "半身不遂", "stroke", "facedroop", "slurredspeech",
    ],
    "心跳異常": [
        "心律不整", "心悸", "心跳很快", "心跳很慢", "心跳亂", "心臟亂跳",
        "心跳異常", "palpitations", "irregularheartbeat",
    ],
}

# 對外保留正規類別清單（向後相容；其他模組可能引用）。
EMERGENCY_SYMPTOMS = list(_EMERGENCY_SYNONYMS.keys())

IMMUNOSUPPRESSED_FEVER_THRESHOLD = 38.0  # 免疫抑制患者發燒門檻（°C）


def _norm(s: str) -> str:
    """比對前正規化：去頭尾空白、移除所有空白、轉小寫（吃掉大小寫/空格差異）。"""
    return "".join((s or "").split()).lower()


def matched_emergency_symptoms(symptoms: list[str]) -> list[str]:
    """回傳「觸發急診紅旗」的原始輸入症狀（同義詞 + 子字串比對）。

    回傳原字串（非 canonical），讓前端顯示病人實際填的內容。
    """
    out: list[str] = []
    for s in symptoms or []:
        ns = _norm(s)
        if not ns:
            continue
        if any(kw in ns for keywords in _EMERGENCY_SYNONYMS.values() for kw in keywords):
            out.append(s)
    return out


def check_emergency(
    symptoms: list[str],
    is_immunosuppressed: bool = False,
    temperature: float = 0,
) -> bool:
    """第一層：規則引擎判斷是否直接升級急診警示（確定性，不走 LLM）。"""
    if matched_emergency_symptoms(symptoms):
        return True
    if is_immunosuppressed and (temperature or 0) >= IMMUNOSUPPRESSED_FEVER_THRESHOLD:
        return True
    return False
