"""TD-077: CLI missing-dependency e2e (simulated real user, subprocess).

User rule: before any release, run tests that simulate real user journeys.
These tests spawn a real interpreter subprocess, because the failure
(TD-077) only manifests at process level: a bare system Python without
``yaml``/``pydantic`` used to hit an opaque ``ModuleNotFoundError`` inside
the import chain instead of the actionable message.

The bare environment is simulated with a ``MetaPathFinder`` that raises
``ImportError`` for the critical modules — the same failure class as a
system Python without the packages installed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "scripts" / "cli.py"

# Simulates a bare system Python: importing yaml/pydantic raises ImportError
# exactly as it would when the packages are not installed.
_BARE_ENV_RUNNER = """\
import sys


class _DepBlocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {"yaml", "pydantic"}:
            raise ImportError(f"{name} blocked (simulated bare system Python)")
        return None


sys.meta_path.insert(0, _DepBlocker())
from scripts.cli import main  # noqa: E402  (dependency check fires here)

sys.exit(main())
"""


class TestCliMissingDependencyE2E:
    """Subprocess e2e for the TD-077 friendly-dependency gate."""

    def test_version_works_in_full_environment(self) -> None:
        """Happy path: a real user with the venv gets --version output."""
        proc = subprocess.run(
            [sys.executable, str(CLI_PATH), "--version"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert "DevSquad" in proc.stdout

    def test_missing_dependency_exits_2_with_actionable_message(self) -> None:
        """Bare-environment user gets exit 2 + install hint, not a raw traceback."""
        proc = subprocess.run(
            [sys.executable, "-c", _BARE_ENV_RUNNER],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            env={
                "PYTHONPATH": str(REPO_ROOT),
                "PATH": "/usr/bin:/bin:/usr/local/bin",
            },
        )
        assert proc.returncode == 2, f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        assert "missing critical dependencies" in proc.stderr
        assert "pyyaml" in proc.stderr
        assert 'pip install -e ".[dev]"' in proc.stderr
        assert "virtual environment" in proc.stderr
        # The old failure mode was a raw ModuleNotFoundError traceback; the
        # friendly gate must not leak one.
        assert "ModuleNotFoundError" not in (proc.stdout + proc.stderr)

    def test_module_not_found_no_longer_hangs(self) -> None:
        """Regression anchor for TD-077: the bare-env run terminates quickly.

        The historical bug was a "hang" (180s timeout) caused by the import
        failure not propagating. subprocess.run's timeout enforces liveness.
        """
        proc = subprocess.run(
            [sys.executable, "-c", _BARE_ENV_RUNNER],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                "PYTHONPATH": str(REPO_ROOT),
                "PATH": "/usr/bin:/bin:/usr/local/bin",
            },
        )
        assert proc.returncode == 2
