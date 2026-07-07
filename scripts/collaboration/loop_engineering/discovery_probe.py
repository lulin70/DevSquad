"""Discovery 阶段：发现本轮该做什么。"""

from __future__ import annotations

from typing import Any


class DiscoveryProbe:
    """发现本轮工作项。

    根据目标、迭代历史和记忆，生成本轮该做的工作。
    """

    def discover(self, objective: str, iter_index: int, memory: Any) -> dict[str, Any]:
        history = memory.load_history(objective) if memory else []
        completed_items = {
            item for entry in history for item in entry.get("completed_items", [])
        }

        if iter_index == 0:
            return {
                "focus": f"Initial analysis for: {objective}",
                "tasks": ["analyze_objective", "identify_scope"],
                "iter_index": iter_index,
            }

        last_cycle = history[-1] if history else {}
        last_errors = last_cycle.get("verification_errors", [])

        if last_errors:
            return {
                "focus": f"Fix errors from iteration {iter_index - 1}",
                "tasks": ["fix_errors"],
                "errors_to_fix": last_errors,
                "iter_index": iter_index,
            }

        remaining = [t for t in ["implement", "test", "review"] if t not in completed_items]
        if not remaining:
            return {
                "focus": "All tasks completed",
                "tasks": [],
                "iter_index": iter_index,
                "done": True,
            }

        return {
            "focus": f"Continue with: {', '.join(remaining)}",
            "tasks": remaining[:1],
            "iter_index": iter_index,
        }
