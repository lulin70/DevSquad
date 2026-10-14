"""Tests for lifecycle BREAK/VULN finding models and phase mappings."""

import pytest

from scripts.collaboration.lifecycle_break_vuln import (
    BREAK_VULN_PHASES,
    categories_for_phase,
    lifecycle_finding_from_review,
    map_findings_to_phase,
    phases_for_category,
    review_finding_from_lifecycle,
)
from scripts.collaboration.lifecycle_protocol import GateResult
from scripts.collaboration.models_lifecycle import LifecycleFinding
from scripts.collaboration.two_stage_review_gate import ReviewFinding, ReviewStage


def _review_finding(category: str = "BREAK-1") -> ReviewFinding:
    return ReviewFinding(
        stage=ReviewStage.CODE_QUALITY,
        severity="critical",
        category=category,
        description="route issue (BV-BREAK1-route-without-handler)",
        file_path="src/routes.py",
        line_range="42",
        suggestion="Add a handler.",
    )


def test_lifecycle_finding_serializes_and_has_stable_defaults() -> None:
    finding = LifecycleFinding(
        category="VULN-1",
        rule_id="BV-VULN1-orm-object-returned",
        severity="critical",
        lifecycle_phase="P4",
        artifact="api.py",
        status="detected",
        description="ORM object returned",
        evidence=[{"type": "location", "file_path": "api.py", "line_range": "8"}],
        file_path="api.py",
        line_range="8",
        suggestion="Serialize the response.",
    )

    data = finding.to_dict()
    assert data["category"] == "VULN-1"
    assert data["lifecycle_phase"] == "P4"
    assert data["evidence"][0]["file_path"] == "api.py"
    assert LifecycleFinding().to_dict()["status"] == "planned"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"category": "BREAK-9"},
        {"lifecycle_phase": "P12"},
        {"status": "open"},
    ],
)
def test_lifecycle_finding_rejects_invalid_values(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        LifecycleFinding(**kwargs)


def test_all_ten_categories_have_expected_mapping() -> None:
    assert BREAK_VULN_PHASES == {
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
    assert phases_for_category("BREAK-2") == ("P3", "P8", "P9")
    assert set(categories_for_phase("P11")) == {"VULN-1", "VULN-2", "VULN-3", "VULN-5"}


@pytest.mark.parametrize("value", ["BREAK-9", "", "VULN-0"])
def test_unknown_category_raises(value: str) -> None:
    with pytest.raises(ValueError):
        phases_for_category(value)


@pytest.mark.parametrize("value", ["P0", "P12", "phase-1"])
def test_unknown_phase_raises(value: str) -> None:
    with pytest.raises(ValueError):
        categories_for_phase(value)


def test_review_finding_converts_both_directions_and_preserves_evidence() -> None:
    review = _review_finding()
    lifecycle = lifecycle_finding_from_review(
        review,
        artifact="route-artifact",
        evidence=("scanner evidence",),
    )

    assert lifecycle.lifecycle_phase == "P1"
    assert lifecycle.rule_id == "BV-BREAK1-route-without-handler"
    assert "scanner evidence" in lifecycle.evidence
    assert {item["type"] for item in lifecycle.evidence if isinstance(item, dict)} == {
        "description",
        "location",
    }

    converted = review_finding_from_lifecycle(lifecycle)
    assert converted.stage is ReviewStage.SPEC_COMPLIANCE
    assert converted.category == review.category
    assert converted.description == review.description
    assert converted.file_path == review.file_path
    assert converted.line_range == review.line_range
    assert converted.suggestion == review.suggestion


def test_lifecycle_to_review_uses_code_quality_for_late_phases() -> None:
    finding = LifecycleFinding(category="VULN-1", lifecycle_phase="P8")
    assert review_finding_from_lifecycle(finding).stage is ReviewStage.CODE_QUALITY


def test_map_findings_to_phase_filters_and_converts() -> None:
    lifecycle = LifecycleFinding(category="BREAK-1", lifecycle_phase="P5")
    review = _review_finding("BREAK-2")

    result = map_findings_to_phase([lifecycle, review], "P5")
    assert len(result) == 1
    assert result[0] is lifecycle

    result = map_findings_to_phase([review], "P8")
    assert len(result) == 1
    assert result[0].category == "BREAK-2"
    assert result[0].lifecycle_phase == "P8"


def test_gate_result_serializes_lifecycle_findings() -> None:
    finding = LifecycleFinding(category="BREAK-1", lifecycle_phase="P1")
    result = GateResult(passed=True, verdict="APPROVE", lifecycle_findings=[finding])

    data = result.to_dict()
    assert data["lifecycle_findings_count"] == 1
    assert data["lifecycle_findings"][0]["category"] == "BREAK-1"
