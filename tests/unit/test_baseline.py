"""Unit tests for backend/utils/baseline.py"""

from backend.utils.baseline import calculate_baseline


class TestCalculateBaseline:
    def test_empty_records(self):
        result = calculate_baseline([])
        assert result == {}

    def test_single_record(self):
        records = [{"pain": 3, "emotion": 4, "medication_rate": 0.9}]
        result = calculate_baseline(records)
        assert result["pain_mean"] == 3.0
        assert result["emotion_mean"] == 4.0
        assert result["medication_rate_mean"] == 0.9
        assert result["pain_stdev"] == 0  # single record → stdev=0

    def test_multiple_records(self):
        records = [
            {"pain": 2, "emotion": 3, "medication_rate": 0.8},
            {"pain": 4, "emotion": 5, "medication_rate": 1.0},
        ]
        result = calculate_baseline(records)
        assert result["pain_mean"] == 3.0
        assert result["emotion_mean"] == 4.0
        assert result["medication_rate_mean"] == 0.9

    def test_partial_records(self):
        records = [
            {"pain": 5},
            {"emotion": 3},
        ]
        result = calculate_baseline(records)
        assert result["pain_mean"] == 5.0
        assert result["emotion_mean"] == 3.0
        assert result["medication_rate_mean"] is None

    def test_missing_all_fields(self):
        records = [{"other": 1}]
        result = calculate_baseline(records)
        assert result["pain_mean"] is None
        assert result["emotion_mean"] is None
        assert result["medication_rate_mean"] is None
