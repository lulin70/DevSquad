"""Tests for scripts.collaboration.task_completion_checker.

Covers TaskCompletionResult dataclass, TaskCompletionChecker init,
progress loading/saving, dispatch result checking, schedule result
checking, history/summary queries, and reset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import patch

from scripts.collaboration.task_completion_checker import (
    TaskCompletionChecker,
    TaskCompletionResult,
)

# ---------------------------------------------------------------------------
# Stub objects
# ---------------------------------------------------------------------------


@dataclass
class StubWorkerResult:
    worker_id: str = "architect"
    success: bool = True
    error: str | None = None
    duration_seconds: float = 1.0
    task_id: str = "test-task"
    output: str = "done"


@dataclass
class StubScheduleResult:
    total_tasks: int = 3
    completed_tasks: int = 2
    failed_tasks: int = 1
    results: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class StubDispatchResult:
    """Minimal dispatch result stub with worker_results and task_description."""

    def __init__(self, task_description: str = "test task", worker_results: list | None = None):
        self.task_description = task_description
        self.worker_results = worker_results or []


def _make_worker(role: str = "architect", success: bool = True, output: str = "ok", error: str | None = None) -> dict:
    return {
        "role_id": role,
        "role_name": role.title(),
        "success": success,
        "output": output,
        "error": error,
    }


# ---------------------------------------------------------------------------
# TaskCompletionResult dataclass
# ---------------------------------------------------------------------------


class TestTaskCompletionResult:
    def test_defaults(self):
        r = TaskCompletionResult(task_id="t1", is_completed=False)
        assert r.task_id == "t1"
        assert r.is_completed is False
        assert r.completion_rate == 0.0
        assert r.total_subtasks == 0
        assert r.completed_subtasks == 0
        assert r.failed_subtasks == 0
        assert r.pending_subtasks == 0
        assert r.details == []
        assert r.summary == ""

    def test_custom_values(self):
        r = TaskCompletionResult(
            task_id="t2",
            is_completed=True,
            completion_rate=100.0,
            total_subtasks=3,
            completed_subtasks=3,
            summary="All done",
        )
        assert r.is_completed is True
        assert r.completion_rate == 100.0
        assert r.summary == "All done"


# ---------------------------------------------------------------------------
# __init__ and progress loading
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_creates_storage_dir(self, tmp_path):
        storage = tmp_path / "progress"
        TaskCompletionChecker(storage_path=str(storage))
        assert storage.exists()

    def test_init_loads_existing_progress(self, tmp_path):
        storage = tmp_path / "progress"
        storage.mkdir()
        progress_file = storage / "progress.json"
        progress_data = {
            "last_update": "2026-01-01T00:00:00",
            "dispatches": {"task1": {"is_completed": True, "completion_rate": 100.0}},
        }
        progress_file.write_text(json.dumps(progress_data))
        checker = TaskCompletionChecker(storage_path=str(storage))
        assert "task1" in checker.progress["dispatches"]

    def test_init_with_corrupt_progress_file(self, tmp_path):
        storage = tmp_path / "progress"
        storage.mkdir()
        progress_file = storage / "progress.json"
        progress_file.write_text("{invalid json}")
        checker = TaskCompletionChecker(storage_path=str(storage))
        assert "dispatches" in checker.progress
        assert checker.progress["dispatches"] == {}

    def test_init_creates_empty_progress_when_no_file(self, tmp_path):
        storage = tmp_path / "progress"
        checker = TaskCompletionChecker(storage_path=str(storage))
        assert "last_update" in checker.progress
        assert checker.progress["dispatches"] == {}


# ---------------------------------------------------------------------------
# check_dispatch_result
# ---------------------------------------------------------------------------


class TestCheckDispatchResult:
    def test_all_workers_success(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True), _make_worker("coder", True)]
        result = checker.check_dispatch_result(StubDispatchResult("test task", workers))
        assert result.is_completed is True
        assert result.completion_rate == 100.0
        assert result.total_subtasks == 2
        assert result.completed_subtasks == 2
        assert result.failed_subtasks == 0
        assert "All 2 workers completed" in result.summary

    def test_partial_failure(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True), _make_worker("coder", False, error="boom")]
        result = checker.check_dispatch_result(StubDispatchResult("test task", workers))
        assert result.is_completed is False
        assert result.completion_rate == 50.0
        assert result.failed_subtasks == 1
        assert "1/2 workers succeeded" in result.summary

    def test_no_workers(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        result = checker.check_dispatch_result(StubDispatchResult("empty task", []))
        assert result.is_completed is False
        assert result.completion_rate == 0.0
        assert result.total_subtasks == 0

    def test_worker_details_built(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True, output="hello world")]
        result = checker.check_dispatch_result(StubDispatchResult("test", workers))
        assert len(result.details) == 1
        detail = result.details[0]
        assert detail["role"] == "architect"
        assert detail["success"] is True
        assert detail["output_preview"] == "hello world"

    def test_worker_with_no_output(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [{"role_id": "tester", "role_name": "Tester", "success": True, "output": ""}]
        result = checker.check_dispatch_result(StubDispatchResult("test", workers))
        assert result.details[0]["output_preview"] is None

    def test_long_output_truncated(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        long_output = "x" * 200
        workers = [_make_worker("architect", True, output=long_output)]
        result = checker.check_dispatch_result(StubDispatchResult("test", workers))
        assert len(result.details[0]["output_preview"]) == 100

    def test_records_dispatch_in_progress(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True)]
        checker.check_dispatch_result(StubDispatchResult("my task", workers))
        history = checker.get_dispatch_history()
        assert "my task" in history

    def test_task_id_truncated(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        long_task = "x" * 100
        result = checker.check_dispatch_result(StubDispatchResult(long_task, []))
        assert len(result.task_id) == 50

    def test_verification_gate_error_handled(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True)]
        with patch(
            "scripts.collaboration.verification_gate.get_shared_gate",
            side_effect=RuntimeError("gate error"),
        ):
            result = checker.check_dispatch_result(StubDispatchResult("test", workers))
        assert result.is_completed is True

    def test_worker_uses_role_fallback(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [{"role": "pm", "success": True, "output": "ok"}]
        result = checker.check_dispatch_result(StubDispatchResult("test", workers))
        assert result.details[0]["role"] == "pm"


# ---------------------------------------------------------------------------
# check_schedule_result
# ---------------------------------------------------------------------------


class TestCheckScheduleResult:
    def test_all_completed(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        results = [
            StubWorkerResult(worker_id="w1", success=True, task_id="task-A"),
            StubWorkerResult(worker_id="w2", success=True, task_id="task-A"),
        ]
        schedule = StubScheduleResult(total_tasks=2, completed_tasks=2, failed_tasks=0, results=results)
        result = checker.check_schedule_result(schedule)
        assert result.is_completed is True
        assert result.completion_rate == 100.0
        assert result.total_subtasks == 2
        assert result.completed_subtasks == 2
        assert "All 2 tasks completed" in result.summary

    def test_partial_failure(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        results = [
            StubWorkerResult(worker_id="w1", success=True, task_id="task-B"),
            StubWorkerResult(worker_id="w2", success=False, error="fail", task_id="task-B"),
        ]
        schedule = StubScheduleResult(total_tasks=2, completed_tasks=1, failed_tasks=1, results=results)
        result = checker.check_schedule_result(schedule)
        assert result.is_completed is False
        assert result.completion_rate == 50.0
        assert result.failed_subtasks == 1
        assert "1/2 tasks succeeded" in result.summary

    def test_with_errors_in_schedule(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        results = [StubWorkerResult(worker_id="w1", success=False, error="err", task_id="task-C")]
        schedule = StubScheduleResult(
            total_tasks=1, completed_tasks=0, failed_tasks=1, results=results, errors=["err1"]
        )
        result = checker.check_schedule_result(schedule)
        assert "Errors: 1" in result.summary

    def test_zero_total_tasks(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        schedule = StubScheduleResult(total_tasks=0, completed_tasks=0, failed_tasks=0, results=[])
        result = checker.check_schedule_result(schedule)
        assert result.is_completed is False
        assert result.completion_rate == 0.0
        assert result.task_id == "unknown"

    def test_pending_calculated(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        results = [StubWorkerResult(worker_id="w1", success=True, task_id="t")]
        schedule = StubScheduleResult(total_tasks=3, completed_tasks=1, failed_tasks=0, results=results)
        result = checker.check_schedule_result(schedule)
        assert result.pending_subtasks == 2

    def test_details_from_schedule(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        results = [
            StubWorkerResult(worker_id="w1", success=True, duration_seconds=2.5, task_id="t"),
        ]
        schedule = StubScheduleResult(total_tasks=1, completed_tasks=1, results=results)
        result = checker.check_schedule_result(schedule)
        assert len(result.details) == 1
        assert result.details[0]["role"] == "w1"
        assert result.details[0]["duration"] == 2.5


# ---------------------------------------------------------------------------
# get_dispatch_history / get_completion_summary / is_task_completed
# ---------------------------------------------------------------------------


class TestHistoryAndSummary:
    def test_get_dispatch_history_empty(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        assert checker.get_dispatch_history() == {}

    def test_get_dispatch_history_after_dispatch(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True)]
        checker.check_dispatch_result(StubDispatchResult("task1", workers))
        history = checker.get_dispatch_history()
        assert "task1" in history
        assert history["task1"]["is_completed"] is True

    def test_get_completion_summary_empty(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        summary = checker.get_completion_summary()
        assert "No dispatch history" in summary

    def test_get_completion_summary_with_data(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True)]
        checker.check_dispatch_result(StubDispatchResult("task1", workers))
        checker.check_dispatch_result(StubDispatchResult("task2", [_make_worker("coder", False)]))
        summary = checker.get_completion_summary()
        assert "Task Completion Summary" in summary
        assert "task1" in summary
        assert "task2" in summary

    def test_is_task_completed_true(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True)]
        checker.check_dispatch_result(StubDispatchResult("done-task", workers))
        assert checker.is_task_completed("done-task") is True

    def test_is_task_completed_false(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", False)]
        checker.check_dispatch_result(StubDispatchResult("fail-task", workers))
        assert checker.is_task_completed("fail-task") is False

    def test_is_task_completed_unknown(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        assert checker.is_task_completed("nonexistent") is False


# ---------------------------------------------------------------------------
# reset_progress / _save_progress error handling
# ---------------------------------------------------------------------------


class TestResetAndSave:
    def test_reset_progress(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        workers = [_make_worker("architect", True)]
        checker.check_dispatch_result(StubDispatchResult("task1", workers))
        assert len(checker.get_dispatch_history()) > 0
        checker.reset_progress()
        assert checker.get_dispatch_history() == {}

    def test_reset_creates_fresh_progress(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        checker.reset_progress()
        assert "last_update" in checker.progress
        assert checker.progress["dispatches"] == {}

    def test_save_progress_error_handled(self, tmp_path):
        checker = TaskCompletionChecker(storage_path=str(tmp_path / "p"))
        with patch("builtins.open", side_effect=OSError("disk full")):
            checker._save_progress()
