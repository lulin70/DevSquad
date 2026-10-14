"""Unit tests for deterministic document scanning."""

import json

import yaml

from scripts.collaboration.document_scanner import PHASE_DOCUMENT_RULES, scan_document, scan_phase_documents


def test_markdown_sections_success_and_missing(tmp_path):
    path = tmp_path / "requirements.md"
    path.write_text("# Objectives\n\n## Acceptance Criteria\n", encoding="utf-8")
    result = scan_document(
        path, "P1", required_sections={"objectives": "Objectives", "acceptance": "Acceptance Criteria"}
    )
    assert result.parsed is True
    assert result.findings == []

    missing = scan_document(path, "P1", required_sections={"success": "Success Criteria"})
    assert missing.findings[0].rule_id == "document.p1.missing.success"
    assert missing.findings[0].evidence[0]["type"] == "document_section"


def test_yaml_and_json_dotted_keys_success_and_missing(tmp_path):
    yaml_path = tmp_path / "plan.yaml"
    yaml_path.write_text(yaml.safe_dump({"service": {"name": "demo"}}), encoding="utf-8")
    assert scan_document(yaml_path, "P2", required_keys={"service.name": "service.name"}).findings == []
    finding = scan_document(yaml_path, "P2", required_keys={"service.owner": "service.owner"}).findings[0]
    assert finding.category == "BREAK-4"
    assert finding.evidence[0]["type"] == "document_key"

    json_path = tmp_path / "plan.json"
    json_path.write_text(json.dumps({"release": {"rollback": True}}), encoding="utf-8")
    assert scan_document(json_path, "P10", required_keys={"release.rollback": "release.rollback"}).parsed is True


def test_parse_unknown_extension_and_decode_errors_are_stable(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    result = scan_document(invalid, "P4")
    assert result.parsed is False
    assert result.errors == ["parse error: invalid JSON"]

    unknown = tmp_path / "notes.txt"
    unknown.write_text("content", encoding="utf-8")
    assert scan_document(unknown, "P4").errors == ["unsupported extension: .txt"]

    binary = tmp_path / "binary.md"
    binary.write_bytes(b"\xff")
    assert scan_document(binary, "P4").errors == ["decode error: UTF-8"]


def test_phase_rules_cover_all_phases_and_explicit_documents_only(tmp_path):
    assert set(PHASE_DOCUMENT_RULES) == {f"P{index}" for index in range(1, 12)}
    path = tmp_path / "p7.md"
    path.write_text("# P7 Evidence\n", encoding="utf-8")
    findings = scan_phase_documents({path: {"required_sections": {"evidence": "P7 Evidence"}}}, "P7")
    assert findings == []


def test_scan_result_serializes(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# Present\n", encoding="utf-8")
    result = scan_document(path, "P1", required_sections={"missing": "Missing"})
    data = result.to_dict()
    assert data["path"] == str(path)
    assert data["findings"][0]["lifecycle_phase"] == "P1"
