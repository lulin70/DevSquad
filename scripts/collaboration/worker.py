#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worker - 工作者执行框架

每个 Worker 是一个独立的 Agent 实例，执行具体任务，
通过 Scratchpad 与其他 Worker 交换信息。
"""

import time
import sys
import os
from typing import List, Optional, Any, Dict

from .models import (
    TaskDefinition,
    WorkerResult,
    TaskNotification,
    ScratchpadEntry,
    EntryType,
    EntryStatus,
)
from .scratchpad import Scratchpad


class Worker:
    def __init__(self, worker_id: str, role_id: str, role_prompt: str,
                 scratchpad: Scratchpad):
        self.worker_id = worker_id
        self.role_id = role_id
        self.role_prompt = role_prompt
        self.scratchpad = scratchpad
        self._notifications_outbox: List[TaskNotification] = []
        self._entries_written_count = 0

    def execute(self, task: TaskDefinition) -> WorkerResult:
        start_time = time.time()
        try:
            context = self._build_execution_context(task)

            finding = self._do_work(context)
            if finding:
                entry = ScratchpadEntry(
                    worker_id=self.worker_id,
                    role_id=self.role_id,
                    entry_type=EntryType.FINDING,
                    content=finding,
                    confidence=0.7,
                    tags=[task.task_id, task.stage_id or "", "auto"],
                )
                self.write_finding(entry)

            output = {
                "worker_id": self.worker_id,
                "role_id": self.role_id,
                "task_id": task.task_id,
                "finding_summary": finding[:500] if finding else "",
            }

            return WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=True,
                output=output,
                scratchpad_entries_written=self._entries_written_count,
                notifications_sent=len(self._notifications_outbox),
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            return WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    def read_scratchpad(self, query: str = "",
                         since=None, limit: int = 20) -> List[ScratchpadEntry]:
        return self.scratchpad.read(
            query=query, since=since, limit=limit,
        )

    def write_finding(self, finding: ScratchpadEntry) -> str:
        finding.worker_id = self.worker_id
        finding.role_id = self.role_id
        eid = self.scratchpad.write(finding)
        self._entries_written_count += 1
        return eid

    def write_question(self, question: str, to_roles: List[str] = None,
                       tags: List[str] = None) -> str:
        entry = ScratchpadEntry(
            worker_id=self.worker_id,
            role_id=self.role_id,
            entry_type=EntryType.QUESTION,
            content=question,
            confidence=0.5,
            tags=tags or [],
        )
        eid = self.scratchpad.write(entry)
        self._entries_written_count += 1

        if to_roles:
            notification = TaskNotification(
                from_worker=self.worker_id,
                to_workers=to_roles,
                notification_type="question",
                summary=question[:100],
                details=question,
                action_required="请回答此问题",
            )
            self.send_notification(notification)
        return eid

    def write_conflict(self, conflict: str, conflicting_entry_id: str,
                        reason: str = "") -> str:
        entry = ScratchpadEntry(
            worker_id=self.worker_id,
            role_id=self.role_id,
            entry_type=EntryType.CONFLICT,
            content=f"{conflict}\n\n[冲突原因] {reason}",
            confidence=0.8,
            tags=["conflict", conflicting_entry_id],
        )
        eid = self.scratchpad.write(entry)
        self._entries_written_count += 1
        return eid

    def send_notification(self, notification: TaskNotification):
        self._notifications_outbox.append(notification)

    def get_pending_notifications(self) -> List[TaskNotification]:
        notifications = list(self._notifications_outbox)
        self._notifications_outbox.clear()
        return notifications

    def vote_on_proposal(self, proposal_id: str, decision: bool,
                          reason: str = "", weight: float = None) -> Dict[str, Any]:
        from .models import Vote, ROLE_WEIGHTS
        w = weight or ROLE_WEIGHTS.get(self.role_id, 1.0)
        vote = Vote(
            voter_id=self.worker_id,
            voter_role=self.role_id,
            decision=decision,
            reason=reason,
            weight=w,
        )
        return {"proposal_id": proposal_id, "vote": vote}

    def _build_execution_context(self, task: TaskDefinition) -> Dict[str, Any]:
        related = self.read_scratchpad(
            query=task.description[:50], limit=10,
        )
        return {
            "task": task,
            "role_prompt": self.role_prompt,
            "related_findings": [f.content for f in related[:5]],
            "worker_id": self.worker_id,
        }

    def _do_work(self, context: Dict[str, Any]) -> str:
        task = context["task"]
        prompt = context["role_prompt"]
        related = context.get("related_findings", [])

        work_instruction = (
            f"=== 任务 ===\n"
            f"任务ID: {task.task_id}\n"
            f"描述: {task.description}\n"
            f"角色: {context['role_prompt'][:200]}...\n\n"
        )

        if related:
            work_instruction += (
                f"=== 相关发现（来自其他Worker） ===\n" +
                "\n".join(f"- {r[:150]}" for r in related) +
                "\n\n"
            )

        work_instruction += (
            f"请基于以上信息完成你的工作。\n"
            f"输出你的核心发现（1-3条关键结论）。"
        )
        return work_instruction


class WorkerFactory:
    @staticmethod
    def create(worker_id: str, role_id: str, role_prompt: str,
               scratchpad: Scratchpad) -> Worker:
        return Worker(worker_id, role_id, role_prompt, scratchpad)

    @staticmethod
    def create_batch(workers_config: List[Dict[str, str]],
                     scratchpad: Scratchpad) -> List[Worker]:
        workers = []
        for cfg in workers_config:
            w = WorkerFactory.create(
                worker_id=cfg.get("worker_id", f"w-{len(workers)}"),
                role_id=cfg["role_id"],
                role_prompt=cfg.get("role_prompt", ""),
                scratchpad=scratchpad,
            )
            workers.append(w)
        return workers
