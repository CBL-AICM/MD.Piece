"""
五層遞進式症狀問卷 schema 與 LLM 結構化輸出處理。

Layer 1：今天整體感覺（一鍵跳出）
Layer 2：不舒服位置（人體輪廓圖前後兩面點選）
Layer 3：症狀描述（痛/麻/腫/緊/喘/暈 + 自由輸入）
Layer 4：嚴重程度（0-10 滑桿）
Layer 5：與平常比較（突然發生/慢慢變嚴重/跟平常差不多）
"""

from typing import List, Dict, Any

OVERALL_OPTIONS = [
    {"key": "good", "label": "今天整體還不錯", "score": 0},
    {"key": "ok", "label": "普通", "score": 1},
    {"key": "uncomfortable", "label": "有些不舒服", "score": 2},
    {"key": "bad", "label": "很不舒服", "score": 3},
]

# 人體輪廓圖點選座標（前後各一張）
# coordinates 為相對座標 (x%, y%)，前端依此繪製可點區
BODY_PARTS = {
    "front": [
        {"key": "head_front", "label": "頭部", "x": 50, "y": 6, "r": 7},
        {"key": "face", "label": "臉部", "x": 50, "y": 11, "r": 5},
        {"key": "neck_front", "label": "頸部", "x": 50, "y": 16, "r": 4},
        {"key": "chest", "label": "胸部", "x": 50, "y": 24, "r": 9},
        {"key": "upper_abdomen", "label": "上腹部", "x": 50, "y": 34, "r": 8},
        {"key": "lower_abdomen", "label": "下腹部", "x": 50, "y": 42, "r": 8},
        {"key": "left_shoulder", "label": "左肩", "x": 32, "y": 22, "r": 5},
        {"key": "right_shoulder", "label": "右肩", "x": 68, "y": 22, "r": 5},
        {"key": "left_arm", "label": "左上臂", "x": 26, "y": 32, "r": 5},
        {"key": "right_arm", "label": "右上臂", "x": 74, "y": 32, "r": 5},
        {"key": "left_forearm", "label": "左前臂", "x": 22, "y": 44, "r": 5},
        {"key": "right_forearm", "label": "右前臂", "x": 78, "y": 44, "r": 5},
        {"key": "left_hand", "label": "左手", "x": 18, "y": 54, "r": 4},
        {"key": "right_hand", "label": "右手", "x": 82, "y": 54, "r": 4},
        {"key": "left_thigh", "label": "左大腿", "x": 42, "y": 60, "r": 6},
        {"key": "right_thigh", "label": "右大腿", "x": 58, "y": 60, "r": 6},
        {"key": "left_knee", "label": "左膝", "x": 42, "y": 73, "r": 4},
        {"key": "right_knee", "label": "右膝", "x": 58, "y": 73, "r": 4},
        {"key": "left_calf", "label": "左小腿", "x": 42, "y": 84, "r": 5},
        {"key": "right_calf", "label": "右小腿", "x": 58, "y": 84, "r": 5},
        {"key": "left_foot", "label": "左腳", "x": 42, "y": 95, "r": 4},
        {"key": "right_foot", "label": "右腳", "x": 58, "y": 95, "r": 4},
    ],
    "back": [
        {"key": "head_back", "label": "後腦", "x": 50, "y": 6, "r": 7},
        {"key": "neck_back", "label": "後頸", "x": 50, "y": 16, "r": 4},
        {"key": "upper_back", "label": "上背", "x": 50, "y": 24, "r": 10},
        {"key": "mid_back", "label": "中背", "x": 50, "y": 34, "r": 9},
        {"key": "lower_back", "label": "下背/腰", "x": 50, "y": 42, "r": 9},
        {"key": "left_buttock", "label": "左臀", "x": 42, "y": 50, "r": 6},
        {"key": "right_buttock", "label": "右臀", "x": 58, "y": 50, "r": 6},
        {"key": "left_back_thigh", "label": "左大腿後", "x": 42, "y": 60, "r": 6},
        {"key": "right_back_thigh", "label": "右大腿後", "x": 58, "y": 60, "r": 6},
        {"key": "left_back_knee", "label": "左膝後", "x": 42, "y": 73, "r": 4},
        {"key": "right_back_knee", "label": "右膝後", "x": 58, "y": 73, "r": 4},
        {"key": "left_back_calf", "label": "左小腿後", "x": 42, "y": 84, "r": 5},
        {"key": "right_back_calf", "label": "右小腿後", "x": 58, "y": 84, "r": 5},
        {"key": "left_heel", "label": "左腳跟", "x": 42, "y": 95, "r": 4},
        {"key": "right_heel", "label": "右腳跟", "x": 58, "y": 95, "r": 4},
    ],
}

SYMPTOM_TYPES = [
    {"key": "pain", "label": "痛", "icon": "zap"},
    {"key": "numbness", "label": "麻", "icon": "circle-dot"},
    {"key": "swelling", "label": "腫", "icon": "circle"},
    {"key": "tightness", "label": "緊繃", "icon": "lock"},
    {"key": "shortness_breath", "label": "喘", "icon": "wind"},
    {"key": "dizziness", "label": "暈", "icon": "loader-2"},
    {"key": "burning", "label": "灼熱", "icon": "flame"},
    {"key": "itching", "label": "癢", "icon": "feather"},
    {"key": "weakness", "label": "無力", "icon": "battery-low"},
]

CHANGE_PATTERNS = [
    {"key": "sudden", "label": "突然發生", "weight": 2},
    {"key": "gradual_worse", "label": "慢慢變嚴重", "weight": 1.5},
    {"key": "same", "label": "跟平常差不多", "weight": 0.5},
    {"key": "improving", "label": "正在改善", "weight": 0},
]


def get_questionnaire_schema() -> Dict[str, Any]:
    """前端據此渲染五層問卷"""
    return {
        "layers": [
            {
                "step": 1,
                "id": "overall_feeling",
                "title": "今天整體感覺",
                "subtitle": "選一個最貼近的感受",
                "type": "single_choice",
                "options": OVERALL_OPTIONS,
                "skip_to_done_if": ["good", "ok"],
            },
            {
                "step": 2,
                "id": "body_locations",
                "title": "哪裡不舒服？",
                "subtitle": "點選身體不舒服的位置（可多選）",
                "type": "body_map",
                "front": BODY_PARTS["front"],
                "back": BODY_PARTS["back"],
            },
            {
                "step": 3,
                "id": "symptom_types",
                "title": "是什麼樣的不舒服？",
                "subtitle": "可以多選，最後也可以自己描述",
                "type": "multi_choice_with_text",
                "options": SYMPTOM_TYPES,
                "free_text_label": "其他描述（自由輸入，小禾會幫你整理）",
            },
            {
                "step": 4,
                "id": "severity",
                "title": "有多不舒服？",
                "subtitle": "0 = 完全沒感覺，10 = 痛到無法忍受",
                "type": "slider",
                "min": 0,
                "max": 10,
                "default": 3,
                "anchors": [
                    {"value": 0, "label": "沒感覺"},
                    {"value": 3, "label": "輕微"},
                    {"value": 5, "label": "明顯"},
                    {"value": 7, "label": "難受"},
                    {"value": 10, "label": "極痛"},
                ],
            },
            {
                "step": 5,
                "id": "change_pattern",
                "title": "跟平常比起來呢？",
                "subtitle": "幫醫師判斷症狀的變化趨勢",
                "type": "single_choice",
                "options": CHANGE_PATTERNS,
            },
        ]
    }


def calculate_severity_index(submission: Dict[str, Any]) -> float:
    """
    將五層問卷結果計算成單一嚴重度指數（0-10）。
    供基準線比對與分流判斷使用。
    """
    overall = submission.get("overall_feeling", "good")
    overall_score = next((o["score"] for o in OVERALL_OPTIONS if o["key"] == overall), 0)
    if overall in ("good", "ok"):
        return float(overall_score)

    severity = float(submission.get("severity", 0))
    pattern_key = submission.get("change_pattern", "same")
    pattern_weight = next(
        (p["weight"] for p in CHANGE_PATTERNS if p["key"] == pattern_key), 1.0
    )
    locations_count = len(submission.get("body_locations", []))
    location_factor = 1 + min(locations_count - 1, 3) * 0.1 if locations_count else 1

    index = severity * pattern_weight * location_factor / 2
    return round(min(max(index, 0), 10), 1)


def to_structured_summary(submission: Dict[str, Any]) -> str:
    """整理 5 層問卷為一段結構化中文摘要供 LLM 與報告使用"""
    parts = []
    overall = submission.get("overall_feeling")
    if overall:
        label = next((o["label"] for o in OVERALL_OPTIONS if o["key"] == overall), overall)
        parts.append(f"整體感覺：{label}")

    locs = submission.get("body_locations", [])
    if locs:
        all_parts = BODY_PARTS["front"] + BODY_PARTS["back"]
        labels = [next((b["label"] for b in all_parts if b["key"] == l), l) for l in locs]
        parts.append(f"位置：{', '.join(labels)}")

    types = submission.get("symptom_types", [])
    if types:
        labels = [next((t["label"] for t in SYMPTOM_TYPES if t["key"] == t_key), t_key) for t_key in types]
        parts.append(f"性質：{', '.join(labels)}")

    free = submission.get("free_text", "").strip()
    if free:
        parts.append(f"描述：{free}")

    sev = submission.get("severity")
    if sev is not None and overall not in ("good", "ok"):
        parts.append(f"嚴重度：{sev}/10")

    pattern = submission.get("change_pattern")
    if pattern:
        label = next((p["label"] for p in CHANGE_PATTERNS if p["key"] == pattern), pattern)
        parts.append(f"變化：{label}")

    return "；".join(parts) if parts else "今日無特殊回報"
