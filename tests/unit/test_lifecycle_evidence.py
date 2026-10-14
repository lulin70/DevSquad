"""Unit tests for explicit CI/runtime evidence adapters."""

from scripts.collaboration.lifecycle_evidence import findings_from_junit_xml, findings_from_runtime_evidence


def test_runtime_evidence_maps_failed_tests_and_health_checks():
    findings = findings_from_runtime_evidence(
        "P9",
        {
            "source": "ci.json",
            "failed_tests": [{"name": "test_login"}],
            "failed_health_checks": ["api-ready"],
            "errors": ["service stopped"],
        },
    )
    assert len(findings) == 3
    assert findings[0].lifecycle_phase == "P9"
    assert findings[0].evidence[0]["type"] == "failed_test"
    assert findings[1].category == "VULN-3"


def test_junit_adapter_reads_only_supplied_report(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite><testcase name="ok" />'
        '<testcase name="bad"><failure>assertion failed</failure></testcase></testsuite>',
        encoding="utf-8",
    )
    findings = findings_from_junit_xml(report, "P7")
    assert len(findings) == 1
    assert findings[0].artifact == str(report)
    assert findings[0].evidence[0]["name"] == "bad"
