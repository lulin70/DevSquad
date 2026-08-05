"""V4.5.1: Connector Framework — External system integration for dispatch.

Design (V451-2):
    Defines the ``Connector`` Protocol (similar to ``SkillProvider``) so
    that workers can interact with external systems (GitHub, Jira, Slack)
    through a uniform interface. V4.5.1 ships ``GitHubConnector`` only;
    Jira/Slack are deferred to future iterations.

    The connector operates in three modes:
      1. **Live mode**: ``GITHUB_TOKEN`` env var is set → real GitHub API
         calls via ``urllib.request``.
      2. **CLI mode**: ``gh`` CLI is available → subprocess calls.
      3. **Simulation mode** (default): neither available → operations are
         recorded but not executed. This is the safe default for tests and
         mock dispatch.

Anti-ghost:
    Module-level ``_call_counter`` is incremented on every public method
    invocation. ``check_module_activation.py`` asserts ``_call_counter > 0``
    in CI to prove the connector is wired into the dispatch pipeline.

Roadmap: V4.5.1 V451-2 (Connector Framework, GitHub first).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Anti-ghost counter
# ---------------------------------------------------------------------------
_call_counter: int = 0


def get_call_count() -> int:
    """Return the module-level call counter (anti-ghost introspection)."""
    return _call_counter


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ConnectorOperation:
    """Record of a single connector operation (for audit/report).

    Attributes
    ----------
    connector_name:
        Name of the connector (e.g. ``"github"``).
    operation:
        What was done (e.g. ``"create_pr_comment"``).
    target:
        Target identifier (e.g. ``"owner/repo#123"``).
    success:
        Whether the operation succeeded.
    details:
        Arbitrary metadata (response body, error message).
    timestamp:
        Unix timestamp.
    """

    connector_name: str
    operation: str
    target: str
    success: bool
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for report embedding."""
        return {
            "connector_name": self.connector_name,
            "operation": self.operation,
            "target": self.target,
            "success": self.success,
            "details": self.details,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Connector Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Connector(Protocol):
    """Protocol for external-system connectors.

    Implementations must provide these methods. V4.5.1 ships
    ``GitHubConnector``; future iterations add Jira/Slack.
    """

    def create_pr_comment(
        self, repo: str, pr_number: int, body: str
    ) -> ConnectorOperation:
        """Post a comment on a pull request."""
        ...

    def update_issue_state(
        self, repo: str, issue_number: int, state: str
    ) -> ConnectorOperation:
        """Open or close an issue (state = "open" or "closed")."""
        ...

    def submit_pr_review(
        self, repo: str, pr_number: int, event: str, body: str
    ) -> ConnectorOperation:
        """Submit a PR review (event = "APPROVE", "REQUEST_CHANGES", "COMMENT")."""
        ...

    def get_operations(self) -> list[dict[str, Any]]:
        """Return all recorded operations for this dispatch."""
        ...

    def export_markdown(self) -> str:
        """Render operations as a Markdown section."""
        ...


# ---------------------------------------------------------------------------
# GitHubConnector
# ---------------------------------------------------------------------------


class GitHubConnector:
    """GitHub connector — PR comments, issue state, PR reviews.

    Mode selection (checked in order):
      1. ``GITHUB_TOKEN`` env var → GitHub REST API via urllib.
      2. ``gh`` CLI on PATH → subprocess calls.
      3. Neither → simulation mode (record but don't execute).
    """

    CONNECTOR_NAME = "github"

    def __init__(self, token: str | None = None, simulation: bool = False) -> None:
        """Initialize the GitHub connector.

        Args:
            token: Optional GitHub API token. When ``None``, falls back to
                the ``GITHUB_TOKEN`` env var.
            simulation: When ``True``, force simulation mode regardless of
                token / ``gh`` CLI availability. This MUST be used by the
                dispatcher probe (``_activate_connector``) to guarantee the
                probe never makes real GitHub API calls during dispatch.
        """
        self._force_simulation: bool = simulation
        self._token: str | None = token or os.environ.get("GITHUB_TOKEN")
        self._gh_cli: str | None = (
            shutil.which("gh") if (not self._token and not simulation) else None
        )
        self._operations: list[ConnectorOperation] = []

    @property
    def mode(self) -> str:
        """Current operating mode (for introspection/testing)."""
        if self._force_simulation:
            return "simulation"
        if self._token:
            return "api"
        if self._gh_cli:
            return "cli"
        return "simulation"

    def _record(
        self, operation: str, target: str, success: bool, details: dict[str, Any]
    ) -> ConnectorOperation:
        """Record an operation and return it."""
        op = ConnectorOperation(
            connector_name=self.CONNECTOR_NAME,
            operation=operation,
            target=target,
            success=success,
            details=details,
        )
        self._operations.append(op)
        return op

    def _api_call(self, method: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make a GitHub API call via urllib (live mode)."""
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}

    # ------------------------------------------------------------------
    # Public API (each increments _call_counter — anti-ghost)
    # ------------------------------------------------------------------

    def create_pr_comment(
        self, repo: str, pr_number: int, body: str
    ) -> ConnectorOperation:
        """Post a comment on a pull request."""
        global _call_counter
        _call_counter += 1

        target = f"{repo}#{pr_number}"
        if self.mode == "simulation":
            return self._record(
                "create_pr_comment", target, True,
                {"simulation": True, "body": body[:200]},
            )
        try:
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            if self.mode == "api":
                self._api_call("POST", url, {"body": body})
            else:
                assert self._gh_cli is not None  # mode=="cli" implies gh on PATH
                subprocess.run(
                    [self._gh_cli, "pr", "comment", str(pr_number),
                     "--repo", repo, "--body", body],
                    check=True, capture_output=True, text=True, timeout=30,
                )
            return self._record("create_pr_comment", target, True, {"body": body[:200]})
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as exc:
            return self._record(
                "create_pr_comment", target, False, {"error": str(exc)},
            )

    def update_issue_state(
        self, repo: str, issue_number: int, state: str
    ) -> ConnectorOperation:
        """Open or close an issue."""
        global _call_counter
        _call_counter += 1

        target = f"{repo}#{issue_number}"
        state = state.lower()
        if state not in ("open", "closed"):
            return self._record(
                "update_issue_state", target, False,
                {"error": f"Invalid state: {state}"},
            )
        if self.mode == "simulation":
            return self._record(
                "update_issue_state", target, True,
                {"simulation": True, "state": state},
            )
        try:
            url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
            if self.mode == "api":
                self._api_call("PATCH", url, {"state": state})
            else:
                assert self._gh_cli is not None  # mode=="cli" implies gh on PATH
                subprocess.run(
                    [self._gh_cli, "issue", "close" if state == "closed" else "reopen",
                     str(issue_number), "--repo", repo],
                    check=True, capture_output=True, text=True, timeout=30,
                )
            return self._record(
                "update_issue_state", target, True, {"state": state},
            )
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as exc:
            return self._record(
                "update_issue_state", target, False, {"error": str(exc)},
            )

    def submit_pr_review(
        self, repo: str, pr_number: int, event: str, body: str
    ) -> ConnectorOperation:
        """Submit a PR review (APPROVE / REQUEST_CHANGES / COMMENT)."""
        global _call_counter
        _call_counter += 1

        target = f"{repo}#{pr_number}"
        if event not in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
            return self._record(
                "submit_pr_review", target, False,
                {"error": f"Invalid event: {event}"},
            )
        if self.mode == "simulation":
            return self._record(
                "submit_pr_review", target, True,
                {"simulation": True, "event": event, "body": body[:200]},
            )
        try:
            url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
            if self.mode == "api":
                self._api_call("POST", url, {"event": event, "body": body})
            else:
                flag = {"APPROVE": "--approve", "REQUEST_CHANGES": "--request-changes",
                        "COMMENT": "--comment"}[event]
                assert self._gh_cli is not None  # mode=="cli" implies gh on PATH
                subprocess.run(
                    [self._gh_cli, "pr", "review", str(pr_number), flag,
                     "--repo", repo, "--body", body],
                    check=True, capture_output=True, text=True, timeout=30,
                )
            return self._record(
                "submit_pr_review", target, True,
                {"event": event, "body": body[:200]},
            )
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as exc:
            return self._record(
                "submit_pr_review", target, False, {"error": str(exc)},
            )

    def get_operations(self) -> list[dict[str, Any]]:
        """Return all recorded operations."""
        global _call_counter
        _call_counter += 1
        return [op.to_dict() for op in self._operations]

    def export_markdown(self) -> str:
        """Render operations as a Markdown section."""
        global _call_counter
        _call_counter += 1

        if not self._operations:
            return ""

        lines = ["## Connector Operations", ""]
        lines.append(f"**Connector**: {self.CONNECTOR_NAME} (mode: {self.mode})")
        lines.append("")
        for i, op in enumerate(self._operations, 1):
            status = "OK" if op.success else "FAILED"
            lines.append(
                f"{i}. **{status}** — {op.operation} → {op.target}"
            )
            if op.details.get("error"):
                lines.append(f"   - Error: {op.details['error']}")
        lines.append("")
        return "\n".join(lines)
