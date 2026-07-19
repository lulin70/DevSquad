"""Unit tests for CheckpointManager atomic write semantics (P1-5).

Verifies that save_checkpoint / save_handoff / save_lifecycle_state use
write-to-temp + atomic-rename, so a crash mid-write never leaves a
corrupted/truncated file visible to readers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.collaboration.checkpoint_manager import (
    Checkpoint,
    CheckpointManager,
    CheckpointStatus,
    HandoffDocument,
)


@pytest.fixture
def manager(tmp_path: Path) -> CheckpointManager:
    """Real CheckpointManager backed by a tmp_path storage directory."""
    return CheckpointManager(storage_path=str(tmp_path))


def _make_checkpoint(task_id: str = "task-1") -> Checkpoint:
    return Checkpoint(
        task_id=task_id,
        step_id="step-1",
        step_name="Test Step",
        agent_id="agent-test",
        status=CheckpointStatus.ACTIVE,
        completed_steps=["s0"],
        remaining_steps=["s1", "s2"],
        progress_percentage=33.3,
    )


def _make_handoff() -> HandoffDocument:
    return HandoffDocument(
        task_id="task-handoff",
        from_agent="architect",
        to_agent="coder",
        completed_work=["Spec written", "Architecture drafted"],
        current_state={"phase": "spec_done"},
        next_steps=["Implement module", "Add type hints"],
        pending_issues=["Need to confirm API surface"],
        important_notes=["Use dataclass", "Avoid asyncio"],
        context_for_next={"module": "frob"},
        accumulated_knowledge={"decision": "use-postgres"},
    )


# ---------------------------------------------------------------------
# save_checkpoint: atomic semantics
# ---------------------------------------------------------------------


def test_save_checkpoint_writes_valid_json(manager: CheckpointManager) -> None:
    """save_checkpoint produces a JSON file that can be loaded back."""
    cp = _make_checkpoint()
    assert manager.save_checkpoint(cp) is True

    loaded = manager.load_checkpoint(cp.checkpoint_id)
    assert loaded is not None
    assert loaded.task_id == "task-1"
    assert loaded.checkpoint_hash == cp.checkpoint_hash


def test_save_checkpoint_uses_atomic_replace(manager: CheckpointManager) -> None:
    """save_checkpoint calls _atomic_write_json (not open(... 'w') directly).

    We patch _atomic_write_json to assert it is invoked, and to verify
    the payload passed to it is a serializable dict containing the
    integrity hash.
    """
    cp = _make_checkpoint()
    captured: list[tuple[Path, dict]] = []

    def fake_write(self: CheckpointManager, target: Path, data: dict) -> None:
        captured.append((target, data))
        # Verify data is JSON-serializable (real write would fail otherwise).
        json.dumps(data)

    with patch.object(CheckpointManager, "_atomic_write_json", fake_write):
        assert manager.save_checkpoint(cp) is True

    assert len(captured) == 1
    target_path, payload = captured[0]
    assert target_path.name == f"{cp.checkpoint_id}.json"
    assert payload["checkpoint_hash"] == cp.checkpoint_hash
    assert payload["task_id"] == "task-1"


def test_save_checkpoint_no_tmp_file_left_on_success(manager: CheckpointManager) -> None:
    """After a successful save_checkpoint, no .tmp files remain in the directory."""
    cp = _make_checkpoint()
    assert manager.save_checkpoint(cp) is True

    tmp_files = list(manager.checkpoints_dir.glob("*.tmp"))
    assert tmp_files == [], f"Unexpected .tmp files left behind: {tmp_files}"


def test_save_checkpoint_failure_leaves_no_corrupt_file(
    manager: CheckpointManager, tmp_path: Path
) -> None:
    """If json.dump raises mid-write, the target file is not created/truncated.

    We force a TypeError by passing a non-serializable object via a patched
    _compute_hash that injects a sentinel into the dict. save_checkpoint
    should return False and leave no .json or .tmp file behind.
    """
    cp = _make_checkpoint()

    original_to_dict = cp.to_dict

    def poisoned_to_dict() -> dict:
        d = original_to_dict()
        d["__poison"] = object()  # not JSON-serializable
        return d

    with patch.object(Checkpoint, "to_dict", lambda _self: poisoned_to_dict()):
        result = manager.save_checkpoint(cp)

    assert result is False
    # The target json file should not exist (atomic write failed).
    target = manager.checkpoints_dir / f"{cp.checkpoint_id}.json"
    assert not target.exists()
    # And no leftover .tmp files.
    tmp_files = list(manager.checkpoints_dir.glob("*.tmp"))
    assert tmp_files == [], f"Leftover .tmp files after failure: {tmp_files}"


# ---------------------------------------------------------------------
# save_handoff: atomic semantics
# ---------------------------------------------------------------------


def test_save_handoff_writes_both_json_and_md(manager: CheckpointManager) -> None:
    """save_handoff produces a .json and a .md file."""
    handoff = _make_handoff()
    assert manager.save_handoff(handoff) is True

    json_path = manager.handoffs_dir / f"{handoff.handoff_id}.json"
    md_path = manager.handoffs_dir / f"{handoff.handoff_id}.md"
    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["from_agent"] == "architect"
    assert data["to_agent"] == "coder"


def test_save_handoff_no_tmp_files(manager: CheckpointManager) -> None:
    """After save_handoff, no .tmp files remain."""
    handoff = _make_handoff()
    assert manager.save_handoff(handoff) is True

    tmp_files = list(manager.handoffs_dir.glob("*.tmp"))
    assert tmp_files == []


# ---------------------------------------------------------------------
# save_lifecycle_state: atomic semantics
# ---------------------------------------------------------------------


def test_save_lifecycle_state_writes_json(manager: CheckpointManager) -> None:
    """save_lifecycle_state produces a valid JSON file."""
    assert (
        manager.save_lifecycle_state(
            task_id="task-lc",
            current_phase="build",
            phase_states={"build": "in_progress"},
            completed_phases=["spec", "plan"],
            mode="FULL",
        )
        is True
    )

    state_path = manager.storage_path / "lifecycle" / "task-lc_lifecycle.json"
    assert state_path.exists()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["task_id"] == "task-lc"
    assert data["current_phase"] == "build"


def test_save_lifecycle_state_no_tmp_files(manager: CheckpointManager) -> None:
    """After save_lifecycle_state, no .tmp files remain."""
    manager.save_lifecycle_state(
        task_id="task-lc2",
        current_phase="test",
        phase_states={"test": "pending"},
        completed_phases=["spec"],
        mode="FULL",
    )

    lifecycle_dir = manager.storage_path / "lifecycle"
    tmp_files = list(lifecycle_dir.glob("*.tmp"))
    assert tmp_files == []


# ---------------------------------------------------------------------
# Direct _atomic_write_json / _atomic_write_text unit tests
# ---------------------------------------------------------------------


def test_atomic_write_json_replaces_existing_file(manager: CheckpointManager, tmp_path: Path) -> None:
    """Atomic write overwrites an existing file completely."""
    target = tmp_path / "subdir" / "target.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"old": true}', encoding="utf-8")

    manager._atomic_write_json(target, {"new": True, "count": 42})

    data = json.loads(target.read_text(encoding="utf-8"))
    assert data == {"new": True, "count": 42}
    assert "old" not in data


def test_atomic_write_json_creates_parent_dirs(manager: CheckpointManager, tmp_path: Path) -> None:
    """Atomic write creates missing parent directories."""
    target = tmp_path / "deep" / "nested" / "path" / "file.json"
    manager._atomic_write_json(target, {"ok": True})

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_atomic_write_json_no_tmp_left_on_success(manager: CheckpointManager, tmp_path: Path) -> None:
    """No .tmp files remain after a successful atomic write."""
    target = tmp_path / "ok.json"
    manager._atomic_write_json(target, {"x": 1})

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []


def test_atomic_write_json_cleans_up_tmp_on_failure(manager: CheckpointManager, tmp_path: Path) -> None:
    """If json.dump raises, the .tmp file is unlinked and target is untouched."""

    class NotSerializable:
        pass

    target = tmp_path / "preexisting.json"
    target.write_text('{"original": true}', encoding="utf-8")

    with pytest.raises(TypeError):
        manager._atomic_write_json(target, {"bad": NotSerializable()})

    # Original file content preserved.
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data == {"original": True}
    # No leftover .tmp files.
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []


def test_atomic_write_text_overwrites_and_cleans_tmp(manager: CheckpointManager, tmp_path: Path) -> None:
    """_atomic_write_text overwrites existing content and leaves no .tmp files."""
    target = tmp_path / "notes.md"
    target.write_text("old content", encoding="utf-8")

    manager._atomic_write_text(target, "# New Heading\n\nBody text.\n")

    assert target.read_text(encoding="utf-8") == "# New Heading\n\nBody text.\n"
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []


def test_atomic_write_json_uses_os_replace(manager: CheckpointManager, tmp_path: Path) -> None:
    """Verify os.replace is called (the atomic primitive)."""
    target = tmp_path / "atom.json"
    called = False
    real_replace = os.replace

    def spy_replace(src: str, dst: str) -> None:
        nonlocal called
        called = True
        real_replace(src, dst)

    with patch("scripts.collaboration.checkpoint_manager.os.replace", spy_replace):
        manager._atomic_write_json(target, {"k": "v"})

    assert called, "os.replace was not invoked — atomic write is broken"
    assert json.loads(target.read_text(encoding="utf-8")) == {"k": "v"}
