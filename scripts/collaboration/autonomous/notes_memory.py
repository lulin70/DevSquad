"""断点续跑记忆：基于文件持久化运行状态。

支持 SHA256 校验确保状态完整性，崩溃后可恢复。
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .run_state import RunState

logger = logging.getLogger(__name__)


class NotesMemory:
    """断点续跑记忆，基于 JSON 文件持久化。

    Usage:
        memory = NotesMemory(storage_dir="/tmp/autonomous")
        memory.save(state)
        restored = memory.load(run_id)
    """

    def __init__(self, storage_dir: str = ".devsquad_autonomous") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: RunState) -> Path:
        """保存运行状态到磁盘，并计算 SHA256 校验值。

        checksum 计算基于「除 checkpoint_sha 外的所有字段」，确保
        save() 和 verify_checksum() 使用一致的输入。
        """
        data = state.to_dict()
        data.pop("checkpoint_sha", "")  # 排除 checksum 本身
        data_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
        state.checkpoint_sha = hashlib.sha256(data_str.encode()).hexdigest()

        # 重新序列化包含 checksum
        data = state.to_dict()
        filepath = self._storage_dir / f"run_{state.run_id}.json"
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return filepath

    def load(self, run_id: str) -> RunState | None:
        """从磁盘加载运行状态。"""
        filepath = self._storage_dir / f"run_{run_id}.json"
        if not filepath.exists():
            return None

        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return RunState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to load run state %s: %s", run_id, e)
            return None

    def verify_checksum(self, state: RunState) -> bool:
        """验证状态的 SHA256 校验值。"""
        if not state.checkpoint_sha:
            return False

        data = state.to_dict()
        data.pop("checkpoint_sha", "")  # 与 save() 保持一致
        data_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
        computed_sha = hashlib.sha256(data_str.encode()).hexdigest()
        return state.checkpoint_sha == computed_sha

    def list_runs(self) -> list[str]:
        """列出所有运行 ID。"""
        return [
            f.stem.replace("run_", "")
            for f in self._storage_dir.glob("run_*.json")
        ]

    def delete(self, run_id: str) -> bool:
        """删除运行状态。"""
        filepath = self._storage_dir / f"run_{run_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def list_resumable(self) -> list[RunState]:
        """列出所有可断点续跑的运行。"""
        runs: list[RunState] = []
        for run_id in self.list_runs():
            state = self.load(run_id)
            if state and state.can_resume:
                runs.append(state)
        return runs

    def wrap_for_loop(self) -> Any:
        """适配为 LoopKernel 可用的 UnifiedMemory。

        NotesMemory 关注运行状态持久化，LoopKernel 的 UnifiedMemory 关注事件/周期持久化。
        本方法返回一个共享存储目录的 UnifiedMemory 实例。
        """
        from ..loop_engineering.unified_memory import UnifiedMemory

        return UnifiedMemory(storage_dir=str(self._storage_dir / "loop"))
