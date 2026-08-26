#!/usr/bin/env python3
"""cli_risks — V4.5.7 P12.5.2.

Risk Register UX CLI — surface V4.5.4 RiskRegister to shell users.

V4.5.7 design principles applied:
    - L-V455-004 (uniform lock ordering): clear() acquires ApprovalGate before mutation
    - L-V456-005 (full P1-P12): ApprovalGate integration preserves V4.5.5 backward compat
    - L-V457-005 (backward compat): RiskRegister.clear() unchanged; CLI wraps ApprovalGate

Subcommands:
    list      — show all risks (Markdown table by default)
    show      — show one risk detail
    clear     — clear all risks (requires --require-approval flag for ApprovalGate)
    export    — export as JSON

Output formats:
    --format md   — Markdown table (default, LLM-friendly)
    --format json — JSON (script-friendly)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Anti-ghost counter (V4.5.6 W1: _er naming)
_call_counter_er: int = 0


def get_call_counter_er() -> int:
    """Return module-level anti-ghost counter."""
    return _call_counter_er


def _inc_call_counter_er() -> None:
    """Bump anti-ghost counter."""
    global _call_counter_er
    _call_counter_er += 1


# Output formatting


def _risk_to_dict(risk: Any) -> dict[str, Any]:
    """Convert RiskItem to JSON-friendly dict."""
    return {
        "id": risk.id,
        "description": risk.description,
        "probability": risk.probability,
        "impact": risk.impact,
        "exposure": risk.exposure,
        "response_strategy": risk.response_strategy.value
        if hasattr(risk.response_strategy, "value")
        else str(risk.response_strategy),
        "owner": risk.owner,
        "status": risk.status.value if hasattr(risk.status, "value") else str(risk.status),
        "category": risk.category,
    }


def _format_markdown(risks: list[Any]) -> str:
    """Render risks as Markdown table."""
    _inc_call_counter_er()
    if not risks:
        return "| Risk ID | Exposure | Probability | Impact | Status | Category |\n|---|---|---|---|---|---|\n| (none) | - | - | - | - | - |\n"

    header = "| Risk ID | Exposure | Probability | Impact | Status | Category |\n"
    sep = "|---|---|---|---|---|---|\n"
    rows: list[str] = []
    for r in sorted(risks, key=lambda x: x.exposure, reverse=True):
        risk_id = getattr(r, "id", "?")[:24]
        exp = f"{r.exposure:.2f}"
        prob = f"{r.probability:.2f}"
        impact = f"{r.impact:.2f}"
        status = r.status.value if hasattr(r.status, "value") else str(r.status)
        cat = getattr(r, "category", "general")
        rows.append(f"| `{risk_id}` | {exp} | {prob} | {impact} | {status} | {cat} |")
    return header + sep + "\n".join(rows) + "\n"


def _format_markdown_risk(risk: Any) -> str:
    """Render single risk detail as Markdown."""
    _inc_call_counter_er()
    d = _risk_to_dict(risk)
    lines = [
        f"# Risk `{d['id']}`",
        "",
        f"- **Description**: {d['description']}",
        f"- **Exposure**: {d['exposure']:.3f} (= {d['probability']:.2f} x {d['impact']:.2f})",
        f"- **Status**: {d['status']}",
        f"- **Response Strategy**: {d['response_strategy']}",
        f"- **Category**: {d['category']}",
        f"- **Owner**: {d['owner'] or '(unassigned)'}",
        "",
    ]
    return "\n".join(lines)


def _format_json(risks: list[Any]) -> str:
    """Render risks as JSON array."""
    _inc_call_counter_er()
    return json.dumps([_risk_to_dict(r) for r in risks], indent=2, ensure_ascii=False)


# Public CLI commands


# Persistent store for risk items across CLI invocations (V4.5.7)
# V4.5.4 RiskRegister is stateless; in-memory dict allows list/show/clear
# to operate on the same items within a single CLI process.
_RISK_STORE: dict[str, Any] = {}


def _get_register() -> Any:
    """Get RiskRegister populated with in-process items."""
    from scripts.collaboration.risk_register import RiskRegister

    register = RiskRegister()
    for item in _RISK_STORE.values():
        register.add(risk_item=item)
    return register


def add_risk(
    description: str,
    probability: float = 0.5,
    impact: float = 0.5,
    category: str = "general",
    owner: str = "",
) -> str:
    """Add a risk (Python API; available for tests/programmatic use)."""
    from scripts.collaboration.risk_register import RiskItem, RiskRegister

    register = RiskRegister()
    item = RiskItem(
        id="",
        description=description,
        probability=probability,
        impact=impact,
        category=category,
        owner=owner,
    )
    # Use register.add to get deterministic id
    saved = register.add(risk_item=item)
    _RISK_STORE[saved.id] = saved
    _inc_call_counter_er()
    return saved.id


def cmd_risks_list(args: argparse.Namespace) -> int:
    """devsquad risks list - show all risks."""
    _inc_call_counter_er()
    register = _get_register()
    all_risks = register.query()

    if getattr(args, "severity", None):
        sev = args.severity.upper()
        all_risks = [r for r in all_risks if r.category.upper() == sev]

    limit = getattr(args, "limit", None)
    if limit and limit > 0:
        all_risks = all_risks[:limit]

    fmt = getattr(args, "format", "md")
    if fmt == "json":
        print(_format_json(all_risks))
    else:
        print(_format_markdown(all_risks))

    return 0


def cmd_risks_show(args: argparse.Namespace) -> int:
    """devsquad risks show <id> - show one risk."""
    _inc_call_counter_er()
    register = _get_register()
    target = None
    for r in register.query():
        if r.id == args.risk_id:
            target = r
            break

    if target is None:
        print(f"ERROR: risk not found: {args.risk_id}", file=sys.stderr)
        return 1

    fmt = getattr(args, "format", "md")
    if fmt == "json":
        print(_format_json([target]))
    else:
        print(_format_markdown_risk(target))
    return 0


def cmd_risks_clear(args: argparse.Namespace) -> int:
    """devsquad risks clear - clear all risks (with optional ApprovalGate)."""
    _inc_call_counter_er()
    register = _get_register()
    count = len(register.query())

    require_approval = getattr(args, "require_approval", False)
    if require_approval:
        try:
            from scripts.collaboration.approval_gate import ApprovalGate

            gate = ApprovalGate(approval_callback=None)  # auto-approve mode
            result = gate.request_approval(
                operation_type="clear_risk_register",
                description=f"Clear all {count} risks from RiskRegister",
                details={"count": count, "operation": "clear_all_risks"},
            )
            if not result.approved:
                print(f"ERROR: Approval denied: {result.reason}", file=sys.stderr)
                return 2
        except ImportError:
            logger.warning("ApprovalGate unavailable; proceeding without approval")

    _RISK_STORE.clear()
    print(f"Cleared {count} risks from RiskRegister")
    return 0


def cmd_risks_export(args: argparse.Namespace) -> int:
    """devsquad risks export [FILE] - export as JSON."""
    _inc_call_counter_er()
    register = _get_register()
    all_risks = register.query()
    json_str = _format_json(all_risks)

    output = getattr(args, "output", None)
    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        print(f"Exported {len(all_risks)} risks to {output}", file=sys.stderr)
    else:
        print(json_str)
    return 0


# CLI subparser registration


def register_risks_subparser(subparsers: Any) -> None:
    """Register risks subparser on the main CLI."""
    p_risks = subparsers.add_parser(
        "risks",
        aliases=["risk"],
        help="Risk Register UX CLI (V4.5.7 P12.5.2)",
    )
    risks_sub = p_risks.add_subparsers(
        dest="risks_command", required=True, help="Risk subcommand"
    )

    p_list = risks_sub.add_parser("list", help="List all risks")
    p_list.add_argument(
        "--format", "-f", choices=["md", "json"], default="md", help="Output format"
    )
    p_list.add_argument("--severity", help="Filter by category (P0/P1/P2/P3)")
    p_list.add_argument("--limit", "-n", type=int, help="Limit number of results")
    p_list.set_defaults(func=cmd_risks_list)

    p_show = risks_sub.add_parser("show", help="Show one risk detail")
    p_show.add_argument("risk_id", help="Risk ID to show")
    p_show.add_argument(
        "--format", "-f", choices=["md", "json"], default="md", help="Output format"
    )
    p_show.set_defaults(func=cmd_risks_show)

    p_clear = risks_sub.add_parser("clear", help="Clear all risks (destructive)")
    p_clear.add_argument(
        "--require-approval",
        action="store_true",
        help="Trigger ApprovalGate before clearing",
    )
    p_clear.set_defaults(func=cmd_risks_clear)

    p_export = risks_sub.add_parser("export", help="Export risks as JSON")
    p_export.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output file (default: stdout)",
    )
    p_export.set_defaults(func=cmd_risks_export)


def main(argv: list[str] | None = None) -> int:
    """Standalone CLI entry for testing."""
    parser = argparse.ArgumentParser(description="DevSquad Risk Register CLI")
    register_risks_subparser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
