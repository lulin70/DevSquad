#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coordinator - 全局协调者

管理多 Worker 协作的核心组件：
1. 任务分解为可并行的 Worker 计划
2. 创建和调度 Workers
3. 收集结果和共享状态
4. 解决冲突和达成共识
5. 生成最终协作报告
"""

import time
import uuid
from typing import Dict, List, Optional, Any, Tuple

from .models import (
    EntryType,
    TaskDefinition,
    ExecutionPlan,
    TaskBatch,
    BatchMode,
    ScheduleResult,
    WorkerResult,
    ConsensusRecord,
    DecisionOutcome,
)
from .scratchpad import Scratchpad
from .worker import Worker, WorkerFactory
from .consensus import ConsensusEngine


class Coordinator:
    def __init__(self, scratchpad: Optional[Scratchpad] = None,
                 persist_dir: Optional[str] = None):
        self.scratchpad = scratchpad or Scratchpad(persist_dir=persist_dir)
        self.consensus = ConsensusEngine()
        self.workers: Dict[str, Worker] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self.coordinator_id = f"coord-{uuid.uuid4().hex[:8]}"

    def plan_task(self, task_description: str,
                  available_roles: List[Dict[str, str]],
                  stage_id: Optional[str] = None) -> ExecutionPlan:
        tasks = []
        for role_cfg in available_roles:
            task = TaskDefinition(
                description=task_description,
                role_id=role_cfg["role_id"],
                stage_id=stage_id,
                is_read_only=True,
            )
            tasks.append(task)

        parallel_batch = TaskBatch(
            mode=BatchMode.PARALLEL,
            tasks=tasks,
            max_concurrency=len(tasks),
        )

        plan = ExecutionPlan(
            batches=[parallel_batch],
            total_tasks=len(tasks),
            estimated_parallelism=1.0 if len(tasks) > 1 else 0.0,
        )
        return plan

    def spawn_workers(self, plan: ExecutionPlan,
                     registry=None) -> List[Worker]:
        self.workers.clear()
        all_tasks = []
        for batch in plan.batches:
            all_tasks.extend(batch.tasks)

        for task in all_tasks:
            worker_id = f"{task.role_id}-{uuid.uuid4().hex[:6]}"
            role_prompt = ""
            if registry:
                from prompts.registry import PromptRegistry
                if isinstance(registry, PromptRegistry):
                    info = registry.get_role_prompt(task.role_id)
                    if info:
                        role_prompt = info.prompt_content[:2000]

            worker = WorkerFactory.create(
                worker_id=worker_id,
                role_id=task.role_id,
                role_prompt=role_prompt,
                scratchpad=self.scratchpad,
            )
            self.workers[worker_id] = worker
        return list(self.workers.values())

    def execute_plan(self, plan: ExecutionPlan) -> ScheduleResult:
        start_time = time.time()
        results = []
        errors = []

        for batch in plan.batches:
            batch_results, batch_errors = self._execute_batch(batch)
            results.extend(batch_results)
            errors.extend(batch_errors)

        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.success)

        result = ScheduleResult(
            success=len(errors) == 0,
            total_tasks=sum(len(b.tasks) for b in plan.batches),
            completed_tasks=success_count,
            failed_tasks=len(errors),
            results=results,
            duration_seconds=duration,
            errors=errors,
        )

        self._record_execution(result)
        return result

    def _execute_batch(self, batch: TaskBatch) -> Tuple[List[WorkerResult], List[str]]:
        results = []
        errors = []

        if batch.mode == BatchMode.PARALLEL:
            results = self._execute_parallel(batch)
        else:
            for task in batch.tasks:
                try:
                    worker = self._get_worker_for_task(task)
                    if worker:
                        r = worker.execute(task)
                        results.append(r)
                except Exception as e:
                    errors.append(f"Task {task.task_id} failed: {e}")

        return results, errors

    def _execute_parallel(self, batch: TaskBatch) -> List[WorkerResult]:
        results = []
        for task in batch.tasks[:batch.max_concurrency]:
            try:
                worker = self._get_worker_for_task(task)
                if worker:
                    r = worker.execute(task)
                    results.append(r)
            except Exception as e:
                results.append(WorkerResult(
                    worker_id="unknown", task_id=task.task_id,
                    success=False, error=str(e))
                )
        return results

    def _get_worker_for_task(self, task: TaskDefinition) -> Optional[Worker]:
        for wid, w in self.workers.items():
            if w.role_id == task.role_id and not any(
                existing_r.task_id == task.task_id
                for existing_r in getattr(w, '_last_results', [])
            ):
                return w
        return None

    def collect_results(self) -> Dict[str, Any]:
        scratchpad_summary = self.scratchpad.get_summary()
        stats = self.scratchpad.get_stats()

        findings = self.scratchpad.read(entry_type=EntryType.FINDING)
        decisions = self.scratchpad.read(entry_type=EntryType.DECISION)
        conflicts = self.scratchpad.get_conflicts()

        notifications = []
        for w in self.workers.values():
            notifications.extend(w.get_pending_notifications())

        return {
            "coordinator_id": self.coordinator_id,
            "scratchpad": scratchpad_summary,
            "scratchpad_stats": stats,
            "findings_count": len(findings),
            "decisions_count": len(decisions),
            "conflicts_count": len(conflicts),
            "notifications": notifications,
            "workers": list(self.workers.keys()),
        }

    def resolve_conflicts(self) -> List[ConsensusRecord]:
        conflicts = self.scratchpad.get_conflicts()
        resolutions = []

        for conflict in conflicts:
            proposal = self.consensus.create_proposal(
                topic=f"解决冲突: {conflict.content[:80]}",
                proposer_id=self.coordinator_id,
                content=f"冲突详情: {conflict.content}",
                options=["接受A", "接受B", "合并方案", "升级人工"],
            )

            for wid, w in self.workers.items():
                vote_result = w.vote_on_proposal(proposal.proposal_id, decision=True,
                                                   reason="默认赞成待讨论")
                vote_obj = vote_result.get("vote", vote_result)
                self.consensus.cast_vote(proposal.proposal_id, vote_obj)

            record = self.consensus.reach_consensus(proposal.proposal_id)
            resolutions.append(record)

            if record.outcome != DecisionOutcome.APPROVED:
                self.scratchpad.resolve(conflict.entry_id,
                                         resolution=f"[共识:{record.outcome.value}] {record.final_decision}")
            else:
                self.scratchpad.resolve(conflict.entry_id,
                                         resolution=f"已通过共识解决")

        return resolutions

    def generate_report(self) -> str:
        collection = self.collect_results()
        lines = [
            "# 多角色协作报告",
            "",
            f"**协调器ID**: {collection['coordinator_id']}",
            f"**参与Worker**: {', '.join(collection['workers'])}",
            f"**总耗时**: {self._get_last_duration():.1f}s",
            "",
            "## Scratchpad 概况",
            collection["scratchpad"],
            "",
            f"- 发现: {collection['findings_count']} 条",
            f"- 决策: {collection['decisions_count']} 条",
            f"- 冲突: {collection['conflicts_count']} 条",
        ]

        if collection["notifications"]:
            lines.append("\n## Worker 间消息")
            for n in collection["notifications"][:10]:
                lines.append(f"- **{n.from_worker}** → {', '.join(n.to_workers)}: {n.summary}")

        consensus_records = self.consensus.get_all_records()
        if consensus_records:
            lines.append("\n## 共识记录")
            for cr in consensus_records:
                icon = "✅" if cr.outcome == DecisionOutcome.APPROVED else \
                       "❌" if cr.outcome == DecisionOutcome.REJECTED else \
                       "⚠️"
                lines.append(f"- [{icon}] {cr.topic}: {cr.outcome.value}")

        return "\n".join(lines)

    def _record_execution(self, result: ScheduleResult):
        self._execution_history.append({
            "timestamp": time.time(),
            "result": {
                "success": result.success,
                "total": result.total_tasks,
                "completed": result.completed_tasks,
                "failed": result.failed_tasks,
                "duration": result.duration_seconds,
            },
        })

    def _get_last_duration(self) -> float:
        if self._execution_history:
            return self._execution_history[-1]["result"]["duration"]
        return 0.0
