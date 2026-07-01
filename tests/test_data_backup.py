#!/usr/bin/env python3
"""P0 data persistence / backup-recovery checks."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

from scripts.collaboration.checkpoint_manager import (
    Checkpoint,
    CheckpointManager,
    CheckpointStatus,
    HandoffDocument,
)
from scripts.history_manager import HistoryManager


class TestHistoryManagerPersistence:
    def test_metrics_snapshot_round_trip(self, tmp_path: Path):
        db_path = tmp_path / "history.db"
        history = HistoryManager(db_path=str(db_path))
        history.save_metrics_snapshot({
            "total_phases": 10,
            "completed_phases": 7,
            "completion_rate": 70.0,
            "custom_field": "custom_value",
        })
        rows = history.get_metrics_history(hours=1, include_custom=True)
        assert len(rows) == 1
        assert rows[0]["completion_rate"] == pytest.approx(70.0)
        assert rows[0]["custom_data"] == {"custom_field": "custom_value"}
        history.close()

    def test_api_log_round_trip(self, tmp_path: Path):
        history = HistoryManager(db_path=str(tmp_path / "history.db"))
        history.log_api_request("POST", "/api/v1/dispatch", 200, 42.0)
        stats = history.get_api_stats(hours=1)
        assert stats["total_requests"] == 1
        history.close()

    def test_lifecycle_event_round_trip(self, tmp_path: Path):
        history = HistoryManager(db_path=str(tmp_path / "history.db"))
        history.save_lifecycle_event("phase_complete", phase_id="P1")
        events = history.get_lifecycle_history(hours=1, phase_id="P1")
        assert len(events) == 1
        history.close()

    def test_database_size_and_cleanup(self, tmp_path: Path):
        history = HistoryManager(db_path=str(tmp_path / "history.db"))
        history.save_metrics_snapshot({"completion_rate": 50.0})
        history.log_api_request("GET", "/health", 200, 1.0)
        size_info = history.get_database_size()
        assert size_info["total_records"] == 2
        deleted = history.cleanup_old_data(retention_days=0)
        assert deleted["metrics_snapshots"] == 1
        assert deleted["api_logs"] == 1
        history.close()

    def test_closed_connection_raises(self, tmp_path: Path):
        history = HistoryManager(db_path=str(tmp_path / "history.db"))
        history.close()
        with pytest.raises(sqlite3.Error):
            _ = history._conn

    def test_reopen_existing_database(self, tmp_path: Path):
        db_path = tmp_path / "history.db"
        history = HistoryManager(db_path=str(db_path))
        history.save_metrics_snapshot({"completion_rate": 99.0})
        history.close()
        history2 = HistoryManager(db_path=str(db_path))
        rows = history2.get_metrics_history(hours=24)
        assert len(rows) == 1
        history2.close()


class TestCheckpointManagerPersistence:
    def test_save_and_load_checkpoint(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        cp = Checkpoint(task_id="task-1", step_name="s1", progress_percentage=0.33)
        assert manager.save_checkpoint(cp) is True
        loaded = manager.load_checkpoint(cp.checkpoint_id)
        assert loaded is not None
        assert loaded.progress_percentage == pytest.approx(0.33)

    def test_checkpoint_integrity_detects_tampering(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        cp = Checkpoint(task_id="task-1", step_name="s1")
        manager.save_checkpoint(cp)
        cp_path = manager._get_checkpoint_path(cp.checkpoint_id)
        data = json.loads(cp_path.read_text(encoding="utf-8"))
        data["task_id"] = "tampered"
        cp_path.write_text(json.dumps(data), encoding="utf-8")
        assert manager.load_checkpoint(cp.checkpoint_id) is None

    def test_list_and_delete_checkpoints(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        manager.create_checkpoint_from_dispatch(
            "task-1", "s1", "agent-1", ["a"], ["b"]
        )
        cp2 = manager.create_checkpoint_from_dispatch(
            "task-2", "s1", "agent-1", ["a"], ["b"]
        )
        assert len(manager.list_checkpoints()) == 2
        assert len(manager.list_checkpoints(task_id="task-1")) == 1
        assert manager.delete_checkpoint(cp2.checkpoint_id) is True
        assert manager.delete_checkpoint(cp2.checkpoint_id) is False
        assert len(manager.list_checkpoints()) == 1

    def test_cleanup_expired_checkpoints(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        cp = Checkpoint(task_id="task-1", step_name="old")
        manager.save_checkpoint(cp)
        cp_path = manager._get_checkpoint_path(cp.checkpoint_id)
        old_mtime = time.time() - 48 * 3600
        os.utime(cp_path, (old_mtime, old_mtime))
        assert manager.cleanup_expired_checkpoints(max_age_hours=24) == 1
        assert len(manager.list_checkpoints()) == 0

    def test_path_traversal_validation(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        with pytest.raises(ValueError):
            manager._get_checkpoint_path("../etc/passwd")
        with pytest.raises(ValueError):
            manager._get_handoff_path("foo/bar")

    def test_handoff_save_and_load(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        handoff = HandoffDocument(
            task_id="task-1", from_agent="architect", to_agent="coder"
        )
        assert manager.save_handoff(handoff) is True
        loaded = manager.load_handoff(handoff.handoff_id)
        assert loaded is not None
        assert loaded.from_agent == "architect"
        assert len(manager.get_task_handoffs("task-1")) == 1

    def test_lifecycle_state_round_trip(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        assert manager.save_lifecycle_state(
            task_id="task-1",
            current_phase="P2",
            phase_states={"P1": "completed"},
            completed_phases=["P1"],
            mode="shortcut",
        ) is True
        state = manager.load_lifecycle_state("task-1")
        assert state is not None
        assert state["current_phase"] == "P2"
        assert len(manager.list_lifecycle_states()) == 1
        assert manager.delete_lifecycle_state("task-1") is True
        assert manager.load_lifecycle_state("task-1") is None

    def test_checkpoint_from_dispatch_progress(self, tmp_path: Path):
        manager = CheckpointManager(storage_path=str(tmp_path))
        cp = manager.create_checkpoint_from_dispatch(
            "task-1", "design", "architect",
            ["discover", "design"], ["implement", "test"],
            context={"goal": "ship"}, outputs={"schema": "users"},
        )
        assert cp.status == CheckpointStatus.ACTIVE
        assert cp.progress_percentage == pytest.approx(0.5)
