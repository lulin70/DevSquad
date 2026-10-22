"""Unit tests for scripts/generate_dogfooding_report.py (V4.8.0 P1-R3).

Covers the parser functions (fixture text → values), the workflow protocol
scanner (tmp fixtures), and report rendering (tmp_path). All fixtures use
real output shapes captured from the actual check scripts on 2026-10-22.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_dogfooding_report import (  # noqa: E402
    MetricRecord,
    count_pr_comment_protocol,
    parse_bandit,
    parse_config_consistency,
    parse_tech_debt,
    parse_test_pyramid,
    parse_version_consistency,
    render_report,
)


class TestVersionConsistencyParser:
    def test_pass_line(self):
        out = "Some noise\nAll 82 required version checks passed (0 optional skipped). Version 4.7.2 is consistent.\n"
        value, note = parse_version_consistency(out)
        assert value == "82/passed"
        assert note == ""

    def test_results_line_with_failures(self):
        out = "Results: 77 passed, 0 skipped, 0 warnings, 5 failed (out of 82 checks)\n"
        value, note = parse_version_consistency(out)
        assert value == "77/82"
        assert "5 failed" in note

    def test_unparseable(self):
        assert parse_version_consistency("no summary here") is None


class TestConfigConsistencyParser:
    def test_counts(self):
        value, note = parse_config_consistency("Checks: 6 passed, 0 failed, 1 warnings, 0 skipped\n")
        assert value == "6 passed / 0 failed"
        assert "1 warnings" in note

    def test_zero_warnings(self):
        value, note = parse_config_consistency("Checks: 7 passed, 0 failed, 0 warnings, 0 skipped\n")
        assert value == "7 passed / 0 failed"
        assert note == ""

    def test_unparseable(self):
        assert parse_config_consistency("garbage") is None


class TestTestPyramidParser:
    def test_total_and_warning(self):
        out = (
            "Test Pyramid Report (V4.2.1 P2-21)\n"
            "  Total: 9842 tests across 406 files\n"
            "  Assessment: warning\n"
            "    - integration ratio 15.0% below 15% target (1472/9842 tests) — consider adding integration tests.\n"
        )
        value, note = parse_test_pyramid(out)
        assert value == "9842 tests / 406 files"
        assert "warning" in note
        assert "integration" in note

    def test_unparseable(self):
        assert parse_test_pyramid("nothing") is None


class TestBanditParser:
    def test_counts(self):
        out = (
            "Running bandit -r scripts/ -ll -f json ...\n"
            "  total HIGH       : 0\n"
            "  total MEDIUM     : 0\n"
            "  total LOW        : 102\n"
            "PASS: bandit gate (HIGH=0; MEDIUM within tolerance).\n"
        )
        value, _ = parse_bandit(out)
        assert value == "HIGH=0 MEDIUM=0 LOW=102"

    def test_unparseable(self):
        assert parse_bandit("no bandit output") is None


class TestTechDebtParser:
    def test_counts(self):
        fixture = """# 技术债登记

### TD-001: something
- **状态**: RESOLVED (V4.3.0 closed)

### TD-002: another
- **状态**: OPEN（2026-10-21 登记）

### TD-003: third
- **状态**: OPEN（登记于今日）
"""
        value, note = parse_tech_debt(fixture)
        assert value == "total=3 open=2 resolved=1"
        assert note == ""

    def test_unknown_status_flagged(self):
        fixture = """### TD-009: no status line here
- something else
"""
        value, note = parse_tech_debt(fixture)
        assert "unknown status" in note
        assert "1 entries" in note


class TestPrCommentProtocolScanner:
    def _write(self, tmp: Path, name: str, body: str) -> None:
        wf = tmp / name
        wf.write_text(body, encoding="utf-8")

    def test_counts_only_sticky_comment_workflows(self, tmp_path):
        self._write(tmp_path, "a.yml", "runs:\n  - run: gh pr comment 1 --edit-last --create-if-none\n")
        self._write(tmp_path, "b.yml", "runs:\n  - run: echo no comment\n")
        value, note = count_pr_comment_protocol(tmp_path)
        assert value == "1 workflow file(s)"
        assert "a.yml" in note
        assert "missing fields" in note  # a.yml lacks the 4 field names

    def test_full_protocol_no_missing_fields(self, tmp_path):
        body = (
            '"- failure_class: x",\n"- coverage: y",\n'
            '"- failed_roles: z",\n"- replay_cache: w",\n'
            "--edit-last --create-if-none\n"
        )
        self._write(tmp_path, "full.yml", body)
        value, note = count_pr_comment_protocol(tmp_path)
        assert value == "1 workflow file(s)"
        assert note == "full.yml"  # file listed, no missing-fields marker

    def test_real_repo_workflows(self):
        # The real repo has at least test.yml carrying the protocol.
        value, note = count_pr_comment_protocol()
        assert value.startswith("1") or "2" in value  # at least one workflow
        assert "test.yml" in note


class TestRenderReport:
    def test_report_contains_reproduce_commands(self, tmp_path):
        records = [
            MetricRecord("指标A", "82/passed", "", "python scripts/check_x.py", 0, "ok", "", "tail line"),
            MetricRecord("指标B", "unavailable", "", "python scripts/check_y.py", 1,
                         "unavailable", "command ran but output unparseable", "err line"),
        ]
        out = tmp_path / "report.md"
        render_report(records, out, ["prog", "--output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "勿手改" in text
        assert "指标总表" in text
        assert "复现命令：`python scripts/check_x.py`" in text
        assert "复现命令：`python scripts/check_y.py`" in text
        assert "tail line" in text  # excerpt embedded
        assert "CI 门禁对照" in text
