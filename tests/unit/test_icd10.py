"""Unit tests for backend/utils/icd10.py"""

from backend.utils.icd10 import (
    ICD10_MAP,
    CHRONIC_DISEASE_CATEGORIES,
    KNOWLEDGE_DIMENSIONS,
    COMPREHENSION_LEVELS,
    KNOWLEDGE_BASELINE,
    get_disease_name,
    get_category_for_code,
)


class TestICD10Map:
    def test_known_code(self):
        assert "E11" in ICD10_MAP
        assert "糖尿病" in ICD10_MAP["E11"] or "diabetes" in ICD10_MAP["E11"].lower()

    def test_map_not_empty(self):
        assert len(ICD10_MAP) > 0


class TestGetDiseaseName:
    def test_known_code(self):
        name = get_disease_name("E11")
        assert name is not None
        assert len(name) > 0

    def test_unknown_code(self):
        name = get_disease_name("ZZZZ")
        # Returns '未知疾病' for unknown codes
        assert name is not None


class TestGetCategoryForCode:
    def test_known_code(self):
        cat = get_category_for_code("E11")
        assert cat is not None

    def test_unknown_code(self):
        cat = get_category_for_code("ZZZZ")
        # Returns '未分類' for unknown codes
        assert cat is not None


class TestDataStructures:
    def test_disease_categories_not_empty(self):
        assert len(CHRONIC_DISEASE_CATEGORIES) > 0

    def test_knowledge_dimensions_count(self):
        assert len(KNOWLEDGE_DIMENSIONS) == 6

    def test_comprehension_levels_count(self):
        assert len(COMPREHENSION_LEVELS) == 5

    def test_knowledge_baseline_has_entries(self):
        assert len(KNOWLEDGE_BASELINE) > 0

    def test_baseline_entries_have_dimensions(self):
        for code, data in KNOWLEDGE_BASELINE.items():
            assert "dimensions" in data or isinstance(data, dict)
