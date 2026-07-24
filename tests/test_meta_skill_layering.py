#!/usr/bin/env python3
"""Tests for MetaSkillGrouper (ROADMAP P2-UI-3: Skillifier Meta-skills 分层架构).

Covers the 6-layer meta-skill architecture that groups DevSquad's 8 flat
sub-skills (dispatch/intent/review/retrospective/security/test/prototype/teach)
into 6 functional layers inspired by taste-skill's meta-skill分层理念.

Test groups:
    T1-T2   : META_LAYERS structure
    T3-T11  : group_skills() behavior
    T12-T13 : get_layer()
    T14-T17 : get_progressive_disclosure()
    T18-T20 : suggest_layer_for_skill()
    T21-T24 : audit_layering()
    T25     : edge cases (empty/unknown/duplicate skill_names)
"""

from __future__ import annotations

import pytest

from scripts.collaboration.meta_skill_layering import MetaSkillGrouper

# Known DevSquad sub-skills (must match skills/ directory).
_ALL_SUBSKILLS = [
    "dispatch",
    "intent",
    "review",
    "retrospective",
    "security",
    "test",
    "prototype",
    "teach",
]


@pytest.fixture
def grouper() -> MetaSkillGrouper:
    """Fresh MetaSkillGrouper instance for each test."""
    return MetaSkillGrouper()


# ============================================================
# T1-T2: META_LAYERS structure
# ============================================================


class TestMetaLayersStructure:
    """Validate the META_LAYERS class constant."""

    def test_t1_meta_layers_contains_exactly_6_layers(self, grouper: MetaSkillGrouper) -> None:
        """T1: META_LAYERS contains exactly 6 layers."""
        assert len(grouper.META_LAYERS) == 6
        expected_layers = {"foundation", "orchestration", "quality", "evolution", "governance", "integration"}
        assert set(grouper.META_LAYERS.keys()) == expected_layers

    def test_t2_each_layer_has_required_fields(self, grouper: MetaSkillGrouper) -> None:
        """T2: Each layer has description/skills/disclosure_level with correct types."""
        for layer_name, info in grouper.META_LAYERS.items():
            assert "description" in info, f"{layer_name} missing description"
            assert isinstance(info["description"], str)
            assert len(info["description"]) > 0
            assert "skills" in info, f"{layer_name} missing skills"
            assert isinstance(info["skills"], list)
            assert "disclosure_level" in info, f"{layer_name} missing disclosure_level"
            assert isinstance(info["disclosure_level"], int)
        # disclosure_levels must be 1-6 unique
        levels = [info["disclosure_level"] for info in grouper.META_LAYERS.values()]
        assert sorted(levels) == [1, 2, 3, 4, 5, 6]


# ============================================================
# T3-T11: group_skills()
# ============================================================


class TestGroupSkills:
    """Validate group_skills() grouping logic."""

    def test_t3_default_reads_all_skills_from_registry(self, grouper: MetaSkillGrouper) -> None:
        """T3: group_skills() with no args reads all skills (>= 8 known sub-skills)."""
        result = grouper.group_skills()
        layers = result["layers"]
        all_actual: list[str] = []
        for info in layers.values():
            all_actual.extend(info["actual_skills"])
        # The 8 known sub-skills should all appear (registry may return more).
        for skill in _ALL_SUBSKILLS:
            assert skill in all_actual, f"{skill} not grouped from registry"

    def test_t4_returns_layers_dict(self, grouper: MetaSkillGrouper) -> None:
        """T4: group_skills() returns a dict containing the 'layers' key."""
        result = grouper.group_skills()
        assert isinstance(result, dict)
        assert "layers" in result
        assert "ungrouped" in result
        assert "coverage" in result
        assert isinstance(result["layers"], dict)

    def test_t5_foundation_layer_contains_intent_and_teach(self, grouper: MetaSkillGrouper) -> None:
        """T5: foundation layer contains intent and teach."""
        result = grouper.group_skills(_ALL_SUBSKILLS)
        foundation = result["layers"]["foundation"]
        assert "intent" in foundation["actual_skills"]
        assert "teach" in foundation["actual_skills"]

    def test_t6_orchestration_layer_contains_dispatch(self, grouper: MetaSkillGrouper) -> None:
        """T6: orchestration layer contains dispatch."""
        result = grouper.group_skills(_ALL_SUBSKILLS)
        orchestration = result["layers"]["orchestration"]
        assert "dispatch" in orchestration["actual_skills"]

    def test_t7_quality_layer_contains_review_test_security(self, grouper: MetaSkillGrouper) -> None:
        """T7: quality layer contains review, test, security."""
        result = grouper.group_skills(_ALL_SUBSKILLS)
        quality = result["layers"]["quality"]
        for skill in ("review", "test", "security"):
            assert skill in quality["actual_skills"], f"{skill} not in quality layer"

    def test_t8_evolution_layer_contains_retrospective_prototype(self, grouper: MetaSkillGrouper) -> None:
        """T8: evolution layer contains retrospective and prototype."""
        result = grouper.group_skills(_ALL_SUBSKILLS)
        evolution = result["layers"]["evolution"]
        assert "retrospective" in evolution["actual_skills"]
        assert "prototype" in evolution["actual_skills"]

    def test_t9_governance_and_integration_layers_are_empty(self, grouper: MetaSkillGrouper) -> None:
        """T9: governance and integration layers are empty (reserved for future)."""
        result = grouper.group_skills(_ALL_SUBSKILLS)
        assert result["layers"]["governance"]["actual_skills"] == []
        assert result["layers"]["integration"]["actual_skills"] == []

    def test_t10_coverage_at_least_80_percent(self, grouper: MetaSkillGrouper) -> None:
        """T10: coverage >= 0.8 (all 8 known skills grouped → 1.0)."""
        result = grouper.group_skills(_ALL_SUBSKILLS)
        assert result["coverage"] >= 0.8
        # With exactly the 8 known skills, coverage should be 1.0.
        assert result["coverage"] == 1.0

    def test_t11_ungrouped_list_is_empty_for_known_skills(self, grouper: MetaSkillGrouper) -> None:
        """T11: ungrouped list is empty when only known sub-skills are supplied."""
        result = grouper.group_skills(_ALL_SUBSKILLS)
        assert result["ungrouped"] == []


# ============================================================
# T12-T13: get_layer()
# ============================================================


class TestGetLayer:
    """Validate get_layer() retrieval and error handling."""

    def test_t12_get_layer_returns_details(self, grouper: MetaSkillGrouper) -> None:
        """T12: get_layer() returns description/skills/disclosure_level for a known layer."""
        layer = grouper.get_layer("quality")
        assert layer["description"] == "Quality assurance — review, test, security"
        assert layer["skills"] == ["review", "test", "security"]
        assert layer["disclosure_level"] == 3

    def test_t13_get_layer_unknown_raises_value_error(self, grouper: MetaSkillGrouper) -> None:
        """T13: get_layer() raises ValueError for an unknown layer name."""
        with pytest.raises(ValueError, match="Unknown meta-skill layer"):
            grouper.get_layer("nonexistent-layer")


# ============================================================
# T14-T17: get_progressive_disclosure()
# ============================================================


class TestProgressiveDisclosure:
    """Validate progressive disclosure by user level."""

    def test_t14_beginner_returns_levels_1_and_2(self, grouper: MetaSkillGrouper) -> None:
        """T14: beginner level shows disclosure_level 1-2 (foundation + orchestration)."""
        layers = grouper.get_progressive_disclosure("beginner")
        shown = [entry for entry in layers if entry["show_to_user"]]
        shown_levels = {entry["disclosure_level"] for entry in shown}
        assert shown_levels == {1, 2}
        hidden = [entry for entry in layers if not entry["show_to_user"]]
        hidden_levels = {entry["disclosure_level"] for entry in hidden}
        assert hidden_levels == {3, 4, 5, 6}

    def test_t15_intermediate_returns_levels_1_to_4(self, grouper: MetaSkillGrouper) -> None:
        """T15: intermediate level shows disclosure_level 1-4."""
        layers = grouper.get_progressive_disclosure("intermediate")
        shown_levels = {entry["disclosure_level"] for entry in layers if entry["show_to_user"]}
        assert shown_levels == {1, 2, 3, 4}

    def test_t16_advanced_returns_all_levels(self, grouper: MetaSkillGrouper) -> None:
        """T16: advanced level shows all 6 disclosure levels."""
        layers = grouper.get_progressive_disclosure("advanced")
        shown_levels = {entry["disclosure_level"] for entry in layers if entry["show_to_user"]}
        assert shown_levels == {1, 2, 3, 4, 5, 6}

    def test_t17_returns_ordered_list_by_disclosure_level(self, grouper: MetaSkillGrouper) -> None:
        """T17: get_progressive_disclosure() returns list ordered by disclosure_level."""
        layers = grouper.get_progressive_disclosure("advanced")
        levels = [entry["disclosure_level"] for entry in layers]
        assert levels == sorted(levels)
        assert levels == [1, 2, 3, 4, 5, 6]


# ============================================================
# T18-T20: suggest_layer_for_skill()
# ============================================================


class TestSuggestLayer:
    """Validate keyword-based layer suggestion."""

    def test_t18_quality_keywords_suggest_quality_layer(self, grouper: MetaSkillGrouper) -> None:
        """T18: description containing 'test' or 'review' → quality layer."""
        assert grouper.suggest_layer_for_skill("unit-test", "Run unit test for the module") == "quality"
        assert grouper.suggest_layer_for_skill("code-review", "Perform code review on PR") == "quality"
        assert grouper.suggest_layer_for_skill("vuln-scan", "Scan for security vulnerabilities") == "quality"

    def test_t19_orchestration_keywords_suggest_orchestration_layer(self, grouper: MetaSkillGrouper) -> None:
        """T19: description containing 'dispatch' or 'coordinate' → orchestration layer."""
        assert grouper.suggest_layer_for_skill("multi-dispatch", "Dispatch tasks to multiple roles") == "orchestration"
        assert grouper.suggest_layer_for_skill("coordinator", "Coordinate work across team") == "orchestration"

    def test_t20_unknown_description_defaults_to_foundation(self, grouper: MetaSkillGrouper) -> None:
        """T20: description with no matching keywords → foundation (default layer)."""
        result = grouper.suggest_layer_for_skill("random-skill", "A completely unrelated description with no keywords")
        assert result == "foundation"


# ============================================================
# T21-T24: audit_layering()
# ============================================================


class TestAuditLayering:
    """Validate audit_layering() reporting."""

    def test_t21_total_skills_positive(self, grouper: MetaSkillGrouper) -> None:
        """T21: audit_layering() reports total_skills > 0 (8 known sub-skills)."""
        audit = grouper.audit_layering()
        assert audit["total_skills"] > 0
        assert audit["total_skills"] >= 8

    def test_t22_coverage_percentage_in_valid_range(self, grouper: MetaSkillGrouper) -> None:
        """T22: coverage_percentage is within [0, 100]."""
        audit = grouper.audit_layering()
        assert 0.0 <= audit["coverage_percentage"] <= 100.0
        # All 8 known skills are mapped → 100%.
        assert audit["coverage_percentage"] == 100.0

    def test_t23_empty_layers_include_governance_and_integration(self, grouper: MetaSkillGrouper) -> None:
        """T23: empty_layers includes governance and integration (reserved layers)."""
        audit = grouper.audit_layering()
        assert "governance" in audit["empty_layers"]
        assert "integration" in audit["empty_layers"]

    def test_t24_recommendations_non_empty(self, grouper: MetaSkillGrouper) -> None:
        """T24: recommendations list is non-empty (at least one recommendation)."""
        audit = grouper.audit_layering()
        assert isinstance(audit["recommendations"], list)
        assert len(audit["recommendations"]) > 0


# ============================================================
# T25: Edge cases (empty/unknown/duplicate skill_names)
# ============================================================


class TestEdgeCases:
    """Validate edge-case handling for group_skills()."""

    def test_t25a_empty_skill_names_returns_zero_coverage(self, grouper: MetaSkillGrouper) -> None:
        """T25a: empty skill_names list → coverage 0.0, no actual_skills, all layers present."""
        result = grouper.group_skills([])
        assert result["coverage"] == 0.0
        assert result["ungrouped"] == []
        # All 6 layers still present (structural completeness).
        assert len(result["layers"]) == 6
        for layer_info in result["layers"].values():
            assert layer_info["actual_skills"] == []

    def test_t25b_unknown_skill_goes_to_ungrouped(self, grouper: MetaSkillGrouper) -> None:
        """T25b: unknown skill name appears in ungrouped list."""
        result = grouper.group_skills(["intent", "totally-unknown-skill"])
        assert "totally-unknown-skill" in result["ungrouped"]
        assert "intent" in result["layers"]["foundation"]["actual_skills"]
        # coverage = 1 grouped / 2 total = 0.5
        assert result["coverage"] == 0.5

    def test_t25c_duplicate_skill_names_are_deduplicated(self, grouper: MetaSkillGrouper) -> None:
        """T25c: duplicate skill names are de-duplicated (no double-counting)."""
        result = grouper.group_skills(["intent", "intent", "teach", "teach"])
        foundation = result["layers"]["foundation"]
        # Each skill appears exactly once in actual_skills.
        assert foundation["actual_skills"].count("intent") == 1
        assert foundation["actual_skills"].count("teach") == 1
        assert result["coverage"] == 1.0
