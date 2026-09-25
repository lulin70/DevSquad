#!/usr/bin/env python3
"""Unit tests for V4.5.20 W1-0 ``check_skill_contract.py`` — contract drift gate.

Iron Rules applied:
  1. Documentation-first: the source (``scripts/check_skill_contract.py``) and the
     two documents it guards were read before this file was written. The gate
     checks clause ids, keywords, ``Effective`` tokens, and that each ``Effective``
     wave still exists in the PRD.
  2. Failure-means-report: real documents, real files, no Mock. Every negative
     case mutates a **copy** of the live document, so the test cannot pass because
     of a stale fixture.
  3. Dimension-completeness: Happy path / Error / Boundary / Config / Side-effect.
  4. Side-effect-verification: ``main()`` exit codes 0 and 1 and 2 all asserted.
  5. User-journey-first: mirrors how the gate is run — a maintainer edits a doc,
     CI must go red for the right reason.
  6. e2e-release-gate: this IS the gate module under test.

Why the live repo is used as the fixture source: the gate's whole job is to
compare a document against a clause table, and a hand-written miniature document
would only prove the comparison works on a document written to pass it. Copying
the real one and deleting exactly one thing per test proves the check can fail.

Coverage of the gate's own honesty claim: ``check_skill_contract.py`` states it
verifies *presence, not behaviour*. Several tests below pin that down — e.g. a
clause whose text is present but whose wave was renamed must fail as a *dangling
annotation*, not silently pass.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts import check_skill_contract as csc  # noqa: E402
from scripts.check_skill_contract import (  # noqa: E402
    CONTRACT_CLAUSES,
    CONTRACT_DOC,
    PRD_DOC,
    SKILL_COMMITMENTS,
    SKILL_DOC,
    _wave_exists_in_prd,
    check_clause,
    check_commitment,
    main,
    run,
)

# The three documents the gate reads, copied into a temp root per test.
_DOC_RELATIVE_PATHS = (SKILL_DOC, CONTRACT_DOC, PRD_DOC)


class _DocRoot:
    """A throwaway repo root holding copies of the three real documents."""

    def __init__(self) -> None:
        self.path = Path(tempfile.mkdtemp(prefix="devsquad_skc_"))
        for relative in _DOC_RELATIVE_PATHS:
            source = Path(_PROJECT_ROOT) / relative
            target = self.path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def read(self, relative: str) -> str:
        return (self.path / relative).read_text(encoding="utf-8")

    def replace(self, relative: str, old: str, new: str) -> None:
        """Replace text in a copy; fail loudly if the anchor is absent."""
        path = self.path / relative
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"test anchor {old!r} not found in {relative}")
        path.write_text(text.replace(old, new), encoding="utf-8")

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class T1_HappyPath(unittest.TestCase):
    """T1: the live repo satisfies its own contract."""

    def test_01_live_repo_has_no_problems(self) -> None:
        """Verify: run() on the real repo returns no problems."""
        self.assertEqual(run(Path(_PROJECT_ROOT)), [])

    def test_02_main_exits_zero_on_live_repo(self) -> None:
        """Verify: CLI exit code is 0 when the contract is intact."""
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 0)

    def test_03_quiet_suppresses_success_output(self) -> None:
        """Verify: --quiet prints nothing at all when passing."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            main(["--quiet"])
        self.assertEqual(buffer.getvalue(), "")


class T2_ClauseIntegrity(unittest.TestCase):
    """T2: the clause table itself is well-formed and non-vacuous."""

    def test_04_clause_ids_are_unique(self) -> None:
        """Verify: no duplicate id — a duplicate would silently shadow a clause."""
        ids = [clause.id for clause in CONTRACT_CLAUSES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_05_ids_and_keywords_are_substantive(self) -> None:
        """Verify: every clause has a dotted id and at least two keywords."""
        for clause in CONTRACT_CLAUSES:
            self.assertIn(".", clause.id)
            self.assertGreaterEqual(len(clause.keywords), 2)

    def test_06_commitment_ids_are_unique(self) -> None:
        """Verify: SKILL.md commitment ids are unique too."""
        ids = [commitment.id for commitment in SKILL_COMMITMENTS]
        self.assertEqual(len(ids), len(set(ids)))


class T3_DriftDetection(unittest.TestCase):
    """T3: each check that the gate claims to perform actually fires."""

    def setUp(self) -> None:
        self.root = _DocRoot()

    def tearDown(self) -> None:
        self.root.cleanup()

    def test_07_deleted_keyword_is_reported(self) -> None:
        """Verify: renaming a gate name in the doc breaks the gate."""
        self.root.replace(CONTRACT_DOC, "unsupported_ext", "unsupported_type")
        problems = run(self.root.path)
        self.assertEqual(len(problems), 1)
        self.assertIn("unsupported_ext", problems[0])
        self.assertIn("gate.named_exclusion_reasons", problems[0])

    def test_08_deleted_clause_id_is_reported(self) -> None:
        """Verify: removing a clause heading is reported as a missing id."""
        self.root.replace(CONTRACT_DOC, "`rule.first_match_wins`", "`rule.first_wins`")
        problems = run(self.root.path)
        self.assertIn("clause id is missing", " ".join(problems))

    def test_09_blanked_effective_cell_is_reported(self) -> None:
        """Verify: blanking one clause's Effective cell is caught row-scoped.

        A document-wide search would miss this, because the two other gate rows
        (C2/C3) still carry the string ``W1-3`` (found by the W1-0 negative pass — N2).
        """
        self.root.replace(
            CONTRACT_DOC,
            "| C1 | `gate.secret_exclude_priority` | Filter gates | W1-3 |",
            "| C1 | `gate.secret_exclude_priority` | Filter gates |  |",
        )
        clause = next(c for c in CONTRACT_CLAUSES if c.id == "gate.secret_exclude_priority")
        problems = check_clause(
            clause,
            self.root.read(CONTRACT_DOC),
            self.root.read(PRD_DOC),
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("clause index row declares Effective ''", problems[0])

    def test_09b_clause_without_index_row_is_reported(self) -> None:
        """Verify: a clause missing from the index table is reported, not skipped."""
        self.root.replace(
            CONTRACT_DOC,
            "| C1 | `gate.secret_exclude_priority` | Filter gates | W1-3 |\n",
            "",
        )
        clause = next(c for c in CONTRACT_CLAUSES if c.id == "gate.secret_exclude_priority")
        problems = check_clause(
            clause,
            self.root.read(CONTRACT_DOC),
            self.root.read(PRD_DOC),
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("has no row in the clause index", problems[0])

    def test_10_dangling_wave_is_reported(self) -> None:
        """Verify: a wave renamed in the PRD makes the annotation dangle."""
        self.root.replace(PRD_DOC, "W1-3", "W1-9")
        problems = run(self.root.path)
        self.assertEqual(len(problems), 3)
        for problem in problems:
            self.assertIn("dangling annotation", problem)

    def test_11_drift_exits_one_not_two(self) -> None:
        """Verify: main() exits 1 (not 2) for a content drift."""
        self.root.replace(CONTRACT_DOC, "unsupported_ext", "unsupported_type")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--root", str(self.root.path)]), 1)


class T4_SkillCommitments(unittest.TestCase):
    """T4: the three caller-facing commitments stay visible in SKILL.md."""

    def setUp(self) -> None:
        self.root = _DocRoot()

    def tearDown(self) -> None:
        self.root.cleanup()

    def test_12_removed_commitment_is_reported(self) -> None:
        """Verify: dropping the non-zero-exit promise fails the gate."""
        self.root.replace(SKILL_DOC, "Incomplete coverage exits non-zero.", "Coverage runs.")
        problems = run(self.root.path)
        self.assertEqual(len(problems), 1)
        self.assertIn("skill.coverage_nonzero_exit", problems[0])

    def test_13_commitment_check_reports_each_missing_keyword(self) -> None:
        """Verify: a partially deleted commitment names every missing keyword."""
        problems = check_commitment(SKILL_COMMITMENTS[0], "nothing here")
        self.assertEqual(len(problems), len(SKILL_COMMITMENTS[0].keywords))

    def test_14_every_commitment_is_present_in_skill_md(self) -> None:
        """Verify: all four commitments are currently satisfied by SKILL.md."""
        skill_text = (Path(_PROJECT_ROOT) / SKILL_DOC).read_text(encoding="utf-8")
        for commitment in SKILL_COMMITMENTS:
            self.assertEqual(check_commitment(commitment, skill_text), [], commitment.id)


class T5_Boundaries(unittest.TestCase):
    """T5: boundaries of the wave matcher and of check_clause."""

    def test_15_wave_matcher_rejects_longer_identifiers(self) -> None:
        """Verify: W1-1 does not match inside W1-10 (no prefix collision)."""
        self.assertEqual(_wave_exists_in_prd("W1-1", "step W1-10 shipped"), False)
        self.assertEqual(_wave_exists_in_prd("W1-1", "step W1-1 shipped"), True)

    def test_16_wave_matcher_ignores_word_internal_hyphens(self) -> None:
        """Verify: a hyphen-joined token is not accepted as a wave."""
        self.assertEqual(_wave_exists_in_prd("W1-1", "see xW1-1"), False)

    def test_17_shipped_clause_is_not_treated_as_a_wave(self) -> None:
        """Verify: 'shipped in V4.5.10' is version evidence, not a wave lookup."""
        shipped = [clause for clause in CONTRACT_CLAUSES if not clause.is_wave]
        self.assertGreaterEqual(len(shipped), 1)
        for clause in shipped:
            with self.subTest(clause=clause.id):
                self.assertIn("shipped in", clause.effective)

    def test_18_check_clause_accumulates_every_problem(self) -> None:
        """Verify: a shipped clause is reported for id, keywords and token."""
        clause = next(clause for clause in CONTRACT_CLAUSES if not clause.is_wave)
        problems = check_clause(clause, "", "")
        # Missing id + every keyword + the missing effective token. A wave clause
        # would add one more: the dangling annotation.
        self.assertEqual(len(problems), 2 + len(clause.keywords))


class T6_ErrorHandling(unittest.TestCase):
    """T6: the gate distinguishes 'drift' from 'cannot read'."""

    def test_19_missing_document_exits_two(self) -> None:
        """Verify: an unreadable document is exit 2, never exit 1."""
        root = _DocRoot()
        try:
            os.remove(root.path / CONTRACT_DOC)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["--root", str(root.path)]), 2)
            self.assertIn("cannot read contract source", err.getvalue())
        finally:
            root.cleanup()

    def test_20_missing_skill_doc_exits_two(self) -> None:
        """Verify: the same holds for SKILL.md — the failure is not doc-specific."""
        root = _DocRoot()
        try:
            os.remove(root.path / SKILL_DOC)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--root", str(root.path)]), 2)
        finally:
            root.cleanup()

    def test_21_module_constants_point_at_real_paths(self) -> None:
        """Verify: the three guarded paths exist in the live repo."""
        for relative in _DOC_RELATIVE_PATHS:
            with self.subTest(relative=relative):
                self.assertEqual((Path(_PROJECT_ROOT) / relative).is_file(), True)

    def test_22_clause_docstring_records_the_honesty_boundary(self) -> None:
        """Verify: the module still admits it checks presence, not behaviour."""
        doc = csc.__doc__ or ""
        self.assertIn("cannot prove semantics", doc)
        self.assertIn("drift", doc.lower())


if __name__ == "__main__":
    unittest.main()
