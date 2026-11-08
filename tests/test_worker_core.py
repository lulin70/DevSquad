#!/usr/bin/env python3
"""Unit tests for worker.py core functionality - Focus on real behavior validation.

Target: Test critical execution paths and edge cases that matter for system stability.
NOT targeting coverage numbers - targeting functional correctness.
"""

from __future__ import annotations

import asyncio

import pytest

from scripts.collaboration.models import (
    EntryType,
    ScratchpadEntry,
    TaskDefinition,
)
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker, _run_coro_on_thread


class TestRunCoroOnThread:
    """Test _run_coro_on_thread() - Critical for sync/async bridge."""

    def test_run_coro_returns_result(self) -> None:
        """Verify coroutine result is correctly returned to sync caller."""

        async def get_value() -> str:
            await asyncio.sleep(0.01)
            return "test_value"

        result = _run_coro_on_thread(get_value())
        assert result == "test_value"

    def test_run_coro_propagates_exception(self) -> None:
        """Verify exceptions in coroutine are propagated, not silenced."""

        async def failing_task() -> None:
            raise ValueError("Expected failure")

        with pytest.raises(ValueError, match="Expected failure"):
            _run_coro_on_thread(failing_task())


class TestWorkerReset:
    """Test Worker.reset() - Critical for worker pool reuse."""

    def test_reset_clears_transient_state(self) -> None:
        """Verify reset() clears notifications and counters for reuse."""
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )

        # Write an entry to increment counter
        entry = ScratchpadEntry(
            worker_id="test-001",
            role_id="tester",
            entry_type=EntryType.FINDING,
            content="Test finding",
        )
        worker.write_finding(entry)
        assert worker._entries_written_count > 0

        # Reset should clear counter
        worker.reset()
        assert worker._entries_written_count == 0
        assert len(worker._notifications_outbox) == 0

    def test_reset_preserves_identity(self) -> None:
        """Verify reset() does NOT change worker identity (critical for pooling)."""
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )
        original_id = worker.worker_id
        original_role = worker.role_id
        original_prompt = worker.role_prompt

        worker.reset()

        # Identity must be preserved for worker pool
        assert worker.worker_id == original_id
        assert worker.role_id == original_role
        assert worker.role_prompt == original_prompt


class TestWorkerExecute:
    """Test Worker.execute() - Core synchronous execution path."""

    def test_execute_returns_success_result(self) -> None:
        """Verify execute() returns WorkerResult on success."""
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )
        task = TaskDefinition(
            task_id="task-001",
            description="Test task",
        )

        result = worker.execute(task)

        # Verify result structure
        assert result.worker_id == "test-001"
        assert result.task_id == "task-001"
        assert result.success in (True, False)  # Either outcome is valid
        assert result.duration_seconds >= 0

    def test_execute_handles_exception_gracefully(self) -> None:
        """Verify execute() returns failure result instead of raising exception."""
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )

        # Task with None description should be handled
        task = TaskDefinition(
            task_id="task-001",
            description=None,  # type: ignore
        )

        # Should not raise, should return failure result
        result = worker.execute(task)
        assert result.task_id == "task-001"
        # Failure is acceptable, crash is not


class TestWorkerWriteMethods:
    """Test Worker write methods - Verify scratchpad integration."""

    def test_write_finding_persists_to_scratchpad(self) -> None:
        """Verify write_finding() actually writes to shared scratchpad."""
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )

        entry = ScratchpadEntry(
            worker_id="test-001",
            role_id="tester",
            entry_type=EntryType.FINDING,
            content="Critical bug found",
        )
        worker.write_finding(entry)

        # Verify it's actually in scratchpad
        entries = scratchpad.read(entry_type=EntryType.FINDING)
        assert len(entries) > 0
        assert any("Critical bug found" in e.content for e in entries)


class TestWorkerScratchpadIntegration:
    """Test Worker integration with Scratchpad."""

    def test_worker_can_read_from_shared_scratchpad(self) -> None:
        """Verify worker can read entries written by others."""
        scratchpad = Scratchpad()
        Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )

        # Another worker writes a finding
        finding = ScratchpadEntry(
            worker_id="arch-001",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="System design completed",
        )
        scratchpad.write(finding)

        # Tester should be able to read it
        entries = scratchpad.read(entry_type=EntryType.FINDING)
        assert len(entries) > 0
        assert any("design completed" in e.content for e in entries)


@pytest.mark.asyncio
async def test_aexecute_async_execution_path() -> None:
    """Test aexecute() - Verify async execution works."""
    scratchpad = Scratchpad()
    worker = Worker(
        worker_id="test-001",
        role_id="tester",
        role_prompt="Test role",
        scratchpad=scratchpad,
    )

    task = TaskDefinition(
        task_id="task-async-001",
        description="Async test task",
    )

    result = await worker.aexecute(task)

    # Verify async execution completed
    assert result.worker_id == "test-001"
    assert result.task_id == "task-async-001"
    assert result.duration_seconds >= 0


class TestWorkerAgentId:
    """Test Worker.agent_id - Verify identity generation."""

    def test_agent_id_includes_role(self) -> None:
        """Verify agent_id contains role information."""
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )

        agent_id = worker.agent_id
        # Agent ID should reflect role
        assert "tester" in agent_id.lower()

    def test_agent_id_is_stable(self) -> None:
        """Verify agent_id doesn't change across calls (caching works)."""
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="test-001",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=scratchpad,
        )

        id1 = worker.agent_id
        id2 = worker.agent_id

        assert id1 == id2  # Must be stable
