import statistics

# 個人化基準線計算工具

def calculate_baseline(records: list[dict]) -> dict:
    """
    以前兩週數據建立個人化基準線
    records: [{"pain": 3, "medication_rate": 0.9, "emotion": 4}, ...]
    """
    if not records:
        return {}

    pain_scores = [r["pain"] for r in records if "pain" in r]
    emotion_scores = [r["emotion"] for r in records if "emotion" in r]
    med_rates = [r["medication_rate"] for r in records if "medication_rate" in r]

    return {
        "pain_mean": statistics.mean(pain_scores) if pain_scores else None,
        "pain_stdev": statistics.stdev(pain_scores) if len(pain_scores) > 1 else 0,
        "emotion_mean": statistics.mean(emotion_scores) if emotion_scores else None,
        "medication_rate_mean": statistics.mean(med_rates) if med_rates else None,
    }
