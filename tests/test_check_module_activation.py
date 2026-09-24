#!/usr/bin/env python3
"""Tests for the V4.5.20 D7 anti-ghost discriminator in check_module_activation.

Background (finding F4 / decision D7): the gate used to call every module
directly and then assert ``_call_counter_er > 0``. The gate satisfied its own
assertion, so the check was vacuous — ``FileBundler_V450`` stayed green for
nineteen releases while ``Coordinator.apply_file_bundling`` had no production
caller. The V4.5.20 fix runs a production probe (real ``dispatch()`` calls)
*before* any direct call, and requires ``PRODUCTION_WIRED_COUNTERS`` modules to
be bumped by that probe rather than by the gate itself.

Coverage dimensions (per DevSquad Iron Rule 3):
  - Happy Path: the probe bumps every production-wired counter
  - Error Case: a module reachable only via self-call is flagged, gate returns 1
  - Regression: severing the review wiring (the F4 failure mode) turns the gate
    red on FileBundler_V450 — the exact case the old gate missed
  - Configuration: the report distinguishes production / self-call evidence
  - Test discipline (F4 delivery requirement 4): an e2e test whose name claims
    activation must reach a production entry point, otherwise the gate fails
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts import check_module_activation as gate
from scripts.collaboration import dispatch_pre_steps

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_main_capturing_output() -> tuple[int, str]:
    """Run ``gate.main()`` and return (exit_code, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = gate.main()
    return rc, buf.getvalue()


class T1_ProductionProbe(unittest.TestCase):
    """T1: ``_production_probe()`` measures real dispatch-driven counter deltas."""

    def test_every_production_wired_counter_is_bumped_by_dispatch(self) -> None:
        """All declared production-wired modules must be reachable from dispatch."""
        deltas = gate._production_probe()
        self.assertEqual(set(deltas), set(gate.PRODUCTION_WIRED_COUNTERS))
        not_wired = {name: delta for name, delta in deltas.items() if delta <= 0}
        self.assertEqual(
            not_wired,
            {},
            f"counter(s) not bumped by a real dispatch: {not_wired}",
        )

    def test_probe_changeset_exceeds_the_bundling_guard(self) -> None:
        """The probe changeset must trip ``len(files) > 5`` so bundling runs."""
        self.assertGreater(len(gate.REVIEW_PROBE_CHANGESET), 5)


class T2_SelfCallDiscriminator(unittest.TestCase):
    """T2: the report distinguishes production evidence from gate self-calls."""

    def test_gate_passes_and_reports_both_evidence_classes(self) -> None:
        rc, out = _run_main_capturing_output()
        self.assertEqual(rc, 0, out[-2000:])
        expected = f"{len(gate.PRODUCTION_WIRED_COUNTERS)}/{len(gate.PRODUCTION_WIRED_COUNTERS)}"
        self.assertIn(f"Anti-ghost gate PASSED: {expected} production-verified", out)
        self.assertIn("[PASS (production +", out)
        self.assertIn("[PASS (self-call)]", out)

    def test_module_without_production_path_is_flagged_and_fails(self) -> None:
        """Pretending MokaAIBackend is production-wired must turn the gate red.

        Measured basis: ``dispatch(auto)`` + ``dispatch(review)`` leave
        ``moka_backend._call_counter_er`` unchanged (delta 0), so the only reason
        its counter is > 0 in the report is the gate's own direct call.
        """
        with mock.patch.dict(
            gate.PRODUCTION_WIRED_COUNTERS,
            {"MokaAIBackend_P12.1.1": "scripts.collaboration.moka_backend"},
        ):
            rc, out = _run_main_capturing_output()
        self.assertEqual(rc, 1, out[-2000:])
        self.assertIn("MokaAIBackend_P12.1.1", out)
        self.assertIn("FAIL (self-call only)", out)


class T3_F4Regression(unittest.TestCase):
    """T3: severing the review wiring reproduces F4 and must be detected."""

    def test_severed_review_wiring_turns_file_bundler_red(self) -> None:
        """Force ``changeset=None`` — the V4.5.19 ghost state — gate must fail."""
        original = dispatch_pre_steps.PreDispatchPipeline.prepare_execution

        def _severed(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["changeset"] = None
            return original(self, *args, **kwargs)

        with mock.patch.object(
            dispatch_pre_steps.PreDispatchPipeline,
            "prepare_execution",
            _severed,
        ):
            rc, out = _run_main_capturing_output()
        self.assertEqual(rc, 1, out[-2000:])
        self.assertIn("FileBundler_V450", out)
        self.assertRegex(out, r"FileBundler_V450\s+counter=\s*\d+\s+\[FAIL \(self-call only\)\]")


class T4_ActivationClaimDiscipline(unittest.TestCase):
    """T4: e2e activation claims must be backed by a real execution path.

    F4 delivery requirement 4 — the pre-fix ``test_v450_features_e2e.py`` was
    named ``..._activates_in_review_mode`` while its body merely imported
    ``FileBundler`` and called it. The scan below reproduces that distinction.
    """

    def _scan_source(self, source: str) -> list[tuple[str, str]]:
        """Write ``source`` into a ``tests/e2e`` tree and scan it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            e2e_dir = Path(tmpdir) / "tests" / "e2e"
            e2e_dir.mkdir(parents=True)
            (e2e_dir / "test_synthetic.py").write_text(source, encoding="utf-8")
            return gate.find_unbacked_activation_claims(e2e_dir)

    def test_repo_e2e_tree_has_no_unbacked_activation_claims(self) -> None:
        """The real e2e tree must be clean — otherwise the gate would be red."""
        violations = gate.find_unbacked_activation_claims(_REPO_ROOT / "tests" / "e2e")
        self.assertEqual(violations, [], f"unbacked activation claims: {violations}")

    def test_direct_import_test_is_flagged(self) -> None:
        """The exact F4 shape — claim in the name, direct import in the body."""
        source = (
            "def test_file_bundler_activates_in_review_mode() -> None:\n"
            "    from scripts.collaboration.file_bundler import FileBundler\n"
            "    assert FileBundler().bundle(['a.py', 'b.py'])\n"
        )
        violations = self._scan_source(source)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][1], "test_file_bundler_activates_in_review_mode")

    def test_dispatch_backed_test_is_not_flagged(self) -> None:
        """A claim backed by a real ``dispatch()`` call passes the scan."""
        source = (
            "def test_feature_activates_via_dispatch() -> None:\n"
            "    result = dispatcher.dispatch('task', mode='review', changeset=['a.py'])\n"
            "    assert result.success\n"
        )
        self.assertEqual(self._scan_source(source), [])

    def test_docstring_mention_does_not_back_a_claim(self) -> None:
        """Only real call sites count — a docstring mention is not evidence."""
        source = (
            "def test_widget_activates_through_dispatch() -> None:\n"
            '    """We would like dispatch() to reach this module."""\n'
            "    assert True\n"
        )
        violations = self._scan_source(source)
        self.assertEqual(len(violations), 1)

    def test_gate_main_fails_when_claim_is_unbacked(self) -> None:
        """``main()`` must fail closed on an unbacked activation claim."""
        fake = [("tests/e2e/test_synthetic.py", "test_thing_activates")]
        with mock.patch.object(gate, "find_unbacked_activation_claims", return_value=fake):
            rc, out = _run_main_capturing_output()
        self.assertEqual(rc, 1, out[-2000:])
        self.assertIn("UNBACKED ACTIVATION CLAIMS", out)
        self.assertIn("test_thing_activates", out)


if __name__ == "__main__":
    unittest.main()
