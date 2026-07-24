"""PrototypeSkill — Rapid prototype generation for hypothesis validation.

ROADMAP P2-1: Fast prototype validation capability.

Before investing in full implementation, produce a minimal runnable
prototype to validate the underlying hypothesis. Reuses MicroTaskPlanner's
vertical-slice pattern and coordinates with Skillifier for skill lifecycle.

Integration:
    - MicroTaskPlanner: vertical-slice decomposition (2-5 min micro-tasks)
    - Skillifier: coordination point for skill auto-generation (PrototypeSkill
      produces *artifacts*; Skillifier *extracts patterns* from execution
      history. No overlap with intent skill, which *detects user intent*.)

Example:
    >>> from skills.prototype.handler import PrototypeSkill
    >>> skill = PrototypeSkill()
    >>> result = skill.generate("Users prefer single-click checkout")
    >>> print(result["prototype_type"])  # "ui" (auto-detected from "checkout")
    >>> print(len(result["files"]))  # <= 3
"""

import os
import sys
from collections.abc import Callable
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from skills.registry import BaseSkill


class PrototypeSkill(BaseSkill):
    """Rapid prototype generation skill.

    Produces minimal runnable prototypes to validate hypotheses before
    committing to full implementation. Supports ui/logic/api prototype
    types with auto-detection from hypothesis keywords.

    Attributes:
        name: Skill identifier ("prototype")
        description: Human-readable skill description
        version: Skill semantic version (inherited from BaseSkill)
    """

    name = "prototype"
    description = (
        "Rapid prototype generation — produce minimal runnable prototype "
        "to validate hypothesis before full implementation"
    )

    # Keyword maps for auto-detecting prototype type from the hypothesis.
    TYPE_KEYWORDS: dict[str, list[str]] = {
        "ui": ["界面", "ui", "页面", "按钮", "表单", "checkout", "interface", "screen", "dialog"],
        "logic": ["算法", "计算", "逻辑", "处理", "algorithm", "compute", "logic", "process"],
        "api": ["接口", "api", "端点", "请求", "endpoint", "request", "rest", "graphql"],
    }

    # Feedback keywords for the validate() heuristic (mock mode, no LLM).
    POSITIVE_FEEDBACK_KEYWORDS: list[str] = [
        "yes", "like", "good", "prefer", "符合", "喜欢", "好", "满意", "确认", "accept", "works",
    ]
    NEGATIVE_FEEDBACK_KEYWORDS: list[str] = [
        "no", "dislike", "bad", "不符合", "不喜欢", "差", "不满意", "拒绝", "reject", "broken",
    ]

    DEFAULT_MAX_FILES = 3
    DEFAULT_MAX_LINES_PER_FILE = 50
    _MAX_HYPOTHESIS_LEN = 2000

    def generate(
        self,
        hypothesis: str,
        prototype_type: str = "auto",
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a minimal runnable prototype to validate a hypothesis.

        Args:
            hypothesis: The assumption to validate (e.g., "Users prefer
                single-click checkout").
            prototype_type: "ui" | "logic" | "api" | "auto" (auto-detect
                from hypothesis).
            constraints: Optional dict with keys:
                - max_files: int (default 3) — max files in prototype
                - max_lines_per_file: int (default 50) — keep prototypes small
                - target_framework: str (e.g., "streamlit", "flask", "plain-python")
                - vertical_slice: bool (default True) — use MicroTaskPlanner
                  vertical-slice pattern

        Returns:
            Dict with keys:
                - hypothesis: str — the assumption being validated
                - prototype_type: str — detected/specified type
                - files: list[dict] — list of {path, content, purpose} dicts
                - validation_steps: list[str] — how to validate the hypothesis
                - estimated_effort_minutes: int — rough effort estimate (2-5)
                - assumptions_made: list[str] — assumptions baked into the prototype
                - next_steps: list[str] — what to do after validation
                - vertical_slice_plan: dict | None — MicroTaskPlanner plan (when
                  vertical_slice=True)

        Raises:
            TypeError: If hypothesis is not a string.
            ValueError: If hypothesis is empty, prototype_type is unsupported,
                or max_files/max_lines_per_file are non-positive.
        """
        # --- Validate inputs -------------------------------------------------
        if not isinstance(hypothesis, str):
            raise TypeError("hypothesis must be a string")
        if not hypothesis.strip():
            raise ValueError("hypothesis must not be empty")
        if len(hypothesis) > self._MAX_HYPOTHESIS_LEN:
            hypothesis = hypothesis[: self._MAX_HYPOTHESIS_LEN]

        valid_types = {"ui", "logic", "api", "auto"}
        if prototype_type not in valid_types:
            raise ValueError(
                f"prototype_type must be one of {sorted(valid_types)}, got {prototype_type!r}"
            )

        # --- Resolve constraints --------------------------------------------
        constraints = constraints or {}
        max_files = constraints.get("max_files", self.DEFAULT_MAX_FILES)
        max_lines = constraints.get("max_lines_per_file", self.DEFAULT_MAX_LINES_PER_FILE)
        target_framework = constraints.get("target_framework", "")
        vertical_slice = constraints.get("vertical_slice", True)

        if not isinstance(max_files, int) or isinstance(max_files, bool) or max_files <= 0:
            raise ValueError(f"max_files must be a positive integer, got {max_files!r}")
        if (
            not isinstance(max_lines, int)
            or isinstance(max_lines, bool)
            or max_lines <= 0
        ):
            raise ValueError(
                f"max_lines_per_file must be a positive integer, got {max_lines!r}"
            )

        # --- Auto-detect prototype type -------------------------------------
        detected_type = prototype_type
        if prototype_type == "auto":
            detected_type = self._detect_type(hypothesis)

        # --- Generate files --------------------------------------------------
        files = self._generate_files(
            hypothesis=hypothesis,
            prototype_type=detected_type,
            max_files=max_files,
            max_lines=max_lines,
            target_framework=target_framework,
        )

        # --- Vertical-slice decomposition via MicroTaskPlanner --------------
        plan_dict: dict[str, Any] | None = None
        if vertical_slice:
            plan_dict = self._decompose_vertical_slice(hypothesis, files)

        # --- Estimate effort (2-5 min range, per MicroTaskPlanner) ----------
        estimated_effort = self._estimate_effort(files)

        # --- Build validation steps, assumptions, next steps ----------------
        validation_steps = self._build_validation_steps(detected_type, hypothesis)
        assumptions = self._build_assumptions(detected_type, hypothesis, target_framework)
        next_steps = self._build_next_steps(detected_type)

        return {
            "hypothesis": hypothesis,
            "prototype_type": detected_type,
            "files": files,
            "validation_steps": validation_steps,
            "estimated_effort_minutes": estimated_effort,
            "assumptions_made": assumptions,
            "next_steps": next_steps,
            "vertical_slice_plan": plan_dict,
        }

    def validate(
        self,
        prototype_result: dict[str, Any],
        actual_outcome: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate whether the prototype confirmed or refuted the hypothesis.

        Args:
            prototype_result: The generate() output dict.
            actual_outcome: Dict with keys:
                - user_feedback: str — what users said
                - metrics: dict — quantitative results
                - observed_behavior: str — what actually happened

        Returns:
            Dict with keys:
                - hypothesis_confirmed: bool
                - confidence: float (0.0-1.0)
                - evidence: list[str]
                - recommendations: list[str]
                - should_proceed_to_full_impl: bool
        """
        user_feedback = str(actual_outcome.get("user_feedback", "")).lower()
        metrics = actual_outcome.get("metrics", {}) or {}
        observed_behavior = str(actual_outcome.get("observed_behavior", "")).lower()

        evidence: list[str] = []
        positive_signals = 0
        negative_signals = 0

        # --- Analyze user feedback ------------------------------------------
        for kw in self.POSITIVE_FEEDBACK_KEYWORDS:
            if kw in user_feedback:
                positive_signals += 1
                evidence.append(f"Positive feedback signal: '{kw}'")
        for kw in self.NEGATIVE_FEEDBACK_KEYWORDS:
            if kw in user_feedback:
                negative_signals += 1
                evidence.append(f"Negative feedback signal: '{kw}'")

        # --- Analyze metrics ------------------------------------------------
        for key, value in metrics.items():
            if isinstance(value, bool):
                if value:
                    positive_signals += 1
                    evidence.append(f"Metric '{key}' is True")
                else:
                    negative_signals += 1
                    evidence.append(f"Metric '{key}' is False")
            elif isinstance(value, (int, float)):
                if value > 0.5:
                    positive_signals += 1
                    evidence.append(f"Metric '{key}' = {value} (>0.5)")
                elif value < 0.5:
                    negative_signals += 1
                    evidence.append(f"Metric '{key}' = {value} (<0.5)")

        # --- Analyze observed behavior vs hypothesis ------------------------
        if observed_behavior and "hypothesis" in prototype_result:
            hypothesis_lower = str(prototype_result["hypothesis"]).lower()
            hyp_words = set(hypothesis_lower.split())
            obs_words = set(observed_behavior.split())
            overlap = hyp_words & obs_words
            if len(overlap) >= 2:
                positive_signals += 1
                evidence.append(
                    f"Observed behavior aligns with hypothesis (overlap: {sorted(overlap)})"
                )

        # --- Compute confidence ---------------------------------------------
        total_signals = positive_signals + negative_signals
        if total_signals == 0:
            confidence = 0.0
            confirmed = False
        else:
            confidence = positive_signals / total_signals
            confirmed = positive_signals > negative_signals

        confidence = max(0.0, min(1.0, confidence))

        should_proceed = confirmed and confidence >= 0.6

        # --- Recommendations ------------------------------------------------
        recommendations: list[str] = []
        if should_proceed:
            recommendations.append(
                "Hypothesis validated — proceed to full implementation"
            )
            recommendations.append(
                "Use the prototype as reference for production code"
            )
        elif confirmed:
            recommendations.append(
                "Hypothesis weakly validated — iterate on prototype before full implementation"
            )
        else:
            recommendations.append(
                "Hypothesis refuted — revise or abandon before full implementation"
            )
            recommendations.append(
                "Consider alternative hypotheses based on observed behavior"
            )

        return {
            "hypothesis_confirmed": confirmed,
            "confidence": round(confidence, 4),
            "evidence": evidence,
            "recommendations": recommendations,
            "should_proceed_to_full_impl": should_proceed,
        }

    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Default entry point — delegates to generate()."""
        return self.generate(*args, **kwargs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_type(self, hypothesis: str) -> str:
        """Auto-detect prototype type from hypothesis keywords.

        Returns the highest-scoring type; falls back to "logic" when no
        keyword matches (logic is the most general prototype kind).
        """
        text = hypothesis.lower()
        scores: dict[str, int] = dict.fromkeys(self.TYPE_KEYWORDS, 0)
        for ptype, keywords in self.TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    scores[ptype] += 1
        best_type = max(scores, key=lambda k: scores[k])
        if scores[best_type] == 0:
            return "logic"
        return best_type

    def _generate_files(
        self,
        hypothesis: str,
        prototype_type: str,
        max_files: int,
        max_lines: int,
        target_framework: str,
    ) -> list[dict[str, str]]:
        """Generate template files for the prototype (mock mode)."""
        safe_hyp = hypothesis.replace('"', "'")[:80]
        generators: dict[str, Callable[[str, str], list[dict[str, str]]]] = {
            "ui": self._generate_ui_files,
            "logic": self._generate_logic_files,
            "api": self._generate_api_files,
        }
        gen = generators.get(prototype_type, self._generate_logic_files)
        files = gen(safe_hyp, target_framework)

        # Enforce max_files.
        files = files[:max_files]
        # Enforce max_lines per file. Reserve one line for the truncation marker
        # so the final content never exceeds max_lines.
        for f in files:
            lines = f["content"].splitlines()
            if len(lines) > max_lines:
                f["content"] = "\n".join(lines[: max_lines - 1]) + "\n# ... (truncated)"
        return files

    def _generate_ui_files(
        self, hypothesis: str, target_framework: str
    ) -> list[dict[str, str]]:
        """Generate UI prototype files (streamlit by default)."""
        framework = target_framework or "streamlit"
        main_py = (
            f'"""Prototype: {hypothesis}\n\n'
            f"Generated by PrototypeSkill (mock mode). Framework: {framework}.\n"
            f"Run with: streamlit run prototype_ui.py\n"
            f'"""\n'
            f"import streamlit as st\n\n"
            f'st.title("Prototype")\n'
            f'st.write("Hypothesis: {hypothesis}")\n\n'
            f'user_input = st.text_input("Test input")\n'
            f'if st.button("Submit"):\n'
            f'    st.write(f"You entered: {{user_input}}")\n'
        )
        html = (
            f"<!DOCTYPE html>\n"
            f"<html>\n"
            f"<head><title>Prototype</title></head>\n"
            f"<body>\n"
            f"  <h1>Prototype</h1>\n"
            f"  <p>Hypothesis: {hypothesis}</p>\n"
            f"  <form>\n"
            f'    <input type="text" placeholder="Test input" />\n'
            f'    <button type="submit">Submit</button>\n'
            f"  </form>\n"
            f"</body>\n"
            f"</html>\n"
        )
        test_py = (
            f'"""Smoke test for UI prototype: {hypothesis}"""\n'
            f"def test_ui_renders():\n"
            f'    title = "Prototype"\n'
            f'    assert title == "Prototype"\n\n'
            f'if __name__ == "__main__":\n'
            f"    test_ui_renders()\n"
            f'    print("UI prototype smoke test passed")\n'
        )
        return [
            {"path": "prototype_ui.py", "content": main_py, "purpose": f"Main {framework} UI prototype"},
            {"path": "prototype_ui.html", "content": html, "purpose": "Static HTML mock"},
            {"path": "test_prototype_ui.py", "content": test_py, "purpose": "Smoke test"},
        ]

    def _generate_logic_files(
        self, hypothesis: str, target_framework: str
    ) -> list[dict[str, str]]:
        """Generate logic prototype files (plain Python)."""
        framework_note = f" (framework: {target_framework})" if target_framework else ""
        main_py = (
            f'"""Prototype: {hypothesis}\n\n'
            f"Generated by PrototypeSkill (mock mode). Plain Python{framework_note}.\n"
            f"Run with: python prototype_logic.py\n"
            f'"""\n\n\n'
            f"def validate_hypothesis(input_data):\n"
            f'    """Core logic to validate: {hypothesis}"""\n'
            f'    result = {{"input": input_data, "output": f"processed: {{input_data}}"}}\n'
            f"    return result\n\n\n"
            f'if __name__ == "__main__":\n'
            f'    test_data = "sample"\n'
            f"    print(validate_hypothesis(test_data))\n"
        )
        test_py = (
            f'"""Smoke test for logic prototype: {hypothesis}"""\n'
            f"from prototype_logic import validate_hypothesis\n\n\n"
            f"def test_logic_returns_result():\n"
            f'    result = validate_hypothesis("test")\n'
            f'    assert "input" in result\n'
            f'    assert "output" in result\n\n\n'
            f'if __name__ == "__main__":\n'
            f"    test_logic_returns_result()\n"
            f'    print("Logic prototype smoke test passed")\n'
        )
        return [
            {"path": "prototype_logic.py", "content": main_py, "purpose": "Main logic prototype"},
            {"path": "test_prototype_logic.py", "content": test_py, "purpose": "Smoke test"},
        ]

    def _generate_api_files(
        self, hypothesis: str, target_framework: str
    ) -> list[dict[str, str]]:
        """Generate API prototype files (Flask by default)."""
        framework = target_framework or "flask"
        main_py = (
            f'"""Prototype: {hypothesis}\n\n'
            f"Generated by PrototypeSkill (mock mode). Framework: {framework}.\n"
            f"Run with: python prototype_api.py\n"
            f'"""\n'
            f"from flask import Flask, jsonify, request\n\n"
            f"app = Flask(__name__)\n\n\n"
            f'@app.route("/api/test", methods=["POST"])\n'
            f"def test_endpoint():\n"
            f"    data = request.get_json() or {{}}\n"
            f'    return jsonify({{"input": data, "status": "ok"}})\n\n\n'
            f'if __name__ == "__main__":\n'
            f"    app.run(debug=True, port=5000)\n"
        )
        test_py = (
            f'"""Smoke test for API prototype: {hypothesis}"""\n'
            f"import prototype_api\n\n\n"
            f"def test_app_exists():\n"
            f"    assert prototype_api.app is not None\n\n\n"
            f'if __name__ == "__main__":\n'
            f"    test_app_exists()\n"
            f'    print("API prototype smoke test passed")\n'
        )
        return [
            {"path": "prototype_api.py", "content": main_py, "purpose": f"Main {framework} API prototype"},
            {"path": "test_prototype_api.py", "content": test_py, "purpose": "Smoke test"},
        ]

    def _decompose_vertical_slice(
        self,
        hypothesis: str,
        files: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Use MicroTaskPlanner to decompose the prototype into vertical slices.

        Marks every micro-task as ``slice_type="vertical"`` (end-to-end slice)
        so the plan reflects the prototype-first workflow: each file is a
        vertical cut through the stack rather than a horizontal layer.
        """
        from scripts.collaboration.micro_task_planner import MicroTaskPlanner

        planner = MicroTaskPlanner()
        spec: dict[str, Any] = {
            "files": [f["path"] for f in files],
            "tests": [f["path"] for f in files if f["path"].startswith("test_")],
        }
        plan = planner.plan(hypothesis, spec=spec)
        # Mark all micro-tasks as vertical slices (end-to-end cuts).
        for mt in plan.micro_tasks:
            mt.slice_type = "vertical"
        return plan.to_dict()

    def _estimate_effort(self, files: list[dict[str, str]]) -> int:
        """Estimate effort in 2-5 min range (MicroTaskPlanner convention).

        Heuristic mirrors MicroTaskPlanner._estimate_duration:
          - 1 file  -> 2 minutes
          - 2-3 files -> 3 minutes
          - 4+ files  -> 5 minutes
        Clamped to [2, 5].
        """
        n = len(files)
        if n <= 1:
            est = 2
        elif n <= 3:
            est = 3
        else:
            est = 5
        return max(2, min(5, est))

    def _build_validation_steps(
        self, prototype_type: str, hypothesis: str
    ) -> list[str]:
        """Build executable validation steps for the prototype."""
        return [
            f"Run the main prototype file (e.g., python prototype_{prototype_type}.py)",
            f"Provide test input that exercises the hypothesis: {hypothesis[:80]}",
            "Observe the output and compare against expected behavior",
            f"Run the smoke test (e.g., python -m pytest test_prototype_{prototype_type}.py -v)",
            "Collect user feedback or metrics to confirm/refute the hypothesis",
        ]

    def _build_assumptions(
        self,
        prototype_type: str,
        hypothesis: str,
        target_framework: str,
    ) -> list[str]:
        """List assumptions baked into the prototype."""
        assumptions = [
            f"Hypothesis can be validated with a {prototype_type} prototype",
            "Mock-mode template is sufficient to elicit user feedback",
            f"Hypothesis: {hypothesis[:80]}",
        ]
        if target_framework:
            assumptions.append(f"Target framework: {target_framework}")
        else:
            assumptions.append("Default framework used (no explicit target_framework)")
        return assumptions

    def _build_next_steps(self, prototype_type: str) -> list[str]:
        """List next steps after validation."""
        return [
            f"Run the {prototype_type} prototype with real users or test data",
            "Collect feedback and metrics",
            "Call validate() with the actual outcome to confirm/refute the hypothesis",
            "If confirmed, proceed to full implementation reusing the prototype as reference",
            "If refuted, revise the hypothesis or prototype and re-validate",
        ]
