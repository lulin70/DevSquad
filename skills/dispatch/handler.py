"""Dispatch Skill — One-click multi-agent task orchestration."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from skills.registry import BaseSkill

_dispatcher = None


def _get_dispatcher():
    global _dispatcher
    if _dispatcher is None:
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        _dispatcher = MultiAgentDispatcher()
    return _dispatcher


class DispatchSkill(BaseSkill):
    name = "dispatch"
    description = "Multi-agent task dispatch: submit a task → auto-match roles → parallel execution → structured report"
    version = "3.6.0"

    def run(self, task: str, roles: list = None, mode: str = "auto",
            dry_run: bool = False) -> dict:
        d = _get_dispatcher()
        result = d.dispatch(
            task_description=task,
            roles=roles,
            mode=mode,
            dry_run=dry_run,
        )
        timing = result.timing if hasattr(result, 'timing') and isinstance(result.timing, dict) else {}
        return {
            "success": result.success,
            "matched_roles": result.matched_roles,
            "worker_results": result.worker_results,
            "report": getattr(result, 'report', None),
            "intent_match": result.intent_match,
            "five_axis_result": result.five_axis_result,
            "timing": {"total_s": round(timing.get("total", 0), 3)},
            "status": "success" if result.success else "failed",
        }

    def quick(self, task: str, **kwargs) -> dict:
        return self.run(task, **kwargs)

    def roles_info(self) -> list:
        from scripts.collaboration.role_matcher import RoleMatcher
        rm = RoleMatcher()
        return [{"id": r.role_id, "name": r.name, "keywords": r.keywords[:5]} for r in rm.roles]
