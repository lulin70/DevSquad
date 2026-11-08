# DevSquad - Simplicity Role - CRAPGate Implementation
# Change Risk Anti-Patterns (CRAP) Gate
# Integrates radon cc to calculate CRAP scores for functions

"""
CRAP Gate: Change Risk Anti-Patterns Metric

Calculates CRAP scores for functions using radon cyclomatic complexity tool.
Formula: CRAP = CC^2 * (1 - Coverage/100)^3 + CC

Thresholds:
- CRAP ≤ 10: PASS
- 10 < CRAP ≤ 15: WARNING
- CRAP > 15: REJECT
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CRAPScore:
    """CRAP score for a single function"""

    file_path: str
    function_name: str
    complexity: int
    crap_score: float
    coverage: float = 0.0
    lineno: int = 0


class CRAPGate:
    """CRAP score gate (based on radon cc)"""

    def __init__(self, threshold: float = 10.0) -> None:
        """
        Initialize CRAP gate

        Args:
            threshold: CRAP threshold (default 10.0)
        """
        self.threshold = threshold
        self.warning_threshold = 15.0

    def calculate_crap_scores(
        self, target_paths: list[Path], coverage_data: dict[str, float] | None = None
    ) -> list[CRAPScore]:
        """
        Calculate CRAP scores for functions in target paths

        Args:
            target_paths: List of file paths to analyze
            coverage_data: Optional coverage data {file_path: coverage_ratio}

        Returns:
            List of CRAPScore objects, sorted by score (descending)

        Raises:
            RuntimeError: If radon is not installed
        """
        coverage_data = coverage_data or {}
        all_scores = []

        for path in target_paths:
            try:
                # Run radon cc with JSON output
                result = subprocess.run(
                    ["radon", "cc", "-j", str(path)], capture_output=True, text=True, timeout=30, check=False
                )

                if result.returncode != 0:
                    logger.warning(f"radon failed for {path}: {result.stderr}")
                    continue

                # Parse JSON output
                try:
                    radon_data = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse radon output for {path}: {e}")
                    continue

                # Extract complexity data for each file
                for file_path, functions in radon_data.items():
                    coverage = coverage_data.get(file_path, 0.0)

                    for func in functions:
                        cc = func.get("complexity", 0)
                        func_name = func.get("name", "unknown")
                        lineno = func.get("lineno", 0)

                        # Calculate CRAP: CC^2 * (1 - Coverage/100)^3 + CC
                        crap = (cc**2) * ((1 - coverage) ** 3) + cc

                        all_scores.append(
                            CRAPScore(
                                file_path=file_path,
                                function_name=func_name,
                                complexity=cc,
                                crap_score=round(crap, 2),
                                coverage=coverage,
                                lineno=lineno,
                            )
                        )

            except subprocess.TimeoutExpired:
                logger.warning(f"radon timeout for {path}")
                continue
            except FileNotFoundError:
                raise RuntimeError("radon is not installed. Install with: pip install radon>=6.0.1") from None
            except PermissionError:
                logger.warning(f"Permission denied: {path}")
                continue

        # Sort by CRAP score (descending)
        all_scores.sort(key=lambda s: s.crap_score, reverse=True)
        return all_scores

    def check(self, target_paths: list[Path], coverage_data: dict[str, float] | None = None) -> dict[str, Any]:
        """
        Execute gate check

        Returns:
            {
                "status": "PASS" | "WARNING" | "REJECT",
                "max_crap": float,
                "violations": list[dict],
                "summary": str
            }
        """
        scores = self.calculate_crap_scores(target_paths, coverage_data)

        if not scores:
            return {
                "status": "PASS",
                "max_crap": 0.0,
                "violations": [],
                "summary": "No functions found or all files skipped",
            }

        max_crap = scores[0].crap_score
        violations = []

        # Collect violations (CRAP > threshold)
        for score in scores:
            if score.crap_score > self.threshold:
                violations.append(
                    {
                        "file": score.file_path,
                        "function": score.function_name,
                        "crap": score.crap_score,
                        "complexity": score.complexity,
                        "line": score.lineno,
                    }
                )

        # Determine status
        if max_crap > self.warning_threshold:
            status = "REJECT"
        elif max_crap > self.threshold:
            status = "WARNING"
        else:
            status = "PASS"

        summary = f"Max CRAP: {max_crap:.2f}, {len(violations)} violations"

        return {"status": status, "max_crap": max_crap, "violations": violations, "summary": summary}
