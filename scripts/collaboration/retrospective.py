#!/usr/bin/env python3
"""
RetrospectiveEngine - V3.7.0 Independent Retrospective Engine

Automatically runs a retrospective after task completion:
1. Analyzes deviations from the original goal
2. Identifies redundant steps
3. Generates improvement suggestions
4. Stores conclusions in MemoryBridge for future task loading

Design Principles:
- No LLM calls: Pure algorithmic analysis
- Triggered automatically on task completion
- Conclusions stored as RETROSPECTIVE memory type
- Next similar task auto-loads historical retrospectives
"""

import logging
from datetime import datetime
from typing import Any

from .models import (
    AnchorResult,
    DeviationRecord,
    LearnedRule,
    RetrospectiveReport,
    StructuredGoal,
)

logger = logging.getLogger(__name__)


class RetrospectiveEngine:
    """
    Independent retrospective engine that runs after task completion.

    Usage:
        engine = RetrospectiveEngine(memory_bridge=bridge)
        report = engine.run(goal=structured_goal, anchor_history=checker.check_history)
        print(report.to_markdown())
    """

    MEMORY_TYPE_STR = "retrospective"

    def __init__(self, memory_bridge: Any = None):
        self._memory_bridge = memory_bridge

    def run(
        self,
        goal: StructuredGoal,
        anchor_history: list[AnchorResult],
        worker_outputs: dict[str, str] | None = None,  # noqa: ARG002
        task_duration_seconds: float = 0.0,  # noqa: ARG002
    ) -> RetrospectiveReport:
        """
        Run a retrospective analysis on a completed task.

        Args:
            goal: The original structured goal.
            anchor_history: History of anchor check results during execution.
            worker_outputs: Optional dict of role_id -> output text.
            task_duration_seconds: Total task execution time.

        Returns:
            RetrospectiveReport with deviations, improvements, and summary.
        """
        deviations = self._analyze_deviations(goal, anchor_history)
        redundant = self._find_redundant_steps(anchor_history)
        improvements = self._generate_improvements(deviations, anchor_history, goal)
        summary = self._build_summary(goal, deviations, improvements, anchor_history)

        drift_count = sum(1 for a in anchor_history if not a.aligned)

        report = RetrospectiveReport(
            task_goal=goal.original_description,
            goal_id=goal.goal_id,
            deviations=deviations,
            redundant_steps=redundant,
            improvements=improvements,
            anchor_check_count=len(anchor_history),
            anchor_drift_count=drift_count,
            final_coverage=goal.overall_coverage,
            summary=summary,
            created_at=datetime.now().isoformat(),
        )

        self._store_report(report, goal)

        logger.info(
            "Retrospective complete: %d deviations, %d improvements, coverage=%.0f%%",
            len(deviations),
            len(improvements),
            goal.overall_coverage * 100,
        )

        return report

    def _analyze_deviations(
        self,
        goal: StructuredGoal,
        anchor_history: list[AnchorResult],
    ) -> list[DeviationRecord]:
        deviations = []
        for item in goal.items:
            if item.status.value in ("pending", "partially_covered"):
                deviations.append(
                    DeviationRecord(
                        step_description=item.description,
                        deviation_type="goal_uncovered",
                        reason=f"Goal item '{item.description}' was only {item.coverage_score:.0%} covered",
                        impact="Partial delivery - user requirement not fully met",
                        suggestion=f"Ensure next task explicitly addresses: {item.description}",
                    )
                )

        drift_events = [a for a in anchor_history if not a.aligned]
        if drift_events:
            worst = max(drift_events, key=lambda a: a.drift_score)
            deviations.append(
                DeviationRecord(
                    step_description=f"Anchor check at {worst.checked_at}",
                    deviation_type="goal_drift",
                    reason=f"Maximum drift score: {worst.drift_score:.0%} (trigger: {worst.trigger.value})",
                    impact="Work may have been done on items outside the original scope",
                    suggestion="Add intermediate anchor checks to catch drift earlier",
                )
            )

        consecutive_drifts = 0
        max_consecutive = 0
        for a in anchor_history:
            if not a.aligned:
                consecutive_drifts += 1
                max_consecutive = max(max_consecutive, consecutive_drifts)
            else:
                consecutive_drifts = 0
        if max_consecutive >= 3:
            deviations.append(
                DeviationRecord(
                    step_description=f"{max_consecutive} consecutive drift checks",
                    deviation_type="sustained_drift",
                    reason=f"Task drifted for {max_consecutive} consecutive anchor checks",
                    impact="Significant effort spent on off-goal work",
                    suggestion="Break task into smaller sub-tasks with more frequent anchor checks",
                )
            )

        return deviations

    def _find_redundant_steps(self, anchor_history: list[AnchorResult]) -> list[str]:
        redundant: list[str] = []
        seen_triggers: dict[str, AnchorResult] = {}
        for a in anchor_history:
            key = a.trigger.value
            if key in seen_triggers:
                prev = seen_triggers[key]
                if a.coverage <= prev.coverage and a.aligned and prev.aligned:
                    redundant.append(
                        f"Anchor at {a.checked_at} ({a.trigger.value}): "
                        f"coverage {a.coverage:.0%} did not improve from previous {prev.coverage:.0%}"
                    )
            seen_triggers[key] = a
        return redundant

    def _generate_improvements(
        self,
        deviations: list[DeviationRecord],
        anchor_history: list[AnchorResult],
        goal: StructuredGoal,
    ) -> list[str]:
        improvements = []

        deviation_types = {d.deviation_type for d in deviations}
        if "goal_uncovered" in deviation_types:
            improvements.append("Decompose task into smaller sub-tasks, each mapping to specific goal items")
        if "goal_drift" in deviation_types:
            improvements.append("Add anchor checks at direction-change points to catch drift earlier")
        if "sustained_drift" in deviation_types:
            improvements.append("Implement auto-correction: when drift exceeds threshold, pause and re-align")

        if anchor_history:
            first_drift = next((a for a in anchor_history if not a.aligned), None)
            if first_drift:
                improvements.append(
                    f"First drift detected at {first_drift.trigger.value} - "
                    f"consider adding a pre-check before this trigger point"
                )

        uncovered = goal.uncovered_items
        if uncovered:
            improvements.append(
                f"Prioritize these uncovered goals in next iteration: "
                f"{', '.join(i.description[:40] for i in uncovered[:3])}"
            )

        if not improvements:
            improvements.append("Task well-executed. Maintain current process for similar tasks.")

        return improvements

    def _build_summary(
        self,
        goal: StructuredGoal,
        deviations: list[DeviationRecord],
        improvements: list[str],
        anchor_history: list[AnchorResult],
    ) -> str:
        total = len(anchor_history)
        drifts = sum(1 for a in anchor_history if not a.aligned)
        coverage = goal.overall_coverage

        if not deviations:
            return (
                f"Task completed with full goal alignment. "
                f"Coverage: {coverage:.0%}, Anchor checks: {total}, Drifts: {drifts}. "
                f"No deviations detected."
            )

        severity_counts: dict[str, int] = {}
        for d in deviations:
            severity_counts[d.deviation_type] = severity_counts.get(d.deviation_type, 0) + 1

        parts = [f"Coverage: {coverage:.0%}, Anchor checks: {total}, Drifts: {drifts}."]
        parts.append(f"Deviations: {len(deviations)} ({', '.join(f'{v}x{k}' for k, v in severity_counts.items())}).")
        parts.append(f"Improvements: {len(improvements)} suggestions generated.")

        return " ".join(parts)

    def _store_report(self, report: RetrospectiveReport, goal: StructuredGoal) -> None:
        if self._memory_bridge is None:
            logger.debug("No MemoryBridge configured, retrospective not persisted")
            return

        try:
            from .memory_bridge import AnalysisCase, MemoryType

            analysis = AnalysisCase(
                id=f"retro_{goal.goal_id}",
                problem=f"Retrospective: {goal.original_description[:60]}",
                context=report.summary,  # type: ignore[arg-type]
                root_cause="; ".join(d.reason for d in report.deviations[:3]) if report.deviations else "No deviations",
                solutions=report.improvements,
                status="completed",
            )
            writer = getattr(self._memory_bridge, "writer", None)
            if writer and hasattr(writer, "write_analysis"):
                writer.write_analysis(analysis)
            else:
                self._memory_bridge.store.save(MemoryType.ANALYSIS, report.to_dict())
            logger.info("Retrospective report stored in MemoryBridge (goal_id=%s)", goal.goal_id)
        except (AttributeError, RuntimeError, ValueError, TypeError) as e:
            logger.warning("Failed to store retrospective report: %s", e)

    def load_historical(
        self,
        task_description: str,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Load historical retrospective reports similar to a task description.

        Args:
            task_description: The task description to match against history.
            limit: Maximum number of historical records to return. Defaults to 3.

        Returns:
            List of historical memory content dictionaries, or an empty list
            when no memory bridge is configured or no matches are found.
        """
        if self._memory_bridge is None:
            return []

        try:
            from .memory_bridge import MemoryQuery

            query = MemoryQuery(
                query_text=task_description,
                limit=limit,
            )
            result = self._memory_bridge.recall(query)
            if result and hasattr(result, "memories") and result.memories:
                return [
                    m.content if isinstance(m.content, dict) else {"summary": str(m.content)[:200]}
                    for m in result.memories[:limit]
                ]
            return []
        except (ImportError, AttributeError, RuntimeError, ValueError) as e:
            logger.warning("Failed to load historical retrospectives: %s", e)
            return []

    def extract_learned_rules(
        self,
        report: RetrospectiveReport,
        task_id: str = "",
    ) -> list[LearnedRule]:
        """Extract LearnedRule entries from a retrospective report (V3.10.0 Phase 4).

        Converts deviations and improvements into actionable rules with
        confidence scores. High-confidence rules (>=0.8) are auto-injected
        into future prompts; medium-confidence rules (0.5-0.8) enter the
        candidate pool.

        Args:
            report: The RetrospectiveReport from a completed/failed task.
            task_id: Source task identifier for traceability.

        Returns:
            List of LearnedRule entries (callers persist via LearnedRuleStore).
        """
        rules: list[LearnedRule] = []
        deviation_types = {d.deviation_type for d in report.deviations}

        if "goal_uncovered" in deviation_types:
            rules.append(LearnedRule(
                rule_text="Decompose tasks into smaller sub-tasks, each mapping to specific goal items, before dispatching to Workers",
                trigger_condition="task_decomposition",
                confidence=0.85,
                source_task_id=task_id,
            ))
        if "goal_drift" in deviation_types:
            rules.append(LearnedRule(
                rule_text="Add anchor checks at direction-change points to catch goal drift before it compounds",
                trigger_condition="anchor_check_scheduling",
                confidence=0.80,
                source_task_id=task_id,
            ))
        if "sustained_drift" in deviation_types:
            rules.append(LearnedRule(
                rule_text="When drift exceeds 3 consecutive checks, pause and re-align with original goal before continuing",
                trigger_condition="sustained_drift_threshold",
                confidence=0.90,
                source_task_id=task_id,
            ))

        if report.anchor_drift_count == 0 and report.deviations:
            rules.append(LearnedRule(
                rule_text="Anchor checks are not catching detected deviations — increase check frequency or add pre-execution anchors",
                trigger_condition="anchor_coverage_gap",
                confidence=0.65,
                source_task_id=task_id,
            ))

        if report.final_coverage < 0.5 and report.deviations:
            rules.append(LearnedRule(
                rule_text="Task coverage below 50% — verify goal decomposition is complete before Worker assignment",
                trigger_condition="low_coverage_detection",
                confidence=0.55,
                source_task_id=task_id,
            ))

        for imp in report.improvements[:2]:
            if imp.startswith("First drift") or imp.startswith("Prioritize"):
                continue
            rules.append(LearnedRule(
                rule_text=imp,
                trigger_condition="retrospective_improvement",
                confidence=0.60,
                source_task_id=task_id,
            ))

        logger.info(
            "Extracted %d LearnedRule entries from retrospective (task_id=%s, deviations=%d)",
            len(rules),
            task_id or "unknown",
            len(report.deviations),
        )
        return rules


def _tokenize_simple(text: str) -> list[str]:
    import re

    tokens = re.findall(r"[a-zA-Z_]{2,}|[\u4e00-\u9fff]{2,}", text.lower())
    return tokens[:10]
