"""Unit tests for the diff-channel pattern wiring (V4.8.0 P1-R1).

Design doc: docs/planning/V4.8.0_R1_devsquad_gate_DESIGN.md §7.1. The V-1
probe proved `review --diff-file` produced no structured findings; these
tests pin the wiring that scans ADDED lines with the three existing
ReviewCheckers regex families (zero new check logic).
"""

from __future__ import annotations

from scripts.collaboration.diff_pattern_scanner import (
    diff_pattern_scan_to_dicts,
    scan_diff_patterns,
)


def _diff(path: str, added: list[str], *, old_start: int = 1, new_start: int = 1) -> str:
    lines = [
        f"diff --git a/{path} b/{path}",
        "index 111..222 100644",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -{old_start},{len(added) + 1} +{new_start},{len(added) + 1} @@",
        " context line",
        "-removed line",
    ]
    lines.extend(f"+{line}" for line in added)
    return "\n".join(lines) + "\n"


def _by_rule(findings, rule_id: str):
    return next(f for f in findings if f.rule_id == rule_id)


class TestScanDiffPatterns:
    def test_todo_in_added_line_becomes_break2_warning(self):
        findings = scan_diff_patterns(_diff("a.py", ["x = 1  # TODO fix"]))
        f = _by_rule(findings, "diff-todo_left")
        assert f.category == "BREAK-2"
        assert f.severity == "warning"
        assert f.status == "detected"

    def test_print_debug_in_added_line(self):
        findings = scan_diff_patterns(_diff("a.py", ['print("debug")']))
        assert _by_rule(findings, "diff-print_debug").category == "BREAK-2"

    def test_hardcoded_secret_becomes_vuln4_critical(self):
        findings = scan_diff_patterns(_diff("a.py", ['api_key = "abcdefghij1234567890"']))
        f = _by_rule(findings, "diff-hardcoded_api_key")
        assert f.category == "VULN-4"
        assert f.severity == "critical"

    def test_sql_injection_format_becomes_vuln4_critical(self):
        findings = scan_diff_patterns(_diff("a.py", ['conn.execute(f"SELECT {x}")']))
        f = _by_rule(findings, "diff-sql_injection_format")
        assert f.category == "VULN-4"
        assert f.severity == "critical"

    def test_eval_usage_stays_critical_even_though_anti_pattern_family(self):
        findings = scan_diff_patterns(_diff("a.py", ["y = eval(x)"]))
        f = _by_rule(findings, "diff-eval_usage")
        # ReviewCheckers classifies eval as a critical anti-pattern (not a
        # security_* category): BREAK family + critical severity.
        assert f.severity == "critical"
        assert f.category == "BREAK-2"

    def test_removed_and_context_lines_are_not_scanned(self):
        diff = (
            "\n".join(
                [
                    "diff --git a/a.py b/a.py",
                    "index 111..222 100644",
                    "--- a/a.py",
                    "+++ b/a.py",
                    "@@ -1,2 +1,2 @@",
                    " # TODO in context",
                    "-# TODO removed",
                ]
            )
            + "\n"
        )
        assert scan_diff_patterns(diff) == []

    def test_line_numbers_come_from_hunk_headers(self):
        # The helper emits one context line before the added lines, so with
        # new_start=41 the first added line lands on 42.
        findings = scan_diff_patterns(_diff("a.py", ["# TODO one", "# TODO two"], new_start=41))
        f = _by_rule(findings, "diff-todo_left")
        assert f.line_range == "42-43"

    def test_aggregation_is_per_pattern_and_file(self):
        findings = scan_diff_patterns(_diff("a.py", ["# TODO one", "# TODO two", "# TODO three"]))
        todos = [f for f in findings if f.rule_id == "diff-todo_left"]
        assert len(todos) == 1
        assert "3 time(s)" in todos[0].description

    def test_matched_text_never_enters_the_finding(self):
        """Secret-safe disclosure: the matched line must not be copied."""
        secret = "supersecretvalue123456"
        findings = scan_diff_patterns(_diff("a.py", [f'api_key = "{secret}"']))
        f = _by_rule(findings, "diff-hardcoded_api_key")
        blob = f.description + str(f.evidence) + f.suggestion
        assert secret not in blob

    def test_empty_diff_returns_no_findings(self):
        assert scan_diff_patterns("") == []
        assert scan_diff_patterns("\n\n") == []

    def test_two_files_produce_separate_findings(self):
        diff = _diff("a.py", ["# TODO a"]) + _diff("b.py", ["# TODO b"])
        findings = scan_diff_patterns(diff)
        assert {f.file_path for f in findings if f.rule_id == "diff-todo_left"} == {"a.py", "b.py"}

    def test_dicts_are_json_compatible(self):
        dicts = diff_pattern_scan_to_dicts(_diff("a.py", ["# TODO x"]))
        assert dicts and set(dicts[0]) == {
            "category",
            "rule_id",
            "severity",
            "lifecycle_phase",
            "artifact",
            "status",
            "description",
            "evidence",
            "file_path",
            "line_range",
            "suggestion",
        }
