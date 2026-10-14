"""E2E test for approval-gated patch preview and verification."""

from scripts.collaboration.models_lifecycle import LifecycleFinding
from scripts.collaboration.remediation import (
    apply_approved_patch,
    approve_proposal,
    create_patch_preview,
    proposal_from_finding,
)


def test_patch_is_rolled_back_when_rescan_fails(tmp_path):
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")
    proposal = proposal_from_finding(
        LifecycleFinding(
            category="BREAK-1",
            rule_id="doc.missing",
            lifecycle_phase="P1",
            artifact=str(target),
            status="detected",
            description="missing content",
        )
    )
    preview = create_patch_preview(proposal, original_content="old\n", proposed_content="new\n", target=str(target))
    approval = approve_proposal(proposal, approved=True, approved_by="e2e")
    result = apply_approved_patch(preview, approval, run_tests=lambda: True, rescan=lambda: False)
    assert result["status"] == "rolled_back"
    assert target.read_text(encoding="utf-8") == "old\n"
