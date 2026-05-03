#!/usr/bin/env python3
import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskCompletionResult:
    task_id: str
    is_completed: bool
    completion_rate: float = 0.0
    total_subtasks: int = 0
    completed_subtasks: int = 0
    failed_subtasks: int = 0
    pending_subtasks: int = 0
    details: List[Dict] = field(default_factory=list)
    summary: str = ""


class TaskCompletionChecker:
    """
    Task completion checker for DevSquad dispatch results.

    Features:
    1. Check WorkerResult success/failure status
    2. Track dispatch execution progress
    3. Support checkpoint-based resume
    4. Generate completion reports
    """

    def __init__(self, storage_path: str = "./task_progress"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.storage_path / "progress.json"
        self.progress = self._load_progress()

    def _load_progress(self) -> Dict:
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load progress: %s", e)
        return self._create_empty_progress()

    def _create_empty_progress(self) -> Dict:
        return {
            "last_update": datetime.now().isoformat(),
            "dispatches": {},
        }

    def _save_progress(self):
        try:
            self.progress["last_update"] = datetime.now().isoformat()
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save progress: %s", e)

    def check_dispatch_result(self, dispatch_result) -> TaskCompletionResult:
        """
        Check completion status of a DispatchResult.

        Args:
            dispatch_result: DispatchResult from MultiAgentDispatcher.dispatch()

        Returns:
            TaskCompletionResult with detailed completion info
        """
        worker_results = getattr(dispatch_result, 'worker_results', [])
        task_id = getattr(dispatch_result, 'task_description', 'unknown')[:50]

        total = len(worker_results)
        completed = sum(1 for w in worker_results if w.get('success'))
        failed = sum(1 for w in worker_results if not w.get('success'))
        pending = 0

        completion_rate = (completed / total * 100) if total > 0 else 0.0
        is_completed = completed == total and total > 0

        details = []
        for wr in worker_results:
            wr_detail = {
                'role': wr.get('role_id', wr.get('role', 'unknown')),
                'role_name': wr.get('role_name', wr.get('role', 'unknown')),
                'success': wr.get('success', False),
                'error': wr.get('error'),
                'output_preview': (str(wr.get('output', ''))[:100] if wr.get('output') else None),
            }

            # P0-2: Apply VerificationGate (P0-2)
            try:
                from scripts.collaboration.verification_gate import get_shared_gate
                if not hasattr(self, '_vgate'):
                    self._vgate = get_shared_gate()
                ctx = self._vgate.build_context_from_worker_result(wr)
                gate_result = self._vgate.check(ctx)
                if not gate_result.passed:
                    wr_detail['verification'] = {
                        'passed': False,
                        'verdict': gate_result.verdict,
                        'red_flags': [rf.description for rf in gate_result.red_flags],
                        'missing_evidence': [e.description for e in gate_result.missing_evidence],
                    }
                    # Track blocked workers for consensus awareness
                    if not hasattr(self, '_blocked_workers'):
                        self._blocked_workers = set()
                    self._blocked_workers.add(
                        wr.get('role_id', wr.get('role', 'unknown'))
                    )
                else:
                    wr_detail['verification'] = {'passed': True, 'verdict': 'APPROVE'}
            except Exception as ve:
                logger.debug("VerificationGate error: %s", ve)

            details.append(wr_detail)

        summary_parts = []
        if is_completed:
            summary_parts.append(f"All {total} workers completed successfully.")
        else:
            summary_parts.append(f"{completed}/{total} workers succeeded, {failed} failed.")

        result = TaskCompletionResult(
            task_id=task_id,
            is_completed=is_completed,
            completion_rate=round(completion_rate, 2),
            total_subtasks=total,
            completed_subtasks=completed,
            failed_subtasks=failed,
            pending_subtasks=pending,
            details=details,
            summary=" ".join(summary_parts),
        )

        self._record_dispatch(task_id, result)
        return result

    def _record_dispatch(self, task_id: str, result: TaskCompletionResult):
        self.progress["dispatches"][task_id] = {
            "is_completed": result.is_completed,
            "completion_rate": result.completion_rate,
            "total": result.total_subtasks,
            "completed": result.completed_subtasks,
            "failed": result.failed_subtasks,
            "checked_at": datetime.now().isoformat(),
        }
        self._save_progress()

    def check_schedule_result(self, schedule_result) -> TaskCompletionResult:
        """
        Check completion status of a ScheduleResult from Coordinator.

        Args:
            schedule_result: ScheduleResult from Coordinator.execute_plan()

        Returns:
            TaskCompletionResult with detailed completion info
        """
        total = schedule_result.total_tasks
        completed = schedule_result.completed_tasks
        failed = schedule_result.failed_tasks
        pending = total - completed - failed

        completion_rate = (completed / total * 100) if total > 0 else 0.0
        is_completed = completed == total and total > 0

        details = []
        for wr in schedule_result.results:
            details.append({
                'role': wr.worker_id,
                'success': wr.success,
                'error': wr.error,
                'duration': wr.duration_seconds,
            })

        summary_parts = []
        if is_completed:
            summary_parts.append(f"All {total} tasks completed successfully.")
        else:
            summary_parts.append(f"{completed}/{total} tasks succeeded, {failed} failed.")

        if schedule_result.errors:
            summary_parts.append(f"Errors: {len(schedule_result.errors)}")

        return TaskCompletionResult(
            task_id=schedule_result.results[0].task_id if schedule_result.results else "unknown",
            is_completed=is_completed,
            completion_rate=round(completion_rate, 2),
            total_subtasks=total,
            completed_subtasks=completed,
            failed_subtasks=failed,
            pending_subtasks=max(0, pending),
            details=details,
            summary=" ".join(summary_parts),
        )

    def get_dispatch_history(self) -> Dict:
        return self.progress.get("dispatches", {})

    def get_completion_summary(self) -> str:
        dispatches = self.progress.get("dispatches", {})
        if not dispatches:
            return "No dispatch history found."

        total = len(dispatches)
        completed = sum(1 for d in dispatches.values() if d.get("is_completed"))
        avg_rate = sum(d.get("completion_rate", 0) for d in dispatches.values()) / total

        lines = [
            f"# Task Completion Summary",
            f"",
            f"- Total dispatches: {total}",
            f"- Fully completed: {completed}",
            f"- Average completion rate: {avg_rate:.1f}%",
            f"",
        ]

        for task_id, data in dispatches.items():
            status = "✅" if data.get("is_completed") else "❌"
            lines.append(f"- {status} {task_id}: {data.get('completion_rate', 0):.1f}%")

        return "\n".join(lines)

    def is_task_completed(self, task_id: str) -> bool:
        dispatch_data = self.progress.get("dispatches", {}).get(task_id)
        return dispatch_data.get("is_completed", False) if dispatch_data else False

    def reset_progress(self):
        self.progress = self._create_empty_progress()
        self._save_progress()
