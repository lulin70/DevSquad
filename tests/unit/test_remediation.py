"""Unit tests for deterministic remediation proposals."""

import json

from scripts.collaboration.models_lifecycle import LifecycleFinding
from scripts.collaboration.remediation import (
    RemediationProposal,
    apply_approved_patch,
    approve_proposal,
    create_patch_preview,
    proposal_from_finding,
    proposals_from_findings,
    render_proposals_json,
    render_proposals_markdown,
    resolve_finding_after_verification,
)


def _finding(suggestion: str = "Add the missing section.") -> LifecycleFinding:
    return LifecycleFinding(
        category="BREAK-1",
        rule_id="document.p1.missing.objectives",
        severity="warning",
        lifecycle_phase="P1",
        artifact="requirements.md",
        status="detected",
        description="P1 document is missing objectives.",
        suggestion=suggestion,
    )


def test_proposal_has_stable_id_and_requires_approval():
    first = proposal_from_finding(_finding())
    second = proposal_from_finding(_finding())
    assert first.proposal_id == second.proposal_id == first.finding_id
    assert first.approval_required is True
    assert "producer/gate" in first.verification[0]
    assert any("pytest" in item for item in first.verification)
    assert isinstance(first, RemediationProposal)


def test_proposals_deduplicate_and_preserve_order():
    first = _finding()
    second = LifecycleFinding(
        category="VULN-1",
        rule_id="document.p4.missing.schema",
        lifecycle_phase="P4",
        artifact="schema.yaml",
        status="detected",
        description="Schema is missing.",
    )
    proposals = proposals_from_findings([first, first, second])
    assert [item.lifecycle_phase for item in proposals] == ["P1", "P4"]


def test_approval_patch_preview_and_apply_require_explicit_approval(tmp_path):
    target = tmp_path / "requirements.md"
    target.write_text("# Old\n", encoding="utf-8")
    proposal = proposal_from_finding(_finding())
    preview = create_patch_preview(
        proposal,
        original_content="# Old\n",
        proposed_content="# New\n",
        target=str(target),
    )
    assert "+# New" in preview.diff
    try:
        apply_approved_patch(
            preview,
            approve_proposal(proposal, approved=False, approved_by="reviewer"),
            run_tests=lambda: True,
            rescan=lambda: True,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("unapproved patch must be rejected")
    approval = approve_proposal(proposal, approved=True, approved_by="reviewer")
    result = apply_approved_patch(preview, approval, run_tests=lambda: True, rescan=lambda: True)
    assert result["status"] == "applied"
    assert target.read_text(encoding="utf-8") == "# New\n"
    finding = _finding()
    assert resolve_finding_after_verification(finding, result).status == "resolved"


def test_renderers_are_serializable_and_disclose_no_auto_fix():
    proposal = proposal_from_finding(_finding())
    markdown = render_proposals_markdown([proposal])
    payload = json.loads(render_proposals_json([proposal]))
    assert "Approval required: `true`" in markdown
    assert payload[0]["approval_required"] is True
    assert "Add the missing section." in payload[0]["actions"]
    assert not hasattr(proposal, "apply")
