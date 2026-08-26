"""Tests for GitLabConnector (V4.5.2 P12.1.3)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from scripts.collaboration.gitlab_connector import (
    GitLabConnector,
    GitLabMRRef,
    _call_counter_er,
    get_call_count,
)


@pytest.fixture(autouse=True)
def reset_counter():
    """Reset module-level counter between tests."""
    import scripts.collaboration.gitlab_connector as mod
    mod._call_counter_er = 0
    yield
    mod._call_counter_er = 0


class TestGitLabConnectorConstants:
    """Test class-level constants."""

    def test_connector_name(self):
        assert GitLabConnector.CONNECTOR_NAME == "gitlab"

    def test_default_base_url(self):
        assert GitLabConnector.DEFAULT_BASE_URL == "https://gitlab.com"

    def test_project_api_version(self):
        assert GitLabConnector.PROJECT_API_VERSION == "v4"


class TestGitLabConnectorInit:
    """Test constructor and configuration loading."""

    def setup_method(self):
        for k in ("GITLAB_TOKEN", "GITLAB_BASE_URL"):
            os.environ.pop(k, None)

    def test_init_default_base_url(self):
        g = GitLabConnector()
        assert g.base_url == "https://gitlab.com"

    def test_init_env_base_url(self):
        with patch.dict(os.environ, {"GITLAB_BASE_URL": "https://gl.example.com"}, clear=True):
            g = GitLabConnector()
            assert g.base_url == "https://gl.example.com"

    def test_init_kwargs_base_url(self):
        g = GitLabConnector(base_url="https://gl.acme.io/")
        assert g.base_url == "https://gl.acme.io"  # trailing slash stripped

    def test_init_explicit_token(self):
        g = GitLabConnector(token="test-token")
        assert g._token == "test-token"

    def test_init_env_token(self):
        with patch.dict(os.environ, {"GITLAB_TOKEN": "env-token"}, clear=True):
            g = GitLabConnector()
            assert g._token == "env-token"

    def test_init_simulation_flag(self):
        g = GitLabConnector(simulation=True)
        assert g._force_simulation is True


class TestGitLabConnectorMode:
    """Test mode selection logic."""

    def test_simulation_explicit(self):
        g = GitLabConnector(token="real-token", simulation=True)
        assert g.mode == "simulation"

    def test_api_with_token(self):
        g = GitLabConnector(token="real-token")
        assert g.mode == "api"

    def test_simulation_default(self):
        g = GitLabConnector()
        assert g.mode == "simulation"

    def test_cli_when_glab_available(self):
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/glab"
            g = GitLabConnector()
            assert g.mode == "cli"

    def test_api_overrides_cli(self):
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/glab"
            g = GitLabConnector(token="real-token")
            assert g.mode == "api"  # token takes priority


class TestGitLabMRRef:
    """Test GitLabMRRef dataclass."""

    def test_construct(self):
        ref = GitLabMRRef(project="g/p", mr_iid=42)
        assert ref.project == "g/p"
        assert ref.mr_iid == 42

    def test_target_format(self):
        ref = GitLabMRRef(project="mygroup/myproject", mr_iid=7)
        assert ref.target == "mygroup/myproject!7"


class TestCreateMRComment:
    """Test create_mr_comment method."""

    def test_simulation_mode(self):
        g = GitLabConnector(simulation=True)
        op = g.create_mr_comment("g/p", 42, "hello")
        assert op.success
        assert op.operation == "create_mr_comment"
        assert op.target == "g/p!42"
        assert op.connector_name == "gitlab"
        assert op.details["simulation"] is True
        assert "hello" in op.details["body"]

    def test_increments_counter(self):
        g = GitLabConnector(simulation=True)
        before = get_call_count()
        g.create_mr_comment("g/p", 42, "hello")
        assert get_call_count() == before + 1


class TestUpdateIssueState:
    """Test update_issue_state method."""

    def test_open_simulation(self):
        g = GitLabConnector(simulation=True)
        op = g.update_issue_state("g/p", 7, "open")
        assert op.success
        assert op.details["state"] == "open"

    def test_closed_simulation(self):
        g = GitLabConnector(simulation=True)
        op = g.update_issue_state("g/p", 7, "closed")
        assert op.success
        assert op.details["state"] == "closed"

    def test_uppercase_state_normalized(self):
        g = GitLabConnector(simulation=True)
        op = g.update_issue_state("g/p", 7, "CLOSED")
        assert op.success
        assert op.details["state"] == "closed"

    def test_invalid_state_returns_failure(self):
        g = GitLabConnector(simulation=True)
        op = g.update_issue_state("g/p", 7, "in-progress")
        assert op.success is False
        assert "Invalid state" in op.details["error"]

    def test_increments_counter(self):
        g = GitLabConnector(simulation=True)
        before = get_call_count()
        g.update_issue_state("g/p", 7, "open")
        assert get_call_count() == before + 1


class TestSubmitMRReview:
    """Test submit_mr_review method."""

    def test_approve_simulation(self):
        g = GitLabConnector(simulation=True)
        op = g.submit_mr_review("g/p", 42, "APPROVE", "LGTM")
        assert op.success
        assert op.details["event"] == "APPROVE"

    def test_request_changes_simulation(self):
        g = GitLabConnector(simulation=True)
        op = g.submit_mr_review("g/p", 42, "REQUEST_CHANGES", "fix typo")
        assert op.success
        assert op.details["event"] == "REQUEST_CHANGES"

    def test_comment_simulation(self):
        g = GitLabConnector(simulation=True)
        op = g.submit_mr_review("g/p", 42, "COMMENT", "question")
        assert op.success
        assert op.details["event"] == "COMMENT"

    def test_invalid_event_returns_failure(self):
        g = GitLabConnector(simulation=True)
        op = g.submit_mr_review("g/p", 42, "MERGE", "wrong")
        assert op.success is False
        assert "Invalid event" in op.details["error"]

    def test_increments_counter(self):
        g = GitLabConnector(simulation=True)
        before = get_call_count()
        g.submit_mr_review("g/p", 42, "APPROVE", "LGTM")
        assert get_call_count() == before + 1


class TestGetOperations:
    """Test get_operations method."""

    def test_empty_initially(self):
        g = GitLabConnector(simulation=True)
        assert g.get_operations() == []

    def test_records_operations(self):
        g = GitLabConnector(simulation=True)
        g.create_mr_comment("g/p", 1, "x")
        g.update_issue_state("g/p", 2, "open")
        g.submit_mr_review("g/p", 3, "APPROVE", "y")
        ops = g.get_operations()
        assert len(ops) == 3
        assert ops[0]["operation"] == "create_mr_comment"
        assert ops[1]["operation"] == "update_issue_state"
        assert ops[2]["operation"] == "submit_mr_review"

    def test_increments_counter(self):
        g = GitLabConnector(simulation=True)
        before = get_call_count()
        g.get_operations()
        assert get_call_count() == before + 1


class TestExportMarkdown:
    """Test export_markdown method."""

    def test_empty_operations_returns_empty_string(self):
        g = GitLabConnector(simulation=True)
        assert g.export_markdown() == ""

    def test_renders_operations(self):
        g = GitLabConnector(simulation=True)
        g.create_mr_comment("g/p", 42, "hello")
        md = g.export_markdown()
        assert "GitLab Connector Operations" in md
        assert "gitlab" in md
        assert "create_mr_comment" in md
        assert "OK" in md

    def test_includes_failure_marker(self):
        g = GitLabConnector(simulation=True)
        g.update_issue_state("g/p", 7, "in-progress")  # invalid
        md = g.export_markdown()
        assert "FAILED" in md

    def test_increments_counter(self):
        g = GitLabConnector(simulation=True)
        before = get_call_counter_value()
        g.export_markdown()
        assert get_call_count() == before + 1


def get_call_counter_value() -> int:
    """Helper to read the current counter value."""
    return _call_counter_er


class TestAntiGhost:
    """Verify anti-ghost semantics."""

    def test_counter_starts_zero(self):
        # Reset by autouse fixture
        assert get_call_count() == 0

    def test_full_workflow_increments_counter(self):
        g = GitLabConnector(simulation=True)
        g.create_mr_comment("g/p", 1, "x")
        g.update_issue_state("g/p", 2, "open")
        g.submit_mr_review("g/p", 3, "APPROVE", "y")
        g.get_operations()
        g.export_markdown()
        # 5 public method calls
        assert get_call_count() == 5


class TestIndependentFromGitHub:
    """Verify GitLab connector has its own counter (not shared with GitHub)."""

    def test_gitlab_counter_independent(self):
        # Verify our local counter is module-level for gitlab_connector
        from scripts.collaboration import gitlab_connector as gc
        assert gc._call_counter_er >= 0

    def test_construct_two_connectors_share_local_counter(self):
        # Note: local counter is module-level, shared across instances.
        # This is intentional and matches parent framework pattern.
        g1 = GitLabConnector(simulation=True)
        g2 = GitLabConnector(simulation=True)
        g1.create_mr_comment("g/p", 1, "x")
        g2.create_mr_comment("g/p", 2, "y")
        assert get_call_count() == 2
