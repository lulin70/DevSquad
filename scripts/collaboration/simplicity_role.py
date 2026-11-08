# DevSquad - Simplicity Role - Core Implementation
# Prevents AI over-engineering by enforcing CRAP and duplication thresholds

"""
Simplicity Role - The 8th Role in DevSquad

Responsibilities:
- S2 Hard Gate: CRAP < 10, Duplication < 0.8
- S3 Dead Code Veto: Detect unused abstractions
- S4 Tech Debt Scanning: Feed back to P2

Anti-Ghost Verification:
- _activation_counter: Number of times dispatched
- _trigger_counter: Number of times actually executed audit
- _skip_counter: Number of times skipped due to conditions
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SimplicityAuditResult:
    """Simplicity audit result"""

    status: str  # "PASS" | "WARNING" | "REJECT"
    verdict: str  # "PASS" | "ADVISORY" | "CONDITIONAL" | "REJECT"
    violations: list[str]
    warnings: list[str]
    metrics: dict[str, Any]
    recommendations: list[str]
    mode: str  # Progressive release mode
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict"""
        return {
            "status": self.status,
            "verdict": self.verdict,
            "violations": self.violations,
            "warnings": self.warnings,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "mode": self.mode,
            "timestamp": self.timestamp.isoformat(),
        }


class SimplicityRole:
    """
    Simplicity Role - Prevents over-engineering

    職責:
    - S2 Hard Gate: CRAP < 10, Duplication < 0.8
    - S3 Dead Code Veto
    - S4 Tech Debt Scanning

    Anti-Ghost Verification:
    - _activation_counter: Dispatch count
    - _trigger_counter: Actual execution count
    - _skip_counter: Skip count
    """

    def __init__(self, workflow_trace: Any, unified_gate_engine: Any) -> None:
        """
        Initialize Simplicity Role

        Args:
            workflow_trace: WorkflowTrace instance
            unified_gate_engine: UnifiedGateEngine instance
        """
        self.workflow_trace = workflow_trace
        self.unified_gate_engine = unified_gate_engine

        # Anti-ghost counters
        self._activation_counter = 0
        self._trigger_counter = 0
        self._skip_counter = 0

        logger.info("SimplicityRole initialized")

    def activate(self, plan: Any, results: list[Any]) -> SimplicityAuditResult | None:
        """
        Main entry point: Called by Coordinator

        Args:
            plan: ExecutionPlan
            results: List of WorkerResult

        Returns:
            SimplicityAuditResult or None (if bypass or skip)

        Flow:
            1. Check emergency bypass (DEVSQUAD_SKIP_SIMPLICITY=1)
            2. Check trigger conditions (_should_trigger())
            3. Execute S1 Gate (ImplementationCompletenessGate) - NEW V5.1
            4. Execute S2 audit (CRAP/Duplication) - Existing V5.1.0
            5. Merge S1+S2 results
            6. Apply progressive release mode (_apply_enforcement_mode())
            7. Record to WorkflowTrace
        """
        self._activation_counter += 1

        # Check emergency bypass
        if os.getenv("DEVSQUAD_SKIP_SIMPLICITY") == "1":
            logger.warning("⚠️ Simplicity S2 gate bypassed (DEVSQUAD_SKIP_SIMPLICITY=1)")
            self._skip_counter += 1

            # Record bypass event
            self.workflow_trace.record(
                {
                    "event": "simplicity_bypass",
                    "reason": "Emergency bypass enabled",
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # TODO: Send alert (will integrate AlertSystem in P8-006)
            return None

        # Check trigger conditions
        if not self._should_trigger(plan):
            self._skip_counter += 1
            logger.debug(f"Simplicity role skipped (phase={plan.phase})")
            return None

        # Execute audit
        self._trigger_counter += 1
        logger.info(f"🔍 Simplicity gates triggered (phase={plan.phase})")

        # **NEW V5.1**: Run S1 Gate first (Implementation Completeness)
        s1_result = self._run_s1_gate(plan, results)

        # Existing V5.1.0: Run S2 audit (CRAP/Duplication)
        s2_result = self._audit(plan, results)

        # Merge S1 and S2 results
        result = self._merge_gate_results(s1_result, s2_result)

        # Apply progressive release mode
        result = self._apply_enforcement_mode(result)

        # Record to WorkflowTrace
        self.workflow_trace.record(
            {"event": "simplicity_audit", "result": result.to_dict(), "timestamp": datetime.now().isoformat()}
        )

        return result

    def _should_trigger(self, plan: Any) -> bool:
        """
        Check if audit should be triggered

        Trigger conditions:
        - Phase is P8 (Implementation Phase)

        Args:
            plan: ExecutionPlan

        Returns:
            True if should trigger, False otherwise
        """
        return bool(plan.phase == "P8")

    def _audit(self, plan: Any, _results: list[Any]) -> SimplicityAuditResult:
        """
        Execute audit logic

        Flow:
            1. Extract target file paths
            2. Call CRAPGate.check()
            3. Call DuplicationGate.check() (TODO: P8-005)
            4. Determine verdict based on thresholds

        Args:
            plan: ExecutionPlan
            _results: List of WorkerResult (kept for call-site symmetry; not read here)

        Returns:
            SimplicityAuditResult
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate

        # Extract target paths
        target_paths = getattr(plan, "target_files", [])
        if not target_paths:
            logger.warning("No target files specified in plan")
            target_paths = []

        # Run CRAP gate
        crap_gate = CRAPGate(threshold=10.0)
        crap_result = crap_gate.check(target_paths)

        # TODO: Run DuplicationGate (P8-005)
        # duplication_gate = DuplicationGate(threshold=0.08)
        # dup_result = duplication_gate.check(target_paths)

        # Determine overall status
        status = crap_result["status"]
        violations = []
        warnings = []
        recommendations = []

        if crap_result["status"] == "REJECT":
            violations.extend(
                [f"CRAP score {v['crap']:.1f} in {v['function']} ({v['file']})" for v in crap_result["violations"]]
            )
            recommendations.append("Refactor high-CRAP functions: reduce cyclomatic complexity or add tests")
        elif crap_result["status"] == "WARNING":
            warnings.append(f"Max CRAP score {crap_result['max_crap']:.1f} approaching threshold")

        # Build metrics
        metrics = {
            "max_crap": crap_result["max_crap"],
            "crap_violations": len(crap_result["violations"]),
            # TODO: Add duplication metrics in P8-005
        }

        return SimplicityAuditResult(
            status=status,
            verdict=status,  # Will be adjusted by _apply_enforcement_mode()
            violations=violations,
            warnings=warnings,
            metrics=metrics,
            recommendations=recommendations,
            mode="",  # Will be set by _apply_enforcement_mode()
            timestamp=datetime.now(),
        )

    def _apply_enforcement_mode(self, result: SimplicityAuditResult) -> SimplicityAuditResult:
        """
        Apply progressive release mode

        Shadow mode: REJECT → ADVISORY
        Soft mode: REJECT → CONDITIONAL (can be manually overridden)
        Full mode: Keep original verdict

        Args:
            result: SimplicityAuditResult

        Returns:
            Adjusted SimplicityAuditResult
        """
        from scripts.collaboration.simplicity_config import SimplicityConfig

        current_mode = SimplicityConfig.get_current_mode()
        result.mode = current_mode

        if result.status == "REJECT":
            if current_mode == "shadow":
                result.verdict = "ADVISORY"
                logger.info("📊 Shadow mode: REJECT downgraded to ADVISORY")
            elif current_mode == "soft":
                result.verdict = "CONDITIONAL"
                logger.info("⚠️ Soft mode: REJECT changed to CONDITIONAL (manual override allowed)")
            else:  # full mode
                result.verdict = "REJECT"
                logger.error("❌ Full mode: REJECT enforced")

        return result

    def get_activation_stats(self) -> dict[str, int]:
        """
        Anti-ghost verification: Return counter stats

        Returns:
            {
                "activation_counter": int,
                "trigger_counter": int,
                "skip_counter": int
            }
        """
        return {
            "activation_counter": self._activation_counter,
            "trigger_counter": self._trigger_counter,
            "skip_counter": self._skip_counter,
        }

    def _run_s1_gate(self, plan: Any, _results: list[Any]) -> dict[str, Any]:
        """
        Run S1 Gate (ImplementationCompletenessGate) - NEW V5.1

        Args:
            plan: ExecutionPlan
            _results: List of WorkerResult (kept for call-site symmetry; not read here)

        Returns:
            S1 gate result dict
        """
        from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate

        logger.info("🔍 Running S1 Gate (ImplementationCompletenessGate)...")

        # Extract target paths
        target_paths = getattr(plan, "target_files", [])
        if not target_paths:
            logger.warning("No target files specified in plan, S1 gate will return perfect score")
            target_paths = []

        # Convert to Path objects
        target_paths = [Path(p) for p in target_paths]

        # Build gate plan
        gate_plan = {
            "p3_doc": getattr(plan, "p3_doc", None),
            "p7_doc": getattr(plan, "p7_doc", None),
            "test_paths": getattr(plan, "test_files", []),
            "mode": os.getenv("DEVSQUAD_S1_MODE", "full"),  # Can override via env
        }

        # Run S1 Gate
        s1_gate = ImplementationCompletenessGate()
        s1_result = s1_gate.check(target_paths, plan=gate_plan)

        logger.info(f"✅ S1 Gate completed: {s1_result['verdict']} (score={s1_result['completeness_score']:.2f})")

        return s1_result

    def _merge_gate_results(self, s1_result: dict[str, Any], s2_result: SimplicityAuditResult) -> SimplicityAuditResult:
        """
        Merge S1 and S2 gate results - NEW V5.1

        Logic:
        - If S1 is REJECT, overall is REJECT (completeness is prerequisite)
        - If S1 is WARNING, S2 verdict wins but add S1 warnings
        - If S1 is PASS, use S2 verdict

        Args:
            s1_result: S1 Gate result dict
            s2_result: S2 audit result (SimplicityAuditResult)

        Returns:
            Merged SimplicityAuditResult
        """
        s1_verdict = s1_result["verdict"]
        s2_status = s2_result.status

        # Merge violations and warnings
        all_violations = s2_result.violations.copy()
        all_warnings = s2_result.warnings.copy()

        # Add S1 issues
        if s1_result["details"]["mock_violations"]:
            all_violations.append(
                f"S1: Found {len(s1_result['details']['mock_violations'])} mock usage(s) in production code"
            )
        if s1_result["details"]["missing_elements"]:
            all_warnings.append(f"S1: {len(s1_result['details']['missing_elements'])} design elements not implemented")
        if s1_result["details"]["missing_tests"]:
            all_warnings.append(f"S1: {len(s1_result['details']['missing_tests'])} test cases not implemented")
        if s1_result["details"]["unprotected_operations"]:
            all_warnings.append(
                f"S1: {len(s1_result['details']['unprotected_operations'])} I/O operations lack error handling"
            )
        if s1_result["details"]["missing_security_features"]:
            all_violations.append(
                f"S1: {len(s1_result['details']['missing_security_features'])} security features missing"
            )

        # Determine final status
        if s1_verdict == "REJECT":
            final_status = "REJECT"
        elif s1_verdict == "WARNING" and s2_status == "PASS":
            final_status = "WARNING"
        else:
            final_status = s2_status

        # Merge metrics
        merged_metrics = s2_result.metrics.copy()
        merged_metrics["s1_completeness_score"] = s1_result["completeness_score"]
        merged_metrics["s1_verdict"] = s1_verdict

        # Add recommendations
        recommendations = s2_result.recommendations.copy()
        if s1_verdict != "PASS":
            recommendations.insert(
                0,
                f"S1 Gate ({s1_verdict}): Review implementation completeness (score={s1_result['completeness_score']:.2f})",
            )

        return SimplicityAuditResult(
            status=final_status,
            verdict=final_status,  # Will be adjusted by _apply_enforcement_mode()
            violations=all_violations,
            warnings=all_warnings,
            metrics=merged_metrics,
            recommendations=recommendations,
            mode="",  # Will be set by _apply_enforcement_mode()
            timestamp=datetime.now(),
        )
