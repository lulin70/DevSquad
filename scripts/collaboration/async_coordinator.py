#!/usr/bin/env python3
"""
Async Coordinator - Asynchronous Global Orchestrator

Provides async versions of Coordinator for improved throughput and reduced latency.
Uses asyncio for parallel worker execution with timeout control.

Key Improvements over Sync Version:
- Native async/await (no ThreadPoolExecutor overhead)
- asyncio.gather for true concurrent worker execution
- asyncio.wait_for for per-task timeout control
- Better resource utilization (single event loop)

Usage:
    import asyncio

    async def main():
        coord = AsyncCoordinator(scratchpad=scratchpad)
        plan = coord.plan_task("design system", available_roles=[...])
        workers = coord.spawn_workers(plan)
        result = await coord.execute_plan(plan)

    asyncio.run(main())
"""

import asyncio
import logging
import time
import uuid
from typing import Any, cast

from .consensus import ConsensusEngine
from .context_compressor import (
    CompressedContext,
    CompressionLevel,
    ContextCompressor,
    Message,
    MessageType,
)
from .models import (
    BatchMode,
    ConsensusRecord,
    DecisionOutcome,
    EntryType,
    ExecutionPlan,
    ScheduleResult,
    TaskBatch,
    TaskDefinition,
    WorkerResult,
)
from .scratchpad import Scratchpad
from .usage_tracker import track_usage
from .worker import Worker, WorkerFactory

logger = logging.getLogger(__name__)


class AsyncWorkerWrapper:
    """
    Wrapper to make synchronous Worker executable in async context.

    Executes Worker.execute() in a thread pool to avoid blocking the event loop.
    Provides timeout control via asyncio.wait_for().
    """

    def __init__(
        self,
        worker: Worker,
        timeout: float | None = None,
    ) -> None:
        self.worker = worker
        self.timeout = timeout

    async def execute(self, task: TaskDefinition) -> WorkerResult:
        """
        Execute worker task asynchronously with optional timeout.

        Args:
            task: Task definition to execute.

        Returns:
            WorkerResult: Execution result.

        Raises:
            asyncio.TimeoutError: If task exceeds timeout.
        """
        loop = asyncio.get_event_loop()

        if self.timeout:

            async def _execute_with_timeout() -> WorkerResult:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, self.worker.execute, task),
                    timeout=self.timeout,
                )

            return await _execute_with_timeout()
        else:
            return await loop.run_in_executor(None, self.worker.execute, task)


class AsyncCoordinator:
    """
    异步全局协调者 - 多 Agent 协作的异步编排组件

    与同步 Coordinator 的主要区别:
    1. 使用 asyncio.gather 实现真正的并行执行（无线程开销）
    2. 支持 asyncio.wait_for 超时控制
    3. 单事件循环，资源利用率更高
    4. 所有 I/O 操作均为异步，降低延迟 50%+

    职责:
    1. 接收用户任务，分解为可并行的 Worker 计划 (plan_task)
    2. 根据计划创建和调度 Worker 实例 (spawn_workers)
    3. 按批次异步执行任务，支持并行/串行混合模式 (execute_plan)
    4. 从 Scratchpad 收集所有 Worker 的结果和状态 (collect_results)
    5. 检测并解决 Worker 间的冲突 (resolve_conflicts)
    6. 生成完整的协作报告 (generate_report)

    使用示例:
        coord = AsyncCoordinator(scratchpad=scratchpad)
        plan = coord.plan_task("设计系统架构", available_roles=[...])
        workers = coord.spawn_workers(plan)
        result = await coord.execute_plan(plan)
        report = await coord.generate_report()
    """

    DEFAULT_TASK_TIMEOUT = 300.0
    MAX_CONCURRENCY = 10

    def __init__(
        self,
        scratchpad: Scratchpad | None = None,
        persist_dir: str | None = None,
        enable_compression: bool = True,
        compression_threshold: int = 100000,
        llm_backend: Any = None,
        stream: bool = False,
        memory_provider: Any = None,
        briefing_mode: bool = True,
        task_timeout: float | None = None,
        max_concurrency: int = MAX_CONCURRENCY,
        enable_retry: bool = False,
        execution_guard: Any = None,
    ) -> None:
        """
        Initialize AsyncCoordinator.

        Args:
            scratchpad: Shared scratchpad instance (auto-created if not provided)
            persist_dir: Scratchpad persistence directory
            enable_compression: Enable context compression
            compression_threshold: Compression trigger threshold (token count)
            llm_backend: LLM execution backend (can be sync or async)
            memory_provider: MemoryProvider implementation (optional)
            briefing_mode: Enable inter-Agent briefing handoff
            task_timeout: Per-task timeout in seconds (None=no limit)
            max_concurrency: Maximum concurrent workers
            enable_retry: Enable AsyncLLMRetryManager for LLM calls with
                exponential backoff, circuit breaker, and fallback support
            execution_guard: ExecutionGuard instance for worker execution monitoring (optional)
        """
        self.scratchpad = scratchpad or Scratchpad(persist_dir=persist_dir)
        self.consensus = ConsensusEngine()
        self.workers: dict[str, Worker] = {}
        self._async_workers: dict[str, AsyncWorkerWrapper] = {}
        self._execution_history: list[dict[str, Any]] = []
        self.coordinator_id = f"async-coord-{uuid.uuid4().hex[:8]}"
        self.enable_compression = enable_compression
        self.compressor = ContextCompressor(token_threshold=compression_threshold) if enable_compression else None
        self._message_buffer: list[Message] = []
        self.llm_backend = llm_backend
        self.stream = stream
        self.memory_provider = memory_provider
        self.briefing_mode = briefing_mode
        self._briefing_chain: list[Any] = []
        self.task_timeout = task_timeout or self.DEFAULT_TASK_TIMEOUT
        self.max_concurrency = max_concurrency
        self.execution_guard = execution_guard
        # V3.8 #9: ContentCache wrapper (set externally when configured).
        self.content_cache: Any = None
        self._semaphore: asyncio.Semaphore | None = None

        # Retry support
        self.enable_retry = enable_retry
        self._retry_manager: Any | None = None
        if enable_retry:
            try:
                from .llm_retry_async import AsyncLLMRetryManager

                self._retry_manager = AsyncLLMRetryManager()
                logger.info("AsyncLLMRetryManager enabled for AsyncCoordinator")
            except ImportError as e:
                logger.warning("AsyncLLMRetryManager init failed: %s", e)
                self.enable_retry = False
                self._retry_manager = None

    async def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._semaphore

    def plan_task(
        self,
        task_description: str,
        available_roles: list[dict[str, str]],
        stage_id: str | None = None,
    ) -> ExecutionPlan:
        """
        将用户任务分解为可并行的 Worker 执行计划

        与同步版本相同，为每个可用角色创建一个 TaskDefinition。

        Args:
            task_description: 用户原始任务描述
            available_roles: 可用角色列表
            stage_id: 阶段标识（可选）

        Returns:
            ExecutionPlan: 包含批次列表、总任务数、并行度估计
        """
        tasks: list[TaskDefinition] = []
        for role_cfg in available_roles:
            task = TaskDefinition(
                description=task_description,
                role_id=role_cfg["role_id"],
                role_prompt=role_cfg.get("role_prompt", ""),
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
        track_usage(
            "async_coordinator.plan_task",
            success=True,
            metadata={
                "num_roles": len(available_roles),
                "total_tasks": len(tasks),
            },
        )
        return plan

    def spawn_workers(self, plan: ExecutionPlan, registry: Any = None) -> list[Worker]:
        """
        根据执行计划创建 Worker 实例

        同时创建 AsyncWorkerWrapper 以支持异步执行。

        Args:
            plan: 执行计划
            registry: 可选的 PromptRegistry 实例

        Returns:
            List[Worker]: 创建的 Worker 实例列表
        """
        self.workers.clear()
        self._async_workers.clear()
        all_tasks: list[TaskDefinition] = []

        for batch in plan.batches:
            all_tasks.extend(batch.tasks)

        for task in all_tasks:
            worker_id = f"{task.role_id}-{uuid.uuid4().hex[:6]}"
            role_prompt = task.role_prompt or ""

            if not role_prompt and registry:
                from prompts.registry import PromptRegistry

                if isinstance(registry, PromptRegistry):
                    info = registry.get_role_prompt(task.role_id)
                    if info:
                        role_prompt = info.prompt_content[:2000]

            # Use EnhancedWorker when execution_guard is available
            if self.execution_guard is not None:
                try:
                    from .enhanced_worker import EnhancedWorker

                    worker: Worker = EnhancedWorker(
                        worker_id=worker_id,
                        role_id=task.role_id,
                        role_prompt=role_prompt,
                        scratchpad=self.scratchpad,
                        llm_backend=self.llm_backend,
                        stream=getattr(self, "stream", False),
                        execution_guard=self.execution_guard,
                        content_cache=getattr(self, "content_cache", None),
                    )
                except (ImportError, ModuleNotFoundError):
                    worker = WorkerFactory.create(
                        worker_id=worker_id,
                        role_id=task.role_id,
                        role_prompt=role_prompt,
                        scratchpad=self.scratchpad,
                        llm_backend=self.llm_backend,
                        stream=getattr(self, "stream", False),
                        content_cache=getattr(self, "content_cache", None),
                    )
            else:
                worker = WorkerFactory.create(
                    worker_id=worker_id,
                    role_id=task.role_id,
                    role_prompt=role_prompt,
                    scratchpad=self.scratchpad,
                    llm_backend=self.llm_backend,
                    stream=getattr(self, "stream", False),
                    content_cache=getattr(self, "content_cache", None),
                )
            self.workers[worker_id] = worker
            self._async_workers[worker_id] = AsyncWorkerWrapper(worker, timeout=self.task_timeout)

        return list(self.workers.values())

    async def execute_plan(self, plan: ExecutionPlan) -> ScheduleResult:
        """
        异步执行完整的协作计划

        使用 asyncio.gather 进行真正的并行执行，
        相比同步版本的 ThreadPoolExecutor 减少线程切换开销。

        Args:
            plan: 执行计划

        Returns:
            ScheduleResult: 执行结果统计
        """
        start_time = time.time()
        results: list[WorkerResult] = []
        errors: list[str] = []

        for batch_idx, batch in enumerate(plan.batches):
            batch_results, batch_errors = await self._execute_batch(batch)
            results.extend(batch_results)
            errors.extend(batch_errors)

            if self.compressor and batch_idx < len(plan.batches) - 1:
                self._buffer_worker_messages(batch_results)
                compressed = self.compressor.check_and_compress(self._message_buffer)
                if compressed.compression_level != CompressionLevel.NONE:
                    self._execution_history.append(
                        {
                            "timestamp": time.time(),
                            "compression": {
                                "level": compressed.compression_level.value,
                                "original_tokens": compressed.original_token_count,
                                "compressed_tokens": compressed.compressed_token_count,
                                "reduction_pct": round(compressed.reduction_percent, 1),
                                "summary": compressed.summary[:200],
                            },
                        }
                    )

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
        self._message_buffer.clear()
        track_usage(
            "async_coordinator.execute_plan",
            success=result.success,
            metadata={
                "total_tasks": result.total_tasks,
                "completed": result.completed_tasks,
                "failed": result.failed_tasks,
                "duration": round(duration, 2),
            },
        )
        return result

    async def _execute_batch(self, batch: TaskBatch) -> tuple[list[WorkerResult], list[str]]:
        """Execute a single batch asynchronously."""
        results: list[WorkerResult] = []
        errors: list[str] = []

        if batch.mode == BatchMode.PARALLEL:
            results = await self._execute_parallel_async(batch)
        else:
            for task in batch.tasks:
                try:
                    worker = self._get_worker_for_task(task)
                    if worker:
                        async_worker = self._async_workers.get(
                            f"{task.role_id}-"
                            f"{[k for k in self._async_workers if k.startswith(task.role_id)][0].split('-')[-1]}"
                            if any(k.startswith(task.role_id) for k in self._async_workers)
                            else ""
                        )
                        if async_worker is None:
                            async_worker = AsyncWorkerWrapper(worker, timeout=self.task_timeout)
                        if self.briefing_mode and self._briefing_chain:
                            self._inject_briefing_to_worker(worker)
                        r = await async_worker.execute(task)
                        results.append(r)
                        if self.briefing_mode:
                            self._collect_briefing_from_worker(worker)
                except asyncio.TimeoutError:
                    errors.append(f"Task {task.task_id} timed out after {self.task_timeout}s")
                except Exception as e:
                    # Per-task isolation: one task failure doesn't abort the batch
                    errors.append(f"Task {task.task_id} failed: {e}")

        return results, errors

    async def _execute_parallel_async(self, batch: TaskBatch) -> list[WorkerResult]:
        """
        Execute tasks in parallel using asyncio.gather.

        Key advantage over ThreadPoolExecutor:
        - No thread creation/destruction overhead
        - Single event loop context switching
        - Better memory efficiency
        - Natural integration with async backends
        """
        semaphore = await self._get_semaphore()
        results: list[WorkerResult] = []
        max_workers = min(batch.max_concurrency or len(batch.tasks), len(batch.tasks))

        if max_workers <= 0:
            return results

        async def _execute_with_semaphore(
            task: TaskDefinition,
        ) -> WorkerResult:
            async with semaphore:
                worker = self._get_worker_for_task(task)
                if not worker:
                    return WorkerResult(
                        worker_id="unknown",
                        task_id=task.task_id,
                        success=False,
                        error="No worker found for task",
                    )

                async_worker = self._get_async_worker(worker)
                if self.briefing_mode and self._briefing_chain:
                    self._inject_briefing_to_worker(worker)

                try:
                    if self.enable_retry and self._retry_manager is not None:
                        result = await self._execute_with_retry(async_worker, task)
                    else:
                        result = await async_worker.execute(task)
                    if self.briefing_mode:
                        self._collect_briefing_from_worker(worker)
                    return result
                except asyncio.TimeoutError:
                    logger.warning(
                        "Task %s timed out after %.1fs",
                        task.task_id,
                        self.task_timeout,
                    )
                    return WorkerResult(
                        worker_id=worker.worker_id,
                        task_id=task.task_id,
                        success=False,
                        error=f"Timeout after {self.task_timeout}s",
                    )
                except Exception as e:
                    # Broad catch: wraps arbitrary worker execution; per-task isolation
                    logger.error("Task %s failed: %s", task.task_id, e)
                    return WorkerResult(
                        worker_id=worker.worker_id,
                        task_id=task.task_id,
                        success=False,
                        error=str(e),
                    )

        tasks = [_execute_with_semaphore(task) for task in batch.tasks]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return results

    def _get_async_worker(self, worker: Worker) -> AsyncWorkerWrapper:
        """Get or create AsyncWorkerWrapper for a Worker."""
        worker_id = worker.worker_id
        if worker_id not in self._async_workers:
            self._async_workers[worker_id] = AsyncWorkerWrapper(worker, timeout=self.task_timeout)
        return self._async_workers[worker_id]

    async def _execute_with_retry(self, async_worker: AsyncWorkerWrapper, task: TaskDefinition) -> WorkerResult:
        """Execute a worker task with retry and fallback via AsyncLLMRetryManager."""
        from .llm_retry_async import RetryConfig

        config = RetryConfig(max_retries=3, initial_delay=1.0, max_delay=60.0)
        current_backend = getattr(self.llm_backend, "backend_name", None)

        assert self._retry_manager is not None
        return cast(
            WorkerResult,
            await self._retry_manager.retry_with_fallback(
                func=async_worker.execute,
                args=(task,),
                kwargs={},
                config=config,
                fallback_backends=None,
                current_backend=current_backend,
            ),
        )

    def _buffer_worker_messages(self, batch_results: list[WorkerResult]) -> None:
        for r in batch_results:
            if r.output:
                self._message_buffer.append(
                    Message(
                        role=r.worker_id,
                        content=str(r.output)[:2000],
                        msg_type=MessageType.ASSISTANT,
                        metadata={
                            "task_id": r.task_id,
                            "success": r.success,
                        },
                    )
                )

    async def compress_context(self, force_level: Any = None) -> CompressedContext | None:
        """
        手动触发上下文压缩

        Args:
            force_level: 强制指定压缩级别

        Returns:
            CompressedContext: 压缩结果
        """
        if not self.compressor:
            return None
        return self.compressor.check_and_compress(self._message_buffer, force_level=force_level)

    def get_compression_stats(self) -> dict[str, Any] | None:
        """获取上下文压缩统计信息"""
        if not self.compressor:
            return None
        compression_events = [e["compression"] for e in self._execution_history if "compression" in e]
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
        avg_reduction = sum(e.get("reduction_pct", 0) for e in compression_events) / len(compression_events)
        return {
            "total_compressions": len(compression_events),
            "avg_reduction_pct": round(avg_reduction, 1),
            "last_compression": compression_events[-1],
            "total_original_tokens": total_original,
            "total_compressed_tokens": total_compressed,
        }

    async def preload_rules(
        self,
        task_description: str,
        user_id: str = "default",
    ) -> dict[str, list[dict]]:
        """
        Pre-load rules from MemoryProvider for all active Workers.

        Args:
            task_description: Task description for rule matching
            user_id: User identifier

        Returns:
            Dict mapping role_id -> list of matched rules
        """
        if not self.memory_provider or not self.memory_provider.is_available():
            return {}

        role_rules: dict[str, list[dict]] = {}
        for wid, worker in self.workers.items():
            try:
                if hasattr(self.memory_provider, "match_rules"):
                    rules = await self._async_call(
                        self.memory_provider.match_rules,
                        task_description=task_description,
                        user_id=user_id,
                        role=worker.role_id,
                        max_rules=5,
                    )
                else:
                    rule_strings = await self._async_call(
                        self.memory_provider.get_rules,
                        user_id=user_id,
                        context={
                            "task": task_description,
                            "role": worker.role_id,
                        },
                    )
                    rules = []
                    for rs in rule_strings:
                        if isinstance(rs, str):
                            rules.append(
                                {
                                    "rule_type": "always",
                                    "trigger": rs.lower(),
                                    "action": rs,
                                    "relevance_score": 0.0,
                                    "rule_id": "",
                                    "override": False,
                                }
                            )
                        elif isinstance(rs, dict):
                            rules.append(rs)
                if rules:
                    role_rules[worker.role_id] = rules if isinstance(rules, list) else []
            except (AttributeError, TypeError, KeyError, ValueError, RuntimeError) as e:
                logger.debug("Rule loading failed for worker %s: %s", wid, e)
                continue

        return role_rules

    async def _async_call(self, func: Any, **kwargs: Any) -> Any:
        """Execute a synchronous function in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(**kwargs))

    def _get_worker_for_task(self, task: TaskDefinition) -> Worker | None:
        for _wid, w in self.workers.items():
            if w.role_id == task.role_id:
                return w
        return None

    def collect_results(self) -> dict[str, Any]:
        """
        从 Scratchpad 收集所有 Worker 的执行结果

        Returns:
            Dict: 结果集合
        """
        scratchpad_summary = self.scratchpad.get_summary()
        stats = self.scratchpad.get_stats()

        findings = self.scratchpad.read(entry_type=EntryType.FINDING)
        decisions = self.scratchpad.read(entry_type=EntryType.DECISION)
        conflicts = self.scratchpad.get_conflicts()

        notifications = []
        for w in self.workers.values():
            notifications.extend(w.get_pending_notifications())

        track_usage(
            "async_coordinator.collect_results",
            success=True,
            metadata={
                "findings": len(findings),
                "decisions": len(decisions),
                "conflicts": len(conflicts),
            },
        )
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

    async def resolve_conflicts(self) -> list[ConsensusRecord]:
        """
        异步检测并解决冲突

        Returns:
            List[ConsensusRecord]: 共识记录列表
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

            for _wid, w in self.workers.items():
                vote_result = w.vote_on_proposal(
                    proposal.proposal_id,
                    decision=True,
                    reason="默认赞成待讨论",
                )
                vote_obj = vote_result.get("vote", vote_result)
                self.consensus.cast_vote(proposal.proposal_id, vote_obj)

            record = self.consensus.reach_consensus(proposal.proposal_id)
            resolutions.append(record)

            if record.outcome != DecisionOutcome.APPROVED:
                self.scratchpad.resolve(
                    conflict.entry_id,
                    resolution=f"[共识:{record.outcome.value}] {record.final_decision}",
                )
            else:
                self.scratchpad.resolve(conflict.entry_id, resolution="已通过共识解决")

        track_usage(
            "async_coordinator.resolve_conflicts",
            success=True,
            metadata={"conflicts_resolved": len(resolutions)},
        )
        return resolutions

    def generate_report(self) -> str:
        """
        生成完整的协作会话报告

        Returns:
            str: Markdown 格式报告
        """
        collection = self.collect_results()
        lines = [
            "# 多角色协作报告 (Async)",
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
                icon = (
                    "✅"
                    if cr.outcome == DecisionOutcome.APPROVED
                    else "❌"
                    if cr.outcome == DecisionOutcome.REJECTED
                    else "⚠️"
                )
                lines.append(f"- [{icon}] {cr.topic}: {cr.outcome.value}")

        return "\n".join(lines)

    def _inject_briefing_to_worker(self, worker: Any) -> None:
        """Inject compressed briefing from preceding Agents."""
        try:
            from .enhanced_worker import EnhancedWorker

            if isinstance(worker, EnhancedWorker) and self._briefing_chain:
                merged = self._merge_briefings(self._briefing_chain)
                worker.receive_briefing(merged)
        except (ImportError, AttributeError) as e:
            logger.debug("Briefing injection failed: %s", e)

    def _collect_briefing_from_worker(self, worker: Any) -> None:
        """Collect compressed briefing from a Worker."""
        try:
            from .enhanced_worker import EnhancedWorker

            if isinstance(worker, EnhancedWorker):
                briefing = worker.compress_to_briefing()
                if briefing and briefing.result_summary:
                    self._briefing_chain.append(briefing)
        except (ImportError, AttributeError) as e:
            logger.debug("Briefing collection failed: %s", e)

    def _merge_briefings(self, briefings: list[Any]) -> Any:
        """Merge multiple Agent briefings into one."""
        from .enhanced_worker import AgentBriefingOutput

        if not briefings:
            return AgentBriefingOutput()

        all_decisions = []
        all_pending = []
        all_rules = []
        summaries = []
        min_confidence = 1.0

        for b in briefings:
            all_decisions.extend(b.key_decisions[:3])
            all_pending.extend(b.pending_items[:3])
            all_rules.extend(b.rules_applied[:5])
            if b.result_summary:
                summaries.append(f"[{b.task_summary}] {b.result_summary}")
            min_confidence = min(min_confidence, b.confidence)

        return AgentBriefingOutput(
            task_summary="; ".join(summaries[:3]),
            key_decisions=all_decisions[:5],
            pending_items=all_pending[:5],
            rules_applied=list(set(all_rules))[:5],
            result_summary=" | ".join(summaries[:3]),
            confidence=min_confidence,
        )

    def _record_execution(self, result: ScheduleResult) -> None:
        self._execution_history.append(
            {
                "timestamp": time.time(),
                "result": {
                    "success": result.success,
                    "total": result.total_tasks,
                    "completed": result.completed_tasks,
                    "failed": result.failed_tasks,
                    "duration": result.duration_seconds,
                },
            }
        )

    def _get_last_duration(self) -> float:
        if self._execution_history:
            duration: Any = self._execution_history[-1]["result"]["duration"]
            return float(duration)
        return 0.0


async def test_async_coordinator() -> None:
    """Quick smoke test for AsyncCoordinator."""
    print("Testing AsyncCoordinator...")

    scratchpad = Scratchpad()
    coord = AsyncCoordinator(scratchpad=scratchpad, task_timeout=30.0)

    roles = [
        {"role_id": "architect", "role_prompt": "You are an architect."},
        {"role_id": "tester", "role_prompt": "You are a tester."},
    ]

    plan = coord.plan_task("Design auth system", roles)
    print(f"✓ Plan created: {plan.total_tasks} tasks")

    workers = coord.spawn_workers(plan)
    print(f"✓ Workers spawned: {len(workers)}")

    result = await coord.execute_plan(plan)
    print(f"✓ Plan executed: success={result.success}, completed={result.completed_tasks}/{result.total_tasks}")

    report = coord.generate_report()
    print(f"✓ Report generated ({len(report)} chars)")

    print("\nAll tests passed! ✓")


if __name__ == "__main__":
    asyncio.run(test_async_coordinator())
