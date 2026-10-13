"""Integration coverage for BREAK/VULN review wiring."""

from __future__ import annotations

import pytest

from scripts.collaboration.review_checkers import ReviewCheckers
from scripts.collaboration.two_stage_review_gate import ReviewStage, StageResult, TwoStageReviewGate


def _gate() -> TwoStageReviewGate:
    return TwoStageReviewGate(enable_redesign_audit=False)


def test_review_checkers_wires_critical_break1_and_line_range() -> None:
    checkers = ReviewCheckers()
    stage, findings = checkers.check_code_quality({"files": {"api.py": {"content": "@app.get('/x')\n"}}})
    finding = next(item for item in findings if item.category == "BREAK-1")
    assert stage == StageResult.FAIL
    assert finding.severity == "critical"
    assert finding.stage == ReviewStage.CODE_QUALITY
    assert finding.file_path == "api.py"
    assert finding.line_range == "1"


def test_gate_critical_taxonomy_finding_fails() -> None:
    result = _gate().review(code_changes={"files": {"api.py": {"content": "@app.get('/x')\n"}}})
    assert result.stage2_result == StageResult.FAIL
    assert not result.overall_passed
    assert any(f.category == "BREAK-1" for f in result.blocking_findings)


def test_documentation_changes_are_informational_na() -> None:
    result = _gate().review(code_changes={"files": {"README.md": {"content": "plain documentation\n"}}})
    scope = next(f for f in result.findings if f.category == "break_vuln_scope")
    assert scope.severity == "info"
    assert "not_applicable" in scope.description
    assert result.stage2_result == StageResult.WARN
    assert result.overall_passed


@pytest.mark.parametrize("payload", ["api.py", ["api.py"], [42]])
def test_invalid_files_payload_is_unparseable_not_na(payload: object) -> None:
    result = _gate().review(code_changes={"files": payload})
    scope = next(f for f in result.findings if f.category == "break_vuln_scope")
    assert scope.severity == "info"
    assert "unparseable_input" in scope.description
    assert "not_applicable" not in scope.description


def test_markdown_and_to_dict_expose_taxonomy_metadata() -> None:
    gate = _gate()
    result = gate.review(code_changes={"files": {"api.py": {"content": "@app.get('/x')\n"}}})
    report = gate.format_report(result)
    payload = result.to_dict()
    finding = next(item for item in payload["findings"] if item["category"] == "BREAK-1")
    assert "[BREAK-1]" in report
    assert "api.py" in report
    assert finding["line_range"] == "1"
    assert finding["file_path"] == "api.py"


def test_multi_file_findings_keep_their_source_path() -> None:
    checkers = ReviewCheckers()
    _, findings = checkers.check_code_quality(
        {
            "files": {
                "first.py": {"content": "@app.get('/first')\n"},
                "second.py": {"content": "@app.get('/second')\n"},
            }
        }
    )
    break1 = {finding.file_path for finding in findings if finding.category == "BREAK-1"}
    assert break1 == {"first.py", "second.py"}


def test_clean_route_reports_checked_scope() -> None:
    result = _gate().review(
        code_changes={
            "files": {
                "api.py": {
                    "content": "@app.get('/x')\ndef x():\n    return 1\nredirect('/x')\n",
                }
            }
        }
    )
    assert any(f.category == "break_vuln_scope" and "checked 10" in f.description for f in result.findings)
