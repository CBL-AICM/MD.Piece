"""個人化基準線單元測試"""
from backend.utils.baseline import (
    calculate_baseline,
    compare_to_baseline,
    detect_consecutive_low_emotion,
)


def test_calculate_baseline_empty():
    assert calculate_baseline([]) == {}


def test_calculate_baseline_basic():
    records = [
        {"pain": 3, "emotion": 4, "medication_rate": 1.0},
        {"pain": 4, "emotion": 3, "medication_rate": 0.8},
        {"pain": 2, "emotion": 5, "medication_rate": 1.0},
    ]
    b = calculate_baseline(records)
    assert b["pain_mean"] == 3
    assert b["emotion_mean"] == 4
    assert b["medication_rate_mean"] == 0.93
    assert b["data_points"] == 3


def test_compare_to_baseline_detects_deviation():
    baseline = {
        "pain_mean": 3,
        "pain_stdev": 1,
        "emotion_mean": 4,
        "known_locations": ["left_knee"],
        "data_points": 14,
    }
    today = {"pain": 6, "emotion": 1, "locations": ["left_knee", "chest"]}
    result = compare_to_baseline(today, baseline)
    assert result["deviation_pain"] == 3.0  # (6-3)/1 = 3σ
    assert result["new_locations"] == ["chest"]
    assert result["emotion_drop"] == 3.0
    assert result["has_baseline"] is True


def test_compare_to_baseline_handles_missing_data():
    baseline = {"data_points": 0}
    today = {"pain": 5, "locations": []}
    result = compare_to_baseline(today, baseline)
    assert result["deviation_pain"] is None
    assert result["new_locations"] == []
    assert result["has_baseline"] is False


def test_consecutive_low_emotion_max_streak():
    scores = [4, 1, 2, 1, 4, 2, 2, 2, 2]
    assert detect_consecutive_low_emotion(scores, threshold=2) == 4


def test_consecutive_low_emotion_no_lows():
    scores = [4, 5, 4, 3, 5]
    assert detect_consecutive_low_emotion(scores, threshold=2) == 0
