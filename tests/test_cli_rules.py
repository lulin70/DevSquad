#!/usr/bin/env python3
"""W1-2 tests for the ``devsquad rules check`` command."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from scripts.cli_rules import cmd_rules_check, register_rules_subparser


def _write_rules(path: Path, rules: list[dict]) -> None:
    path.write_text(json.dumps({"rules": rules}), encoding="utf-8")


def test_rules_check_prints_effective_layer_pattern_and_body(tmp_path: Path, capsys) -> None:
    project = tmp_path / ".devsquad" / "rule.json"
    project.parent.mkdir()
    _write_rules(project, [{"pattern": "**/*.py", "body": {"review": True, "owner": "project"}}])

    rc = cmd_rules_check(Namespace(path="src/app.py", rule=None, repo_root=tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "Path: src/app.py" in captured.out
    assert "Layer: project" in captured.out
    assert "Pattern: **/*.py" in captured.out
    assert '"owner": "project"' in captured.out


def test_rules_check_forwards_explicit_cli_rule(tmp_path: Path, capsys) -> None:
    rule_file = tmp_path / "explicit.json"
    _write_rules(rule_file, [{"pattern": "**", "body": {"source": "cli"}}])

    rc = cmd_rules_check(Namespace(path="notes.txt", rule=rule_file, repo_root=tmp_path))

    captured = capsys.readouterr()
    assert rc == 0
    assert "Layer: cli" in captured.out
    assert '"source": "cli"' in captured.out


def test_rules_check_reports_malformed_config(tmp_path: Path, capsys) -> None:
    project = tmp_path / ".devsquad" / "rule.json"
    project.parent.mkdir()
    project.write_text("{not json", encoding="utf-8")

    rc = cmd_rules_check(Namespace(path="src/app.py", rule=None, repo_root=tmp_path))

    captured = capsys.readouterr()
    assert rc == 1
    assert "Error resolving rule" in captured.err
    assert str(project) in captured.err


def test_register_rules_subparser_exposes_nested_command() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_rules_subparser(subparsers)

    args = parser.parse_args(["rules", "check", "README.md"])

    assert args.command == "rules"
    assert args.rules_command == "check"
    assert args.path == "README.md"
    assert callable(args.func)
