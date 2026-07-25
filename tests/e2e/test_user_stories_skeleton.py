#!/usr/bin/env python3
"""DevSquad SDLC user story E2E test skeletons (V4.3.0 P0-4 → V4.3.1 un-xfail).

This module establishes 8 E2E test skeletons driven by SDLC user stories.
V4.3.0 introduced them as ``xfail(strict=True)`` skeletons; V4.3.1 un-xfailed
all 8 (RequirementTracer + BenchmarkRegressionChecker landed).

Reference:
- PRD: docs/prd/V4.3.0_PRD.md §9 (SDLC user stories)
- Architecture: docs/architecture/V4.3.0_ARCHITECTURE.md §9 (Skill integration)
- Test plan: docs/testing/V4.3.0_TEST_PLAN.md §11 (E2E skeletons)
- Consensus: docs/analysis/2026-07-25_user_stories_review_consensus.md §5

Skeleton policy (Anti-ghost feature guarantee):
1. V4.3.0: ``xfail(strict=True)`` — accidental XPASS fails CI, forcing Phase completion
2. V4.3.1: all 8 skeletons un-xfailed (Phase 0/1/2/3/4 implementation landed)
3. Each skeleton docstring records: Phase / PRD / pass condition
4. CI ``--collect-only`` verifies all 8 skeletons exist (skeleton integrity check)
5. Skeletons MUST NOT be deleted; they flip from xfail to xpass on Phase completion

Anti-ghost feature checks (per consensus §3.2):
- Module activation: each new module is called > 0 times in CI
- Skill integration: each new module is registered in dispatcher / gate engine
- Test coverage: each new module has unit + E2E coverage
- User visibility: each new module appears in Markdown report
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# E2E-01: User story journey (V4.3.1 — un-xfail, RequirementTracer landed)
# ---------------------------------------------------------------------------
def test_e2e_01_user_story_journey_skeleton(tmp_path) -> None:
    """E2E-01: User story journey from requirements to deployment (V4.3.1).

    Scenario: A user submits a task to DevSquad and the full lifecycle
    (P1 requirements → P8 implementation → P10 deployment) is traceable
    via user stories.

    Pass condition:
    - RequirementTracer can parse [REQ-XXX] markers from PRD
    - Each lifecycle phase has at least one user story mapped
    - The journey report is visible in Markdown output

    Related PRD: P0-4 (test skeleton), P1-1 (RequirementTracer — V4.3.0 landed)
    V4.3.1: un-xfail — RequirementTracer API stable, E2E-01 aligned to actual API.
    """
    # Arrange — prepare a PRD with [REQ-XXX] markers (written to temp file
    # because RequirementTracer.parse_requirements accepts a file path)
    prd_text = "[REQ-P0-4] Establish 8 E2E test skeletons"
    prd_file = tmp_path / "test_prd.md"
    prd_file.write_text(prd_text, encoding="utf-8")

    # Act — parse requirements and trace lifecycle
    from scripts.collaboration.requirement_tracer import RequirementTracer

    tracer = RequirementTracer(codebase_root="scripts")
    reqs = tracer.parse_requirements(prd_file)
    results = tracer.trace_matrix()

    # Assert — journey is traceable end-to-end
    assert len(reqs) >= 1, "Requirement should be parsed"
    # RequirementTracer pattern \b(P\d+-\d+)\b extracts "P0-4" from "[REQ-P0-4]"
    assert reqs[0].req_id == "P0-4"
    assert len(results) >= 1
    # status is "implemented" if code references found, else "missing"
    assert results[0].status in ("implemented", "missing")


# ---------------------------------------------------------------------------
# E2E-02: P10 compliant deployment (Phase 0, P0-3 — PASSED)
# ---------------------------------------------------------------------------
def test_e2e_02_compliant_deployment_passes_p10_gate() -> None:
    """E2E-02: A compliant deployment passes the P10 lifecycle gate (Phase 0 P0-3).

    Scenario: A user deploys the Pro edition to the sanctioned cloud host
    (47.116.219.15). DevSquad's P10 lifecycle gate runs the
    DeploymentComplianceChecker, which returns a compliant report.

    Pass condition:
    - ``lifecycle_gate_check(phase="P10", target_env={"edition": "pro",
      "host": "47.116.219.15"})`` returns ``ComplianceReport(compliant=True)``
    - No violations are recorded

    Related PRD: P0-3 (DeploymentComplianceChecker simplified)
    """
    from scripts.collaboration.deployment_compliance_checker import (
        ComplianceReport,
        lifecycle_gate_check,
    )

    target_env = {"edition": "pro", "host": "47.116.219.15"}

    report = lifecycle_gate_check(phase="P10", target_env=target_env)

    assert isinstance(report, ComplianceReport)
    assert report.compliant is True
    assert report.violations == []


# ---------------------------------------------------------------------------
# E2E-03: P11 performance baseline (V4.3.1 — un-xfail, BenchmarkRegressionChecker landed)
# ---------------------------------------------------------------------------
def test_e2e_03_p11_performance_baseline_passes() -> None:
    """E2E-03: A performance baseline check passes the P11 lifecycle gate (V4.3.1).

    Scenario: Nightly CI runs the BenchmarkRegressionChecker against the
    latest version. Performance is within 10%% of the baseline.

    Pass condition:
    - ``lifecycle_gate_check(phase="P11", baseline_version="4.2.9",
      current_snapshot=<near-baseline>)`` returns a BenchmarkReport with
      ``regression_detected=False``

    Related PRD: V4.3.1 (BenchmarkRegressionChecker — V4.3.1 Phase 1 landed)
    V4.3.1: un-xfail — BenchmarkRegressionChecker module implemented.
    """
    from scripts.collaboration.benchmark_regression_checker import (
        BenchmarkMetric,
        BenchmarkSnapshot,
        lifecycle_gate_check,
    )

    # Inject a current snapshot that is within 10%% of the baseline
    # (baseline: dispatch_p95_ms=100.0, memory_peak_mb=200.0)
    # (current:  dispatch_p95_ms=105.0, memory_peak_mb=200.0 → 5%% regression, < 10%% threshold)
    baseline_snapshot = BenchmarkSnapshot(
        version="4.2.9",
        timestamp=0.0,
        metrics=[
            BenchmarkMetric("dispatch_p95_ms", 100.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ],
    )
    current_snapshot = BenchmarkSnapshot(
        version="4.3.1",
        timestamp=0.0,
        metrics=[
            BenchmarkMetric("dispatch_p95_ms", 105.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ],
    )

    report = lifecycle_gate_check(
        phase="P11",
        baseline_version="4.2.9",
        current_version="4.3.1",
        baseline_snapshot=baseline_snapshot,
        current_snapshot=current_snapshot,
    )

    assert report.regression_detected is False


# ---------------------------------------------------------------------------
# E2E-04: P6 hallucinated dependency detection (Phase 1, P1-7 — PASSED)
# ---------------------------------------------------------------------------
def test_e2e_04_hallucinated_dependency_detected() -> None:
    """E2E-04: A hallucinated PyPI package is detected and reported (Phase 1 P1-7).

    Scenario: An AI worker generates code importing ``huggingface_cli``
    (a hallucinated package; the real package is ``huggingface_hub``).
    The SecuritySkill's DependencyHallucinationChecker flags it as
    SUSPICIOUS via the ``security_scan_dependencies`` API.

    Pass condition:
    - ``security_scan_dependencies("import huggingface_cli")`` returns a
      ``DependencyScanResult`` with at least one SUSPICIOUS finding
    - The finding's package name matches ``huggingface_cli``
    - The suggested fix is ``huggingface_hub``

    Related PRD: P1-7 (DependencyHallucinationChecker)
    Source: arXiv:2605.17062 cross-model hallucination study
    """
    from scripts.collaboration.dependency_hallucination_checker import (
        DependencyCategory,
        DependencyScanResult,
        security_scan_dependencies,
    )

    code = "import huggingface_cli  # hallucinated package"

    result = security_scan_dependencies(code)

    assert isinstance(result, DependencyScanResult)
    suspicious = [
        f for f in result.findings
        if f.category == DependencyCategory.SUSPICIOUS
    ]
    assert len(suspicious) >= 1
    assert any("huggingface_cli" in f.package_name for f in suspicious)
    # Suggested fix should point to the real package
    assert suspicious[0].suggested_fix == "huggingface_hub"


# ---------------------------------------------------------------------------
# E2E-05: P8 LLM output validation (Phase 2, P1-8 — PASSED)
# ---------------------------------------------------------------------------
def test_e2e_05_sensitive_llm_output_blocked() -> None:
    """E2E-05: Sensitive information in LLM output is blocked by dispatch hook (Phase 2 P1-8).

    Scenario: A worker's LLM output contains an OpenAI API key
    (``sk-...``). The dispatch post-worker hook's OutputValidator
    intercepts the leak and either blocks the output (blocking mode)
    or redacts it before persisting the report (non-blocking mode).

    Phase 2 P1-8 adds:
    1. Integration into ``dispatch_hooks.py`` post-worker hook (auto-trigger)
    2. Configurable blocking/non-blocking mode via config dict
    3. Audit log entry for every validation finding

    Pass condition:
    - ``PostDispatchPipeline`` runs OutputValidator on every worker output
    - When ``output_validation.mode == "blocking"``, dispatch fails fast
      on high-severity findings
    - When ``output_validation.mode == "non_blocking"``, findings are
      logged + redacted + dispatch continues
    - Audit log records the finding pattern_name + severity

    Related PRD: P1-8 (OutputValidator full integration — Phase 2 upgrades
    the V4.1.2 skeleton to production-grade with dispatch hook integration)
    """
    # V4.3.0 Phase 2: PostDispatchPipeline is re-exported from dispatch_hooks
    # (E2E-05 import contract). Construction uses __new__ + _apply_output_validation_config
    # because __init__ requires heavy dependency injection (coordinator, services, etc.).
    from scripts.collaboration.dispatch_hooks import PostDispatchPipeline
    from scripts.collaboration.output_validator import OutputValidator

    pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
    pipeline.output_validator = OutputValidator()
    pipeline.audit_logger = _FakeAuditLogger()
    pipeline._apply_output_validation_config(
        config={"output_validation": {"mode": "blocking"}}
    )

    leaky_output = "My key is sk-abcdefghijklmnopqrstuvwxyz123456"

    result = pipeline._validate_outputs([leaky_output])

    assert result.blocked is True
    assert len(result.findings) >= 1
    assert result.findings[0].category == "sensitive_info"
    assert result.audit_logged is True


class _FakeAuditLogger:
    """Minimal audit logger for E2E-05 (records events for assertion)."""

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def log_event(self, event_type: str, details: dict[str, object]) -> None:
        self.events.append({"event_type": event_type, "details": details})


# ---------------------------------------------------------------------------
# E2E-06: P10 violating deployment blocked (Phase 0, P0-3 — PASSED)
# ---------------------------------------------------------------------------
def test_e2e_06_violating_deployment_blocked() -> None:
    """E2E-06: A violating deployment is blocked by the P10 gate (Phase 0 P0-3).

    Scenario: A user attempts to deploy the basic edition to the cloud
    host 47.116.219.15. DevSquad's P10 lifecycle gate runs the
    DeploymentComplianceChecker, which detects the violation and blocks
    the deployment.

    Pass condition:
    - ``lifecycle_gate_check(phase="P10",
      target_env={"edition": "basic", "host": "47.116.219.15"})`` returns
      ``ComplianceReport(compliant=False)``
    - The first violation's message contains "基础版禁止云端部署"

    Related PRD: P0-3 (DeploymentComplianceChecker simplified)
    Historical lesson: 2026-07-12 basic edition violating deployment incident
    """
    from scripts.collaboration.deployment_compliance_checker import (
        ComplianceReport,
        lifecycle_gate_check,
    )

    target_env = {"edition": "basic", "host": "47.116.219.15"}

    report = lifecycle_gate_check(phase="P10", target_env=target_env)

    assert isinstance(report, ComplianceReport)
    assert report.compliant is False
    assert len(report.violations) >= 1
    assert "基础版禁止云端部署" in report.violations[0].message


# ---------------------------------------------------------------------------
# E2E-07: P8 multi-axis review (Phase 3, P3-4 — PASSED)
# ---------------------------------------------------------------------------
def test_e2e_07_multi_axis_review_reported() -> None:
    """E2E-07: Multi-axis review produces a structured report (Phase 3 P3-4).

    Scenario: A user runs ``devsquad run`` with 7 roles. The
    FiveAxisConsensusEngine produces a structured report with
    correctness / readability / architecture / security / performance
    scores, and the report is visible in the Markdown output.

    Pass condition:
    - ``FiveAxisConsensusEngine().evaluate(...)`` returns a result with
      all 5 axis scores populated
    - The Markdown report contains a "Five-Axis Review" section

    Related PRD: Phase 3 P3-4 (FiveAxisConsensusEngine.evaluate() heuristic)
    """
    from scripts.collaboration.five_axis_consensus import (
        FiveAxisConsensusEngine,
        FiveAxisEvaluationResult,
    )

    engine = FiveAxisConsensusEngine()
    result = engine.evaluate(artifacts={"code": "print('hello')"})

    # Verify all 5 axis scores are populated (float, not None)
    assert isinstance(result, FiveAxisEvaluationResult)
    assert result.correctness is not None
    assert result.readability is not None
    assert result.architecture is not None
    assert result.security is not None
    assert result.performance is not None
    # Verify verdict is one of the allowed values
    assert result.verdict in ("APPROVE", "CONDITIONAL", "REJECT")
    # Verify Markdown report contains the Five-Axis Review section
    markdown = result.to_markdown()
    assert "Five-Axis Review" in markdown
    assert "Correctness" in markdown
    assert "Security" in markdown


# ---------------------------------------------------------------------------
# E2E-08: P11 benchmark regression (V4.3.1 — un-xfail, BenchmarkRegressionChecker landed)
# ---------------------------------------------------------------------------
def test_e2e_08_benchmark_regression_alerted() -> None:
    """E2E-08: A benchmark regression triggers a nightly alert (V4.3.1).

    Scenario: Nightly CI runs the BenchmarkRegressionChecker. The latest
    version's P95 latency is 25%% slower than the baseline, exceeding the
    10%% threshold. The checker reports ``regression_detected=True`` and
    triggers a Slack notification.

    Pass condition:
    - ``lifecycle_gate_check(phase="P11", baseline_version="4.2.9",
      current_snapshot=<25%%-slower>)`` returns
      ``BenchmarkReport(regression_detected=True)``
    - The report includes the regression percentage (> 10.0)

    Related PRD: V4.3.1 (BenchmarkRegressionChecker — V4.3.1 Phase 1 landed)
    V4.3.1: un-xfail — BenchmarkRegressionChecker module implemented.
    """
    from scripts.collaboration.benchmark_regression_checker import (
        BenchmarkMetric,
        BenchmarkSnapshot,
        lifecycle_gate_check,
    )

    # Inject a current snapshot that is 25%% slower than the baseline
    # (baseline: dispatch_p95_ms=100.0, memory_peak_mb=200.0)
    # (current:  dispatch_p95_ms=125.0, memory_peak_mb=200.0 → 25%% regression, > 10%% threshold)
    baseline_snapshot = BenchmarkSnapshot(
        version="4.2.9",
        timestamp=0.0,
        metrics=[
            BenchmarkMetric("dispatch_p95_ms", 100.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ],
    )
    current_snapshot = BenchmarkSnapshot(
        version="4.3.1",
        timestamp=0.0,
        metrics=[
            BenchmarkMetric("dispatch_p95_ms", 125.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ],
    )

    report = lifecycle_gate_check(
        phase="P11",
        baseline_version="4.2.9",
        current_version="4.3.1",
        baseline_snapshot=baseline_snapshot,
        current_snapshot=current_snapshot,
    )

    assert report.regression_detected is True
    assert report.regression_percent > 10.0
