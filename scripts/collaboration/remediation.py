"""Deterministic remediation proposals for lifecycle findings.

Proposals require approval. Patch application requires explicit approval, is verified, and rollback-safe; this module performs no auto-fix.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models_lifecycle import LifecycleFinding


def _finding_key(finding: LifecycleFinding) -> str:
    value = ":".join(
        (
            finding.lifecycle_phase,
            finding.category,
            finding.rule_id,
            finding.artifact,
            finding.line_range,
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


@dataclass
class RemediationProposal:
    """Approval-gated remediation advice. Instances describe changes but never apply them."""

    proposal_id: str
    finding_id: str
    category: str
    lifecycle_phase: str
    title: str
    rationale: str
    target: str
    actions: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    approval_required: bool = True
    status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible proposal."""
        return {
            "proposal_id": self.proposal_id,
            "finding_id": self.finding_id,
            "category": self.category,
            "lifecycle_phase": self.lifecycle_phase,
            "title": self.title,
            "rationale": self.rationale,
            "target": self.target,
            "actions": list(self.actions),
            "verification": list(self.verification),
            "approval_required": self.approval_required,
            "status": self.status,
        }


def proposal_from_finding(finding: LifecycleFinding) -> RemediationProposal:
    """Create a stable, approval-gated proposal from one finding."""
    finding_id = _finding_key(finding)
    target = finding.artifact or finding.file_path
    action = finding.suggestion or f"Review and correct the finding in {target or 'the reported artifact'}."
    phase = finding.lifecycle_phase
    verification = [
        f"Run the {phase} lifecycle producer/gate for the explicit artifact and confirm the finding is resolved.",
        f"Run pytest for the {phase} lifecycle coverage (for example: pytest -q tests/unit tests/integration).",
        "Perform manual review of the proposed change before applying it.",
    ]
    return RemediationProposal(
        proposal_id=finding_id,
        finding_id=finding_id,
        category=finding.category,
        lifecycle_phase=phase,
        title=f"Remediate {finding.category} in {phase}",
        rationale=finding.description,
        target=target,
        actions=[action],
        verification=verification,
    )


def proposals_from_findings(findings: Iterable[LifecycleFinding]) -> list[RemediationProposal]:
    """Build proposals in input order and remove duplicate stable finding IDs."""
    proposals: list[RemediationProposal] = []
    seen: set[str] = set()
    for finding in findings:
        proposal = proposal_from_finding(finding)
        if proposal.proposal_id in seen:
            continue
        seen.add(proposal.proposal_id)
        proposals.append(proposal)
    return proposals


def render_proposals_markdown(proposals: Iterable[RemediationProposal]) -> str:
    """Render proposals as deterministic Markdown text."""
    items = list(proposals)
    lines = ["# Remediation Proposals", ""]
    if not items:
        lines.append("No remediation proposals.")
        return "\n".join(lines) + "\n"
    for proposal in items:
        lines.extend(
            [
                f"## {proposal.title}",
                "",
                f"- Proposal ID: `{proposal.proposal_id}`",
                f"- Finding ID: `{proposal.finding_id}`",
                f"- Category: `{proposal.category}`",
                f"- Lifecycle phase: `{proposal.lifecycle_phase}`",
                f"- Target: `{proposal.target}`",
                f"- Approval required: `{str(proposal.approval_required).lower()}`",
                f"- Status: `{proposal.status}`",
                "",
                f"**Rationale**: {proposal.rationale}",
                "",
                "### Actions",
            ]
        )
        lines.extend(f"- {action}" for action in proposal.actions)
        lines.extend(["", "### Verification"])
        lines.extend(f"- {step}" for step in proposal.verification)
        lines.append("")
    return "\n".join(lines)


def render_proposals_json(proposals: Iterable[RemediationProposal]) -> str:
    """Render proposals as deterministic, pretty JSON text."""
    return (
        json.dumps([proposal.to_dict() for proposal in proposals], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


@dataclass(frozen=True)
class ApprovalRecord:
    """Explicit human approval for one proposal."""

    proposal_id: str
    approved: bool
    approved_by: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "approved": self.approved,
            "approved_by": self.approved_by,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PatchPreview:
    """A preview of a caller-supplied patch. It does not write files."""

    proposal_id: str
    target: str
    original_content: str
    proposed_content: str
    diff: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "target": self.target,
            "diff": self.diff,
        }


def approve_proposal(
    proposal: RemediationProposal,
    *,
    approved: bool,
    approved_by: str,
    reason: str = "",
) -> ApprovalRecord:
    """Create an explicit approval record. Approval is never implicit."""
    if not approved_by.strip():
        raise ValueError("approved_by is required")
    if proposal.status not in {"proposed", "approved", "denied"}:
        raise ValueError(f"Proposal is not approval-ready: {proposal.status}")
    return ApprovalRecord(proposal.proposal_id, approved, approved_by.strip(), reason)


def create_patch_preview(
    proposal: RemediationProposal,
    *,
    original_content: str,
    proposed_content: str,
    target: str | None = None,
) -> PatchPreview:
    """Create a deterministic unified diff without modifying the target."""
    target_path = target or proposal.target
    diff = "".join(
        difflib.unified_diff(
            original_content.splitlines(keepends=True),
            proposed_content.splitlines(keepends=True),
            fromfile=target_path,
            tofile=target_path,
        )
    )
    return PatchPreview(proposal.proposal_id, target_path, original_content, proposed_content, diff)


def resolve_finding_after_verification(
    finding: LifecycleFinding,
    application_result: dict[str, Any],
) -> LifecycleFinding:
    """Mark a finding resolved only after tests and a rescan both pass."""
    if application_result.get("status") != "applied":
        raise ValueError("Finding can be resolved only after an applied patch")
    if not application_result.get("tests_passed") or not application_result.get("rescanned"):
        raise ValueError("Finding can be resolved only after verification")
    finding.status = "resolved"
    return finding


def apply_approved_patch(
    preview: PatchPreview,
    approval: ApprovalRecord,
    *,
    run_tests: Callable[[], bool],
    rescan: Callable[[], bool],
) -> dict[str, Any]:
    """Apply one approved patch, verify it, and restore on verification failure."""
    if approval.proposal_id != preview.proposal_id or not approval.approved:
        raise PermissionError("An explicit approval for this proposal is required")
    target = Path(preview.target).expanduser()
    if target.is_symlink() or not target.is_file():
        raise ValueError("Patch target must be a regular non-symlink file")
    current = target.read_text(encoding="utf-8")
    if current != preview.original_content:
        raise ValueError("Patch target changed since preview")
    mode = stat.S_IMODE(target.stat().st_mode)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
            handle.write(preview.proposed_content)
            temporary_path = handle.name
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, target)
        tests_passed = bool(run_tests())
        rescanned = bool(rescan()) if tests_passed else False
        if not tests_passed or not rescanned:
            target.write_text(preview.original_content, encoding="utf-8")
            os.chmod(target, mode)
            return {"status": "rolled_back", "tests_passed": tests_passed, "rescanned": rescanned}
        return {"status": "applied", "tests_passed": True, "rescanned": True}
    finally:
        if temporary_path:
            with suppress(FileNotFoundError):
                os.unlink(temporary_path)


__all__ = [
    "ApprovalRecord",
    "PatchPreview",
    "RemediationProposal",
    "apply_approved_patch",
    "approve_proposal",
    "create_patch_preview",
    "proposal_from_finding",
    "resolve_finding_after_verification",
    "proposals_from_findings",
    "render_proposals_markdown",
    "render_proposals_json",
]
