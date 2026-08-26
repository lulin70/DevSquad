#!/usr/bin/env python3
"""Unit tests for V4.5.0 FileBundler (PRD §10.1.3).

Iron Rules applied:
  1. Documentation-first: source (scripts/collaboration/file_bundler.py) read
     first. Documented: deterministic grouping (no LLM); same dir → same
     bundle; import chain → same bundle (via stdlib ``ast``); max_per_bundle
     overflow → split; ALL ast exceptions caught; module-level _call_counter_er.
  2. Failure-means-report: REAL files on disk via tempfile, no Mock.
  3. Dimension-completeness: 7 tests (directory / imports / max / single /
     empty / invalid-python / call-counter).
  4. Side-effect-verification: invalid Python is skipped (not crashed on);
     _call_counter_er increments.
  5. User-journey-first: bundle → review-unit split mirrors the review-mode
     divide-and-conquer journey.
  6. e2e-release-gate: covered by the broader V4.5.0 e2e suite.

Anti-ghost note: ``_call_counter_er`` is a module-level int on ``file_bundler``.
We read it via module attribute access (``fb_module._call_counter_er``), NOT
``from module import _call_counter_er`` (which would snapshot a stale int).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration import file_bundler as fb_module  # noqa: E402
from scripts.collaboration.file_bundler import FileBundler  # noqa: E402


class TestFileBundler(unittest.TestCase):
    """V4.5.0 FileBundler unit tests (7 tests)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="devsquad_fb_")
        self._bundler = FileBundler()

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write(self, rel_path: str, content: str) -> str:
        """Write a file under the temp dir and return its full path."""
        full = Path(self._tmpdir) / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return str(full)

    @staticmethod
    def _bundles_contain_together(bundles: list[list[str]], a: str, b: str) -> bool:
        """True if files ``a`` and ``b`` appear in the SAME bundle."""
        return any(a in bundle and b in bundle for bundle in bundles)

    # ------------------------------------------------------------------
    # 1. files in the same directory → same bundle
    # ------------------------------------------------------------------

    def test_bundle_by_directory(self) -> None:
        """Happy: files sharing a parent directory land in the same bundle;
        files in different directories (no import link) land in separate
        bundles."""
        f1 = self._write("auth/login.py", "# login module\n")
        f2 = self._write("auth/session.py", "# session module\n")
        f3 = self._write("billing/invoice.py", "# invoice module\n")

        bundles = self._bundler.bundle([f1, f2, f3], max_per_bundle=10)

        self.assertEqual(len(bundles), 2, f"expected 2 bundles, got {bundles}")
        # login.py and session.py share auth/ → same bundle.
        self.assertTrue(
            self._bundles_contain_together(bundles, f1, f2),
            f"same-directory files not grouped together: {bundles}",
        )
        # invoice.py is in a different directory with no import link → separate.
        self.assertFalse(
            self._bundles_contain_together(bundles, f1, f3),
            f"different-directory files incorrectly merged: {bundles}",
        )

    # ------------------------------------------------------------------
    # 2. file A imports file B → same bundle
    # ------------------------------------------------------------------

    def test_bundle_by_imports(self) -> None:
        """Happy: when file A imports file B (and they live in different
        directories), the import chain merges them into one bundle."""
        # helper.py lives in utils/; importer.py lives in services/ and
        # imports helper. Without import-merging they'd be in 2 bundles.
        helper = self._write("utils/helper.py", "def assist():\n    return 42\n")
        importer = self._write(
            "services/importer.py",
            "import helper\n\n\ndef run():\n    return helper.assist()\n",
        )

        bundles = self._bundler.bundle([helper, importer], max_per_bundle=10)

        # Import chain → single merged bundle (not 2 separate dir bundles).
        self.assertEqual(len(bundles), 1, f"import-merged files should be 1 bundle: {bundles}")
        self.assertTrue(
            self._bundles_contain_together(bundles, helper, importer),
            f"import-linked files not merged: {bundles}",
        )

    # ------------------------------------------------------------------
    # 3. max_per_bundle: 15 files, max=10 → at least 2 bundles
    # ------------------------------------------------------------------

    def test_max_per_bundle(self) -> None:
        """Boundary: 15 files in one directory with max_per_bundle=10 must
        split into at least 2 bundles, each of size ≤ 10."""
        files = [self._write(f"src/module_{i}.py", f"# module {i}\n") for i in range(15)]

        bundles = self._bundler.bundle(files, max_per_bundle=10)

        # All 15 files accounted for.
        total = sum(len(b) for b in bundles)
        self.assertEqual(total, 15, f"file count changed: {bundles}")
        # At least 2 bundles (15 / 10 → ceil = 2).
        self.assertGreaterEqual(len(bundles), 2, f"expected ≥2 bundles, got {len(bundles)}")
        # No bundle exceeds the max.
        for b in bundles:
            self.assertLessEqual(len(b), 10, f"bundle exceeds max: {b}")

    # ------------------------------------------------------------------
    # 4. single file → single bundle
    # ------------------------------------------------------------------

    def test_single_file(self) -> None:
        """Boundary: a single input file yields exactly one bundle containing
        that one file."""
        only = self._write("solo/lonely.py", "# all alone\n")

        bundles = self._bundler.bundle([only], max_per_bundle=10)

        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0], [only])

    # ------------------------------------------------------------------
    # 5. empty list → empty list
    # ------------------------------------------------------------------

    def test_empty_list(self) -> None:
        """Boundary: an empty file list yields an empty bundle list (not an
        error, not a [[]])."""
        bundles = self._bundler.bundle([], max_per_bundle=10)
        self.assertEqual(bundles, [])

    # ------------------------------------------------------------------
    # 6. invalid Python (syntax error) → grouped by directory only, no crash
    # ------------------------------------------------------------------

    def test_invalid_python_skipped(self) -> None:
        """Error/Side-Effect: a file with a Python syntax error does NOT crash
        the bundler. Its imports cannot be parsed, so it is grouped by
        directory only (no import-based merge)."""
        # broken.py has a syntax error AND an (unreachable) import of helper.
        # Because ast.parse fails, the `import helper` is never seen, so
        # broken.py and helper.py do NOT merge across directories.
        broken = self._write(
            "pkg_a/broken.py",
            "import helper\n\ndef bad(:\n    pass\n",  # syntax error: `def bad(:`
        )
        helper = self._write("pkg_b/helper.py", "def assist():\n    return 1\n")

        # Must not raise.
        bundles = self._bundler.bundle([broken, helper], max_per_bundle=10)

        # No crash, 2 files accounted for.
        total = sum(len(b) for b in bundles)
        self.assertEqual(total, 2, f"file count changed: {bundles}")
        # broken.py's `import helper` was NOT detected (syntax error) → the
        # two files stay in separate bundles (grouped by directory only).
        self.assertFalse(
            self._bundles_contain_together(bundles, broken, helper),
            f"syntax-error file's import should not merge: {bundles}",
        )
        self.assertGreaterEqual(len(bundles), 2, f"expected ≥2 bundles, got {len(bundles)}")

    # ------------------------------------------------------------------
    # 7. anti-ghost: module-level _call_counter_er increments
    # ------------------------------------------------------------------

    def test_call_counter_er(self) -> None:
        """Side-Effect: module-level ``_call_counter_er`` increments on every
        ``bundle()`` call (anti-ghost guarantee)."""
        before = fb_module._call_counter_er
        self._bundler.bundle([], max_per_bundle=10)
        self._bundler.bundle(["x.py"], max_per_bundle=10)
        self._bundler.bundle(["a.py", "b.py"], max_per_bundle=5)
        after = fb_module._call_counter_er
        self.assertGreater(after, before, "module _call_counter_er did not increment")
        # 3 bundle() calls => at least 3 increments.
        self.assertGreaterEqual(after - before, 3)


if __name__ == "__main__":
    unittest.main()
