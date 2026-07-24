#!/usr/bin/env python3
"""Tests for TeachSkill -- V4.2+ Roadmap P2-2.

Covers TeachSkill registration, teach()/assess()/curriculum()/run() methods,
8 topics, 3 user levels, 3 languages, and Iron Rules compliance.

Test IDs T1-T28 map directly to the task specification.
"""

import pytest

from skills import get_skill, list_skills
from skills.registry import BaseSkill
from skills.teach.handler import (
    BUILTIN_GLOSSARY,
    IRON_RULES,
    LIFECYCLE_PHASES,
    SEVEN_ROLES,
    SUB_SKILLS,
    TeachSkill,
)

pytestmark = pytest.mark.unit


# ===== T1: Skill registration and discovery =====


class TestTeachSkillRegistration:
    """T1: Skill registration and discovery via registry."""

    def test_teach_in_list_skills(self):
        """Verify: 'teach' appears in list_skills() output.

        Scenario: Registry scans skills/ directory for handler.py files.
        Expected: 'teach' is discovered and included in skill list.
        """
        skills = list_skills()
        assert "teach" in skills

    def test_get_skill_returns_teach_instance(self):
        """Verify: get_skill('teach') returns a TeachSkill instance."""
        skill = get_skill("teach")
        assert isinstance(skill, TeachSkill)

    def test_get_skill_returns_baseskill(self):
        """Verify: TeachSkill is a subclass of BaseSkill."""
        skill = get_skill("teach")
        assert isinstance(skill, BaseSkill)

    def test_teach_skill_inherits_baseskill(self):
        """Verify: TeachSkill class itself inherits from BaseSkill."""
        assert issubclass(TeachSkill, BaseSkill)


# ===== T2-T9: teach() topic coverage =====


class TestTeachTopics:
    """T2-T9: teach() returns correct content for each topic."""

    def test_t2_teach_overview_returns_complete_structure(self):
        """T2: Verify overview topic returns title/content/examples/exercises."""
        skill = TeachSkill()
        result = skill.teach("overview")
        assert result["topic"] == "overview"
        assert isinstance(result["title"], str) and len(result["title"]) > 0
        assert isinstance(result["content"], str) and len(result["content"]) > 0
        assert isinstance(result["examples"], list) and len(result["examples"]) >= 1
        assert isinstance(result["exercises"], list) and len(result["exercises"]) >= 1
        # Each example has scenario/code/explanation keys
        for ex in result["examples"]:
            assert "scenario" in ex
            assert "code" in ex
            assert "explanation" in ex

    def test_t3_teach_seven_roles_contains_all_roles(self):
        """T3: Verify seven_roles content includes all 7 role names."""
        skill = TeachSkill()
        result = skill.teach("seven_roles", lang="zh")
        content = result["content"]
        # All 7 role IDs must appear
        for role in SEVEN_ROLES:
            assert role["id"] in content, f"Role ID '{role['id']}' missing from content"
        # Chinese names should appear in zh mode
        for role in SEVEN_ROLES:
            assert role["name_zh"] in content, f"Role name_zh '{role['name_zh']}' missing"

    def test_t4_teach_lifecycle_contains_all_phases(self):
        """T4: Verify lifecycle content includes P1-P11."""
        skill = TeachSkill()
        result = skill.teach("lifecycle")
        content = result["content"]
        for phase in LIFECYCLE_PHASES:
            assert phase["phase"] in content, f"Phase '{phase['phase']}' missing from content"
        # Verify all 11 phases present
        assert len(LIFECYCLE_PHASES) == 11

    def test_t5_teach_iron_rules_contains_three_rules(self):
        """T5: Verify iron_rules content includes all 3 Iron Rules."""
        skill = TeachSkill()
        result = skill.teach("iron_rules", lang="zh")
        content = result["content"]
        for rule in IRON_RULES:
            assert rule["name_zh"] in content, f"Iron Rule '{rule['name_zh']}' missing"
        assert len(IRON_RULES) == 3

    def test_t6_teach_sub_skills_contains_six_skills(self):
        """T6: Verify sub_skills content includes all 6 sub-skill names."""
        skill = TeachSkill()
        result = skill.teach("sub_skills")
        content = result["content"]
        for s in SUB_SKILLS:
            assert s["name"] in content, f"Sub-skill '{s['name']}' missing from content"
            assert s["class"] in content, f"Class '{s['class']}' missing from content"
        assert len(SUB_SKILLS) == 6

    def test_t7_teach_glossary_returns_non_empty_terms(self):
        """T7: Verify glossary topic returns non-empty glossary_terms."""
        skill = TeachSkill()
        result = skill.teach("glossary")
        assert isinstance(result["glossary_terms"], list)
        # glossary topic loads all terms; should be > 0
        assert len(result["glossary_terms"]) >= 5
        for term in result["glossary_terms"]:
            assert "term" in term
            assert "definition" in term

    def test_t8_teach_quickstart_contains_install_and_dispatch(self):
        """T8: Verify quickstart content includes install and dispatch steps."""
        skill = TeachSkill()
        result = skill.teach("quickstart", lang="zh")
        content = result["content"]
        # Install step
        assert "pip install" in content or "pip" in content.lower()
        # Dispatch step
        assert "dispatch" in content.lower()
        # MultiAgentDispatcher reference
        assert "MultiAgentDispatcher" in content

    def test_t9_teach_full_curriculum_includes_all_topics(self):
        """T9: Verify full_curriculum content includes all individual topics."""
        skill = TeachSkill()
        result = skill.teach("full_curriculum", user_level="beginner", lang="zh")
        content = result["content"]
        # All individual topic titles (zh) should appear
        for topic in [
            "overview",
            "seven_roles",
            "lifecycle",
            "iron_rules",
            "sub_skills",
            "glossary",
            "quickstart",
        ]:
            from skills.teach.handler import TOPIC_TITLES

            assert TOPIC_TITLES[topic]["zh"] in content, f"Topic '{topic}' title missing"
        # estimated_minutes should be sum of individual topics (beginner: 5+15+20+18+12+8+10=88)
        assert result["estimated_minutes"] == 88


# ===== T10-T11: User level adjustments =====


class TestTeachUserLevels:
    """T10-T11: teach() adjusts content by user_level."""

    def test_t10_beginner_level_is_detailed(self):
        """T10: Verify beginner content is detailed (longer than advanced)."""
        skill = TeachSkill()
        beginner = skill.teach("overview", user_level="beginner", lang="zh")
        advanced = skill.teach("overview", user_level="advanced", lang="zh")
        # Beginner content should be longer (more detailed explanations)
        assert len(beginner["content"]) > len(advanced["content"])
        # Beginner should include extra explanatory sections
        assert "为什么" in beginner["content"] or "Why" in beginner["content"]

    def test_t11_advanced_level_is_concise(self):
        """T11: Verify advanced content is concise (shorter than beginner)."""
        skill = TeachSkill()
        beginner = skill.teach("seven_roles", user_level="beginner", lang="zh")
        advanced = skill.teach("seven_roles", user_level="advanced", lang="zh")
        assert len(advanced["content"]) <= len(beginner["content"])
        # Advanced should have fewer estimated minutes
        assert advanced["estimated_minutes"] < beginner["estimated_minutes"]


# ===== T12-T13: Language support =====


class TestTeachLanguages:
    """T12-T13: teach() supports zh/en/ja languages."""

    def test_t12_lang_zh_returns_chinese_content(self):
        """T12: Verify lang=zh returns Chinese content."""
        skill = TeachSkill()
        result = skill.teach("overview", lang="zh")
        assert result["lang"] == "zh"
        # Chinese characters should be present
        assert "概览" in result["title"] or "DevSquad" in result["title"]
        assert "对比" in result["content"] or "视角" in result["content"]

    def test_t13_lang_en_returns_english_content(self):
        """T13: Verify lang=en returns English content."""
        skill = TeachSkill()
        result = skill.teach("overview", lang="en")
        assert result["lang"] == "en"
        # English title
        assert "Overview" in result["title"]
        # English content markers
        assert "Single AI" in result["content"] or "Dimension" in result["content"]

    def test_lang_auto_defaults_to_zh(self):
        """Verify: lang='auto' defaults to 'zh'."""
        skill = TeachSkill()
        result = skill.teach("overview", lang="auto")
        assert result["lang"] == "zh"

    def test_lang_ja_returns_japanese_content(self):
        """Verify: lang=ja returns Japanese content."""
        skill = TeachSkill()
        result = skill.teach("overview", lang="ja")
        assert result["lang"] == "ja"
        # Japanese title contains 概要
        assert "概要" in result["title"]


# ===== T14-T16: Return structure and metadata =====


class TestTeachReturnStructure:
    """T14-T16: teach() return structure completeness and metadata."""

    def test_t14_return_structure_has_all_required_keys(self):
        """T14: Verify return dict has all required keys per spec."""
        skill = TeachSkill()
        result = skill.teach("overview")
        required_keys = {
            "topic",
            "user_level",
            "lang",
            "title",
            "content",
            "examples",
            "exercises",
            "next_topic",
            "glossary_terms",
            "estimated_minutes",
        }
        assert set(result.keys()) >= required_keys, f"Missing keys: {required_keys - set(result.keys())}"

    def test_t15_next_topic_recommendation_is_valid(self):
        """T15: Verify next_topic is a valid recommendation (or None for terminal)."""
        skill = TeachSkill()
        # overview -> seven_roles
        result = skill.teach("overview")
        assert result["next_topic"] == "seven_roles"
        # seven_roles -> lifecycle
        result = skill.teach("seven_roles")
        assert result["next_topic"] == "lifecycle"
        # quickstart -> None (terminal)
        result = skill.teach("quickstart")
        assert result["next_topic"] is None

    def test_t16_estimated_minutes_is_reasonable(self):
        """T16: Verify estimated_minutes is a positive integer within reasonable range."""
        skill = TeachSkill()
        for topic in ["overview", "seven_roles", "lifecycle", "iron_rules", "sub_skills", "glossary", "quickstart"]:
            for level in ["beginner", "intermediate", "advanced"]:
                result = skill.teach(topic, user_level=level)
                minutes = result["estimated_minutes"]
                assert isinstance(minutes, int)
                assert 1 <= minutes <= 120, f"{topic}/{level}: {minutes} out of range"
                # Beginner should take >= intermediate >= advanced
        begin = skill.teach("lifecycle", user_level="beginner")["estimated_minutes"]
        inter = skill.teach("lifecycle", user_level="intermediate")["estimated_minutes"]
        adv = skill.teach("lifecycle", user_level="advanced")["estimated_minutes"]
        assert begin >= inter >= adv


# ===== T17-T18: Error handling =====


class TestTeachErrorHandling:
    """T17-T18: teach() raises ValueError for invalid inputs."""

    def test_t17_unknown_topic_raises_valueerror(self):
        """T17: Verify unknown topic raises ValueError."""
        skill = TeachSkill()
        with pytest.raises(ValueError, match="Unknown topic"):
            skill.teach("nonexistent_topic")

    def test_t18_unknown_user_level_raises_valueerror(self):
        """T18: Verify unknown user_level raises ValueError."""
        skill = TeachSkill()
        with pytest.raises(ValueError, match="Unknown user_level"):
            skill.teach("overview", user_level="expert")

    def test_assess_unknown_topic_raises_valueerror(self):
        """Verify: assess() raises ValueError for unknown topic."""
        skill = TeachSkill()
        with pytest.raises(ValueError, match="Unknown topic"):
            skill.assess("nonexistent", {"q1": "x"})

    def test_curriculum_unknown_level_raises_valueerror(self):
        """Verify: curriculum() raises ValueError for unknown user_level."""
        skill = TeachSkill()
        with pytest.raises(ValueError, match="Unknown user_level"):
            skill.curriculum("guru")


# ===== T19-T23: assess() scoring =====


class TestTeachAssess:
    """T19-T23: assess() correctly scores user answers."""

    def test_t19_assess_perfect_score(self):
        """T19: Verify perfect score scenario (all correct)."""
        skill = TeachSkill()
        result = skill.assess("overview", {"q1": "7", "q2": "consensus", "q3": "mock"})
        assert result["score"] == 1.0
        assert result["passed"] is True
        assert len(result["correct_answers"]) == 3
        assert len(result["incorrect_answers"]) == 0

    def test_t20_assess_zero_score(self):
        """T20: Verify zero score scenario (all wrong)."""
        skill = TeachSkill()
        result = skill.assess("overview", {"q1": "wrong", "q2": "wrong", "q3": "wrong"})
        assert result["score"] == 0.0
        assert result["passed"] is False
        assert len(result["correct_answers"]) == 0
        assert len(result["incorrect_answers"]) == 3

    def test_t21_assess_partial_score(self):
        """T21: Verify partial score scenario (1/3 correct)."""
        skill = TeachSkill()
        result = skill.assess("overview", {"q1": "7", "q2": "wrong", "q3": "wrong"})
        # 1/3 = 0.3333
        assert result["score"] == pytest.approx(0.3333, abs=0.001)
        assert result["passed"] is False
        assert "q1" in result["correct_answers"]
        assert "q2" in result["incorrect_answers"]
        assert "q3" in result["incorrect_answers"]

    def test_t22_assess_passed_true_when_score_above_threshold(self):
        """T22: Verify passed=True when score >= 0.7 (2/3 = 0.6667 -> False; need 3/3)."""
        skill = TeachSkill()
        # 3/3 = 1.0 -> passed
        result = skill.assess("seven_roles", {"q1": "architect", "q2": "security", "q3": "tester"})
        assert result["score"] == 1.0
        assert result["passed"] is True

    def test_t23_assess_passed_false_when_score_below_threshold(self):
        """T23: Verify passed=False when score < 0.7."""
        skill = TeachSkill()
        # 1/3 = 0.333 -> not passed
        result = skill.assess("lifecycle", {"q1": "wrong", "q2": "pm", "q3": "wrong"})
        assert result["score"] < 0.7
        assert result["passed"] is False

    def test_assess_recommendations_are_non_empty(self):
        """Verify: recommendations list is non-empty."""
        skill = TeachSkill()
        result = skill.assess("overview", {"q1": "7", "q2": "consensus", "q3": "mock"})
        assert len(result["recommendations"]) >= 1

    def test_assess_case_insensitive_matching(self):
        """Verify: answer matching is case-insensitive."""
        skill = TeachSkill()
        result = skill.assess("overview", {"q1": "7", "q2": "CONSENSUS", "q3": "Mock"})
        assert result["score"] == 1.0


# ===== T24-T26: curriculum() =====


class TestTeachCurriculum:
    """T24-T26: curriculum() returns structured learning path."""

    def test_t24_beginner_returns_ordered_modules(self):
        """T24: Verify beginner curriculum returns ordered modules with prerequisites."""
        skill = TeachSkill()
        result = skill.curriculum("beginner")
        assert result["user_level"] == "beginner"
        assert isinstance(result["modules"], list)
        # Beginner should have all 7 modules
        assert len(result["modules"]) == 7
        # First module has no prerequisites
        assert result["modules"][0]["prerequisites"] == []
        # Subsequent modules have prerequisites
        for i in range(1, len(result["modules"])):
            assert len(result["modules"][i]["prerequisites"]) == i
        # Verify ordering: overview -> seven_roles -> lifecycle -> ...
        topics_in_order = [m["topic"] for m in result["modules"]]
        assert topics_in_order[0] == "overview"
        assert topics_in_order[1] == "seven_roles"
        # Each module has required keys
        for m in result["modules"]:
            assert "topic" in m
            assert "title" in m
            assert "estimated_minutes" in m
            assert "prerequisites" in m

    def test_t25_advanced_skips_basic_modules(self):
        """T25: Verify advanced curriculum skips basic modules (overview/glossary/quickstart)."""
        skill = TeachSkill()
        result = skill.curriculum("advanced")
        topics = [m["topic"] for m in result["modules"]]
        # Advanced should NOT include overview, glossary, quickstart
        assert "overview" not in topics
        assert "glossary" not in topics
        assert "quickstart" not in topics
        # Advanced should include the core technical topics
        assert "seven_roles" in topics
        assert "lifecycle" in topics
        assert "iron_rules" in topics
        assert "sub_skills" in topics
        # Fewer modules than beginner
        beginner = skill.curriculum("beginner")
        assert len(result["modules"]) < len(beginner["modules"])

    def test_t26_total_estimated_minutes_is_reasonable(self):
        """T26: Verify total_estimated_minutes is reasonable (sum of module minutes)."""
        skill = TeachSkill()
        for level in ["beginner", "intermediate", "advanced"]:
            result = skill.curriculum(level)
            total = result["total_estimated_minutes"]
            module_sum = sum(m["estimated_minutes"] for m in result["modules"])
            assert total == module_sum, f"{level}: total {total} != module sum {module_sum}"
            # Reasonable range: 15 min to 200 min
            assert 15 <= total <= 200, f"{level}: {total} out of range"

    def test_curriculum_graduation_criteria_non_empty(self):
        """Verify: graduation_criteria is non-empty list."""
        skill = TeachSkill()
        for level in ["beginner", "intermediate", "advanced"]:
            result = skill.curriculum(level)
            assert isinstance(result["graduation_criteria"], list)
            assert len(result["graduation_criteria"]) >= 3

    def test_curriculum_intermediate_includes_quickstart(self):
        """Verify: intermediate curriculum includes quickstart but not glossary."""
        skill = TeachSkill()
        result = skill.curriculum("intermediate")
        topics = [m["topic"] for m in result["modules"]]
        assert "quickstart" in topics
        assert "glossary" not in topics  # intermediate skips glossary


# ===== T27-T28: run() and info() =====


class TestTeachRunAndInfo:
    """T27-T28: run() delegates to teach(); info() returns correct metadata."""

    def test_t27_run_delegates_to_teach(self):
        """T27: Verify run() delegates to teach() with same arguments."""
        skill = TeachSkill()
        # run() with topic argument
        run_result = skill.run("overview", user_level="beginner", lang="zh")
        teach_result = skill.teach("overview", user_level="beginner", lang="zh")
        assert run_result == teach_result
        assert run_result["topic"] == "overview"

    def test_t27_run_with_default_args(self):
        """Verify: run() with no args uses teach() defaults."""
        skill = TeachSkill()
        result = skill.run()
        assert result["topic"] == "overview"
        assert result["user_level"] == "beginner"

    def test_t28_info_returns_correct_metadata(self):
        """T28: Verify info() returns name, description, version."""
        skill = TeachSkill()
        info = skill.info()
        assert info["name"] == "teach"
        assert "onboarding" in info["description"].lower() or "7-role" in info["description"].lower()
        assert "version" in info
        assert isinstance(info["version"], str)
        assert len(info["version"]) > 0

    def test_teach_skill_class_attributes(self):
        """Verify: TeachSkill class attributes are correctly set."""
        assert TeachSkill.name == "teach"
        assert "DevSquad onboarding" in TeachSkill.description
        assert "overview" in TeachSkill.TOPICS
        assert "full_curriculum" in TeachSkill.TOPICS
        assert len(TeachSkill.TOPICS) == 8
        assert "beginner" in TeachSkill.USER_LEVELS
        assert "auto" in TeachSkill.LANGS


# ===== Additional tests: glossary parsing and content validation =====


class TestTeachGlossaryParsing:
    """Additional: GLOSSARY.md parsing and built-in fallback."""

    def test_builtin_glossary_is_non_empty(self):
        """Verify: BUILTIN_GLOSSARY has canonical terms."""
        assert len(BUILTIN_GLOSSARY) >= 20
        terms = [t["term"] for t in BUILTIN_GLOSSARY]
        assert "Coordinator" in terms
        assert "Worker" in terms
        assert "Scratchpad" in terms
        assert "ConsensusEngine" in terms
        assert "Iron Rule" in terms

    def test_parse_glossary_md_handles_three_column_table(self):
        """Verify: _parse_glossary_md handles 3-column tables (term/def/source)."""
        sample = """# Glossary

| Term | Definition | Source |
|------|------------|--------|
| **Foo** | A foo thing | Bar |
| **Baz** | A baz thing | Qux |
"""
        parsed = TeachSkill._parse_glossary_md(sample)
        assert len(parsed) == 2
        assert parsed[0]["term"] == "Foo"
        assert parsed[0]["definition"] == "A foo thing"
        assert parsed[1]["term"] == "Baz"

    def test_parse_glossary_md_handles_chinese_header(self):
        """Verify: _parse_glossary_md handles Chinese table headers."""
        sample = """# 术语表

| 术语 | 定义 | 来源 |
|------|------|------|
| **Coordinator** | 全局编排器 | DevSquad |
"""
        parsed = TeachSkill._parse_glossary_md(sample)
        assert len(parsed) == 1
        assert parsed[0]["term"] == "Coordinator"
        assert parsed[0]["definition"] == "全局编排器"

    def test_load_glossary_terms_returns_list(self):
        """Verify: _load_glossary_terms returns a non-empty list."""
        skill = TeachSkill()
        terms = skill._load_glossary_terms()
        assert isinstance(terms, list)
        assert len(terms) > 0
        for t in terms:
            assert "term" in t
            assert "definition" in t


# ===== Additional tests: content correctness =====


class TestTeachContentCorrectness:
    """Additional: Verify content sourced from SKILL.md is canonical."""

    def test_seven_roles_data_matches_skill_md(self):
        """Verify: SEVEN_ROLES data matches SKILL.md canonical source (7 roles)."""
        assert len(SEVEN_ROLES) == 7
        role_ids = [r["id"] for r in SEVEN_ROLES]
        expected_ids = [
            "architect",
            "product-manager",
            "security",
            "tester",
            "solo-coder",
            "devops",
            "ui-designer",
        ]
        assert role_ids == expected_ids

    def test_lifecycle_phases_data_matches_skill_md(self):
        """Verify: LIFECYCLE_PHASES matches SKILL.md (11 phases P1-P11)."""
        assert len(LIFECYCLE_PHASES) == 11
        phase_ids = [p["phase"] for p in LIFECYCLE_PHASES]
        expected = [f"P{i}" for i in range(1, 12)]
        assert phase_ids == expected

    def test_iron_rules_data_matches_skill_md(self):
        """Verify: IRON_RULES matches SKILL.md (3 rules: Documentation/Test/Delivery)."""
        assert len(IRON_RULES) == 3
        rule_ids = [r["id"] for r in IRON_RULES]
        assert "documentation_first" in rule_ids
        assert "test_iron_rules" in rule_ids
        assert "delivery_workflow" in rule_ids

    def test_sub_skills_data_matches_skill_md(self):
        """Verify: SUB_SKILLS matches SKILL.md (6 atomic sub-skills)."""
        assert len(SUB_SKILLS) == 6
        skill_names = [s["name"] for s in SUB_SKILLS]
        expected = ["dispatch", "intent", "review", "security", "test", "retrospective"]
        assert skill_names == expected

    def test_teach_seven_roles_contains_triggers(self):
        """Verify: seven_roles content includes trigger keywords."""
        skill = TeachSkill()
        result = skill.teach("seven_roles", lang="en")
        content = result["content"]
        # Check a few trigger keywords
        assert "architecture" in content.lower()
        assert "security" in content.lower()
        assert "CI/CD" in content or "ci/cd" in content.lower()

    def test_teach_lifecycle_contains_templates(self):
        """Verify: lifecycle content includes all 5 templates."""
        skill = TeachSkill()
        result = skill.teach("lifecycle", lang="en")
        content = result["content"]
        for template in ["full", "backend", "frontend", "internal_tool", "minimal"]:
            assert template in content, f"Template '{template}' missing"

    def test_teach_iron_rules_contains_violation_consequences(self):
        """Verify: iron_rules content includes violation consequences."""
        skill = TeachSkill()
        result = skill.teach("iron_rules", lang="en")
        content = result["content"]
        assert "Violation Consequence" in content or "Violation" in content

    def test_teach_sub_skills_contains_wraps_info(self):
        """Verify: sub_skills content includes wraps (core module) info."""
        skill = TeachSkill()
        result = skill.teach("sub_skills", lang="en")
        content = result["content"]
        assert "MultiAgentDispatcher" in content
        assert "IntentWorkflowMapper" in content
        assert "FiveAxisConsensusEngine" in content


# ===== Additional tests: full curriculum integration =====


class TestTeachFullCurriculumIntegration:
    """Additional: full_curriculum integrates all topics correctly."""

    def test_full_curriculum_aggregates_examples(self):
        """Verify: full_curriculum aggregates examples from all topics."""
        skill = TeachSkill()
        result = skill.teach("full_curriculum", user_level="beginner", lang="zh")
        # Should have at least one example per topic (7 topics)
        assert len(result["examples"]) >= 7

    def test_full_curriculum_aggregates_exercises(self):
        """Verify: full_curriculum aggregates exercises from all topics."""
        skill = TeachSkill()
        result = skill.teach("full_curriculum", user_level="beginner", lang="zh")
        # Should have at least 3 exercises per topic (7 topics) = 21
        assert len(result["exercises"]) >= 21

    def test_full_curriculum_deduplicates_glossary(self):
        """Verify: full_curriculum deduplicates glossary terms."""
        skill = TeachSkill()
        result = skill.teach("full_curriculum", user_level="beginner", lang="zh")
        terms = [t["term"] for t in result["glossary_terms"]]
        # No duplicates
        assert len(terms) == len(set(terms)), "Duplicate glossary terms found"

    def test_full_curriculum_advanced_is_shorter_than_beginner(self):
        """Verify: advanced full_curriculum is shorter than beginner."""
        skill = TeachSkill()
        beginner = skill.teach("full_curriculum", user_level="beginner")
        advanced = skill.teach("full_curriculum", user_level="advanced")
        assert advanced["estimated_minutes"] < beginner["estimated_minutes"]
        assert len(advanced["content"]) < len(beginner["content"])
