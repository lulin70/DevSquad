"""P8-005: DuplicationGate wiring integration tests (TD-078 / W2).

Verifies the real wiring — not mocks — because the anti-ghost principle
requires gate modules to be *activated*, not just importable:

- DuplicationGate.check() runs for real inside SimplicityRole._audit()
- the worse of CRAP/duplication statuses wins
- duplication metrics land in SimplicityAuditResult.metrics
"""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_workflow_trace():
    trace = Mock()
    trace.record = Mock()
    return trace


@pytest.fixture
def mock_engine():
    return Mock()


def _make_plan(tmp_path, target_files):
    plan = Mock()
    plan.phase = "P8"
    plan.target_files = target_files
    plan.p3_doc = ""
    plan.p7_doc = ""
    plan.test_paths = []
    return plan


_CRAP_PASS = {"status": "PASS", "max_crap": 5.0, "violations": [], "summary": "OK"}


def _activate(role, plan):
    """Run activate() with CRAPGate mocked (radon not in test deps) while
    keeping DuplicationGate REAL — the module under test for P8-005."""
    from scripts.collaboration.gates.crap_gate import CRAPGate

    with (
        patch.dict(os.environ, {"DEVSQUAD_SKIP_SIMPLICITY": ""}),
        patch.object(CRAPGate, "check", return_value=dict(_CRAP_PASS)),
    ):
        return role.activate(plan, [])


class TestDuplicationGateWiring:
    """P8-005 integration: real DuplicationGate inside the S2 audit."""

    def test_unique_file_passes_with_real_metrics(self, tmp_path, mock_workflow_trace, mock_engine) -> None:
        """A small unique file runs both gates and reports duplication metrics."""
        from scripts.collaboration.simplicity_role import SimplicityRole

        target = tmp_path / "unique.py"
        target.write_text("def only_here():\n    return 42\n")

        role = SimplicityRole(mock_workflow_trace, mock_engine)
        result = _activate(role, _make_plan(tmp_path, [str(target)]))

        assert result is not None
        assert result.metrics["duplication_rate"] == 0.0
        assert result.metrics["duplication_clones"] == 0
        assert result.metrics["max_crap"] >= 0

    def test_duplicated_files_trigger_warning(self, tmp_path, mock_workflow_trace, mock_engine) -> None:
        """Two files with a >50-token duplicated block raise the WARNING path."""
        from scripts.collaboration.simplicity_role import SimplicityRole

        # A long, token-identical block duplicated across two files (>50 tokens).
        duplicated_body = "\n".join(
            [
                "import os",
                "import sys",
                "import json",
                "def process(alpha, beta, gamma):",
                "    total = 0",
                "    for index in range(alpha):",
                "        total += index * beta",
                "        if total > gamma:",
                "            total -= gamma",
                "        elif total < -gamma:",
                "            total += beta",
                "    result = {'total': total, 'alpha': alpha}",
                "    payload = json.dumps(result)",
                "    with open('/dev/null', 'w') as handle:",
                "        handle.write(payload)",
                "    sys.stderr.write(str(total))",
                "    os.path.join('a', 'b', 'c', 'd')",
                "    return total",
            ]
        )
        file_a = tmp_path / "module_a.py"
        file_a.write_text(duplicated_body)
        file_b = tmp_path / "module_b.py"
        file_b.write_text(duplicated_body)

        role = SimplicityRole(mock_workflow_trace, mock_engine)
        result = _activate(role, _make_plan(tmp_path, [str(file_a), str(file_b)]))

        assert result is not None
        assert result.metrics["duplication_rate"] > 0.0
        assert result.metrics["duplication_clones"] >= 1
        # Any duplication signal must surface in warnings or violations
        assert result.warnings or result.violations

    def test_worse_status_wins_when_dup_rejects(self, tmp_path, mock_workflow_trace, mock_engine) -> None:
        """REJECT from the duplication gate overrides a CRAP PASS status."""
        from scripts.collaboration.gates.duplication_gate import DuplicationGate
        from scripts.collaboration.simplicity_role import SimplicityRole

        duplicated_body = "x = 1 + 2 + 3 + 4\n" * 40
        file_a = tmp_path / "dup_a.py"
        file_a.write_text(duplicated_body)
        file_b = tmp_path / "dup_b.py"
        file_b.write_text(duplicated_body)

        plan = _make_plan(tmp_path, [str(file_a), str(file_b)])

        with (
            patch.dict(os.environ, {"DEVSQUAD_SKIP_SIMPLICITY": ""}),
            patch("scripts.collaboration.gates.crap_gate.CRAPGate.check", return_value=dict(_CRAP_PASS)),
            patch.object(
                DuplicationGate,
                "check",
                return_value={
                    "status": "REJECT",
                    "duplication_rate": 0.95,
                    "clones": [{"file1": "dup_a.py", "file2": "dup_b.py", "line1": 1, "line2": 1, "tokens": 50}],
                    "total_clones": 1,
                },
            ),
        ):
            role = SimplicityRole(mock_workflow_trace, mock_engine)
            result = role.activate(plan, [])

        assert result is not None
        assert result.status == "REJECT"
        assert any("Duplication rate" in v for v in result.violations)
        assert any("shared helpers" in r for r in result.recommendations)
