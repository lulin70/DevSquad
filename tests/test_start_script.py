#!/usr/bin/env python3
"""
Tests for scripts/start.sh one-click startup script (P0-2).

Verifies:
  - Script exists and is executable
  - Script syntax is valid (bash -n)
  - Contains the 4 mandatory phases per project hard constraint:
    1. Environment check (Python version + dependencies)
    2. Database initialization (runtime dirs + SQLite)
    3. Frontend build (Streamlit availability check)
    4. Service startup (uvicorn API server + optional dashboard)
  - --help flag works
  - Supports --dashboard flag
  - Honors DEVSQUAD_API_PORT / DEVSQUAD_DASHBOARD_PORT env vars
"""

import os
import subprocess
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts", "start.sh")


class TestStartScriptExists:
    """Verify start.sh exists and is executable."""

    def test_script_exists(self):
        """start.sh must exist (project hard constraint)."""
        assert os.path.isfile(SCRIPT_PATH), f"Missing: {SCRIPT_PATH}"

    def test_script_is_executable(self):
        """start.sh must be executable."""
        assert os.access(SCRIPT_PATH, os.X_OK), f"Not executable: {SCRIPT_PATH}"

    def test_script_has_shebang(self):
        """start.sh must have bash shebang."""
        with open(SCRIPT_PATH) as f:
            first_line = f.readline()
        assert first_line.startswith("#!/bin/bash"), f"Bad shebang: {first_line}"


class TestStartScriptSyntax:
    """Verify start.sh syntax is valid."""

    def test_bash_syntax_valid(self):
        """bash -n must pass (no syntax errors)."""
        result = subprocess.run(
            ["bash", "-n", SCRIPT_PATH],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error:\n{result.stderr}"


class TestStartScriptPhases:
    """Verify start.sh contains the 4 mandatory phases per hard constraint."""

    def test_phase_1_environment_check(self):
        """Phase 1: Environment check (Python version + dependencies)."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "环境检查" in content or "Environment Check" in content
        assert "PYTHON_VERSION" in content or "python3" in content
        assert "3.10" in content  # Minimum version check

    def test_phase_2_database_initialization(self):
        """Phase 2: Database initialization (runtime dirs + SQLite)."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "数据库" in content or "Database" in content
        assert "mkdir" in content  # Create runtime directories
        assert "data" in content or "checkpoints" in content

    def test_phase_3_frontend_build(self):
        """Phase 3: Frontend build (Streamlit availability check)."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "前端" in content or "Frontend" in content
        assert "streamlit" in content.lower()

    def test_phase_4_service_startup(self):
        """Phase 4: Service startup (uvicorn API server)."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "服务启动" in content or "Service Startup" in content
        assert "uvicorn" in content
        assert "api_server" in content

    def test_all_four_phases_present(self):
        """All 4 phases must be present in order."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        phase_markers = ["[1/4]", "[2/4]", "[3/4]", "[4/4]"]
        positions = [content.find(m) for m in phase_markers]
        assert all(p >= 0 for p in positions), f"Missing phase marker: {phase_markers}"
        assert positions == sorted(positions), "Phases out of order"


class TestStartScriptHelpFlag:
    """Verify --help flag works."""

    def test_help_flag_exits_zero(self):
        """--help must exit 0 and show usage."""
        result = subprocess.run(
            ["bash", SCRIPT_PATH, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0
        assert "用法" in result.stdout or "usage" in result.stdout.lower()

    def test_help_shows_dashboard_option(self):
        """--help must mention --dashboard option."""
        result = subprocess.run(
            ["bash", SCRIPT_PATH, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert "--dashboard" in result.stdout

    def test_help_shows_env_vars(self):
        """--help must document env vars."""
        result = subprocess.run(
            ["bash", SCRIPT_PATH, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert "DEVSQUAD_API_PORT" in result.stdout
        assert "DEVSQUAD_DASHBOARD_PORT" in result.stdout


class TestStartScriptFlags:
    """Verify flag parsing."""

    def test_dashboard_flag_in_content(self):
        """Script must handle --dashboard flag."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "--dashboard" in content
        assert "START_DASHBOARD" in content

    def test_env_var_defaults(self):
        """Script must have default ports."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "8000" in content  # Default API port
        assert "8501" in content  # Default Streamlit port


if __name__ == "__main__":
    unittest.main()
