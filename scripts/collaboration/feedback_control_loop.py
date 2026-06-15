#!/usr/bin/env python3
"""
FeedbackControlLoop - V3.7.0 Closed-Loop Iteration Engine

Implements a "Sense-Decide-Act-Feedback" closed-loop iteration mechanism
that continuously improves task execution quality through iterative refinement.

Design Principles:
- Quality-driven: Only iterate when quality falls below threshold
- Bounded iteration: Prevents infinite loops with max_iterations limit
- Thread-safe: Uses RLock for concurrent access
- Lightweight quality assessment: Algorithmic scoring without LLM calls
- Dry-run support: Plan iterations without actual dispatch

Usage:
    loop = FeedbackControlLoop(dispatcher, quality_gate=0.7, max_iterations=3)
    result = loop.run("Design secure auth system", roles=["architect", "security"])
    print(f"Completed in {loop.iteration_count} iterations")
"""

import logging
import threading
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackControlLoop:
    """
    Closed-loop feedback controller for iterative task improvement.

    Monitors dispatch results and automatically refines tasks when quality
    falls below the configured threshold. Implements the control theory
    pattern of sense-assess-adjust-execute.

    Attributes:
        quality_gate: Minimum quality score (0.0-1.0) to accept a result
        max_iterations: Maximum number of refinement iterations
        iteration_history: List of (iteration_num, quality_score, adjustment) tuples
    """

    DEFAULT_QUALITY_GATE = 0.7
    DEFAULT_MAX_ITERATIONS = 3

    def __init__(
        self,
        dispatcher,
        quality_gate: float = DEFAULT_QUALITY_GATE,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        llm_backend=None,
    ):
        """
        Initialize the feedback control loop.

        Args:
            dispatcher: MultiAgentDispatcher instance to use for task execution
            quality_gate: Minimum acceptable quality score (0.0-1.0). Default 0.7
            max_iterations: Maximum number of refinement attempts. Default 3
            llm_backend: Optional LLM backend for intelligent task refinement.
                        If None, falls back to algorithmic string concatenation.
        """
        self._dispatcher = dispatcher
        self._quality_gate = min(max(quality_gate, 0.0), 1.0)
        self._max_iterations = max(1, max_iterations)
        self._llm_backend = llm_backend
        self._lock = threading.RLock()
        self._iteration_history: list[dict[str, Any]] = []
        self._best_result = None
        self._best_quality = 0.0
        self._iteration_count = 0

    @property
    def quality_gate(self) -> float:
        """Current quality threshold."""
        return self._quality_gate

    @property
    def max_iterations(self) -> int:
        """Maximum allowed iterations."""
        return self._max_iterations

    @property
    def iteration_count(self) -> int:
        """Number of iterations executed in last run."""
        return self._iteration_count

    @property
    def iteration_history(self) -> list[dict[str, Any]]:
        """History of all iterations with quality scores."""
        return list(self._iteration_history)

    @property
    def best_result(self):
        """Best result achieved across all iterations."""
        return self._best_result

    @property
    def best_quality(self) -> float:
        """Highest quality score achieved."""
        return self._best_quality

    def run(self, task: str, roles: list[str] | None = None, mode: str = "auto", dry_run: bool = False, **kwargs):
        """
        Execute the feedback control loop.

        Runs the dispatch task and iteratively refines it until quality
        meets the threshold or maximum iterations are reached.

        Args:
            task: Task description to execute
            roles: Optional list of role IDs to use
            mode: Execution mode ("auto"/"parallel"/"sequential"/"consensus")
            dry_run: If True, only simulate without actual execution
            **kwargs: Additional arguments passed to dispatcher.dispatch()

        Returns:
            DispatchResult: Best result (highest quality or last iteration)
        """
        with self._lock:
            self._iteration_history.clear()
            self._best_result = None
            self._best_quality = 0.0
            self._iteration_count = 0

            current_task = task
            best_result = None
            best_quality = 0.0

            for iteration in range(self._max_iterations + 1):
                self._iteration_count = iteration + 1
                logger.info(
                    "Feedback loop iteration %d/%d (task: %.50s...)",
                    iteration + 1,
                    self._max_iterations + 1,
                    current_task,
                )

                if dry_run:
                    result = self._dry_run_dispatch(current_task, roles, mode)
                    quality = self._assess_quality(result)

                    iteration_record = {
                        "iteration": iteration + 1,
                        "quality": quality,
                        "passed": quality >= self._quality_gate,
                        "task_preview": current_task[:100],
                        "timestamp": datetime.now().isoformat(),
                    }
                    self._iteration_history.append(iteration_record)
                    best_result = result
                    best_quality = quality
                    break
                else:
                    result = self._dispatcher.dispatch(current_task, roles=roles, mode=mode, **kwargs)

                quality = self._assess_quality(result)

                iteration_record = {
                    "iteration": iteration + 1,
                    "quality": quality,
                    "passed": quality >= self._quality_gate,
                    "task_preview": current_task[:100],
                    "timestamp": datetime.now().isoformat(),
                }
                self._iteration_history.append(iteration_record)

                logger.info(
                    "Iteration %d: quality=%.2f (gate=%.2f) %s",
                    iteration + 1,
                    quality,
                    self._quality_gate,
                    "PASSED" if quality >= self._quality_gate else "FAILED",
                )

                if quality > best_quality:
                    best_quality = quality
                    best_result = result

                if quality >= self._quality_gate:
                    logger.info(
                        "Quality gate met at iteration %d (%.2f >= %.2f)", iteration + 1, quality, self._quality_gate
                    )
                    break

                if iteration < self._max_iterations:
                    adjustment = self._generate_adjustment(result, quality)
                    current_task = self._refine_task(current_task, adjustment)

                    iteration_record["adjustment"] = adjustment
                    iteration_record["refined_task"] = current_task[:100]

                    logger.info("Generated adjustment for iteration %d: %.80s...", iteration + 1, adjustment)

            self._best_result = best_result
            self._best_quality = best_quality

            return best_result

    def _dry_run_dispatch(self, task: str, roles: list[str] | None, mode: str):
        """Simulate a dispatch for dry-run mode."""
        from .dispatcher import DispatchResult

        return DispatchResult(
            success=True,
            task_description=task,
            matched_roles=roles or [],
            summary=f"[DRY RUN] Would dispatch: {task[:50]}",
            duration_seconds=0.0,
        )

    def _assess_quality(self, result) -> float:
        """
        Assess the quality of a dispatch result.

        Computes a quality score (0.0-1.0) based on multiple factors:
        - Success status (weight: 0.4)
        - Worker result coverage (weight: 0.3)
        - Consensus agreement (weight: 0.2)
        - Error presence (weight: -0.1)

        Args:
            result: DispatchResult to evaluate

        Returns:
            float: Quality score between 0.0 and 1.0
        """
        score = 0.0

        if not result:
            return 0.0

        success_score = 1.0 if result.success else 0.3
        score += success_score * 0.4

        worker_results = getattr(result, "worker_results", []) or []
        if worker_results:
            successful_workers = sum(1 for wr in worker_results if wr.get("success"))
            worker_ratio = successful_workers / len(worker_results)
            score += worker_ratio * 0.3
        else:
            score += 0.1

        consensus_records = getattr(result, "consensus_records", []) or []
        if consensus_records:
            approved = sum(1 for cr in consensus_records if cr.get("outcome") == "APPROVED")
            consensus_ratio = approved / len(consensus_records) if consensus_records else 0
            score += consensus_ratio * 0.2
        else:
            score += 0.1

        errors = getattr(result, "errors", []) or []
        if errors:
            error_penalty = min(len(errors) * 0.05, 0.15)
            score -= error_penalty

        return min(max(score, 0.0), 1.0)

    def _generate_adjustment(self, result, quality: float) -> str:
        """
        Generate adjustment suggestion based on failed result analysis.

        Analyzes failure patterns and produces actionable recommendations
        for task refinement.

        Args:
            result: DispatchResult that failed quality gate
            quality: Current quality score

        Returns:
            str: Adjustment suggestion to refine the task
        """
        adjustments = []

        worker_results = getattr(result, "worker_results", []) or []
        errors = getattr(result, "errors", []) or []

        failed_workers = [wr for wr in worker_results if not wr.get("success") and wr.get("error")]

        if failed_workers:
            failed_roles = set()
            for fw in failed_workers:
                role_id = fw.get("role_id", "unknown")
                failed_roles.add(role_id)

            if len(failed_roles) == 1:
                role = list(failed_roles)[0]
                adjustments.append(f"Add additional review from {role} role or simplify requirements for {role}")
            else:
                roles_str = ", ".join(sorted(failed_roles))
                adjustments.append(
                    f"Address failures in roles: {roles_str}. Consider breaking down task into smaller sub-tasks"
                )

        if errors:
            error_types = set()
            for err in errors[:5]:
                err_lower = err.lower()
                if "timeout" in err_lower or "time" in err_lower:
                    error_types.add("timeout")
                elif "permission" in err_lower or "auth" in err_lower:
                    error_types.add("permission")
                elif "memory" in err_lower or "resource" in err_lower:
                    error_types.add("resource")
                else:
                    error_types.add("general")

            if "timeout" in error_types:
                adjustments.append("Reduce task complexity or scope to prevent timeout")
            if "permission" in error_types:
                adjustments.append("Clarify permission requirements and constraints")
            if "resource" in error_types:
                adjustments.append("Optimize resource usage or reduce memory footprint")

        if not worker_results:
            adjustments.append("Task may be too vague. Add specific acceptance criteria and expected outputs")

        successful_workers = [wr for wr in worker_results if wr.get("success")]
        if successful_workers and failed_workers:
            success_count = len(successful_workers)
            total = len(worker_results)
            if success_count / total < 0.5:
                adjustments.append(
                    "Low success rate detected. Consider reducing number of roles or simplifying task scope"
                )

        if quality < 0.4:
            adjustments.append("Quality critically low. Recommend complete task reformulation with clearer objectives")
        elif quality < 0.6:
            adjustments.append(
                "Quality below acceptable level. Strengthen task description with examples and constraints"
            )

        if not adjustments:
            adjustments.append(
                "General refinement needed: Review outputs against original goals and add missing requirements"
            )

        return " | ".join(adjustments[:5])

    def _refine_task(self, task: str, adjustment: str) -> str:
        """
        Refine task by merging original task with adjustment suggestions.

        When an LLM backend is available, uses it to generate an intelligent
        reformulation. Otherwise falls back to simple string concatenation.

        Args:
            task: Original task description
            adjustment: Adjustment suggestion from _generate_adjustment()

        Returns:
            str: Refined task description with adjustment integrated
        """
        if self._llm_backend is not None:
            try:
                refined = self._llm_refine_task(task, adjustment)
                if refined and len(refined) > 10:
                    return refined
            except (ValueError, AttributeError, RuntimeError, ConnectionError) as e:
                logger.debug("LLM task refinement failed, falling back to concatenation: %s", e)

        # Fallback: simple concatenation
        refined = f"{task}\n\n[Iteration Feedback]\n{adjustment}"
        return refined

    def _llm_refine_task(self, task: str, adjustment: str) -> str:
        """
        Use LLM to intelligently refine a task based on feedback.

        Generates a reformulated task that incorporates the adjustment
        suggestions in a natural, coherent way.

        Args:
            task: Original task description
            adjustment: Adjustment suggestions from _generate_adjustment()

        Returns:
            str: LLM-refined task description
        """
        prompt = (
            "You are a task refinement assistant. Given an original task and feedback "
            "from a failed execution attempt, produce a refined task description that "
            "addresses the issues identified.\n\n"
            f"Original task:\n{task}\n\n"
            f"Execution feedback:\n{adjustment}\n\n"
            "Produce a refined task description that:\n"
            "1. Preserves the original intent and goals\n"
            "2. Incorporates the feedback to address identified issues\n"
            "3. Adds specific constraints or clarifications where needed\n"
            "4. Is clear and actionable for a multi-agent team\n\n"
            "Output ONLY the refined task description, no preamble."
        )

        if hasattr(self._llm_backend, 'generate'):
            return self._llm_backend.generate(prompt)
        elif hasattr(self._llm_backend, 'call'):
            return self._llm_backend.call(prompt)
        elif hasattr(self._llm_backend, 'chat'):
            response = self._llm_backend.chat([{"role": "user", "content": prompt}])
            if isinstance(response, dict):
                return response.get("content", response.get("text", ""))
            return str(response)
        else:
            raise ValueError(f"Unsupported LLM backend type: {type(self._llm_backend)}")

    def reset(self):
        """Reset all state for reuse."""
        with self._lock:
            self._iteration_history.clear()
            self._best_result = None
            self._best_quality = 0.0
            self._iteration_count = 0

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the last execution.

        Returns:
            Dict containing iteration count, quality scores, and history summary
        """
        with self._lock:
            if not self._iteration_history:
                return {
                    "iterations": 0,
                    "best_quality": 0.0,
                    "converged": False,
                    "history": [],
                }

            qualities = [h["quality"] for h in self._iteration_history]
            return {
                "iterations": self._iteration_count,
                "best_quality": round(self._best_quality, 3),
                "worst_quality": round(min(qualities), 3),
                "avg_quality": round(sum(qualities) / len(qualities), 3),
                "converged": any(h["passed"] for h in self._iteration_history),
                "converged_at_iteration": next((h["iteration"] for h in self._iteration_history if h["passed"]), None),
                "history": self._iteration_history,
            }
