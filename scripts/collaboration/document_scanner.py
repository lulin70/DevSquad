"""Deterministic, read-only scans for explicitly supplied lifecycle documents.

The scanner is read-only, uses no SU/SFD, and never traverses directories. Contract boundary: no SU/SFD.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .lifecycle_break_vuln import categories_for_phase, phases_for_category
from .models_lifecycle import LifecycleFinding

_PHASES = tuple(f"P{index}" for index in range(1, 12))
_DEFAULT_CATEGORY_BY_PHASE = {
    "P1": "BREAK-1",
    "P2": "BREAK-4",
    "P3": "BREAK-2",
    "P4": "VULN-1",
    "P5": "BREAK-1",
    "P6": "VULN-4",
    "P7": "BREAK-5",
    "P8": "BREAK-2",
    "P9": "BREAK-2",
    "P10": "BREAK-5",
    "P11": "VULN-2",
}
PHASE_DOCUMENT_RULES: dict[str, dict[str, dict[str, str]]] = {
    phase: {"required_sections": {f"{phase.lower()}_evidence": phase}} for phase in _PHASES
}


@dataclass
class DocumentScanResult:
    """Result of scanning one explicitly supplied document."""

    path: str
    phase_id: str
    parsed: bool
    findings: list[LifecycleFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible scan result."""
        return {
            "path": self.path,
            "phase_id": self.phase_id,
            "parsed": self.parsed,
            "findings": [finding.to_dict() for finding in self.findings],
            "errors": list(self.errors),
        }


def _validate_phase(phase_id: str) -> None:
    if phase_id not in _PHASES:
        raise ValueError(f"Unknown lifecycle phase: {phase_id}")


def _normalise_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().rstrip("#").strip()).casefold()


def _markdown_headings(text: str) -> set[str]:
    headings: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.add(_normalise_heading(match.group(1)))
    return headings


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug or "item"


def _category_for_phase(phase_id: str) -> str:
    candidate = _DEFAULT_CATEGORY_BY_PHASE[phase_id]
    if phase_id in phases_for_category(candidate):
        return candidate
    categories = categories_for_phase(phase_id)
    if categories:
        return categories[0]
    return candidate


def _missing_finding(
    path: str,
    phase_id: str,
    item_type: str,
    item_path: str,
    expected: str,
) -> LifecycleFinding:
    category = _category_for_phase(phase_id)
    suggestion = f"Add the required {item_type.removeprefix('document_')} '{expected}' to {path}."
    return LifecycleFinding(
        category=category,
        rule_id=f"document.{phase_id.lower()}.missing.{_slug(item_path)}",
        severity="warning",
        lifecycle_phase=phase_id,
        artifact=path,
        status="detected",
        description=f"{phase_id} document is missing required {item_type.removeprefix('document_')}: {expected}.",
        evidence=[
            {
                "type": item_type,
                "path": item_path,
                "expected": expected,
                "suggestion": suggestion,
            }
        ],
        file_path=path,
        suggestion=suggestion,
    )


def _key_at_path(document: Any, key_path: str) -> tuple[bool, Any]:
    current = document
    for part in key_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _parse_document(path: Path, text: str) -> tuple[Any, bool, str | None]:
    suffix = path.suffix.casefold()
    if suffix in {".md", ".markdown"}:
        return _markdown_headings(text), True, None
    if suffix in {".yaml", ".yml"}:
        try:
            return yaml.safe_load(text), True, None
        except yaml.YAMLError:
            return None, False, "parse error: invalid YAML"
    if suffix == ".json":
        try:
            return json.loads(text), True, None
        except json.JSONDecodeError:
            return None, False, "parse error: invalid JSON"
    return None, False, f"unsupported extension: {suffix or '<none>'}"


def scan_document(
    path: str | Path,
    phase_id: str,
    *,
    required_sections: Mapping[str, str] | None = None,
    required_keys: Mapping[str, str] | None = None,
) -> DocumentScanResult:
    """Read and inspect one explicitly supplied document without writing it."""
    _validate_phase(phase_id)
    document_path = Path(path)
    display_path = str(path)
    try:
        text = document_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DocumentScanResult(display_path, phase_id, False, errors=["read error: file not found"])
    except IsADirectoryError:
        return DocumentScanResult(display_path, phase_id, False, errors=["read error: path is a directory"])
    except UnicodeDecodeError:
        return DocumentScanResult(display_path, phase_id, False, errors=["decode error: UTF-8"])
    except OSError:
        return DocumentScanResult(display_path, phase_id, False, errors=["read error: unreadable file"])

    parsed_document, parsed, error = _parse_document(document_path, text)
    if not parsed:
        return DocumentScanResult(display_path, phase_id, False, errors=[error or "parse error"])

    findings: list[LifecycleFinding] = []
    sections = required_sections or {}
    keys = required_keys or {}
    if document_path.suffix.casefold() in {".md", ".markdown"}:
        headings = parsed_document
        for item_path, expected in sections.items():
            if _normalise_heading(expected) not in headings:
                findings.append(_missing_finding(display_path, phase_id, "document_section", item_path, expected))
    elif document_path.suffix.casefold() in {".yaml", ".yml", ".json"}:
        for item_path, expected in keys.items():
            present, _ = _key_at_path(parsed_document, item_path)
            if not present:
                findings.append(_missing_finding(display_path, phase_id, "document_key", item_path, expected))

    return DocumentScanResult(display_path, phase_id, True, findings=findings)


def scan_phase_documents(documents: Mapping[str | Path, Mapping[str, Any]], phase_id: str) -> list[LifecycleFinding]:
    """Scan the explicitly listed documents for one lifecycle phase."""
    _validate_phase(phase_id)
    default_rules = PHASE_DOCUMENT_RULES[phase_id]
    findings: list[LifecycleFinding] = []
    for path, options in documents.items():
        if not isinstance(options, Mapping):
            raise ValueError("Document scan options must be a mapping")
        sections = options.get("required_sections", default_rules["required_sections"])
        keys = options.get("required_keys", default_rules.get("required_keys", {}))
        result = scan_document(path, phase_id, required_sections=sections, required_keys=keys)
        findings.extend(result.findings)
    return findings


__all__ = [
    "DocumentScanResult",
    "PHASE_DOCUMENT_RULES",
    "scan_document",
    "scan_phase_documents",
]
