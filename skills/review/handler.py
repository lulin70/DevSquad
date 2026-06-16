"""Five-Axis Code Review Skill - V3.7.0

Encapsulates FiveAxisConsensusEngine for multi-dimensional code review:
  1. Correctness: Logic correctness, bug-free, meets requirements
  2. Readability: Code clarity, naming, comments, structure
  3. Architecture: Design patterns, modularity, scalability
  4. Security: Vulnerabilities, input validation, data protection
  5. Performance: Efficiency, resource usage, bottlenecks

Supports both direct API and dispatcher integration (mode="consensus").
"""

from pathlib import Path
from typing import Any

from scripts.collaboration.five_axis_consensus import (
    ConsensusResult,
    FiveAxisConsensusEngine,
    ReviewAxis,
)
from skills.registry import BaseSkill


class ReviewSkill(BaseSkill):
    """Five-axis code review skill for comprehensive code quality assessment."""

    name = "review"
    description = "Five-axis code review: correctness/readability/architecture/security/performance"
    version = "3.7.0"

    AXES_INFO = [
        {
            "axis": "correctness",
            "label": "Correctness",
            "description": "Logic correctness, bug-free, meets requirements",
            "weight": 0.30,
        },
        {
            "axis": "readability",
            "label": "Readability",
            "description": "Code clarity, naming conventions, comments, structure",
            "weight": 0.10,
        },
        {
            "axis": "architecture",
            "label": "Architecture",
            "description": "Design patterns, modularity, scalability",
            "weight": 0.20,
        },
        {
            "axis": "security",
            "label": "Security",
            "description": "Vulnerabilities, input validation, data protection",
            "weight": 0.25,
        },
        {
            "axis": "performance",
            "label": "Performance",
            "description": "Efficiency, resource usage, bottleneck detection",
            "weight": 0.15,
        },
    ]

    def __init__(self):
        self._engine: FiveAxisConsensusEngine | None = None

    def _get_engine(self, strict_mode: bool = False) -> FiveAxisConsensusEngine:
        if self._engine is None or self._engine._strict_mode != strict_mode:
            self._engine = FiveAxisConsensusEngine(strict_mode=strict_mode)
        return self._engine

    def review(
        self,
        code: str,
        strict_mode: bool = False,
        file_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Perform five-axis code review.

        Args:
            code: Source code to review (required)
            strict_mode: Enable strict mode (security veto on low scores)
            file_path: Optional file path for context (reads file if provided)

        Returns:
            Dict with review results including:
                - axis_scores: Per-axis consensus scores
                - overall_score: Weighted overall score
                - verdict: APPROVE/CONDITIONAL/REJECT
                - action_items: List of improvement suggestions
                - metadata: Review metadata (file_path, mode, etc.)
        """
        if file_path and not code:
            path = Path(file_path)
            if path.exists():
                code = path.read_text(encoding="utf-8")
            else:
                return {
                    "error": f"File not found: {file_path}",
                    "verdict": "REJECT",
                }

        if not code or not code.strip():
            return {
                "error": "No code provided for review",
                "verdict": "REJECT",
            }

        engine = self._get_engine(strict_mode=strict_mode)

        review = engine.create_review(reviewer_id="review-skill", role="code-reviewer")

        axis_scores = self._analyze_code(code)

        for axis_name, score_data in axis_scores.items():
            try:
                axis = ReviewAxis(axis_name)
                engine.add_axis_vote(
                    review=review,
                    axis=axis,
                    score=score_data["score"],
                    confidence=score_data["confidence"],
                    comment=score_data["comment"],
                )
            except ValueError:
                continue

        result: ConsensusResult = engine.compute_consensus([review])

        return {
            **result.to_dict(),
            "metadata": {
                "file_path": file_path,
                "strict_mode": strict_mode,
                "code_length": len(code),
                "skill_version": self.version,
            },
        }

    def quick_review(self, code_snippet: str) -> dict[str, Any]:
        """
        Simplified single-axis quick scan for rapid feedback.

        Focuses on correctness axis only for fast iteration.
        Suitable for inline code snippets during development.

        Args:
            code_snippet: Short code snippet to quickly review

        Returns:
            Dict with quick assessment:
                - score: Correctness score (0.0-1.0)
                - status: PASS/WARN/FAIL
                - issues: List of detected issues
                - suggestion: One-line improvement suggestion
        """
        if not code_snippet or not code_snippet.strip():
            return {
                "score": 0.0,
                "status": "FAIL",
                "issues": ["Empty code snippet"],
                "suggestion": "Provide valid code for review",
            }

        issues = []
        score = 1.0

        lines = code_snippet.strip().split("\n")

        if len(lines) < 3:
            issues.append("Very short snippet - limited analysis possible")
            score -= 0.1

        has_comments = any(line.strip().startswith("#") for line in lines)
        if not has_comments and len(lines) > 5:
            issues.append("No comments found")
            score -= 0.15

        if "TODO" in code_snippet or "FIXME" in code_snippet or "XXX" in code_snippet:
            issues.append("Contains TODO/FIXME markers")
            score -= 0.2

        if "print(" in code_snippet and "logging" not in code_snippet:
            issues.append("Uses print() instead of logging")
            score -= 0.1

        if "except:" in code_snippet or "except Exception" in code_snippet:
            for line in lines:
                if "except" in line and ("pass" in line or "continue" in line):
                    issues.append("Silent exception handling detected")
                    score -= 0.2
                    break

        if len(lines[0]) > 120:
            issues.append("Very long first line")
            score -= 0.05

        score = max(0.0, min(1.0, score))

        if score >= 0.8:
            status = "PASS"
        elif score >= 0.5:
            status = "WARN"
        else:
            status = "FAIL"

        suggestion = (
            "Looks good"
            if status == "PASS"
            else "Consider addressing warnings"
            if status == "WARN"
            else "Needs significant improvement"
        )

        return {
            "score": round(score, 2),
            "status": status,
            "issues": issues,
            "suggestion": suggestion,
            "snippet_length": len(code_snippet),
        }

    def list_axes(self) -> list[dict[str, Any]]:
        """
        Return information about all five review axes.

        Returns:
            List of dicts with axis details:
                - axis: Axis identifier
                - label: Human-readable name
                - description: What this axis evaluates
                - weight: Default weight in consensus calculation
        """
        return self.AXES_INFO

    def run(self, *args, **kwargs):
        """
        Main entry point for the skill.

        Supports multiple calling patterns:

        1. Direct call: run(code="...", strict_mode=False)
        2. Quick mode: run(mode="quick", code_snippet="...")
        3. Dispatcher integration: run(task="...", mode="consensus")
        """
        mode = kwargs.get("mode", "full")

        if mode == "quick":
            code_snippet = kwargs.get("code_snippet", "") or kwargs.get("code", "")
            return self.quick_review(code_snippet)

        elif mode == "consensus":
            task = kwargs.get("task", "")
            code = kwargs.get("code", task)
            strict_mode = kwargs.get("strict_mode", False)
            file_path = kwargs.get("file_path")
            return self.review(code=code, strict_mode=strict_mode, file_path=file_path)

        else:
            code = kwargs.get("code", "")
            if not code and args:
                code = str(args[0])
            strict_mode = kwargs.get("strict_mode", False)
            file_path = kwargs.get("file_path")
            return self.review(code=code, strict_mode=strict_mode, file_path=file_path)

    @staticmethod
    def _analyze_code(code: str) -> dict[str, dict[str, Any]]:
        """
        Static analysis of code across five axes.
        Returns simulated scores based on heuristics.
        In production, this would integrate LLM-based analysis.
        """
        lines = code.split("\n")
        total_lines = len(lines)
        non_empty = [line for line in lines if line.strip()]

        scores = {
            "correctness": {"score": 0.85, "confidence": 0.8, "comment": "Basic structure looks valid"},
            "readability": {"score": 0.75, "confidence": 0.7, "comment": "Moderate readability"},
            "architecture": {"score": 0.80, "confidence": 0.6, "comment": "Reasonable structure"},
            "security": {"score": 0.90, "confidence": 0.7, "comment": "No obvious security issues"},
            "performance": {"score": 0.80, "confidence": 0.6, "comment": "Acceptable performance characteristics"},
        }

        has_imports = any(line.strip().startswith("import ") or line.strip().startswith("from ") for line in lines)
        has_functions = any("def " in line for line in lines)
        has_classes = any("class " in line for line in lines)
        has_docstring = '"""' in code or "'''" in code
        any(line.strip().startswith("#") for line in lines)

        comment_ratio = sum(1 for line in lines if line.strip().startswith("#")) / max(len(non_empty), 1)

        avg_line_length = sum(len(line) for line in non_empty) / max(len(non_empty), 1)

        if total_lines < 10:
            scores["correctness"]["score"] -= 0.1
            scores["correctness"]["comment"] = "Short code snippet - limited analysis"
        else:
            if has_functions or has_classes:
                scores["correctness"]["score"] = min(1.0, scores["correctness"]["score"] + 0.05)
                scores["correctness"]["comment"] = "Contains functions/classes - good structure"

        if has_docstring:
            scores["readability"]["score"] = min(1.0, scores["readability"]["score"] + 0.1)
            scores["readability"]["comment"] = "Has docstrings"
        else:
            scores["readability"]["score"] -= 0.1
            scores["readability"]["comment"] = "Missing docstrings"

        if 0.1 <= comment_ratio <= 0.3:
            scores["readability"]["score"] = min(1.0, scores["readability"]["score"] + 0.05)
        elif comment_ratio > 0.5:
            scores["readability"]["score"] -= 0.05
            scores["readability"]["comment"] += " (over-commented?)"

        if avg_line_length > 100:
            scores["readability"]["score"] -= 0.1
            scores["readability"]["comment"] += "; Long lines detected"

        if has_classes and has_functions:
            scores["architecture"]["score"] = min(1.0, scores["architecture"]["score"] + 0.1)
            scores["architecture"]["comment"] = "OOP structure detected"
        elif has_imports:
            scores["architecture"]["score"] = min(1.0, scores["architecture"]["score"] + 0.05)
            scores["architecture"]["comment"] = "Modular imports present"

        dangerous_patterns = ["eval(", "exec(", "os.system(", "subprocess.call(", "__import__"]
        for pattern in dangerous_patterns:
            if pattern in code:
                scores["security"]["score"] -= 0.2
                scores["security"]["comment"] = f"Dangerous pattern found: {pattern}"
                break

        if ("password" in code.lower() or "secret" in code.lower() or "api_key" in code.lower()) and "=" in code and ('"' in code or "'" in code):
            scores["security"]["score"] -= 0.3
            scores["security"]["comment"] = "Possible hardcoded credentials detected"

        if "sql" in code.lower() and ("SELECT" in code or "INSERT" in code) and ('f"' in code or "f'" in code or "%" in code or ".format(" in code):
            scores["security"]["score"] -= 0.15
            scores["security"]["comment"] += "; Possible SQL injection risk"

        if "for " in code and " range(" in code:
            if total_lines > 50:
                scores["performance"]["score"] -= 0.1
                scores["performance"]["comment"] = "Nested loops may impact performance at scale"
        elif "while True" in code:
            scores["performance"]["score"] -= 0.15
            scores["performance"]["comment"] = "Infinite loop detected - ensure proper exit condition"

        for axis in scores:
            scores[axis]["score"] = max(0.0, min(1.0, scores[axis]["score"]))
            scores[axis]["score"] = round(scores[axis]["score"], 2)

        return scores
