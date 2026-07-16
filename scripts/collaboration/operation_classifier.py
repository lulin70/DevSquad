#!/usr/bin/env python3
"""
OperationCategory Extension for PermissionGuard (P1-2)

Adds three-tier operation classification to existing 4-level permission model:
  - ALWAYS_SAFE: Read-only, local queries (auto-approved at most levels)
  - NEEDS_REVIEW: Write ops, external API calls (requires confirmation or AI check)
  - FORBIDDEN: Dangerous ops (delete, secrets, eval) (denied unless BYPASS)

P2-3 (V4.1.0): git-guardrails — ``OperationClassifier.classify_git_command``
applies Matt Pocock's git-guardrails philosophy to classify git command strings
(force-push to protected branches, reset --hard, clean -f, branch -D and
rebase -i are FORBIDDEN; push/merge/rebase/cherry-pick/commit --amend/
stash drop are NEEDS_REVIEW; status/log/diff/show/add/fetch/pull/branch/
checkout/stash are ALWAYS_SAFE).

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.2
"""

import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Any


class OperationCategory(Enum):
    """
    Three-tier operation classification for fine-grained permission control.

    Hierarchy:
      ALWAYS_SAFE → Auto-approved at DEFAULT/AUTO levels
      NEEDS_REVIEW → Requires explicit approval or AI risk assessment
      FORBIDDEN     → Blocked unless BYPASS level + explicit override
    """

    ALWAYS_SAFE = "always_safe"
    NEEDS_REVIEW = "needs_review"
    FORBIDDEN = "forbidden"


# Branches protected from force-push and deletion (Matt Pocock git-guardrails).
PROTECTED_BRANCHES: frozenset[str] = frozenset({"main", "master"})


# Default classification mapping for common operations
OPERATION_CLASSIFICATION: dict[str, OperationCategory] = {
    # === Always Safe Operations ===
    "read_config": OperationCategory.ALWAYS_SAFE,
    "read_file": OperationCategory.ALWAYS_SAFE,
    "read_scratchpad": OperationCategory.ALWAYS_SAFE,
    "list_directory": OperationCategory.ALWAYS_SAFE,
    "query_status": OperationCategory.ALWAYS_SAFE,
    "get_role_info": OperationCategory.ALWAYS_SAFE,
    "validate_input": OperationCategory.ALWAYS_SAFE,
    # === Needs Review Operations ===
    "write_scratchpad": OperationCategory.NEEDS_REVIEW,
    "write_file": OperationCategory.NEEDS_REVIEW,
    "create_file": OperationCategory.NEEDS_REVIEW,
    "modify_file": OperationCategory.NEEDS_REVIEW,
    "call_llm": OperationCategory.NEEDS_REVIEW,
    "network_request": OperationCategory.NEEDS_REVIEW,
    "git_operation": OperationCategory.NEEDS_REVIEW,
    "modify_config": OperationCategory.NEEDS_REVIEW,
    "install_template": OperationCategory.NEEDS_REVIEW,
    "publish_template": OperationCategory.NEEDS_REVIEW,
    # === Forbidden Operations ===
    "delete_file": OperationCategory.FORBIDDEN,
    "execute_shell": OperationCategory.FORBIDDEN,
    "access_secrets": OperationCategory.FORBIDDEN,
    "eval_code": OperationCategory.FORBIDDEN,
    "import_module": OperationCategory.FORBIDDEN,
    "spawn_process": OperationCategory.FORBIDDEN,
    "modify_system_path": OperationCategory.FORBIDDEN,
    "environment_write": OperationCategory.FORBIDDEN,
}


@dataclass
class ClassifiedOperation:
    """An operation with its category classification."""

    operation_id: str
    category: OperationCategory
    description: str
    risk_factors: list[str]
    requires_confirmation: bool
    override_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize the classified operation to a dictionary.

        Returns:
            Dictionary containing operation id, category, description, risk factors,
            confirmation requirement, and override allowance.
        """
        return {
            "operation_id": self.operation_id,
            "category": self.category.value,
            "description": self.description,
            "risk_factors": self.risk_factors,
            "requires_confirmation": self.requires_confirmation,
            "override_allowed": self.override_allowed,
        }


class OperationClassifier:
    """
    Classifies operations into three-tier categories.

    Usage:
        classifier = OperationClassifier()
        classified = classifier.classify("delete_file", "/tmp/important.txt")
        if classified.category == OperationCategory.FORBIDDEN:
            # Block or escalate
            pass
    """

    def __init__(
        self,
        custom_classifications: dict[str, OperationCategory] | None = None,
        strict_mode: bool = False,
    ):
        """
        Initialize classifier.

        Args:
            custom_classifications: Override default classifications
            strict_mode: If True, unknown operations are classified as FORBIDDEN
                           If False (default), unknown operations are NEEDS_REVIEW
        """
        self._classifications = dict(OPERATION_CLASSIFICATION)
        if custom_classifications:
            self._classifications.update(custom_classifications)
        self._strict_mode = strict_mode

    def classify(
        self,
        operation_id: str,
        target: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ClassifiedOperation:
        """
        Classify an operation into a category.

        Args:
            operation_id: The operation identifier
            target: Optional target path/URL for context
            context: Additional context (source role, etc.)

        Returns:
            ClassifiedOperation with full details
        """
        base_category = self._classifications.get(operation_id)

        if base_category is None:
            base_category = OperationCategory.FORBIDDEN if self._strict_mode else OperationCategory.NEEDS_REVIEW

        description = self._get_description(operation_id)
        risk_factors = self._assess_risk_factors(operation_id, target, context)

        return ClassifiedOperation(
            operation_id=operation_id,
            category=base_category,
            description=description,
            risk_factors=risk_factors,
            requires_confirmation=(
                base_category == OperationCategory.NEEDS_REVIEW or base_category == OperationCategory.FORBIDDEN
            ),
            override_allowed=base_category != OperationCategory.FORBIDDEN,
        )

    def batch_classify(
        self,
        operations: list[dict[str, Any]],
    ) -> list[ClassifiedOperation]:
        """
        Classify multiple operations at once.

        Args:
            operations: List of dicts with 'operation_id' and optional 'target', 'context'

        Returns:
            List of ClassifiedOperation results
        """
        return [
            self.classify(
                op.get("operation_id", ""),
                op.get("target"),
                op.get("context"),
            )
            for op in operations
        ]

    def is_allowed(
        self,
        operation_id: str,
        permission_level: str = "DEFAULT",
        target: str | None = None,
    ) -> tuple:
        """
        Quick check if operation is allowed at given permission level.

        Returns:
            (allowed: bool, reason: str)
        """
        classified = self.classify(operation_id, target)

        if classified.category == OperationCategory.ALWAYS_SAFE:
            return True, "Operation is always safe"

        if classified.category == OperationCategory.FORBIDDEN:
            if permission_level.upper() == "BYPASS":
                return True, "Allowed via BYPASS override"
            return False, f"Operation '{operation_id}' is forbidden"

        if classified.category == OperationCategory.NEEDS_REVIEW:
            if permission_level.upper() in ("AUTO", "BYPASS"):
                return True, f"Auto-approved at {permission_level} level"
            if permission_level.upper() == "PLAN":
                return False, "Write operations denied in PLAN mode"
            return True, "Requires user confirmation"

        return False, "Unknown category"

    def get_forbidden_operations(self) -> list[str]:
        """Return list of all operations classified as FORBIDDEN."""
        return [op_id for op_id, cat in self._classifications.items() if cat == OperationCategory.FORBIDDEN]

    def get_review_required_operations(self) -> list[str]:
        """Return list of all operations classified as NEEDS_REVIEW."""
        return [op_id for op_id, cat in self._classifications.items() if cat == OperationCategory.NEEDS_REVIEW]

    def add_custom_classification(
        self,
        operation_id: str,
        category: OperationCategory,
    ) -> None:
        """Add or update custom operation classification."""
        self._classifications[operation_id] = category

    # ===== P2-3: git-guardrails (Matt Pocock) =====

    def classify_git_command(self, command: str) -> str:
        """Classify a git command string into a three-tier category.

        Implements Matt Pocock's git-guardrails philosophy by tagging
        dangerous git operations so they can be blocked or escalated before
        execution.

        Classification summary:
          - FORBIDDEN: force-push to protected branches (main/master),
            ``reset --hard``, ``clean -f``, ``branch -D``, ``rebase -i``.
          - NEEDS_REVIEW: ``push`` (non-force or to non-protected branches),
            ``merge``, ``rebase`` (non-interactive), ``cherry-pick``,
            ``commit --amend``, ``stash drop``.
          - ALWAYS_SAFE: ``status``, ``log``, ``diff``, ``show``, ``add``,
            ``fetch``, ``pull`` (non-rebase), ``branch`` (listing),
            ``checkout`` (non-orphan), ``stash`` (push/list/show/apply).

        Args:
            command: A git command string, e.g.
                ``"git push --force origin main"``.

        Returns:
            One of ``"FORBIDDEN"``, ``"NEEDS_REVIEW"``, ``"ALWAYS_SAFE"``.
            Empty or non-git commands return ``"NEEDS_REVIEW"`` as a safe
            default (consistent with the non-strict classifier behavior).
        """
        if not command or not command.strip():
            return OperationCategory.NEEDS_REVIEW.name

        try:
            tokens = shlex.split(command)
        except ValueError:
            # Malformed quoting — fall back to a naive whitespace split so
            # we still make a best-effort classification.
            tokens = command.split()

        if not tokens or tokens[0] != "git":
            return OperationCategory.NEEDS_REVIEW.name

        args = tokens[1:]
        if not args:
            # Bare ``git`` with no subcommand — cannot classify.
            return OperationCategory.NEEDS_REVIEW.name

        subcommand = args[0]
        rest = args[1:]

        # --- Always-safe read-only / staging subcommands ---
        if subcommand in {"status", "log", "diff", "show", "add", "fetch"}:
            return OperationCategory.ALWAYS_SAFE.name
        if subcommand == "branch":
            return self._classify_git_branch(rest)
        if subcommand == "checkout":
            return self._classify_git_checkout(rest)
        if subcommand == "stash":
            return self._classify_git_stash(rest)
        if subcommand == "pull":
            return self._classify_git_pull(rest)

        # --- Mutation subcommands ---
        if subcommand == "push":
            return self._classify_git_push(rest)
        if subcommand == "merge":
            return OperationCategory.NEEDS_REVIEW.name
        if subcommand == "rebase":
            return self._classify_git_rebase(rest)
        if subcommand == "cherry-pick":
            return OperationCategory.NEEDS_REVIEW.name
        if subcommand == "commit":
            return self._classify_git_commit(rest)
        if subcommand == "reset":
            return self._classify_git_reset(rest)
        if subcommand == "clean":
            return self._classify_git_clean(rest)

        # Unknown subcommand — safe default.
        return OperationCategory.NEEDS_REVIEW.name

    @staticmethod
    def _has_force_flag(push_args: list[str]) -> bool:
        """Detect force-push flags in ``git push`` arguments."""
        for arg in push_args:
            if arg in ("--force", "-f", "--force-with-lease"):
                return True
            if arg.startswith("--force=") or arg.startswith("--force-with-lease="):
                return True
        return False

    @staticmethod
    def _extract_push_target_branch(push_args: list[str]) -> str | None:
        """Extract the remote target branch from ``git push`` arguments.

        Handles common refspec forms:
          - ``git push origin main``        → ``"main"``
          - ``git push origin HEAD:main``   → ``"main"`` (push to remote main)
          - ``git push origin :main``       → ``"main"`` (delete remote main)
          - ``git push`` (no positional)    → ``None`` (cannot determine)
        """
        candidates = [a for a in push_args if not a.startswith("-")]
        if len(candidates) < 2:
            return None
        refspec = candidates[1]
        if ":" in refspec:
            remote_part = refspec.split(":", 1)[1]
            return remote_part if remote_part else None
        return refspec

    def _classify_git_push(self, push_args: list[str]) -> str:
        """Classify ``git push`` based on force flags and target branch."""
        if self._has_force_flag(push_args):
            target = self._extract_push_target_branch(push_args)
            if target is None:
                # Unknown target branch — conservative: treat as FORBIDDEN
                # since we cannot rule out a protected branch.
                return OperationCategory.FORBIDDEN.name
            branch = target
            if branch.startswith("refs/heads/"):
                branch = branch[len("refs/heads/") :]
            if branch in PROTECTED_BRANCHES:
                return OperationCategory.FORBIDDEN.name
            return OperationCategory.NEEDS_REVIEW.name
        return OperationCategory.NEEDS_REVIEW.name

    @staticmethod
    def _classify_git_branch(branch_args: list[str]) -> str:
        """Classify ``git branch``: ``-D`` is FORBIDDEN, ``-d`` is review."""
        if "-D" in branch_args:
            return OperationCategory.FORBIDDEN.name
        if "-d" in branch_args or "--delete" in branch_args:
            return OperationCategory.NEEDS_REVIEW.name
        return OperationCategory.ALWAYS_SAFE.name

    @staticmethod
    def _classify_git_checkout(checkout_args: list[str]) -> str:
        """Classify ``git checkout``: ``--orphan`` needs review, else safe."""
        if "--orphan" in checkout_args:
            return OperationCategory.NEEDS_REVIEW.name
        return OperationCategory.ALWAYS_SAFE.name

    @staticmethod
    def _classify_git_stash(stash_args: list[str]) -> str:
        """Classify ``git stash``: ``drop``/``pop`` need review, else safe."""
        if not stash_args:
            return OperationCategory.ALWAYS_SAFE.name
        sub = stash_args[0]
        if sub in {"drop", "pop"}:
            return OperationCategory.NEEDS_REVIEW.name
        return OperationCategory.ALWAYS_SAFE.name

    @staticmethod
    def _classify_git_pull(pull_args: list[str]) -> str:
        """Classify ``git pull``: ``--rebase`` mode needs review, else safe."""
        if "--rebase" in pull_args or any(a.startswith("--rebase=") for a in pull_args):
            return OperationCategory.NEEDS_REVIEW.name
        return OperationCategory.ALWAYS_SAFE.name

    @staticmethod
    def _classify_git_rebase(rebase_args: list[str]) -> str:
        """Classify ``git rebase``: interactive (``-i``) is FORBIDDEN."""
        if "-i" in rebase_args or "--interactive" in rebase_args:
            return OperationCategory.FORBIDDEN.name
        return OperationCategory.NEEDS_REVIEW.name

    @staticmethod
    def _classify_git_commit(commit_args: list[str]) -> str:
        """Classify ``git commit``: ``--amend`` rewrites history (review)."""
        # Plain commits and amends both mutate history — require review.
        if "--amend" in commit_args:
            return OperationCategory.NEEDS_REVIEW.name
        return OperationCategory.NEEDS_REVIEW.name

    @staticmethod
    def _classify_git_reset(reset_args: list[str]) -> str:
        """Classify ``git reset``: ``--hard`` discards work (FORBIDDEN)."""
        if "--hard" in reset_args:
            return OperationCategory.FORBIDDEN.name
        return OperationCategory.NEEDS_REVIEW.name

    @staticmethod
    def _classify_git_clean(clean_args: list[str]) -> str:
        """Classify ``git clean``: ``-f`` (or combined ``-fd``) is FORBIDDEN."""
        for arg in clean_args:
            if arg == "-f" or arg.startswith("--force"):
                return OperationCategory.FORBIDDEN.name
            if arg.startswith("-") and not arg.startswith("--") and "f" in arg:
                return OperationCategory.FORBIDDEN.name
        return OperationCategory.NEEDS_REVIEW.name

    def _get_description(self, operation_id: str) -> str:
        descriptions = {
            "read_config": "Read configuration values",
            "write_file": "Write or modify file contents",
            "delete_file": "Delete file from filesystem",
            "execute_shell": "Execute shell command",
            "call_llm": "Call LLM API for inference",
            "access_secrets": "Access secret keys or credentials",
            "eval_code": "Evaluate arbitrary code string",
            "read_scratchpad": "Read shared scratchpad data",
            "write_scratchpad": "Write to shared scratchpad",
        }
        return descriptions.get(operation_id, f"Operation: {operation_id}")

    def _assess_risk_factors(
        self,
        operation_id: str,
        target: str | None,
        context: dict[str, Any] | None,
    ) -> list[str]:
        factors = []
        category = self._classifications.get(operation_id, OperationCategory.NEEDS_REVIEW)

        if category == OperationCategory.FORBIDDEN:
            factors.append("High-risk operation category")

        if target:
            dangerous_patterns = ["/etc/", "/var/", ".env", "secret", "credential"]
            for pattern in dangerous_patterns:
                if pattern.lower() in target.lower():
                    factors.append(f"Target contains sensitive pattern: {pattern}")

        if context:
            source_role = context.get("source_role_id", "")
            if source_role == "solo-coder" and category == OperationCategory.FORBIDDEN:
                factors.append("Coder attempting forbidden operation")

        return factors


def create_default_classifier() -> OperationClassifier:
    """Create classifier with default classifications."""
    return OperationClassifier()


def create_strict_classifier(
    custom_classifications: dict[str, OperationCategory] | None = None,
) -> OperationClassifier:
    """Create classifier in strict mode (unknown ops = FORBIDDEN)."""
    return OperationClassifier(
        custom_classifications=custom_classifications,
        strict_mode=True,
    )
