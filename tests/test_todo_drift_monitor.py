"""Tests for ``scripts.collaboration.todo_drift_monitor`` — V4.3.0 P0-2.

Coverage focus (per test plan §3 P0-2 row):
- Scan detects TODO/FIXME/HACK/XXX/WIP/待办/待修复 markers
- Case-insensitive matching
- Diff against TECH_DEBT.md identifies new unregistered markers
- Report formatting (text / json / markdown)
- Pre-commit + CI integration behavior (main() exit codes)
- Regex bypass variants (parametrized matrix from test plan §7.3)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.collaboration.todo_drift_monitor import (
    DEFAULT_SCAN_ROOT,
    DEFAULT_TRACKER_PATH,
    MARKER_PATTERN,
    DriftReport,
    TechDebtEntry,
    diff_with_tracker,
    main,
    report_new_debts,
    scan_tech_debt,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_source_tree(tmp_path: Path) -> Path:
    """Create a sample scripts/ tree with known markers for scanning."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "module_a.py").write_text(
        """# TODO: refactor this module
def hello():
    pass
# FIXME: bug here
x = 1
""",
        encoding="utf-8",
    )
    (scripts_dir / "module_b.py").write_text(
        """# hack: quick workaround
def bye():
    pass
# XXX: revisit later
y = 2
""",
        encoding="utf-8",
    )
    (scripts_dir / "chinese.py").write_text(
        """# 待办: 中文标记检测
def cn():
    pass
# 待修复: 另一个中文标记
z = 3
""",
        encoding="utf-8",
    )
    # Excluded directory — should be skipped
    excl = scripts_dir / "tests"
    excl.mkdir()
    (excl / "test_something.py").write_text("# TODO: should be skipped\n", encoding="utf-8")
    return scripts_dir


@pytest.fixture()
def tracker_with_a_registered(tmp_path: Path, sample_source_tree: Path) -> Path:
    """Tracker that registers one of the markers in sample_source_tree."""
    tracker = tmp_path / "TECH_DEBT.md"
    tracker.write_text(
        f"""# Tech Debt Tracker

## TD-001
- Location: {sample_source_tree}/module_a.py:1
- Description: refactor this module
""",
        encoding="utf-8",
    )
    return tracker


# ---------------------------------------------------------------------------
# Marker regex
# ---------------------------------------------------------------------------


class TestMarkerPattern:
    """Verify the regex covers English + Chinese markers, case-insensitive."""

    @pytest.mark.parametrize(
        "marker",
        ["TODO", "todo", "Todo", "tOdO", "FIXME", "fixme", "HACK", "hack", "XXX", "WIP", "wip"],
    )
    def test_english_markers_case_insensitive(self, marker: str) -> None:
        assert MARKER_PATTERN.search(f"# {marker}: something") is not None

    @pytest.mark.parametrize("marker", ["待办", "待修复"])
    def test_chinese_markers(self, marker: str) -> None:
        assert MARKER_PATTERN.search(f"# {marker}: 中文标记") is not None

    @pytest.mark.parametrize(
        "text,should_match",
        [
            # Real comment markers (after #, followed by : or space)
            ("# TODO: fix this", True),
            ("# todo: fix this", True),
            ("# TODO fix this", True),  # no colon, but space after
            ("#FIXME: bug", True),  # no space after #
            ("# TODO list of items", True),  # TODO followed by space
            # Not markers — no # prefix
            ("TODO", False),  # bare string, no comment context
            ("todo", False),  # bare string
            ("TODO_LIST", False),  # variable name, no #
            ("do it todo now", False),  # no # prefix
            # Not markers — # present but marker followed by / (descriptive)
            ("# TODO/FIXME/HACK comments", False),  # TODO followed by /
            # Not markers — other
            ("# TO-DO: fix", False),  # hyphenated variant
            ("# TODAY: meeting", False),  # not TODO
            ("TODO = 'todo'", False),  # assignment, no #
            ('"TODO"', False),  # string literal
            ("todos = []", False),  # variable name
            ("waterfall", False),  # no marker
        ],
    )
    def test_bypass_variants(self, text: str, should_match: bool) -> None:
        match = MARKER_PATTERN.search(text)
        assert (match is not None) == should_match


# ---------------------------------------------------------------------------
# scan_tech_debt
# ---------------------------------------------------------------------------


class TestScanTechDebt:
    def test_finds_todo_and_fixme(self, sample_source_tree: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        markers = [e.marker.upper() for e in entries]
        assert "TODO" in markers
        assert "FIXME" in markers

    def test_finds_hack_case_insensitive(self, sample_source_tree: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        markers = [e.marker.upper() for e in entries]
        assert "HACK" in markers

    def test_finds_xxx(self, sample_source_tree: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        markers = [e.marker.upper() for e in entries]
        assert "XXX" in markers

    def test_finds_chinese_markers(self, sample_source_tree: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        markers = [e.marker for e in entries]
        assert "待办" in markers
        assert "待修复" in markers

    def test_excludes_tests_dir(self, sample_source_tree: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        # The tests/test_something.py TODO should not appear — check path
        # components, not substring (tmp_path may contain "tests" in its name)
        for e in entries:
            assert "tests" not in Path(e.file_path).parts, (
                f"Excluded file leaked into scan results: {e.file_path}"
            )

    def test_entries_sorted_by_file_and_line(self, sample_source_tree: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        keys = [(e.file_path, e.line_number) for e in entries]
        assert keys == sorted(keys)

    def test_entry_content_is_stripped(self, sample_source_tree: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        todo_entry = next(e for e in entries if e.marker.upper() == "TODO")
        assert todo_entry.content.startswith("# TODO")
        assert todo_entry.marker == "TODO"
        assert todo_entry.line_number == 1

    def test_scan_nonexistent_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Scan root does not exist"):
            scan_tech_debt(tmp_path / "nonexistent")

    def test_scan_file_root_raises_not_dir(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.py"
        file_path.write_text("# TODO\n", encoding="utf-8")
        with pytest.raises(NotADirectoryError, match="Scan root is not a directory"):
            scan_tech_debt(file_path)

    def test_scan_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert scan_tech_debt(empty) == []

    def test_scan_skips_unreadable_files(self, tmp_path: Path) -> None:
        root = tmp_path / "scripts"
        root.mkdir()
        # Write a file with invalid UTF-8 bytes
        (root / "bad.py").write_bytes(b"\xff\xfe# TODO: invalid utf8\n")
        entries = scan_tech_debt(root)
        # Should not crash; should skip the unreadable file
        assert entries == []

    def test_scan_ignores_markers_inside_strings(self, tmp_path: Path) -> None:
        """V4.3.0 P0-2: tokenize-based scan must not match ``#`` inside strings.

        Regression for the ``"## Todo Drift Report"`` false positive —
        ``#`` inside a string literal is NOT a Python comment.
        """
        root = tmp_path / "scripts"
        root.mkdir()
        (root / "strings.py").write_text(
            'x = "## Todo Drift Report"\n'
            'y = "# TODO: not a real comment"\n'
            '# TODO: real comment\n'
            'z = 1\n',
            encoding="utf-8",
        )
        entries = scan_tech_debt(root)
        # Only the real comment on line 3 should be found
        assert len(entries) == 1
        assert entries[0].line_number == 3
        assert entries[0].marker.upper() == "TODO"

    def test_scan_ignores_descriptive_marker_lists(self, tmp_path: Path) -> None:
        """V4.3.0 P0-2: ``# TODO/FIXME/HACK comments`` is descriptive, not a marker.

        The regex requires the marker to be followed by ``:`` or whitespace —
        a ``/`` after the marker means it's a list of marker names, not a
        real tech-debt marker.
        """
        root = tmp_path / "scripts"
        root.mkdir()
        (root / "descriptive.py").write_text(
            '# TODO/FIXME/HACK comments\n'
            '# Detect TODO/FIXME in source code\n'
            '# TODO: real marker\n',
            encoding="utf-8",
        )
        entries = scan_tech_debt(root)
        # Only the real marker on line 3 should be found
        assert len(entries) == 1
        assert entries[0].line_number == 3

    def test_default_exclude_dirs_skips_pycache(self, tmp_path: Path) -> None:
        root = tmp_path / "scripts"
        root.mkdir()
        pycache = root / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("# TODO: should be skipped\n", encoding="utf-8")
        entries = scan_tech_debt(root)
        assert all("__pycache__" not in e.file_path for e in entries)


# ---------------------------------------------------------------------------
# diff_with_tracker
# ---------------------------------------------------------------------------


class TestDiffWithTracker:
    def test_identifies_new_unregistered(
        self, sample_source_tree: Path, tracker_with_a_registered: Path
    ) -> None:
        entries = scan_tech_debt(sample_source_tree)
        report = diff_with_tracker(entries, tracker_with_a_registered)
        # module_a.py:1 is registered; the rest are new
        assert len(report.new_unregistered) >= 4
        assert all(
            e.file_path != f"{sample_source_tree}/module_a.py" or e.line_number != 1
            for e in report.new_unregistered
        )

    def test_registered_count_matches_tracker(
        self, sample_source_tree: Path, tracker_with_a_registered: Path
    ) -> None:
        entries = scan_tech_debt(sample_source_tree)
        report = diff_with_tracker(entries, tracker_with_a_registered)
        # Tracker has 1 registered location
        assert report.registered_count >= 1

    def test_removed_registered_when_source_has_no_marker(
        self, sample_source_tree: Path, tracker_with_a_registered: Path
    ) -> None:
        # Add a tracker entry for a location that doesn't exist in source
        tracker = tracker_with_a_registered
        tracker.write_text(
            tracker.read_text(encoding="utf-8")
            + f"\n## TD-999\n- Location: {sample_source_tree}/nonexistent.py:42\n",
            encoding="utf-8",
        )
        entries = scan_tech_debt(sample_source_tree)
        report = diff_with_tracker(entries, tracker)
        assert any("nonexistent.py:42" in loc for loc in report.removed_registered)

    def test_missing_tracker_raises(self, sample_source_tree: Path, tmp_path: Path) -> None:
        entries = scan_tech_debt(sample_source_tree)
        with pytest.raises(FileNotFoundError, match="Tech debt tracker not found"):
            diff_with_tracker(entries, tmp_path / "missing.md")

    def test_empty_diff_when_all_registered(
        self, sample_source_tree: Path, tmp_path: Path
    ) -> None:
        # Register every marker found in the source tree
        entries = scan_tech_debt(sample_source_tree)
        tracker = tmp_path / "TECH_DEBT.md"
        lines = ["# Tech Debt Tracker\n"]
        for i, e in enumerate(entries, start=1):
            lines.append(f"## TD-{i:03d}\n- Location: {e.file_path}:{e.line_number}\n")
        tracker.write_text("".join(lines), encoding="utf-8")
        report = diff_with_tracker(entries, tracker)
        assert report.new_unregistered == []


# ---------------------------------------------------------------------------
# report_new_debts
# ---------------------------------------------------------------------------


class TestReportNewDebts:
    def _sample_report(self) -> DriftReport:
        return DriftReport(
            scanned_files=5,
            total_markers=10,
            registered_count=8,
            new_unregistered=[
                TechDebtEntry(
                    file_path="scripts/foo.py",
                    line_number=42,
                    marker="TODO",
                    content="# TODO: refactor this",
                ),
            ],
            removed_registered=["scripts/gone.py:99"],
        )

    def test_text_format(self) -> None:
        report = self._sample_report()
        text = report_new_debts(report, "text")
        assert "Scanned 5 files" in text
        assert "10 markers" in text
        assert "NEW: scripts/foo.py:42" in text
        assert "GONE: scripts/gone.py:99" in text

    def test_json_format(self) -> None:
        report = self._sample_report()
        text = report_new_debts(report, "json")
        data = json.loads(text)
        assert data["scanned_files"] == 5
        assert data["total_markers"] == 10
        assert data["new_unregistered"][0]["file_path"] == "scripts/foo.py"

    def test_markdown_format(self) -> None:
        report = self._sample_report()
        text = report_new_debts(report, "markdown")
        assert "## Todo Drift Report" in text
        assert "| scripts/foo.py | 42 |" in text

    def test_unsupported_format_raises(self) -> None:
        report = self._sample_report()
        with pytest.raises(ValueError, match="Unsupported output_format"):
            report_new_debts(report, "yaml")


# ---------------------------------------------------------------------------
# main / CI integration
# ---------------------------------------------------------------------------


class TestMainIntegration:
    def test_main_returns_0_when_no_new_debts(
        self, sample_source_tree: Path, tracker_with_a_registered: Path, capsys
    ) -> None:
        # Register every marker so diff is empty
        entries = scan_tech_debt(sample_source_tree)
        tracker = tracker_with_a_registered
        lines = ["# Tech Debt Tracker\n"]
        for i, e in enumerate(entries, start=1):
            lines.append(f"## TD-{i:03d}\n- Location: {e.file_path}:{e.line_number}\n")
        tracker.write_text("".join(lines), encoding="utf-8")

        exit_code = main(["--root", str(sample_source_tree), "--tracker", str(tracker)])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "0 new unregistered" in captured.out

    def test_main_returns_1_when_new_debts(
        self, sample_source_tree: Path, tracker_with_a_registered: Path, capsys
    ) -> None:
        exit_code = main(["--root", str(sample_source_tree), "--tracker", str(tracker_with_a_registered)])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "new unregistered" in captured.out

    def test_main_returns_2_on_missing_tracker(
        self, sample_source_tree: Path, tmp_path: Path, capsys
    ) -> None:
        exit_code = main(
            ["--root", str(sample_source_tree), "--tracker", str(tmp_path / "missing.md")]
        )
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "ERROR" in captured.err

    def test_main_returns_2_on_missing_root(self, tmp_path: Path, capsys) -> None:
        exit_code = main(["--root", str(tmp_path / "nonexistent")])
        assert exit_code == 2

    def test_main_json_output(self, sample_source_tree: Path, tracker_with_a_registered: Path, capsys) -> None:
        main([
            "--root", str(sample_source_tree),
            "--tracker", str(tracker_with_a_registered),
            "--format", "json",
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "new_unregistered" in data
        assert "scanned_files" in data

    def test_main_markdown_output(self, sample_source_tree: Path, tracker_with_a_registered: Path, capsys) -> None:
        main([
            "--root", str(sample_source_tree),
            "--tracker", str(tracker_with_a_registered),
            "--format", "markdown",
        ])
        captured = capsys.readouterr()
        assert "## Todo Drift Report" in captured.out


# ---------------------------------------------------------------------------
# Pre-commit hook integration (simulated)
# ---------------------------------------------------------------------------


class TestPreCommitHookIntegration:
    """Simulate the pre-commit hook behavior — blocking new TODOs."""

    def test_blocks_commit_with_new_todo(
        self, sample_source_tree: Path, tracker_with_a_registered: Path
    ) -> None:
        """If scan finds new markers, pre-commit hook must block (exit 1)."""
        entries = scan_tech_debt(sample_source_tree)
        report = diff_with_tracker(entries, tracker_with_a_registered)
        assert report.new_unregistered, "Expected new unregistered markers"
        # main() should return 1 — pre-commit interprets non-zero as block
        assert main(["--root", str(sample_source_tree), "--tracker", str(tracker_with_a_registered)]) == 1

    def test_allows_commit_when_all_registered(
        self, sample_source_tree: Path, tracker_with_a_registered: Path
    ) -> None:
        """If all markers are registered, pre-commit hook allows (exit 0)."""
        entries = scan_tech_debt(sample_source_tree)
        tracker = tracker_with_a_registered
        lines = ["# Tech Debt Tracker\n"]
        for i, e in enumerate(entries, start=1):
            lines.append(f"## TD-{i:03d}\n- Location: {e.file_path}:{e.line_number}\n")
        tracker.write_text("".join(lines), encoding="utf-8")
        assert main(["--root", str(sample_source_tree), "--tracker", str(tracker)]) == 0


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_scan_root(self) -> None:
        assert DEFAULT_SCAN_ROOT == "scripts"

    def test_default_tracker_path(self) -> None:
        assert DEFAULT_TRACKER_PATH == "docs/TECH_DEBT.md"
