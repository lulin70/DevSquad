"""Deterministic adapters for explicit CI and runtime evidence.

The adapters read only caller-supplied files or mappings. They do not discover
files, execute tests, inspect databases, or collect SU/SFD black-box evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET

from .lifecycle_finding_producers import produce_phase_findings
from .models_lifecycle import LifecycleFinding


def _finding(
    phase_id: str,
    category: str,
    rule_id: str,
    description: str,
    artifact: str,
    evidence: Any,
    suggestion: str,
) -> LifecycleFinding:
    return LifecycleFinding(
        category=category,
        rule_id=rule_id,
        severity="warning",
        lifecycle_phase=phase_id,
        artifact=artifact,
        status="detected",
        description=description,
        evidence=[evidence],
        file_path=artifact,
        suggestion=suggestion,
    )


def findings_from_runtime_evidence(
    phase_id: str,
    evidence: dict[str, Any] | None,
) -> list[LifecycleFinding]:
    """Convert explicit test, health, release, and log evidence to findings."""
    if evidence is None:
        return []
    if not isinstance(evidence, dict):
        raise ValueError("Runtime evidence must be a mapping")

    findings = list(produce_phase_findings(phase_id, evidence.get("artifacts"))) if evidence.get("artifacts") else []
    failed_tests = evidence.get("failed_tests", [])
    if not isinstance(failed_tests, list):
        raise ValueError("Runtime evidence.failed_tests must be a list")
    for item in failed_tests:
        name = str(item.get("name", item)) if isinstance(item, dict) else str(item)
        findings.append(
            _finding(
                phase_id,
                "BREAK-5" if phase_id in {"P7", "P9", "P10"} else "BREAK-2",
                f"evidence.{phase_id.lower()}.failed_test",
                f"{phase_id} evidence reports a failed test: {name}.",
                str(evidence.get("source", "runtime evidence")),
                {"type": "failed_test", "name": name},
                "Fix the failed test and rerun the relevant lifecycle checks.",
            )
        )

    failed_health = evidence.get("failed_health_checks", [])
    if not isinstance(failed_health, list):
        raise ValueError("Runtime evidence.failed_health_checks must be a list")
    for item in failed_health:
        name = str(item.get("name", item)) if isinstance(item, dict) else str(item)
        findings.append(
            _finding(
                phase_id,
                "VULN-3",
                f"evidence.{phase_id.lower()}.health_check",
                f"{phase_id} evidence reports a failed health check: {name}.",
                str(evidence.get("source", "runtime evidence")),
                {"type": "failed_health_check", "name": name},
                "Restore the health check and verify the operational path before release.",
            )
        )

    errors = evidence.get("errors", [])
    if not isinstance(errors, list):
        raise ValueError("Runtime evidence.errors must be a list")
    for error in errors:
        findings.append(
            _finding(
                phase_id,
                "BREAK-2",
                f"evidence.{phase_id.lower()}.runtime_error",
                f"{phase_id} evidence contains a runtime error: {error}.",
                str(evidence.get("source", "runtime evidence")),
                {"type": "runtime_error", "message": str(error)},
                "Resolve the runtime error and repeat the explicit evidence collection.",
            )
        )
    return findings


def findings_from_junit_xml(path: str | Path, phase_id: str) -> list[LifecycleFinding]:
    """Parse one explicit JUnit XML report without modifying it."""
    report_path = Path(path)
    try:
        root = ET.parse(report_path).getroot()
    except FileNotFoundError as exc:
        raise ValueError("JUnit report not found") from exc
    except (ET.ParseError, OSError) as exc:
        raise ValueError("Invalid JUnit XML report") from exc

    findings: list[LifecycleFinding] = []
    for testcase in root.iter("testcase"):
        failure = testcase.find("failure")
        if failure is None:
            failure = testcase.find("error")
        if failure is None:
            continue
        name = testcase.attrib.get("name", "unnamed test")
        findings.extend(
            findings_from_runtime_evidence(
                phase_id,
                {
                    "source": str(report_path),
                    "failed_tests": [{"name": name, "message": failure.text or ""}],
                },
            )
        )
    return findings


__all__ = ["findings_from_junit_xml", "findings_from_runtime_evidence"]
