#!/usr/bin/env python3
import hashlib
import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CheckpointStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Checkpoint:
    checkpoint_id: str = field(default_factory=lambda: f"cp-{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    step_id: str = ""
    step_name: str = ""
    agent_id: str = ""
    status: CheckpointStatus = CheckpointStatus.ACTIVE
    completed_steps: list[str] = field(default_factory=list)
    remaining_steps: list[str] = field(default_factory=list)
    progress_percentage: float = 0.0
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str | None = None
    checkpoint_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the checkpoint to a JSON-compatible dictionary.

        Returns:
            Dict containing all checkpoint fields with enum values converted
            to their string representation.
        """
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "step_name": self.step_name,
            "agent_id": self.agent_id,
            "status": self.status.value if isinstance(self.status, CheckpointStatus) else self.status,
            "completed_steps": self.completed_steps,
            "remaining_steps": self.remaining_steps,
            "progress_percentage": self.progress_percentage,
            "context_snapshot": self.context_snapshot,
            "variables": self.variables,
            "outputs": self.outputs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "checkpoint_hash": self.checkpoint_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Reconstruct a Checkpoint instance from a serialized dictionary.

        Args:
            data: Dict produced by `to_dict`. The `status` field may be a
                string and will be converted back to a `CheckpointStatus`
                enum value; invalid values fall back to `ACTIVE`.

        Returns:
            A new Checkpoint instance populated from `data`.
        """
        data_copy = dict(data)
        if isinstance(data_copy.get("status"), str):
            try:
                data_copy["status"] = CheckpointStatus(data_copy["status"])
            except ValueError:
                data_copy["status"] = CheckpointStatus.ACTIVE
        return cls(**data_copy)


@dataclass
class HandoffDocument:
    handoff_id: str = field(default_factory=lambda: f"hoff-{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    from_agent: str = ""
    to_agent: str = ""
    completed_work: list[str] = field(default_factory=list)
    current_state: dict[str, Any] = field(default_factory=dict)
    next_steps: list[str] = field(default_factory=list)
    pending_issues: list[str] = field(default_factory=list)
    important_notes: list[str] = field(default_factory=list)
    context_for_next: dict[str, Any] = field(default_factory=dict)
    accumulated_knowledge: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    handoff_reason: str = "task_completed"
    confidence: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffDocument":
        """Reconstruct a HandoffDocument from a serialized dictionary.

        Args:
            data: Dict containing handoff fields (typically produced by
                `dataclasses.asdict`).

        Returns:
            A new HandoffDocument instance populated from `data`.
        """
        return cls(**data)

    def to_markdown(self) -> str:
        """Render the handoff document as a human-readable Markdown string.

        Returns:
            Markdown-formatted string containing basic info, completed work,
            current state (as JSON), next steps, pending issues, and notes.
        """
        md = "# Task Handoff Document\n\n"
        md += "## Basic Info\n"
        md += f"- **Handoff ID**: {self.handoff_id}\n"
        md += f"- **Task ID**: {self.task_id}\n"
        md += f"- **Time**: {self.created_at}\n"
        md += f"- **Reason**: {self.handoff_reason}\n"
        md += f"- **Confidence**: {self.confidence:.0%}\n\n"
        md += "## From -> To\n"
        md += f"- **From**: {self.from_agent}\n"
        md += f"- **To**: {self.to_agent}\n\n---\n\n"
        md += "## Completed Work\n"
        for i, work in enumerate(self.completed_work, 1):
            md += f"{i}. {work}\n"
        md += f"\n## Current State\n\n```json\n{json.dumps(self.current_state, indent=2, ensure_ascii=False)}\n```\n"
        md += "\n## Next Steps\n"
        for i, step in enumerate(self.next_steps, 1):
            md += f"{i}. {step}\n"
        if self.pending_issues:
            md += "\n## Pending Issues\n"
            for i, issue in enumerate(self.pending_issues, 1):
                md += f"{i}. {issue}\n"
        if self.important_notes:
            md += "\n## Important Notes\n"
            for note in self.important_notes:
                md += f"- {note}\n"
        return md


class CheckpointManager:
    """
    Checkpoint manager for long-running task state persistence.

    Features:
    1. Periodic task state saving (like git commits)
    2. Recovery from any checkpoint
    3. Automatic handoff document generation
    4. Data integrity verification (SHA256)
    5. Expired checkpoint auto-cleanup
    """

    def __init__(self, storage_path: str = "./checkpoints"):
        self.storage_path = Path(storage_path)
        self.checkpoints_dir = self.storage_path / "checkpoints"
        self.handoffs_dir = self.storage_path / "handoffs"
        self._file_lock = threading.Lock()
        self._ensure_directories()

    def _ensure_directories(self):
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.handoffs_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, data: dict[str, Any]) -> str:
        data_for_hash = {k: v for k, v in data.items() if k != "checkpoint_hash"}
        json_str = json.dumps(data_for_hash, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def _validate_id(self, id_str: str) -> None:
        if ".." in id_str or "/" in id_str or "\\" in id_str:
            raise ValueError(f"Invalid ID (path traversal detected): {id_str}")

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        self._validate_id(checkpoint_id)
        path = self.checkpoints_dir / f"{checkpoint_id}.json"
        if not path.resolve().is_relative_to(self.checkpoints_dir.resolve()):
            raise ValueError(f"Path traversal detected: {checkpoint_id}")
        return path

    def _get_handoff_path(self, handoff_id: str) -> Path:
        self._validate_id(handoff_id)
        path = self.handoffs_dir / f"{handoff_id}.json"
        if not path.resolve().is_relative_to(self.handoffs_dir.resolve()):
            raise ValueError(f"Path traversal detected: {handoff_id}")
        return path

    def save_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Persist a checkpoint to disk with an integrity hash.

        Args:
            checkpoint: Checkpoint instance to save. Its `updated_at` and
                `checkpoint_hash` fields are updated in place before writing.

        Returns:
            True if the checkpoint was written successfully, False on
            OSError/TypeError/ValueError.
        """
        try:
            checkpoint.updated_at = datetime.now().isoformat()
            checkpoint_dict = checkpoint.to_dict()
            checkpoint.checkpoint_hash = self._compute_hash(checkpoint_dict)
            checkpoint_dict["checkpoint_hash"] = checkpoint.checkpoint_hash

            checkpoint_path = self._get_checkpoint_path(checkpoint.checkpoint_id)
            with self._file_lock, open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_dict, f, indent=2, ensure_ascii=False)

            logger.info("Checkpoint saved: %s (%.1f%%)", checkpoint.checkpoint_id, checkpoint.progress_percentage)
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Failed to save checkpoint: %s", e)
            return False

    def load_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Load and integrity-verify a checkpoint by ID.

        Args:
            checkpoint_id: Unique checkpoint identifier.

        Returns:
            Reconstructed Checkpoint if found and hash matches, None if the
            file is missing, hash verification fails, or parsing errors occur.
        """
        try:
            checkpoint_path = self._get_checkpoint_path(checkpoint_id)
            if not checkpoint_path.exists():
                logger.warning("Checkpoint not found: %s", checkpoint_id)
                return None

            with open(checkpoint_path, encoding="utf-8") as f:
                data = json.load(f)

            checkpoint = Checkpoint.from_dict(data)
            computed_hash = self._compute_hash({k: v for k, v in data.items() if k != "checkpoint_hash"})
            if computed_hash != checkpoint.checkpoint_hash:
                logger.warning("Checkpoint integrity check failed: %s", checkpoint_id)
                return None

            return checkpoint
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning("Failed to load checkpoint: %s", e)
            return None

    def get_latest_checkpoint(self, task_id: str) -> Checkpoint | None:
        """Return the most recently modified checkpoint for a given task.

        Args:
            task_id: Task identifier to filter checkpoints by.

        Returns:
            The newest Checkpoint by file mtime, or None if no checkpoints
            exist for the task or loading fails.
        """
        try:
            task_checkpoints = []
            for cp_path in self.checkpoints_dir.glob("*.json"):
                with open(cp_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("task_id") == task_id:
                        task_checkpoints.append((cp_path.stat().st_mtime, Checkpoint.from_dict(data)))

            if not task_checkpoints:
                return None

            latest = sorted(task_checkpoints, key=lambda x: x[0], reverse=True)[0][1]
            return latest
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning("Failed to get latest checkpoint: %s", e)
            return None

    def list_checkpoints(self, task_id: str | None = None) -> list[Checkpoint]:
        """List checkpoints, optionally filtered by task.

        Args:
            task_id: Optional task identifier. When None, all checkpoints
                are returned.

        Returns:
            List of Checkpoints sorted by `created_at` descending. Returns
            an empty list on errors.
        """
        try:
            checkpoints = []
            for cp_path in self.checkpoints_dir.glob("*.json"):
                with open(cp_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if task_id is None or data.get("task_id") == task_id:
                        checkpoints.append(Checkpoint.from_dict(data))
            checkpoints.sort(key=lambda x: x.created_at, reverse=True)
            return checkpoints
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning("Failed to list checkpoints: %s", e)
            return []

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint file by ID.

        Args:
            checkpoint_id: Unique checkpoint identifier.

        Returns:
            True if the file existed and was deleted, False if it did not
            exist or deletion failed.
        """
        try:
            checkpoint_path = self._get_checkpoint_path(checkpoint_id)
            if checkpoint_path.exists():
                checkpoint_path.unlink()
                return True
            return False
        except OSError as e:
            logger.warning("Failed to delete checkpoint: %s", e)
            return False

    def cleanup_expired_checkpoints(self, max_age_hours: int = 24) -> int:
        """Remove checkpoint files older than `max_age_hours`.

        Args:
            max_age_hours: Maximum age in hours. Checkpoints whose file
                mtime is older than this cutoff are deleted.

        Returns:
            Number of checkpoint files removed. Returns 0 on errors or when
            nothing qualifies.
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            cleaned_count = 0
            for cp_path in self.checkpoints_dir.glob("*.json"):
                if cp_path.stat().st_mtime < cutoff_time.timestamp():
                    cp_path.unlink()
                    cleaned_count += 1
            if cleaned_count > 0:
                logger.info("Cleaned %d expired checkpoints", cleaned_count)
            return cleaned_count
        except OSError as e:
            logger.warning("Failed to cleanup expired checkpoints: %s", e)
            return 0

    def save_handoff(self, handoff: HandoffDocument) -> bool:
        """Persist a handoff document as JSON and Markdown.

        Args:
            handoff: HandoffDocument instance to save. Both a `.json` file
                (via `dataclasses.asdict`) and a `.md` file (via
                `to_markdown`) are written.

        Returns:
            True if both files were written successfully, False on
            OSError/TypeError/ValueError.
        """
        try:
            handoff_path = self._get_handoff_path(handoff.handoff_id)
            with self._file_lock:
                with open(handoff_path, "w", encoding="utf-8") as f:
                    json.dump(asdict(handoff), f, indent=2, ensure_ascii=False)

                md_path = handoff_path.with_suffix(".md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(handoff.to_markdown())

            logger.info("Handoff saved: %s -> %s", handoff.from_agent, handoff.to_agent)
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Failed to save handoff: %s", e)
            return False

    def load_handoff(self, handoff_id: str) -> HandoffDocument | None:
        """Load a handoff document by ID.

        Args:
            handoff_id: Unique handoff identifier.

        Returns:
            Reconstructed HandoffDocument if found, None if missing or
            parsing fails.
        """
        try:
            handoff_path = self._get_handoff_path(handoff_id)
            if not handoff_path.exists():
                return None
            with open(handoff_path, encoding="utf-8") as f:
                data = json.load(f)
            return HandoffDocument.from_dict(data)
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning("Failed to load handoff: %s", e)
            return None

    def get_task_handoffs(self, task_id: str) -> list[HandoffDocument]:
        """List all handoff documents for a given task.

        Args:
            task_id: Task identifier to filter handoffs by.

        Returns:
            List of HandoffDocuments sorted by `created_at` ascending.
            Returns an empty list on errors.
        """
        try:
            handoffs = []
            for hf_path in self.handoffs_dir.glob("*.json"):
                with open(hf_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("task_id") == task_id:
                        handoffs.append(HandoffDocument.from_dict(data))
            handoffs.sort(key=lambda x: x.created_at)
            return handoffs
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning("Failed to get task handoffs: %s", e)
            return []

    def create_checkpoint_from_dispatch(
        self,
        task_id: str,
        step_name: str,
        agent_id: str,
        completed_steps: list[str],
        remaining_steps: list[str],
        context: dict[str, Any] = None,
        outputs: dict[str, Any] = None,
    ) -> Checkpoint:
        """Create and persist a checkpoint from dispatch progress.

        Args:
            task_id: Unique task identifier.
            step_name: Human-readable name of the current step.
            agent_id: Identifier of the agent producing this checkpoint.
            completed_steps: List of completed step identifiers.
            remaining_steps: List of remaining step identifiers.
            context: Optional context snapshot dict.
            outputs: Optional outputs dict produced so far.

        Returns:
            The newly created and saved Checkpoint instance.
        """
        total = len(completed_steps) + len(remaining_steps)
        progress = len(completed_steps) / total if total > 0 else 0.0

        checkpoint = Checkpoint(
            task_id=task_id,
            step_id=f"step-{len(completed_steps) + 1}",
            step_name=step_name,
            agent_id=agent_id,
            status=CheckpointStatus.ACTIVE,
            completed_steps=completed_steps,
            remaining_steps=remaining_steps,
            progress_percentage=progress,
            context_snapshot=context or {},
            outputs=outputs or {},
        )
        self.save_checkpoint(checkpoint)
        return checkpoint

    # ========== Lifecycle State Management (Plan C Integration) ==========

    def save_lifecycle_state(
        self,
        task_id: str,
        current_phase: str | None,
        phase_states: dict[str, str],
        completed_phases: list[str],
        mode: str = "shortcut",
        gate_results: dict[str, dict] = None,
        metadata: dict[str, Any] = None,
    ) -> bool:
        """
        Save lifecycle state for Plan C unified architecture.

        Integrates with LifecycleProtocol and UnifiedGateEngine to persist
        lifecycle progress across sessions.

        Args:
            task_id: Unique task identifier
            current_phase: Current active phase ID (e.g., "P8")
            phase_states: Dict mapping phase_id → state string
            completed_phases: List of completed phase IDs
            mode: Lifecycle mode (shortcut/full/custom)
            gate_results: Optional dict of recent gate check results
            metadata: Additional metadata

        Returns:
            True if saved successfully
        """
        try:
            lifecycle_dir = self.storage_path / "lifecycle"
            lifecycle_dir.mkdir(parents=True, exist_ok=True)

            state_data = {
                "task_id": task_id,
                "current_phase": current_phase,
                "phase_states": phase_states,
                "completed_phases": completed_phases,
                "mode": mode,
                "gate_results": gate_results or {},
                "metadata": metadata or {},
                "saved_at": datetime.now().isoformat(),
                "version": "3.7.2",
            }

            state_path = lifecycle_dir / f"{task_id}_lifecycle.json"
            with self._file_lock, open(state_path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)

            logger.info(
                "Lifecycle state saved: %s (phase=%s, mode=%s)",
                task_id,
                current_phase,
                mode,
            )
            return True

        except (OSError, TypeError, ValueError) as e:
            logger.warning("Failed to save lifecycle state: %s", e)
            return False

    def load_lifecycle_state(self, task_id: str) -> dict[str, Any] | None:
        """
        Load lifecycle state for a task.

        Args:
            task_id: Unique task identifier

        Returns:
            Lifecycle state dict or None if not found
        """
        try:
            lifecycle_dir = self.storage_path / "lifecycle"
            state_path = lifecycle_dir / f"{task_id}_lifecycle.json"

            if not state_path.exists():
                logger.debug("Lifecycle state not found: %s", task_id)
                return None

            with open(state_path, encoding="utf-8") as f:
                data = json.load(f)

            logger.info("Lifecycle state loaded: %s", task_id)
            return data

        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning("Failed to load lifecycle state: %s", e)
            return None

    def list_lifecycle_states(self) -> list[dict[str, Any]]:
        """
        List all saved lifecycle states.

        Returns:
            List of lifecycle state summaries
        """
        try:
            lifecycle_dir = self.storage_path / "lifecycle"
            if not lifecycle_dir.exists():
                return []

            states = []
            for state_file in lifecycle_dir.glob("*_lifecycle.json"):
                try:
                    with open(state_file, encoding="utf-8") as f:
                        data = json.load(f)
                    states.append(
                        {
                            "task_id": data.get("task_id"),
                            "current_phase": data.get("current_phase"),
                            "mode": data.get("mode"),
                            "completed_count": len(data.get("completed_phases", [])),
                            "saved_at": data.get("saved_at"),
                        }
                    )
                except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                    logger.debug("Error reading %s: %e", state_file, e)

            states.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
            return states

        except OSError as e:
            logger.warning("Failed to list lifecycle states: %s", e)
            return []

    def delete_lifecycle_state(self, task_id: str) -> bool:
        """
        Delete lifecycle state for a task.

        Args:
            task_id: Unique task identifier

        Returns:
            True if deleted successfully
        """
        try:
            lifecycle_dir = self.storage_path / "lifecycle"
            state_path = lifecycle_dir / f"{task_id}_lifecycle.json"

            if state_path.exists():
                state_path.unlink()
                logger.info("Lifecycle state deleted: %s", task_id)
                return True

            return False

        except OSError as e:
            logger.warning("Failed to delete lifecycle state: %s", e)
            return False

    def create_checkpoint_from_lifecycle(
        self,
        task_id: str,
        protocol=None,
    ) -> Checkpoint | None:
        """
        Create a checkpoint from current lifecycle protocol state.

        This bridges the gap between LifecycleProtocol and CheckpointManager,
        allowing lifecycle state to be persisted as checkpoints.

        Args:
            task_id: Unique task identifier
            protocol: Optional LifecycleProtocol instance to extract state from

        Returns:
            Created Checkpoint or None on failure
        """
        try:
            if protocol:
                status = protocol.get_status()
                phase_states = {}
                for phase in protocol.get_all_phases():
                    state = protocol._phase_states.get(phase.phase_id, "pending")
                    phase_states[phase.phase_id] = state.value if hasattr(state, "value") else str(state)

                # Save lifecycle state first
                self.save_lifecycle_state(
                    task_id=task_id,
                    current_phase=status.current_phase,
                    phase_states=phase_states,
                    completed_phases=status.completed_phases,
                    mode=status.mode.value if hasattr(status.mode, "value") else str(status.mode),
                )

                # Create checkpoint
                checkpoint = Checkpoint(
                    task_id=task_id,
                    step_id=f"phase-{status.current_phase or 'init'}",
                    step_name=f"Lifecycle {status.mode.value.upper()}",
                    agent_id="lifecycle-protocol",
                    status=CheckpointStatus.ACTIVE,
                    completed_steps=status.completed_phases,
                    remaining_steps=[
                        p.phase_id for p in protocol.get_all_phases() if p.phase_id not in status.completed_phases
                    ],
                    progress_percentage=status.progress_percent,
                    context_snapshot={
                        "mode": status.mode.value,
                        "can_advance": status.can_advance,
                        "next_phase": status.next_phase,
                    },
                    outputs={"lifecycle_status": status.to_summary()},
                )

                self.save_checkpoint(checkpoint)
                logger.info(
                    "Created checkpoint from lifecycle: %s (%.1f%%)",
                    checkpoint.checkpoint_id,
                    checkpoint.progress_percentage,
                )
                return checkpoint

            return None

        # Broad catch needed: protocol object methods and file I/O can raise various exceptions
        except (OSError, AttributeError, TypeError, KeyError, ValueError) as e:  # noqa: BLE001
            logger.warning("Failed to create checkpoint from lifecycle: %s", e)
            return None
