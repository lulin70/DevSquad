#!/usr/bin/env python3
"""Generate the DevSquad dogfooding quarterly report (V4.8.0 P1-R3).

Every number in the report comes from a real command run in THIS invocation
(TD-074 discipline: no handwritten or estimated numbers). When a command
fails or its output cannot be parsed, the metric is marked ``unavailable``
with the reason — never fabricated.

Usage:
    python scripts/generate_dogfooding_report.py
        # writes docs/analysis/dogfooding_report_<YYYY-QN>.md
    python scripts/generate_dogfooding_report.py --skip-slow
        # skip the bandit scan (slow) for quick iterations
    python scripts/generate_dogfooding_report.py --with-pip-audit
        # also run pip-audit locally (network + slow; CI runs it by default)
    python scripts/generate_dogfooding_report.py --output docs/analysis/2026-Q4_dogfooding_report.md
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# CI mapping appendix: local command -> where CI runs the same gate.
CI_MAPPING: list[tuple[str, str]] = [
    (
        ".venv/bin/python scripts/check_version_consistency.py",
        "test.yml::test (per-Python test job, final consistency gate)",
    ),
    (".venv/bin/python scripts/check_config_consistency.py", "test.yml::test (consistency step)"),
    (".venv/bin/python scripts/check_test_pyramid.py tests/", "test.yml::test (pyramid gate)"),
    (".venv/bin/python scripts/check_bandit.py", "test.yml::security (bandit gate)"),
    ("static scan .github/workflows/*.yml", "test.yml (the protocol itself) + devsquad-gate.yml (P1-R1)"),
    ("parse docs/TECH_DEBT.md", "manual registry; referenced by retrospective batches"),
    ("pip-audit (CI security job)", "test.yml::security pip-audit steps"),
]


@dataclass
class MetricRecord:
    """One collected metric with full provenance."""

    name: str
    value: str
    unit: str
    command: str
    exit_code: int
    status: str  # ok | failed | unavailable
    note: str = ""
    excerpt: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_command(cmd: list[str]) -> tuple[int, str]:
    """Run a command at the project root, return (exit_code, combined_output)."""
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr)


def _record(
    name: str,
    command: str,
    exit_code: int,
    value: str,
    unit: str,
    status: str = "ok",
    note: str = "",
    excerpt: str = "",
) -> MetricRecord:
    tail = "\n".join(excerpt.strip().splitlines()[-6:]) if excerpt else ""
    return MetricRecord(name, value, unit, command, exit_code, status, note, tail)


# ------------------------------------------------------------------
# Parsers (pure functions over captured text — unit-tested)
# ------------------------------------------------------------------


def parse_version_consistency(text: str) -> tuple[str, str] | None:
    """Return (value, note) or None if unparseable."""
    m = re.search(r"All (\d+) required version checks passed", text)
    if m:
        return m.group(1) + "/passed", ""
    m = re.search(r"Results: (\d+) passed, \d+ skipped, \d+ warnings, (\d+) failed \(out of (\d+) checks\)", text)
    if m:
        return f"{m.group(1)}/{m.group(3)}", f"{m.group(2)} failed"
    return None


def parse_config_consistency(text: str) -> tuple[str, str] | None:
    m = re.search(r"Checks: (\d+) passed, (\d+) failed, (\d+) warnings, (\d+) skipped", text)
    if m:
        note = f"{m.group(3)} warnings (non-blocking)" if m.group(3) != "0" else ""
        return f"{m.group(1)} passed / {m.group(2)} failed", note
    return None


def parse_test_pyramid(text: str) -> tuple[str, str] | None:
    m = re.search(r"Total: (\d+) tests across (\d+) files", text)
    if not m:
        return None
    note = ""
    am = re.search(r"Assessment: (\w+)", text)
    if am and am.group(1) != "passing":
        detail = [ln.strip() for ln in text.splitlines() if "below" in ln or "above" in ln]
        note = f"assessment={am.group(1)}; " + "; ".join(detail[:1])
    return f"{m.group(1)} tests / {m.group(2)} files", note


def parse_bandit(text: str) -> tuple[str, str] | None:
    high = re.search(r"total HIGH\s*: (\d+)", text)
    med = re.search(r"total MEDIUM\s*: (\d+)", text)
    low = re.search(r"total LOW\s*: (\d+)", text)
    if not (high and med and low):
        return None
    return f"HIGH={high.group(1)} MEDIUM={med.group(1)} LOW={low.group(1)}", ""


def parse_tech_debt(text: str) -> tuple[str, str]:
    """Parse docs/TECH_DEBT.md entries: '### TD-NNN:' + following 状态 line."""
    entries = re.findall(r"^### (TD-\d+):", text, re.MULTILINE)
    statuses: list[str] = []
    for block in re.split(r"^### TD-\d+:", text, flags=re.MULTILINE)[1:]:
        sm = re.search(r"\*\*状态\*\*:\s*(OPEN|RESOLVED)", block)
        statuses.append(sm.group(1) if sm else "unknown")
    open_n = statuses.count("OPEN")
    resolved_n = statuses.count("RESOLVED")
    note = "" if "unknown" not in statuses else f"{statuses.count('unknown')} entries with unknown status"
    return (f"total={len(entries)} open={open_n} resolved={resolved_n}", note)


def count_pr_comment_protocol(workflows_dir: Path | None = None) -> tuple[str, str]:
    """Static scan: workflows carrying the idempotent 4-field PR comment."""
    fields = ("failure_class", "coverage", "failed_roles", "replay_cache")
    base = workflows_dir or Path(PROJECT_ROOT, ".github", "workflows")
    files = sorted(base.glob("*.yml"))
    with_protocol = []
    for wf in files:
        text = wf.read_text(encoding="utf-8")
        if "--edit-last" in text and "--create-if-none" in text:
            missing = [f for f in fields if f not in text]
            with_protocol.append(f"{wf.name} (missing fields: {', '.join(missing)})" if missing else wf.name)
    return (f"{len(with_protocol)} workflow file(s)", "; ".join(with_protocol))


# ------------------------------------------------------------------
# Collectors (run real commands)
# ------------------------------------------------------------------


def _collect(name: str, cmd: list[str], command_str: str, parser) -> MetricRecord:
    exit_code, output = run_command(cmd)
    parsed = parser(output)
    if parsed is None:
        return _record(
            name, command_str, exit_code, "unavailable", "", "unavailable", "command ran but output unparseable", output
        )
    value, note = parsed
    status = "ok" if exit_code == 0 else "failed"
    return _record(name, command_str, exit_code, value, "", status, note, output)


def collect_all(skip_slow: bool) -> list[MetricRecord]:
    py = str(Path(sys.executable))
    records: list[MetricRecord] = [
        _collect(
            "版本一致性",
            [py, "scripts/check_version_consistency.py"],
            f"{py} scripts/check_version_consistency.py",
            parse_version_consistency,
        ),
        _collect(
            "配置一致性",
            [py, "scripts/check_config_consistency.py"],
            f"{py} scripts/check_config_consistency.py",
            parse_config_consistency,
        ),
        _collect(
            "测试金字塔",
            [py, "scripts/check_test_pyramid.py", "tests/"],
            f"{py} scripts/check_test_pyramid.py tests/",
            parse_test_pyramid,
        ),
    ]
    if not skip_slow:
        records.append(
            _collect("Bandit 静态安全", [py, "scripts/check_bandit.py"], f"{py} scripts/check_bandit.py", parse_bandit)
        )
    # PR 评论协议（静态扫描，无子进程）
    value, note = count_pr_comment_protocol()
    records.append(_record("PR 评论协议覆盖", "static scan .github/workflows/*.yml", 0, value, "files", "ok", note))
    # TD 债务进出（文件解析，无子进程）
    td_text = Path(PROJECT_ROOT, "docs", "TECH_DEBT.md").read_text(encoding="utf-8")
    value, note = parse_tech_debt(td_text)
    records.append(_record("TD 债务进出", "parse docs/TECH_DEBT.md", 0, value, "entries", "ok", note))
    return records


def pip_audit_record(run_locally: bool) -> MetricRecord:
    if not run_locally:
        return MetricRecord(
            "pip-audit",
            "collected in CI",
            "advisories",
            "CI security job (test.yml) — 本地默认不执行；复现：见 CI 同款命令于报告附录",
            -1,
            "unavailable",
            "本地未执行（--with-pip-audit 未开启）",
        )
    exit_code, output = run_command([str(Path(sys.executable)), "-m", "pip", "audit", "--skip-editable"])
    finding = re.search(r"No known vulnerabilities", output)
    value = "0 known vulnerabilities" if finding and exit_code == 0 else "see excerpt"
    return _record(
        "pip-audit",
        f"{Path(sys.executable)} -m pip audit --skip-editable",
        exit_code,
        value,
        "",
        "ok" if exit_code == 0 else "failed",
        "",
        output,
    )


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------


def _git_sha() -> str:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True)
        return proc.stdout.strip()[:12] if proc.returncode == 0 else "unavailable"
    except OSError:
        return "unavailable"


def render_report(records: list[MetricRecord], out_path: Path, argv: list[str]) -> str:
    lines = [
        "# DevSquad Dogfooding 季度报告",
        "",
        "> 本报告由 `scripts/generate_dogfooding_report.py` 生成，勿手改。",
        f"> 生成时间：{_now()} | git SHA：{_git_sha()}",
        f"> 生成命令：`{' '.join(argv)}`",
        "",
        "## 指标总表",
        "",
        "| 指标 | 值 | 状态 |",
        "|---|---|---|",
    ]
    for r in records:
        lines.append(f"| {r.name} | {r.value} | {r.status} |")
    lines += ["", "## 指标详情（每项附复现命令与本次输出摘录）", ""]
    for r in records:
        note = f"  \n  备注：{r.note}" if r.note else ""
        lines += [
            f"### {r.name}",
            "",
            f"- 值：`{r.value}`（exit_code={r.exit_code}）",
            f"- 复现命令：`{r.command}`",
            note,
        ]
        if r.excerpt:
            lines += ["", "```", r.excerpt, "```"]
        lines.append("")
    lines += ["## 附录：CI 门禁对照（本地命令 ↔ CI 调用点）", "", "| 本地采集 | CI 调用点 |", "|---|---|"]
    for local, ci in CI_MAPPING:
        lines.append(f"| `{local}` | {ci} |")
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)


def main() -> int:
    quarter = f"{datetime.now().year}-Q{(datetime.now().month - 1) // 3 + 1}"
    parser = argparse.ArgumentParser(description="Generate the dogfooding quarterly report")
    parser.add_argument(
        "--output", type=Path, default=Path(PROJECT_ROOT, "docs", "analysis", f"dogfooding_report_{quarter}.md")
    )
    parser.add_argument("--skip-slow", action="store_true", help="skip the bandit scan")
    parser.add_argument(
        "--with-pip-audit", action="store_true", help="run pip-audit locally too (slow, network; CI runs it anyway)"
    )
    args = parser.parse_args()

    records = collect_all(skip_slow=args.skip_slow)
    records.append(pip_audit_record(run_locally=args.with_pip_audit))
    path = render_report(records, args.output, sys.argv)
    failed = [r.name for r in records if r.status != "ok"]
    print(f"[dogfooding] report written: {path}")
    print(f"[dogfooding] metrics collected: {len(records)}; non-ok: {failed or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
