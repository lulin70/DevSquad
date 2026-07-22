#!/usr/bin/env python3
"""V4.2.1 P1-4: Hidden Content Scanner.

Detects content that is invisible or hard to spot in normal review but could
mask malicious instructions, data exfiltration, or code manipulation.

Detection categories:
  1. Zero-width characters (U+200B/200C/200D/FEFF) — steganography
  2. Invisible formatting characters (U+00AD/2060/2061-2064)
  3. Control characters (U+0000-001F except \n\r\t, U+007F DEL)
  4. Cyrillic/Greek homoglyphs in ASCII context (confusable character attack)
  5. HTML comments in markdown/source (``<!--...-->`` hiding instructions)

Usage:
    python scripts/check_hidden_content.py [paths...]
    python scripts/check_hidden_content.py --source scripts/ tests/

Exit codes:
    0 = no hidden content found
    1 = hidden content detected
    2 = script error
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class HiddenCategory(Enum):
    """Category of hidden content detected."""

    ZERO_WIDTH = "zero_width"
    INVISIBLE_FORMAT = "invisible_format"
    CONTROL_CHAR = "control_char"
    HOMOGLYPH = "homoglyph"
    HTML_COMMENT = "html_comment"


@dataclass
class HiddenFinding:
    """A single hidden content finding.

    Attributes:
        file: File path where the finding was made.
        line: 1-based line number.
        column: 1-based column number.
        category: Category of hidden content.
        char_code: Unicode code point as hex string (e.g., "U+200B").
        char_name: Unicode character name or description.
        context: Surrounding text for context (truncated).
    """

    file: str
    line: int
    column: int
    category: HiddenCategory
    char_code: str
    char_name: str
    context: str = ""


# Zero-width characters used for steganography.
ZERO_WIDTH_CHARS: dict[int, str] = {
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE (BOM)",
    0x2060: "WORD JOINER",
}

# Invisible formatting characters.
INVISIBLE_FORMAT_CHARS: dict[int, str] = {
    0x00AD: "SOFT HYPHEN",
    0x2061: "INVISIBLE FUNCTION APPLICATION",
    0x2062: "INVISIBLE TIMES",
    0x2063: "INVISIBLE SEPARATOR",
    0x2064: "INVISIBLE PLUS",
}

# Allowed control characters (tab, newline, carriage return).
ALLOWED_CONTROL = {0x09, 0x0A, 0x0D}

# Cyrillic characters that look like ASCII letters (homoglyph attack).
# Maps Cyrillic code point → ASCII lookalike.
CYRILLIC_HOMOGLYPHS: dict[int, str] = {
    0x0430: "a",  # Cyrillic small a
    0x0435: "e",  # Cyrillic small e (IE)
    0x043E: "o",  # Cyrillic small o
    0x0440: "p",  # Cyrillic small er
    0x0441: "c",  # Cyrillic small es
    0x0443: "y",  # Cyrillic small u
    0x0445: "x",  # Cyrillic small ha
    0x0410: "A",  # Cyrillic capital A
    0x0412: "B",  # Cyrillic capital Ve
    0x0415: "E",  # Cyrillic capital IE
    0x041A: "K",  # Cyrillic capital Ka
    0x041C: "M",  # Cyrillic capital Em
    0x041D: "H",  # Cyrillic capital En
    0x041E: "O",  # Cyrillic capital O
    0x0420: "P",  # Cyrillic capital Er
    0x0421: "C",  # Cyrillic capital Es
    0x0422: "T",  # Cyrillic capital Te
    0x0425: "X",  # Cyrillic capital Ha
}

# Greek characters that look like ASCII letters.
GREEK_HOMOGLYPHS: dict[int, str] = {
    0x03BF: "o",  # Greek small omicron
    0x039F: "O",  # Greek capital omicron
    0x03A1: "P",  # Greek capital rho
    0x03C1: "p",  # Greek small rho
}

# HTML comment pattern in source/markdown.
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# File extensions where HTML comments are syntactically meaningful.
# In .py files, `<!--` is just a string literal, not a real comment.
HTML_COMMENT_EXTENSIONS = {".md", ".markdown", ".html", ".htm", ".rst", ".adoc"}


def _should_check_html_comments(path: Path, flag: bool) -> bool:
    """Decide whether HTML comment detection applies to this file.

    HTML comments are only syntactically meaningful in markdown/HTML file
    types. In Python source, ``<!--`` is a string literal, not a real
    comment, so flagging it would produce false positives.

    Args:
        path: File path to check.
        flag: Master enable flag for HTML comment detection.

    Returns:
        True if HTML comment detection should run on this file.
    """
    if not flag:
        return False
    return path.suffix.lower() in HTML_COMMENT_EXTENSIONS


def _get_char_name(code: int) -> str:
    """Get human-readable name for a Unicode code point.

    Args:
        code: Unicode code point integer.

    Returns:
        Character name from unicodedata or a fallback description.
    """
    try:
        return unicodedata.name(chr(code))
    except ValueError:
        return f"U+{code:04X} (no name)"


def scan_line(
    line: str,
    file_path: str,
    line_no: int,
    check_homoglyphs: bool = True,
    check_html_comments: bool = True,
) -> list[HiddenFinding]:
    """Scan a single line for hidden content.

    Args:
        line: Text content of the line (without newline).
        file_path: File path for reporting.
        line_no: 1-based line number.
        check_homoglyphs: Whether to check for Cyrillic/Greek homoglyphs.
        check_html_comments: Whether to check for HTML comments.

    Returns:
        List of HiddenFinding for this line.
    """
    findings: list[HiddenFinding] = []

    for col, char in enumerate(line, 1):
        code = ord(char)

        # Check zero-width characters.
        if code in ZERO_WIDTH_CHARS:
            findings.append(HiddenFinding(
                file=file_path, line=line_no, column=col,
                category=HiddenCategory.ZERO_WIDTH,
                char_code=f"U+{code:04X}",
                char_name=ZERO_WIDTH_CHARS[code],
                context=line[max(0, col - 10):col + 10],
            ))
            continue

        # Check invisible format characters.
        if code in INVISIBLE_FORMAT_CHARS:
            findings.append(HiddenFinding(
                file=file_path, line=line_no, column=col,
                category=HiddenCategory.INVISIBLE_FORMAT,
                char_code=f"U+{code:04X}",
                char_name=INVISIBLE_FORMAT_CHARS[code],
                context=line[max(0, col - 10):col + 10],
            ))
            continue

        # Check control characters (except allowed: tab, newline, CR).
        if code < 0x20 and code not in ALLOWED_CONTROL:
            findings.append(HiddenFinding(
                file=file_path, line=line_no, column=col,
                category=HiddenCategory.CONTROL_CHAR,
                char_code=f"U+{code:04X}",
                char_name=_get_char_name(code),
                context=line[max(0, col - 10):col + 10],
            ))
            continue

        if code == 0x7F:  # DEL character
            findings.append(HiddenFinding(
                file=file_path, line=line_no, column=col,
                category=HiddenCategory.CONTROL_CHAR,
                char_code="U+007F",
                char_name="DELETE",
                context=line[max(0, col - 10):col + 10],
            ))
            continue

        # Check homoglyphs.
        if check_homoglyphs:
            ascii_lookalike = CYRILLIC_HOMOGLYPHS.get(code) or GREEK_HOMOGLYPHS.get(code)
            if ascii_lookalike:
                findings.append(HiddenFinding(
                    file=file_path, line=line_no, column=col,
                    category=HiddenCategory.HOMOGLYPH,
                    char_code=f"U+{code:04X}",
                    char_name=f"{_get_char_name(code)} (looks like ASCII '{ascii_lookalike}')",
                    context=line[max(0, col - 10):col + 10],
                ))

    # Check HTML comments.
    if check_html_comments:
        for match in HTML_COMMENT_RE.finditer(line):
            col = match.start() + 1
            comment_text = match.group()[:60]
            findings.append(HiddenFinding(
                file=file_path, line=line_no, column=col,
                category=HiddenCategory.HTML_COMMENT,
                char_code="N/A",
                char_name=f"HTML comment: {comment_text}",
                context=line[max(0, col - 10):col + 40],
            ))

    return findings


def scan_file(
    path: Path,
    check_homoglyphs: bool = True,
    check_html_comments: bool = True,
) -> list[HiddenFinding]:
    """Scan a single file for hidden content.

    Args:
        path: Path to the file to scan.
        check_homoglyphs: Whether to check for homoglyphs.
        check_html_comments: Whether to check for HTML comments (only
            applied to markdown/HTML file types — see
            ``_should_check_html_comments``).

    Returns:
        List of HiddenFinding in the file.
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  WARN: cannot read {path}: {exc}", file=sys.stderr)
        return []

    # HTML comment detection only applies to markdown/HTML file types.
    effective_html_check = _should_check_html_comments(path, check_html_comments)

    findings: list[HiddenFinding] = []
    for line_no, line in enumerate(content.split("\n"), 1):
        findings.extend(scan_line(
            line, str(path), line_no,
            check_homoglyphs=check_homoglyphs,
            check_html_comments=effective_html_check,
        ))
    return findings


def scan_directory(
    root: Path,
    extensions: set[str] | None = None,
    check_homoglyphs: bool = True,
    check_html_comments: bool = True,
) -> list[HiddenFinding]:
    """Scan all files in a directory tree for hidden content.

    Args:
        root: Root directory to scan.
        extensions: Set of file extensions to scan (e.g., {".py", ".md"}).
                    If None, scans all text files.
        check_homoglyphs: Whether to check for homoglyphs.
        check_html_comments: Whether to check for HTML comments.

    Returns:
        List of HiddenFinding across all scanned files.
    """
    if extensions is None:
        extensions = {".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".json"}

    all_findings: list[HiddenFinding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue
        # Skip common non-source directories.
        if any(part in {".git", "__pycache__", ".mypy_cache", ".hypothesis", "node_modules"}
               for part in path.parts):
            continue
        all_findings.extend(scan_file(
            path, check_homoglyphs=check_homoglyphs,
            check_html_comments=check_html_comments,
        ))
    return all_findings


def format_finding(f: HiddenFinding) -> str:
    """Format a finding for display.

    Args:
        f: HiddenFinding to format.

    Returns:
        Human-readable string with category, file, line, column, and details.
    """
    return (
        f"  [{f.category.value.upper():16s}] {f.file}:{f.line}:{f.column} "
        f"{f.char_code} {f.char_name}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hidden content scanner — detects zero-width chars, "
        "invisible characters, homoglyphs, and hidden HTML comments."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[str(REPO_ROOT / "scripts"), str(REPO_ROOT / "tests")],
        help="Files or directories to scan (default: scripts/ tests/)",
    )
    parser.add_argument(
        "--no-homoglyphs",
        action="store_true",
        help="Skip homoglyph detection (Cyrillic/Greek lookalikes)",
    )
    parser.add_argument(
        "--no-html-comments",
        action="store_true",
        help="Skip HTML comment detection",
    )
    args = parser.parse_args()

    check_homoglyphs = not args.no_homoglyphs
    check_html_comments = not args.no_html_comments

    all_findings: list[HiddenFinding] = []
    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"ERROR: path not found: {path}")
            return 2
        if path.is_file():
            all_findings.extend(scan_file(
                path, check_homoglyphs, check_html_comments,
            ))
        else:
            all_findings.extend(scan_directory(
                path, check_homoglyphs=check_homoglyphs,
                check_html_comments=check_html_comments,
            ))

    # Group by category.
    by_cat: dict[HiddenCategory, list[HiddenFinding]] = {}
    for f in all_findings:
        by_cat.setdefault(f.category, []).append(f)

    print("Hidden Content Report (V4.2.1 P1-4)")
    print(f"  Scanned: {len(args.paths)} path(s)")
    print(f"  Findings: {len(all_findings)} total")
    for cat in HiddenCategory:
        count = len(by_cat.get(cat, []))
        if count:
            print(f"    {cat.value}: {count}")
    print("-" * 70)

    for cat in HiddenCategory:
        cat_findings = by_cat.get(cat, [])
        if cat_findings:
            print(f"\n{cat.value.upper()} ({len(cat_findings)}):")
            for f in cat_findings[:50]:  # Limit output to 50 per category.
                print(format_finding(f))
            if len(cat_findings) > 50:
                print(f"  ... and {len(cat_findings) - 50} more")

    print("-" * 70)

    if all_findings:
        print(f"\nFAIL: {len(all_findings)} hidden content finding(s)")
        return 1

    print("\nOK: no hidden content found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
