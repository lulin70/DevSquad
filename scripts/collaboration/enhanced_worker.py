#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import re
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .worker import Worker
from .models import TaskDefinition, WorkerResult, ROLE_REGISTRY

logger = logging.getLogger(__name__)

_SAFE_FILENAME_RE = re.compile(r'[^\w\-.]')


@dataclass
class AgentBriefingOutput:
    """Compressed state passed between Agents (latent-briefing pattern)."""
    task_summary: str = ""
    key_decisions: List[str] = field(default_factory=list)
    pending_items: List[str] = field(default_factory=list)
    rules_applied: List[str] = field(default_factory=list)
    result_summary: str = ""
    confidence: float = 0.0
    assumptions: List[str] = field(default_factory=list)


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
        """
        super().__init__(
            worker_id=worker_id,
            role_id=role_id,
            role_prompt=role_prompt,
            scratchpad=scratchpad,
            llm_backend=llm_backend,
            stream=stream,
        )

        self.cache_provider = cache_provider
        self.retry_provider = retry_provider
        self.monitor_provider = monitor_provider

        self._briefing = None
        self._briefing_loaded = False
        self._last_result: Optional[WorkerResult] = None
        self._confidence_scorer = None
        self._injected_rules: List[Dict[str, Any]] = []
        self._rules_applied: List[str] = []

        try:
            from .confidence_score import ConfidenceScorer
            self._confidence_scorer = ConfidenceScorer()
        except Exception:
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
        except Exception as e:
            logger.warning("Failed to load briefing for %s: %s", self.role_id, e)
            self._briefing = None

    def _do_work_with_briefing(self, task: TaskDefinition) -> WorkerResult:
        """
        Execute task with briefing context injection.

        Args:
            task: Task definition

        Returns:
            WorkerResult with briefing context
        """
        start_time = time.time()

        try:
            briefing_context = None
            if self._briefing:
                try:
                    briefing_context = self._briefing.get_briefing_context(task.description)
                except Exception as e:
                    logger.warning("Failed to get briefing context: %s", e)

            result = self._do_work(task)

            if briefing_context and result.output:
                if isinstance(result.output, dict):
                    result.output["briefing_context"] = briefing_context
                elif isinstance(result.output, str):
                    result.output = f"{briefing_context}\n\n{result.output}"

            duration = time.time() - start_time
            self._record_monitor(task, duration, success=True)

            return result

        except Exception as e:
            duration = time.time() - start_time
            self._record_monitor(task, duration, success=False)
            raise

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
            except Exception as e:
                logger.warning("Monitor recording failed: %s", e)

    def execute(self, task: TaskDefinition) -> WorkerResult:
        """
        Execute task with all enhanced features.

        Args:
            task: Task definition

        Returns:
            WorkerResult
        """
        if self.retry_provider and self.retry_provider.is_available():
            try:
                result = self.retry_provider.retry_with_fallback(
                    func=lambda: self._do_work_with_briefing(task),
                    max_attempts=3,
                    fallback=lambda: self._do_work(task),
                )
            except Exception:
                result = self._do_work(task)
        else:
            result = self._do_work_with_briefing(task)

        self._last_result = result

        if self._confidence_scorer and result.success and result.output:
            try:
                output_text = result.output if isinstance(result.output, str) else str(result.output)
                score = self._confidence_scorer.score_response(output_text)
                if isinstance(result.output, dict):
                    result.output["confidence"] = score.overall_score
                    result.output["confidence_factors"] = {
                        "completeness": score.completeness_score,
                        "certainty": score.certainty_score,
                        "specificity": score.specificity_score,
                    }
                    if score.overall_score < 0.7:
                        result.output["low_confidence_warning"] = (
                            f"Low confidence ({score.overall_score:.2f}). "
                            "Assumptions may need verification by subsequent agents."
                        )
            except Exception as e:
                logger.warning("Confidence scoring failed: %s", e)

        if self._injected_rules and result.success and result.output:
            violations = self._check_forbid_violations(result)
            if violations:
                if isinstance(result.output, dict):
                    result.output["rule_violations"] = violations

        return result

    def _check_forbid_violations(self, result: WorkerResult) -> List[Dict[str, str]]:
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
        forbid_rules = [r for r in self._injected_rules
                        if isinstance(r, dict) and r.get("rule_type") == "forbid"]

        if not forbid_rules or not result.output:
            return violations

        output_text = result.output if isinstance(result.output, str) else str(result.output)
        output_lower = output_text.lower()

        for rule in forbid_rules:
            trigger = rule.get("trigger", "").lower()
            action = rule.get("action", "").lower()
            rule_id = rule.get("rule_id", "unknown")

            if trigger and trigger in output_lower:
                violations.append({
                    "rule_id": rule_id,
                    "trigger": trigger,
                    "action": action,
                    "severity": "high" if rule.get("override") else "medium",
                    "message": f"Output may violate forbid rule '{rule_id}': "
                               f"trigger '{trigger}' found in output",
                })

        return violations

    def get_briefing_summary(self) -> Dict[str, Any]:
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
        except Exception:
            return {"status": "error", "role": self.role_id}

    def export_briefing(self, output_dir: str = "output/briefings") -> Optional[str]:
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

            safe_role = _SAFE_FILENAME_RE.sub('_', self.role_id)
            output_path = os.path.join(output_dir, f"{safe_role}_briefing.json")

            return self._briefing.export_briefing(output_path)
        except Exception as e:
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
            except Exception:
                confidence = 0.5

        return AgentBriefingOutput(
            task_summary=self._last_result.task_id if hasattr(self._last_result, 'task_id') else "",
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

    def _extract_decisions(self, text: str) -> List[str]:
        """Extract key decisions from output text."""
        decisions = []
        markers = ["decision:", "decided:", "chosen:", "selected:", "conclusion:"]
        for line in text.split('\n'):
            lower = line.strip().lower()
            for marker in markers:
                if marker in lower:
                    decisions.append(line.strip()[:100])
                    break
            if len(decisions) >= 5:
                break
        return decisions

    def _extract_pending(self, text: str) -> List[str]:
        """Extract pending items from output text."""
        pending = []
        markers = ["todo:", "pending:", "next:", "follow-up:", "remaining:"]
        for line in text.split('\n'):
            lower = line.strip().lower()
            for marker in markers:
                if marker in lower:
                    pending.append(line.strip()[:100])
                    break
            if len(pending) >= 5:
                break
        return pending

    def get_provider_status(self) -> Dict[str, Any]:
        """
        Get status of all injected providers.

        Returns:
            Provider status dictionary
        """
        return {
            "worker_id": self.worker_id,
            "role_id": self.role_id,
            "cache": {
                "available": self.cache_provider.is_available() if self.cache_provider else False,
                "type": type(self.cache_provider).__name__ if self.cache_provider else "none",
            },
            "retry": {
                "available": self.retry_provider.is_available() if self.retry_provider else False,
                "type": type(self.retry_provider).__name__ if self.retry_provider else "none",
            },
            "monitor": {
                "available": self.monitor_provider.is_available() if self.monitor_provider else False,
                "type": type(self.monitor_provider).__name__ if self.monitor_provider else "none",
            },
            "briefing": {
                "available": self._briefing is not None,
            },
        }


__all__ = ["EnhancedWorker", "AgentBriefingOutput"]
