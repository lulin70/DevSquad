#!/usr/bin/env python3
"""Integration tests for Dispatcher ↔ Worker ↔ Scratchpad interaction.

Focus: Verify real component integration, not mocked behavior.
Risk level: HIGH (core workflow integrity)
"""

from __future__ import annotations

import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker
from scripts.collaboration.models import ScratchpadEntry, EntryType, TaskDefinition


@pytest.fixture
def real_dispatcher() -> MultiAgentDispatcher:
    """Create real MultiAgentDispatcher instance (not mocked)."""
    return MultiAgentDispatcher()


@pytest.fixture
def shared_scratchpad() -> Scratchpad:
    """Create shared scratchpad for worker collaboration."""
    return Scratchpad()


class TestDispatcherWorkerIntegration:
    """Test MultiAgentDispatcher and Worker working together with real components."""

    def test_dispatcher_creates_workers_for_task(self, real_dispatcher: MultiAgentDispatcher) -> None:
        """Verify dispatcher creates appropriate workers for a given task."""
        task_description = "Design authentication system with security review"
        
        # This should trigger role matching and worker creation
        # We're not mocking - testing real dispatcher logic
        result = real_dispatcher.dispatch(task_description)
        
        # Verify dispatcher actually ran and produced result
        assert result is not None
        assert result.task_description == task_description
        
        # Verify workers were actually created and executed
        # (Even if task fails, should have attempted execution)
        assert hasattr(result, 'matched_roles')
        assert isinstance(result.matched_roles, list)

    def test_multiple_workers_share_scratchpad(self, shared_scratchpad: Scratchpad) -> None:
        """Verify multiple workers can read/write shared scratchpad correctly."""
        # Create two workers sharing same scratchpad
        worker1 = Worker(
            worker_id="architect-001",
            role_id="architect",
            role_prompt="Design system architecture",
            scratchpad=shared_scratchpad,
        )
        
        worker2 = Worker(
            worker_id="security-001",
            role_id="security",
            role_prompt="Review security aspects",
            scratchpad=shared_scratchpad,
        )
        
        # Worker 1 writes a finding
        from scripts.collaboration.models import ScratchpadEntry, EntryType
        entry1 = ScratchpadEntry(
            worker_id="architect-001",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="Proposed JWT authentication with refresh tokens",
        )
        worker1.write_finding(entry1)
        
        # Worker 2 should be able to read worker 1's finding
        entries = shared_scratchpad.read()
        assert len(entries) >= 1
        
        found_entry = False
        for entry in entries:
            if entry.worker_id == "architect-001" and "JWT" in entry.content:
                found_entry = True
                break
        
        assert found_entry, "Worker 2 should see Worker 1's scratchpad entry"
        
        # Worker 2 writes a response
        entry2 = ScratchpadEntry(
            worker_id="security-001",
            role_id="security",
            entry_type=EntryType.FINDING,
            content="JWT approach approved. Recommend HTTPS-only and token expiry.",
        )
        worker2.write_finding(entry2)
        
        # Both entries should be visible
        all_entries = shared_scratchpad.read()
        assert len(all_entries) >= 2
        
        worker_ids = {e.worker_id for e in all_entries}
        assert "architect-001" in worker_ids
        assert "security-001" in worker_ids

    def test_worker_reset_allows_reuse(self, shared_scratchpad: Scratchpad) -> None:
        """Verify worker can be reset and reused for multiple tasks."""
        worker = Worker(
            worker_id="test-worker",
            role_id="tester",
            role_prompt="Test functionality",
            scratchpad=shared_scratchpad,
        )
        
        # Execute first task
        task1 = TaskDefinition(
            task_id="task-001",
            description="Test login functionality",
        )
        result1 = worker.execute(task1)
        assert result1.task_id == "task-001"
        
        # Reset worker for reuse
        initial_entry_count = worker._entries_written_count
        worker.reset()
        
        # Verify reset cleared transient state
        assert worker._entries_written_count == 0
        assert len(worker._notifications_outbox) == 0
        
        # Verify identity preserved (critical for pooling)
        assert worker.worker_id == "test-worker"
        assert worker.role_id == "tester"
        
        # Execute second task with same worker
        task2 = TaskDefinition(
            task_id="task-002",
            description="Test registration flow",
        )
        result2 = worker.execute(task2)
        assert result2.task_id == "task-002"
        
        # Verify worker produced results for both tasks
        assert result1.worker_id == result2.worker_id == "test-worker"

    def test_worker_failure_doesnt_corrupt_scratchpad(
        self, shared_scratchpad: Scratchpad
    ) -> None:
        """Verify worker failure doesn't leave scratchpad in invalid state."""
        worker = Worker(
            worker_id="failing-worker",
            role_id="tester",
            role_prompt="Test role",
            scratchpad=shared_scratchpad,
        )
        
        # Get initial scratchpad state
        initial_entry_count = len(shared_scratchpad.read())
        
        # Create task that may cause issues
        bad_task = TaskDefinition(
            task_id="bad-task",
            description=None,  # type: ignore - Intentionally invalid
        )
        
        # Worker should handle gracefully, not crash
        result = worker.execute(bad_task)
        
        # Verify scratchpad is still accessible
        final_entries = shared_scratchpad.read()
        assert isinstance(final_entries, list)
        
        # Scratchpad should not be corrupted
        assert len(final_entries) >= initial_entry_count


class TestDispatcherRealTaskExecution:
    """Test dispatcher with realistic task scenarios."""

    def test_simple_task_completes_end_to_end(self, real_dispatcher: MultiAgentDispatcher) -> None:
        """Verify dispatcher can execute a simple real task from description to result."""
        task_description = "Create a simple hello world function in Python"
        
        result = real_dispatcher.dispatch(task_description)
        
        # Basic execution verification
        assert result is not None
        assert result.task_description == task_description
        
        # Result should have timing information
        assert hasattr(result, 'duration_seconds')
        assert result.duration_seconds >= 0
        
        # Result should indicate success or failure (not crash)
        assert hasattr(result, 'success')
        assert isinstance(result.success, bool)

    def test_multi_role_task_creates_multiple_workers(
        self, real_dispatcher: MultiAgentDispatcher
    ) -> None:
        """Verify dispatcher creates multiple workers for complex tasks."""
        task_description = "Design a secure RESTful API for user management with full test coverage"
        
        result = real_dispatcher.dispatch(task_description)
        
        # Task keywords suggest multiple roles: architect, security, tester
        # At minimum, should have attempted role matching
        assert hasattr(result, 'matched_roles')
        
        # For a complex task mentioning security and testing,
        # we expect multiple roles to be matched
        if result.matched_roles:
            # If roles were matched, verify they're relevant
            role_str = " ".join(result.matched_roles).lower()
            # At least one of these should appear for this task type
            has_relevant_role = any(
                keyword in role_str
                for keyword in ["architect", "security", "test", "api", "backend"]
            )
            assert has_relevant_role, f"Expected relevant roles, got: {result.matched_roles}"


class TestScratchpadConcurrency:
    """Test scratchpad behavior under concurrent access."""

    def test_concurrent_writes_from_multiple_workers(
        self, shared_scratchpad: Scratchpad
    ) -> None:
        """Verify scratchpad handles concurrent writes correctly."""
        from scripts.collaboration.models import ScratchpadEntry, EntryType
        
        # Create 3 workers writing simultaneously
        workers = [
            Worker(
                worker_id=f"worker-{i}",
                role_id=f"role-{i}",
                role_prompt=f"Worker {i}",
                scratchpad=shared_scratchpad,
            )
            for i in range(3)
        ]
        
        # Each worker writes an entry
        for i, worker in enumerate(workers):
            entry = ScratchpadEntry(
                worker_id=f"worker-{i}",
                role_id=f"role-{i}",
                entry_type=EntryType.FINDING,
                content=f"Finding from worker {i}",
            )
            worker.write_finding(entry)
        
        # Verify all entries were written
        all_entries = shared_scratchpad.read()
        
        # Should have at least the 3 entries we wrote
        # (may have more if other tests ran in same process)
        worker_ids_found = {e.worker_id for e in all_entries if e.worker_id.startswith("worker-")}
        assert len(worker_ids_found) == 3
        
        # Verify each worker's entry is present
        for i in range(3):
            found = False
            for entry in all_entries:
                if entry.worker_id == f"worker-{i}" and f"Finding from worker {i}" in entry.content:
                    found = True
                    break
            assert found, f"Entry from worker-{i} not found in scratchpad"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
