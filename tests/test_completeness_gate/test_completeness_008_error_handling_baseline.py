"""Test Case 008: ErrorHandlingChecker Baseline

Tests that ErrorHandlingChecker can detect risky operations and verify
if they are protected by try-except blocks.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from scripts.collaboration.gates.completeness_gate.detectors.error_handling_checker import ErrorHandlingChecker


class TestErrorHandlingBaseline:
    """Test error handling checking baseline functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)
    
    @pytest.fixture
    def checker(self):
        """Create ErrorHandlingChecker instance."""
        return ErrorHandlingChecker()
    
    def test_all_protected(self, checker, temp_dir):
        """Test code where all risky operations are protected."""
        code_file = temp_dir / "safe_api.py"
        code_file.write_text("""
import requests

def fetch_data(url):
    try:
        response = requests.get(url)
        return response.json()
    except requests.RequestException:
        return None

def read_config():
    try:
        with open('config.txt', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return ""
""")
        
        result = checker.check([code_file])
        
        assert result["error_handling_score"] == 1.0
        assert len(result["unprotected_operations"]) == 0
    
    def test_unprotected_requests(self, checker, temp_dir):
        """Test detection of unprotected requests call."""
        code_file = temp_dir / "unsafe_api.py"
        code_file.write_text("""
import requests

def get_data():
    response = requests.get("https://api.example.com")
    return response.json()
""")
        
        result = checker.check([code_file])
        
        assert result["error_handling_score"] < 1.0
        assert len(result["unprotected_operations"]) >= 1
        assert any("requests.get" in op["operation"] for op in result["unprotected_operations"])
    
    def test_unprotected_file_open(self, checker, temp_dir):
        """Test detection of unprotected file operations."""
        code_file = temp_dir / "file_ops.py"
        code_file.write_text("""
def read_file(path):
    with open(path, 'r') as f:
        return f.read()
""")
        
        result = checker.check([code_file])
        
        assert result["error_handling_score"] < 1.0
        violations = result["unprotected_operations"]
        assert len(violations) >= 1
        assert any("open" in op["operation"] for op in violations)
    
    def test_unprotected_subprocess(self, checker, temp_dir):
        """Test detection of unprotected subprocess call."""
        code_file = temp_dir / "runner.py"
        code_file.write_text("""
import subprocess

def run_command(cmd):
    result = subprocess.run(cmd, shell=True)
    return result.returncode
""")
        
        result = checker.check([code_file])
        
        assert result["error_handling_score"] < 1.0
        assert any("subprocess.run" in op["operation"] for op in result["unprotected_operations"])
    
    def test_mixed_protection(self, checker, temp_dir):
        """Test code with mixed protected and unprotected operations."""
        code_file = temp_dir / "mixed.py"
        code_file.write_text("""
import requests

def safe_fetch():
    try:
        return requests.get("https://api.com").json()
    except:
        return {}

def unsafe_fetch():
    return requests.post("https://api.com", data={}).json()
""")
        
        result = checker.check([code_file])
        
        # One protected, one unprotected = 0.5 score
        assert result["error_handling_score"] == pytest.approx(0.5, abs=0.1)
        assert len(result["unprotected_operations"]) == 1
    
    def test_no_risky_operations(self, checker, temp_dir):
        """Test code with no risky operations."""
        code_file = temp_dir / "clean.py"
        code_file.write_text("""
def add(a, b):
    return a + b

def process(data):
    return [x * 2 for x in data]
""")
        
        result = checker.check([code_file])
        
        assert result["error_handling_score"] == 1.0
        assert len(result["unprotected_operations"]) == 0
    
    def test_multiple_files(self, checker, temp_dir):
        """Test checking multiple files."""
        file1 = temp_dir / "safe.py"
        file1.write_text("""
def safe():
    try:
        with open('file.txt') as f:
            return f.read()
    except:
        return ""
""")
        
        file2 = temp_dir / "unsafe.py"
        file2.write_text("""
def unsafe():
    with open('other.txt') as f:
        return f.read()
""")
        
        result = checker.check([file1, file2])
        
        # 1 protected + 1 unprotected = 0.5
        assert result["error_handling_score"] == 0.5
        assert len(result["unprotected_operations"]) == 1
