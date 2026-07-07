"""Persistence 阶段：统一记忆读写。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CycleResult, LoopEvent


class UnifiedMemory:
    """统一记忆层，基于文件持久化。

    存储事件和单轮结果，支持历史查询。
    """

    def __init__(self, storage_dir: str = ".devsquad_loop") -> None:
        self._storage_dir = Path(storage_dir)
        self._events: list[LoopEvent] = []
        self._cycles: list[dict[str, Any]] = []
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def persist_event(self, event: LoopEvent) -> None:
        self._events.append(event)

    def load_history(self, _objective: str) -> list[dict[str, Any]]:
        return list(self._cycles)

    def persist_cycle(self, cycle: CycleResult) -> None:
        self._cycles.append({
            "iter_index": cycle.iter_index,
            "verification_passed": cycle.verification_passed,
            "verification_errors": cycle.verification_errors,
            "discovery": cycle.discovery,
            "handoff": cycle.handoff,
        })

    def save_to_disk(self, objective: str) -> Path:
        filepath = self._storage_dir / f"loop_{hash(objective) % 100000}.json"
        data = {
            "objective": objective,
            "events": [
                {
                    "type": e.event_type.value,
                    "phase": e.phase,
                    "iter": e.iter_index,
                    "payload": e.payload,
                }
                for e in self._events
            ],
            "cycles": self._cycles,
        }
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return filepath

    def clear(self) -> None:
        self._events.clear()
        self._cycles.clear()
