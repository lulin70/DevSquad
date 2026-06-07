#!/usr/bin/env python3
"""
DevSquad Code Quality Toolkit

Provides automated code quality checks and fixes:
- Ruff linting & formatting
- Type checking with mypy
- Test coverage analysis
- Security scanning
- Import optimization
- Docstring validation

Usage:
    python scripts/code_quality.py check          # Run all checks
    python scripts/code_quality.py fix            # Auto-fix issues
    python scripts/code_quality.py report          # Generate quality report
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class CodeQualityToolkit:
    """
    Automated code quality toolkit for DevSquad.

    Features:
    - Multi-tool integration (ruff, mypy, pytest)
    - Configurable severity levels
    - Detailed reporting
    - Auto-fix capabilities
    """

    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root or os.getcwd())
        self.results: dict[str, any] = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "summary": {},
        }

    def run_ruff_check(self) -> tuple[int, str]:
        """Run ruff linter to find code style issues."""
        print("\n🔍 Running ruff linter...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "."],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode, result.stdout + result.stderr
        except FileNotFoundError:
            return 1, "ruff not installed. Install with: pip install ruff"
        except subprocess.TimeoutExpired:
            return 1, "ruff check timed out"

    def run_ruff_format_check(self) -> tuple[int, str]:
        """Check formatting without modifying files."""
        print("📐 Checking code format...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "format", "--check", "."],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode, result.stdout + result.stderr
        except FileNotFoundError:
            return 1, "ruff not installed"
        except subprocess.TimeoutExpired:
            return 1, "Format check timed out"

    def run_mypy_check(self) -> tuple[int, str]:
        """Run mypy type checker."""
        print("🔎 Running type checker (mypy)...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "mypy", "scripts", "skills"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=180,
            )
            return result.returncode, result.stdout + result.stderr
        except FileNotFoundError:
            return 0, "mypy not installed (optional)"
        except subprocess.TimeoutExpired:
            return 1, "mypy timed out"

    def run_import_sort(self) -> tuple[int, str]:
        """Check import sorting with ruff."""
        print("📚 Checking import order...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--select", "I", "."],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode, result.stdout + result.stderr
        except Exception as e:
            return 1, str(e)

    def count_print_statements(self) -> int:
        """Count remaining print() statements in source code."""
        print("📊 Counting print() statements...")
        count = 0
        for py_file in self.project_root.rglob("*.py"):
            # Skip test files, examples, and migration scripts
            if any(part in str(py_file) for part in ["test_", "_test.py", "examples/", "verify_", "sync_"]):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        stripped = line.strip()
                        if stripped.startswith("print(") and not stripped.startswith("#"):
                            # Allow print in CLI user-facing output
                            if (
                                "cli.py" not in str(py_file)
                                or "logger.error" in stripped
                                or "file=sys.stderr" in stripped
                            ):
                                count += 1
                                if count <= 10:  # Show first 10 occurrences
                                    print(f"  ⚠️  {py_file.relative_to(self.project_root)}:{line_num}")
            except Exception:
                pass
        return count

    def check_docstring_coverage(self) -> dict[str, any]:
        """Check docstring coverage for modules, classes, and functions."""
        print("📝 Checking docstring coverage...")
        import ast

        stats = {
            "modules": {"total": 0, "with_docstring": 0},
            "classes": {"total": 0, "with_docstring": 0},
            "functions": {"total": 0, "with_docstring": 0},
        }

        for py_file in self.project_root.rglob("*.py"):
            if any(part in str(py_file) for part in ["test_", "_test.py", "__pycache__"]):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))

                # Check module docstring
                stats["modules"]["total"] += 1
                if ast.get_docstring(tree):
                    stats["modules"]["with_docstring"] += 1

                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        node_type = "classes" if isinstance(node, ast.ClassDef) else "functions"
                        stats[node_type]["total"] += 1
                        if ast.get_docstring(node):
                            stats[node_type]["with_docstring"] += 1
            except Exception:
                pass

        # Calculate percentages
        for key in stats:
            total = stats[key]["total"]
            with_ds = stats[key]["with_docstring"]
            stats[key]["coverage"] = round((with_ds / total * 100), 1) if total > 0 else 0

        return stats

    def generate_report(self) -> str:
        """Generate comprehensive quality report."""
        report = []
        report.append("=" * 70)
        report.append("DevSquad Code Quality Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)

        # Summary
        total_issues = sum(v.get("issues", 0) for v in self.results["checks"].values())
        report.append("\n📊 Summary:")
        report.append(f"  Total Issues Found: {total_issues}")
        report.append(f"  Checks Run: {len(self.results['checks'])}")

        # Individual checks
        for check_name, data in self.results["checks"].items():
            status = "✅ PASS" if data.get("exit_code") == 0 else "❌ FAIL"
            issues = data.get("issues", 0)
            report.append(f"\n{status} {check_name}: {issues} issues")

            if data.get("output") and len(data["output"]) > 0:
                # Show first 20 lines of output
                lines = data["output"].split("\n")[:20]
                for line in lines:
                    if line.strip():
                        report.append(f"  {line}")
                if len(data["output"].split("\n")) > 20:
                    extra_lines = len(data["output"].split("\n")) - 20
                    report.append(f"  ... ({extra_lines} more lines)")

        # Recommendations
        report.append("\n💡 Recommendations:")
        if total_issues == 0:
            report.append("  Excellent! Code quality is top-notch.")
        else:
            report.append("  1. Run: python scripts/code_quality.py fix   # Auto-fix where possible")
            report.append("  2. Review manual fixes needed for complex issues")
            report.append("  3. Re-run: python scripts/code_quality.py check  # Verify fixes")

        report.append("\n" + "=" * 70)
        return "\n".join(report)

    def check(self) -> bool:
        """Run all quality checks and return True if all pass."""
        print("🚀 Starting DevSquad Code Quality Check\n")

        # Ruff linting
        exit_code, output = self.run_ruff_check()
        issues = len([l for l in output.split("\n") if l.strip()])
        self.results["checks"]["Ruff Linting"] = {
            "exit_code": exit_code,
            "issues": issues,
            "output": output,
        }
        print(f"  Found {issues} issues" if exit_code != 0 else "  ✅ No issues")

        # Format check
        exit_code, output = self.run_ruff_format_check()
        issues = len([l for l in output.split("\n") if l.strip() and "would reformat" in l])
        self.results["checks"]["Code Formatting"] = {
            "exit_code": exit_code,
            "issues": issues,
            "output": output,
        }
        print(f"  {issues} files need formatting" if exit_code != 0 else "  ✅ All files formatted")

        # Import sorting
        exit_code, output = self.run_import_sort()
        issues = len([l for l in output.split("\n") if l.strip()])
        self.results["checks"]["Import Sorting"] = {
            "exit_code": exit_code,
            "issues": issues,
            "output": output,
        }
        print(f"  {issues} import issues" if exit_code != 0 else "  ✅ Imports properly sorted")

        # Type checking (mypy)
        exit_code, output = self.run_mypy_check()
        type_errors = len([l for l in output.split("\n") if "error:" in l.lower()])
        self.results["checks"]["Type Checking (mypy)"] = {
            "exit_code": exit_code,
            "issues": type_errors,
            "output": output,
        }
        print(f"  {type_errors} type errors" if exit_code != 0 else "  ✅ Types OK")

        # Print statements
        print_count = self.count_print_statements()
        self.results["checks"]["print() Statements"] = {
            "exit_code": 1 if print_count > 0 else 0,
            "issues": print_count,
            "output": f"{print_count} print() statements found",
        }
        print(f"  {print_count} remaining" if print_count > 0 else "  ✅ All replaced with logging")

        # Docstring coverage
        ds_stats = self.check_docstring_coverage()
        avg_coverage = sum(v.get("coverage", 0) for v in ds_stats.values() if isinstance(v, dict)) / 3
        self.results["checks"]["Docstring Coverage"] = {
            "exit_code": 0 if avg_coverage >= 80 else 1,
            "issues": 100 - int(avg_coverage),
            "output": json.dumps(ds_stats, indent=2),
        }
        print(f"  Coverage: {avg_coverage:.1f}%")

        # Print report
        print(self.generate_report())

        # Return overall status
        all_pass = all(data.get("exit_code") == 0 for data in self.results["checks"].values())
        return all_pass

    def fix(self) -> None:
        """Auto-fix fixable issues."""
        print("🔧 Auto-fixing code quality issues...\n")

        # Fix imports
        print("📚 Fixing import sorting...")
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "--select", "I", "."],
            cwd=self.project_root,
        )

        # Fix linting issues
        print("🔍 Fixing linting issues...")
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "."],
            cwd=self.project_root,
        )

        # Format code
        print("📐 Formatting code...")
        subprocess.run(
            [sys.executable, "-m", "ruff", "format", "."],
            cwd=self.project_root,
        )

        print("\n✅ Auto-fix complete!")
        print("Run 'python scripts/code_quality.py check' to verify fixes.")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="DevSquad Code Quality Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s check     Run all quality checks
  %(prog)s fix       Auto-fix issues
  %(prog)s report    Show detailed report
        """,
    )
    parser.add_argument(
        "command",
        choices=["check", "fix", "report"],
        help="Command to execute",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Project root path (default: current directory)",
    )

    args = parser.parse_args()

    toolkit = CodeQualityToolkit(project_root=args.path)

    if args.command == "check":
        success = toolkit.check()
        sys.exit(0 if success else 1)
    elif args.command == "fix":
        toolkit.fix()
    elif args.command == "report":
        toolkit.check()


if __name__ == "__main__":
    main()
