#!/usr/bin/env python3
"""
Coordinator - Global Orchestrator

Core component for multi-Worker collaboration:
1. Decompose tasks into parallel Worker plans
2. Create and schedule Workers
3. Collect results and shared state
4. Resolve conflicts and reach consensus
5. Generate final collaboration report
6. Inter-Agent briefing handoff (latent-briefing pattern)
7. Rule pre-check via MemoryProvider (optional)
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from .consensus import ConsensusEngine
from .context_compressor import CompressedContext, CompressionLevel, ContextCompressor, Message, MessageType
from .models import (
    BatchMode,
    ConsensusRecord,
    DecisionOutcome,
    EntryType,
    ExecutionPlan,
    ScheduleResult,
    TaskBatch,
    TaskDefinition,
    TokenBudget,
    WorkerResult,
)
from .scratchpad import Scratchpad
from .usage_tracker import track_usage
from .worker import Worker, WorkerFactory

if TYPE_CHECKING:
    from .ccr_store import CCRStore

logger = logging.getLogger(__name__)

# Pattern for ``devsquad_retrieve(trace_id=X, query=Y)`` markers in Worker output.
# Coordinator scans Worker output for these markers and auto-injects the original
# content from CCRStore so downstream Workers see the full uncompressed context.
_DEVSQUAD_RETRIEVE_PATTERN = re.compile(
    r"devsquad_retrieve\(\s*trace_id\s*=\s*['\"]?([a-f0-9]+)['\"]?\s*(?:,\s*query\s*=\s*['\"]([^'\"]*)['\"]\s*)?\)"
)


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

    __slots__ = (
        "scratchpad",
        "consensus",
        "workers",
        "_worker_index",
        "_executor",
        "_execution_history",
        "coordinator_id",
        "enable_compression",
        "compressor",
        "_message_buffer",
        "llm_backend",
        "stream",
        "memory_provider",
        "briefing_mode",
        "_briefing_chain",
        "execution_guard",
        "content_cache",
        "code_graph",
        "smart_compression",
        "_smart_stats",
        "token_budget",
        "ccr_store",
        "_used_input_tokens",
    )

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
        execution_guard: Any = None,
        smart_compression: bool = False,
        token_budget: TokenBudget | None = None,
        ccr_store: CCRStore | None = None,
    ) -> None:
        """
        Initialize Coordinator.

        Args:
            scratchpad: Shared scratchpad instance (auto-created if not provided)
            persist_dir: Scratchpad persistence directory
            enable_compression: Enable context compression (prevent overflow in long tasks)
            compression_threshold: Compression trigger threshold (token count), default 100000
            llm_backend: LLM execution backend (None=MockBackend, returns prompt text)
            memory_provider: MemoryProvider implementation (optional, for rule pre-check)
            briefing_mode: Enable inter-Agent briefing handoff (default True)
            execution_guard: ExecutionGuard instance for worker execution monitoring (optional)
            smart_compression: V3.10.0 — apply SMART structure-aware pre-compression
                between batches before destructive compression. Preserves all messages
                while compressing JSON/log/code content, reducing token count without
                information loss. When True, SMART runs first; if tokens still exceed
                threshold, destructive level (SNIP/SESSION_MEMORY/FULL_COMPACT) runs next.
            token_budget: V3.10.0 Phase 3 — per-dispatch token budget. When set,
                ``execute_plan`` checks ``used_input_tokens`` against the budget
                before each batch. On warning (>=80% by default) SMART compression
                is force-triggered; on exceed (>=100%) destructive compression
                is force-triggered via FULL_COMPACT. ``get_budget_status`` exposes
                the live counters for dashboard/API.
            ccr_store: V3.10.0 Phase 3 — reversible compression store. When set,
                passed to ``ContextCompressor`` so ``SmartCrusher`` injects
                ``retrieve full: trace_id=...`` markers into crushed output. The
                Coordinator scans Worker output for ``devsquad_retrieve(trace_id=...)``
                markers and auto-injects the original content from the store.
        """
        self.scratchpad = scratchpad or Scratchpad(persist_dir=persist_dir)
        self.consensus = ConsensusEngine()
        self.workers: dict[str, Worker] = {}
        self._worker_index: dict[str, Worker] = {}
        self._executor = ThreadPoolExecutor(max_workers=7)
        self._execution_history: list[dict[str, Any]] = []
        self.coordinator_id = f"coord-{uuid.uuid4().hex[:8]}"
        self.enable_compression = enable_compression
        self.compressor = (
            ContextCompressor(token_threshold=compression_threshold, ccr_store=ccr_store)
            if enable_compression
            else None
        )
        self._message_buffer: list[Message] = []
        self.smart_compression = smart_compression
        self._smart_stats: dict[str, Any] = {
            "smart_precompressions": 0,
            "smart_messages_crushed": 0,
            "smart_tokens_before": 0,
            "smart_tokens_after": 0,
        }
        self.llm_backend = llm_backend
        self.stream = stream
        self.memory_provider = memory_provider
        self.briefing_mode = briefing_mode
        self._briefing_chain: list[Any] = []
        self.execution_guard = execution_guard
        # V3.8 #9: ContentCache wrapper (set by the dispatcher after
        # construction when a ContentCache is configured). When set,
        # workers check it before LLM API calls.
        self.content_cache: Any = None
        # V3.9-02: CodeKnowledgeGraph (set by the dispatcher after
        # construction when a graph is configured). When set, workers
        # query the graph before LLM calls to reduce Read/Grep usage.
        self.code_graph: Any = None
        # V3.10.0 Phase 3: Token budget + reversible compression store.
        self.token_budget = token_budget
        self.ccr_store = ccr_store
        self._used_input_tokens: int = 0

    def plan_task(
        self, task_description: str, available_roles: list[dict[str, str]], stage_id: str | None = None
    ) -> ExecutionPlan:
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
            >>> plan = coord.plan_task("设计用户认证系统", [{"role_id": "architect", "role_prompt": "..."}])
            >>> plan.total_tasks
            1
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
            "coordinator.plan_task",
            success=True,
            metadata={"num_roles": len(available_roles), "total_tasks": len(tasks)},
        )
        return plan

    def spawn_workers(self, plan: ExecutionPlan, registry: Any = None) -> list[Worker]:
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
        self._worker_index.clear()
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
                        code_graph=getattr(self, "code_graph", None),
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
                        code_graph=getattr(self, "code_graph", None),
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
                    code_graph=getattr(self, "code_graph", None),
                )
            self.workers[worker_id] = worker
            self._worker_index[worker.role_id] = worker
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
            # V3.10.0 Phase 3: Token budget pre-batch check.
            # On warning: force SMART compression (preserves all messages,
            # only crushes structured content). On exceed: force destructive
            # FULL_COMPACT to free token budget before the next batch runs.
            self._check_token_budget_before_batch()

            batch_results, batch_errors = self._execute_batch(batch)
            # V3.10.0 Phase 3: Auto-retrieve compressed originals.
            # If Worker output contains ``devsquad_retrieve(trace_id=...)``
            # markers and a CCRStore is configured, replace the marker with
            # the original content so downstream Workers see full context.
            if self.ccr_store is not None:
                batch_results = [self._retrieve_compressed_originals(r) for r in batch_results]
            results.extend(batch_results)
            errors.extend(batch_errors)

            if self.compressor and batch_idx < len(plan.batches) - 1:
                self._buffer_worker_messages(batch_results)
                # V3.10.0: SMART pre-compression — structure-aware content compression
                # that preserves all messages. Runs before destructive compression
                # (SNIP/SESSION_MEMORY/FULL_COMPACT) so structured content (JSON/logs/
                # code) is crushed first; if tokens still exceed threshold, the
                # destructive level runs next on the already-reduced buffer.
                if self.smart_compression:
                    smart_ctx = self.apply_smart_compression()
                    if smart_ctx is not None and smart_ctx.stats.get("smart_crush_applied", 0) > 0:
                        self._execution_history.append(
                            {
                                "timestamp": time.time(),
                                "smart_precompression": {
                                    "messages_crushed": smart_ctx.stats.get("smart_crush_applied", 0),
                                    "tokens_before": smart_ctx.original_token_count,
                                    "tokens_after": smart_ctx.compressed_token_count,
                                    "reduction_pct": round(smart_ctx.reduction_percent, 1),
                                },
                            }
                        )
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
                # V3.10.0 Phase 3: Update used_input_tokens from compressed result.
                if self.token_budget is not None:
                    self._used_input_tokens = compressed.compressed_token_count

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
            "coordinator.execute_plan",
            success=result.success,
            metadata={
                "total_tasks": result.total_tasks,
                "completed": result.completed_tasks,
                "failed": result.failed_tasks,
                "duration": round(duration, 2),
            },
        )
        return result

    def _buffer_worker_messages(self, batch_results: list[WorkerResult]) -> None:
        for r in batch_results:
            if r.output:
                self._message_buffer.append(
                    Message(
                        role=r.worker_id,
                        content=str(r.output)[:2000],
                        msg_type=MessageType.ASSISTANT,
                        metadata={"task_id": r.task_id, "success": r.success},
                    )
                )

    def compress_context(self, force_level: Any = None) -> CompressedContext | None:
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

    def apply_smart_compression(self) -> CompressedContext | None:
        """
        V3.10.0 — Apply SMART structure-aware compression to the message buffer.

        SMART compression preserves all messages (no deletion) while compressing
        structured content (JSON arrays, logs, code) via ContentRouter + SmartCrusher.
        After compression, the internal _message_buffer is replaced with the
        compressed messages so subsequent destructive compression (SNIP/
        SESSION_MEMORY/FULL_COMPACT) sees the reduced token count.

        This is the "SMART-first" strategy: structure-aware compression runs
        before destructive compression. If SMART reduces tokens below the
        destructive threshold, no messages are lost.

        Returns:
            CompressedContext with SMART-level stats, or None if compression
            is disabled or the buffer is empty.
        """
        if not self.compressor or not self._message_buffer:
            return None
        smart_ctx = self.compressor.check_and_compress(
            self._message_buffer, force_level=CompressionLevel.SMART
        )
        crushed_count = smart_ctx.stats.get("smart_crush_applied", 0)
        if crushed_count > 0:
            # Replace buffer with SMART-compressed messages so later automatic
            # compression sees the reduced token count.
            self._message_buffer = list(smart_ctx.messages)
            self._smart_stats["smart_precompressions"] += 1
            self._smart_stats["smart_messages_crushed"] += crushed_count
            self._smart_stats["smart_tokens_before"] += smart_ctx.original_token_count
            self._smart_stats["smart_tokens_after"] += smart_ctx.compressed_token_count
        return smart_ctx

    def _check_token_budget_before_batch(self) -> None:
        """V3.10.0 Phase 3 — Enforce token budget before each batch.

        Estimates the current message buffer token count and updates
        ``_used_input_tokens``. When a ``TokenBudget`` is configured:
          - On warning (>=80% by default): force SMART compression to reduce
            structured content without losing messages.
          - On exceed (>=100%): force destructive FULL_COMPACT compression
            to free token budget before the next batch runs.

        Logs a warning when the budget is exceeded. No-op when no budget
        is configured or compression is disabled.
        """
        if self.token_budget is None or self.compressor is None:
            return
        if self._message_buffer:
            self._used_input_tokens = self.compressor.estimate_messages_tokens(self._message_buffer)
        if self.token_budget.is_exceeded(self._used_input_tokens):
            logger.warning(
                "Token budget exceeded (%d/%d) — forcing FULL_COMPACT compression",
                self._used_input_tokens,
                self.token_budget.total_input_budget,
            )
            self.compressor.check_and_compress(
                self._message_buffer, force_level=CompressionLevel.FULL_COMPACT
            )
        elif self.token_budget.is_warning(self._used_input_tokens):
            logger.info(
                "Token budget warning (%d/%d) — forcing SMART compression",
                self._used_input_tokens,
                self.token_budget.total_input_budget,
            )
            self.apply_smart_compression()

    def _retrieve_compressed_originals(self, result: WorkerResult) -> WorkerResult:
        """V3.10.0 Phase 3 — Auto-inject compressed originals into Worker output.

        Scans ``result.output`` for ``devsquad_retrieve(trace_id=X, query=Y)``
        markers emitted by SmartCrusher. For each marker, retrieves the original
        content from ``CCRStore`` and appends it after the marker so downstream
        Workers see the full uncompressed context.

        Args:
            result: WorkerResult whose ``output`` may contain retrieve markers.

        Returns:
            The same WorkerResult with ``output`` updated in-place when markers
            were found and originals retrieved. Returns the result unchanged
            when no CCRStore is configured or no markers are present.
        """
        if self.ccr_store is None or not result.output:
            return result
        output_str = str(result.output)

        def _replace(match: re.Match[str]) -> str:
            trace_id = match.group(1)
            query = match.group(2) if match.lastindex and match.lastindex >= 2 else None
            try:
                original = self.ccr_store.retrieve(trace_id, query=query)  # type: ignore[union-attr]
                if original:
                    return f"\n[Retrieved original (trace_id={trace_id})]\n{original}\n[/Retrieved]\n"
            except (KeyError, ValueError) as e:
                logger.warning("Failed to retrieve trace_id=%s: %s", trace_id, e)
            return match.group(0)

        new_output = _DEVSQUAD_RETRIEVE_PATTERN.sub(_replace, output_str)
        if new_output != output_str:
            result.output = new_output
        return result

    def get_budget_status(self) -> dict[str, Any] | None:
        """V3.10.0 Phase 3 — Return live token budget status for dashboard/API.

        Returns:
            Dict with budget config + live counters, or None when no
            TokenBudget is configured. Fields:
              - total_input_budget / per_role_input_budget / output_budget
              - warning_ratio / warning_threshold
              - used_input_tokens / remaining_input_tokens
              - is_warning / is_exceeded
        """
        if self.token_budget is None:
            return None
        return {
            "total_input_budget": self.token_budget.total_input_budget,
            "per_role_input_budget": self.token_budget.per_role_input_budget,
            "output_budget": self.token_budget.output_budget,
            "warning_ratio": self.token_budget.warning_ratio,
            "warning_threshold": self.token_budget.warning_threshold(),
            "used_input_tokens": self._used_input_tokens,
            "remaining_input_tokens": self.token_budget.remaining(self._used_input_tokens),
            "is_warning": self.token_budget.is_warning(self._used_input_tokens),
            "is_exceeded": self.token_budget.is_exceeded(self._used_input_tokens),
        }

    def get_compression_stats(self) -> dict[str, Any] | None:
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
        compression_events = [e["compression"] for e in self._execution_history if "compression" in e]
        smart_events = [e["smart_precompression"] for e in self._execution_history if "smart_precompression" in e]
        if not compression_events and not smart_events:
            return {
                "total_compressions": 0,
                "avg_reduction_pct": 0.0,
                "last_compression": None,
                "total_original_tokens": 0,
                "total_compressed_tokens": 0,
                "smart_precompressions": self._smart_stats["smart_precompressions"],
                "smart_messages_crushed": self._smart_stats["smart_messages_crushed"],
            }
        total_original = sum(e.get("original_tokens", 0) for e in compression_events)
        total_compressed = sum(e.get("compressed_tokens", 0) for e in compression_events)
        avg_reduction = sum(e.get("reduction_pct", 0) for e in compression_events) / len(compression_events) if compression_events else 0.0
        smart_tokens_before = sum(e.get("tokens_before", 0) for e in smart_events)
        smart_tokens_after = sum(e.get("tokens_after", 0) for e in smart_events)
        smart_avg_reduction = (
            sum(e.get("reduction_pct", 0) for e in smart_events) / len(smart_events)
            if smart_events
            else 0.0
        )
        return {
            "total_compressions": len(compression_events),
            "avg_reduction_pct": round(avg_reduction, 1),
            "last_compression": compression_events[-1] if compression_events else None,
            "total_original_tokens": total_original,
            "total_compressed_tokens": total_compressed,
            "smart_precompressions": len(smart_events),
            "smart_messages_crushed": sum(e.get("messages_crushed", 0) for e in smart_events),
            "smart_tokens_before": smart_tokens_before,
            "smart_tokens_after": smart_tokens_after,
            "smart_avg_reduction_pct": round(smart_avg_reduction, 1),
        }

    def get_session_memory(self, category: Any = None, limit: int = 50) -> list[dict[str, Any]] | None:
        """
        获取会话记忆（从 ContextCompressor 的 SessionMemory 中提取）

        Args:
            category: 记忆类别过滤（可选）
            limit: 返回条数上限

        Returns:
            List[Dict]: 提取的记忆条目列表
        """
        if self.compressor is None:
            return None
        entries = self.compressor.get_session_memory(category=category, limit=limit)
        return [entry.to_dict() for entry in entries]

    def _execute_batch(self, batch: TaskBatch) -> tuple[list[WorkerResult], list[str]]:
        results: list[WorkerResult] = []
        errors: list[str] = []

        if batch.mode == BatchMode.PARALLEL:
            results = self._execute_parallel(batch)
        else:
            for task in batch.tasks:
                try:
                    worker = self._get_worker_for_task(task)
                    if worker:
                        if self.briefing_mode and self._briefing_chain:
                            self._inject_briefing_to_worker(worker)
                        r = worker.execute(task)
                        results.append(r)
                        if self.briefing_mode:
                            self._collect_briefing_from_worker(worker)
                except Exception as e:
                    # Broad catch: wraps arbitrary worker execution; per-task isolation
                    errors.append(f"Task {task.task_id} failed: {e}")

        return results, errors

    def _execute_parallel(self, batch: TaskBatch) -> list[WorkerResult]:
        results: list[WorkerResult] = []
        max_workers = min(batch.max_concurrency or len(batch.tasks), len(batch.tasks))
        if max_workers <= 0:
            return results
        futures = {}
        for task in batch.tasks:
            worker = self._get_worker_for_task(task)
            if worker:
                future = self._executor.submit(worker.execute, task)
                futures[future] = task.task_id
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                # Broad catch: wraps arbitrary worker execution in thread pool
                results.append(
                    WorkerResult(
                        worker_id="unknown",
                        task_id=futures[future],
                        success=False,
                        error=str(e),
                    )
                )
        return results

    def _inject_briefing_to_worker(self, worker: Any) -> None:
        """Inject compressed briefing from preceding Agents into the next Worker."""
        try:
            from .enhanced_worker import EnhancedWorker

            if isinstance(worker, EnhancedWorker) and self._briefing_chain:
                merged = self._merge_briefings(self._briefing_chain)
                worker.receive_briefing(merged)
        except (ImportError, AttributeError) as _e:
            logger.debug("Briefing injection failed: %s", _e)

    def _collect_briefing_from_worker(self, worker: Any) -> None:
        """Collect compressed briefing from a Worker after execution."""
        try:
            from .enhanced_worker import EnhancedWorker

            if isinstance(worker, EnhancedWorker):
                briefing = worker.compress_to_briefing()
                if briefing and briefing.result_summary:
                    self._briefing_chain.append(briefing)
        except (ImportError, AttributeError) as _e:
            logger.debug("Briefing collection failed: %s", _e)

    def _merge_briefings(self, briefings: list[Any]) -> Any:
        """Merge multiple Agent briefings into a single composite briefing."""
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

    def preload_rules(self, task_description: str, user_id: str = "default") -> dict[str, list[dict]]:
        """
        Pre-load rules from MemoryProvider for all active Workers.

        Called before execute_plan() to pre-check rules at the orchestrator level,
        avoiding repeated queries from individual Agents.

        Uses match_rules() when available (CarryMem v0.2.9+), falls back to
        get_rules() for backward compatibility.

        Args:
            task_description: Task description for rule matching
            user_id: User identifier for rule lookup

        Returns:
            Dict mapping role_id -> list of matched rules
        """
        if not self.memory_provider or not self.memory_provider.is_available():
            return {}

        role_rules: dict[str, list[dict]] = {}
        for _wid, worker in self.workers.items():
            try:
                if hasattr(self.memory_provider, "match_rules"):
                    rules = self.memory_provider.match_rules(
                        task_description=task_description, user_id=user_id, role=worker.role_id, max_rules=5
                    )
                else:
                    rule_strings = self.memory_provider.get_rules(
                        user_id=user_id, context={"task": task_description, "role": worker.role_id}
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
            except (AttributeError, TypeError, KeyError, ValueError, RuntimeError) as _e:
                logger.debug("Rule extraction failed for worker %s: %s", worker.role_id, _e)
                continue

        return role_rules

    def _get_worker_for_task(self, task: TaskDefinition) -> Worker | None:
        return self._worker_index.get(task.role_id)

    def collect_results(self) -> dict[str, Any]:
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

        track_usage(
            "coordinator.collect_results",
            success=True,
            metadata={"findings": len(findings), "decisions": len(decisions), "conflicts": len(conflicts)},
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

    def resolve_conflicts(self) -> list[ConsensusRecord]:
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

            for _wid, w in self.workers.items():
                vote_result = w.vote_on_proposal(proposal.proposal_id, decision=True, reason="默认赞成待讨论")
                vote_obj = vote_result.get("vote", vote_result)
                self.consensus.cast_vote(proposal.proposal_id, vote_obj)

            record = self.consensus.reach_consensus(proposal.proposal_id)
            resolutions.append(record)

            if record.outcome != DecisionOutcome.APPROVED:
                self.scratchpad.resolve(
                    conflict.entry_id, resolution=f"[共识:{record.outcome.value}] {record.final_decision}"
                )
            else:
                self.scratchpad.resolve(conflict.entry_id, resolution="已通过共识解决")

        track_usage("coordinator.resolve_conflicts", success=True, metadata={"conflicts_resolved": len(resolutions)})
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
                icon = (
                    "✅"
                    if cr.outcome == DecisionOutcome.APPROVED
                    else "❌"
                    if cr.outcome == DecisionOutcome.REJECTED
                    else "⚠️"
                )
                lines.append(f"- [{icon}] {cr.topic}: {cr.outcome.value}")

        return "\n".join(lines)

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

    def __del__(self) -> None:
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)
