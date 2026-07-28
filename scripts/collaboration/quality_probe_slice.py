#!/usr/bin/env python3
"""Slice 1: Thin-Slice Quality Probe (V4.4.0).

Runs a 3-task × 3-arm × n-samples comparison to measure the signal
strength of LLM vs Mock output quality difference.

Three arms:
1. frozen_mock: existing MockBackend (frozen baseline, unmodified)
2. role_specific_mock: RoleSpecificMockBackend (role_specific=True)
3. llm: LLM backend (e.g., MOKA AI), skipped if no API key

Gate 0 (calibration) is a precondition. If it fails, the probe is
skipped and signal_strength = "calibration_failed".

Usage:
    from scripts.collaboration.quality_probe_slice import run_probe_slice
    from scripts.collaboration.llm_backend import MockBackend

    # Without LLM (2-arm comparison only)
    report = run_probe_slice(llm_backend=None)

    # With LLM
    report = run_probe_slice(llm_backend=my_llm_backend, n_samples=3)
    print(report.to_markdown())
"""

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .confidence_score import ConfidenceScorer
from .five_axis_consensus import FiveAxisConsensusEngine
from .llm_backend import LLMBackend, MockBackend
from .quality_calibration_gate import run_calibration_gate
from .role_specific_mock_backend import RoleSpecificMockBackend

# Anti-phantom-feature counter
_call_counter: int = 0

_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "calibration" / "gold_outputs.json"

# Signal strength thresholds (on 0-1 scale)
_SIG_SIGNIFICANT = 0.15
_SIG_MARGINAL = 0.05

# Task IDs
_TASK_IDS = ("simple", "medium", "complex")

# Arm IDs
_ARM_FROZEN = "frozen_mock"
_ARM_ROLE_SPECIFIC = "role_specific_mock"
_ARM_LLM = "llm"


@dataclass
class ProbeSliceReport:
    """Thin-slice probe report with signal strength assessment.

    Attributes:
        gate_passed: Whether Gate 0 calibration passed.
        task_results: {task_id: {arm_id: [score_1, ..., score_n]}}.
        mean_stddev: {task_id: {arm_id: (mean, stddev)}}.
        signal_strength: "significant" / "marginal" / "noise" / "calibration_failed".
        conclusion: Human-readable conclusion paragraph.
        llm_arm_skipped: True if LLM arm was skipped (no API key).
    """

    gate_passed: bool = False
    task_results: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    mean_stddev: dict[str, dict[str, tuple[float, float]]] = field(default_factory=dict)
    signal_strength: str = "calibration_failed"
    conclusion: str = ""
    llm_arm_skipped: bool = False

    def to_markdown(self) -> str:
        """Render Markdown decision report."""
        lines = [
            "## Slice 1: Thin-Slice Quality Probe Report",
            "",
            f"**Gate 0 Passed**: {self.gate_passed}",
            f"**Signal Strength**: `{self.signal_strength}`",
            f"**LLM Arm Skipped**: {self.llm_arm_skipped}",
            "",
        ]
        if not self.gate_passed:
            lines.append("_Probe skipped — calibration gate failed._")
            return "\n".join(lines)

        lines.append("### Mean ± Stddev by Task × Arm")
        lines.append("")
        lines.append("| Task | frozen_mock | role_specific_mock | llm |")
        lines.append("|------|-------------|-------------------|-----|")
        for task_id in _TASK_IDS:
            row = f"| {task_id} "
            for arm_id in (_ARM_FROZEN, _ARM_ROLE_SPECIFIC, _ARM_LLM):
                ms = self.mean_stddev.get(task_id, {}).get(arm_id)
                if ms is None:
                    row += "| N/A "
                else:
                    mean, stddev = ms
                    row += f"| {mean:.3f}±{stddev:.3f} "
            row += "|"
            lines.append(row)

        lines.append("")
        lines.append("### Conclusion")
        lines.append("")
        lines.append(self.conclusion or "(no conclusion)")
        return "\n".join(lines)


def _score_output(text: str, scorer: ConfidenceScorer, engine: FiveAxisConsensusEngine) -> dict[str, float]:
    """Score a single output on all 10 dimensions (same as Gate 0)."""
    scores: dict[str, float] = {}
    cs = scorer.score_response(text)
    scores["completeness"] = cs.factors.get("completeness", 0.0)
    scores["certainty"] = cs.factors.get("certainty", 0.0)
    scores["specificity"] = cs.factors.get("specificity", 0.0)
    scores["consistency"] = cs.factors.get("consistency", 0.0)
    scores["model_quality"] = cs.factors.get("model_quality", 0.0)
    artifacts: dict[str, Any] = {"code": text, "docs": text}
    fr = engine.evaluate(artifacts)
    scores["correctness"] = fr.correctness
    scores["readability"] = fr.readability
    scores["architecture"] = fr.architecture
    scores["security"] = fr.security
    scores["performance"] = fr.performance
    return scores


def _mean_score(scores: dict[str, float]) -> float:
    """Compute mean of all dimension scores."""
    return sum(scores.values()) / len(scores) if scores else 0.0


def _determine_signal_strength(
    mean_stddev: dict[str, dict[str, tuple[float, float]]],
    gate_passed: bool,
    llm_skipped: bool,
) -> tuple[str, str]:
    """Determine signal strength and produce conclusion.

    Returns:
        (signal_strength, conclusion_text)
    """
    if not gate_passed:
        return ("calibration_failed",
                "Gate 0 calibration failed. Scoring instruments cannot "
                "reliably distinguish output quality levels. Slice 1 skipped. "
                "Recommendation: improve scoring instruments before re-evaluating.")

    if llm_skipped:
        return ("noise",
                "LLM arm skipped (no API key). Only frozen_mock vs "
                "role_specific_mock compared. Cannot assess LLM vs Mock gap. "
                "Recommendation: re-run with API key for full comparison.")

    # Collect per-task deltas: llm_mean - max(mock_means)
    deltas: list[float] = []
    for task_id in _TASK_IDS:
        task_data = mean_stddev.get(task_id, {})
        llm_ms = task_data.get(_ARM_LLM)
        frozen_ms = task_data.get(_ARM_FROZEN)
        role_ms = task_data.get(_ARM_ROLE_SPECIFIC)
        if llm_ms is None or frozen_ms is None:
            continue
        llm_mean = llm_ms[0]
        mock_means = [frozen_ms[0]]
        if role_ms is not None:
            mock_means.append(role_ms[0])
        delta = llm_mean - max(mock_means)
        deltas.append(delta)

    if not deltas:
        return ("noise", "Insufficient data for signal strength assessment.")

    median_delta = statistics.median(deltas)

    if median_delta > _SIG_SIGNIFICANT:
        strength = "significant"
    elif median_delta > _SIG_MARGINAL:
        strength = "marginal"
    else:
        strength = "noise"

    conclusion = (
        f"Across {len(deltas)} tasks, median LLM advantage = {median_delta:.3f} "
        f"(0-1 scale). Signal strength: {strength}. "
        f"Thresholds: significant >{_SIG_SIGNIFICANT}, "
        f"marginal >{_SIG_MARGINAL}, noise ≤{_SIG_MARGINAL}. "
    )
    if strength == "significant":
        conclusion += "LLM provides substantial quality advantage. Recommend full comparison in V4.5.0."
    elif strength == "marginal":
        conclusion += "LLM provides modest advantage. Recommend targeted LLM-as-judge evaluation before full investment."
    else:
        conclusion += "LLM advantage is within noise band. DevSquad may not need LLM for typical tasks."

    return (strength, conclusion)


def run_probe_slice(
    llm_backend: LLMBackend | None = None,
    n_samples: int = 3,
) -> ProbeSliceReport:
    """Run thin-slice quality probe.

    Args:
        llm_backend: LLM backend instance. None skips the LLM arm.
        n_samples: Samples per arm per task (default 3 for LLM stochasticity).

    Returns:
        ProbeSliceReport with gate_passed, task_results, mean_stddev,
        signal_strength, and conclusion.
    """
    global _call_counter
    _call_counter += 1

    # Precondition: Gate 0 must pass
    gate_result = run_calibration_gate()
    if not gate_result.passed:
        return ProbeSliceReport(
            gate_passed=False,
            signal_strength="calibration_failed",
            conclusion="Gate 0 failed. Probe skipped.",
        )

    # Load probe tasks
    try:
        data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        tasks: dict[str, str] = data["probe_tasks"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        return ProbeSliceReport(
            gate_passed=True,
            signal_strength="noise",
            conclusion=f"Failed to load probe tasks: {e}",
        )

    scorer = ConfidenceScorer()
    engine = FiveAxisConsensusEngine()
    frozen_mock = MockBackend()
    role_mock = RoleSpecificMockBackend(role_specific=True)

    task_results: dict[str, dict[str, list[float]]] = {}
    llm_skipped = llm_backend is None

    for task_id in _TASK_IDS:
        prompt = tasks.get(task_id, "")
        task_results[task_id] = {}

        # Arm 1: frozen_mock (deterministic, 1 sample is enough but run n for symmetry)
        scores_list: list[float] = []
        for _ in range(n_samples):
            output = frozen_mock.generate(prompt, role_name="AI Assistant", task_description=prompt)
            scores = _score_output(output, scorer, engine)
            scores_list.append(_mean_score(scores))
        task_results[task_id][_ARM_FROZEN] = scores_list

        # Arm 2: role_specific_mock (deterministic, run n for symmetry)
        scores_list = []
        for _ in range(n_samples):
            output = role_mock.generate(prompt, role_name="Architect", task_description=prompt)
            scores = _score_output(output, scorer, engine)
            scores_list.append(_mean_score(scores))
        task_results[task_id][_ARM_ROLE_SPECIFIC] = scores_list

        # Arm 3: llm (stochastic, n samples essential)
        if llm_backend is not None:
            scores_list = []
            for _ in range(n_samples):
                try:
                    output = llm_backend.generate(prompt, role_name="Architect", task_description=prompt)
                    scores = _score_output(output, scorer, engine)
                    scores_list.append(_mean_score(scores))
                except Exception:
                    scores_list.append(0.0)
            task_results[task_id][_ARM_LLM] = scores_list

    # Aggregate mean ± stddev
    mean_stddev: dict[str, dict[str, tuple[float, float]]] = {}
    for task_id, arms in task_results.items():
        mean_stddev[task_id] = {}
        for arm_id, score_list in arms.items():
            if score_list:
                m = statistics.mean(score_list)
                sd = statistics.stdev(score_list) if len(score_list) > 1 else 0.0
                mean_stddev[task_id][arm_id] = (m, sd)

    # Determine signal strength
    strength, conclusion = _determine_signal_strength(mean_stddev, True, llm_skipped)

    return ProbeSliceReport(
        gate_passed=True,
        task_results=task_results,
        mean_stddev=mean_stddev,
        signal_strength=strength,
        conclusion=conclusion,
        llm_arm_skipped=llm_skipped,
    )
