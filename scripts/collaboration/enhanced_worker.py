#!/usr/bin/env python3
"""
Enhanced Worker Module

Extends the base Worker with:
- Agent briefing integration (personalization memory)
- Performance monitoring integration
- LLM cache integration
- Retry mechanism integration
- Protocol-based provider injection

Usage:
    from scripts.collaboration.enhanced_worker import EnhancedWorker

    worker = EnhancedWorker(
        worker_id="architect-1",
        role_id="architect",
        cache_provider=llm_cache,
        retry_provider=llm_retry,
        monitor_provider=performance_monitor,
    )

    result = worker.execute(task)

Version: v1.0
Created: 2026-05-01
"""

import contextlib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .models import EntryType, ScratchpadEntry, TaskDefinition, WorkerResult
from .worker import Worker

logger = logging.getLogger(__name__)

# Lazy import for ExecutionGuard - graceful degradation
_ExecutionGuard = None
with contextlib.suppress(ImportError, ModuleNotFoundError):
    from .execution_guard import ExecutionGuard as _ExecutionGuard

_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")
_MAX_RULE_TEXT_LENGTH = 500


def _is_available(provider) -> bool:
    """Check provider availability, compatible with both property and method."""
    if provider is None:
        return False
    val = provider.is_available
    if callable(val):
        return val()
    return bool(val)


@dataclass
class AgentBriefingOutput:
    """Compressed state passed between Agents (latent-briefing pattern)."""

    task_summary: str = ""
    key_decisions: list[str] = field(default_factory=list)
    pending_items: list[str] = field(default_factory=list)
    rules_applied: list[str] = field(default_factory=list)
    result_summary: str = ""
    confidence: float = 0.0
    assumptions: list[str] = field(default_factory=list)


class EnhancedWorker(Worker):
    """
    Enhanced Worker with protocol-based provider injection.

    Extends base Worker with:
    - CacheProvider: LLM response caching
    - RetryProvider: LLM call retry with fallback
    - MonitorProvider: Performance monitoring
    - Agent briefing: Personalization memory injection
    """

    def __init__(
        self,
        worker_id: str,
        role_id: str,
        role_prompt: str = "",
        scratchpad=None,
        llm_backend=None,
        stream: bool = False,
        cache_provider=None,
        retry_provider=None,
        monitor_provider=None,
        memory_provider=None,
        execution_guard: Any = None,
        content_cache: Any = None,
    ):
        """
        Initialize EnhancedWorker.

        Args:
            worker_id: Unique worker identifier
            role_id: Role identifier (e.g., 'architect', 'coder')
            role_prompt: Custom role prompt
            scratchpad: Scratchpad instance for inter-agent communication
            llm_backend: LLM backend instance
            stream: Whether to enable streaming output
            cache_provider: CacheProvider implementation (optional)
            retry_provider: RetryProvider implementation (optional)
            monitor_provider: MonitorProvider implementation (optional)
            memory_provider: MemoryProvider implementation (optional, for rule injection)
            execution_guard: ExecutionGuard instance for execution monitoring (optional;
                           defaults to a standard ExecutionGuard if not provided and
                           the module is available)
            content_cache: Optional ContentCache wrapper (V3.8 #9). When
                provided, checked before LLM API calls and populated after
                responses.
        """
        super().__init__(
            worker_id=worker_id,
            role_id=role_id,
            role_prompt=role_prompt,
            scratchpad=scratchpad,
            llm_backend=llm_backend,
            stream=stream,
            content_cache=content_cache,
        )

        self.cache_provider = cache_provider
        self.retry_provider = retry_provider
        self.monitor_provider = monitor_provider
        self.memory_provider = memory_provider

        # ExecutionGuard: use provided instance, or create default if available
        if execution_guard is not None:
            self.execution_guard = execution_guard
        elif _ExecutionGuard is not None:
            self.execution_guard = _ExecutionGuard(max_duration_sec=300, max_output_tokens=8000)
        else:
            self.execution_guard = None

        self._briefing = None
        self._briefing_loaded = False
        self._last_result: WorkerResult | None = None
        self._confidence_scorer = None
        self._injected_rules: list[dict[str, Any]] = []
        self._rules_applied: list[str] = []
        self._validator = None

        try:
            from .confidence_score import ConfidenceScorer

            self._confidence_scorer = ConfidenceScorer()
        except (ImportError, ModuleNotFoundError):
            pass

        try:
            from .input_validator import InputValidator

            self._validator = InputValidator()
        except (ImportError, ModuleNotFoundError):
            pass

    @property
    def briefing(self):
        """Get agent briefing (lazy load)."""
        if not self._briefing_loaded:
            self._load_briefing()
            self._briefing_loaded = True
        return self._briefing

    def _load_briefing(self):
        """Load agent briefing from memory provider."""
        try:
            from .agent_briefing import AgentBriefing

            self._briefing = AgentBriefing(agent_role=self.role_id)
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning("Failed to load briefing for %s: %s", self.role_id, e)
            self._briefing = None

    def _do_work_with_briefing(self, task: TaskDefinition) -> WorkerResult:
        """
        Execute task with briefing context injection.

        Follows the same flow as Worker.execute():
        1. Build execution context
        2. _do_work() returns str (finding text)
        3. Write finding to scratchpad
        4. Wrap into WorkerResult

        Args:
            task: Task definition

        Returns:
            WorkerResult with briefing context
        """
        start_time = time.time()

        try:
            # Inject briefing context into task description if available
            briefing_context = None
            if self._briefing:
                try:
                    briefing_context = self._briefing.get_briefing_context(task.description)
                except (AttributeError, KeyError, RuntimeError) as e:
                    logger.warning("Failed to get briefing context: %s", e)

            # Build context and execute (same flow as Worker.execute)
            context = self._build_execution_context(task)
            finding = self._do_work(context)

            # Write finding to scratchpad
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

            # Build output dict (same structure as Worker.execute)
            output = {
                "worker_id": self.worker_id,
                "role_id": self.role_id,
                "task_id": task.task_id,
                "finding_summary": finding,
            }

            # Inject briefing context into output
            if briefing_context and output["finding_summary"]:
                output["briefing_context"] = briefing_context

            result = WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=True,
                output=output,
                scratchpad_entries_written=self._entries_written_count,
                notifications_sent=len(self._notifications_outbox),
                duration_seconds=time.time() - start_time,
            )

            duration = time.time() - start_time
            self._record_monitor(task, duration, success=True)

            return result

        except Exception as e:  # Broad catch: re-raise after recording
            duration = time.time() - start_time
            logger.debug("Worker execution failed: %s", e)
            self._record_monitor(task, duration, success=False)
            raise

    def _do_work_simple(self, task: TaskDefinition) -> WorkerResult:
        """
        Execute task without briefing (fallback path).

        Same flow as Worker.execute(): build context → _do_work → write scratchpad → WorkerResult.

        Args:
            task: Task definition

        Returns:
            WorkerResult
        """
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
                "finding_summary": finding,
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
        except Exception as e:  # Broad catch: fallback worker entry; ensures WorkerResult on failure
            logger.error("Worker %s fallback execution failed: %s", self.worker_id, e)
            return WorkerResult(
                worker_id=self.worker_id,
                task_id=task.task_id,
                success=False,
                output={
                    "worker_id": self.worker_id,
                    "role_id": self.role_id,
                    "task_id": task.task_id,
                    "error_detail": "Fallback execution failed",
                },
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    def _record_monitor(self, task: TaskDefinition, duration: float, success: bool):
        """Record execution metrics to monitor provider."""
        if self.monitor_provider and self.monitor_provider.is_available():
            try:
                self.monitor_provider.record_agent_execution(
                    agent_role=self.role_id,
                    task=task.description[:100],
                    duration=duration,
                    success=success,
                )
            except (AttributeError, RuntimeError, ConnectionError) as e:
                logger.warning("Monitor recording failed: %s", e)

    def execute(self, task: TaskDefinition) -> WorkerResult:
        """
        Execute task with all enhanced features.

        Args:
            task: Task definition

        Returns:
            WorkerResult
        """
        self._inject_rules_from_provider(task)

        # Track elapsed time for ExecutionGuard
        exec_start = time.monotonic()

        if self.retry_provider and self.retry_provider.is_available():
            try:
                result = self.retry_provider.retry_with_fallback(
                    func=lambda: self._do_work_with_briefing(task),
                    max_attempts=3,
                    fallback=lambda: self._do_work_simple(task),
                )
            except Exception as e:  # Broad catch: retry mechanism fallback
                logger.debug("Retry mechanism failed, falling back: %s", e)
                result = self._do_work_simple(task)
        else:
            result = self._do_work_with_briefing(task)

        elapsed_time = time.monotonic() - exec_start

        self._last_result = result

        # ExecutionGuard: check abort conditions and warnings
        if self.execution_guard and result.success and result.output:
            output_text = result.output if isinstance(result.output, str) else str(result.output)
            try:
                should_abort, abort_reason = self.execution_guard.check_abort(
                    output_text, elapsed_time
                )
                if should_abort:
                    logger.warning(
                        "ExecutionGuard abort triggered for worker %s: %s",
                        self.worker_id, abort_reason,
                    )
                    if isinstance(result.output, dict):
                        result.output["execution_guard_abort"] = True
                        result.output["execution_guard_reason"] = abort_reason

                warnings = self.execution_guard.check_warnings(output_text)
                if warnings:
                    logger.warning(
                        "ExecutionGuard warnings for worker %s: %s",
                        self.worker_id, ", ".join(warnings),
                    )
                    if isinstance(result.output, dict):
                        result.output["execution_guard_warnings"] = warnings
            except (ValueError, AttributeError, RuntimeError) as guard_err:
                logger.debug("ExecutionGuard check failed: %s", guard_err)

        if self._confidence_scorer and result.success and result.output:
            try:
                output_text = result.output if isinstance(result.output, str) else str(result.output)
                score = self._confidence_scorer.score_response(output_text)
                if isinstance(result.output, dict):
                    result.output["confidence"] = score.overall_score
                    result.output["confidence_factors"] = {
                        "completeness": score.factors.get("completeness", 0.0),
                        "certainty": score.factors.get("certainty", 0.0),
                        "specificity": score.factors.get("specificity", 0.0),
                    }
                    if score.overall_score < 0.7:
                        result.output["low_confidence_warning"] = (
                            f"Low confidence ({score.overall_score:.2f}). "
                            "Assumptions may need verification by subsequent agents."
                        )
            except (ValueError, AttributeError, RuntimeError) as e:
                logger.warning("Confidence scoring failed: %s", e)

        if self._injected_rules and result.success and result.output:
            violations = self._check_forbid_violations(result)
            if violations and isinstance(result.output, dict):
                result.output["rule_violations"] = violations

        return result

    def _inject_rules_from_provider(self, task: TaskDefinition):
        """Fetch and validate rules from MemoryProvider before task execution."""
        if not self.memory_provider or not _is_available(self.memory_provider):
            return

        try:
            if hasattr(self.memory_provider, "match_rules"):
                raw_rules = self.memory_provider.match_rules(
                    task_description=task.description,
                    user_id=getattr(task, "user_id", None) or "default",
                    role=self.role_id,
                    max_rules=5,
                )
            else:
                rule_strings = self.memory_provider.get_rules(
                    user_id=getattr(task, "user_id", None) or "default",
                    context={"task": task.description, "role": self.role_id},
                )
                raw_rules = []
                for rs in rule_strings:
                    if isinstance(rs, str):
                        raw_rules.append(
                            {
                                "rule_type": "always",
                                "trigger": rs.lower(),
                                "action": rs,
                                "relevance_score": 0.0,
                                "rule_id": "",
                                "override": False,
                            }
                        )

            safe_rules = self._validate_injected_rules(raw_rules)
            self._injected_rules = safe_rules
            self._rules_applied = [r.get("rule_id", r.get("action", "")[:50]) for r in safe_rules]
        except (AttributeError, KeyError, RuntimeError, ValueError) as e:
            logger.warning("Rule injection from provider failed: %s", e)
            self._injected_rules = []

    def _validate_injected_rules(self, rules: list[dict]) -> list[dict]:
        """Sanitize rules before prompt injection to prevent prompt injection attacks.

        Two-layer defense:
        1. InputValidator check on rule text + Unicode NFKC normalization + length limit
        2. Length check in format_rules_as_prompt() (handled by MCEAdapter)

        Args:
            rules: List of rule dicts from match_rules()

        Returns:
            List of validated rule dicts (suspicious rules silently skipped)
        """
        safe_rules = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue

            action = rule.get("action", "")
            trigger = rule.get("trigger", "")

            if isinstance(action, str):
                action = unicodedata.normalize("NFKC", action)
                rule["action"] = action
            if isinstance(trigger, str):
                trigger = unicodedata.normalize("NFKC", trigger)
                rule["trigger"] = trigger

            if len(action) > _MAX_RULE_TEXT_LENGTH:
                rule["action"] = action[:_MAX_RULE_TEXT_LENGTH]
            if len(trigger) > _MAX_RULE_TEXT_LENGTH:
                rule["trigger"] = trigger[:_MAX_RULE_TEXT_LENGTH]

            if self._validator:
                try:
                    action_valid = self._validator.validate_task(action).valid
                    trigger_valid = self._validator.validate_task(trigger).valid if trigger else True
                    if not action_valid or not trigger_valid:
                        logger.warning(
                            "Skipping suspicious rule: action_valid=%s, trigger_valid=%s", action_valid, trigger_valid
                        )
                        continue
                except (ValueError, AttributeError):
                    pass

            safe_rules.append(rule)

        return safe_rules

    def _check_forbid_violations(self, result: WorkerResult) -> list[dict[str, str]]:
        """
        Post-processing check: verify forbid rules were not violated in output.

        Short-term: annotate violations as warnings (no auto-retry).
        Mid-term: auto-retry with enhanced prompt on forbid violation.

        Args:
            result: Worker execution result

        Returns:
            List of violation dicts with rule_id and description
        """
        violations = []
        forbid_rules = [r for r in self._injected_rules if isinstance(r, dict) and r.get("rule_type") == "forbid"]

        if not forbid_rules or not result.output:
            return violations

        output_text = result.output if isinstance(result.output, str) else str(result.output)
        output_lower = output_text.lower()

        for rule in forbid_rules:
            trigger = rule.get("trigger", "").lower()
            action = rule.get("action", "").lower()
            rule_id = rule.get("rule_id", "unknown")

            if trigger and trigger in output_lower:
                violations.append(
                    {
                        "rule_id": rule_id,
                        "trigger": trigger,
                        "action": action,
                        "severity": "high" if rule.get("override") else "medium",
                        "message": f"Output may violate forbid rule '{rule_id}': trigger '{trigger}' found in output",
                    }
                )

        return violations

    def get_briefing_summary(self) -> dict[str, Any]:
        """
        Get agent briefing summary.

        Returns:
            Briefing summary dictionary
        """
        if not self._briefing:
            return {"status": "unavailable", "role": self.role_id}

        try:
            return {
                "status": "available",
                "role": self.role_id,
                "rules_count": len(self._briefing.get_rules()),
            }
        except (AttributeError, KeyError):
            return {"status": "error", "role": self.role_id}

    def export_briefing(self, output_dir: str = "output/briefings") -> str | None:
        """
        Export agent briefing to file.

        Args:
            output_dir: Output directory path

        Returns:
            File path if successful, None otherwise
        """
        if not self._briefing:
            return None

        try:
            import os

            os.makedirs(output_dir, exist_ok=True)

            safe_role = _SAFE_FILENAME_RE.sub("_", self.role_id)
            output_path = os.path.join(output_dir, f"{safe_role}_briefing.json")

            return self._briefing.export_briefing(output_path)
        except (OSError, AttributeError, KeyError) as e:
            logger.warning("Failed to export briefing for %s: %s", self.role_id, e)
            return None

    def compress_to_briefing(self) -> AgentBriefingOutput:
        """
        Compress current execution result into a briefing for the next Agent.

        Implements the latent-briefing pattern: instead of passing full message
        history between Agents, pass a compressed state with key decisions,
        pending items, and applied rules.

        Returns:
            AgentBriefingOutput: Compressed state for inter-Agent handoff
        """
        if not self._last_result:
            return AgentBriefingOutput()

        output_text = ""
        if isinstance(self._last_result.output, dict):
            output_text = self._last_result.output.get("finding_summary", "")
        elif isinstance(self._last_result.output, str):
            output_text = self._last_result.output[:500]

        confidence = 0.0
        if self._confidence_scorer and output_text:
            try:
                score = self._confidence_scorer.score_response(output_text)
                confidence = score.overall_score
            except (ValueError, AttributeError, RuntimeError):
                confidence = 0.5

        return AgentBriefingOutput(
            task_summary=self._last_result.task_id if hasattr(self._last_result, "task_id") else "",
            key_decisions=self._extract_decisions(output_text),
            pending_items=self._extract_pending(output_text),
            rules_applied=list(self._rules_applied),
            result_summary=output_text[:200] if output_text else "",
            confidence=confidence,
            assumptions=[],
        )

    def receive_briefing(self, briefing: AgentBriefingOutput):
        """
        Receive compressed state from a preceding Agent.

        Args:
            briefing: Compressed state from the previous Agent
        """
        self._received_briefing = briefing

    def _extract_decisions(self, text: str) -> list[str]:
        """Extract key decisions from output text."""
        decisions = []
        markers = ["decision:", "decided:", "chosen:", "selected:", "conclusion:"]
        for line in text.split("\n"):
            lower = line.strip().lower()
            for marker in markers:
                if marker in lower:
                    decisions.append(line.strip()[:100])
                    break
            if len(decisions) >= 5:
                break
        return decisions

    def _extract_pending(self, text: str) -> list[str]:
        """Extract pending items from output text."""
        pending = []
        markers = ["todo:", "pending:", "next:", "follow-up:", "remaining:"]
        for line in text.split("\n"):
            lower = line.strip().lower()
            for marker in markers:
                if marker in lower:
                    pending.append(line.strip()[:100])
                    break
            if len(pending) >= 5:
                break
        return pending

    def get_provider_status(self) -> dict[str, Any]:
        """
        Get status of all injected providers.

        Returns:
            Provider status dictionary
        """
        return {
            "worker_id": self.worker_id,
            "role_id": self.role_id,
            "cache": {
                "available": _is_available(self.cache_provider),
                "type": type(self.cache_provider).__name__ if self.cache_provider else "none",
            },
            "retry": {
                "available": _is_available(self.retry_provider),
                "type": type(self.retry_provider).__name__ if self.retry_provider else "none",
            },
            "monitor": {
                "available": _is_available(self.monitor_provider),
                "type": type(self.monitor_provider).__name__ if self.monitor_provider else "none",
            },
            "memory": {
                "available": _is_available(self.memory_provider),
                "type": type(self.memory_provider).__name__ if self.memory_provider else "none",
                "rules_injected": len(self._injected_rules),
            },
            "execution_guard": {
                "available": self.execution_guard is not None,
                "type": type(self.execution_guard).__name__ if self.execution_guard else "none",
            },
            "briefing": {
                "available": self._briefing is not None,
            },
        }


__all__ = ["EnhancedWorker", "AgentBriefingOutput"]
