"""Deterministic mapping between BREAK/VULN findings and lifecycle phases."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .models_lifecycle import LifecycleFinding
from .two_stage_review_gate import ReviewFinding, ReviewStage

BREAK_VULN_PHASES: dict[str, tuple[str, ...]] = {
    "BREAK-1": ("P1", "P5"),
    "BREAK-2": ("P3", "P8", "P9"),
    "BREAK-3": ("P3", "P4", "P6"),
    "BREAK-4": ("P2", "P3", "P4"),
    "BREAK-5": ("P1", "P5", "P8", "P9", "P10"),
    "VULN-1": ("P4", "P6", "P8", "P9", "P11"),
    "VULN-2": ("P4", "P8", "P9", "P11"),
    "VULN-3": ("P5", "P8", "P9", "P11"),
    "VULN-4": ("P3", "P4", "P6", "P8", "P9"),
    "VULN-5": ("P5", "P8", "P9", "P11"),
}

_LIFECYCLE_PHASES = tuple(f"P{index}" for index in range(1, 12))
_RULE_ID_PATTERN = re.compile(r"\bBV-[A-Za-z0-9_-]+\b")


def phases_for_category(category: str) -> tuple[str, ...]:
    """Return the deterministic lifecycle phases for a finding category."""
    try:
        return BREAK_VULN_PHASES[category]
    except KeyError as exc:
        raise ValueError(f"Unknown BREAK/VULN category: {category}") from exc


def categories_for_phase(phase_id: str) -> tuple[str, ...]:
    """Return categories mapped to a lifecycle phase."""
    if phase_id not in _LIFECYCLE_PHASES:
        raise ValueError(f"Unknown lifecycle phase: {phase_id}")
    return tuple(category for category, phases in BREAK_VULN_PHASES.items() if phase_id in phases)


def _finding_rule_id(description: str, category: str) -> str:
    """Extract a stable BV rule id or derive one from the category."""
    match = _RULE_ID_PATTERN.search(description)
    return match.group(0) if match else category.lower().replace("-", "_")


def _finding_evidence(finding: ReviewFinding, evidence: Iterable[Any]) -> list[Any]:
    """Preserve supplied evidence and add structured description/location evidence."""
    result = list(evidence)
    result.append({"type": "description", "value": finding.description})
    result.append(
        {
            "type": "location",
            "file_path": finding.file_path,
            "line_range": finding.line_range,
        }
    )
    return result


def lifecycle_finding_from_review(
    finding: ReviewFinding,
    lifecycle_phase: str | None = None,
    artifact: str = "",
    status: str = "detected",
    evidence: Iterable[Any] = (),
) -> LifecycleFinding:
    """Convert a review finding into a lifecycle finding."""
    phases = phases_for_category(finding.category)
    phase = lifecycle_phase or phases[0]
    if phase not in phases:
        raise ValueError(f"Phase {phase} is not mapped to category {finding.category}")
    return LifecycleFinding(
        category=finding.category,
        rule_id=_finding_rule_id(finding.description, finding.category),
        severity=finding.severity,
        lifecycle_phase=phase,
        artifact=artifact,
        status=status,
        description=finding.description,
        evidence=_finding_evidence(finding, evidence),
        file_path=finding.file_path,
        line_range=finding.line_range,
        suggestion=finding.suggestion,
    )


def review_finding_from_lifecycle(finding: LifecycleFinding) -> ReviewFinding:
    """Convert a lifecycle finding into the appropriate review stage finding."""
    stage = (
        ReviewStage.SPEC_COMPLIANCE
        if finding.lifecycle_phase in {f"P{index}" for index in range(1, 8)}
        else ReviewStage.CODE_QUALITY
    )
    return ReviewFinding(
        stage=stage,
        severity=finding.severity,
        category=finding.category,
        description=finding.description,
        file_path=finding.file_path,
        line_range=finding.line_range,
        suggestion=finding.suggestion,
    )


def map_findings_to_phase(
    findings: Iterable[LifecycleFinding | ReviewFinding], phase_id: str
) -> list[LifecycleFinding]:
    """Return findings applicable to a lifecycle phase, converting review findings."""
    categories_for_phase(phase_id)
    mapped: list[LifecycleFinding] = []
    for finding in findings:
        category = finding.category
        if phase_id not in phases_for_category(category):
            continue
        lifecycle_finding = (
            finding
            if isinstance(finding, LifecycleFinding)
            else lifecycle_finding_from_review(finding, lifecycle_phase=phase_id)
        )
        mapped.append(lifecycle_finding)
    return mapped


__all__ = [
    "BREAK_VULN_PHASES",
    "categories_for_phase",
    "lifecycle_finding_from_review",
    "map_findings_to_phase",
    "phases_for_category",
    "review_finding_from_lifecycle",
]
