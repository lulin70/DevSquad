#!/usr/bin/env python3
"""Tests for check_hidden_content.py (V4.2.1 P1-4) — Hidden Content Scanner.

Test fixtures construct hidden characters dynamically via chr() so that the
test source file itself remains ASCII-clean (no zero-width chars, no
homoglyphs). This prevents the scanner from flagging the test file when CI
runs `python scripts/check_hidden_content.py scripts/ tests/`.

Coverage dimensions (per DevSquad Iron Rule 3):
  - Happy Path: each detection category (zero-width, invisible format,
    control char, DEL, Cyrillic/Greek homoglyph, HTML comment)
  - Error Case: nonexistent file, empty input
  - Boundary: empty line, ASCII-only line, allowed control chars (tab/CR)
  - Performance: scan timing baseline
  - Configuration: --no-homoglyphs / --no-html-comments flags, file-type filter
  - Integration: scan_directory tree walk + extension filter + skip dirs
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.check_hidden_content import (
    ALLOWED_CONTROL,
    CYRILLIC_HOMOGLYPHS,
    GREEK_HOMOGLYPHS,
    HTML_COMMENT_EXTENSIONS,
    HTML_COMMENT_RE,
    ZERO_WIDTH_CHARS,
    HiddenCategory,
    HiddenFinding,
    _get_char_name,
    _should_check_html_comments,
    format_finding,
    scan_directory,
    scan_file,
    scan_line,
)


class T1_DataModels(unittest.TestCase):
    """T1: Data model verification — enums and dataclasses."""

    def test_01_hidden_category_values(self) -> None:
        """Verify: HiddenCategory enum has exactly 5 categories with correct values.

        Scenario: Enumerate all detection categories.
        Expected: 5 distinct values matching spec.
        """
        self.assertEqual(len(HiddenCategory), 5)
        self.assertEqual(HiddenCategory.ZERO_WIDTH.value, "zero_width")
        self.assertEqual(HiddenCategory.INVISIBLE_FORMAT.value, "invisible_format")
        self.assertEqual(HiddenCategory.CONTROL_CHAR.value, "control_char")
        self.assertEqual(HiddenCategory.HOMOGLYPH.value, "homoglyph")
        self.assertEqual(HiddenCategory.HTML_COMMENT.value, "html_comment")

    def test_02_hidden_finding_creation(self) -> None:
        """Verify: HiddenFinding dataclass stores all fields correctly.

        Scenario: Construct a finding with all fields.
        Expected: All attributes accessible and correct.
        """
        f = HiddenFinding(
            file="src/app.py",
            line=10,
            column=3,
            category=HiddenCategory.ZERO_WIDTH,
            char_code="U+200B",
            char_name="ZERO WIDTH SPACE",
            context="abc",
        )
        self.assertEqual(f.file, "src/app.py")
        self.assertEqual(f.line, 10)
        self.assertEqual(f.column, 3)
        self.assertEqual(f.category, HiddenCategory.ZERO_WIDTH)
        self.assertEqual(f.char_code, "U+200B")
        self.assertEqual(f.char_name, "ZERO WIDTH SPACE")
        self.assertEqual(f.context, "abc")

    def test_03_hidden_finding_default_context(self) -> None:
        """Verify: HiddenFinding context defaults to empty string.

        Scenario: Omit context when constructing.
        Expected: context == "".
        """
        f = HiddenFinding(
            file="x.py", line=1, column=1,
            category=HiddenCategory.HOMOGLYPH,
            char_code="U+0430", char_name="test",
        )
        self.assertEqual(f.context, "")


class T2_Constants(unittest.TestCase):
    """T2: Constant tables — verify no duplicate keys (Python dict silently
    deduplicates, so we check source intent by comparing key counts)."""

    def test_01_zero_width_chars_nonempty(self) -> None:
        """Verify: ZERO_WIDTH_CHARS table has entries."""
        self.assertGreaterEqual(len(ZERO_WIDTH_CHARS), 4)
        # Core steganography chars must be present.
        self.assertIn(0x200B, ZERO_WIDTH_CHARS)
        self.assertIn(0x200D, ZERO_WIDTH_CHARS)
        self.assertIn(0xFEFF, ZERO_WIDTH_CHARS)

    def test_02_homoglyph_dicts_no_duplicate_intent(self) -> None:
        """Verify: Greek homoglyph dict has 4 distinct code points.

        Scenario: Previous bug had duplicate 0x03BF key masking intended
            0x03C1 (Greek small rho).
        Expected: 4 entries with distinct keys, including 0x03C1.
        """
        self.assertEqual(len(GREEK_HOMOGLYPHS), 4)
        self.assertIn(0x03BF, GREEK_HOMOGLYPHS)  # small omicron
        self.assertIn(0x039F, GREEK_HOMOGLYPHS)  # capital omicron
        self.assertIn(0x03A1, GREEK_HOMOGLYPHS)  # capital rho
        self.assertIn(0x03C1, GREEK_HOMOGLYPHS)  # small rho (was duplicate-keyed before)

    def test_03_cyrillic_homoglyphs_nonempty(self) -> None:
        """Verify: CYRILLIC_HOMOGLYPHS has at least 10 entries."""
        self.assertGreaterEqual(len(CYRILLIC_HOMOGLYPHS), 10)

    def test_04_allowed_control_includes_tab_newline_cr(self) -> None:
        """Verify: ALLOWED_CONTROL permits tab (0x09), LF (0x0A), CR (0x0D)."""
        self.assertEqual(ALLOWED_CONTROL, {0x09, 0x0A, 0x0D})

    def test_05_html_comment_extensions_includes_md(self) -> None:
        """Verify: HTML_COMMENT_EXTENSIONS includes .md and .html but not .py."""
        self.assertIn(".md", HTML_COMMENT_EXTENSIONS)
        self.assertIn(".html", HTML_COMMENT_EXTENSIONS)
        self.assertNotIn(".py", HTML_COMMENT_EXTENSIONS)


class T3_GetCharName(unittest.TestCase):
    """T3: _get_char_name helper."""

    def test_01_known_char(self) -> None:
        """Verify: Latin 'A' returns 'LATIN CAPITAL LETTER A'."""
        self.assertEqual(_get_char_name(0x41), "LATIN CAPITAL LETTER A")

    def test_02_unknown_char_returns_fallback(self) -> None:
        """Verify: Unnamed code point returns fallback string.

        Scenario: U+0000 has no Unicode name.
        Expected: Fallback 'U+0000 (no name)'.
        """
        name = _get_char_name(0x00)
        self.assertIn("U+0000", name)
        self.assertIn("no name", name)


class T4_ShouldCheckHtmlComments(unittest.TestCase):
    """T4: _should_check_html_comments file-type filter."""

    def test_01_md_file_returns_true(self) -> None:
        """Verify: .md files trigger HTML comment check."""
        self.assertTrue(_should_check_html_comments(Path("doc.md"), True))

    def test_02_py_file_returns_false(self) -> None:
        """Verify: .py files skip HTML comment check (string literal, not comment)."""
        self.assertFalse(_should_check_html_comments(Path("app.py"), True))

    def test_03_html_file_returns_true(self) -> None:
        """Verify: .html files trigger HTML comment check."""
        self.assertTrue(_should_check_html_comments(Path("page.html"), True))

    def test_04_flag_false_returns_false(self) -> None:
        """Verify: Master flag=False overrides file type."""
        self.assertFalse(_should_check_html_comments(Path("doc.md"), False))

    def test_05_uppercase_extension(self) -> None:
        """Verify: Uppercase .MD extension still matches (case-insensitive)."""
        self.assertTrue(_should_check_html_comments(Path("README.MD"), True))


class T5_ScanLine_Happy(unittest.TestCase):
    """T5: scan_line happy path — each detection category."""

    def test_01_detects_zero_width_space(self) -> None:
        """Verify: U+200B in a line produces a ZERO_WIDTH finding.

        Scenario: Line contains a zero-width space between two words.
        Expected: 1 finding, category ZERO_WIDTH, column 6.
        """
        line = "hello" + chr(0x200B) + "world"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.ZERO_WIDTH)
        self.assertEqual(findings[0].char_code, "U+200B")
        self.assertEqual(findings[0].column, 6)

    def test_02_detects_invisible_format_soft_hyphen(self) -> None:
        """Verify: U+00AD soft hyphen produces INVISIBLE_FORMAT finding."""
        line = "cafe" + chr(0x00AD) + "table"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.INVISIBLE_FORMAT)
        self.assertEqual(findings[0].char_code, "U+00AD")

    def test_03_detects_control_char(self) -> None:
        """Verify: U+0001 control char produces CONTROL_CHAR finding."""
        line = "abc" + chr(0x01) + "def"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.CONTROL_CHAR)
        self.assertEqual(findings[0].char_code, "U+0001")

    def test_04_detects_del_char(self) -> None:
        """Verify: U+007F DELETE produces CONTROL_CHAR finding."""
        line = "x" + chr(0x7F) + "y"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.CONTROL_CHAR)
        self.assertEqual(findings[0].char_code, "U+007F")
        self.assertEqual(findings[0].char_name, "DELETE")

    def test_05_detects_cyrillic_homoglyph(self) -> None:
        """Verify: Cyrillic small a (U+0430) produces HOMOGLYPH finding."""
        # Cyrillic small a looks like ASCII 'a'.
        line = "hello " + chr(0x0430) + "bc"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.HOMOGLYPH)
        self.assertEqual(findings[0].char_code, "U+0430")
        self.assertIn("ASCII 'a'", findings[0].char_name)

    def test_06_detects_greek_small_rho(self) -> None:
        """Verify: Greek small rho (U+03C1) produces HOMOGLYPH finding.

        Scenario: This code point was missing before the duplicate-key fix.
        Expected: Now detected as looking like ASCII 'p'.
        """
        line = "test" + chr(0x03C1) + "x"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.HOMOGLYPH)
        self.assertEqual(findings[0].char_code, "U+03C1")
        self.assertIn("ASCII 'p'", findings[0].char_name)


class T6_ScanLine_Boundary(unittest.TestCase):
    """T6: scan_line boundary conditions."""

    def test_01_empty_line(self) -> None:
        """Verify: Empty line produces zero findings."""
        self.assertEqual(scan_line("", "test.py", 1), [])

    def test_02_ascii_only_line(self) -> None:
        """Verify: Plain ASCII line produces zero findings."""
        self.assertEqual(scan_line("hello world 123", "test.py", 1), [])

    def test_03_allowed_control_chars_not_flagged(self) -> None:
        """Verify: Tab and CR are NOT flagged as control chars."""
        # Tab and CR are in ALLOWED_CONTROL.
        line = "col1\tcol2\r"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(findings, [])

    def test_04_multiple_findings_in_one_line(self) -> None:
        """Verify: Multiple hidden chars in one line each produce a finding."""
        line = "a" + chr(0x200B) + "b" + chr(0x200C) + "c"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 2)
        codes = {f.char_code for f in findings}
        self.assertEqual(codes, {"U+200B", "U+200C"})

    def test_05_context_truncated_to_window(self) -> None:
        """Verify: Context field captures surrounding text within window.

        Scenario: Zero-width char placed in the middle of a long line.
        Expected: Context contains the hidden char and nearby text
            (exact boundaries are approximate, not contractually fixed).
        """
        line = "0123456789" + chr(0x200B) + "abcdefghij"
        findings = scan_line(line, "test.py", 1)
        self.assertEqual(len(findings), 1)
        # Context should include the hidden char itself and text after it.
        self.assertIn(chr(0x200B), findings[0].context)
        self.assertIn("abcdefghij", findings[0].context)


class T7_ScanLine_HtmlComment(unittest.TestCase):
    """T7: scan_line HTML comment detection."""

    def test_01_detects_html_comment(self) -> None:
        """Verify: HTML comment syntax produces HTML_COMMENT finding."""
        line = "text <!-- hidden instruction --> more"
        findings = scan_line(line, "test.md", 1, check_html_comments=True)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.HTML_COMMENT)
        self.assertEqual(findings[0].column, 6)

    def test_02_no_html_comment_when_disabled(self) -> None:
        """Verify: check_html_comments=False skips HTML comment detection."""
        line = "text <!-- hidden instruction --> more"
        findings = scan_line(line, "test.md", 1, check_html_comments=False)
        self.assertEqual(findings, [])

    def test_03_multiple_html_comments_in_line(self) -> None:
        """Verify: Multiple HTML comments in one line each produce a finding."""
        line = "<!-- a --> middle <!-- b -->"
        findings = scan_line(line, "test.md", 1, check_html_comments=True)
        self.assertEqual(len(findings), 2)


class T8_ScanFile(unittest.TestCase):
    """T8: scan_file integration."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="hidden_test_")
        self.tmpdir_path = Path(self.tmpdir)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir_path, ignore_errors=True)

    def _write_file(self, name: str, content: str) -> Path:
        """Helper: write a temp file and return its path."""
        path = self.tmpdir_path / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_01_file_with_zero_width_content(self) -> None:
        """Verify: scan_file detects hidden char in a file.

        Scenario: File contains a zero-width space on line 2.
        Expected: 1 finding on line 2.
        """
        content = "line1\nline2" + chr(0x200B) + "\nline3\n"
        path = self._write_file("test.txt", content)
        findings = scan_file(path)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 2)
        self.assertEqual(findings[0].category, HiddenCategory.ZERO_WIDTH)

    def test_02_clean_file_no_findings(self) -> None:
        """Verify: ASCII-only file produces zero findings."""
        path = self._write_file("clean.py", "def hello():\n    return 'world'\n")
        self.assertEqual(scan_file(path), [])

    def test_03_empty_file_no_findings(self) -> None:
        """Verify: Empty file produces zero findings."""
        path = self._write_file("empty.py", "")
        self.assertEqual(scan_file(path), [])

    def test_04_py_file_skips_html_comment(self) -> None:
        """Verify: .py file does NOT flag HTML comment syntax (string literal).

        Scenario: Python file contains a regex pattern with HTML comment syntax.
        Expected: 0 findings (HTML comment check skipped for .py files).
        """
        # Construct a pattern that looks like an HTML comment but is a string.
        content = "pattern = r'<!--.*?-->'\n"
        path = self._write_file("regex.py", content)
        self.assertEqual(scan_file(path), [])

    def test_05_md_file_detects_html_comment(self) -> None:
        """Verify: .md file DOES flag HTML comment syntax."""
        content = "# Title\n\n<!-- hidden payload -->\n\nText.\n"
        path = self._write_file("doc.md", content)
        findings = scan_file(path)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, HiddenCategory.HTML_COMMENT)
        self.assertEqual(findings[0].line, 3)

    def test_06_nonexistent_file_returns_empty(self) -> None:
        """Verify: Non-existent file returns empty list (no exception)."""
        path = Path(self.tmpdir) / "does_not_exist.py"
        self.assertEqual(scan_file(path), [])


class T9_ScanDirectory(unittest.TestCase):
    """T9: scan_directory tree walk + filters."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="hidden_dir_test_")
        self.tmpdir_path = Path(self.tmpdir)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir_path, ignore_errors=True)

    def test_01_directory_with_hidden_content(self) -> None:
        """Verify: scan_directory finds hidden char across multiple files."""
        (self.tmpdir_path / "a.py").write_text(
            "x = 1\ny = 'a" + chr(0x200B) + "b'\n", encoding="utf-8")
        (self.tmpdir_path / "b.md").write_text(
            "# Doc\n<!-- comment -->\n", encoding="utf-8")
        findings = scan_directory(self.tmpdir_path)
        self.assertEqual(len(findings), 2)
        categories = {f.category for f in findings}
        self.assertEqual(categories, {HiddenCategory.ZERO_WIDTH, HiddenCategory.HTML_COMMENT})

    def test_02_directory_skips_pycache(self) -> None:
        """Verify: __pycache__ directories are skipped."""
        pycache = self.tmpdir_path / "__pycache__"
        pycache.mkdir()
        # Place a file with hidden char in __pycache__ — should be skipped.
        (pycache / "cached.py").write_text(
            "x = '" + chr(0x200B) + "'\n", encoding="utf-8")
        findings = scan_directory(self.tmpdir_path)
        self.assertEqual(findings, [])

    def test_03_directory_skips_git(self) -> None:
        """Verify: .git directories are skipped."""
        gitdir = self.tmpdir_path / ".git"
        gitdir.mkdir()
        (gitdir / "config").write_text(
            "secret" + chr(0x200B) + "\n", encoding="utf-8")
        findings = scan_directory(self.tmpdir_path)
        self.assertEqual(findings, [])

    def test_04_extension_filter(self) -> None:
        """Verify: Only files with allowed extensions are scanned."""
        # .log file with hidden char — not in default extensions, skipped.
        (self.tmpdir_path / "app.log").write_text(
            "log" + chr(0x200B) + "\n", encoding="utf-8")
        # .py file with hidden char — included.
        (self.tmpdir_path / "app.py").write_text(
            "x = '" + chr(0x200B) + "'\n", encoding="utf-8")
        findings = scan_directory(self.tmpdir_path)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].file.endswith("app.py"))

    def test_05_custom_extensions(self) -> None:
        """Verify: Custom extensions override default set."""
        (self.tmpdir_path / "app.log").write_text(
            "log" + chr(0x200B) + "\n", encoding="utf-8")
        # Scan only .log files.
        findings = scan_directory(self.tmpdir_path, extensions={".log"})
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].file.endswith("app.log"))


class T10_FormatFinding(unittest.TestCase):
    """T10: format_finding display helper."""

    def test_01_format_includes_category_file_line(self) -> None:
        """Verify: format_finding output contains key fields."""
        f = HiddenFinding(
            file="src/app.py", line=42, column=7,
            category=HiddenCategory.ZERO_WIDTH,
            char_code="U+200B", char_name="ZERO WIDTH SPACE",
        )
        s = format_finding(f)
        self.assertIn("ZERO_WIDTH", s)
        self.assertIn("src/app.py", s)
        self.assertIn(":42:7", s)
        self.assertIn("U+200B", s)
        self.assertIn("ZERO WIDTH SPACE", s)


class T11_CLI(unittest.TestCase):
    """T11: CLI main() entry point — exit codes and flags."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="hidden_cli_test_")
        self.tmpdir_path = Path(self.tmpdir)
        # Save and restore sys.argv for each test.
        self._orig_argv = sys.argv

    def tearDown(self) -> None:
        sys.argv = self._orig_argv
        import shutil
        shutil.rmtree(self.tmpdir_path, ignore_errors=True)

    def _run_main(self, *args: str) -> int:
        """Helper: invoke main() with given argv and return exit code."""
        from scripts.check_hidden_content import main
        sys.argv = ["check_hidden_content.py", *args]
        return main()

    def test_01_exit_0_when_clean(self) -> None:
        """Verify: Clean file → exit code 0."""
        path = self.tmpdir_path / "clean.py"
        path.write_text("x = 1\n", encoding="utf-8")
        rc = self._run_main(str(path))
        self.assertEqual(rc, 0)

    def test_02_exit_1_when_findings(self) -> None:
        """Verify: File with hidden char → exit code 1."""
        path = self.tmpdir_path / "hidden.py"
        path.write_text("x = '" + chr(0x200B) + "'\n", encoding="utf-8")
        rc = self._run_main(str(path))
        self.assertEqual(rc, 1)

    def test_03_exit_2_when_path_not_found(self) -> None:
        """Verify: Non-existent path → exit code 2."""
        rc = self._run_main(str(self.tmpdir_path / "nonexistent.py"))
        self.assertEqual(rc, 2)

    def test_04_no_homoglyphs_flag_skips_homoglyph_detection(self) -> None:
        """Verify: --no-homoglyphs suppresses homoglyph findings.

        Scenario: File contains a Cyrillic homoglyph; --no-homoglyphs passed.
        Expected: Exit code 0 (no findings).
        """
        path = self.tmpdir_path / "homoglyph.py"
        path.write_text("x = '" + chr(0x0430) + "'\n", encoding="utf-8")
        rc = self._run_main(str(path), "--no-homoglyphs")
        self.assertEqual(rc, 0)

    def test_05_no_html_comments_flag_skips_html_detection(self) -> None:
        """Verify: --no-html-comments suppresses HTML comment findings."""
        path = self.tmpdir_path / "doc.md"
        path.write_text("<!-- hidden -->\n", encoding="utf-8")
        rc = self._run_main(str(path), "--no-html-comments")
        self.assertEqual(rc, 0)

    def test_06_directory_arg_scanned(self) -> None:
        """Verify: Directory argument triggers recursive scan."""
        (self.tmpdir_path / "hidden.py").write_text(
            "x = '" + chr(0x200B) + "'\n", encoding="utf-8")
        rc = self._run_main(str(self.tmpdir_path))
        self.assertEqual(rc, 1)


class T12_Performance(unittest.TestCase):
    """T12: Performance baseline — scan should be fast."""

    def test_01_scan_large_file_under_500ms(self) -> None:
        """Verify: Scanning a 10000-line ASCII file completes under 500ms.

        Scenario: Large clean file should scan quickly.
        Expected: Wall time < 500ms (generous baseline; typically <50ms).
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            for i in range(10000):
                f.write(f"x_{i} = {i}\n")
            large_path = Path(f.name)
        try:
            start = time.perf_counter()
            findings = scan_file(large_path)
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.assertEqual(findings, [])
            self.assertLess(elapsed_ms, 500.0,
                            f"Scan took {elapsed_ms:.1f}ms, expected <500ms")
        finally:
            large_path.unlink(missing_ok=True)


class T13_HtmlCommentRegex(unittest.TestCase):
    """T13: HTML_COMMENT_RE pattern behavior."""

    def test_01_matches_simple_comment(self) -> None:
        """Verify: Regex matches a simple HTML comment."""
        match = HTML_COMMENT_RE.search("text <!-- hidden --> more")
        self.assertIsNotNone(match)

    def test_02_matches_empty_comment(self) -> None:
        """Verify: Regex matches an empty HTML comment."""
        match = HTML_COMMENT_RE.search("<!---->")
        self.assertIsNotNone(match)

    def test_03_no_match_without_close(self) -> None:
        """Verify: Regex requires closing --> delimiter."""
        match = HTML_COMMENT_RE.search("text <!-- unclosed")
        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main()
