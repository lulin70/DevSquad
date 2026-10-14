"""Integration tests for document scans through the lifecycle protocol."""

from scripts.collaboration.lifecycle_protocol import (
    DocumentScanResult,
    RemediationProposal,
    proposal_from_finding,
    scan_document,
    scan_phase_documents,
)


def test_document_scan_findings_flow_into_lifecycle_and_proposal(tmp_path):
    path = tmp_path / "architecture.yaml"
    path.write_text("service:\n  name: demo\n", encoding="utf-8")
    result = scan_document(path, "P2", required_keys={"service.owner": "service.owner"})
    assert isinstance(result, DocumentScanResult)
    assert len(result.findings) == 1
    proposal = proposal_from_finding(result.findings[0])
    assert isinstance(proposal, RemediationProposal)
    assert proposal.lifecycle_phase == "P2"


def test_phase_scan_uses_only_explicit_files(tmp_path):
    path = tmp_path / "release.md"
    path.write_text("# Release Checklist\n", encoding="utf-8")
    findings = scan_phase_documents(
        {path: {"required_sections": {"checklist": "Release Checklist", "rollback": "Rollback Plan"}}},
        "P10",
    )
    assert len(findings) == 1
    assert findings[0].evidence[0]["path"] == "rollback"
