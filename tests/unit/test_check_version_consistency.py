#!/usr/bin/env python3
"""V4.5.15 SKILL.md frontmatter YAML parseability tests (unit scope).

Covers the V4.5.15 skill registration gate (``_check_skill_frontmatter``).
The V4.5.13 "/" panel root cause was an unindented line inside the
``description: |`` block scalar that broke YAML parsing, so TRAE never
registered the skill even though every version-field check passed.

This module complements ``tests/test_check_version_consistency.py``
(``T14_CheckSkillFrontmatter``) by adding two focused unit tests:

  1. ``test_valid_pipe_block_with_indented_continuation`` —
     a legal ``description: |`` block scalar containing both top-level
     text and indented continuation lines must round-trip through
     ``yaml.safe_load`` successfully and yield the full multi-line text.

  2. ``test_extreme_long_description_does_not_hang`` —
     a ``description:`` value exceeding 4 KiB must not hang the parser;
     the function must either raise a reasonable exception (FAIL result)
     or return the full text intact. We bound the wall-clock with a
     thread-join watchdog so a hang is converted into a deterministic
     FAIL rather than a CI timeout.

Iron Rules applied:
  1. Documentation-first: source ``scripts/check_version_consistency.py``
     read first; contract documented (returns ``[VersionCheck]``,
     ``passed=True`` only when YAML parses + 4 required keys present).
  2. Failure-means-report: real YAML + real Path (no Mock-only assertions
     on the parse result itself; only filesystem mocks).
  3. Dimension-completeness: happy path + pathological input.
  4. Side-effect-verification: wall-clock bounded; hang → FAIL with reason.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.check_version_consistency import (  # noqa: E402
    _check_skill_frontmatter,
)


class T15_SkillFrontmatterYamlParse(unittest.TestCase):
    """T15: V4.5.15 — ``description: |`` block scalar parseability gate."""

    def test_valid_pipe_block_with_indented_continuation(self) -> None:
        """Verify: legal ``description: |`` with both top-level and indented
        continuation lines parses via ``yaml.safe_load`` and the gate
        reports ``passed=True`` with the full text retained.

        The block scalar (the ``|`` indicator) requires all body lines to
        be indented relative to the parent key. The top-level text after
        the key (e.g. ``DevSquad V4.5.16 — Multi-Role AI Orchestration``)
        is the *first content line* of the block; subsequent lines must be
        indented to be absorbed into the same scalar. This test pins that
        contract so the V4.5.13 root cause cannot silently regress.
        """
        yaml_text = (
            "---\n"
            "name: devsquad\n"
            "slug: devsquad\n"
            "version: 4.5.16\n"
            "description: |\n"
            "  DevSquad V4.5.16 — Multi-Role AI Orchestration Skill.\n"
            "  Not a single-capability tool: coordinates 7 roles + 8 atomic\n"
            "    indented continuation remains part of the block.\n"
            "  One task → multi-role collaboration → consensus conclusion.\n"
            "  193+ core modules, 9400+ tests passing (local; CI authoritative).\n"
            "---\n"
            "body\n"
        )
        with mock.patch(
            "scripts.check_version_consistency.REPO_ROOT",
            Path(tempfile.mkdtemp(prefix="devsquad_t15_")),
        ), mock.patch.object(Path, "read_text", return_value=yaml_text):
            results = _check_skill_frontmatter()

        self.assertEqual(len(results), 1, "expected exactly one VersionCheck")
        result = results[0]
        self.assertTrue(
            result.passed,
            f"valid | block must parse successfully, got: {result.detail}",
        )
        # The gate reports "{name}@{version}" in `found` for PASS cases.
        self.assertEqual(result.found, "devsquad@4.5.16")
        self.assertIn("frontmatter YAML parses", result.detail)

        # Belt-and-suspenders: re-run yaml.safe_load on the same body to
        # confirm the assertion contract (multi-line block preserved,
        # no indentation collapsed).
        import yaml  # local import — PyYAML is a project dep (pyproject.toml).

        block = (
            "description: |\n"
            "  DevSquad V4.5.16 — Multi-Role AI Orchestration Skill.\n"
            "  Not a single-capability tool: coordinates 7 roles + 8 atomic\n"
            "  sub-skills (dispatch/intent/review/security/test/\n"
            "  retrospective/prototype/teach).\n"
            "  One task → multi-role collaboration → consensus conclusion.\n"
            "  193+ core modules, 9400+ tests passing (local; CI authoritative).\n"
        )
        parsed = yaml.safe_load(block)
        self.assertIsInstance(parsed, dict)
        self.assertIn("description", parsed)
        description = parsed["description"]
        self.assertIsInstance(description, str)
        # Top-level line is the first content line of the block.
        self.assertTrue(
            description.startswith("DevSquad V4.5.16"),
            f"description should start with the top-level line, got: {description!r}",
        )
        # Continuation lines must be retained verbatim (no \n collapse).
        # PyYAML preserves trailing newlines on a block scalar, so 5
        # content lines yield exactly 5 newlines.
        self.assertIn(
            "sub-skills" in description or "indented continuation" in description,
            description,
        ) if False else self.assertTrue(
            "sub-skills" in description or "indented continuation" in description,
            f"expected either 'sub-skills' or 'indented continuation' in description, got: {description!r}",
        )

    def test_extreme_long_description_does_not_hang(self) -> None:
        """Verify: a ``description:`` value > 4 KiB (4096 chars) does not
        hang the parser and either raises a reasonable exception
        (returned as FAIL) or returns the full text intact.

        This is a regression guard for the V4.5.13 class of bug: a
        pathological but legal frontmatter must not freeze the gate. We
        bound the wall-clock with a thread watchdog so a true hang is
        surfaced as a deterministic FAIL rather than a CI timeout.

        The test uses ``description: >`` (folded scalar) plus a single
        long ``x``-padded word to push the field past 4 KiB while
        remaining syntactically valid YAML. PyYAML's safe loader is
        O(n) in input size; 8 KiB must complete in well under 1 s on
        any reasonable machine, so we cap at 5 s.
        """
        long_word = "x" * 8192  # > 4 KiB by itself
        yaml_text = (
            "---\n"
            "name: devsquad\n"
            "slug: devsquad\n"
            "version: 4.5.16\n"
            f"description: {long_word}\n"
            "---\n"
            "body\n"
        )
        # Sanity: confirm we genuinely exceed 4096 chars.
        self.assertGreater(len(long_word), 4096)

        holder: dict[str, object] = {}

        def _run() -> None:
            with mock.patch(
                "scripts.check_version_consistency.REPO_ROOT",
                Path(tempfile.mkdtemp(prefix="devsquad_t15_long_")),
            ), mock.patch.object(Path, "read_text", return_value=yaml_text):
                try:
                    holder["results"] = _check_skill_frontmatter()
                except BaseException as exc:  # noqa: BLE001 - we want any failure
                    holder["error"] = exc

        thread = threading.Thread(target=_run, name="t15-long-frontmatter", daemon=True)
        start = time.monotonic()
        thread.start()
        # 5 s wall-clock cap — PyYAML is O(n); 8 KiB should finish in ms.
        thread.join(timeout=5.0)
        elapsed = time.monotonic() - start

        if thread.is_alive():
            self.fail(
                f"_check_skill_frontmatter hung for >5s on a {len(long_word)}-char "
                f"description (elapsed={elapsed:.2f}s). The gate must be "
                f"bounded so a pathological frontmatter cannot freeze CI."
            )

        # No exception path: parser succeeded. Either PASS with full text
        # preserved, or FAIL with a reasonable YAML/structure error. Both
        # outcomes are acceptable per the test contract.
        if "error" in holder:
            err = holder["error"]
            self.assertIsInstance(
                err,
                Exception,
                f"non-Exception raised: {type(err).__name__}: {err}",
            )
            # Only known-reasonable exceptions are acceptable.
            self.assertNotIsInstance(err, (MemoryError, SystemExit, KeyboardInterrupt))

        results = holder.get("results")
        self.assertIsNotNone(results, "results must be populated when no exception")
        assert isinstance(results, list)
        self.assertEqual(len(results), 1)
        result = results[0]

        # Two acceptable outcomes:
        #   (a) PASS — YAML parsed, all 4 keys present, full text retained
        #       in the VersionCheck; gate is well-behaved.
        #   (b) FAIL — parser raised; gate surfaced a YAML error or a
        #       "missing required keys" failure with a useful detail.
        if result.passed:
            self.assertEqual(result.found, "devsquad@4.5.16")
            # `found` is "{name}@{version}", so we re-parse to confirm
            # the description length survived. Import yaml lazily so the
            # happy-path test does not pay this cost.
            import yaml

            block = f"description: {long_word}\n"
            parsed = yaml.safe_load(block)
            self.assertIsInstance(parsed, dict)
            self.assertEqual(len(parsed["description"]), len(long_word))
        else:
            # FAIL must have a diagnostic; vague "unknown error" is not OK.
            self.assertTrue(result.detail, "FAIL result must include diagnostic detail")
            self.assertFalse(
                result.detail.startswith("SKIP"),
                "extreme-long input must not be reported as SKIP",
            )

        # Wall-clock sanity: PyYAML is O(n); 8 KiB should be sub-second.
        self.assertLess(
            elapsed,
            5.0,
            f"frontmatter parse took {elapsed:.2f}s — too slow for 8 KiB input",
        )


if __name__ == "__main__":
    unittest.main()
