"""Unit tests for backend/services/ai_analyzer.py — fallback logic."""

from backend.services.ai_analyzer import _fallback_analysis


class TestFallbackAnalysis:
    def test_emergency_symptom_chest_pain(self):
        result = _fallback_analysis(["chest pain"])
        assert result["urgency"] == "emergency"

    def test_emergency_symptom_chinese(self):
        result = _fallback_analysis(["胸痛"])
        assert result["urgency"] == "emergency"

    def test_high_urgency_breathing(self):
        result = _fallback_analysis(["breathing difficulty"])
        assert result["urgency"] == "high"

    def test_low_urgency_default(self):
        result = _fallback_analysis(["頭痛"])
        assert result["urgency"] == "low"

    def test_response_structure(self):
        result = _fallback_analysis(["fever"])
        assert "conditions" in result
        assert "recommended_department" in result
        assert "urgency" in result
        assert "advice" in result
        assert "disclaimer" in result
        assert isinstance(result["conditions"], list)

    def test_symptoms_in_advice(self):
        result = _fallback_analysis(["headache", "nausea"])
        assert "headache" in result["advice"]
        assert "nausea" in result["advice"]

    def test_empty_symptoms(self):
        result = _fallback_analysis([])
        assert result["urgency"] == "low"
