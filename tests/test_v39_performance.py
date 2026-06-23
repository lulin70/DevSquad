#!/usr/bin/env python3
"""V3.9 Performance Tests — Verify all performance benchmarks from test plan.

Benchmarks (from docs/prd/V3.9_Test_Plan.md section 3):
1. Graph query <50ms       — time.perf_counter() wrapping query
2. Incremental update <500ms — modify single file then update_file
3. RBAC check <5ms         — check_dispatch_permission
4. Audit log <1ms          — single log_dispatch_start
5. PromptDials <1ms        — to_prompt_fragment
6. YagniChecker <5ms       — single check
7. RedesignAudit <100ms    — audit(100 lines of code)

Each test follows the same methodology:
- One warmup run (not measured) to amortize cold-start overhead.
- N measured runs (>= 10) using time.perf_counter().
- The median latency is asserted to be under the target threshold.
- Median (not mean) is used because it is robust to GC/scheduler outliers.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.code_knowledge_graph import CodeKnowledgeGraph
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatch_rbac import DispatchRBAC
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.micro_task_planner import MicroTaskPlanner
from scripts.collaboration.prompt_dials import PromptDials
from scripts.collaboration.redesign_auditor import RedesignAuditor
from scripts.collaboration.yagni_checker import YagniChecker

# ---------------------------------------------------------------------------
# Constants — targets from V3.9_Test_Plan.md section 3
# ---------------------------------------------------------------------------

GRAPH_QUERY_TARGET_MS = 50.0
INCREMENTAL_UPDATE_TARGET_MS = 500.0
RBAC_CHECK_TARGET_MS = 5.0
AUDIT_LOG_TARGET_MS = 1.0
PROMPT_DIALS_TARGET_MS = 1.0
YAGNI_CHECKER_TARGET_MS = 5.0
REDESIGN_AUDIT_TARGET_MS = 100.0
# Extended benchmarks (full pipeline + build + chain verification).
FULL_DISPATCH_TARGET_MS = 2000.0
GRAPH_BUILD_TARGET_MS = 5000.0
VERIFY_CHAIN_TARGET_MS = 500.0

# Number of measured runs per benchmark. Median is robust with >= 10 samples.
MEASURED_RUNS = 15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_project() -> tuple[str, Path]:
    """Create a small temp Python project for CodeKnowledgeGraph indexing.

    Returns (tmpdir, project_root).
    """
    tmpdir = tempfile.mkdtemp(prefix="v39_perf_")
    project_root = Path(tmpdir) / "src"
    project_root.mkdir(parents=True, exist_ok=True)

    (project_root / "sample.py").write_text(
        '''"""Sample module for performance testing."""

def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}"


def call_hello() -> str:
    """Call hello."""
    return hello("world")


class Greeter:
    """A greeter class."""

    def greet(self) -> str:
        return hello("class")
''',
        encoding="utf-8",
    )
    return tmpdir, project_root


def _measure_ms(func, runs: int = MEASURED_RUNS) -> float:
    """Run func ``runs`` times and return the median latency in milliseconds.

    Args:
        func: Zero-argument callable to measure.
        runs: Number of measured runs (>= 10 recommended for stable median).

    Returns:
        Median latency in milliseconds across the measured runs.
    """
    latencies_ms: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        latencies_ms.append((end - start) * 1000.0)
    return statistics.median(latencies_ms)


# ---------------------------------------------------------------------------
# Benchmark 1: Graph query <50ms
# ---------------------------------------------------------------------------


class TestGraphQueryPerformance:
    """Verify CodeKnowledgeGraph.query() operations complete under 50ms."""

    def test_find_symbol_under_50ms(self) -> None:
        """Verify: find_symbol median latency < 50ms.

        Scenario: Query a pre-built graph for an existing symbol.
        Expected: Median latency across 15 runs is under 50ms.
        """
        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)
            query = graph.query()

            # Warmup (not measured).
            query.find_symbol("hello")

            median_ms = _measure_ms(lambda: query.find_symbol("hello"))
            assert median_ms < GRAPH_QUERY_TARGET_MS, (
                f"find_symbol median {median_ms:.3f}ms >= "
                f"{GRAPH_QUERY_TARGET_MS}ms target"
            )
            graph.close()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_find_callers_under_50ms(self) -> None:
        """Verify: find_callers median latency < 50ms.

        Scenario: Query callers of a known function in a pre-built graph.
        Expected: Median latency across 15 runs is under 50ms.
        """
        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)
            query = graph.query()

            query.find_callers("hello")  # warmup

            median_ms = _measure_ms(lambda: query.find_callers("hello"))
            assert median_ms < GRAPH_QUERY_TARGET_MS, (
                f"find_callers median {median_ms:.3f}ms >= "
                f"{GRAPH_QUERY_TARGET_MS}ms target"
            )
            graph.close()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Benchmark 2: Incremental update <500ms
# ---------------------------------------------------------------------------


class TestIncrementalUpdatePerformance:
    """Verify CodeKnowledgeGraph.update_file() completes under 500ms."""

    def test_update_file_under_500ms(self) -> None:
        """Verify: update_file median latency < 500ms.

        Scenario: Modify a single file's content and re-index it.
        Expected: Median latency across 15 runs is under 500ms.
        """
        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            sample_file = project_root / "sample.py"
            original_content = sample_file.read_text(encoding="utf-8")

            # Warmup: one unchanged update (hash-skip path).
            graph.update_file(sample_file)

            # For measured runs, alternate content so the hash changes and
            # the file is actually re-parsed. We restore original after.
            counter = [0]

            def _measured_update() -> None:
                counter[0] += 1
                if counter[0] % 2 == 1:
                    sample_file.write_text(
                        original_content + f"\n# perf marker {counter[0]}\n",
                        encoding="utf-8",
                    )
                else:
                    sample_file.write_text(original_content, encoding="utf-8")
                graph.update_file(sample_file)

            median_ms = _measure_ms(_measured_update)
            assert median_ms < INCREMENTAL_UPDATE_TARGET_MS, (
                f"update_file median {median_ms:.3f}ms >= "
                f"{INCREMENTAL_UPDATE_TARGET_MS}ms target"
            )

            # Restore original content for cleanliness.
            sample_file.write_text(original_content, encoding="utf-8")
            graph.close()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Benchmark 3: RBAC check <5ms
# ---------------------------------------------------------------------------


class TestRBACCheckPerformance:
    """Verify DispatchRBAC.check_dispatch_permission() completes under 5ms."""

    def test_rbac_check_under_5ms(self) -> None:
        """Verify: check_dispatch_permission median latency < 5ms.

        Scenario: An admin user requests an allowed dispatch configuration.
        Expected: Median latency across 15 runs is under 5ms.
        """
        mock_auth = MagicMock()
        mock_auth.credentials = {"admin_user": {"role": "admin"}}
        rbac = DispatchRBAC(auth_manager=mock_auth)

        # Warmup.
        rbac.check_dispatch_permission(
            user_id="admin_user",
            roles=["architect"],
            mode="auto",
        )

        median_ms = _measure_ms(
            lambda: rbac.check_dispatch_permission(
                user_id="admin_user",
                roles=["architect"],
                mode="auto",
            )
        )
        assert median_ms < RBAC_CHECK_TARGET_MS, (
            f"RBAC check median {median_ms:.3f}ms >= "
            f"{RBAC_CHECK_TARGET_MS}ms target"
        )

    def test_rbac_check_denied_under_5ms(self) -> None:
        """Verify: denied permission check median latency < 5ms.

        Scenario: A viewer user requests a disallowed mode (consensus).
        Expected: Median latency across 15 runs is under 5ms (denial path).
        """
        mock_auth = MagicMock()
        mock_auth.credentials = {"viewer_user": {"role": "viewer"}}
        rbac = DispatchRBAC(auth_manager=mock_auth)

        rbac.check_dispatch_permission(
            user_id="viewer_user",
            roles=["architect"],
            mode="consensus",
        )  # warmup

        median_ms = _measure_ms(
            lambda: rbac.check_dispatch_permission(
                user_id="viewer_user",
                roles=["architect"],
                mode="consensus",
            )
        )
        assert median_ms < RBAC_CHECK_TARGET_MS, (
            f"RBAC denied-check median {median_ms:.3f}ms >= "
            f"{RBAC_CHECK_TARGET_MS}ms target"
        )


# ---------------------------------------------------------------------------
# Benchmark 4: Audit log <1ms
# ---------------------------------------------------------------------------


class TestAuditLogPerformance:
    """Verify DispatchAuditLogger.log_dispatch_start() completes under 1ms."""

    def test_audit_log_start_under_1ms(self) -> None:
        """Verify: log_dispatch_start median latency < 1ms.

        Scenario: Append a single dispatch_start entry to the in-memory chain.
        Expected: Median latency across 15 runs is under 1ms.
        """
        audit_logger = DispatchAuditLogger()  # in-memory

        # Warmup.
        audit_logger.log_dispatch_start(
            user_id="warmup_user",
            task="warmup task",
            roles=["architect"],
        )

        counter = [0]

        def _measured_log() -> None:
            counter[0] += 1
            audit_logger.log_dispatch_start(
                user_id=f"user_{counter[0]}",
                task=f"task {counter[0]}",
                roles=["architect"],
            )

        median_ms = _measure_ms(_measured_log)
        assert median_ms < AUDIT_LOG_TARGET_MS, (
            f"Audit log_dispatch_start median {median_ms:.3f}ms >= "
            f"{AUDIT_LOG_TARGET_MS}ms target"
        )

    def test_audit_log_end_under_1ms(self) -> None:
        """Verify: log_dispatch_end median latency < 1ms.

        Scenario: Append a single dispatch_end entry to the in-memory chain.
        Expected: Median latency across 15 runs is under 1ms.
        """
        audit_logger = DispatchAuditLogger()

        audit_logger.log_dispatch_end(
            user_id="warmup_user",
            success=True,
            duration=0.1,
        )  # warmup

        median_ms = _measure_ms(
            lambda: audit_logger.log_dispatch_end(
                user_id="user",
                success=True,
                duration=0.1,
            )
        )
        assert median_ms < AUDIT_LOG_TARGET_MS, (
            f"Audit log_dispatch_end median {median_ms:.3f}ms >= "
            f"{AUDIT_LOG_TARGET_MS}ms target"
        )


# ---------------------------------------------------------------------------
# Benchmark 5: PromptDials <1ms
# ---------------------------------------------------------------------------


class TestPromptDialsPerformance:
    """Verify PromptDials.to_prompt_fragment() completes under 1ms."""

    def test_to_prompt_fragment_under_1ms(self) -> None:
        """Verify: to_prompt_fragment median latency < 1ms.

        Scenario: Generate a prompt fragment from non-default dials.
        Expected: Median latency across 15 runs is under 1ms.
        """
        dials = PromptDials(verbosity=2, creativity=4, risk_tolerance=1)

        dials.to_prompt_fragment()  # warmup

        median_ms = _measure_ms(lambda: dials.to_prompt_fragment())
        assert median_ms < PROMPT_DIALS_TARGET_MS, (
            f"PromptDials.to_prompt_fragment median {median_ms:.3f}ms >= "
            f"{PROMPT_DIALS_TARGET_MS}ms target"
        )

    def test_from_variant_under_1ms(self) -> None:
        """Verify: from_variant median latency < 1ms.

        Scenario: Convert a legacy variant string to PromptDials.
        Expected: Median latency across 15 runs is under 1ms.
        """
        PromptDials.from_variant("concise")  # warmup

        median_ms = _measure_ms(lambda: PromptDials.from_variant("concise"))
        assert median_ms < PROMPT_DIALS_TARGET_MS, (
            f"PromptDials.from_variant median {median_ms:.3f}ms >= "
            f"{PROMPT_DIALS_TARGET_MS}ms target"
        )


# ---------------------------------------------------------------------------
# Benchmark 6: YagniChecker <5ms
# ---------------------------------------------------------------------------


class TestYagniCheckerPerformance:
    """Verify YagniChecker.check() completes under 5ms."""

    def test_yagni_check_under_5ms(self) -> None:
        """Verify: YagniChecker.check median latency < 5ms.

        Scenario: Run the YAGNI ladder on a typical micro-task description.
        Expected: Median latency across 15 runs is under 5ms.
        """
        checker = YagniChecker()

        checker.check("Write a function to parse JSON response")  # warmup

        median_ms = _measure_ms(
            lambda: checker.check("Write a function to parse JSON response")
        )
        assert median_ms < YAGNI_CHECKER_TARGET_MS, (
            f"YagniChecker.check median {median_ms:.3f}ms >= "
            f"{YAGNI_CHECKER_TARGET_MS}ms target"
        )

    def test_yagni_check_exploratory_under_5ms(self) -> None:
        """Verify: YagniChecker.check on exploratory task < 5ms.

        Scenario: Run the YAGNI ladder on an exploratory task (SKIP path).
        Expected: Median latency across 15 runs is under 5ms.
        """
        checker = YagniChecker()

        checker.check("Explore different approaches and prototype a demo")  # warmup

        median_ms = _measure_ms(
            lambda: checker.check(
                "Explore different approaches and prototype a demo"
            )
        )
        assert median_ms < YAGNI_CHECKER_TARGET_MS, (
            f"YagniChecker.check (exploratory) median {median_ms:.3f}ms >= "
            f"{YAGNI_CHECKER_TARGET_MS}ms target"
        )


# ---------------------------------------------------------------------------
# Benchmark 7: RedesignAudit <100ms
# ---------------------------------------------------------------------------


class TestRedesignAuditPerformance:
    """Verify RedesignAuditor.audit() on ~100 lines of code < 100ms."""

    def test_redesign_audit_100_lines_under_100ms(self) -> None:
        """Verify: RedesignAuditor.audit median latency < 100ms.

        Scenario: Audit a ~100-line code sample with several patterns.
        Expected: Median latency across 15 runs is under 100ms.
        """
        auditor = RedesignAuditor()
        code_sample = _build_100_line_code_sample()

        auditor.audit(code_sample)  # warmup

        median_ms = _measure_ms(lambda: auditor.audit(code_sample))
        assert median_ms < REDESIGN_AUDIT_TARGET_MS, (
            f"RedesignAuditor.audit median {median_ms:.3f}ms >= "
            f"{REDESIGN_AUDIT_TARGET_MS}ms target"
        )

    def test_redesign_audit_clean_code_under_100ms(self) -> None:
        """Verify: RedesignAuditor.audit on clean code < 100ms.

        Scenario: Audit a ~100-line code sample with no findings.
        Expected: Median latency across 15 runs is under 100ms.
        """
        auditor = RedesignAuditor()
        clean_code = _build_clean_code_sample()

        auditor.audit(clean_code)  # warmup

        median_ms = _measure_ms(lambda: auditor.audit(clean_code))
        assert median_ms < REDESIGN_AUDIT_TARGET_MS, (
            f"RedesignAuditor.audit (clean) median {median_ms:.3f}ms >= "
            f"{REDESIGN_AUDIT_TARGET_MS}ms target"
        )


# ---------------------------------------------------------------------------
# Benchmark 8: Full dispatch with all V3.9 modules <2s (mock mode)
# ---------------------------------------------------------------------------


class TestFullDispatchPerformance:
    """Verify a full dispatch with all V3.9 modules completes under 2s."""

    def test_full_dispatch_with_v39_modules_under_2s(self) -> None:
        """Verify: full dispatch (mock mode) median latency < 2s.

        Scenario: Configure a dispatcher with CodeKnowledgeGraph +
        DispatchRBAC + DispatchAuditLogger + MicroTaskPlanner, then
        dispatch a simple task in mock mode (no LLM backend).

        Expected: Median latency across 5 runs is under 2000ms.
        """
        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            mock_auth = MagicMock()
            mock_auth.credentials = {"admin_user": {"role": "admin"}}
            rbac = DispatchRBAC(auth_manager=mock_auth)
            audit = DispatchAuditLogger()
            planner = MicroTaskPlanner(yagni_checker=YagniChecker())

            # Warmup: one dispatch (not measured) to amortize cold-start.
            warmup_disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                code_graph=graph,
                micro_task_planner=planner,
                rbac=rbac,
                audit_logger=audit,
                enable_rbac=False,
            )
            warmup_disp.dispatch(
                "Write a hello function",
                roles=["solo-coder"],
                user_id="admin_user",
            )
            warmup_disp.shutdown()

            counter = [0]

            def _measured_dispatch() -> None:
                counter[0] += 1
                disp = MultiAgentDispatcher(
                    persist_dir=tmpdir,
                    code_graph=graph,
                    micro_task_planner=planner,
                    rbac=rbac,
                    audit_logger=audit,
                    enable_rbac=False,
                )
                result = disp.dispatch(
                    "Write a hello function",
                    roles=["solo-coder"],
                    user_id="admin_user",
                )
                assert result.success, (
                    f"Dispatch run {counter[0]} failed: {result.errors}"
                )
                disp.shutdown()

            # Use 5 runs (full dispatch is heavier than unit benchmarks).
            median_ms = _measure_ms(_measured_dispatch, runs=5)
            assert median_ms < FULL_DISPATCH_TARGET_MS, (
                f"Full dispatch median {median_ms:.3f}ms >= "
                f"{FULL_DISPATCH_TARGET_MS}ms target"
            )

            graph.close()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Benchmark 9: CodeKnowledgeGraph build_from_project <5s
# ---------------------------------------------------------------------------


class TestGraphBuildPerformance:
    """Verify CodeKnowledgeGraph.build_from_project() completes under 5s."""

    def test_build_from_collaboration_dir_under_5s(self) -> None:
        """Verify: build_from_project median latency < 5s.

        Scenario: Build the code graph from the real scripts/collaboration/
        directory (88+ Python files) and measure the build time.

        Expected: Median latency across 3 runs is under 5000ms.
        """
        project_root = Path(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "collaboration")
        ).resolve()
        assert project_root.is_dir(), (
            f"scripts/collaboration/ not found at {project_root}"
        )

        tmpdir = tempfile.mkdtemp(prefix="v39_perf_build_")
        try:
            # Warmup: one build (not measured).
            warmup_db = Path(tmpdir) / "warmup.db"
            warmup_graph = CodeKnowledgeGraph(warmup_db)
            warmup_graph.build_from_project(project_root)
            warmup_stats = warmup_graph.get_stats()
            warmup_graph.close()
            assert warmup_stats["files"] >= 10, (
                f"Expected >=10 files indexed, got {warmup_stats['files']}"
            )

            counter = [0]

            def _measured_build() -> None:
                counter[0] += 1
                db = Path(tmpdir) / f"build_{counter[0]}.db"
                g = CodeKnowledgeGraph(db)
                g.build_from_project(project_root)
                g.close()

            # Use 3 runs (full project build is the heaviest benchmark).
            median_ms = _measure_ms(_measured_build, runs=3)
            assert median_ms < GRAPH_BUILD_TARGET_MS, (
                f"build_from_project median {median_ms:.3f}ms >= "
                f"{GRAPH_BUILD_TARGET_MS}ms target"
            )
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Benchmark 10: DispatchAuditLogger verify_chain <500ms
# ---------------------------------------------------------------------------


class TestVerifyChainPerformance:
    """Verify DispatchAuditLogger.verify_chain() completes under 500ms."""

    def test_verify_chain_50_entries_under_500ms(self) -> None:
        """Verify: verify_chain (50 entries) median latency < 500ms.

        Scenario: Log 50 audit entries (alternating dispatch_start and
        dispatch_end), then call verify_chain to recompute all hashes.

        Expected: Median latency across 15 runs is under 500ms.
        """
        audit_logger = DispatchAuditLogger()

        # Populate the chain with 50 entries.
        for i in range(50):
            if i % 2 == 0:
                audit_logger.log_dispatch_start(
                    user_id=f"user_{i}",
                    task=f"task {i}",
                    roles=["architect"],
                )
            else:
                audit_logger.log_dispatch_end(
                    user_id=f"user_{i}",
                    success=True,
                    duration=0.5,
                )

        assert audit_logger.count() == 50, (
            f"Expected 50 entries, got {audit_logger.count()}"
        )

        # Warmup.
        audit_logger.verify_chain()

        median_ms = _measure_ms(lambda: audit_logger.verify_chain())
        assert median_ms < VERIFY_CHAIN_TARGET_MS, (
            f"verify_chain (50 entries) median {median_ms:.3f}ms >= "
            f"{VERIFY_CHAIN_TARGET_MS}ms target"
        )

    def test_verify_chain_empty_under_500ms(self) -> None:
        """Verify: verify_chain on empty chain median latency < 500ms.

        Scenario: An empty audit chain (no entries) is verified. This
        exercises the early-return path.

        Expected: Median latency across 15 runs is under 500ms.
        """
        audit_logger = DispatchAuditLogger()

        audit_logger.verify_chain()  # warmup

        median_ms = _measure_ms(lambda: audit_logger.verify_chain())
        assert median_ms < VERIFY_CHAIN_TARGET_MS, (
            f"verify_chain (empty) median {median_ms:.3f}ms >= "
            f"{VERIFY_CHAIN_TARGET_MS}ms target"
        )


# ---------------------------------------------------------------------------
# Code sample builders for the RedesignAudit benchmark
# ---------------------------------------------------------------------------


def _build_100_line_code_sample() -> str:
    """Build a ~100-line code sample with several redesign patterns.

    Includes: a factory class (OVERENGINEERING), a custom JSON wrapper
    (STDLIB), some duplicate lines (DUPLICATE), and a placeholder function
    (YAGNI). This exercises all four category checkers.
    """
    lines: list[str] = []
    lines.append('"""Sample module with several redesign opportunities."""')
    lines.append("import json")
    lines.append("import os")
    lines.append("import unused_module  # unused import")
    lines.append("")
    lines.append("")
    lines.append("class WidgetFactory:")
    lines.append('    """A factory class — overengineering."""')
    lines.append("")
    lines.append("    @staticmethod")
    lines.append("    def create_widget(name):")
    lines.append("        return Widget(name)")
    lines.append("")
    lines.append("")
    lines.append("class Widget:")
    lines.append('    """A widget."""')
    lines.append("")
    lines.append("    def __init__(self, name):")
    lines.append("        self.name = name")
    lines.append("")
    lines.append("    def render(self):")
    lines.append("        return f'<widget>{self.name}</widget>'")
    lines.append("")
    lines.append("")
    lines.append("def parse_json_wrapper(text):")
    lines.append('    """Wraps json.loads — stdlib replacement."""')
    lines.append("    return json.loads(text)")
    lines.append("")
    lines.append("")
    lines.append("def placeholder_function():")
    lines.append("    pass  # placeholder")
    lines.append("")
    lines.append("")
    lines.append("def process_item_a(item):")
    lines.append("    result = {}")
    lines.append("    result['name'] = item.name")
    lines.append("    result['value'] = item.value")
    lines.append("    result['type'] = 'a'")
    lines.append("    return result")
    lines.append("")
    lines.append("")
    lines.append("def process_item_b(item):")
    lines.append("    result = {}")
    lines.append("    result['name'] = item.name")
    lines.append("    result['value'] = item.value")
    lines.append("    result['type'] = 'b'")
    lines.append("    return result")
    lines.append("")
    lines.append("")
    lines.append("def process_item_c(item):")
    lines.append("    result = {}")
    lines.append("    result['name'] = item.name")
    lines.append("    result['value'] = item.value")
    lines.append("    result['type'] = 'c'")
    lines.append("    return result")
    lines.append("")
    lines.append("")
    lines.append("def main():")
    lines.append("    factory = WidgetFactory()")
    lines.append("    w = factory.create_widget('hello')")
    lines.append("    print(w.render())")
    lines.append("    data = parse_json_wrapper('{\"k\": 1}')")
    lines.append("    print(data)")
    lines.append("    placeholder_function()")
    lines.append("")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append("    main()")
    # Pad to ~100 lines with blank/comment lines (no new patterns).
    while len(lines) < 100:
        lines.append(f"# padding line {len(lines) + 1}")
    return "\n".join(lines)


def _build_clean_code_sample() -> str:
    """Build a ~100-line code sample with no redesign findings.

    Uses simple functions, no factories, no stdlib wrappers, no duplicates.
    """
    lines: list[str] = []
    lines.append('"""Clean sample module with no redesign opportunities."""')
    lines.append("import json")
    lines.append("")
    lines.append("")
    lines.append("def greet(name):")
    lines.append('    return f"Hello, {name}"')
    lines.append("")
    lines.append("")
    lines.append("def add(a, b):")
    lines.append("    return a + b")
    lines.append("")
    lines.append("")
    lines.append("def main():")
    lines.append("    print(greet('world'))")
    lines.append("    print(add(1, 2))")
    lines.append("    data = json.loads('{\"k\": 1}')")
    lines.append("    print(data)")
    lines.append("")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append("    main()")
    while len(lines) < 100:
        lines.append(f"# clean padding line {len(lines) + 1}")
    return "\n".join(lines)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--no-cov"])
