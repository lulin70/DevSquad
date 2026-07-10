"""运行状态管理：跟踪自主迭代的进度。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    """自主迭代运行状态。"""

    IDLE = "idle"
    PLANNING = "planning"
    DEVELOPING = "developing"
    VERIFYING = "verifying"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    PAUSED = "paused"  # 等待人类确认


@dataclass
class RunState:
    """单次自主迭代的运行状态。"""

    run_id: str
    objective: str
    status: RunStatus = RunStatus.IDLE
    current_iteration: int = 0
    max_iterations: int = 20
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_phases: list[str] = field(default_factory=list)
    failed_phases: list[str] = field(default_factory=list)
    checkpoint_sha: str = ""  # SHA256 校验值，用于断点续跑
    notes: list[str] = field(default_factory=list)
    error: str = ""
    loop_report: Any = None  # LoopRunReport，运行结束后填充

    def update_status(self, status: RunStatus) -> None:
        """更新状态。"""
        self.status = status
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def increment_iteration(self) -> int:
        """递增迭代次数。"""
        self.current_iteration += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self.current_iteration

    def add_note(self, note: str) -> None:
        """添加备注。"""
        self.notes.append(f"[{datetime.now(timezone.utc).isoformat()}] {note}")
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_phase_completed(self, phase: str) -> None:
        """标记阶段完成。"""
        if phase not in self.completed_phases:
            self.completed_phases.append(phase)

    def mark_phase_failed(self, phase: str) -> None:
        """标记阶段失败。"""
        if phase not in self.failed_phases:
            self.failed_phases.append(phase)

    @property
    def is_terminal(self) -> bool:
        """是否为终态（不可继续）。"""
        return self.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED)

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self.status in (
            RunStatus.PLANNING,
            RunStatus.DEVELOPING,
            RunStatus.VERIFYING,
            RunStatus.FIXING,
        )

    @property
    def can_resume(self) -> bool:
        """是否可断点续跑。"""
        return self.status == RunStatus.PAUSED and not self.is_terminal

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "status": self.status.value,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_phases": self.completed_phases,
            "failed_phases": self.failed_phases,
            "checkpoint_sha": self.checkpoint_sha,
            "notes": self.notes,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RunState:
        """从字典反序列化。"""
        return cls(
            run_id=data["run_id"],
            objective=data["objective"],
            status=RunStatus(data.get("status", "idle")),
            current_iteration=data.get("current_iteration", 0),
            max_iterations=data.get("max_iterations", 20),
            started_at=data.get("started_at", ""),
            updated_at=data.get("updated_at", ""),
            completed_phases=data.get("completed_phases", []),
            failed_phases=data.get("failed_phases", []),
            checkpoint_sha=data.get("checkpoint_sha", ""),
            notes=data.get("notes", []),
            error=data.get("error", ""),
        )
