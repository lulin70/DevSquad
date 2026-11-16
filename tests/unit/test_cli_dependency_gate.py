"""TD-077: CLI dependency self-check gate (unit tests).

Covers ``scripts.cli.check_critical_dependencies``:

- missing dependency list -> ``SystemExit(2)`` with an actionable message
- all dependencies present -> no exception
- partial dependency missing -> only the missing package is reported
"""

from __future__ import annotations

import pytest

from scripts.cli import check_critical_dependencies


class TestCheckCriticalDependencies:
    """Unit tests for the TD-077 fail-fast dependency gate."""

    def test_missing_dependency_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A missing module raises SystemExit(2) and names the fix command."""
        with pytest.raises(SystemExit) as exc_info:
            check_critical_dependencies([("no_such_module_td077", "no-such-pkg")])

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "missing critical dependencies" in captured.err
        assert "no-such-pkg" in captured.err
        assert "pip install" in captured.err

    def test_all_present_passes_silently(self, capsys: pytest.CaptureFixture[str]) -> None:
        """With every dependency importable the check returns without output."""
        check_critical_dependencies([("yaml", "pyyaml"), ("pydantic", "pydantic")])

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_partial_missing_reports_only_missing_pkg(self, capsys: pytest.CaptureFixture[str]) -> None:
        """One missing module lists only that package, not the present ones."""
        with pytest.raises(SystemExit):
            check_critical_dependencies([("yaml", "pyyaml"), ("no_such_module_td077", "ghost-pkg")])

        captured = capsys.readouterr()
        assert "ghost-pkg" in captured.err
        assert "pyyaml" not in captured.err
