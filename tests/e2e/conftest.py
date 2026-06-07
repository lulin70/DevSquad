# conftest.py for E2E tests
# Shared fixtures for all user journey and integration tests

import pytest
import subprocess
import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class E2ETestResult:
    """E2E test result with detailed metrics"""
    scenario: str
    passed: bool
    duration_ms: float
    steps_executed: int
    steps_total: int
    error_message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class E2ETestRunner:
    """
    E2E Test Runner - Simulates real user interactions
    
    Features:
    - CLI command execution
    - API server interaction
    - File system operations
    - Environment setup/teardown
    - Result collection and reporting
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root or Path(__file__).parent.parent.parent)
        self.results: List[E2ETestResult] = []
        self.temp_dirs: List[Path] = []
        self.start_time: float = 0
        self.test_env: Optional[Dict[str, str]] = None

    def setup_test_environment(self) -> Dict[str, str]:
        """Setup isolated test environment"""
        env = os.environ.copy()
        
        # Ensure we're using project's Python
        env["PYTHONPATH"] = str(self.project_root)
        env["PYTHONUNBUFFERED"] = "1"
        env["DEVSQUAD_LLM_BACKEND"] = "mock"  # Use mock for E2E tests
        env["DEVSQUAD_LOG_LEVEL"] = "DEBUG"
        
        # Disable color output for parsing
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"
        
        self.test_env = env
        return env

    def run_cli_command(
        self,
        args: List[str],
        timeout: int = 30,
        expect_success: bool = True,
        working_dir: Optional[str] = None
    ) -> subprocess.CompletedProcess:
        """Run a CLI command and return result"""
        cli_script = self.project_root / "scripts" / "cli.py"
        cmd = [sys.executable, str(cli_script)] + args
        
        result = subprocess.run(
            cmd,
            cwd=working_dir or str(self.project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self.test_env or self.setup_test_environment()
        )
        
        if expect_success and result.returncode != 0:
            raise AssertionError(
                f"CLI command failed: {' '.join(args)}\n"
                f"Exit code: {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )
        
        return result

    def run_python_script(
        self,
        script: str,
        timeout: int = 30
    ) -> subprocess.CompletedProcess:
        """Run a Python script in project context"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self.test_env or self.setup_test_environment()
        )
        return result

    def create_temp_dir(self, prefix: str = "devsquad_e2e_") -> Path:
        """Create temporary directory for test isolation"""
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        self.temp_dirs.append(temp_dir)
        return temp_dir

    def cleanup(self):
        """Cleanup all temporary resources"""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        self.temp_dirs.clear()

    def measure_time(self) -> float:
        """Get elapsed time since start"""
        if self.start_time == 0:
            return 0
        return (time.time() - self.start_time) * 1000


@pytest.fixture(scope="session")
def e2e_runner():
    """Create E2E test runner for entire session"""
    runner = E2ETestRunner()
    runner.start_time = time.time()
    yield runner
    runner.cleanup()


@pytest.fixture
def temp_project_dir(e2e_runner: E2ETestRunner):
    """Create isolated temporary project directory"""
    temp_dir = e2e_runner.create_temp_dir()
    yield temp_dir


# Utility functions for assertions
def assert_output_contains(output: str, *expected_strings: str):
    """Assert that output contains all expected strings"""
    for expected in expected_strings:
        assert expected in output, (
            f"Expected to find '{expected}' in output.\n"
            f"Actual output:\n{output[:500]}..."
        )


def assert_json_output_valid(output: str):
    """Assert that output is valid JSON"""
    import json
    try:
        data = json.loads(output)
        assert isinstance(data, dict), "Output should be a JSON object"
        return data
    except json.JSONDecodeError as e:
        raise AssertionError(f"Output is not valid JSON: {e}\nOutput:\n{output[:200]}")


def measure_performance(operation, *args, **kwargs) -> Dict[str, Any]:
    """Measure performance of an operation"""
    start = time.time()
    result = operation(*args, **kwargs)
    duration_ms = (time.time() - start) * 1000
    
    return {
        "duration_ms": round(duration_ms, 2),
        "success": result is not None,
        "result": result
    }
