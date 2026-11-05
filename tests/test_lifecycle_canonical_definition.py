"""Canonical lifecycle definition contract tests.

Verifies that the lifecycle phases (P0-P11), role assignments, gate
conditions, and dispatch step mappings all use one canonical vocabulary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.collaboration.dispatch_lifecycle import (
    DISPATCH_LIFECYCLE_MAPPING,
    DISPATCH_STAGE_LABELS,
)
from scripts.collaboration.lifecycle_gate import check_gate_basic, check_role_participation
from scripts.collaboration.lifecycle_protocol import PhaseState
from scripts.collaboration.lifecycle_shortcut_adapter import FullLifecycleAdapter, ShortcutLifecycleAdapter
from scripts.collaboration.lifecycle_shortcut_helpers import get_phase_definition
from scripts.collaboration.models import ROLE_REGISTRY
from scripts.collaboration.workflow_engine_base import (
    LIFECYCLE_TEMPLATES,
    PHASE_TEMPLATES,
)

pytestmark = pytest.mark.unit

CANONICAL_PHASES = [f"P{index}" for index in range(0, 12)]

REPO_ROOT = Path(__file__).resolve().parents[1]

SHORT_ROLE_IDS = {
    "pm": "product-manager",
    "arch": "architect",
    "sec": "security",
    "test": "tester",
    "coder": "solo-coder",
    "infra": "devops",
    "ui": "ui-designer",
}


def _parse_phase_table(filename: str) -> dict[str, list[str]]:
    """Return the lifecycle table rows of a markdown document keyed by phase ID."""
    rows: dict[str, list[str]] = {}
    text = (REPO_ROOT / filename).read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("| P"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6 or cells[0] not in CANONICAL_PHASES:
            continue
        rows[cells[0]] = cells
    return rows


def _assert_optional_flag(filename: str, phase_id: str, cell: str, optional: bool) -> None:
    accepted = {"Yes", "是", "✅"} if optional else {"No", "否", "❌"}
    assert cell in accepted, f"{filename} {phase_id} optional flag '{cell}' is wrong"


def test_canonical_phase_set() -> None:
    """P0-P11 exist and P0 is optional."""
    assert set(PHASE_TEMPLATES) == set(CANONICAL_PHASES)
    assert PHASE_TEMPLATES["P0"]["optional"] is True


def test_phase_roles_are_registry_roles() -> None:
    """Every phase role and reviewer belongs to the 7-role registry."""
    legal_roles = set(ROLE_REGISTRY)
    for phase_id, phase in PHASE_TEMPLATES.items():
        assert phase["role_id"] in legal_roles, f"{phase_id} has unknown lead role"
        for reviewer in phase["reviewers"]:
            assert reviewer in legal_roles, f"{phase_id} has unknown reviewer {reviewer}"


def test_all_registry_roles_are_used() -> None:
    """All 7 roles appear somewhere in the phase table."""
    used_roles = set()
    for phase in PHASE_TEMPLATES.values():
        used_roles.add(phase["role_id"])
        used_roles.update(phase["reviewers"])
    assert used_roles == set(ROLE_REGISTRY)


def test_lifecycle_templates_reference_known_phases() -> None:
    """Every template phase ID is canonical and every phase is in a template."""
    covered_phases = set()
    for template_name, phase_ids in LIFECYCLE_TEMPLATES.items():
        for phase_id in phase_ids:
            assert phase_id in CANONICAL_PHASES, f"{template_name} references invalid phase {phase_id}"
            covered_phases.add(phase_id)
    assert covered_phases == set(CANONICAL_PHASES)


def test_gate_condition_keywords() -> None:
    """Mandatory gate additions are present in the phase definitions."""
    assert "dependency" in PHASE_TEMPLATES["P6"]["gate_condition"]
    assert "NFR" in PHASE_TEMPLATES["P9"]["gate_condition"]
    assert "UAT" in PHASE_TEMPLATES["P9"]["gate_condition"]
    assert "migration" in PHASE_TEMPLATES["P10"]["gate_condition"]


def test_dispatch_mapping_values_are_canonical() -> None:
    """Dispatch step targets are canonical phase IDs."""
    for step_name, phase_id in DISPATCH_LIFECYCLE_MAPPING.items():
        assert phase_id in CANONICAL_PHASES, f"{step_name} maps to invalid phase {phase_id}"


def test_dispatch_mapping_steps_have_labels() -> None:
    """Each dispatch target phase has a semantic label."""
    for step_name, phase_id in DISPATCH_LIFECYCLE_MAPPING.items():
        assert phase_id in DISPATCH_STAGE_LABELS, f"{step_name} target {phase_id} has no label"


def test_dispatch_mapping_has_unique_keys() -> None:
    """The step mapping contains no duplicate step keys."""
    keys = list(DISPATCH_LIFECYCLE_MAPPING)
    assert len(keys) == len(set(keys))


def test_dispatch_mapping_has_one_test_execution_phase() -> None:
    """P9 is used by exactly one dispatch step."""
    assert list(DISPATCH_LIFECYCLE_MAPPING.values()).count("P9") == 1


def test_p0_gate_accepts_all_required_participants() -> None:
    """The P0 phase definition is usable by the basic gate."""
    phase_def = get_phase_definition("P0")
    assert phase_def is not None
    required = [PHASE_TEMPLATES["P0"]["role_id"], *PHASE_TEMPLATES["P0"]["reviewers"]]
    result = check_gate_basic("P0", phase_def, {}, [], artifacts={"participating_roles": required})
    assert result.passed is True


def test_role_participation_fails_when_reviewer_missing() -> None:
    """A missing required reviewer fails the participation gate."""
    phase = PHASE_TEMPLATES["P1"]
    required = [phase["role_id"], *phase["reviewers"]]
    result = check_role_participation(phase, required[1:])
    assert result.passed is False
    assert result.missing_evidence
    assert required[0] in result.gap_report


def test_role_participation_passes_with_all_required_roles() -> None:
    """All required roles participating passes the gate."""
    phase = PHASE_TEMPLATES["P1"]
    required = [phase["role_id"], *phase["reviewers"]]
    result = check_role_participation(phase, required)
    assert result.passed is True


@pytest.mark.parametrize("filename", ["SKILL.md", "SKILL-CN.md"])
def test_skill_docs_phase_table_matches_canonical(filename: str) -> None:
    """Skill docs must not restate a divergent lifecycle table."""
    rows = _parse_phase_table(filename)
    assert set(rows) == set(CANONICAL_PHASES), f"{filename} does not list exactly P0-P11"
    for phase_id, cells in rows.items():
        phase = PHASE_TEMPLATES[phase_id]
        if filename == "SKILL.md":
            assert cells[1] == phase["name"], f"{filename} {phase_id} name mismatch"
        assert cells[2] == phase["role_id"], f"{filename} {phase_id} lead mismatch"
        reviewers = [role.strip() for role in cells[3].split(",")]
        assert reviewers == phase["reviewers"], f"{filename} {phase_id} reviewers mismatch"
        _assert_optional_flag(filename, phase_id, cells[4], phase["optional"])


@pytest.mark.parametrize(
    "filename",
    ["docs/reference/SUB_SKILLS.md", "GUIDE.md"],
)
def test_short_role_doc_phase_table_matches_canonical(filename: str) -> None:
    """Reference docs that use CLI short role IDs must agree with the canonical definition."""
    rows = _parse_phase_table(filename)
    assert set(rows) == set(CANONICAL_PHASES), f"{filename} does not list exactly P0-P11"
    for phase_id, cells in rows.items():
        phase = PHASE_TEMPLATES[phase_id]
        assert SHORT_ROLE_IDS[cells[2]] == phase["role_id"], f"{filename} {phase_id} lead mismatch"
        reviewers = [SHORT_ROLE_IDS[role.strip()] for role in cells[3].split("+")]
        assert reviewers == phase["reviewers"], f"{filename} {phase_id} reviewers mismatch"
        _assert_optional_flag(filename, phase_id, cells[4], phase["optional"])



@pytest.mark.parametrize("adapter_cls", [ShortcutLifecycleAdapter, FullLifecycleAdapter])
def test_adapter_records_and_enforces_participants(adapter_cls) -> None:
    """A recorded participant list drives the gate without caller artifacts."""
    adapter = adapter_cls(use_unified_gate=False)
    adapter.record_participation("P1", ["product-manager", "product-manager"])
    assert adapter.get_participating_roles("P1") == ["product-manager"]

    result = adapter.check_gate("P1")
    assert result.passed is False
    assert result.verdict == "REJECT"
    assert "architect" in result.gap_report

    required = [PHASE_TEMPLATES["P1"]["role_id"], *PHASE_TEMPLATES["P1"]["reviewers"]]
    adapter.record_participation("P1", required)
    assert adapter.check_gate("P1").passed is True


def test_advance_to_phase_rejects_incomplete_participation() -> None:
    """Recording incomplete roles blocks the phase transition."""
    adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
    result = adapter.advance_to_phase("P1", ["product-manager"])
    assert result.success is False
    assert result.new_state == PhaseState.BLOCKED
    assert adapter.get_participating_roles("P1") == ["product-manager"]


def test_passing_role_gate_does_not_skip_dependency_check() -> None:
    """Dependencies stay enforced after the role gate passes."""
    required = [
        PHASE_TEMPLATES["P2"]["role_id"],
        *PHASE_TEMPLATES["P2"]["reviewers"],
    ]
    phase_def = get_phase_definition("P2")
    result = check_gate_basic("P2", phase_def, {}, [], artifacts={"participating_roles": required})
    assert result.passed is False
    assert result.verdict == "CONDITIONAL"
    assert result.missing_evidence


