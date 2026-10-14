"""Deterministic lifecycle BREAK/VULN finding producers for phases P1-P11."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .lifecycle_break_vuln import lifecycle_finding_from_review, phases_for_category
from .models_lifecycle import LifecycleFinding
from .two_stage_review_gate import ReviewFinding, ReviewStage

_PHASE_MISSING_RULES: dict[str, dict[str, str]] = {
    "P1": {
        "objectives": "BREAK-1",
        "user_stories": "BREAK-1",
        "acceptance_criteria": "BREAK-5",
        "success_criteria": "BREAK-5",
        "preconditions": "BREAK-3",
    },
    "P2": {
        "architecture": "BREAK-4",
        "service_boundaries": "BREAK-4",
        "data_flows": "VULN-2",
        "dependencies": "VULN-2",
    },
    "P3": {
        "api_specifications": "BREAK-2",
        "interfaces": "BREAK-2",
        "preconditions": "BREAK-3",
        "validation_rules": "BREAK-3",
        "error_handling": "BREAK-2",
    },
    "P4": {
        "data_model": "BREAK-4",
        "schema": "BREAK-4",
        "transaction_strategy": "VULN-2",
        "access_controls": "VULN-1",
        "sensitive_data_controls": "VULN-1",
    },
    "P5": {
        "entry_points": "BREAK-1",
        "user_flows": "BREAK-1",
        "navigation_targets": "BREAK-5",
        "action_reachability": "VULN-3",
        "navigation_consistency": "VULN-5",
    },
    "P6": {
        "threat_model": "VULN-4",
        "authz_matrix": "VULN-4",
        "input_validation": "VULN-4",
        "data_classification": "VULN-1",
        "secret_controls": "VULN-1",
    },
    "P7": {
        "test_plan": "BREAK-5",
        "test_cases": "BREAK-5",
        "acceptance_tests": "BREAK-5",
        "coverage_dimensions": "VULN-4",
        "user_journeys": "VULN-3",
    },
    "P8": {
        "runnable_code": "BREAK-2",
        "implementation": "BREAK-2",
        "unit_tests": "BREAK-5",
        "input_validation": "VULN-4",
        "route_reachability": "VULN-3",
        "data_serialization": "VULN-1",
    },
    "P9": {
        "test_results": "BREAK-2",
        "failed_tests": "BREAK-5",
        "state_consistency": "VULN-2",
        "journey_reachability": "VULN-3",
        "navigation_consistency": "VULN-5",
    },
    "P10": {
        "release_checklist": "BREAK-5",
        "deployment_plan": "BREAK-5",
        "rollback_plan": "BREAK-2",
        "rollback_verified": "BREAK-2",
        "health_checks": "VULN-3",
        "secrets_config": "VULN-1",
    },
    "P11": {
        "monitoring": "BREAK-2",
        "alerts": "BREAK-2",
        "incident_response": "BREAK-5",
        "state_consistency": "VULN-2",
        "operation_reachability": "VULN-3",
        "navigation_consistency": "VULN-5",
    },
}

_PHASES = tuple(f"P{index}" for index in range(1, 12))


def _validate_phase(phase_id: str) -> None:
    if phase_id not in _PHASES:
        raise ValueError(f"Unknown lifecycle phase: {phase_id}")


def _finding_from_failure(phase_id: str, failure: Mapping[str, Any]) -> LifecycleFinding:
    if not isinstance(failure, Mapping):
        raise ValueError("Each lifecycle failure must be a mapping")
    if "category" not in failure or "description" not in failure:
        raise ValueError("Each lifecycle failure requires category and description")
    category = failure["category"]
    if not isinstance(category, str):
        raise ValueError("Lifecycle finding category must be a string")
    phases_for_category(category)
    evidence = failure.get("evidence", [])
    if evidence is None:
        evidence = []
    if isinstance(evidence, (str, bytes)):
        evidence = [evidence]
    return LifecycleFinding(
        category=category,
        rule_id=str(failure.get("rule_id", category.lower().replace("-", "_"))),
        severity=str(failure.get("severity", "warning")),
        lifecycle_phase=phase_id,
        artifact=str(failure.get("artifact", "")),
        status=str(failure.get("status", "detected")),
        description=str(failure["description"]),
        evidence=list(evidence),
        file_path=str(failure.get("file_path", "")),
        line_range=str(failure.get("line_range", "")),
        suggestion=str(failure.get("suggestion", "")),
    )


def _review_from_value(value: ReviewFinding | Mapping[str, Any]) -> ReviewFinding:
    if isinstance(value, ReviewFinding):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("Each review finding must be a ReviewFinding or mapping")
    try:
        stage = value.get("stage", ReviewStage.SPEC_COMPLIANCE)
        if isinstance(stage, str):
            stage = ReviewStage(stage)
        return ReviewFinding(
            stage=stage,
            severity=str(value["severity"]),
            category=str(value["category"]),
            description=str(value["description"]),
            file_path=str(value.get("file_path", "")),
            line_range=str(value.get("line_range", "")),
            suggestion=str(value.get("suggestion", "")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Invalid review finding mapping") from exc


def _produce(phase_id: str, artifacts: Mapping[str, Any] | None) -> list[LifecycleFinding]:
    _validate_phase(phase_id)
    if artifacts is None:
        return []
    if not isinstance(artifacts, Mapping):
        raise ValueError("Lifecycle artifacts must be a mapping")
    if not artifacts:
        return []

    findings: list[LifecycleFinding] = []
    rules = _PHASE_MISSING_RULES[phase_id]
    missing = artifacts.get("missing", [])
    if not isinstance(missing, list):
        raise ValueError("Lifecycle artifacts.missing must be a list")
    for item in missing:
        if not isinstance(item, str):
            raise ValueError("Each missing lifecycle artifact must be a string")
        category = rules.get(item)
        if category is None:
            continue
        findings.append(
            LifecycleFinding(
                category=category,
                rule_id=f"lifecycle.{phase_id.lower()}.missing.{item}",
                severity="warning",
                lifecycle_phase=phase_id,
                artifact=item,
                status="detected",
                description=f"{phase_id} is missing required artifact: {item}.",
                evidence=[{"type": "missing_artifact", "artifact": item}],
                suggestion=f"Provide the {item} artifact before completing {phase_id}.",
            )
        )

    failures = artifacts.get("failures", [])
    if not isinstance(failures, list):
        raise ValueError("Lifecycle artifacts.failures must be a list")
    findings.extend(_finding_from_failure(phase_id, failure) for failure in failures)

    review_findings = artifacts.get("review_findings", [])
    if not isinstance(review_findings, list):
        raise ValueError("Lifecycle artifacts.review_findings must be a list")
    for value in review_findings:
        review = _review_from_value(value)
        category = review.category
        if phase_id in phases_for_category(category):
            findings.append(lifecycle_finding_from_review(review, lifecycle_phase=phase_id))

    checks = artifacts.get("checks", {})
    if not isinstance(checks, Mapping):
        raise ValueError("Lifecycle artifacts.checks must be a mapping")
    for check_name, passed in checks.items():
        if check_name not in rules or passed is not False:
            continue
        category = rules[check_name]
        findings.append(
            LifecycleFinding(
                category=category,
                rule_id=f"lifecycle.{phase_id.lower()}.check.{check_name}",
                severity="warning",
                lifecycle_phase=phase_id,
                artifact=check_name,
                status="detected",
                description=f"{phase_id} check failed: {check_name}.",
                evidence=[{"type": "check", "name": check_name, "passed": False}],
            )
        )
    return findings


def produce_p1_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P1."""
    return _produce("P1", artifacts)


def produce_p2_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P2."""
    return _produce("P2", artifacts)


def produce_p3_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P3."""
    return _produce("P3", artifacts)


def produce_p4_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P4."""
    return _produce("P4", artifacts)


def produce_p5_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P5."""
    return _produce("P5", artifacts)


def produce_p6_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P6."""
    return _produce("P6", artifacts)


def produce_p7_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P7."""
    return _produce("P7", artifacts)


def produce_p8_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P8."""
    return _produce("P8", artifacts)


def produce_p9_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P9."""
    return _produce("P9", artifacts)


def produce_p10_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P10."""
    return _produce("P10", artifacts)


def produce_p11_findings(artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for P11."""
    return _produce("P11", artifacts)


PHASE_PRODUCERS: dict[str, Callable[[Mapping[str, Any] | None], list[LifecycleFinding]]] = {
    "P1": produce_p1_findings,
    "P2": produce_p2_findings,
    "P3": produce_p3_findings,
    "P4": produce_p4_findings,
    "P5": produce_p5_findings,
    "P6": produce_p6_findings,
    "P7": produce_p7_findings,
    "P8": produce_p8_findings,
    "P9": produce_p9_findings,
    "P10": produce_p10_findings,
    "P11": produce_p11_findings,
}


def produce_phase_findings(phase_id: str, artifacts: Mapping[str, Any] | None = None) -> list[LifecycleFinding]:
    """Produce deterministic findings for one lifecycle phase."""
    try:
        producer = PHASE_PRODUCERS[phase_id]
    except KeyError as exc:
        raise ValueError(f"Unknown lifecycle phase: {phase_id}") from exc
    return producer(artifacts)


__all__ = [
    "PHASE_PRODUCERS",
    "produce_phase_findings",
    *(f"produce_p{index}_findings" for index in range(1, 12)),
]
