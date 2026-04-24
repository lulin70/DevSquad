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
from .context_compressor import ContextCompressor, Message, MessageType, CompressionLevel, CompressedContext


class Coordinator:
    """
    全局协调者 - 多 Agent 协作的核心编排组件

    职责:
    1. 接收用户任务，分解为可并行的 Worker 计划 (plan_task)
    2. 根据计划创建和调度 Worker 实例 (spawn_workers)
    3. 按批次执行任务，支持并行/串行混合模式 (execute_plan)
    4. 从 Scratchpad 收集所有 Worker 的结果和状态 (collect_results)
    5. 检测并解决 Worker 间的冲突 (resolve_conflicts)
    6. 生成完整的协作报告 (generate_report)

    与其他组件的关系:
    - Scratchpad: 共享黑板，Worker 间交换信息的媒介
    - Worker: 执行具体任务的 Agent 实例
    - ConsensusEngine: 解决冲突时的共识决策引擎
    - ContextCompressor: 长任务中的上下文压缩管理

    使用示例:
        coord = Coordinator(scratchpad=scratchpad)
        plan = coord.plan_task("设计系统架构", available_roles=[...])
        workers = coord.spawn_workers(plan)
        result = coord.execute_plan(plan)
        report = coord.generate_report()
    """

    def __init__(self, scratchpad: Optional[Scratchpad] = None,
                 persist_dir: Optional[str] = None,
                 enable_compression: bool = True,
                 compression_threshold: int = 100000,
                 llm_backend=None):
        """
        初始化协调者

        Args:
            scratchpad: 共享黑板实例，如不提供则自动创建
            persist_dir: Scratchpad 持久化目录
            enable_compression: 是否启用上下文压缩（长任务防溢出）
            compression_threshold: 压缩触发阈值（token数），默认100000
            llm_backend: LLM执行后端（None=MockBackend，返回prompt文本）
        """
        self.scratchpad = scratchpad or Scratchpad(persist_dir=persist_dir)
        self.consensus = ConsensusEngine()
        self.workers: Dict[str, Worker] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self.coordinator_id = f"coord-{uuid.uuid4().hex[:8]}"
        self.enable_compression = enable_compression
        self.compressor = ContextCompressor(token_threshold=compression_threshold) if enable_compression else None
        self._message_buffer: List[Message] = []
        self.llm_backend = llm_backend

    def plan_task(self, task_description: str,
                  available_roles: List[Dict[str, str]],
                  stage_id: Optional[str] = None) -> ExecutionPlan:
        """
        将用户任务分解为可并行的 Worker 执行计划

        为每个可用角色创建一个 TaskDefinition，打包为并行批次。
        当前实现为简单的一对一映射（每个角色一个任务），
        未来可扩展为智能任务拆分（如将大任务拆为子任务分配给多个角色）。

        Args:
            task_description: 用户原始任务描述
            available_roles: 可用角色列表，每项含 role_id 和 role_prompt
            stage_id: 阶段标识（可选，用于多阶段工作流）

        Returns:
            ExecutionPlan: 包含批次列表、总任务数、并行度估计

        Example:
            >>> plan = coord.plan_task(
            ...     "设计用户认证系统",
            ...     [{"role_id": "architect", "role_prompt": "..."}]
            ... )
            >>> plan.total_tasks
            1
        """
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
        """
        根据执行计划创建 Worker 实例

        遍历计划中的所有任务，为每个任务创建对应的 Worker。
        如提供 registry（PromptRegistry），会自动加载角色的 prompt 模板。
        创建的 Worker 会自动关联到本协调器的 Scratchpad。

        Args:
            plan: 执行计划（由 plan_task 生成）
            registry: 可选的 PromptRegistry 实例，用于加载角色 prompt

        Returns:
            List[Worker]: 创建的 Worker 实例列表
        """
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
                llm_backend=self.llm_backend,
            )
            self.workers[worker_id] = worker
        return list(self.workers.values())

    def execute_plan(self, plan: ExecutionPlan) -> ScheduleResult:
        """
        执行完整的协作计划

        按批次顺序执行计划中的所有任务。对于每个批次：
        - PARALLEL 模式: 并行执行所有任务
        - SEQUENTIAL 模式: 串行逐个执行
        执行过程中自动进行上下文压缩（如启用）。

        Args:
            plan: 执行计划（由 plan_task + spawn_workers 准备）

        Returns:
            ScheduleResult: 包含成功/失败统计、各 Worker 结果、耗时、错误列表
        """
        start_time = time.time()
        results = []
        errors = []

        for batch_idx, batch in enumerate(plan.batches):
            batch_results, batch_errors = self._execute_batch(batch)
            results.extend(batch_results)
            errors.extend(batch_errors)

            if self.compressor and batch_idx < len(plan.batches) - 1:
                self._buffer_worker_messages(batch_results)
                compressed = self.compressor.check_and_compress(self._message_buffer)
                if compressed.compression_level != CompressionLevel.NONE:
                    self._execution_history.append({
                        "timestamp": time.time(),
                        "compression": {
                            "level": compressed.compression_level.value,
                            "original_tokens": compressed.original_token_count,
                            "compressed_tokens": compressed.compressed_token_count,
                            "reduction_pct": round(compressed.reduction_percent, 1),
                            "summary": compressed.summary[:200],
                        },
                    })

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

    def _buffer_worker_messages(self, batch_results: List[WorkerResult]):
        for r in batch_results:
            if r.output:
                self._message_buffer.append(Message(
                    role=r.worker_id,
                    content=str(r.output)[:2000],
                    msg_type=MessageType.ASSISTANT,
                    metadata={"task_id": r.task_id, "success": r.success},
                ))

    def compress_context(self, force_level=None) -> Optional[CompressedContext]:
        """
        手动触发上下文压缩

        Args:
            force_level: 强制指定压缩级别（None=自动判断）

        Returns:
            CompressedContext: 压缩结果，含级别/原始token/压缩后token/摘要
            如未启用压缩则返回 None
        """
        if not self.compressor:
            return None
        return self.compressor.check_and_compress(self._message_buffer, force_level=force_level)

    def get_compression_stats(self) -> Optional[Dict[str, Any]]:
        """
        获取上下文压缩统计信息

        从执行历史中提取所有压缩事件的聚合统计数据，
        包括总压缩次数、平均节省率、最近一次压缩详情等。

        Returns:
            Dict[str, Any]: 统计信息字典，包含:
                - total_compressions: 总压缩次数
                - avg_reduction_pct: 平均压缩率(%)
                - last_compression: 最近一次压缩的详细信息
                - total_original_tokens: 原始token总数
                - total_compressed_tokens: 压缩后token总数
            如未启用压缩则返回 None

        Example:
            >>> stats = coord.get_compression_stats()
            >>> if stats:
            ...     print(f"平均节省 {stats['avg_reduction_pct']}%")
        """
        if not self.compressor:
            return None
        compression_events = [
            e["compression"] for e in self._execution_history
            if "compression" in e
        ]
        if not compression_events:
            return {
                "total_compressions": 0,
                "avg_reduction_pct": 0.0,
                "last_compression": None,
                "total_original_tokens": 0,
                "total_compressed_tokens": 0,
            }
        total_original = sum(e.get("original_tokens", 0) for e in compression_events)
        total_compressed = sum(e.get("compressed_tokens", 0) for e in compression_events)
        avg_reduction = (
            sum(e.get("reduction_pct", 0) for e in compression_events) / len(compression_events)
        )
        return {
            "total_compressions": len(compression_events),
            "avg_reduction_pct": round(avg_reduction, 1),
            "last_compression": compression_events[-1],
            "total_original_tokens": total_original,
            "total_compressed_tokens": total_compressed,
        }

    def get_session_memory(self, category=None, limit=50):
        """
        获取会话记忆（从 ContextCompressor 的 SessionMemory 中提取）

        Args:
            category: 记忆类别过滤（可选）
            limit: 返回条数上限

        Returns:
            List[Dict]: 提取的记忆条目列表
        """

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
        """
        从 Scratchpad 收集所有 Worker 的执行结果和共享状态

        汇总当前会话中的所有协作数据，包括：
        - Scratchpad 全局摘要和统计
        - 各类型的条目计数（发现/决策/冲突）
        - 所有 Worker 的待处理通知（跨Worker消息）

        Returns:
            Dict[str, Any]: 结果集合，包含:
                - coordinator_id: 协调器唯一标识
                - scratchpad: Scratchpad 文本摘要
                - scratchpad_stats: 详细统计（按类型/状态/Worker分布）
                - findings_count: 发现条目数
                - decisions_count: 决策条目数
                - conflicts_count: 冲突条目数
                - notifications: 待处理通知列表 (TaskNotification)
                - workers: 当前活跃 Worker ID 列表
        """
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
        """
        检测并解决 Scratchpad 中的所有活跃冲突

        对每个 CONFLICT 类型的条目发起共识投票流程：
        1. 通过 ConsensusEngine 创建提案（含4个选项：接受A/接受B/合并/升级人工）
        2. 收集所有 Worker 的投票
        3. 调用 reach_consensus() 生成最终决策
        4. 根据决策结果更新冲突条目状态为 RESOLVED

        Returns:
            List[ConsensusRecord]: 共识记录列表，每条包含:
                - topic: 冲突主题
                - outcome: 最终决策结果 (APPROVED/REJECTED/TIE)
                - final_decision: 决策描述文本
                - votes_for/against/abstain: 各选项票数

        Note:
            此方法会修改 Scratchpad 中冲突条目的状态。
            解决后的条目会被标记为 RESOLVED 并附加解决方案说明。
        """
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
        """
        生成完整的协作会话报告（Markdown格式）

        汇聚所有协作组件的数据，生成结构化的 Markdown 报告，
        包含以下章节：
        - 协作概要（协调器ID、参与Worker、耗时）
        - Scratchpad 概况（发现/决策/冲突统计）
        - Worker 间消息通知（如有）
        - 共识决策记录（如有）

        Returns:
            str: Markdown 格式的完整报告文本

        Example:
            >>> report = coord.generate_report()
            >>> print(report)
            # 多角色协作报告
            **协调器ID**: coord-a1b2c3d4
            **参与Worker**: architect-abc123, tester-def456
            ...
        """
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
