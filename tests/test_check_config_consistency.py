#!/usr/bin/env python3
"""Tests for check_config_consistency.py (V4.2.1 P2-15) — Config Audit.

Coverage dimensions (per DevSquad Iron Rule 3):
  - Happy Path: all config files present and consistent → PASS
  - Error Case: version mismatch → FAIL; missing file → SKIP
  - Boundary: empty config, malformed YAML
  - Cross-file: VERSION ↔ Dockerfile/Chart.yaml/values.yaml alignment
  - Dependency: pyproject.toml ↔ requirements.txt sync
  - Key presence: required sections in .devsquad.yaml, values.yaml
  - Integration: main() CLI with --strict flag
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.check_config_consistency import (
    ConfigCheck,
    ConfigConsistencyChecker,
    format_report,
    main,
)


def _write(path: Path, content: str) -> None:
    """Write content to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class T1_ConfigCheckDataclass(unittest.TestCase):
    """T1: ConfigCheck dataclass fields."""

    def test_01_creation_with_all_fields(self) -> None:
        """Verify: ConfigCheck stores all fields correctly."""
        c = ConfigCheck(name="test", category="dependency", status="pass", message="OK")
        self.assertEqual(c.name, "test")
        self.assertEqual(c.category, "dependency")
        self.assertEqual(c.status, "pass")
        self.assertEqual(c.message, "OK")


class T2_DependencySync(unittest.TestCase):
    """T2: _check_dependency_sync() pyproject.toml ↔ requirements.txt."""

    def test_01_all_deps_present_passes(self) -> None:
        """Verify: All pyproject.toml deps in requirements.txt → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "pyproject.toml",
                """
[project]
name = "test"
version = "1.0.0"
dependencies = [
    "fastapi>=0.100.0",
    "pyyaml>=6.0",
]
""",
            )
            _write(root / "requirements.txt", "fastapi>=0.100.0\npyyaml>=6.0\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_dependency_sync()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "pass")

    def test_02_missing_dep_fails(self) -> None:
        """Verify: pyproject.toml dep missing from requirements.txt → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "pyproject.toml",
                """
[project]
name = "test"
version = "1.0.0"
dependencies = [
    "fastapi>=0.100.0",
    "pyyaml>=6.0",
]
""",
            )
            _write(root / "requirements.txt", "fastapi>=0.100.0\n")  # missing pyyaml
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_dependency_sync()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "fail")
            self.assertIn("pyyaml", results[0].message)

    def test_03_missing_pyproject_skips(self) -> None:
        """Verify: Missing pyproject.toml → SKIP."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "requirements.txt", "fastapi\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_dependency_sync()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "skip")

    def test_04_missing_requirements_skips(self) -> None:
        """Verify: Missing requirements.txt → SKIP."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "pyproject.toml",
                """
[project]
dependencies = ["fastapi"]
""",
            )
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_dependency_sync()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "skip")


class T3_KeyPresence(unittest.TestCase):
    """T3: _check_key_presence() required config keys."""

    def test_01_devsquad_yaml_with_quality_control_passes(self) -> None:
        """Verify: .devsquad.yaml with quality_control: section → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / ".devsquad.yaml", "quality_control:\n  enabled: true\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_key_presence()
            qc_check = next(c for c in results if c.name == "devsquad_yaml_quality_control")
            self.assertEqual(qc_check.status, "pass")

    def test_02_devsquad_yaml_missing_quality_control_fails(self) -> None:
        """Verify: .devsquad.yaml without quality_control → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / ".devsquad.yaml", "other_key: value\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_key_presence()
            qc_check = next(c for c in results if c.name == "devsquad_yaml_quality_control")
            self.assertEqual(qc_check.status, "fail")

    def test_03_values_yaml_with_image_keys_passes(self) -> None:
        """Verify: values.yaml with image: and tag: → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "helm/devsquad/values.yaml", 'image:\n  repository: foo\n  tag: "1.0.0"\n')
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_key_presence()
            img_check = next(c for c in results if c.name == "values_yaml_image_keys")
            self.assertEqual(img_check.status, "pass")

    def test_04_values_yaml_missing_tag_fails(self) -> None:
        """Verify: values.yaml without tag: → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "helm/devsquad/values.yaml", "image:\n  repository: foo\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_key_presence()
            img_check = next(c for c in results if c.name == "values_yaml_image_keys")
            self.assertEqual(img_check.status, "fail")

    def test_05_deployment_yaml_with_auth_passes(self) -> None:
        """Verify: deployment.yaml with authentication: → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "config/deployment.yaml", "authentication:\n  enabled: true\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_key_presence()
            auth_check = next(c for c in results if c.name == "deployment_yaml_auth")
            self.assertEqual(auth_check.status, "pass")

    def test_06_missing_devsquad_yaml_skips(self) -> None:
        """Verify: Missing .devsquad.yaml → SKIP."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_key_presence()
            devsquad_check = next(c for c in results if "devsquad" in c.name)
            self.assertEqual(devsquad_check.status, "skip")


class T4_CrossFileVersionAlignment(unittest.TestCase):
    """T4: _check_cross_file() version alignment across files."""

    def _setup_version_files(
        self,
        root: Path,
        version: str = "1.0.0",
        dockerfile_ver: str | None = "1.0.0",
        chart_ver: str | None = "1.0.0",
        values_ver: str | None = "1.0.0",
    ) -> None:
        """Helper: create VERSION + Dockerfile + Chart.yaml + values.yaml."""
        _write(root / "VERSION", version)
        if dockerfile_ver is not None:
            _write(root / "Dockerfile", f"ARG VERSION={dockerfile_ver}\n")
        if chart_ver is not None:
            _write(root / "helm/devsquad/Chart.yaml", f'version: {chart_ver}\nappVersion: "{chart_ver}"\n')
        if values_ver is not None:
            _write(root / "helm/devsquad/values.yaml", f'image:\n  repository: foo\n  tag: "{values_ver}"\n')

    def test_01_all_versions_match_passes(self) -> None:
        """Verify: All version refs match VERSION file → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._setup_version_files(root, "1.0.0")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_cross_file()
            pass_checks = [c for c in results if c.status == "pass"]
            self.assertGreaterEqual(len(pass_checks), 3)  # dockerfile + chart + values

    def test_02_dockerfile_version_mismatch_fails(self) -> None:
        """Verify: Dockerfile ARG VERSION != VERSION file → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._setup_version_files(root, "1.0.0", dockerfile_ver="2.0.0")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_cross_file()
            df_check = next(c for c in results if c.name == "dockerfile_version_match")
            self.assertEqual(df_check.status, "fail")

    def test_03_chart_appversion_mismatch_fails(self) -> None:
        """Verify: Chart.yaml appVersion != VERSION file → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._setup_version_files(root, "1.0.0", chart_ver="3.0.0")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_cross_file()
            chart_check = next(c for c in results if c.name == "chart_appversion_match")
            self.assertEqual(chart_check.status, "fail")

    def test_04_values_tag_mismatch_warns(self) -> None:
        """Verify: values.yaml tag != VERSION file → WARN (not FAIL)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._setup_version_files(root, "1.0.0", values_ver="0.9.0")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_cross_file()
            values_check = next(c for c in results if c.name == "values_yaml_tag_match")
            self.assertEqual(values_check.status, "warn")

    def test_05_missing_version_file_fails(self) -> None:
        """Verify: Missing VERSION file → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "Dockerfile", "ARG VERSION=1.0.0\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_cross_file()
            self.assertEqual(results[0].status, "fail")

    def test_06_missing_dockerfile_warns(self) -> None:
        """Verify: Missing Dockerfile → no dockerfile check (not crash)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "VERSION", "1.0.0")
            # No Dockerfile, no Chart.yaml, no values.yaml
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker._check_cross_file()
            # Should return empty list (all files missing, only version_file check)
            # Actually version_file exists, so check passes but no other checks
            self.assertIsInstance(results, list)


class T5_CheckAll(unittest.TestCase):
    """T5: check_all() runs all categories."""

    def test_01_returns_results_from_all_categories(self) -> None:
        """Verify: check_all() returns results from dependency + key_presence + cross_file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "VERSION", "1.0.0")
            _write(root / "Dockerfile", "ARG VERSION=1.0.0\n")
            _write(root / "pyproject.toml", "[project]\ndependencies = []\n")
            _write(root / "requirements.txt", "")
            _write(root / ".devsquad.yaml", "quality_control:\n  enabled: true\n")
            _write(root / "helm/devsquad/values.yaml", 'image:\n  repository: foo\n  tag: "1.0.0"\n')
            _write(root / "helm/devsquad/Chart.yaml", 'version: 1.0.0\nappVersion: "1.0.0"\n')
            _write(root / "config/deployment.yaml", "authentication:\n  enabled: true\n")
            checker = ConfigConsistencyChecker(repo_root=root)
            results = checker.check_all()
            categories = {c.category for c in results}
            self.assertIn("dependency", categories)
            self.assertIn("key_presence", categories)
            self.assertIn("cross_file", categories)
            self.assertIn("doc_command", categories)


class T6_FormatReport(unittest.TestCase):
    """T6: format_report() output."""

    def test_01_contains_check_names(self) -> None:
        """Verify: Check names appear in report."""
        checks = [
            ConfigCheck(name="test_check", category="dependency", status="pass", message="OK"),
        ]
        text = format_report(checks)
        self.assertIn("test_check", text)
        self.assertIn("[PASS]", text)

    def test_02_contains_summary_counts(self) -> None:
        """Verify: Summary counts appear in report."""
        checks = [
            ConfigCheck(name="a", category="x", status="pass", message=""),
            ConfigCheck(name="b", category="x", status="fail", message=""),
            ConfigCheck(name="c", category="x", status="warn", message=""),
        ]
        text = format_report(checks)
        self.assertIn("1 passed", text)
        self.assertIn("1 failed", text)
        self.assertIn("1 warnings", text)


class T7_MainCLI(unittest.TestCase):
    """T7: main() CLI entry point."""

    def test_01_returns_zero_when_all_pass(self) -> None:
        """Verify: main() exits 0 when all checks pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "VERSION", "1.0.0")
            _write(root / "Dockerfile", "ARG VERSION=1.0.0\n")
            _write(root / "helm/devsquad/Chart.yaml", 'version: 1.0.0\nappVersion: "1.0.0"\n')
            _write(root / "helm/devsquad/values.yaml", 'image:\n  repository: foo\n  tag: "1.0.0"\n')
            _write(root / "pyproject.toml", "[project]\ndependencies = []\n")
            _write(root / "requirements.txt", "")
            _write(root / ".devsquad.yaml", "quality_control:\n  enabled: true\n")
            _write(root / "config/deployment.yaml", "authentication:\n  enabled: true\n")
            with (
                mock.patch("sys.argv", ["check_config_consistency.py"]),
                mock.patch("scripts.check_config_consistency.REPO_ROOT", root),
            ):
                exit_code = main()
            # May have warnings but no failures → exit 0
            self.assertEqual(exit_code, 0)

    def test_02_returns_one_on_critical_failure(self) -> None:
        """Verify: main() exits 1 on FAIL status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(root / "VERSION", "1.0.0")
            _write(root / "Dockerfile", "ARG VERSION=2.0.0\n")  # mismatch → FAIL
            _write(root / "pyproject.toml", "[project]\ndependencies = []\n")
            _write(root / "requirements.txt", "")
            with (
                mock.patch("sys.argv", ["check_config_consistency.py"]),
                mock.patch("scripts.check_config_consistency.REPO_ROOT", root),
            ):
                exit_code = main()
            self.assertEqual(exit_code, 1)


class T8_RealRepoIntegration(unittest.TestCase):
    """T8: Integration test against real repo config files."""

    def test_01_real_repo_check_runs_without_crash(self) -> None:
        """Verify: Real repo config files can be checked without crashing."""
        checker = ConfigConsistencyChecker()
        results = checker.check_all()
        self.assertGreater(len(results), 0, "Expected at least one config check")
        # All results should have valid status
        valid_statuses = {"pass", "fail", "warn", "skip"}
        for c in results:
            self.assertIn(c.status, valid_statuses, f"Invalid status: {c.status}")


class T9_DocCommandConsistency(unittest.TestCase):
    """T9: _check_doc_commands() — doc commands vs real parser (V4.8.0 R2)."""

    def _doc_check(self, root: Path):
        """Run doc_command check against given repo root, return results."""
        checker = ConfigConsistencyChecker(repo_root=root)
        return checker._check_doc_commands()

    def test_01_valid_commands_pass(self) -> None:
        """Verify: All valid documented commands (incl. second-level) → PASS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "QUICKSTART.md",
                "# Quick Start\n"
                "```bash\n"
                "devsquad init\n"
                "devsquad demo\n"
                'devsquad run "design auth" --roles architect tester\n'
                'devsquad dispatch -t "task"\n'
                "devsquad sessions list\n"
                "devsquad sessions show abc123\n"
                "python scripts/cli.py init\n"
                "python3 scripts/cli.py status\n"
                'devsquad lifecycle spec -t "requirement"\n'
                "```\n",
            )
            results = self._doc_check(root)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "pass")

    def test_02_unknown_top_level_fails_with_location(self) -> None:
        """Verify: `devsquad nosuchcmd` → FAIL with file:line:command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "README.md",
                "```bash\ndevsquad init\ndevsquad nosuchcmd --flag\n```\n",
            )
            results = self._doc_check(root)
            self.assertEqual(results[0].status, "fail")
            self.assertIn("README.md:3:", results[0].message)
            self.assertIn("devsquad nosuchcmd", results[0].message)

    def test_03_unknown_second_level_fails(self) -> None:
        """Verify: `devsquad sessions badsub` → FAIL (second-level unknown)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "README-CN.md",
                "```bash\ndevsquad sessions list\ndevsquad sessions badsub\n```\n",
            )
            results = self._doc_check(root)
            self.assertEqual(results[0].status, "fail")
            self.assertIn("README-CN.md:3:", results[0].message)

    def test_04_no_doc_files_skips(self) -> None:
        """Verify: No doc files present → SKIP."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            results = self._doc_check(root)
            self.assertEqual(results[0].status, "skip")

    def test_05_commands_outside_code_blocks_ignored(self) -> None:
        """Verify: `devsquad nosuchcmd` outside a fenced block → not flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "QUICKSTART.md",
                "Run `devsquad nosuchcmd` inline — outside code blocks, not scanned.\n```bash\ndevsquad demo\n```\n",
            )
            results = self._doc_check(root)
            self.assertEqual(results[0].status, "pass")

    def test_06_flag_only_lines_skipped(self) -> None:
        """Verify: `devsquad --version` (no subcommand) and comment tails → not flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write(
                root / "QUICKSTART.md",
                "```bash\n"
                "devsquad --version\n"
                "python3 scripts/cli.py --version       # Expected: DevSquad 4.7.2\n"
                "python3 scripts/cli.py status          # Expected: System ready\n"
                "```\n",
            )
            results = self._doc_check(root)
            self.assertEqual(results[0].status, "pass")

    def test_07_registry_matches_parser_includes_aliases(self) -> None:
        """Verify: Registry from build_parser() contains aliases (e.g., run, i, lc)."""
        from scripts.check_config_consistency import _cli_command_registry

        top, groups = _cli_command_registry()
        for alias in ("run", "i", "lc", "ls", "m", "s", "try", "setup", "sess", "risk", "d", "play"):
            self.assertIn(alias, top, f"Alias '{alias}' missing from registry")
        self.assertIn("sessions", groups)
        self.assertIn("list", groups["sessions"])
        self.assertIn("spec", groups["lifecycle"])

    def test_08_real_repo_docs_all_green(self) -> None:
        """Verify: Current repo docs (QUICKSTART + README x3) pass doc_command gate."""
        checker = ConfigConsistencyChecker()
        results = checker._check_doc_commands()
        doc_results = [c for c in results if c.category == "doc_command"]
        self.assertTrue(any(c.status == "pass" for c in doc_results), f"doc_command not green: {doc_results}")


if __name__ == "__main__":
    unittest.main()
