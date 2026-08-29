#!/usr/bin/env python3
"""Risk Register CLI with file-backed persistence (V4.5.8 Wave 2)."""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from collections.abc import Callable, Iterator, MutableMapping
from functools import wraps
from pathlib import Path
from typing import Any

from scripts.collaboration.file_risk_store import (
    DEFAULT_ROOT,
    FileRiskStore,
    RiskStoreCorruptError,
    RiskStoreError,
)
from scripts.collaboration.risk_register import RiskRegister, RiskStatus

logger = logging.getLogger(__name__)
_call_counter_er: int = 0


def get_call_counter_er() -> int:
    return _call_counter_er


def _inc_call_counter_er() -> None:
    global _call_counter_er
    _call_counter_er += 1


# Output formatting

def _risk_to_dict(risk: Any) -> dict[str, Any]:
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
    _inc_call_counter_er()
    if not risks:
        return (
            "| Risk ID | Exposure | Probability | Impact | Status | Category |\n"
            "|---|---|---|---|---|---|\n"
            "| (none) | - | - | - | - | - |\n"
        )
    header = "| Risk ID | Exposure | Probability | Impact | Status | Category |\n"
    sep = "|---|---|---|---|---|---|\n"
    rows: list[str] = []
    for risk in sorted(risks, key=lambda item: item.exposure, reverse=True):
        status = risk.status.value if hasattr(risk.status, "value") else str(risk.status)
        rows.append(
            f"| `{getattr(risk, 'id', '?')[:24]}` | {risk.exposure:.2f} | "
            f"{risk.probability:.2f} | {risk.impact:.2f} | {status} | "
            f"{getattr(risk, 'category', 'general')} |"
        )
    return header + sep + "\n".join(rows) + "\n"


def _format_markdown_risk(risk: Any) -> str:
    _inc_call_counter_er()
    data = _risk_to_dict(risk)
    return "\n".join(
        [
            f"# Risk `{data['id']}`",
            "",
            f"- **Description**: {data['description']}",
            f"- **Exposure**: {data['exposure']:.3f} (= {data['probability']:.2f} x {data['impact']:.2f})",
            f"- **Status**: {data['status']}",
            f"- **Response Strategy**: {data['response_strategy']}",
            f"- **Category**: {data['category']}",
            f"- **Owner**: {data['owner'] or '(unassigned)'}",
            "",
        ]
    )


def _format_json(risks: list[Any]) -> str:
    _inc_call_counter_er()
    return json.dumps([_risk_to_dict(risk) for risk in risks], indent=2, ensure_ascii=False)


class _LegacyRiskStoreProxy(MutableMapping[str, Any]):
    """Compatibility view; the JSON FileRiskStore remains the source of truth."""

    def _items(self) -> dict[str, Any]:
        store = FileRiskStore(root=DEFAULT_ROOT)
        payload = store.load("default")
        return store.payload_to_items(payload)

    def __getitem__(self, key: str) -> Any:
        return self._items()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        store = FileRiskStore(root=DEFAULT_ROOT)
        with store.transaction("default") as transaction:
            items = store.payload_to_items(transaction.payload)
            items[key] = value
            transaction["items"] = [item.to_dict() for item in items.values()]

    def __delitem__(self, key: str) -> None:
        store = FileRiskStore(root=DEFAULT_ROOT)
        with store.transaction("default") as transaction:
            items = store.payload_to_items(transaction.payload)
            del items[key]
            transaction["items"] = [item.to_dict() for item in items.values()]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items())

    def __len__(self) -> int:
        return len(self._items())

    def clear(self) -> None:
        store = FileRiskStore(root=DEFAULT_ROOT)
        with store.transaction("default") as transaction:
            transaction["items"] = []


# Kept for V4.5.7 import compatibility. It is only a view over FileRiskStore.
_RISK_STORE: MutableMapping[str, Any] = _LegacyRiskStoreProxy()


def _get_store(args: argparse.Namespace | None = None) -> FileRiskStore:
    root = getattr(args, "root", None) if args is not None else None
    return FileRiskStore(root=Path(root) if root else DEFAULT_ROOT)


def _get_register(register_id: str = "default", root: Path | str = DEFAULT_ROOT) -> RiskRegister:
    store = FileRiskStore(root=root)
    return RiskRegister.from_store(store, register_id)


def _register_from_transaction(store: FileRiskStore, transaction: Any) -> RiskRegister:
    try:
        return RiskRegister.from_items(store.payload_to_items(transaction.payload).values())
    except (TypeError, ValueError, KeyError) as exc:
        raise RiskStoreCorruptError(f"Invalid risk item in store: {exc}") from exc


def _write_register(transaction: Any, register: RiskRegister) -> None:
    transaction["items"] = [item.to_dict() for item in register.items()]


def add_risk(
    description: str,
    probability: float = 0.5,
    impact: float = 0.5,
    category: str = "general",
    owner: str = "",
    register_id: str = "default",
    root: Path | str | None = None,
) -> str:
    """Add a risk through the persistent store (Python API compatibility helper)."""
    _inc_call_counter_er()
    store = FileRiskStore(root=Path(root) if root is not None else DEFAULT_ROOT)
    with store.transaction(register_id) as transaction:
        register = _register_from_transaction(store, transaction)
        saved = register.add(
            description=description,
            probability=probability,
            impact=impact,
            category=category,
            owner=owner,
        )
        _write_register(transaction, register)
    return saved.id


def _error_code(exc: Exception) -> int:
    if isinstance(exc, (RiskStoreError, OSError)):
        return 3
    return 1


def _safe_command(func: Callable[[argparse.Namespace], int]) -> Callable[[argparse.Namespace], int]:
    @wraps(func)
    def wrapped(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except Exception as exc:  # CLI boundary: never expose a traceback.
            print(f"ERROR: {exc}", file=sys.stderr)
            return _error_code(exc)

    return wrapped


def _validate_probability(value: float, field: str) -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{field} must be a finite number between 0 and 1")


def _filter_risks(risks: list[Any], args: argparse.Namespace) -> list[Any]:
    threshold = getattr(args, "min_exposure", None)
    severity = getattr(args, "severity", None)
    category = getattr(args, "category", None)
    if threshold is not None:
        _validate_probability(threshold, "min-exposure")
        risks = [risk for risk in risks if risk.exposure >= threshold]
    elif severity:
        try:
            numeric = float(severity)
        except ValueError:
            category = severity
        else:
            _validate_probability(numeric, "severity")
            risks = [risk for risk in risks if risk.exposure >= numeric]
    if category:
        if severity and not _looks_numeric(severity):
            print("WARNING: --severity category mode is deprecated; use --category", file=sys.stderr)
        risks = [risk for risk in risks if risk.category.lower() == category.lower()]
    return risks


def _looks_numeric(value: str) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


@_safe_command
def cmd_risks_list(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    register = _get_register(getattr(args, "register_id", "default"), _get_store(args).root)
    risks = _filter_risks(register.query(), args)
    limit = getattr(args, "limit", None)
    if limit is not None and limit > 0:
        risks = sorted(risks, key=lambda item: item.exposure, reverse=True)[:limit]
    if getattr(args, "format", "md") == "json":
        print(_format_json(risks))
    else:
        print(_format_markdown(risks))
    return 0


@_safe_command
def cmd_risks_show(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    register = _get_register(getattr(args, "register_id", "default"), _get_store(args).root)
    risks = _filter_risks(register.query(), args)
    target = next((risk for risk in risks if risk.id == args.risk_id), None)
    if target is None:
        print(f"ERROR: risk not found: {args.risk_id}", file=sys.stderr)
        return 1
    if getattr(args, "format", "md") == "json":
        print(_format_json([target]))
    else:
        print(_format_markdown_risk(target))
    return 0


def _approval_allowed(args: argparse.Namespace, operation: str, description: str, details: dict[str, Any]) -> int:
    from scripts.collaboration.approval_gate import ApprovalGate

    callback = getattr(args, "approval_callback", None)
    gate = ApprovalGate(approval_callback=callback)
    if getattr(gate, "_callback", None) is None:
        print("ERROR: approval unavailable", file=sys.stderr)
        return 2
    result = gate.request_approval(operation_type=operation, description=description, details=details)
    if not result.approved:
        print(f"ERROR: Approval denied: {result.reason}", file=sys.stderr)
        return 2
    return 0


@_safe_command
def cmd_risks_clear(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    store = _get_store(args)
    register_id = getattr(args, "register_id", "default")
    # Read count and request approval OUTSIDE the transaction: a human
    # approval must never hold the cross-process file lock (deadlock risk).
    count = len(store.load(register_id)["items"])
    if getattr(args, "require_approval", False):
        approval_rc = _approval_allowed(
            args,
            "clear_risk_register",
            f"Clear all {count} risks from RiskRegister",
            {"count": count, "operation": "clear_all_risks"},
        )
        if approval_rc != 0:
            return approval_rc
    with store.transaction(register_id) as transaction:
        transaction["items"] = []
    print(f"Cleared {count} risks from RiskRegister")
    return 0


@_safe_command
def cmd_risks_export(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    register = _get_register(getattr(args, "register_id", "default"), _get_store(args).root)
    risks = _filter_risks(register.query(), args)
    json_str = _format_json(risks)
    output = getattr(args, "output", None) or getattr(args, "output_positional", None)
    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        print(f"Exported {len(risks)} risks to {output}", file=sys.stderr)
    else:
        print(json_str)
    return 0


@_safe_command
def cmd_risks_add(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    _validate_probability(args.probability, "probability")
    _validate_probability(args.impact, "impact")
    store = _get_store(args)
    register_id = getattr(args, "register_id", "default")
    with store.transaction(register_id) as transaction:
        register = _register_from_transaction(store, transaction)
        risk = register.add(
            description=args.description,
            probability=args.probability,
            impact=args.impact,
            category=args.category,
            owner=args.owner,
        )
        _write_register(transaction, register)
    print(json.dumps(_risk_to_dict(risk), ensure_ascii=False))
    return 0


def _parse_votes(args: argparse.Namespace) -> dict[str, tuple[float, float]]:
    raw = args.votes
    if getattr(args, "votes_file", None):
        raw = Path(args.votes_file).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid votes JSON: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise ValueError("votes must be a non-empty JSON object")
    votes: dict[str, tuple[float, float]] = {}
    for role, pair in data.items():
        if not isinstance(role, str) or not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("each vote must be [probability, impact]")
        probability, impact = pair
        if not isinstance(probability, (int, float)) or not isinstance(impact, (int, float)):
            raise ValueError("vote probability and impact must be numbers")
        _validate_probability(float(probability), "vote probability")
        _validate_probability(float(impact), "vote impact")
        votes[role] = (float(probability), float(impact))
    return votes


@_safe_command
def cmd_risks_assess(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    votes = _parse_votes(args)
    store = _get_store(args)
    with store.transaction(getattr(args, "register_id", "default")) as transaction:
        register = _register_from_transaction(store, transaction)
        risk = register.assess(args.risk_id, votes)
        _write_register(transaction, register)
    print(json.dumps(_risk_to_dict(risk), ensure_ascii=False))
    return 0


@_safe_command
def cmd_risks_mitigate(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    store = _get_store(args)
    with store.transaction(getattr(args, "register_id", "default")) as transaction:
        register = _register_from_transaction(store, transaction)
        risk = register.mitigate(args.risk_id, args.strategy, args.owner, getattr(args, "plan", "") or "")
        _write_register(transaction, register)
    print(json.dumps(_risk_to_dict(risk), ensure_ascii=False))
    return 0


@_safe_command
def cmd_risks_close(args: argparse.Namespace) -> int:
    _inc_call_counter_er()
    store = _get_store(args)
    register_id = getattr(args, "register_id", "default")
    # Existence check and approval OUTSIDE the transaction: approval must
    # never hold the cross-process file lock (deadlock risk).
    items = store.payload_to_items(store.load(register_id))
    if args.risk_id not in items:
        print(f"ERROR: risk not found: {args.risk_id}", file=sys.stderr)
        return 1
    if getattr(args, "require_approval", False):
        approval_rc = _approval_allowed(
            args,
            "close_risk",
            f"Close risk {args.risk_id}",
            {"risk_id": args.risk_id, "operation": "close_risk"},
        )
        if approval_rc != 0:
            return approval_rc
    with store.transaction(register_id) as transaction:
        register = _register_from_transaction(store, transaction)
        risk = register.track(args.risk_id, RiskStatus.CLOSED)
        _write_register(transaction, register)
    print(json.dumps(_risk_to_dict(risk), ensure_ascii=False))
    return 0


def _add_common_arguments(parser: Any) -> None:
    parser.add_argument("--register-id", default="default", help="Risk register identifier")
    parser.add_argument("--root", default=None, help=argparse.SUPPRESS)


def register_risks_subparser(subparsers: Any) -> None:
    p_risks = subparsers.add_parser("risks", aliases=["risk"], help="Risk Register UX CLI")
    risks_sub = p_risks.add_subparsers(dest="risks_command", required=True, help="Risk subcommand")

    p_list = risks_sub.add_parser("list", help="List all risks")
    _add_common_arguments(p_list)
    p_list.add_argument("--format", "-f", choices=["md", "json"], default="md")
    p_list.add_argument("--min-exposure", type=float)
    p_list.add_argument("--severity")
    p_list.add_argument("--category")
    p_list.add_argument("--limit", "-n", type=int)
    p_list.set_defaults(func=cmd_risks_list)

    p_show = risks_sub.add_parser("show", help="Show one risk detail")
    _add_common_arguments(p_show)
    p_show.add_argument("risk_id")
    p_show.add_argument("--format", "-f", choices=["md", "json"], default="md")
    p_show.add_argument("--min-exposure", type=float)
    p_show.add_argument("--severity")
    p_show.add_argument("--category")
    p_show.set_defaults(func=cmd_risks_show)

    p_add = risks_sub.add_parser("add", help="Add a risk")
    _add_common_arguments(p_add)
    p_add.add_argument("description")
    p_add.add_argument("--probability", required=True, type=float)
    p_add.add_argument("--impact", required=True, type=float)
    p_add.add_argument("--category", required=True)
    p_add.add_argument("--owner", required=True)
    p_add.set_defaults(func=cmd_risks_add)

    p_assess = risks_sub.add_parser("assess", help="Assess a risk with role votes")
    _add_common_arguments(p_assess)
    p_assess.add_argument("risk_id")
    votes = p_assess.add_mutually_exclusive_group(required=True)
    votes.add_argument("--votes")
    votes.add_argument("--votes-file")
    p_assess.set_defaults(func=cmd_risks_assess)

    p_mitigate = risks_sub.add_parser("mitigate", help="Set a risk response strategy")
    _add_common_arguments(p_mitigate)
    p_mitigate.add_argument("risk_id")
    p_mitigate.add_argument("--strategy", required=True, choices=["avoid", "transfer", "mitigate", "accept"])
    p_mitigate.add_argument("--owner", required=True)
    p_mitigate.add_argument("--plan")
    p_mitigate.set_defaults(func=cmd_risks_mitigate)

    p_close = risks_sub.add_parser("close", help="Close a risk")
    _add_common_arguments(p_close)
    p_close.add_argument("risk_id")
    p_close.add_argument("--require-approval", action="store_true")
    p_close.set_defaults(func=cmd_risks_close)

    p_clear = risks_sub.add_parser("clear", help="Clear all risks")
    _add_common_arguments(p_clear)
    p_clear.add_argument("--require-approval", action="store_true")
    p_clear.set_defaults(func=cmd_risks_clear)

    p_export = risks_sub.add_parser("export", help="Export risks as JSON")
    _add_common_arguments(p_export)
    p_export.add_argument("output_positional", nargs="?", default=None)
    p_export.add_argument("--output", default=None)
    p_export.add_argument("--min-exposure", type=float)
    p_export.add_argument("--severity")
    p_export.add_argument("--category")
    p_export.set_defaults(func=cmd_risks_export)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DevSquad Risk Register CLI")
    register_risks_subparser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
