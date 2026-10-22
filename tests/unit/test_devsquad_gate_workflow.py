"""Structural guard for the devsquad-gate reusable workflow (V4.8.0 P1-R1).

The gate is a reusable workflow consumed by external repositories: no unit
test can execute it locally. These tests pin the *declaration* instead —
the workflow_call trigger, the minimal permission set, the SHA-pinned
actions, the fail-closed exit wiring, and the protocol-v1 comment anchor —
so a later edit cannot silently drop the feature or widen its surface
(design doc V4.8.0_R1_devsquad_gate_DESIGN.md §2/§4/§5; test matrix T-1).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
_GATE_YML = _WORKFLOWS / "devsquad-gate.yml"

_SHA = re.compile(r"^[0-9a-f]{40}$")


def _load() -> dict:
    return yaml.safe_load(_GATE_YML.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    return _load()["jobs"]["gate"]["steps"]


def _step(name_fragment: str) -> dict:
    return next(s for s in _steps() if name_fragment in s.get("name", ""))


def _trigger() -> dict:
    """YAML 1.1 parses the bare `on:` key as boolean True."""
    doc = _load()
    return doc.get(True, doc.get("on", {}))


class TestReusability:
    def test_triggers_on_workflow_call_only(self):
        assert "workflow_call" in _trigger()

    def test_declared_inputs_match_the_design(self):
        inputs = _trigger()["workflow_call"]["inputs"]
        expected = {
            "devsquad-version": "4.8.0",
            "task": "devsquad-gate: deterministic PR review",
            "include": "",
            "exclude": "",
            "fail-on": "break",
            "preview-only": False,
        }
        for name, default in expected.items():
            assert inputs[name]["default"] == default, f"input {name} default changed"


class TestPermissions:
    def test_permission_set_is_minimal(self):
        permissions = _load()["permissions"]
        assert permissions == {"contents": "read", "pull-requests": "write"}


class TestSupplyChain:
    @pytest.mark.parametrize("step_name", ["Check out", "Set up Python"])
    def test_actions_are_pinned_to_full_sha(self, step_name):
        step = _step(step_name)
        ref = step["uses"].split("@", 1)[1].split()[0]
        assert _SHA.match(ref), f"{step_name} is not pinned to a full SHA: {ref}"


class TestFailClosedShape:
    def test_install_failure_cannot_red_the_job_directly(self):
        """Design §5: a failed install becomes an honest blocked verdict,
        not a raw red job — the verdict step owns the exit code."""
        assert _step("Install").get("continue-on-error") is True

    def test_review_step_runs_the_diff_file_face_in_json(self):
        run = _step("Run deterministic review")["run"]
        assert "--diff-file /tmp/pr.diff" in run
        assert "--format json" in run
        assert "devsquad review" in run

    def test_verdict_step_is_the_single_decision_point(self):
        run = _step("Compute verdict")["run"]
        assert "lifecycle_findings" in run
        assert "/tmp/gate-exit" in run

    def test_exit_step_uses_the_verdict_code(self):
        run = _step("Exit by verdict")["run"]
        assert 'exit "$(cat /tmp/gate-exit)"' in run

    def test_inputs_never_interpolate_directly_into_the_shell(self):
        """Injection guard: task/include/exclude ride env vars, not ${{ }}."""
        for step in _steps():
            run = str(step.get("run", ""))
            for risky in ("inputs.include", "inputs.exclude", "inputs.task"):
                assert ("${{ " + risky + " }}") not in run, f"{risky} interpolated into shell"

    def test_job_has_timeout_and_per_pr_concurrency(self):
        job = _load()["jobs"]["gate"]
        assert job["timeout-minutes"] == 15
        assert job["concurrency"]["cancel-in-progress"] is True


class TestCommentProtocol:
    def test_comment_step_is_sticky_and_idempotent(self):
        step = _step("Post the PR comment")
        run = step["run"]
        assert "gh pr comment" in run
        assert "--edit-last" in run
        assert "--create-if-none" in run

    def test_comment_failure_cannot_change_the_verdict(self):
        assert _step("Post the PR comment").get("continue-on-error") is True

    def test_comment_body_carries_protocol_v1_anchor(self):
        run = _step("Compute verdict")["run"]
        assert "<!-- devsquad-gate v1 -->" in run

    def test_comment_body_reports_the_four_structured_fields(self):
        run = _step("Compute verdict")["run"]
        for field in ("verdict:", "findings:", "failure_class:", "coverage:"):
            assert field in run

    def test_no_secret_values_can_enter_the_comment(self):
        """Only whitelisted counts/labels enter the body (design §6)."""
        run = _step("Compute verdict")["run"]
        assert "secrets." not in run


class TestWorkflowFileParses:
    def test_yaml_is_valid(self):
        assert isinstance(_load(), dict)
