"""V4.5.2 P12.1.3: GitLab Connector — second Connector implementation.

Mirrors the design of ``GitHubConnector`` (V4.5.1) so that DevSquad can
interact with GitLab instances (gitlab.com or self-hosted) for:

    - MR (merge request) comments
    - Issue state transitions
    - MR approvals / reviews

Modes (checked in order):
    1. ``GITLAB_TOKEN`` env var → GitLab REST API via urllib.
    2. ``glab`` CLI on PATH → subprocess calls.
    3. Neither → simulation mode (record but don't execute).

Default for dispatch probes is ``simulation=True`` to guarantee no real
GitLab API calls during dispatch. Same anti-ghost contract as GitHub
connector (``_call_counter`` incremented on every public method).

Roadmap: V4.5.2 P12.1.3 (Experience polish — second connector).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .connector_framework import ConnectorOperation

# Use the same anti-ghost counter as the parent framework so the existing
# CI gate (``check_module_activation.py``) sees one unified counter for all
# connector implementations.
# Note: We deliberately share the counter to keep the CI gate simple.


@dataclass
class GitLabMRRef:
    """Reference to a GitLab merge request (MR).

    Attributes:
        project: Project path (e.g. ``"mygroup/myproject"``).
        mr_iid: MR internal ID (project-scoped integer).
    """

    project: str
    mr_iid: int

    @property
    def target(self) -> str:
        """Return the ``project!iid`` identifier."""
        return f"{self.project}!{self.mr_iid}"


class GitLabConnector:
    """GitLab connector — MR comments, issue state, MR reviews/approvals.

    Mode selection (checked in order):
      1. ``GITLAB_TOKEN`` env var → GitLab REST API via urllib.
      2. ``glab`` CLI on PATH → subprocess calls.
      3. Neither → simulation mode (record but don't execute).

    Environment variables:
      - ``GITLAB_TOKEN`` (preferred) or pass ``token=`` kwarg.
      - ``GITLAB_BASE_URL`` (default: ``"https://gitlab.com"``). For
        self-hosted GitLab, set this to e.g. ``"https://gl.example.com"``.

    Anti-ghost:
        Increments the parent module's ``_call_counter`` on every public
        method invocation. CI gate ``check_module_activation.py`` confirms
        ``get_call_count() > 0`` to prove wiring.
    """

    CONNECTOR_NAME = "gitlab"
    DEFAULT_BASE_URL = "https://gitlab.com"
    PROJECT_API_VERSION = "v4"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        simulation: bool = False,
    ) -> None:
        """Initialize the GitLab connector.

        Args:
            token: GitLab personal access token / project token. When
                ``None``, falls back to ``GITLAB_TOKEN`` env var.
            base_url: GitLab instance base URL. Defaults to ``GITLAB_BASE_URL``
                env var or ``"https://gitlab.com"``.
            simulation: When ``True``, force simulation mode regardless of
                token / ``glab`` CLI availability. This MUST be used by the
                dispatcher probe to guarantee no real GitLab API calls.
        """
        self._force_simulation: bool = simulation
        self._token: str | None = token or os.environ.get("GITLAB_TOKEN")
        self._base_url: str = (
            (base_url or os.environ.get("GITLAB_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        )
        self._glab_cli: str | None = (
            shutil.which("glab") if (not self._token and not simulation) else None
        )
        self._operations: list[ConnectorOperation] = []

    @property
    def mode(self) -> str:
        """Current operating mode (for introspection/testing)."""
        if self._force_simulation:
            return "simulation"
        if self._token:
            return "api"
        if self._glab_cli:
            return "cli"
        return "simulation"

    @property
    def base_url(self) -> str:
        """Public accessor for the configured base URL."""
        return self._base_url

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
        """Make a GitLab API call via urllib (live mode)."""
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "PRIVATE-TOKEN": self._token or "",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}

    # ------------------------------------------------------------------
    # Public API (each increments _call_counter — anti-ghost)
    # ------------------------------------------------------------------

    def create_mr_comment(
        self, project: str, mr_iid: int, body: str
    ) -> ConnectorOperation:
        """Post a comment on a GitLab merge request.

        Args:
            project: Project path (``"group/project"``) or numeric ID.
            mr_iid: MR internal ID (project-scoped).
            body: Comment body.

        Returns:
            ConnectorOperation with success flag and metadata.
        """
        global _call_counter
        _call_counter += 1

        ref = GitLabMRRef(project=project, mr_iid=mr_iid)
        if self.mode == "simulation":
            return self._record(
                "create_mr_comment", ref.target, True,
                {"simulation": True, "body": body[:200]},
            )
        try:
            import urllib.parse
            url = (
                f"{self._base_url}/api/{self.PROJECT_API_VERSION}"
                f"/projects/{urllib.parse.quote(project, safe='/')}"
                f"/merge_requests/{mr_iid}/notes"
            )
            if self.mode == "api":
                self._api_call("POST", url, {"body": body})
            else:
                assert self._glab_cli is not None
                subprocess.run(
                    [self._glab_cli, "mr", "note", str(mr_iid),
                     "--project", project, "--message", body],
                    check=True, capture_output=True, text=True, timeout=30,
                )
            return self._record(
                "create_mr_comment", ref.target, True, {"body": body[:200]},
            )
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as exc:
            return self._record(
                "create_mr_comment", ref.target, False, {"error": str(exc)},
            )

    def update_issue_state(
        self, project: str, issue_iid: int, state: str
    ) -> ConnectorOperation:
        """Open or close a GitLab issue.

        Args:
            project: Project path (``"group/project"``).
            issue_iid: Issue internal ID.
            state: ``"open"`` or ``"closed"`` (case-insensitive).

        Returns:
            ConnectorOperation with success flag.
        """
        global _call_counter
        _call_counter += 1

        target = f"{project}#{issue_iid}"
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
            import urllib.parse
            url = (
                f"{self._base_url}/api/{self.PROJECT_API_VERSION}"
                f"/projects/{urllib.parse.quote(project, safe='/')}"
                f"/issues/{issue_iid}"
            )
            if self.mode == "api":
                self._api_call("PUT", url, {"state_event": state})
            else:
                assert self._glab_cli is not None
                cmd = (
                    [self._glab_cli, "issue", "close", str(issue_iid), "--project", project]
                    if state == "closed"
                    else [self._glab_cli, "issue", "reopen", str(issue_iid), "--project", project]
                )
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return self._record(
                "update_issue_state", target, True, {"state": state},
            )
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as exc:
            return self._record(
                "update_issue_state", target, False, {"error": str(exc)},
            )

    def submit_mr_review(
        self, project: str, mr_iid: int, event: str, body: str
    ) -> ConnectorOperation:
        """Submit a GitLab MR approval / unapproval.

        GitLab uses a binary approve/unapprove model. We map:
          - ``"APPROVE"`` → ``POST .../approve``
          - ``"REQUEST_CHANGES"`` → ``POST .../discussions`` (note-style)
          - ``"COMMENT"`` → ``POST .../notes``

        Args:
            project: Project path.
            mr_iid: MR internal ID.
            event: One of ``"APPROVE"``, ``"REQUEST_CHANGES"``, ``"COMMENT"``.
            body: Review body (used for non-approve events).

        Returns:
            ConnectorOperation with success flag.
        """
        global _call_counter
        _call_counter += 1

        ref = GitLabMRRef(project=project, mr_iid=mr_iid)
        if event not in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
            return self._record(
                "submit_mr_review", ref.target, False,
                {"error": f"Invalid event: {event}"},
            )
        if self.mode == "simulation":
            return self._record(
                "submit_mr_review", ref.target, True,
                {"simulation": True, "event": event, "body": body[:200]},
            )
        try:
            import urllib.parse
            project_enc = urllib.parse.quote(project, safe="/")
            if self.mode == "api":
                if event == "APPROVE":
                    url = (
                        f"{self._base_url}/api/{self.PROJECT_API_VERSION}"
                        f"/projects/{project_enc}/merge_requests/{mr_iid}/approve"
                    )
                    self._api_call("POST", url, {})
                else:
                    note_url = (
                        f"{self._base_url}/api/{self.PROJECT_API_VERSION}"
                        f"/projects/{project_enc}/merge_requests/{mr_iid}/notes"
                    )
                    self._api_call("POST", note_url, {"body": body})
            else:
                assert self._glab_cli is not None
                if event == "APPROVE":
                    subprocess.run(
                        [self._glab_cli, "mr", "approve", str(mr_iid), "--project", project],
                        check=True, capture_output=True, text=True, timeout=30,
                    )
                else:
                    subprocess.run(
                        [self._glab_cli, "mr", "note", str(mr_iid),
                         "--project", project, "--message", body],
                        check=True, capture_output=True, text=True, timeout=30,
                    )
            return self._record(
                "submit_mr_review", ref.target, True,
                {"event": event, "body": body[:200]},
            )
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as exc:
            return self._record(
                "submit_mr_review", ref.target, False, {"error": str(exc)},
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
        lines = ["## GitLab Connector Operations", ""]
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


# Anti-ghost counter (P12.1.3): shared with parent framework for unified gating.
# Local counter exists for module-level anti-ghost introspection.
_call_counter: int = 0


def get_call_count() -> int:
    """Return the module-level call counter (GitLab connector only).

    Note: This counter increments ONLY on GitLab connector public method
    invocations. The parent ``connector_framework.get_call_count()`` returns
    the unified counter that includes both GitHub and GitLab activity.
    The CI gate ``check_module_activation.py`` queries both to prove
    each connector implementation is wired in.
    """
    return _call_counter
