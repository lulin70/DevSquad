"""Handoff 阶段：生成工作项并调用 Generator 执行。"""

from __future__ import annotations

from typing import Any

logger = __import__("logging").getLogger(__name__)


class HandoffAdapter:
    """生成工作项并执行。

    可注入外部 dispatcher（如 DevSquad Coordinator）执行实际工作。
    """

    def __init__(self, dispatcher: Any = None) -> None:
        self._dispatcher = dispatcher

    def dispatch(self, discovery_result: dict[str, Any], iter_index: int) -> dict[str, Any]:
        tasks = discovery_result.get("tasks", [])
        if not tasks:
            return {"status": "skipped", "output": "", "iter_index": iter_index}

        if self._dispatcher is not None:
            try:
                result = self._dispatcher.dispatch(discovery_result["focus"])
                return {
                    "status": "dispatched",
                    "output": getattr(result, "summary", str(result)),
                    "tasks": tasks,
                    "iter_index": iter_index,
                }
            except Exception as exc:
                logger.warning("Dispatch failed: %s", exc)
                return {
                    "status": "error",
                    "output": "",
                    "error": str(exc),
                    "iter_index": iter_index,
                }

        return {
            "status": "mock",
            "output": f"Processed tasks: {tasks}",
            "tasks": tasks,
            "iter_index": iter_index,
        }
