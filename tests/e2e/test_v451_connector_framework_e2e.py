#!/usr/bin/env python3
"""E2E test for V4.5.1 Connector Framework (V451-2 / V451-9).

Verifies the Connector Framework is properly wired into the dispatch
pipeline (anti-ghost) and that user-visible artifacts (Markdown report,
to_dict serialization) contain the expected connector output.

Iron Rules (per V4.5.1 anti-ghost discipline):
  1. ``GitHubConnector._call_counter`` MUST be > 0 after a single
     ``dispatch()`` call — otherwise the connector is a ghost feature.
  2. Dispatch result MUST expose ``connector_operations`` (list) and
     ``connector_md`` (str) fields, populated by ``_activate_connector``.
  3. ``result.to_markdown()`` MUST render a ``## Connector Operations``
     section when ``connector_md`` is non-empty (user-visible output).
  4. ``result.to_dict()`` MUST include the ``connector_operations`` key
     for JSON consumers (e.g. dashboard, API server).
  5. The simulation-mode probe operation MUST be recorded as
     ``success=True`` with ``simulation=True`` details — proving the
     pipeline path was exercised without touching the real GitHub API.

Coverage:
  - test_e2e_dispatch_increments_connector_call_counter  (AG-1 anti-ghost)
  - test_e2e_dispatch_populates_connector_operations     (AG-2 integration)
  - test_e2e_dispatch_populates_connector_md             (AG-3 integration)
  - test_e2e_to_markdown_contains_connector_section      (AG-4 user-visible)
  - test_e2e_to_dict_contains_connector_operations_key   (AG-5 serialization)
  - test_e2e_simulation_operation_recorded_successfully  (AG-6 sim-mode path)
  - test_e2e_dry_run_path_also_activates_connector       (AG-7 early-return)
  - test_e2e_connector_md_has_github_header              (AG-8 markdown shape)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.collaboration import connector_framework as connector_module  # noqa: E402
from scripts.collaboration.connector_framework import (  # noqa: E402
    GitHubConnector,
    get_call_count,
)
from scripts.collaboration.dispatcher import MultiAgentDispatcher  # noqa: E402

pytestmark = [
    pytest.mark.e2e,
]


@pytest.fixture
def dispatcher() -> MultiAgentDispatcher:
    """Create a real MultiAgentDispatcher with default mock backend."""
    return MultiAgentDispatcher()


@pytest.fixture(autouse=True)
def _ensure_no_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force simulation mode for determinism (no real GitHub API calls)."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Block gh CLI lookup so simulation mode is selected even if gh is on PATH.
    monkeypatch.setattr("shutil.which", lambda *_args, **_kw: None)


# ---------------------------------------------------------------------------
# AG-1: _call_counter increments after a single dispatch() call (anti-ghost)
# ---------------------------------------------------------------------------


def test_e2e_dispatch_increments_connector_call_counter(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-1: One dispatch() call MUST increment GitHubConnector._call_counter > 0.

    A counter stuck at 0 means the connector is ghost code — present on disk
    but never activated by the dispatch pipeline. CI treats this as a critical
    quality defect (per V4.5.1 anti-ghost discipline).
    """
    before = connector_module._call_counter
    dispatcher.dispatch("Design a payment gateway")
    after = connector_module._call_counter

    assert after > before, (
        f"GitHubConnector._call_counter did not increment during dispatch: "
        f"before={before}, after={after}. The connector is a ghost feature."
    )
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# AG-2: dispatch result populates result.connector_operations (integration)
# ---------------------------------------------------------------------------


def test_e2e_dispatch_populates_connector_operations(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-2: dispatch() MUST populate result.connector_operations (list)."""
    result = dispatcher.dispatch("Refactor the auth module")
    assert isinstance(result.connector_operations, list), (
        f"connector_operations must be a list, got: {type(result.connector_operations)}"
    )
    assert len(result.connector_operations) >= 1, (
        "connector_operations must be populated (≥1 probe op) after dispatch"
    )
    op = result.connector_operations[0]
    assert op["connector_name"] == "github", (
        f"connector_name must be 'github', got: {op['connector_name']!r}"
    )
    assert op["operation"] == "create_pr_comment", (
        f"operation must be 'create_pr_comment' (probe), got: {op['operation']!r}"
    )
    assert op["success"] is True, (
        f"simulation-mode probe must succeed, got success={op['success']}"
    )
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# AG-3: dispatch result populates result.connector_md (integration)
# ---------------------------------------------------------------------------


def test_e2e_dispatch_populates_connector_md(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-3: dispatch() MUST populate result.connector_md (non-empty str)."""
    result = dispatcher.dispatch("Build a search index")
    assert isinstance(result.connector_md, str), (
        f"connector_md must be a str, got: {type(result.connector_md)}"
    )
    assert result.connector_md != "", (
        "connector_md must be non-empty after dispatch (probe op recorded)"
    )
    assert "## Connector Operations" in result.connector_md, (
        "connector_md must contain the '## Connector Operations' header"
    )
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# AG-4: result.to_markdown() contains '## Connector Operations' section
# ---------------------------------------------------------------------------


def test_e2e_to_markdown_contains_connector_section(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-4: to_markdown() MUST render the '## Connector Operations' section.

    User-visible output is a hard requirement of the anti-ghost principle:
    if the user cannot see the connector's contribution in the report, the
    module is treated as a ghost.
    """
    result = dispatcher.dispatch("Design a cache layer")
    md = result.to_markdown()
    assert "## Connector Operations" in md, (
        "to_markdown() must contain '## Connector Operations' section"
    )
    # The markdown must reference the github connector and its mode.
    assert "github" in md.lower(), "to_markdown() must mention the 'github' connector"
    # Simulation-mode probe must be reported as OK.
    assert "OK" in md, "to_markdown() must render OK status for successful ops"
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# AG-5: result.to_dict() contains 'connector_operations' key (serialization)
# ---------------------------------------------------------------------------


def test_e2e_to_dict_contains_connector_operations_key(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-5: to_dict() MUST include 'connector_operations' for JSON consumers."""
    result = dispatcher.dispatch("Design a queue system")
    d = result.to_dict()
    assert "connector_operations" in d, (
        "to_dict() must contain 'connector_operations' key"
    )
    assert isinstance(d["connector_operations"], list)
    assert len(d["connector_operations"]) >= 1, (
        "connector_operations in to_dict() must be populated after dispatch"
    )
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# AG-6: simulation-mode probe operation is recorded as success with sim flag
# ---------------------------------------------------------------------------


def test_e2e_simulation_operation_recorded_successfully(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-6: The probe operation MUST be recorded as success with simulation=True.

    This proves the pipeline path was exercised end-to-end through the
    GitHubConnector public API without touching the real GitHub API
    (deterministic, network-safe).
    """
    result = dispatcher.dispatch("Plan a release")
    assert len(result.connector_operations) >= 1
    op = result.connector_operations[0]
    assert op["success"] is True, "simulation-mode probe must succeed"
    assert op["details"].get("simulation") is True, (
        f"simulation flag must be True in details, got: {op['details']}"
    )
    # The body must be a non-empty string (truncated to 200 chars).
    body = op["details"].get("body", "")
    assert isinstance(body, str) and body, (
        f"simulation body must be a non-empty str, got: {body!r}"
    )
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# AG-7: dry_run (early_return) path also activates the connector (anti-ghost)
# ---------------------------------------------------------------------------


def test_e2e_dry_run_path_also_activates_connector(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-7: dry_run=True (early_return path) MUST still activate the connector.

    The early_return path in dispatch() is a common place for ghost features
    to hide — modules that only activate on the normal execution path are
    only half-wired. This test proves _activate_connector is called on BOTH
    paths (early_return and normal).
    """
    before = connector_module._call_counter
    result = dispatcher.dispatch("Design a tokens system", dry_run=True)
    after = connector_module._call_counter

    assert after > before, (
        "Connector must be activated on the dry_run / early_return path too"
    )
    # And the result must still carry the connector artifacts.
    assert len(result.connector_operations) >= 1, (
        "dry_run result must still populate connector_operations"
    )
    assert result.connector_md != "", (
        "dry_run result must still populate connector_md"
    )
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# AG-8: connector_md has the github connector header and mode label
# ---------------------------------------------------------------------------


def test_e2e_connector_md_has_github_header(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """AG-8: connector_md MUST render the github connector header + mode label.

    Markdown shape contract:
      ## Connector Operations

      **Connector**: github (mode: simulation)

      1. **OK** — create_pr_comment → devsquad/internal#0
    """
    result = dispatcher.dispatch("Audit the dependencies")
    md = result.connector_md
    assert md.startswith("## Connector Operations"), (
        f"connector_md must start with '## Connector Operations', got: {md[:60]!r}"
    )
    assert "**Connector**: github" in md, (
        "connector_md must render the 'Connector: github' label line"
    )
    assert "mode: simulation" in md, (
        "connector_md must render the simulation mode label"
    )
    # The probe op target must be 'devsquad/internal#0' (per _activate_connector).
    assert "devsquad/internal#0" in md, (
        "connector_md must reference the probe target 'devsquad/internal#0'"
    )
    dispatcher.shutdown()


# ---------------------------------------------------------------------------
# Direct unit-level E2E sanity: GitHubConnector simulation-mode basics
# ---------------------------------------------------------------------------


def test_e2e_github_connector_simulation_mode_default() -> None:
    """Happy: GitHubConnector defaults to simulation mode without token/CLI.

    This is a network-safe sanity check that complements the dispatch-level
    E2E tests above. It runs against the real GitHubConnector class (no Mock)
    to prove the public API works end-to-end in simulation mode.
    """
    connector = GitHubConnector()
    assert connector.mode == "simulation", (
        f"default mode must be 'simulation', got: {connector.mode!r}"
    )

    op = connector.create_pr_comment("devsquad/test", 1, "hello world")
    assert op.success is True
    assert op.connector_name == "github"
    assert op.operation == "create_pr_comment"
    assert op.target == "devsquad/test#1"
    assert op.details.get("simulation") is True
    assert op.details.get("body") == "hello world"

    ops = connector.get_operations()
    assert len(ops) == 1
    assert ops[0]["operation"] == "create_pr_comment"

    md = connector.export_markdown()
    assert "## Connector Operations" in md
    assert "github" in md
    assert "devsquad/test#1" in md


def test_e2e_github_connector_invalid_state_validation() -> None:
    """Happy: update_issue_state validates state ∈ {open, closed}.

    Invalid states are recorded as a FAILED operation (not raised), so the
    dispatch pipeline is never broken by a bad connector call.
    """
    connector = GitHubConnector()
    op = connector.update_issue_state("devsquad/test", 5, "deleted")
    assert op.success is False, "invalid state must record as failed"
    assert "Invalid state" in op.details.get("error", "")
    # The failure is still recorded in operations for audit.
    assert len(connector.get_operations()) == 1


def test_e2e_github_connector_invalid_review_event_validation() -> None:
    """Happy: submit_pr_review validates event ∈ {APPROVE, REQUEST_CHANGES, COMMENT}."""
    connector = GitHubConnector()
    op = connector.submit_pr_review("devsquad/test", 9, "REJECT", "blocking")
    assert op.success is False, "invalid event must record as failed"
    assert "Invalid event" in op.details.get("error", "")


def test_e2e_get_call_count_returns_module_counter() -> None:
    """Anti-Ghost: get_call_count() mirrors connector_module._call_counter."""
    connector = GitHubConnector()
    connector.create_pr_comment("devsquad/probe", 0, "probe")
    module_value = connector_module._call_counter
    assert get_call_count() == module_value, (
        f"get_call_count()={get_call_count()} != _call_counter={module_value}"
    )
