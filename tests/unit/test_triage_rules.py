"""Unit tests for backend/utils/triage_rules.py"""

from backend.utils.triage_rules import check_emergency, EMERGENCY_SYMPTOMS


class TestCheckEmergency:
    def test_emergency_symptom_detected(self):
        assert check_emergency(["胸痛"], False) is True

    def test_all_emergency_symptoms(self):
        for symptom in EMERGENCY_SYMPTOMS:
            assert check_emergency([symptom], False) is True, f"Failed for: {symptom}"

    def test_non_emergency_symptom(self):
        assert check_emergency(["頭痛"], False) is False

    def test_empty_symptoms(self):
        assert check_emergency([], False) is False

    def test_immunosuppressed_with_fever(self):
        assert check_emergency([], True, 38.5) is True

    def test_immunosuppressed_below_threshold(self):
        assert check_emergency([], True, 37.5) is False

    def test_immunosuppressed_at_threshold(self):
        assert check_emergency([], True, 38.0) is True

    def test_not_immunosuppressed_with_fever(self):
        assert check_emergency([], False, 39.0) is False

    def test_emergency_symptom_overrides_temperature(self):
        assert check_emergency(["呼吸困難"], False, 36.5) is True

    def test_multiple_symptoms_with_one_emergency(self):
        assert check_emergency(["頭痛", "胸痛", "咳嗽"], False) is True

    def test_multiple_non_emergency_symptoms(self):
        assert check_emergency(["頭痛", "咳嗽", "流鼻涕"], False) is False
