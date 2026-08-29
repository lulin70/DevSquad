#!/usr/bin/env python3
"""PostDispatchPipeline — Post-dispatch step orchestration.

This module keeps the post-dispatch orchestration (``__init__`` and
``execute``) and a small set of execution helpers.  Step-specific logic
has been split into single-responsibility mixins under
``dispatch_steps_*_mixin.py``.

Pipeline steps covered:
  Step 8:  Collect worker results
  Step 10: Resolve consensus
  Step 11: Check permissions
  Step 12: Process memory pipeline
  Step 13: Learn skills
  Step 14: Five-axis consensus
  Step 15: Retrospective
  Step 18: Feedback loop
  Step 19: UE testing
  Step 20: Tech debt scan
  Step 21: Two-stage review gate
  Step 22: Severity router + auto-fix loop
  Step 23: Judge agent consolidation
"""

import logging
import time
from typing import Any, cast

from .dispatch_models import DispatchResult
from .dispatch_result_assembler import ResultAssembler
from .dispatch_services import MemoryPipelineService, MetricsService, PermissionService, SkillProposalService
from .dispatch_steps_consensus_mixin import PostDispatchConsensusMixin
from .dispatch_steps_feedback_mixin import PostDispatchFeedbackMixin
from .dispatch_steps_quality_mixin import PostDispatchQualityMixin
from .dispatch_steps_services_mixin import PostDispatchServicesMixin
from .dispatcher_base import ReportFormatterProtocol
from .event_bus import EventBus
from .output_validator import (
    OutputFinding,
    OutputValidationPipelineResult,
    OutputValidator,
)
from .severity_router import SeverityRouter
from .two_stage_review_gate import TwoStageReviewGate
from .ue_test_framework import UETestFramework

logger = logging.getLogger(__name__)


class PostDispatchPipeline(
    PostDispatchConsensusMixin,
    PostDispatchFeedbackMixin,
    PostDispatchQualityMixin,
    PostDispatchServicesMixin,
):
    """Post-dispatch pipeline containing steps 8-23.

    Receives all dependencies via ``__init__`` (composition pattern) instead of
    relying on mixin ``self.*`` attribute sharing.
    """

    def __init__(
        self,
        # Core components
        coordinator: Any,
        report_formatter: ReportFormatterProtocol,
        enterprise: Any,
        # Service instances
        metrics_service: MetricsService,
        permission_service: PermissionService,
        memory_pipeline: MemoryPipelineService,
        skill_service: SkillProposalService,
        # Feature flags
        enable_compression: bool = True,
        enable_permission: bool = True,
        enable_feedback_loop: bool | str = "auto",
        # V3.8 #2: Two-stage review gate
        enable_two_stage_review: bool = True,
        # V3.9-02: Stage 3 — Redesign audit (code simplicity check)
        enable_redesign_audit: bool = True,
        # V3.8 #3: Severity router + auto-fix loop
        enable_severity_router: bool = True,
        development_mode: bool = True,
        max_fix_iterations: int = 3,
        severity_router: Any = None,
        # V3.8 #4: Judge agent for finding consolidation
        judge_agent: Any = None,
        # Additional dependencies
        compressor: Any = None,
        usage_tracker: Any = None,
        retrospective_engine: Any = None,
        anchor_checker: Any = None,
        learned_rule_store: Any = None,
        llm_backend: Any = None,
        persist_dir: str = "",
        # Dispatcher reference (needed for FeedbackControlLoop and post_execution_processing)
        dispatcher: Any = None,
        # Event bus for decoupled communication
        event_bus: EventBus | None = None,
        # Result assembler for direct assembly calls
        result_assembler: ResultAssembler | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.report_formatter = report_formatter
        self.enterprise = enterprise
        self.metrics_service = metrics_service
        self.permission_service = permission_service
        self.memory_pipeline = memory_pipeline
        self.skill_service = skill_service
        self.enable_compression = enable_compression
        self.enable_permission = enable_permission
        self.enable_feedback_loop = enable_feedback_loop
        self.compressor = compressor
        self.usage_tracker = usage_tracker
        self.retrospective_engine = retrospective_engine
        self.learned_rule_store = learned_rule_store
        self.anchor_checker = anchor_checker
        self.llm_backend = llm_backend
        self.persist_dir = persist_dir
        self.dispatcher = dispatcher
        self.event_bus = event_bus or EventBus()
        self.result_assembler = result_assembler

        # Lazy-initialized frameworks
        self._ue_framework: UETestFramework | None = None
        self._debt_manager: Any = None

        # V3.8 #2: Two-stage review gate
        self.enable_two_stage_review = enable_two_stage_review
        # V3.9-02: Stage 3 — Redesign audit (enabled by default, can be disabled)
        self.enable_redesign_audit = enable_redesign_audit
        self.two_stage_review_gate = TwoStageReviewGate(
            enable_two_stage_review=enable_two_stage_review,
            enable_redesign_audit=enable_redesign_audit,
        )

        # V3.8 #3: Severity router
        self.enable_severity_router = enable_severity_router
        if severity_router is not None:
            # Use the injected router instance (advanced integration).
            self.severity_router = severity_router
        else:
            self.severity_router = SeverityRouter(
                event_bus=self.event_bus,
                development_mode=development_mode,
                max_fix_iterations=max_fix_iterations,
            )
        if self.enable_severity_router and severity_router is None:
            # Only auto-subscribe when we created the router ourselves
            # (an injected router is expected to be subscribed already).
            self.severity_router.subscribe()

        # V3.8 #4: Judge agent for finding consolidation
        self.judge_agent = judge_agent

        # V4.1.2 P1-6: OutputValidator (non-blocking, log-only for now).
        # V4.3.0 Phase 2 (P1-8): upgraded to blocking/non_blocking dual-mode
        # with DispatchAuditLogger integration.
        self.output_validator: OutputValidator | None = OutputValidator()
        self.output_validation_mode: str = "non_blocking"
        self.audit_logger: Any = None

    # ------------------------------------------------------------------
    # V4.1.2 P1-6 / V4.3.0 Phase 2 (P1-8): Output validation
    # ------------------------------------------------------------------

    def _validate_outputs(
        self,
        outputs: list[str] | list[dict[str, Any]],
    ) -> OutputValidationPipelineResult:
        """Scan worker outputs for risky content (V4.3.0 Phase 2 upgrade).

        Supports dual-mode input:
          - ``list[str]``: each string is a worker output (E2E-05 contract)
          - ``list[dict]``: each dict carries output/raw_output/content/report
            (backward compat with V4.1.2 P1-6 callers)

        Returns:
            :class:`OutputValidationPipelineResult` with ``blocked`` /
            ``findings`` / ``audit_logged`` / ``redacted_outputs``.

        Blocking semantics (decision point 2 of the 7-Role review):
          - ``blocking`` mode: ``blocked=True`` when any high-severity finding
            is raised. ``execute()`` should raise
            :class:`OutputValidationBlockedError` afterwards.
          - ``non_blocking`` mode (default): ``blocked=False`` always;
            findings are logged + audit-logged but dispatch continues.

        Fail-secure (decision point 3.2 of the 7-Role review):
          - Validator exception → ``blocked=True`` in blocking mode
          - Audit logger failure → blocking decision stands, ``audit_logged=False``
          - Config invalid → defaults to ``non_blocking`` + WARNING log
        """
        # Disabled validator → empty result
        if self.output_validator is None or not outputs:
            return OutputValidationPipelineResult()

        # Detect input mode from the first element
        is_string_mode = isinstance(outputs[0], str)

        all_findings: list[OutputFinding] = []
        redacted_outputs: list[str] = []
        audit_ok = True
        has_high = False

        for idx, item in enumerate(outputs):
            text = self._extract_text(item, is_string_mode)
            if not text:
                redacted_outputs.append("")
                continue

            worker_findings, redacted, worker_high, worker_audit_ok = (
                self._validate_one_output(text, idx)
            )
            if worker_findings is None:
                # Validator crashed in blocking mode → fail-secure return
                return OutputValidationPipelineResult(
                    blocked=True,
                    findings=all_findings,
                    audit_logged=False,
                    redacted_outputs=redacted_outputs,
                )

            all_findings.extend(worker_findings)
            redacted_outputs.append(redacted)
            has_high = has_high or worker_high
            audit_ok = audit_ok and worker_audit_ok

        blocked = has_high and self.output_validation_mode == "blocking"
        audit_logged = self._finalize_audit_log(
            blocked=blocked,
            has_high=has_high,
            audit_ok=audit_ok,
            all_findings=all_findings,
        )

        if all_findings:
            logger.info(
                "OutputValidator: %d finding(s) across %d worker output(s), blocked=%s",
                len(all_findings),
                len(outputs),
                blocked,
            )

        return OutputValidationPipelineResult(
            blocked=blocked,
            findings=all_findings,
            audit_logged=audit_logged,
            redacted_outputs=redacted_outputs,
        )

    @staticmethod
    def _extract_text(item: object, is_string_mode: bool) -> str:
        """Extract text from a worker output item based on detected mode.

        Args:
            item: Either a string (string mode) or a dict (compat mode).
            is_string_mode: True when the input list is ``list[str]``.

        Returns:
            The textual payload, or empty string if not extractable.
        """
        if is_string_mode:
            return item if isinstance(item, str) else ""
        return PostDispatchPipeline._extract_output_text(item) if isinstance(item, dict) else ""

    def _validate_one_output(
        self,
        text: str,
        idx: int,
    ) -> tuple[list[OutputFinding] | None, str, bool, bool]:
        """Validate a single worker output (V4.3.0 Phase 2 refactor).

        Args:
            text: The worker output text to scan.
            idx: Worker index (for logging/audit context).

        Returns:
            Tuple ``(findings, redacted_text, has_high, audit_ok)``.
            ``findings`` is ``None`` to signal "fail-secure blocking return"
            (validator crashed in blocking mode).
        """
        validator = self.output_validator
        if validator is None:  # defensive: caller should have short-circuited
            return [], "", False, True
        try:
            result = validator.validate(text)
        except Exception as exc:
            logger.warning(
                "OutputValidator: worker[%d] validator crashed: %s — fail-secure",
                idx,
                exc,
            )
            if self.output_validation_mode == "blocking":
                return None, "", False, False
            # non_blocking: skip this output but continue
            return [], "", False, True

        has_high = not result.valid
        audit_ok = self._audit_log_findings(idx, result.findings)

        return list(result.findings), result.redacted_text, has_high, audit_ok

    def _audit_log_findings(
        self,
        idx: int,
        findings: list[OutputFinding],
    ) -> bool:
        """Log + audit each finding for a single worker output.

        Args:
            idx: Worker index.
            findings: Findings list from the validator.

        Returns:
            ``True`` if all audit writes succeeded (or no audit logger
            attached), ``False`` otherwise.
        """
        audit_ok = True
        for finding in findings:
            if finding.severity == "high":
                logger.warning(
                    "OutputValidator: worker[%d] %s %s — %s",
                    idx,
                    finding.category,
                    finding.severity,
                    finding.redacted_text,
                )
                if not self._write_audit_event(
                    "output_validation_finding",
                    {
                        "worker_idx": idx,
                        "category": finding.category,
                        "severity": finding.severity,
                        "pattern_name": finding.pattern_name,
                        "redacted_text": finding.redacted_text,
                        "mode": self.output_validation_mode,
                    },
                ):
                    audit_ok = False
            else:
                logger.info(
                    "OutputValidator: worker[%d] %s %s — %s",
                    idx,
                    finding.category,
                    finding.severity,
                    finding.redacted_text,
                )
        return audit_ok

    def _write_audit_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        """Write a single audit log event (V4.3.0 Phase 2 helper).

        Args:
            event_type: Audit event type string.
            payload: Event payload dict.

        Returns:
            ``True`` on success or when no audit logger is attached,
            ``False`` on write failure.
        """
        if self.audit_logger is None:
            return True
        try:
            self.audit_logger.log_event(event_type, payload)
            return True
        except Exception as audit_exc:
            logger.warning(
                "OutputValidator: audit log write failed: %s",
                audit_exc,
            )
            return False

    def _finalize_audit_log(
        self,
        blocked: bool,
        has_high: bool,
        audit_ok: bool,
        all_findings: list[OutputFinding],
    ) -> bool:
        """Finalize audit log: write the blocked event if applicable.

        Args:
            blocked: Whether the dispatch is being blocked.
            has_high: Whether any high-severity finding exists.
            audit_ok: Cumulative audit write success so far.
            all_findings: All findings collected across workers.

        Returns:
            Final ``audit_logged`` flag.
        """
        if not blocked or self.audit_logger is None:
            return has_high and audit_ok and self.audit_logger is not None

        high_count = sum(1 for f in all_findings if f.severity == "high")
        if not self._write_audit_event(
            "output_validation_blocked",
            {
                "findings_count": len(all_findings),
                "high_severity_count": high_count,
                "mode": self.output_validation_mode,
            },
        ):
            return False
        return audit_ok

    def _apply_output_validation_config(self, config: dict[str, Any]) -> None:
        """Apply output validation config (V4.3.0 Phase 2 P1-8).

        Config priority (decision point 3 of the 7-Role review):
          - ``config["output_validation"]["mode"]`` (explicit config dict)
          - Default: ``non_blocking`` (fail-secure, low user friction)

        Invalid values degrade to ``non_blocking`` + WARNING log.

        Args:
            config: Config dict that may carry ``output_validation.mode``.
        """
        ov_config = config.get("output_validation", {}) if isinstance(config, dict) else {}
        mode = ov_config.get("mode", "non_blocking") if isinstance(ov_config, dict) else "non_blocking"

        if mode not in ("blocking", "non_blocking"):
            logger.warning(
                "OutputValidator: invalid mode %r — defaulting to non_blocking",
                mode,
            )
            mode = "non_blocking"

        self.output_validation_mode = mode

    @staticmethod
    def _extract_output_text(worker_result: dict[str, Any]) -> str:
        """Extract the textual payload from a worker result dict.

        Tries common output field names in order. Returns an empty
        string when no textual payload is found.
        """
        for key in ("output", "raw_output", "content", "report"):
            val = worker_result.get(key)
            if isinstance(val, str) and val:
                return val
        return ""

    # ------------------------------------------------------------------
    # Main execution entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        pre_result: Any,
        exec_result: Any,
        worker_results: list[dict[str, Any]],
        exec_errors: list[str],
        exec_timing: dict[str, float],
        start_time: float,
        phase: str,
        **kwargs: Any,
    ) -> DispatchResult:
        """Steps 9-23: post-processing, consensus, permissions, memory, assembly."""
        task_description = pre_result.task_description
        lang = pre_result.lang
        matched_roles = pre_result.matched_roles
        role_ids = pre_result.role_ids
        concern_packs = pre_result.concern_packs
        intent_match = pre_result.intent_match
        structured_goal = pre_result.structured_goal
        plan = pre_result.plan
        step1_time = pre_result.step1_time
        step2_time = pre_result.step2_time
        step3_time = pre_result.prep_timing.get("step3_time", step2_time)
        step4_time = pre_result.prep_timing.get("step4_time", step3_time)
        step5_time = pre_result.prep_timing.get("step5_time", step4_time)

        errors: list[str] = list(exec_errors)

        step6_time = exec_timing.get("step6_time", step5_time)
        step7_time = exec_timing.get("step7_time", step6_time)

        # Step 9: Post-execution processing (collect, slice, anchor check)
        scratchpad_summary, anchor_result, collection, post_errors, post_timing = self.dispatcher.hooks.post_execution_processing(
            worker_results, structured_goal
        )
        errors.extend(post_errors)
        step8_time = post_timing["step8_time"]

        # Notify listeners that execution processing completed
        self.event_bus.emit(
            "post_dispatch.execution_completed",
            worker_results=worker_results,
            structured_goal=structured_goal,
            scratchpad_summary=scratchpad_summary,
            errors=post_errors,
        )

        # Step 10: Resolve consensus
        mode = kwargs.get('mode', 'auto')
        consensus_records, compression_info = self._resolve_consensus(collection, mode)
        step9_time = time.time()

        # Step 11: Check permissions
        permission_checks = self._check_permissions(task_description, worker_results, consensus_records, **kwargs)
        step10_time = time.time()

        # Step 12: Process memory pipeline
        memory_stats, mem_errors = self._process_memory_pipeline(
            task_description, worker_results, lang, scratchpad_summary, role_ids
        )
        errors.extend(mem_errors)
        step11_time = time.time()

        # Step 13: Learn skills
        skill_proposals, skill_errors = self._learn_skills(task_description, worker_results, matched_roles, exec_result)
        errors.extend(skill_errors)
        step12_time = time.time()

        # Step 14: Run five-axis consensus
        five_axis_result = self._run_five_axis_consensus(task_description, worker_results, mode, exec_result)

        # Step 15: Run retrospective
        total_duration = time.time() - start_time
        retrospective_report = self._run_retrospective(
            task_description, worker_results, structured_goal, exec_result, total_duration
        )

        # Step 15.5: Pre-decision consensus gate (HC-2)
        # ConsensusEngine 前置介入关键决策点，在结果组装前进行共识检查
        consensus_gate_result = self._run_consensus_gate(
            task_description, worker_results
        )

        # Step 16: Assemble result
        step_timings = self._build_step_timings(
            step1_time, step2_time, step3_time, step4_time, step5_time,
            step6_time, step7_time, step8_time, step9_time, step10_time,
            step11_time, step12_time,
        )
        tenant_id = None
        if hasattr(self.dispatcher, '_get_current_tenant_id'):
            tenant_id = self.dispatcher._get_current_tenant_id()
        assert self.result_assembler is not None
        result = self.result_assembler.assemble(
            task_description=task_description,
            role_ids=role_ids,
            exec_result=exec_result,
            scratchpad_summary=scratchpad_summary,
            consensus_records=consensus_records,
            compression_info=compression_info,
            memory_stats=memory_stats,
            permission_checks=permission_checks,
            skill_proposals=skill_proposals,
            anchor_result=anchor_result,
            retrospective_report=retrospective_report,
            intent_match=intent_match,
            five_axis_result=five_axis_result,
            errors=errors,
            lang=lang,
            concern_packs=concern_packs,
            total_duration=total_duration,
            plan=plan,
            step_timings=step_timings,
            worker_results=worker_results,
            coordinator=self.coordinator,
            tenant_id=tenant_id,
            enterprise=self.enterprise,
        )

        # Lifecycle phase trace
        lifecycle_trace = self._build_lifecycle_trace(step_timings)
        result.details["lifecycle_trace"] = lifecycle_trace

        # HC-2: Apply consensus gate result
        if consensus_gate_result is not None:
            result.details["consensus_gate"] = {
                "outcome": consensus_gate_result.outcome,
                "approved": consensus_gate_result.approved,
                "needs_review": consensus_gate_result.needs_review,
                "reason": consensus_gate_result.reason,
            }
            if not consensus_gate_result.approved:
                result.success = False
                result.errors.append(
                    f"Consensus gate blocked: {consensus_gate_result.reason}"
                )
            if consensus_gate_result.needs_review:
                result.details["needs_review"] = True

        # Audit: dispatch complete
        self.enterprise.audit_dispatch_complete(result, **kwargs)

        # Step 17: Post-dispatch hooks (fire-and-forget via event bus)
        self.event_bus.emit(
            "post_dispatch.hooks",
            result=result,
            task=task_description,
            role_ids=role_ids,
            total_duration=total_duration,
        )

        # Step 18: Feedback loop
        roles = kwargs.get('roles')
        dry_run = kwargs.get('dry_run', False)
        result = cast(DispatchResult, self._run_feedback_loop(task_description, result, lang, roles, mode, dry_run, kwargs))

        # Step 19: UE testing (when tester role is involved)
        ue_test_plan = self._run_ue_testing(task_description, role_ids, worker_results, lang)
        if ue_test_plan:
            result.details["ue_test_plan"] = ue_test_plan

        # Step 20: Tech debt scan
        tech_debt_report = self._run_tech_debt_scan(task_description, worker_results)
        if tech_debt_report:
            result.details["tech_debt_report"] = tech_debt_report

        # Step 21: V3.8 #2 — Two-stage review gate
        # Runs after consensus + tech debt scan, before final completion.
        # Critical issues block progression (recorded in errors).
        two_stage_review_result = self._run_two_stage_review(
            plan, worker_results, structured_goal
        )
        if two_stage_review_result is not None:
            result.details["two_stage_review"] = two_stage_review_result.to_dict()
            result.two_stage_review = two_stage_review_result.to_dict()
            if not two_stage_review_result.passed:
                blocking_msgs = [
                    f"Two-stage review blocked: {i.description}"
                    for i in two_stage_review_result.blocking_issues
                ]
                errors.extend(blocking_msgs)
                result.errors = list(errors)
                result.success = False

        # Step 22: V3.8 #3 — Severity router + auto-fix loop
        # Processes findings from the review gate and worker outputs.
        # Only runs in development mode (production: collect-only).
        auto_fix_result = self._run_severity_router(
            worker_results, two_stage_review_result
        )
        if auto_fix_result is not None:
            result.details["auto_fix_result"] = auto_fix_result.to_dict()
            result.auto_fix_result = auto_fix_result.to_dict()

        # Step 23: V3.8 #4 — Judge agent consolidation
        # Consolidates/deduplicates findings from the two-stage review
        # gate and severity router before reporting. Runs only when a
        # JudgeAgent is configured.
        judge_result = self._run_judge_consolidation(
            two_stage_review_result, auto_fix_result
        )
        if judge_result is not None:
            result.details["judge_result"] = judge_result.to_dict()
            result.judge_result = judge_result.to_dict()

        # Prometheus: record dispatch end (duration + tasks_in_progress)
        self.metrics_service.safe_record(lambda m: (
            m.dispatch_histogram.labels(mode=mode).observe(total_duration),
            m.dispatch_counter.labels(mode=mode, role_count=str(len(role_ids))).inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).dec(),
        ))

        # Multi-tenant context cleanup
        self.enterprise.clear_tenant_context(pre_result.tenant_ctx)

        return result

    # ------------------------------------------------------------------
    # Step 8: Collect worker results
    # ------------------------------------------------------------------

    def _collect_worker_results(self, exec_result: Any) -> tuple[list[dict[str, Any]], float, float]:
        """Collect worker results from execution result into standardized dicts."""
        step6_time = time.time()
        worker_results: list[dict[str, Any]] = []
        for r in exec_result.results:
            role_id = r.worker_id.split("-")[0] if "-" in r.worker_id else r.worker_id
            from .models import ROLE_REGISTRY

            rdef = ROLE_REGISTRY.get(role_id)
            role_name = rdef.name if rdef else role_id
            worker_results.append(
                {
                    "worker_id": r.worker_id,
                    "role_id": role_id,
                    "role_name": role_name,
                    "task_id": r.task_id,
                    "success": r.success,
                    "output": (r.output.get("finding_summary", "") if isinstance(r.output, dict) else str(r.output))
                    if r.output
                    else None,
                    "error": r.error,
                    # V4.5.9 (DESIGN §6): user-visible gather-executor evidence.
                    "executor": (r.output.get("executor", "gather") if isinstance(r.output, dict) else "gather"),
                }
            )
        step7_time = time.time()
        return worker_results, step6_time, step7_time

    # ------------------------------------------------------------------
    # Result building helpers
    # ------------------------------------------------------------------

    def _build_step_timings(
        self, step1: float, step2: float, step3: float, step4: float, step5: float,
        step6: float, step7: float, step8: float, step9: float, step10: float,
        step11: float, step12: float,
    ) -> dict[str, float]:
        """Build step timings dict from absolute timestamps."""
        names = ["analyze", "warmup", "plan", "spawn", "execute", "collect",
                 "consensus", "compress", "permission", "memory", "skillify"]
        times = [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10, step11, step12]
        return {name: round(times[i + 1] - times[i], 3) for i, name in enumerate(names)}

    def _build_lifecycle_trace(self, step_timings: dict[str, float]) -> dict[str, Any]:
        """Build lifecycle phase trace from step timings.

        Maps dispatch pipeline steps to lifecycle phases (P1-P11),
        aggregating timing per phase for observability.
        """
        step_to_lifecycle = {
            "analyze": "P1_Requirements",
            "warmup": "P2_Architecture",
            "plan": "P3_Implementation",
            "spawn": "P3_Implementation",
            "execute": "P3_Implementation",
            "collect": "P4_Review",
            "consensus": "P4_Review",
            "compress": "P5_Integration",
            "permission": "P6_Security",
            "memory": "P5_Integration",
            "skillify": "P8_Optimization",
        }

        phase_durations: dict[str, float] = {}
        phase_steps: dict[str, list[str]] = {}
        for step_name, duration in step_timings.items():
            phase = step_to_lifecycle.get(step_name, "P10_Delivery")
            phase_durations[phase] = phase_durations.get(phase, 0.0) + duration
            phase_steps.setdefault(phase, []).append(step_name)

        return {
            "lifecycle_phases": phase_durations,
            "phase_steps": phase_steps,
            "mapping_version": "1.0",
        }

    def _build_summary(self, task: str, roles: list[str], exec_result: Any, sp_summary: str) -> str:
        """Build execution summary."""
        return self.report_formatter.build_summary(task, roles, exec_result, sp_summary)
