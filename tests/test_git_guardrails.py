#!/usr/bin/env python3
"""
Tests for P2-3 git-guardrails (Matt Pocock) — git command classification.

Covers ``OperationClassifier.classify_git_command`` which tags git commands as
FORBIDDEN / NEEDS_REVIEW / ALWAYS_SAFE per the git-guardrails philosophy.

Spec reference: V4.1.0_PRD_Matt_Skills_Fusion.md §3.3 (P2-3 git-guardrails)
"""

import pytest

from scripts.collaboration.operation_classifier import (
    PROTECTED_BRANCHES,
    OperationClassifier,
    create_default_classifier,
)


@pytest.fixture
def classifier() -> OperationClassifier:
    """Default classifier instance for git-guardrails tests."""
    return create_default_classifier()


# ===== Category constants (keep tests readable) =====
FORBIDDEN = "FORBIDDEN"
NEEDS_REVIEW = "NEEDS_REVIEW"
ALWAYS_SAFE = "ALWAYS_SAFE"


class TestProtectedBranchesConstant:
    """Sanity-check the protected-branches set used by the classifier."""

    def test_main_and_master_are_protected(self):
        assert "main" in PROTECTED_BRANCHES
        assert "master" in PROTECTED_BRANCHES

    def test_feature_branches_not_protected(self):
        assert "feature/api" not in PROTECTED_BRANCHES
        assert "develop" not in PROTECTED_BRANCHES


class TestForbiddenGitCommands:
    """Commands that must be classified as FORBIDDEN."""

    def test_force_push_to_main(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git push --force origin main") == FORBIDDEN

    def test_force_push_to_master(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git push --force origin master") == FORBIDDEN

    def test_force_push_short_flag_to_main(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git push -f origin main") == FORBIDDEN

    def test_force_with_lease_to_main(self, classifier: OperationClassifier):
        assert (
            classifier.classify_git_command("git push --force-with-lease origin main")
            == FORBIDDEN
        )

    def test_force_push_complex_args_to_master(self, classifier: OperationClassifier):
        # Complex argument combination from the task spec.
        assert classifier.classify_git_command("git push --force origin master") == FORBIDDEN

    def test_force_push_head_refspec_to_main(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git push --force origin HEAD:main") == FORBIDDEN

    def test_force_push_delete_main(self, classifier: OperationClassifier):
        # ``:main`` refspec deletes remote main — must be FORBIDDEN.
        assert classifier.classify_git_command("git push --force origin :main") == FORBIDDEN

    def test_force_push_refs_heads_main(self, classifier: OperationClassifier):
        assert (
            classifier.classify_git_command("git push --force origin refs/heads/main")
            == FORBIDDEN
        )

    def test_reset_hard(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git reset --hard") == FORBIDDEN
        assert classifier.classify_git_command("git reset --hard HEAD~1") == FORBIDDEN

    def test_clean_force(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git clean -f") == FORBIDDEN

    def test_clean_force_directory(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git clean -fd") == FORBIDDEN

    def test_clean_force_ignored(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git clean -fx") == FORBIDDEN

    def test_branch_force_delete(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git branch -D feature/x") == FORBIDDEN

    def test_rebase_interactive(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git rebase -i main") == FORBIDDEN

    def test_rebase_interactive_long_flag(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git rebase --interactive main") == FORBIDDEN


class TestNeedsReviewGitCommands:
    """Commands that must be classified as NEEDS_REVIEW."""

    def test_plain_push(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git push origin feature/x") == NEEDS_REVIEW

    def test_plain_push_to_main(self, classifier: OperationClassifier):
        # Non-force push to main is still a mutation — review required.
        assert classifier.classify_git_command("git push origin main") == NEEDS_REVIEW

    def test_force_push_to_feature_branch(self, classifier: OperationClassifier):
        assert (
            classifier.classify_git_command("git push --force origin feature/new-api")
            == NEEDS_REVIEW
        )

    def test_force_with_lease_to_feature(self, classifier: OperationClassifier):
        assert (
            classifier.classify_git_command(
                "git push --force-with-lease origin feature/y"
            )
            == NEEDS_REVIEW
        )

    def test_merge(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git merge feature/x") == NEEDS_REVIEW

    def test_rebase_non_interactive(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git rebase main") == NEEDS_REVIEW

    def test_cherry_pick(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git cherry-pick abc1234") == NEEDS_REVIEW

    def test_commit_amend(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git commit --amend") == NEEDS_REVIEW

    def test_commit_amend_with_message(self, classifier: OperationClassifier):
        assert (
            classifier.classify_git_command("git commit --amend -m 'new msg'") == NEEDS_REVIEW
        )

    def test_stash_drop(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git stash drop") == NEEDS_REVIEW

    def test_stash_pop(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git stash pop") == NEEDS_REVIEW

    def test_branch_safe_delete(self, classifier: OperationClassifier):
        # lowercase -d is a non-force delete — review required.
        assert classifier.classify_git_command("git branch -d feature/x") == NEEDS_REVIEW

    def test_branch_delete_long_flag(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git branch --delete feature/x") == NEEDS_REVIEW

    def test_reset_soft(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git reset --soft HEAD~1") == NEEDS_REVIEW

    def test_reset_mixed(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git reset --mixed HEAD~1") == NEEDS_REVIEW

    def test_pull_rebase(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git pull --rebase") == NEEDS_REVIEW

    def test_checkout_orphan(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git checkout --orphan newbranch") == NEEDS_REVIEW

    def test_clean_without_force(self, classifier: OperationClassifier):
        # clean without -f prompts — review required.
        assert classifier.classify_git_command("git clean -d") == NEEDS_REVIEW

    def test_force_push_alone_is_conservative_forbidden(self, classifier: OperationClassifier):
        # No target branch determinable — conservative FORBIDDEN.
        assert classifier.classify_git_command("git push --force") == FORBIDDEN


class TestAlwaysSafeGitCommands:
    """Commands that must be classified as ALWAYS_SAFE."""

    def test_status(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git status") == ALWAYS_SAFE

    def test_log(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git log") == ALWAYS_SAFE
        assert classifier.classify_git_command("git log --oneline -5") == ALWAYS_SAFE

    def test_diff(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git diff") == ALWAYS_SAFE
        assert classifier.classify_git_command("git diff HEAD~1") == ALWAYS_SAFE

    def test_show(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git show HEAD") == ALWAYS_SAFE

    def test_add(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git add file.py") == ALWAYS_SAFE
        assert classifier.classify_git_command("git add -A") == ALWAYS_SAFE

    def test_fetch(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git fetch origin") == ALWAYS_SAFE

    def test_pull_default(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git pull") == ALWAYS_SAFE
        assert classifier.classify_git_command("git pull origin main") == ALWAYS_SAFE

    def test_branch_list(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git branch") == ALWAYS_SAFE
        assert classifier.classify_git_command("git branch -a") == ALWAYS_SAFE

    def test_checkout_branch(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git checkout main") == ALWAYS_SAFE
        assert classifier.classify_git_command("git checkout feature/x") == ALWAYS_SAFE

    def test_stash_push(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git stash") == ALWAYS_SAFE
        assert classifier.classify_git_command("git stash push") == ALWAYS_SAFE

    def test_stash_list(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git stash list") == ALWAYS_SAFE


class TestEdgeCases:
    """Edge cases: empty, non-git, malformed input."""

    def test_empty_string(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("") == NEEDS_REVIEW

    def test_whitespace_only(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("   ") == NEEDS_REVIEW

    def test_non_git_command(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("npm install") == NEEDS_REVIEW
        assert classifier.classify_git_command("ls -la") == NEEDS_REVIEW

    def test_bare_git(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git") == NEEDS_REVIEW

    def test_unknown_git_subcommand(self, classifier: OperationClassifier):
        assert classifier.classify_git_command("git frobnicate") == NEEDS_REVIEW

    def test_malformed_quoting_falls_back(self, classifier: OperationClassifier):
        # Unbalanced quote — shlex raises, fallback split still classifies.
        assert (
            classifier.classify_git_command("git status 'unclosed quote")
            == ALWAYS_SAFE
        )

    def test_returns_are_uppercase_category_names(self, classifier: OperationClassifier):
        for cmd in (
            "git status",
            "git push origin feature/x",
            "git push --force origin main",
        ):
            result = classifier.classify_git_command(cmd)
            assert result in {FORBIDDEN, NEEDS_REVIEW, ALWAYS_SAFE}
            assert result.isupper()


class TestForceFlagDetection:
    """Targeted tests for force-flag parsing variations."""

    def test_force_equals_form(self, classifier: OperationClassifier):
        # ``--force=`` is still a force flag (used with refspec aliases).
        assert (
            classifier.classify_git_command("git push --force=if:has:remote origin main")
            == FORBIDDEN
        )

    def test_force_flag_after_positional(self, classifier: OperationClassifier):
        # Flags may appear after the remote/branch positionally.
        assert classifier.classify_git_command("git push origin main --force") == FORBIDDEN

    def test_force_with_lease_equals_refspec(self, classifier: OperationClassifier):
        # ``--force-with-lease=main:abc123`` to a feature branch → review.
        assert (
            classifier.classify_git_command(
                "git push --force-with-lease=main:abc123 origin feature/x"
            )
            == NEEDS_REVIEW
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
