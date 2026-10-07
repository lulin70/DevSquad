"""Unit tests for C18 review input normalization."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.collaboration.review_input import (
    ReviewInputError,
    normalize_review_input,
    parse_unified_diff,
    read_diff_file,
)
from skills.review.handler import ReviewSkill


def test_parse_multiple_files_and_deletion() -> None:
    diff = """diff --git a/src/keep.py b/src/keep.py
--- a/src/keep.py
+++ b/src/keep.py
@@ -1 +1 @@
-print('old')
+print('new')
 diff --git a/src/removed.py b/src/removed.py
--- a/src/removed.py
+++ /dev/null
@@ -1 +0,0 @@
-print('removed')
""".replace("\n diff --git", "\ndiff --git")

    result = parse_unified_diff(diff)

    assert result.paths == ("src/keep.py", "src/removed.py")
    assert result.deleted_paths == ("src/removed.py",)
    assert result.diff == diff


def test_parse_new_file_and_strip_dev_null() -> None:
    diff = """diff --git a/src/new.py b/src/new.py
new file mode 100644
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1 @@
+print('new')
"""

    result = parse_unified_diff(diff)

    assert result.paths == ("src/new.py",)
    assert result.deleted_paths == ()


def test_parse_rename_only_marks_old_path_deleted() -> None:
    diff = """diff --git a/src/old.py b/src/new.py
similarity index 100%
rename from src/old.py
rename to src/new.py
"""

    result = parse_unified_diff(diff)

    assert result.paths == ("src/new.py",)
    assert result.deleted_paths == ("src/old.py",)


def test_parse_quoted_paths_with_spaces() -> None:
    diff = """diff --git "a/src/old file.py" "b/src/new file.py"
similarity index 90%
rename from src/old file.py
rename to src/new file.py
--- "a/src/old file.py"
+++ "b/src/new file.py"
@@ -1 +1 @@
-old
+new
"""

    result = parse_unified_diff(diff)

    assert result.paths == ("src/new file.py",)
    assert result.deleted_paths == ("src/old file.py",)


def test_parse_binary_diff_uses_git_header() -> None:
    diff = """diff --git a/assets/logo.png b/assets/logo.png
new file mode 100644
index 0000000..1234567
Binary files /dev/null and b/assets/logo.png differ
"""

    result = parse_unified_diff(diff)

    assert result.paths == ("assets/logo.png",)
    assert result.deleted_paths == ()


def test_parse_deduplicates_paths() -> None:
    diff = """diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-a
+b
diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -2 +2 @@
-a
+b
"""

    assert parse_unified_diff(diff).paths == ("src/a.py",)


@pytest.mark.parametrize(
    "diff, message",
    [
        ("", "non-empty"),
        ("not a diff", "no file paths"),
        ("diff --git a/only-one-path", "malformed diff header"),
    ],
)
def test_malformed_diff_is_deterministic(diff: str, message: str) -> None:
    with pytest.raises(ReviewInputError, match=message):
        parse_unified_diff(diff)


def test_changeset_and_diff_are_mutually_exclusive() -> None:
    with pytest.raises(ReviewInputError, match="mutually exclusive"):
        normalize_review_input(changeset=["src/a.py"], diff="diff --git a/a b/a")


def test_changeset_normalization_deduplicates_and_preserves_order() -> None:
    result = normalize_review_input(
        changeset=["./src/a.py", "src/a.py", Path("src/b.py")],
        deleted_paths=["src/b.py", "src/b.py"],
    )

    assert result.paths == ("src/a.py", "src/b.py")
    assert result.deleted_paths == ("src/b.py",)


def test_read_diff_file_reports_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ReviewInputError, match="cannot read diff file"):
        read_diff_file(tmp_path / "missing.diff")


def test_review_skill_keeps_single_code_string_api() -> None:
    code = "def answer():\n    return 42\n"
    skill = ReviewSkill()

    direct = skill.review(code=code)
    keyword_run = skill.run(code=code)
    positional_run = skill.run(code)

    assert direct["verdict"] in {"APPROVE", "CONDITIONAL", "REJECT"}
    assert keyword_run["verdict"] == direct["verdict"]
    assert positional_run["verdict"] == direct["verdict"]
