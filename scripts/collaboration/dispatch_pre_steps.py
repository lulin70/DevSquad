#!/usr/bin/env python3
"""PreDispatchPipeline — Pre-dispatch step methods extracted from MultiAgentDispatcher.

This pipeline reduces the God Class by moving pre-dispatch pipeline step methods
(steps 0-7) into a separate module. Uses composition pattern: receives all
dependencies via __init__ instead of relying on mixin self.* attribute sharing.

Pipeline steps covered:
  Step 0: Multi-tenant context setup (delegated to EnterpriseFeature)
  Step 1: Language resolution
  Step 2: Input validation
  Step 3: Rule collection + CI context injection
  Step 4: Intent detection
  Step 5: Role matching
  Step 6: Security validation (concern packs + dry_run)
  Step 7: Execution preparation (warmup, prompts, plan, spawn, anchor, retrospective)
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from .dispatch_models import ROLE_TEMPLATES, DispatchResult
from .models import EntryType
from .scratchpad import ScratchpadEntry
from .user_friendly_error import make_user_friendly_error, translate_validation_result

logger = logging.getLogger(__name__)


@dataclass
class _PreDispatchResult:
    """Result container for PreDispatchPipeline.execute()."""
    task_description: str
    lang: str
    rule_collection: Any
    intent_match: Any
    matched_roles: list[dict[str, Any]]
    role_ids: list[str]
    concern_packs: Any
    concern_enhancements: dict[str, Any]
    plan: Any
    structured_goal: Any
    prep_timing: dict[str, float]
    step1_time: float
    step2_time: float
    tenant_ctx: Any = None
    early_return: DispatchResult | None = None


class PreDispatchPipeline:
    """Composition-based pre-dispatch pipeline.

    Receives all dependencies via __init__ instead of relying on mixin
    self.* attribute sharing with MultiAgentDispatcher.
    """

    def __init__(
        self,
        validator: Any,
        ci_feedback: Any,
        persist_dir: str,
        usage_tracker: Any,
        intent_mapper: Any,
        context_manager: Any,
        role_matcher: Any,
        semantic_matcher: Any,
        llm_backend: Any,
        concern_loader: Any,
        warmup_manager: Any,
        coordinator: Any,
        anchor_checker: Any,
        retrospective_engine: Any,
        enable_memory: bool,
        scratchpad: Any,
        enterprise: Any,
        resolve_language_fn: Any,
        analyze_task_fn: Any,
        lang: str = "auto",
    ) -> None:
        self.validator = validator
        self.ci_feedback = ci_feedback
        self.persist_dir = persist_dir
        self.usage_tracker = usage_tracker
        self.intent_mapper = intent_mapper
        self.context_manager = context_manager
        self.role_matcher = role_matcher
        self.semantic_matcher = semantic_matcher
        self.llm_backend = llm_backend
        self.concern_loader = concern_loader
        self.warmup_manager = warmup_manager
        self.coordinator = coordinator
        self.anchor_checker = anchor_checker
        self.retrospective_engine = retrospective_engine
        self.enable_memory = enable_memory
        self.scratchpad = scratchpad
        self.enterprise = enterprise
        self.resolve_language_fn = resolve_language_fn
        self.analyze_task_fn = analyze_task_fn
        self.lang = lang

        # Lazy-initialized caches
        self._rule_collector: Any | None = None
        self._std_template_cache: dict[str, Any] = {}

    def execute(
        self,
        task_description: str,
        roles: list[str] | None,
        _mode: str,
        dry_run: bool,
        start_time: float,
        _phase: str,
        **kwargs: Any,
    ):
        """Steps 0-7: tenant setup, validation, intent, roles, preparation."""
        # Step 0: Multi-tenant context setup
        tenant_ctx = self.enterprise.set_tenant_context(kwargs, start_time)
        if isinstance(tenant_ctx, DispatchResult):
            return self.make_early_pre_result(
                task_description, self.lang, None, tenant_ctx,
                step1_time=start_time, step2_time=start_time,
            )

        # Step 1: Resolve language
        lang = self.resolve_language_fn(self.lang)

        # Step 2: Validate input
        task_description, early_return = self.validate_input(task_description, roles, lang)
        if early_return:
            return self.make_early_pre_result(
                task_description, lang, tenant_ctx, early_return,
                step1_time=start_time, step2_time=start_time,
            )

        # RBAC pre-check
        rbac_denied = self.enterprise.check_rbac_access(kwargs, task_description, lang, start_time)
        if rbac_denied:
            return self.make_early_pre_result(
                task_description, lang, tenant_ctx, rbac_denied,
                step1_time=start_time, step2_time=start_time,
            )

        # Step 3: Collect rules and inject CI context
        task_description, rule_collection, early_return = self.collect_rules(task_description, lang)
        if early_return:
            return self.make_early_pre_result(
                task_description, lang, tenant_ctx, early_return,
                rule_collection=rule_collection,
                step1_time=start_time, step2_time=start_time,
            )

        step1_time = time.time()

        # Step 4: Detect intent
        intent_match = self.detect_intent(task_description, lang)

        # Audit: dispatch start
        self.enterprise.audit_dispatch_start(task_description, **kwargs)

        # Step 5: Match roles
        matched_roles = self.match_roles(task_description, roles)

        # Step 6: Validate roles and security (concern packs + dry_run)
        role_ids, concern_packs, concern_enhancements, early_return = self.validate_roles_and_security(
            task_description, matched_roles, lang, dry_run, start_time
        )
        if early_return:
            return self.make_early_pre_result(
                task_description, lang, tenant_ctx, early_return,
                rule_collection=rule_collection, intent_match=intent_match,
                matched_roles=matched_roles, role_ids=role_ids,
                concern_packs=concern_packs, concern_enhancements=concern_enhancements,
                step1_time=step1_time, step2_time=time.time(),
            )

        step2_time = time.time()

        # Step 7: Prepare execution (warmup, prompts, plan, spawn, anchor, retrospective load)
        plan, structured_goal, prep_timing = self.prepare_execution(
            task_description, matched_roles, lang, intent_match, rule_collection, concern_enhancements
        )

        return _PreDispatchResult(
            task_description=task_description,
            lang=lang,
            rule_collection=rule_collection,
            intent_match=intent_match,
            matched_roles=matched_roles,
            role_ids=role_ids,
            concern_packs=concern_packs,
            concern_enhancements=concern_enhancements,
            plan=plan,
            structured_goal=structured_goal,
            prep_timing=prep_timing,
            step1_time=step1_time,
            step2_time=step2_time,
            tenant_ctx=tenant_ctx,
            early_return=None,
        )

    def make_early_pre_result(
        self,
        task_description: str,
        lang: str,
        tenant_ctx: Any,
        early_return: DispatchResult,
        rule_collection: Any = None,
        intent_match: Any = None,
        matched_roles: list[dict[str, Any]] | None = None,
        role_ids: list[str] | None = None,
        concern_packs: Any = None,
        concern_enhancements: dict[str, Any] | None = None,
        step1_time: float = 0.0,
        step2_time: float = 0.0,
    ):
        """Create a _PreDispatchResult with early_return set, filling defaults."""
        return _PreDispatchResult(
            task_description=task_description,
            lang=lang,
            rule_collection=rule_collection,
            intent_match=intent_match,
            matched_roles=matched_roles or [],
            role_ids=role_ids or [],
            concern_packs=concern_packs,
            concern_enhancements=concern_enhancements or {},
            plan=None,
            structured_goal=None,
            prep_timing={},
            step1_time=step1_time,
            step2_time=step2_time,
            tenant_ctx=tenant_ctx,
            early_return=early_return,
        )

    def validate_input(
        self, task: str, roles: list[str] | None, lang: str
    ) -> tuple[str, DispatchResult | None]:
        """Validate task and roles input. Returns (sanitized_task, early_return)."""
        validator = self.validator
        task_result = validator.validate_task(task)
        if not task_result.valid:
            friendly = translate_validation_result(task_result.reason or "")
            return task, DispatchResult(
                success=False,
                task_description=task,
                matched_roles=[],
                worker_results=[],
                summary=friendly.message,
                errors=[friendly.format()],
                lang=lang,
            )
        task = task_result.sanitized_input or task

        if roles:
            roles_result = validator.validate_roles(roles)
            if not roles_result.valid:
                friendly = make_user_friendly_error("role_not_found")
                return task, DispatchResult(
                    success=False,
                    task_description=task,
                    matched_roles=[],
                    worker_results=[],
                    summary=friendly.message,
                    errors=[friendly.format()],
                    lang=lang,
                )

        warnings = validator.check_suspicious_patterns(task)
        if warnings:
            logger.warning("Suspicious patterns in task: %s", ", ".join(warnings))

        injection_warnings = validator.check_prompt_injection(task)
        if injection_warnings:
            logger.warning("Prompt injection patterns detected: %s", ", ".join(injection_warnings))

        return task, None

    def collect_rules(
        self, task: str, lang: str
    ) -> tuple[str, Any, DispatchResult | None]:
        """Collect rules via RuleCollector and inject CI context. Returns (task, rules, early_return)."""
        rule_collection = None
        try:
            from scripts.collaboration.rule_collector import RuleCollector

            if self._rule_collector is None:
                self._rule_collector = RuleCollector()
            rule_collection = self._rule_collector.process(task, lang)
            if rule_collection.rule_detected and not rule_collection.remaining_task:
                return task, rule_collection, DispatchResult(
                    success=True,
                    task_description=task,
                    matched_roles=[],
                    worker_results=[],
                    summary=rule_collection.message,
                    errors=[],
                    lang=lang,
                )
            if rule_collection.rule_detected:
                task = rule_collection.remaining_task
        except (ImportError, AttributeError, ValueError, KeyError) as e:
            logger.debug("RuleCollector not available: %s", e)

        if self.ci_feedback:
            self.inject_ci_context(task)

        return task, rule_collection, None

    def inject_ci_context(self, task: str) -> str:
        """Inject CI feedback context into task description if failures found."""
        try:
            import glob as glob_mod

            ci_files = glob_mod.glob(os.path.join(self.persist_dir, "**/pytest*.txt"), recursive=True)
            ci_files += glob_mod.glob(os.path.join(self.persist_dir, "**/junit*.xml"), recursive=True)
            if ci_files:
                ci_results = []
                for cf in ci_files[:3]:
                    with open(cf, encoding="utf-8", errors="ignore") as f:
                        r = self.ci_feedback.parse_ci_output(f.read(), "pytest")
                        if r:
                            ci_results.append(r)
                if ci_results:
                    ctx = self.ci_feedback.generate_context(ci_results)
                    if ctx and ctx.overall_status == "has_failures":
                        if self.usage_tracker:
                            self.usage_tracker.tick("ci_context_injected")
                        return f"{task}\n\n[CI Context] {ctx.summary}"
        except (OSError, ValueError, AttributeError) as e:
            logger.warning(f"CI context injection failed: {e}")
        return task

    def detect_intent(self, task: str, lang: str) -> Any:
        """Detect intent via IntentWorkflowMapper. Returns intent match or None."""
        intent_match = None
        try:
            intent_match = self.intent_mapper.detect_intent(task, lang=lang)
            if intent_match and self.usage_tracker:
                self.usage_tracker.tick("intent_detected")
        except (ValueError, AttributeError, RuntimeError, ImportError) as intent_err:
            logger.debug("Intent detection failed: %s", intent_err)

        self.context_manager.clear_task_context()
        self.context_manager.set_task("task_description", task)
        self.context_manager.set_task("lang", lang)
        if intent_match:
            self.context_manager.set_task("intent_type", intent_match.intent_type)
            self.context_manager.set_task("workflow_chain", list(intent_match.workflow_chain))

        return intent_match

    def match_roles(self, task: str, roles: list[str] | None) -> list[dict[str, Any]]:
        """Match roles via RoleMatcher, AISemanticMatcher, and enhanced adaptive/similar recommendations."""
        matched_roles = self.analyze_task_fn(task)

        # Enhanced role matching: merge adaptive and similar-task recommendations
        try:
            enhanced_roles = self.role_matcher.analyze_task_enhanced(task)
            if enhanced_roles:
                existing_ids = {r["role_id"] for r in matched_roles}
                for er in enhanced_roles:
                    if er["role_id"] not in existing_ids:
                        matched_roles.append(er)
                        existing_ids.add(er["role_id"])
        except (ValueError, AttributeError, RuntimeError, OSError) as enhanced_err:
            logger.debug("Enhanced role matching failed, using keyword-only results: %s", enhanced_err)

        if self.semantic_matcher and self.llm_backend:
            try:
                semantic_results = self.semantic_matcher.match(task)
                if semantic_results:
                    existing_ids = {r["role_id"] for r in matched_roles}
                    for sr in semantic_results:
                        if sr.role_id not in existing_ids and sr.confidence > 0.5:
                            matched_roles.append(
                                {
                                    "role_id": sr.role_id,
                                    "name": sr.role_name,
                                    "reason": sr.reasoning,
                                    "confidence": str(sr.confidence),
                                }
                            )
                            existing_ids.add(sr.role_id)
                    if self.usage_tracker:
                        self.usage_tracker.tick("semantic_matcher")
            except (ValueError, AttributeError, RuntimeError, ConnectionError) as sem_err:
                logger.debug("Semantic matching failed: %s", sem_err)

        if roles:
            matched_roles = self.role_matcher.resolve_roles(roles, matched_roles)

        return matched_roles

    def validate_roles_and_security(
        self,
        task: str,
        matched_roles: list[dict[str, Any]],
        lang: str,
        dry_run: bool,
        start_time: float,
    ) -> tuple[list[str], Any, dict[str, Any], DispatchResult | None]:
        """Validate roles and run security scans. Returns (role_ids, concern_packs, enhancements, early_return)."""
        role_ids = [r["role_id"] for r in matched_roles]

        concern_packs = self.concern_loader.match_packs(task)
        concern_enhancements = self.concern_loader.get_all_role_enhancements(concern_packs)

        if concern_packs:
            pack_names = ", ".join(p.name for p in concern_packs)
            logger.info("Concern packs activated: %s", pack_names)

        if dry_run:
            return role_ids, concern_packs, concern_enhancements, DispatchResult(
                success=True,
                task_description=task,
                matched_roles=role_ids,
                summary=f"[DRY RUN] 将调度角色: {', '.join(role_ids)}",
                duration_seconds=time.time() - start_time,
                lang=lang,
            )

        return role_ids, concern_packs, concern_enhancements, None

    def prepare_execution(
        self,
        task: str,
        matched_roles: list[dict[str, Any]],
        _lang: str,
        _intent_match: Any,
        _rule_collection: Any,
        concern_enhancements: dict[str, Any],
    ) -> tuple[Any, Any, dict[str, float]]:
        """Prepare execution: warmup, prompt assembly, planning, spawn. Returns (plan, goal, timing)."""
        role_ids = [r["role_id"] for r in matched_roles]

        if self.warmup_manager:
            for rid in role_ids:
                cache_key = f"role-prompt-{rid}"
                if not self.warmup_manager.is_ready(cache_key):
                    template = ROLE_TEMPLATES.get(rid, {})
                    self.warmup_manager.set_cache(
                        cache_key,
                        template.get("prompt", ""),
                        ttl=1800,
                    )

        step3_time = time.time()

        available_roles: list[dict[str, Any]] = []
        for r in matched_roles:
            template = ROLE_TEMPLATES.get(r["role_id"], {})
            role_prompt: str = str(template.get("prompt", ""))

            role_id = r["role_id"]
            if role_id in concern_enhancements:
                enhancement = concern_enhancements[role_id]
                if enhancement:
                    enhancement_str: str = str(enhancement)
                    role_prompt = role_prompt + "\n\n" + enhancement_str if role_prompt else enhancement_str

            available_roles.append(
                {
                    "role_id": role_id,
                    "role_prompt": role_prompt,
                    "confidence": r.get("confidence", 0.5),
                }
            )

        plan = self.coordinator.plan_task(
            task_description=task,
            available_roles=available_roles,
        )

        step4_time = time.time()

        self.coordinator.spawn_workers(plan)

        step5_time = time.time()

        # V3.7.0: Parse structured goal for anchor checking
        structured_goal = None
        if self.anchor_checker:
            structured_goal = self.anchor_checker.parse_goal(task)
            if self.usage_tracker:
                self.usage_tracker.tick("anchor_check")

        # V3.7.0: Load historical retrospectives into Scratchpad
        self.load_historical_retrospectives(task)

        return plan, structured_goal, {
            "step3_time": step3_time,
            "step4_time": step4_time,
            "step5_time": step5_time,
        }

    def load_historical_retrospectives(self, task: str) -> None:
        """Load historical retrospectives into Scratchpad."""
        if not self.retrospective_engine or not self.enable_memory:
            return
        try:
            historical = self.retrospective_engine.load_historical(task, limit=3)
            if historical:
                retro_lines = ["[Historical Retrospective Context]"]
                for idx, h in enumerate(historical, 1):
                    if isinstance(h, dict):
                        retro_lines.append(f"  {idx}. {h.get('summary', str(h)[:100])}")
                    else:
                        retro_lines.append(f"  {idx}. {str(h)[:100]}")
                self.scratchpad.write(
                    ScratchpadEntry(
                        worker_id="system",
                        entry_type=EntryType.FINDING,
                        content="\n".join(retro_lines),
                        confidence=0.85,
                        tags=["retrospective", "auto-loaded"],
                    )
                )
        except (OSError, ValueError, AttributeError, KeyError) as retro_load_err:
            logger.debug("Failed to load historical retrospectives: %s", retro_load_err)
