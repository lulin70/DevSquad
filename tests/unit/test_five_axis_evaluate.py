"""Unit tests for FiveAxisConsensusEngine.evaluate() and FiveAxisEvaluationResult.

V4.3.0 Phase 3 P3-4: Verifies the heuristic 5-axis evaluation pipeline:
  - FiveAxisEvaluationResult dataclass + to_markdown()
  - 5 heuristic evaluators (correctness/readability/architecture/security/performance)
  - evaluate_artifacts() module-level function
  - FiveAxisConsensusEngine.evaluate() instance method (incl. walkthrough engine)

All tests are self-contained (no external files, no LLM calls) and exercise
the pure-Python heuristic scorers only.
"""

import os
import sys
import unittest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration.five_axis_consensus import (  # noqa: E402
    FiveAxisConsensusEngine,
    FiveAxisEvaluationResult,
    ReviewAxis,
    _evaluate_architecture,
    _evaluate_correctness,
    _evaluate_performance,
    _evaluate_readability,
    _evaluate_security,
    create_walkthrough_engine,
    evaluate_artifacts,
)


class TestFiveAxisEvaluationResult(unittest.TestCase):
    """Test FiveAxisEvaluationResult dataclass + to_markdown()."""

    def test_01_construction(self) -> None:
        result = FiveAxisEvaluationResult(
            correctness=0.7,
            readability=0.5,
            architecture=0.6,
            security=0.8,
            performance=0.4,
            overall=0.62,
            verdict="CONDITIONAL",
            notes={"correctness": "raise found"},
        )
        self.assertEqual(result.correctness, 0.7)
        self.assertEqual(result.readability, 0.5)
        self.assertEqual(result.architecture, 0.6)
        self.assertEqual(result.security, 0.8)
        self.assertEqual(result.performance, 0.4)
        self.assertEqual(result.overall, 0.62)
        self.assertEqual(result.verdict, "CONDITIONAL")
        self.assertEqual(result.notes["correctness"], "raise found")

    def test_02_to_markdown_contains_all_axes(self) -> None:
        result = FiveAxisEvaluationResult(
            correctness=0.7,
            readability=0.5,
            architecture=0.6,
            security=0.8,
            performance=0.4,
            overall=0.62,
            verdict="CONDITIONAL",
            notes={},
        )
        md = result.to_markdown()
        self.assertIn("Correctness", md)
        self.assertIn("Readability", md)
        self.assertIn("Architecture", md)
        self.assertIn("Security", md)
        self.assertIn("Performance", md)

    def test_03_to_markdown_contains_verdict(self) -> None:
        result = FiveAxisEvaluationResult(
            correctness=0.7,
            readability=0.5,
            architecture=0.6,
            security=0.8,
            performance=0.4,
            overall=0.62,
            verdict="CONDITIONAL",
            notes={},
        )
        md = result.to_markdown()
        self.assertIn("`CONDITIONAL`", md)
        self.assertIn("0.62", md)


class TestEvaluateCorrectness(unittest.TestCase):
    """Test _evaluate_correctness heuristic."""

    def test_01_raise_increases_score(self) -> None:
        score_without, _ = _evaluate_correctness("x = 1")
        score_with, _ = _evaluate_correctness("raise ValueError('bad')")
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.2, places=5)

    def test_02_assert_increases_score(self) -> None:
        score_without, _ = _evaluate_correctness("x = 1")
        score_with, _ = _evaluate_correctness("assert x > 0")
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.2, places=5)

    def test_03_try_except_increases_score(self) -> None:
        score_without, _ = _evaluate_correctness("x = 1")
        code_with = "try:\n    x = 1\nexcept Exception:\n    x = 0"
        score_with, _ = _evaluate_correctness(code_with)
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.2, places=5)

    def test_04_pass_decreases_score(self) -> None:
        # Both have `raise`; the variant with `pass` forfeits the +0.1 no-pass bonus.
        score_without_pass, _ = _evaluate_correctness("raise ValueError('x')")
        score_with_pass, _ = _evaluate_correctness("raise ValueError('x')\npass")
        self.assertGreater(score_without_pass, score_with_pass)
        self.assertAlmostEqual(score_without_pass - score_with_pass, 0.1, places=5)

    def test_05_score_capped_at_0_9(self) -> None:
        # All markers present: raise(0.2)+assert(0.2)+try/except(0.2)+no-pass(0.1)=0.7.
        # Cap is 0.9 — verify the score never exceeds 0.9 even with all markers.
        code_with_all = (
            "raise ValueError('x')\n"
            "assert x > 0\n"
            "try:\n"
            "    x = 1\n"
            "except Exception:\n"
            "    x = 0\n"
        )
        score, _ = _evaluate_correctness(code_with_all)
        self.assertLessEqual(score, 0.9)
        self.assertAlmostEqual(score, 0.7, places=5)


class TestEvaluateReadability(unittest.TestCase):
    """Test _evaluate_readability heuristic."""

    def test_01_short_lines_increase_score(self) -> None:
        long_line = "x = " + "a" * 200
        score_short, _ = _evaluate_readability("x = 1\ny = 2")
        score_long, _ = _evaluate_readability(long_line)
        self.assertGreater(score_short, score_long)
        self.assertAlmostEqual(score_short - score_long, 0.2, places=5)

    def test_02_comments_increase_score(self) -> None:
        score_without, _ = _evaluate_readability("x = 1\ny = 2")
        score_with, _ = _evaluate_readability("# comment\nx = 1\ny = 2")
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.3, places=5)

    def test_03_snake_case_funcs_increase_score(self) -> None:
        score_without, _ = _evaluate_readability("x = 1\ny = 2")
        score_with, _ = _evaluate_readability("def my_func():\n    return 1")
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.2, places=5)


class TestEvaluateArchitecture(unittest.TestCase):
    """Test _evaluate_architecture heuristic."""

    def test_01_class_def_layering(self) -> None:
        score_without, _ = _evaluate_architecture("x = 1")
        code_with = "class Foo:\n    def bar(self):\n        return 1\n"
        score_with, _ = _evaluate_architecture(code_with)
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.3, places=5)

    def test_02_modular_imports(self) -> None:
        score_without, _ = _evaluate_architecture("x = 1")
        score_with, _ = _evaluate_architecture("import os\nx = 1")
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.2, places=5)

    def test_03_god_class_detected(self) -> None:
        # Code with >= 500 lines forfeits the +0.2 "no God Class" bonus.
        small_code = "x = 1\n"
        large_code = "\n".join(["x = 1"] * 500)
        score_small, _ = _evaluate_architecture(small_code)
        score_large, _ = _evaluate_architecture(large_code)
        self.assertGreater(score_small, score_large)
        self.assertAlmostEqual(score_small - score_large, 0.2, places=5)


class TestEvaluateSecurity(unittest.TestCase):
    """Test _evaluate_security heuristic."""

    def test_01_eval_detected(self) -> None:
        score_clean, _ = _evaluate_security("x = 1")
        score_eval, _ = _evaluate_security("x = eval('1+1')")
        self.assertGreater(score_clean, score_eval)
        self.assertAlmostEqual(score_clean - score_eval, 0.3, places=5)

    def test_02_exec_detected(self) -> None:
        score_clean, _ = _evaluate_security("x = 1")
        score_exec, _ = _evaluate_security("exec('print(1)')")
        self.assertGreater(score_clean, score_exec)
        self.assertAlmostEqual(score_clean - score_exec, 0.3, places=5)

    def test_03_os_system_detected(self) -> None:
        score_clean, _ = _evaluate_security("x = 1")
        score_os, _ = _evaluate_security("os.system('ls')")
        self.assertGreater(score_clean, score_os)
        self.assertAlmostEqual(score_clean - score_os, 0.3, places=5)

    def test_04_hardcoded_secret_detected(self) -> None:
        score_clean, _ = _evaluate_security("x = 1")
        code_with_secret = 'password = "supersecret123"'
        score_secret, _ = _evaluate_security(code_with_secret)
        self.assertGreater(score_clean, score_secret)
        self.assertAlmostEqual(score_clean - score_secret, 0.3, places=5)

    def test_05_input_validation_increases_score(self) -> None:
        score_without, _ = _evaluate_security("x = 1")
        score_with, _ = _evaluate_security("isinstance(x, int)")
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.2, places=5)


class TestEvaluatePerformance(unittest.TestCase):
    """Test _evaluate_performance heuristic."""

    def test_01_deep_nesting_detected(self) -> None:
        # 24-space indent (6 levels) is flagged as deep nesting.
        score_flat, _ = _evaluate_performance("x = 1\ny = 2")
        deep_code = "x = 1\n" + " " * 24 + "y = 2\n"
        score_deep, _ = _evaluate_performance(deep_code)
        self.assertGreater(score_flat, score_deep)
        self.assertAlmostEqual(score_flat - score_deep, 0.2, places=5)

    def test_02_generator_detected(self) -> None:
        score_without, _ = _evaluate_performance("x = 1\ny = 2")
        score_with, _ = _evaluate_performance("def gen():\n    yield 1\n")
        self.assertGreater(score_with, score_without)
        self.assertAlmostEqual(score_with - score_without, 0.1, places=5)


class TestEvaluateArtifacts(unittest.TestCase):
    """Test evaluate_artifacts() module-level function."""

    def test_01_empty_code_returns_low_score(self) -> None:
        result = evaluate_artifacts({"code": ""})
        self.assertLess(result.overall, 0.4)
        self.assertEqual(result.verdict, "REJECT")

    def test_02_well_structured_code_returns_higher_score(self) -> None:
        good_code = (
            '"""Module docstring."""\n'
            "import os\n"
            "from typing import Any\n"
            "\n"
            "class Service:\n"
            '    """A service."""\n'
            "    def process(self, x: int) -> int:\n"
            "        # Validate input\n"
            "        if not isinstance(x, int):\n"
            "            raise ValueError('x must be int')\n"
            "        try:\n"
            "            return x * 2\n"
            "        except Exception:\n"
            "            return 0\n"
        )
        result_good = evaluate_artifacts({"code": good_code})
        result_empty = evaluate_artifacts({"code": ""})
        self.assertGreater(result_good.overall, result_empty.overall)

    def test_03_verdict_in_allowed_values(self) -> None:
        for code in ["", "x = 1", "raise ValueError('x')", "eval('1')"]:
            result = evaluate_artifacts({"code": code})
            self.assertIn(result.verdict, {"APPROVE", "CONDITIONAL", "REJECT"})

    def test_04_custom_weights_respected(self) -> None:
        code = "raise ValueError('x')\nassert x\n"
        default_result = evaluate_artifacts({"code": code})
        security_heavy = {
            ReviewAxis.SECURITY: 0.9,
            ReviewAxis.CORRECTNESS: 0.0,
            ReviewAxis.READABILITY: 0.0,
            ReviewAxis.ARCHITECTURE: 0.0,
            ReviewAxis.PERFORMANCE: 0.1,
        }
        custom_result = evaluate_artifacts({"code": code}, weights=security_heavy)
        # Different weight distributions must yield different overall scores.
        self.assertNotAlmostEqual(default_result.overall, custom_result.overall, places=5)

    def test_05_overall_is_weighted_average(self) -> None:
        code = "raise ValueError('x')\nassert x\n"
        weights = {
            ReviewAxis.CORRECTNESS: 0.5,
            ReviewAxis.SECURITY: 0.3,
            ReviewAxis.ARCHITECTURE: 0.1,
            ReviewAxis.PERFORMANCE: 0.05,
            ReviewAxis.READABILITY: 0.05,
        }
        result = evaluate_artifacts({"code": code}, weights=weights)
        total_weight = sum(weights.values())
        expected = (
            result.correctness * weights[ReviewAxis.CORRECTNESS]
            + result.readability * weights[ReviewAxis.READABILITY]
            + result.architecture * weights[ReviewAxis.ARCHITECTURE]
            + result.security * weights[ReviewAxis.SECURITY]
            + result.performance * weights[ReviewAxis.PERFORMANCE]
        ) / total_weight
        self.assertAlmostEqual(result.overall, expected, places=5)


class TestEngineEvaluate(unittest.TestCase):
    """Test FiveAxisConsensusEngine.evaluate() instance method."""

    def test_01_evaluate_uses_engine_weights(self) -> None:
        code = "raise ValueError('x')\nassert x\n"
        custom_weights = {
            ReviewAxis.SECURITY: 0.7,
            ReviewAxis.CORRECTNESS: 0.1,
            ReviewAxis.READABILITY: 0.1,
            ReviewAxis.ARCHITECTURE: 0.05,
            ReviewAxis.PERFORMANCE: 0.05,
        }
        engine = FiveAxisConsensusEngine(
            custom_weights=custom_weights, replace_weights=True
        )
        engine_result = engine.evaluate({"code": code})
        direct_result = evaluate_artifacts({"code": code}, weights=custom_weights)
        self.assertAlmostEqual(engine_result.overall, direct_result.overall, places=5)

    def test_02_evaluate_returns_correct_type(self) -> None:
        engine = FiveAxisConsensusEngine()
        result = engine.evaluate({"code": "x = 1"})
        self.assertIsInstance(result, FiveAxisEvaluationResult)

    def test_03_evaluate_with_walkthrough_engine(self) -> None:
        # Walkthrough engine replaces PERFORMANCE with OPERABILITY (unscored axis).
        # evaluate() must still return a valid result with a verdict from the
        # allowed set, even though OPERABILITY contributes 0 to the weighted sum.
        engine = create_walkthrough_engine()
        result = engine.evaluate({"code": "raise ValueError('x')\n"})
        self.assertIsInstance(result, FiveAxisEvaluationResult)
        self.assertIn(result.verdict, {"APPROVE", "CONDITIONAL", "REJECT"})


if __name__ == "__main__":
    unittest.main()
