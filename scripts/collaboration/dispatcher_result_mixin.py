"""Dispatcher result-enrichment mixin.

V4.9.0: the two result-enrichment helpers were extracted out of
``dispatcher.py`` to keep the module under the 800-LOC ceiling
(``docs/audits/dispatcher_size_baseline.json``, release-blocking gate).

Both helpers share the same concern — decorate a ``DispatchResult`` with
metadata and activate the anti-ghost modules — so they live together here
instead of inside the core orchestration module.
"""

import contextlib
import logging
from typing import Any

from .dispatch_models import DispatchResult
from .dispatcher_base import DispatcherBase
from .models import GitContext, WorkflowStep, WorkflowTrace

logger = logging.getLogger(__name__)


class DispatcherResultMixin(DispatcherBase):
    """Result enrichment for early-return and success paths."""

    def _enrich_early_return_result(
        self,
        early_result: DispatchResult,
        task_description: str,
        permission_result_dict: dict[str, Any] | None,
        git_context: GitContext | None,
        output_style: str | None,
        approval_callback: Any | None,
    ) -> DispatchResult:
        """Enrich early-return result with metadata and activate anti-ghost modules.

        V4.9.0: Extracted from dispatch() to reduce complexity.
        """
        # V4.4.4: Restore original task_description (without git context).
        early_result.task_description = task_description
        if permission_result_dict is not None:
            early_result.permission_result = permission_result_dict
        self._attach_audit_entries(early_result)
        # V4.4.4: Populate WorkflowTrace even on early_return / dry_run
        # (anti-ghost: trace is present but empty for dry_run).
        self._populate_workflow_trace(early_result, dry_run=True)
        # V4.4.4: Store git_context in result (anti-ghost).
        if git_context is not None:
            early_result.git_context = git_context
        # V4.5.0: Apply OutputStyle + activate SkillProvider (anti-ghost).
        if output_style is not None:
            self.report_formatter.format_report(early_result, output_style=output_style)
        with contextlib.suppress(Exception):
            self.skill_registry.discover()
        # V4.5.1: Activate Approval Gate (anti-ghost: _call_counter_er > 0).
        self._activate_approval_gate(early_result, approval_callback)
        # V4.5.1: Activate Connector Framework (anti-ghost: _call_counter_er > 0).
        self._activate_connector(early_result)
        # V4.5.4 P12.3: Activate ModuleFiber + Coeffect (anti-ghost).
        # Best-effort — never let activation errors break the early-return path.
        try:
            self._activate_v454_modules(early_result, task_description)
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as v454_err:
            logger.debug("early_return _activate_v454_modules best-effort: %s", v454_err)
        return early_result

    def _enrich_success_result(
        self,
        result: DispatchResult,
        task_description: str,
        permission_result_dict: dict[str, Any] | None,
        git_context: GitContext | None,
        output_style: str | None,
        approval_callback: Any | None,
        dry_run: bool,
    ) -> DispatchResult:
        """Enrich successful result with metadata and activate anti-ghost modules.

        V4.9.0: Extracted from dispatch() to reduce complexity.
        """
        if permission_result_dict is not None:
            result.permission_result = permission_result_dict

        # V4.4.0: Activate 5 enhancement modules (anti-ghost + risk report).
        self._activate_v440_modules(result, task_description)

        # V4.4.4: Populate WorkflowTrace (anti-ghost: always set, even if empty).
        self._populate_workflow_trace(result, dry_run)

        # V4.4.4: Store git_context in result (anti-ghost: always set when provided).
        if git_context is not None:
            result.git_context = git_context

        # V4.4.4: Restore original task_description (without git context section).
        if git_context is not None:
            result.task_description = task_description

        # V4.5.0: Apply OutputStyle via ReportFormatter (anti-ghost: format_report called).
        if output_style is not None:
            self.report_formatter.format_report(result, output_style=output_style)

        # V4.5.0: Invoke SkillProvider discover (anti-ghost: skill provider activated).
        with contextlib.suppress(Exception):
            self.skill_registry.discover()

        # V4.5.1: Activate Approval Gate (anti-ghost: _call_counter_er > 0).
        self._activate_approval_gate(result, approval_callback)
        # V4.5.1: Activate Connector Framework (anti-ghost: _call_counter_er > 0).
        self._activate_connector(result)
        # V4.5.4 P12.3: Activate ModuleFiber + Coeffect (anti-ghost).
        # Best-effort — never let activation errors break the sync success path.
        try:
            self._activate_v454_modules(result, task_description)
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as v454_err:
            logger.debug("sync _activate_v454_modules best-effort: %s", v454_err)

        return result

    def _inject_git_context(
        self,
        git_context: GitContext,
        task_description: str,
    ) -> str:
        """V4.4.4: Inject GitContext into Coordinator prompt + Scratchpad.

        Appends the Git context prompt section to the task description so
        the Coordinator (and downstream Workers) see the current branch /
        recent commits / open issues. Also writes a DECISION entry to the
        Scratchpad so the git context is searchable in the dispatch history.

        Args:
            git_context: Populated GitContext to inject.
            task_description: Original task description.

        Returns:
            Augmented task description with the Git context section appended.
        """
        from .models import EntryType, ScratchpadEntry

        section = git_context.to_prompt_section()
        # Write a DECISION entry to the Scratchpad (Branch-as-Context).
        entry = ScratchpadEntry(
            worker_id="coordinator",
            role_id="coordinator",
            entry_type=EntryType.DECISION,
            content=(
                f"Git Context: branch={git_context.branch}, "
                f"recent_commits={git_context.recent_commits[:3]}, "
                f"open_issues={git_context.open_issues[:3]}"
            ),
            confidence=1.0,
            tags=["git-context", "v4.4.4"],
        )
        self.scratchpad.write(entry)
        # Augment the task description with the git context section so the
        # Coordinator prompt includes "## Git Context".
        return f"{task_description}\n\n{section}"

    def _populate_workflow_trace(
        self,
        result: DispatchResult,
        dry_run: bool,
    ) -> None:
        """V4.4.4: Populate WorkflowTrace on the dispatch result (anti-ghost).

        Builds a ``WorkflowTrace`` from the dispatch execution and attaches
        it to ``result.workflow_trace``. Always sets a trace (even if empty
        for dry_run) so the report formatter renders the section and the
        module-level ``_call_counter_er`` is incremented (anti-ghost).

        Args:
            result: The DispatchResult to attach the trace to.
            dry_run: Whether this was a dry_run (no worker steps).
        """
        # Decomposition tree: one node per matched role.
        decomposition_tree: list[dict] = []
        for role_id in result.matched_roles:
            decomposition_tree.append(
                {
                    "task": f"{role_id} analysis",
                    "roles": [role_id],
                    "subtasks": [],
                }
            )

        # Steps: one per worker result (skipped on dry_run).
        steps: list[WorkflowStep] = []
        if not dry_run:
            for wr in result.worker_results:
                role_id = wr.get("role_id", wr.get("role", "unknown"))
                agent_id = wr.get("agent_id", f"agent-{role_id}-unknown")
                status = "success" if wr.get("success") else "failed"
                duration_ms = float(wr.get("duration_ms", 0.0))
                steps.append(
                    WorkflowStep(
                        step_name=f"execute-{role_id}",
                        role_id=role_id,
                        agent_id=agent_id,
                        status=status,
                        duration_ms=duration_ms,
                        details=(wr.get("output", "") or "")[:120],
                    )
                )

        # Decision points: from consensus records.
        decision_points: list[dict] = []
        for cr in result.consensus_records:
            decision_points.append(
                {
                    "topic": cr.get("topic", ""),
                    "outcome": cr.get("outcome", ""),
                }
            )

        result.workflow_trace = WorkflowTrace(
            task_description=result.task_description,
            decomposition_tree=decomposition_tree,
            steps=steps,
            decision_points=decision_points,
        )
