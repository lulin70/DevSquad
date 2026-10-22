#!/usr/bin/env python3
"""Configuration Consistency Checker (V4.2.1 P2-15).

Audits configuration consistency across multiple config files to catch
config drift early. Performs cross-file checks for version alignment,
dependency sync, and required key presence.

Usage:
    python scripts/check_config_consistency.py
    python scripts/check_config_consistency.py --strict  # fail on warnings too

Exit codes:
    0 = all critical checks passed (warnings may exist)
    1 = one or more critical checks failed
    2 = script error

Check categories:
    1. dependency  — pyproject.toml ↔ requirements.txt sync
    2. key_presence — required keys in .devsquad.yaml, values.yaml, etc.
    3. cross_file  — VERSION ↔ Dockerfile/Chart.yaml/values.yaml alignment
    4. doc_command — QUICKSTART/README×3 CLI commands ↔ real parser registrations (V4.8.0 R2)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ConfigCheck:
    """Result of a single configuration consistency check."""

    name: str  # e.g., "requirements_lock_sync"
    category: str  # "dependency" / "key_presence" / "cross_file"
    status: str  # "pass" / "fail" / "warn" / "skip"
    message: str  # Human-readable result detail


class ConfigConsistencyChecker:
    """Performs cross-file configuration consistency checks."""

    def __init__(self, repo_root: Path | None = None) -> None:
        """Initialize checker.

        Args:
            repo_root: Repository root path. Defaults to parent of scripts/.
        """
        self.repo_root = repo_root or REPO_ROOT

    # pytest collection guard
    __test__ = False

    def check_all(self) -> list[ConfigCheck]:
        """Run all configuration consistency checks.

        Returns:
            List of :class:`ConfigCheck` results across all categories.
        """
        results: list[ConfigCheck] = []
        results.extend(self._check_dependency_sync())
        results.extend(self._check_key_presence())
        results.extend(self._check_cross_file())
        results.extend(self._check_doc_commands())
        return results

    # === Category 1: Dependency sync ===

    def _check_dependency_sync(self) -> list[ConfigCheck]:
        """Verify pyproject.toml dependencies are present in requirements.txt."""
        results: list[ConfigCheck] = []
        pyproject_path = self.repo_root / "pyproject.toml"
        requirements_path = self.repo_root / "requirements.txt"

        if not pyproject_path.exists():
            results.append(
                ConfigCheck(
                    name="pyproject_exists",
                    category="dependency",
                    status="skip",
                    message=f"pyproject.toml not found at {pyproject_path}",
                )
            )
            return results

        if not requirements_path.exists():
            results.append(
                ConfigCheck(
                    name="requirements_exists",
                    category="dependency",
                    status="skip",
                    message=f"requirements.txt not found at {requirements_path}",
                )
            )
            return results

        # Extract dependencies from pyproject.toml [project.dependencies]
        pyproject_deps = self._extract_pyproject_dependencies(pyproject_path)
        requirements_text = requirements_path.read_text(encoding="utf-8")

        missing: list[str] = []
        for dep in pyproject_deps:
            # Check if the package name appears in requirements.txt
            # Match package name at start of line (ignoring version specifiers)
            dep_name = re.split(r"[<>=!\[ ]", dep, maxsplit=1)[0].lower()
            pattern = re.compile(rf"^\s*{re.escape(dep_name)}\b", re.MULTILINE | re.IGNORECASE)
            if not pattern.search(requirements_text):
                missing.append(dep)

        if missing:
            results.append(
                ConfigCheck(
                    name="pyproject_to_requirements_sync",
                    category="dependency",
                    status="fail",
                    message=f"{len(missing)} dependency(s) in pyproject.toml missing from "
                    f"requirements.txt: {', '.join(missing[:5])}",
                )
            )
        else:
            results.append(
                ConfigCheck(
                    name="pyproject_to_requirements_sync",
                    category="dependency",
                    status="pass",
                    message=f"All {len(pyproject_deps)} pyproject.toml dependencies present in requirements.txt",
                )
            )
        return results

    def _extract_pyproject_dependencies(self, path: Path) -> list[str]:
        """Extract dependency names from pyproject.toml [project.dependencies].

        Args:
            path: Path to pyproject.toml.

        Returns:
            List of dependency strings (e.g., ["fastapi>=0.100.0", "pyyaml>=6.0"]).
        """
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return []
        # Find [project.dependencies] section
        match = re.search(
            r"^\[project\]\s*\n(.*?)(?=^\[|\Z)",
            content,
            re.MULTILINE | re.DOTALL,
        )
        if not match:
            return []
        section = match.group(1)
        # Find dependencies = [...] array
        dep_match = re.search(
            r"^dependencies\s*=\s*\[(.*?)\]",
            section,
            re.MULTILINE | re.DOTALL,
        )
        if not dep_match:
            return []
        deps_raw = dep_match.group(1)
        # Extract quoted strings
        deps = re.findall(r'"([^"]+)"', deps_raw)
        return [d for d in deps if d]

    # === Category 2: Key presence ===

    def _check_key_presence(self) -> list[ConfigCheck]:
        """Verify required keys are present in config files."""
        results: list[ConfigCheck] = []

        # .devsquad.yaml must have quality_control section
        devsquad_path = self.repo_root / ".devsquad.yaml"
        if devsquad_path.exists():
            content = devsquad_path.read_text(encoding="utf-8")
            if re.search(r"^quality_control\s*:", content, re.MULTILINE):
                results.append(
                    ConfigCheck(
                        name="devsquad_yaml_quality_control",
                        category="key_presence",
                        status="pass",
                        message=".devsquad.yaml has quality_control section",
                    )
                )
            else:
                results.append(
                    ConfigCheck(
                        name="devsquad_yaml_quality_control",
                        category="key_presence",
                        status="fail",
                        message=".devsquad.yaml missing required 'quality_control' section",
                    )
                )
        else:
            results.append(
                ConfigCheck(
                    name="devsquad_yaml_exists",
                    category="key_presence",
                    status="skip",
                    message=".devsquad.yaml not found",
                )
            )

        # helm/devsquad/values.yaml must have image.repository and image.tag
        values_path = self.repo_root / "helm" / "devsquad" / "values.yaml"
        if values_path.exists():
            content = values_path.read_text(encoding="utf-8")
            has_repo = bool(re.search(r"^image\s*:", content, re.MULTILINE))
            has_tag = bool(re.search(r"^\s+tag\s*:", content, re.MULTILINE))
            if has_repo and has_tag:
                results.append(
                    ConfigCheck(
                        name="values_yaml_image_keys",
                        category="key_presence",
                        status="pass",
                        message="values.yaml has image.repository and image.tag",
                    )
                )
            else:
                missing_keys = []
                if not has_repo:
                    missing_keys.append("image")
                if not has_tag:
                    missing_keys.append("image.tag")
                results.append(
                    ConfigCheck(
                        name="values_yaml_image_keys",
                        category="key_presence",
                        status="fail",
                        message=f"values.yaml missing required keys: {', '.join(missing_keys)}",
                    )
                )
        else:
            results.append(
                ConfigCheck(
                    name="values_yaml_exists",
                    category="key_presence",
                    status="skip",
                    message="helm/devsquad/values.yaml not found",
                )
            )

        # config/deployment.yaml must have authentication section
        deployment_path = self.repo_root / "config" / "deployment.yaml"
        if deployment_path.exists():
            content = deployment_path.read_text(encoding="utf-8")
            if re.search(r"^authentication\s*:", content, re.MULTILINE):
                results.append(
                    ConfigCheck(
                        name="deployment_yaml_auth",
                        category="key_presence",
                        status="pass",
                        message="deployment.yaml has authentication section",
                    )
                )
            else:
                results.append(
                    ConfigCheck(
                        name="deployment_yaml_auth",
                        category="key_presence",
                        status="warn",
                        message="deployment.yaml missing 'authentication' section (security-relevant)",
                    )
                )
        else:
            results.append(
                ConfigCheck(
                    name="deployment_yaml_exists",
                    category="key_presence",
                    status="skip",
                    message="config/deployment.yaml not found",
                )
            )

        return results

    # === Category 3: Cross-file version alignment ===

    def _check_cross_file(self) -> list[ConfigCheck]:
        """Verify version alignment across VERSION, Dockerfile, Chart.yaml, values.yaml."""
        results: list[ConfigCheck] = []
        version_path = self.repo_root / "VERSION"

        # Read canonical version from VERSION file
        canonical_version: str | None = None
        if version_path.exists():
            canonical_version = version_path.read_text(encoding="utf-8").strip()
        if not canonical_version:
            results.append(
                ConfigCheck(
                    name="version_file_readable",
                    category="cross_file",
                    status="fail",
                    message="VERSION file not found or empty",
                )
            )
            return results

        # Dockerfile ARG VERSION must match VERSION file
        dockerfile_path = self.repo_root / "Dockerfile"
        if dockerfile_path.exists():
            content = dockerfile_path.read_text(encoding="utf-8")
            match = re.search(r"^ARG\s+VERSION\s*=\s*\"?(\d+\.\d+\.\d+)\"?", content, re.MULTILINE)
            if match:
                dockerfile_version = match.group(1)
                if dockerfile_version == canonical_version:
                    results.append(
                        ConfigCheck(
                            name="dockerfile_version_match",
                            category="cross_file",
                            status="pass",
                            message=f"Dockerfile ARG VERSION = {dockerfile_version} (matches VERSION file)",
                        )
                    )
                else:
                    results.append(
                        ConfigCheck(
                            name="dockerfile_version_match",
                            category="cross_file",
                            status="fail",
                            message=f"Dockerfile ARG VERSION = {dockerfile_version} but VERSION file = {canonical_version}",
                        )
                    )
            else:
                results.append(
                    ConfigCheck(
                        name="dockerfile_version_match",
                        category="cross_file",
                        status="warn",
                        message="Dockerfile does not contain 'ARG VERSION' directive",
                    )
                )

        # Chart.yaml appVersion must match VERSION file
        chart_path = self.repo_root / "helm" / "devsquad" / "Chart.yaml"
        if chart_path.exists():
            content = chart_path.read_text(encoding="utf-8")
            match = re.search(r'^appVersion\s*:\s*"(\d+\.\d+\.\d+)"', content, re.MULTILINE)
            if match:
                chart_version = match.group(1)
                if chart_version == canonical_version:
                    results.append(
                        ConfigCheck(
                            name="chart_appversion_match",
                            category="cross_file",
                            status="pass",
                            message=f"Chart.yaml appVersion = {chart_version} (matches VERSION file)",
                        )
                    )
                else:
                    results.append(
                        ConfigCheck(
                            name="chart_appversion_match",
                            category="cross_file",
                            status="fail",
                            message=f"Chart.yaml appVersion = {chart_version} but VERSION file = {canonical_version}",
                        )
                    )
            else:
                results.append(
                    ConfigCheck(
                        name="chart_appversion_match",
                        category="cross_file",
                        status="warn",
                        message="Chart.yaml does not contain appVersion field",
                    )
                )

        # values.yaml image.tag should match VERSION file (WARN, not FAIL —
        # values.yaml tag may intentionally lag for deployment pinning)
        values_path = self.repo_root / "helm" / "devsquad" / "values.yaml"
        if values_path.exists():
            content = values_path.read_text(encoding="utf-8")
            match = re.search(r'^\s+tag\s*:\s*"?(\d+\.\d+\.\d+)"?', content, re.MULTILINE)
            if match:
                values_tag = match.group(1)
                if values_tag == canonical_version:
                    results.append(
                        ConfigCheck(
                            name="values_yaml_tag_match",
                            category="cross_file",
                            status="pass",
                            message=f"values.yaml image.tag = {values_tag} (matches VERSION file)",
                        )
                    )
                else:
                    results.append(
                        ConfigCheck(
                            name="values_yaml_tag_match",
                            category="cross_file",
                            status="warn",
                            message=f"values.yaml image.tag = {values_tag} but VERSION file = {canonical_version} "
                            f"(may be intentional for deployment pinning)",
                        )
                    )
            else:
                results.append(
                    ConfigCheck(
                        name="values_yaml_tag_match",
                        category="cross_file",
                        status="warn",
                        message="values.yaml does not contain image.tag field",
                    )
                )

        return results

    # === Category 4: Doc command consistency (V4.8.0 R2) ===

    def _check_doc_commands(self) -> list[ConfigCheck]:
        """Verify documented CLI commands match real parser registrations.

        Scans fenced code blocks in QUICKSTART.md and README x3 for lines
        starting with ``devsquad`` / ``python scripts/cli.py`` / ``python3
        scripts/cli.py``, extracts the first (and where applicable second)
        subcommand token, and compares against the CLI parser's registered
        subcommand set (aliases included). Unknown subcommands → FAIL with
        file:line:command detail.
        """
        results: list[ConfigCheck] = []

        try:
            top_commands, group_subcommands = _cli_command_registry()
        except Exception as exc:  # defensive: parser build must never break CI
            results.append(
                ConfigCheck(
                    name="doc_command_registry",
                    category="doc_command",
                    status="skip",
                    message=f"Could not build CLI parser for doc_command check: {exc}",
                )
            )
            return results

        existing = [name for name in _DOC_SCAN_FILES if (self.repo_root / name).exists()]
        if not existing:
            results.append(
                ConfigCheck(
                    name="doc_files_present",
                    category="doc_command",
                    status="skip",
                    message=f"None of the doc files found ({', '.join(_DOC_SCAN_FILES)})",
                )
            )
            return results

        violations: list[str] = []
        scanned = 0
        for doc_name in _DOC_SCAN_FILES:
            doc_path = self.repo_root / doc_name
            if not doc_path.exists():
                continue
            in_block = False
            for lineno, line in enumerate(doc_path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.lstrip().startswith("```"):
                    in_block = not in_block
                    continue
                if not in_block:
                    continue
                match = _DOC_COMMAND_LINE_RE.match(line)
                if not match:
                    continue
                scanned += 1
                tokens = _tokens_without_comment(match.group(1))
                if not tokens or tokens[0].startswith(("-", "\\")):
                    continue  # flags only (e.g., `devsquad --version`) or continuation marker
                first = tokens[0]
                if first not in top_commands:
                    violations.append(f"{doc_name}:{lineno}: {line.strip()}")
                    continue
                sub_set = group_subcommands.get(first)
                if sub_set and len(tokens) > 1 and not tokens[1].startswith(("-", "\\")) and tokens[1] not in sub_set:
                    violations.append(f"{doc_name}:{lineno}: {line.strip()}")

        if violations:
            detail = "; ".join(violations[:3])
            more = f" (+{len(violations) - 3} more)" if len(violations) > 3 else ""
            results.append(
                ConfigCheck(
                    name="doc_command_consistency",
                    category="doc_command",
                    status="fail",
                    message=f"{len(violations)} documented command(s) reference unknown CLI subcommand(s): "
                    f"{detail}{more}",
                )
            )
        else:
            results.append(
                ConfigCheck(
                    name="doc_command_consistency",
                    category="doc_command",
                    status="pass",
                    message=f"All {scanned} documented CLI command(s) match registered subcommands "
                    f"(scanned: {', '.join(existing)})",
                )
            )
        return results


_DOC_SCAN_FILES = ("QUICKSTART.md", "README.md", "README-CN.md", "README-JP.md")
_DOC_COMMAND_LINE_RE = re.compile(r"^\s*[$%]?\s*(?:devsquad|python3?\s+scripts/cli\.py)\s+(.+?)\s*$")


def _tokens_without_comment(text: str) -> list[str]:
    """Split into whitespace tokens, dropping an inline comment tail.

    Args:
        text: Command tail after the ``devsquad``/``python scripts/cli.py`` prefix.

    Returns:
        Tokens up to (excluding) the first ``#``-prefixed token.
    """
    tokens: list[str] = []
    for tok in text.split():
        if tok.startswith("#"):
            break
        tokens.append(tok)
    return tokens


def _collect_subparser_commands(parser: argparse.ArgumentParser) -> set[str]:
    """Collect registered subcommand names (aliases included) from a parser.

    Args:
        parser: The argparse parser to introspect.

    Returns:
        Names registered via ``add_subparsers().add_parser()`` (incl. aliases),
        plus positional-with-choices values (e.g., ``lifecycle spec|plan|...``).
    """
    names: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            names.update(action.choices.keys())
        elif action.choices and not action.option_strings:
            names.update(action.choices)
    return names


def _cli_command_registry() -> tuple[set[str], dict[str, set[str]]]:
    """Build the real CLI parser and extract registered command names.

    Returns:
        Tuple of (top-level command names incl. aliases, second-level command
        names keyed by group command, e.g., {"sessions": {"list", "show"}}).
    """
    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.cli import build_parser  # lazy: heavy import chain

    parser = build_parser()
    top: set[str] = set()
    groups: dict[str, set[str]] = {}
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, sub_parser in action.choices.items():
            top.add(name)
            subs = _collect_subparser_commands(sub_parser)
            if subs:
                groups[name] = subs
    return top, groups


def format_report(checks: list[ConfigCheck]) -> str:
    """Format check results as a human-readable report.

    Args:
        checks: List of ConfigCheck results.

    Returns:
        Multi-line string report.
    """
    passed = [c for c in checks if c.status == "pass"]
    failed = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status == "warn"]
    skipped = [c for c in checks if c.status == "skip"]

    lines: list[str] = []
    lines.append("Configuration Consistency Report (V4.2.1 P2-15)")
    lines.append(
        f"  Checks: {len(passed)} passed, {len(failed)} failed, {len(warnings)} warnings, {len(skipped)} skipped"
    )
    lines.append("")

    for check in checks:
        status_label = {
            "pass": "[PASS]",
            "fail": "[FAIL]",
            "warn": "[WARN]",
            "skip": "[SKIP]",
        }.get(check.status, "[????]")
        lines.append(f"  {status_label} {check.name:<35} {check.message}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit configuration consistency across project config files.")
    parser.add_argument("--strict", action="store_true", help="fail on warnings too")
    args = parser.parse_args()

    checker = ConfigConsistencyChecker()
    checks = checker.check_all()

    print(format_report(checks))
    print("")

    failed = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status == "warn"]

    if failed:
        print(f"\n{len(failed)} critical check(s) failed:")
        for c in failed:
            print(f"  - {c.name}: {c.message}")
        return 1

    if warnings and args.strict:
        print(f"\n{len(warnings)} warning(s) treated as failures (--strict mode):")
        for c in warnings:
            print(f"  - {c.name}: {c.message}")
        return 1

    if warnings:
        print(f"\n{len(warnings)} warning(s) (non-blocking). All critical checks passed.")
    else:
        print("All configuration consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
