#!/usr/bin/env python3
"""V4.6.0-doc-governance P0: Bandit CI Gate.

Wraps `bandit -r scripts/ -ll` (low + medium severity) and:

- Fails CI when HIGH or MEDIUM severity issues exceed ``--fail-on-medium`` (default
  on for CI).
- Writes a JSON report to ``docs/audits/bandit_v{version}.json`` for trend-tracking.
- Skips files under ``scripts/collaboration/_version.py`` (artifact, not source).

The gate is intentionally lenient on LOW severity (bandit defaults report ~100 LOW
for our codebase; treating them as CI-blockers would create churn). High and Medium
findings must be addressed or marked ``# nosec`` with a justification comment.

Exit codes:
  0 = no HIGH/MEDIUM findings (LOW may exist)
  1 = HIGH or MEDIUM findings present (per --fail-on-medium)
  2 = bandit not installed or scan error

Usage:
    python scripts/check_bandit.py [--source scripts/] [--report docs/audits/bandit_vX.json]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bandit_path() -> str | None:
    """Return the bandit binary path or None if not installed."""
    return shutil.which("bandit") or shutil.which("python3 -m bandit")


def _parse_json_report(output: str) -> dict:
    """Parse bandit's JSON payload even when the CLI prefixes progress text."""
    if not output:
        return {}
    start = output.find("{")
    end = output.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        parsed = json.loads(output[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_bandit(source: str, json_report: Path) -> tuple[int, dict]:
    """Invoke bandit and return (exit_code, parsed_json_report)."""
    cmd = [
        "bandit",
        "-q",
        "-r",
        source,
        "-ll",  # report low + medium + high
        "-f",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    json_report.parent.mkdir(parents=True, exist_ok=True)
    json_report.write_text(proc.stdout or "{}", encoding="utf-8")
    return proc.returncode, _parse_json_report(proc.stdout)


def _is_scan_clean(report: dict) -> bool:
    """True iff the bandit JSON report is non-empty and parseable.

    Bandit may return non-zero exit with empty stdout in restricted sandboxes
    (e.g. network/import restrictions). In that case the report dict is empty
    and we must fail closed rather than pretend the scan passed.
    """
    if not report:
        return False
    return "results" in report and "metrics" in report


def _summarize(report: dict) -> tuple[int, int, int]:
    """Return (high, medium, low) counts from a bandit JSON report."""
    metrics = report.get("metrics", {}).get("_totals", {})
    high = int(metrics.get("SEVERITY.HIGH", metrics.get("HIGH", 0)))
    medium = int(metrics.get("SEVERITY.MEDIUM", metrics.get("MEDIUM", 0)))
    low = int(metrics.get("SEVERITY.LOW", metrics.get("LOW", 0)))
    return high, medium, low


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bandit CI gate wrapper")
    parser.add_argument(
        "--source",
        default="scripts/",
        help="Source directory to scan (default: scripts/)",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="JSON report output path (default: docs/audits/bandit_latest.json)",
    )
    parser.add_argument(
        "--fail-on-medium",
        action="store_true",
        default=True,
        help="Exit 1 when any HIGH or MEDIUM finding is present (default: on)",
    )
    parser.add_argument(
        "--no-fail-on-medium",
        dest="fail_on_medium",
        action="store_false",
        help="Only fail on HIGH findings",
    )
    parser.add_argument(
        "--max-medium",
        type=int,
        default=None,
        help="Allowed MEDIUM finding count; omit to fail on any MEDIUM",
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="Version label for the report file (default: latest)",
    )
    args = parser.parse_args(argv)

    if not _bandit_path():
        print("ERROR: bandit is not installed.", file=sys.stderr)
        print("Install with: pip install bandit", file=sys.stderr)
        return 2

    if args.report is None:
        args.report = f"docs/audits/bandit_{args.version}.json"

    print(f"Running bandit -r {args.source} -ll -f json ...")
    rc, report = _run_bandit(args.source, Path(args.report))
    high, medium, low = _summarize(report)
    ts = datetime.now(timezone.utc).isoformat()
    clean = _is_scan_clean(report)
    print(f"  bandit exit code : {rc}")
    print(f"  total HIGH       : {high}")
    print(f"  total MEDIUM     : {medium}")
    print(f"  total LOW        : {low}")
    print(f"  scan clean       : {clean}")
    print(f"  report           : {args.report}")
    print(f"  scanned_at       : {ts}")
    if not clean:
        print(
            "FAIL: bandit scan did not produce a parseable JSON report. "
            "Inspect the report at " + str(args.report) + " and verify the "
            "bandit install (pip show bandit).",
            file=sys.stderr,
        )
        return 1
    allowed_medium = args.max_medium if args.max_medium is not None else 0
    if args.fail_on_medium and (high > 0 or medium > allowed_medium):
        allowed = args.max_medium if args.max_medium is not None else 0
        print(
            f"FAIL: {high} HIGH + {medium} MEDIUM findings "
            f"(allowed MEDIUM={allowed}) — address or add # nosec "
            "with justification before merging.",
            file=sys.stderr,
        )
        return 1
    if high > 0:
        print(f"FAIL: {high} HIGH findings — address before merging.", file=sys.stderr)
        return 1
    print("PASS: bandit gate (HIGH=0; MEDIUM within tolerance).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
