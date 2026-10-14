"""Unit tests for deterministic lifecycle finding producers."""

import pytest

from scripts.collaboration.lifecycle_finding_producers import (
    PHASE_PRODUCERS,
    produce_phase_findings,
)
from scripts.collaboration.two_stage_review_gate import ReviewFinding, ReviewStage


@pytest.mark.parametrize("phase_id", [f"P{index}" for index in range(1, 12)])
def test_all_phases_are_registered_and_empty_input_is_quiet(phase_id: str) -> None:
    assert phase_id in PHASE_PRODUCERS
    assert produce_phase_findings(phase_id) == []
    assert produce_phase_findings(phase_id, {}) == []


@pytest.mark.parametrize(
    ("phase_id", "artifact", "category"),
    [
        ("P1", "objectives", "BREAK-1"),
        ("P2", "architecture", "BREAK-4"),
        ("P3", "api_specifications", "BREAK-2"),
        ("P4", "data_model", "BREAK-4"),
        ("P5", "entry_points", "BREAK-1"),
        ("P6", "threat_model", "VULN-4"),
        ("P7", "test_plan", "BREAK-5"),
        ("P8", "runnable_code", "BREAK-2"),
        ("P9", "test_results", "BREAK-2"),
        ("P10", "release_checklist", "BREAK-5"),
        ("P11", "monitoring", "BREAK-2"),
    ],
)
def test_missing_artifact_maps_to_phase_category(phase_id: str, artifact: str, category: str) -> None:
    finding = produce_phase_findings(phase_id, {"missing": [artifact]})[0]
    assert finding.lifecycle_phase == phase_id
    assert finding.category == category
    assert finding.artifact == artifact
    assert phase_id in finding.description


def test_failure_custom_finding_preserves_evidence() -> None:
    finding = produce_phase_findings(
        "P8",
        {
            "failures": [
                {
                    "category": "VULN-1",
                    "description": "Serialization exposes a secret field.",
                    "rule_id": "BV-P8-secret-serialization",
                    "severity": "critical",
                    "artifact": "serializer.py",
                    "status": "detected",
                    "evidence": [{"token": "secret"}],
                    "file_path": "src/serializer.py",
                    "line_range": "18-19",
                    "suggestion": "Remove the secret field.",
                }
            ]
        },
    )[0]
    assert finding.category == "VULN-1"
    assert finding.lifecycle_phase == "P8"
    assert finding.evidence == [{"token": "secret"}]
    assert finding.file_path == "src/serializer.py"
    assert finding.line_range == "18-19"


def test_review_findings_are_converted_and_filtered_by_phase() -> None:
    applicable = ReviewFinding(
        stage=ReviewStage.CODE_QUALITY,
        severity="warning",
        category="VULN-3",
        description="Route is unreachable.",
        file_path="routes.py",
        line_range="7",
    )
    unrelated = ReviewFinding(
        stage=ReviewStage.CODE_QUALITY,
        severity="warning",
        category="BREAK-1",
        description="Not applicable to P8.",
    )
    findings = produce_phase_findings("P8", {"review_findings": [applicable, unrelated]})
    assert len(findings) == 1
    assert findings[0].category == "VULN-3"
    assert findings[0].lifecycle_phase == "P8"
    assert findings[0].line_range == "7"


def test_false_checks_produce_findings_and_true_or_unknown_do_not() -> None:
    findings = produce_phase_findings(
        "P1",
        {"checks": {"objectives": False, "acceptance_criteria": True, "future_check": False}},
    )
    assert len(findings) == 1
    assert findings[0].artifact == "objectives"
    assert findings[0].category == "BREAK-1"


@pytest.mark.parametrize("phase_id", ["P0", "P12", "phase-1"])
def test_invalid_phase_fails_closed(phase_id: str) -> None:
    with pytest.raises(ValueError):
        produce_phase_findings(phase_id)


def test_invalid_failure_category_fails_closed() -> None:
    with pytest.raises(ValueError):
        produce_phase_findings("P1", {"failures": [{"category": "BREAK-9", "description": "bad"}]})


def test_invalid_artifact_shape_fails_closed() -> None:
    with pytest.raises(ValueError):
        produce_phase_findings("P1", {"checks": []})
