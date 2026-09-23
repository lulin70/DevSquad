"""Context-compression mixin for :class:`Coordinator`.

Extracted from ``coordinator.py`` (V4.5.20 size-gate refactor) so the core
orchestrator module keeps only planning / scheduling / reporting. This mixin
owns the V3.10.0 Phase 3 context-window surface: SMART structure-aware
pre-compression, destructive-compression delegation, per-batch token-budget
enforcement, CCR original retrieval, and the dashboard/API status accessors.

All methods read state from the owning ``Coordinator`` (declared in its
``__slots__``); the mixin declares ``__slots__ = ()`` so instances keep the
subclass's slot-only layout.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .context_compressor import CompressedContext, CompressionLevel, ContextCompressor
from .models import WorkerResult

logger = logging.getLogger(__name__)

# Pattern for ``devsquad_retrieve(trace_id=X, query=Y)`` markers in Worker output.
# Coordinator scans Worker output for these markers and auto-injects the original
# content from CCRStore so downstream Workers see the full uncompressed context.
_DEVSQUAD_RETRIEVE_PATTERN = re.compile(
    r"devsquad_retrieve\(\s*trace_id\s*=\s*['\"]?([a-f0-9]+)['\"]?\s*(?:,\s*query\s*=\s*['\"]([^'\"]*)['\"]\s*)?\)"
)

# V4.2.1 Bugfix: SmartCrusher emits ``retrieve full: trace_id=X`` markers in
# compressed content headers (e.g. ``[N items compressed to M; retrieve full: trace_id=X]``).
# This pattern detects them so the Coordinator can auto-retrieve originals.
_RETRIEVE_FULL_PATTERN = re.compile(
    r"retrieve full:\s*trace_id\s*=\s*([a-f0-9]+)"
)


class CoordinatorCompressionMixin:
    """Context compression / token-budget helpers used by :class:`Coordinator`."""

    __slots__ = ()

    # Injected by Coordinator.__init__; declared here for mypy.
    # NOTE: the two slot-backed attributes assigned inside this mixin carry
    # ``# type: ignore[misc]`` — mypy enforces ``__slots__`` membership against
    # the declaring class, and the storage here lives in ``Coordinator.__slots__``
    # (this mixin adds no slots, see class docstring).
    compressor: ContextCompressor | None
    _message_buffer: list[Any]
    smart_compression: bool
    _smart_stats: dict[str, Any]
    _execution_history: list[dict[str, Any]]
    token_budget: Any
    ccr_store: Any
    _used_input_tokens: int

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
            self._message_buffer = list(smart_ctx.messages)  # type: ignore[misc]
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
            self._used_input_tokens = self.compressor.estimate_messages_tokens(self._message_buffer)  # type: ignore[misc]
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

        Scans ``result.output`` for retrieval markers emitted by SmartCrusher
        and replaces them with the original content from ``CCRStore`` so
        downstream Workers see the full uncompressed context.

        Two marker formats are detected:

        1. ``devsquad_retrieve(trace_id=X, query=Y)`` — canonical API format
           (explicit retrieval request in Worker output).
        2. ``retrieve full: trace_id=X`` — SmartCrusher metadata format injected
           into compressed content headers (V4.2.1 bugfix: previously undetected).

        Args:
            result: WorkerResult whose ``output`` may contain retrieve markers.

        Returns:
            The same WorkerResult with ``output`` updated in-place when markers
            were found and originals retrieved. Returns the result unchanged
            when no CCRStore is configured or no markers are present.
        """
        store = self.ccr_store
        if store is None or not result.output:
            return result
        output_str = str(result.output)

        def _replace(match: re.Match[str]) -> str:
            trace_id = match.group(1)
            query = match.group(2) if match.lastindex and match.lastindex >= 2 else None
            try:
                original = store.retrieve(trace_id, query=query)
                if original:
                    return f"\n[Retrieved original (trace_id={trace_id})]\n{original}\n[/Retrieved]\n"
            except (KeyError, ValueError) as e:
                logger.warning("Failed to retrieve trace_id=%s: %s", trace_id, e)
            return match.group(0)

        # V4.2.1 bugfix: apply both marker formats — canonical API and SmartCrusher metadata.
        new_output = _DEVSQUAD_RETRIEVE_PATTERN.sub(_replace, output_str)
        new_output = _RETRIEVE_FULL_PATTERN.sub(_replace, new_output)
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


__all__ = ["CoordinatorCompressionMixin"]
