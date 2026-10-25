"""Unit tests for the diff-channel pattern wiring (V4.8.0 P1-R1).

Design doc: docs/planning/V4.8.0_R1_devsquad_gate_DESIGN.md §7.1. The V-1
probe proved `review --diff-file` produced no structured findings; these
tests pin the wiring that scans ADDED lines with the three existing
ReviewCheckers regex families (zero new check logic).

V4.8.1 F-D1 tests (§7.4): the findings face is filtered with the same
deterministic path gates as the changeset face — user include/exclude
globs, unsupported extensions, and built-in default excludes all apply
via review_filter's gate sequence.
"""

from __future__ import annotations

from scripts.collaboration.diff_pattern_scanner import (
    diff_pattern_scan_to_dicts,
    filter_diff_pattern_findings,
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

    def test_print_debug_exempt_in_cli_output_layer(self):
        # V4.9.0 dogfood finding (PR #71): print() is the product interface
        # of scripts/cli*.py command modules, not debug residue.
        findings = scan_diff_patterns(_diff("scripts/cli_defect.py", ['print("result")']))
        assert not [f for f in findings if f.rule_id == "diff-print_debug"]

    def test_print_debug_still_flagged_in_collaboration_modules(self):
        findings = scan_diff_patterns(_diff("scripts/collaboration/foo.py", ['print("debug")']))
        assert _by_rule(findings, "diff-print_debug").category == "BREAK-2"

    def test_cli_output_layer_exempt_is_print_debug_only(self):
        # The exemption is narrow: other anti-patterns still fire inside
        # CLI modules (secrets/eval remain fully covered).
        findings = scan_diff_patterns(_diff("scripts/cli_defect.py", ["y = eval(x)"]))
        assert _by_rule(findings, "diff-eval_usage").severity == "critical"

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


class TestFilterDiffPatternFindings:
    """V4.8.1 F-D1: pattern findings respect the deterministic path gates."""

    def test_user_exclude_drops_findings_for_excluded_path_keeps_others(self):
        # "tests/**" covers nested paths (trailing-/** matcher extension),
        # so the dogfood wrapper's exclude form works on the findings face.
        diff = _diff("tests/unit/test_fixture.py", ["x = 1  # TODO fix"]) + _diff("src/app.py", ["y = 2  # TODO fix"])
        dicts = diff_pattern_scan_to_dicts(diff, exclude=["tests/**"])
        assert {d["file_path"] for d in dicts} == {"src/app.py"}

    def test_markdown_code_smell_findings_dropped(self):
        # .md resolves to kind=document (NOT unsupported); code-smell
        # families require kind=source, so doc text quoting an anti-pattern
        # is prose, not a finding (F-D1 impact (b)).
        dicts = diff_pattern_scan_to_dicts(_diff("docs/evidence.md", ["seen: # TODO mention"]))
        assert dicts == []

    def test_markdown_secret_findings_are_kept(self):
        # Secrets are content leaks: a real key in a document is still a
        # leak, so the secret family survives on review-retained docs.
        dicts = diff_pattern_scan_to_dicts(_diff("docs/evidence.md", ['api_key = "abcdefghij1234567890"']))
        assert [d["rule_id"] for d in dicts] == ["diff-hardcoded_api_key"]

    def test_python_findings_survive_without_filters(self):
        dicts = diff_pattern_scan_to_dicts(_diff("src/app.py", ["z = 3  # TODO fix"]))
        assert [d["file_path"] for d in dicts] == ["src/app.py"]

    def test_unclaimed_extension_findings_dropped(self):
        # .js resolves to the system catch-all (kind=unclaimed): dropped by
        # the unsupported_ext gate, same as the changeset face.
        dicts = diff_pattern_scan_to_dicts(_diff("web/app.js", ["q = 5  # TODO fix"]))
        assert dicts == []

    def test_default_exclude_applies_to_findings(self):
        dicts = diff_pattern_scan_to_dicts(_diff("dist/bundle.py", ["w = 4  # TODO fix"]))
        assert dicts == []

    def test_default_exclude_covers_nested_paths(self):
        # Regression-pins the trailing-/** matcher fix: the built-in
        # "dist/**" exclude now covers dist/sub/x.py too.
        dicts = diff_pattern_scan_to_dicts(_diff("dist/sub/bundle.py", ["w = 4  # TODO fix"]))
        assert dicts == []

    def test_user_include_rescues_secrets_but_not_code_smells(self):
        # Same rescue semantics as the changeset face: --include
        # force-retains an otherwise-unsupported path (.yml). The secret
        # family survives the rescue; code smells still require source kind.
        secret = _diff("ci/config.yml", ['api_key = "abcdefghij1234567890"'])
        smell = _diff("ci/config.yml", ["k = 6  # TODO fix"])
        kept_secret = diff_pattern_scan_to_dicts(secret, include=["ci/**"])
        kept_smell = diff_pattern_scan_to_dicts(smell, include=["ci/**"])
        assert [d["rule_id"] for d in kept_secret] == ["diff-hardcoded_api_key"]
        assert kept_smell == []

    def test_filter_function_operates_on_scanner_output(self):
        findings = scan_diff_patterns(
            _diff("tests/unit/test_fixture.py", ["x = 1  # TODO fix"]) + _diff("src/app.py", ["y = 2  # TODO fix"])
        )
        kept = filter_diff_pattern_findings(findings, exclude=["tests/**"])
        assert {f.file_path for f in kept} == {"src/app.py"}

    def test_empty_findings_short_circuits(self):
        assert filter_diff_pattern_findings([], exclude=["tests/**"]) == []

    def test_secrets_in_excluded_paths_are_also_filtered(self):
        # The path gates apply to every family: a critical secret finding in
        # an excluded path is dropped with the same user_exclude gate.
        dicts = diff_pattern_scan_to_dicts(
            _diff("tests/unit/test_fixture.py", ['api_key = "abcdefghij1234567890"']),
            exclude=["tests/**"],
        )
        assert dicts == []
