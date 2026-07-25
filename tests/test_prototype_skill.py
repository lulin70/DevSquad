#!/usr/bin/env python3
"""Tests for PrototypeSkill — ROADMAP P2-1.

Covers registration, generate(), validate(), run(), info(), edge cases,
and error handling. 21 test methods total (T1-T21).

Run with: python -m pytest tests/test_prototype_skill.py -v
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from skills._version import __version__ as _SKILLS_VERSION
from skills.prototype.handler import PrototypeSkill
from skills.registry import get_skill, list_skills


class TestPrototypeSkillRegistration(unittest.TestCase):
    """T1: skill registration and discovery."""

    def setUp(self) -> None:
        # Clear the registry cache so list_skills() re-scans the skills/ dir.
        import skills.registry as reg_module

        reg_module._AVAILABLE_SKILLS.clear()

    def test_t1_skill_registered_and_discoverable(self) -> None:
        skills = list_skills()
        self.assertIn("prototype", skills)
        skill = get_skill("prototype")
        self.assertIsInstance(skill, PrototypeSkill)


class TestPrototypeSkillGenerateTypes(unittest.TestCase):
    """T2-T5: generate() prototype type detection."""

    def setUp(self) -> None:
        self.skill = PrototypeSkill()

    def test_t2_generate_ui_type(self) -> None:
        result = self.skill.generate("用户喜欢单击结账界面", prototype_type="auto")
        self.assertEqual(result["prototype_type"], "ui")
        paths = [f["path"] for f in result["files"]]
        # UI type should include at least one .py and one .html file.
        self.assertTrue(any(p.endswith(".py") for p in paths), f"No .py in {paths}")
        self.assertTrue(any(p.endswith(".html") for p in paths), f"No .html in {paths}")

    def test_t3_generate_logic_type(self) -> None:
        result = self.skill.generate("验证排序算法的性能", prototype_type="auto")
        self.assertEqual(result["prototype_type"], "logic")
        paths = [f["path"] for f in result["files"]]
        self.assertTrue(any("logic" in p for p in paths), f"No logic file in {paths}")

    def test_t4_generate_api_type(self) -> None:
        result = self.skill.generate("提供用户查询的 API 接口", prototype_type="auto")
        self.assertEqual(result["prototype_type"], "api")
        paths = [f["path"] for f in result["files"]]
        self.assertTrue(any("api" in p for p in paths), f"No api file in {paths}")

    def test_t5_generate_auto_type_default(self) -> None:
        # No keyword match — should fall back to "logic".
        result = self.skill.generate("A generic hypothesis with no keywords", prototype_type="auto")
        self.assertEqual(result["prototype_type"], "logic")


class TestPrototypeSkillGenerateConstraints(unittest.TestCase):
    """T6-T8: generate() constraints (max_files, max_lines, vertical_slice)."""

    def setUp(self) -> None:
        self.skill = PrototypeSkill()

    def test_t6_max_files_limit(self) -> None:
        result = self.skill.generate(
            "Test hypothesis",
            prototype_type="ui",
            constraints={"max_files": 2},
        )
        self.assertLessEqual(len(result["files"]), 2)

    def test_t7_max_lines_per_file_limit(self) -> None:
        result = self.skill.generate(
            "Test hypothesis",
            prototype_type="ui",
            constraints={"max_files": 3, "max_lines_per_file": 5},
        )
        for f in result["files"]:
            line_count = len(f["content"].splitlines())
            self.assertLessEqual(
                line_count,
                5,
                f"File {f['path']} has {line_count} lines, expected <= 5",
            )

    def test_t8_vertical_slice_calls_micro_task_planner(self) -> None:
        with patch(
            "scripts.collaboration.micro_task_planner.MicroTaskPlanner"
        ) as mock_planner_cls:
            mock_planner = MagicMock()
            mock_planner_cls.return_value = mock_planner
            # plan() returns a MagicMock; .to_dict() returns a dict.
            mock_plan = MagicMock()
            mock_plan.micro_tasks = []
            mock_plan.to_dict.return_value = {"task_id": "mock", "micro_tasks": []}
            mock_planner.plan.return_value = mock_plan

            self.skill.generate("Test hypothesis", prototype_type="logic")

            self.assertTrue(
                mock_planner.plan.called,
                "MicroTaskPlanner.plan() should be called when vertical_slice=True",
            )

    def test_t8b_vertical_slice_disabled_skips_planner(self) -> None:
        with patch(
            "scripts.collaboration.micro_task_planner.MicroTaskPlanner"
        ) as mock_planner_cls:
            result = self.skill.generate(
                "Test hypothesis",
                prototype_type="logic",
                constraints={"vertical_slice": False},
            )
            self.assertFalse(
                mock_planner_cls.called,
                "MicroTaskPlanner should NOT be instantiated when vertical_slice=False",
            )
            self.assertIsNone(result["vertical_slice_plan"])


class TestPrototypeSkillGenerateStructure(unittest.TestCase):
    """T9-T13: generate() return structure completeness."""

    def setUp(self) -> None:
        self.skill = PrototypeSkill()
        self.result = self.skill.generate("Test hypothesis", prototype_type="logic")

    def test_t9_return_structure_complete(self) -> None:
        required_keys = {
            "hypothesis",
            "prototype_type",
            "files",
            "validation_steps",
            "estimated_effort_minutes",
            "assumptions_made",
            "next_steps",
            "vertical_slice_plan",
        }
        self.assertTrue(required_keys.issubset(self.result.keys()))
        # Each file dict should have path, content, purpose.
        for f in self.result["files"]:
            self.assertIn("path", f)
            self.assertIn("content", f)
            self.assertIn("purpose", f)

    def test_t10_validation_steps_non_empty_and_executable(self) -> None:
        steps = self.result["validation_steps"]
        self.assertIsInstance(steps, list)
        self.assertGreater(len(steps), 0)
        # Each step should be a non-empty string (executable instruction).
        for step in steps:
            self.assertIsInstance(step, str)
            self.assertGreater(len(step.strip()), 0)

    def test_t11_estimated_effort_in_2_to_5_range(self) -> None:
        effort = self.result["estimated_effort_minutes"]
        self.assertIsInstance(effort, int)
        self.assertGreaterEqual(effort, 2)
        self.assertLessEqual(effort, 5)

    def test_t12_assumptions_made_is_list(self) -> None:
        assumptions = self.result["assumptions_made"]
        self.assertIsInstance(assumptions, list)
        self.assertGreater(len(assumptions), 0)
        for a in assumptions:
            self.assertIsInstance(a, str)

    def test_t13_next_steps_is_list(self) -> None:
        next_steps = self.result["next_steps"]
        self.assertIsInstance(next_steps, list)
        self.assertGreater(len(next_steps), 0)
        for s in next_steps:
            self.assertIsInstance(s, str)


class TestPrototypeSkillValidate(unittest.TestCase):
    """T14-T17: validate() confirmed/refuted/confidence/proceed logic."""

    def setUp(self) -> None:
        self.skill = PrototypeSkill()
        self.prototype_result = self.skill.generate(
            "Users prefer single-click checkout", prototype_type="ui"
        )

    def test_t14_validate_hypothesis_confirmed_true(self) -> None:
        outcome = {
            "user_feedback": "Yes, I like the single-click flow",
            "metrics": {"completion_rate": 0.85, "satisfaction": 0.9},
            "observed_behavior": "Users completed checkout faster",
        }
        verdict = self.skill.validate(self.prototype_result, outcome)
        self.assertTrue(verdict["hypothesis_confirmed"])
        self.assertTrue(verdict["should_proceed_to_full_impl"])
        self.assertGreater(len(verdict["evidence"]), 0)

    def test_t15_validate_hypothesis_confirmed_false(self) -> None:
        outcome = {
            "user_feedback": "No, I dislike the bad interface",
            "metrics": {"completion_rate": 0.2, "abandonment": 0.8},
            "observed_behavior": "Users abandoned the flow",
        }
        verdict = self.skill.validate(self.prototype_result, outcome)
        self.assertFalse(verdict["hypothesis_confirmed"])
        self.assertFalse(verdict["should_proceed_to_full_impl"])

    def test_t16_validate_confidence_in_range(self) -> None:
        # Confirmed case.
        outcome_yes = {
            "user_feedback": "yes good",
            "metrics": {},
            "observed_behavior": "",
        }
        verdict_yes = self.skill.validate(self.prototype_result, outcome_yes)
        self.assertGreaterEqual(verdict_yes["confidence"], 0.0)
        self.assertLessEqual(verdict_yes["confidence"], 1.0)

        # Refuted case.
        outcome_no = {
            "user_feedback": "no bad",
            "metrics": {},
            "observed_behavior": "",
        }
        verdict_no = self.skill.validate(self.prototype_result, outcome_no)
        self.assertGreaterEqual(verdict_no["confidence"], 0.0)
        self.assertLessEqual(verdict_no["confidence"], 1.0)

        # Empty outcome.
        verdict_empty = self.skill.validate(self.prototype_result, {})
        self.assertGreaterEqual(verdict_empty["confidence"], 0.0)
        self.assertLessEqual(verdict_empty["confidence"], 1.0)

    def test_t17_validate_should_proceed_logic(self) -> None:
        # Strong positive — should proceed.
        strong = {
            "user_feedback": "yes like good prefer",
            "metrics": {"success_rate": 0.95},
            "observed_behavior": "",
        }
        verdict_strong = self.skill.validate(self.prototype_result, strong)
        self.assertTrue(verdict_strong["hypothesis_confirmed"])
        self.assertTrue(verdict_strong["should_proceed_to_full_impl"])

        # Weak positive (low confidence due to mixed signals) — should not proceed.
        # 1 positive + 1 negative => confirmed=False, so should_proceed=False.
        weak = {
            "user_feedback": "yes bad",
            "metrics": {},
            "observed_behavior": "",
        }
        verdict_weak = self.skill.validate(self.prototype_result, weak)
        self.assertFalse(verdict_weak["should_proceed_to_full_impl"])

        # Refuted — should not proceed.
        refuted = {
            "user_feedback": "no dislike bad",
            "metrics": {"failure_rate": 0.9},
            "observed_behavior": "",
        }
        verdict_refuted = self.skill.validate(self.prototype_result, refuted)
        self.assertFalse(verdict_refuted["should_proceed_to_full_impl"])


class TestPrototypeSkillRunAndInfo(unittest.TestCase):
    """T18-T19: run() delegation and info() metadata."""

    def setUp(self) -> None:
        self.skill = PrototypeSkill()

    def test_t18_run_delegates_to_generate(self) -> None:
        result = self.skill.run("Test hypothesis", prototype_type="logic")
        self.assertEqual(result["hypothesis"], "Test hypothesis")
        self.assertEqual(result["prototype_type"], "logic")
        # run() should produce the same structure as generate().
        required_keys = {"hypothesis", "prototype_type", "files", "validation_steps"}
        self.assertTrue(required_keys.issubset(result.keys()))

    def test_t19_info_returns_correct_metadata(self) -> None:
        info = self.skill.info()
        self.assertEqual(info["name"], "prototype")
        self.assertIn("prototype", info["description"].lower())
        # Version should match the skills layer version (dynamic, sourced
        # from scripts/collaboration/_version.py via skills/_version.py).
        self.assertEqual(info["version"], _SKILLS_VERSION)


class TestPrototypeSkillEdgeCases(unittest.TestCase):
    """T20: edge cases (empty hypothesis, long hypothesis, constraints=None)."""

    def setUp(self) -> None:
        self.skill = PrototypeSkill()

    def test_t20a_empty_hypothesis_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.skill.generate("", prototype_type="auto")
        with self.assertRaises(ValueError):
            self.skill.generate("   ", prototype_type="auto")

    def test_t20b_long_hypothesis_truncated(self) -> None:
        long_hyp = "a" * 3000
        result = self.skill.generate(long_hyp, prototype_type="logic")
        # Should be truncated to _MAX_HYPOTHESIS_LEN (2000).
        self.assertLessEqual(len(result["hypothesis"]), 2000)

    def test_t20c_constraints_none_uses_defaults(self) -> None:
        result = self.skill.generate("Test hypothesis", prototype_type="logic", constraints=None)
        self.assertLessEqual(len(result["files"]), PrototypeSkill.DEFAULT_MAX_FILES)
        for f in result["files"]:
            self.assertLessEqual(
                len(f["content"].splitlines()),
                PrototypeSkill.DEFAULT_MAX_LINES_PER_FILE,
            )
        # vertical_slice defaults to True.
        self.assertIsNotNone(result["vertical_slice_plan"])


class TestPrototypeSkillErrors(unittest.TestCase):
    """T21: error handling (unsupported prototype_type, negative max_files)."""

    def setUp(self) -> None:
        self.skill = PrototypeSkill()

    def test_t21a_unsupported_prototype_type_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.skill.generate("Test hypothesis", prototype_type="database")
        with self.assertRaises(ValueError):
            self.skill.generate("Test hypothesis", prototype_type="")

    def test_t21b_negative_max_files_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.skill.generate(
                "Test hypothesis",
                prototype_type="logic",
                constraints={"max_files": -1},
            )

    def test_t21c_zero_max_files_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.skill.generate(
                "Test hypothesis",
                prototype_type="logic",
                constraints={"max_files": 0},
            )

    def test_t21d_negative_max_lines_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.skill.generate(
                "Test hypothesis",
                prototype_type="logic",
                constraints={"max_lines_per_file": -5},
            )

    def test_t21e_non_string_hypothesis_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            self.skill.generate(123, prototype_type="auto")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.skill.generate(None, prototype_type="auto")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
