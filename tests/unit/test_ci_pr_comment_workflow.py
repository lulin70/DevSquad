"""Structural guard for the P2-b failure-comment workflow (V4.6.0).

The e2e failure comment is CI-only behavior: no unit test can execute it
locally. These tests pin the *declaration* instead — the permission, the
comment step, and its failure-scoping — so a later edit cannot silently drop
the feature or widen its trigger (design §10 Q4).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
_TEST_YML = _WORKFLOWS / "test.yml"
_RELEASE_E2E_YML = _WORKFLOWS / "release-e2e.yml"

_COMMENT_BODY_PATH = "/tmp/e2e-comment.md"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _e2e_steps() -> list[dict]:
    return _load(_TEST_YML)["jobs"]["e2e"]["steps"]


def _step_with_run(steps: list[dict], fragment: str) -> dict | None:
    return next((s for s in steps if fragment in str(s.get("run", ""))), None)


class TestPullRequestPermission:
    def test_pull_requests_write_is_granted(self):
        """``gh pr comment`` needs it; without it the step fails silently."""
        permissions = _load(_TEST_YML)["permissions"]
        assert permissions.get("pull-requests") == "write"

    def test_contents_stays_read_only(self):
        """The P2-b permission is the only widening; no repo write is added."""
        permissions = _load(_TEST_YML)["permissions"]
        assert permissions.get("contents") == "read"


class TestCommentStep:
    def test_comment_step_exists_and_is_sticky(self):
        step = _step_with_run(_e2e_steps(), "gh pr comment")
        assert step is not None, "the e2e job no longer posts a PR comment"
        run = step["run"]
        assert f"--body-file {_COMMENT_BODY_PATH}" in run
        # Idempotence: one comment per PR, updated on rerun.
        assert "--edit-last" in run
        assert "--create-if-none" in run

    def test_comment_step_cannot_change_job_status(self):
        step = _step_with_run(_e2e_steps(), "gh pr comment")
        assert step is not None
        assert step.get("continue-on-error") is True

    def test_comment_step_is_failure_scoped_to_pull_requests(self):
        step = _step_with_run(_e2e_steps(), "gh pr comment")
        assert step is not None
        condition = str(step.get("if", ""))
        assert "failure()" in condition
        assert "github.event_name == 'pull_request'" in condition


class TestSummarySteps:
    def test_summary_dispatch_is_produced(self):
        step = _step_with_run(_e2e_steps(), "/tmp/dispatch-summary.json")
        assert step is not None, "the comment has no data source"
        run = step["run"]
        assert "scripts/cli.py dispatch" in run
        assert "-f json" in run
        # A failed dispatch must not fail the job: the summary is derived data.
        assert "|| true" in run

    def test_comment_body_discloses_the_four_structured_fields(self):
        step = _step_with_run(_e2e_steps(), _COMMENT_BODY_PATH)
        assert step is not None
        run = step["run"]
        for field in ("failure_class", "coverage", "failed_roles", "replay_cache"):
            assert field in run, f"comment body no longer reports {field}"
        # The run URL lets a human return to the actual failure site.
        assert "actions/runs/" in run

    def test_summary_steps_do_not_run_on_green_pull_requests(self):
        """Cost guard: the summary dispatch makes real model calls on a miss."""
        for fragment in ("/tmp/dispatch-summary.json", _COMMENT_BODY_PATH, "gh pr comment"):
            step = _step_with_run(_e2e_steps(), fragment)
            assert step is not None
            assert "failure()" in str(step.get("if", "")), f"{fragment} runs outside a failing job"


class TestJudgeWiring:
    def test_release_gate_configures_a_cross_provider_judge(self):
        """The judge rides on existing Anthropic credentials (design §10 Q3)."""
        doc = _load(_RELEASE_E2E_YML)
        job = doc["jobs"]["real-llm-e2e"]
        env = job["env"]
        assert env["DEVSQUAD_JUDGE_API_KEY"] == "${{ secrets.DEVSQUAD_ANTHROPIC_API_KEY }}"
        assert env["DEVSQUAD_JUDGE_BACKEND"] == "anthropic"

    def test_judge_never_reuses_the_author_key(self):
        """Self-judging is the trap this separation exists to avoid."""
        for job in _load(_RELEASE_E2E_YML)["jobs"].values():
            env = job.get("env") or {}
            judge_key = str(env.get("DEVSQUAD_JUDGE_API_KEY", ""))
            if judge_key:
                assert "OPENAI" not in judge_key.upper()


class TestWorkflowFilesParse:
    @pytest.mark.parametrize("workflow", [_TEST_YML, _RELEASE_E2E_YML])
    def test_yaml_is_valid(self, workflow):
        assert isinstance(_load(workflow), dict)
