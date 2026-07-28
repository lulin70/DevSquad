#!/usr/bin/env python3
"""Generate LLM vs Mock Quality Decision Report (V4.4.0).

CLI entry point that runs Gate 0 (calibration) + Slice 1 (probe),
then writes a Markdown decision report.

Usage:
    # Full comparison (requires MOKA_API_KEY in .env)
    python scripts/generate_quality_decision_report.py

    # Skip LLM arm (2-arm comparison only)
    python scripts/generate_quality_decision_report.py --no-llm
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.collaboration.quality_calibration_gate import run_calibration_gate  # noqa: E402
from scripts.collaboration.quality_probe_slice import run_probe_slice  # noqa: E402


def main() -> int:
    """Generate quality decision report.

    Returns:
        0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(description="Generate LLM vs Mock quality decision report")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM arm (2-arm comparison only)")
    args = parser.parse_args()

    print("[INFO] Starting V4.4.0 quality decision report generation...")

    # Step 1: Gate 0
    print("[1/3] Running Gate 0 (calibration)...")
    gate_result = run_calibration_gate()
    print(f"      Gate 0 passed: {gate_result.passed}")
    if not gate_result.passed:
        for d in gate_result.diagnostics:
            print(f"      Diagnostic: {d}")

    # Step 2: Slice 1
    llm_backend = None
    if not args.no_llm and gate_result.passed:
        api_key = os.environ.get("MOKA_API_KEY")
        if api_key:
            from scripts.collaboration.llm_backend import OpenAIBackend
            llm_backend = OpenAIBackend(
                api_key=api_key,
                base_url=os.environ.get("MOKA_API_BASE", "https://api.moka-ai.com/v1"),
                model=os.environ.get("MOKA_MODEL", "anthropic/claude-opus-5"),
                max_tokens=1500,
                timeout=180.0,
            )
            print("[2/3] Running Slice 1 (probe) with LLM backend...")
        else:
            print("[2/3] No MOKA_API_KEY found. Running Slice 1 without LLM arm...")
    elif args.no_llm:
        print("[2/3] Running Slice 1 (probe) without LLM arm (--no-llm)...")
    else:
        print("[2/3] Gate 0 failed. Slice 1 skipped.")

    probe_report = run_probe_slice(llm_backend=llm_backend, n_samples=3)
    print(f"      Signal strength: {probe_report.signal_strength}")

    # Step 3: Generate report
    print("[3/3] Generating Markdown report...")
    date_str = time.strftime("%Y-%m-%d")
    report_path = _PROJECT_ROOT / "docs" / "analysis" / f"{date_str}_LLM_vs_Mock_Quality_Report.md"

    content = f"""# LLM vs Mock Quality Decision Report

**Date**: {time.strftime("%Y-%m-%d %H:%M:%S")}
**Version**: V4.4.0
**LLM Arm**: {"Skipped" if probe_report.llm_arm_skipped else "Included"}

---

{gate_result.to_markdown()}

---

{probe_report.to_markdown()}

---

## Decision

Based on the signal strength `{probe_report.signal_strength}`, see PRD §10 for the recommended next steps.

| Signal Strength | Recommended Path |
|----------------|-----------------|
| significant | Full comparison in V4.5.0 (OutputQualityComparator + 10 tasks + LLM-as-judge) |
| marginal | Targeted LLM-as-judge evaluation before full investment |
| noise | DevSquad does not need LLM for typical tasks |
| calibration_failed | Improve scoring instruments before re-evaluating |
"""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")
    print(f"[INFO] Report saved to: {report_path}")
    print(f"[INFO] Signal strength: {probe_report.signal_strength}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
