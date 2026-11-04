"""Test Enhancement 002: Large-Scale PR Performance Testing (AC-009)."""

import pytest
import time
import tempfile
from pathlib import Path
from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate


def test_large_scale_pr_1000_files():
    """Test S1 Gate performance on 1000+ files.
    
    Acceptance Criteria: AC-009
    - Process 1000+ Python files
    - Complete within 30 seconds
    - Return valid results
    """
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create 1000 Python files
    files = []
    for i in range(1000):
        f = temp_dir / f"module_{i:04d}.py"
        f.write_text(f"def func_{i}(): return {i}", encoding="utf-8")
        files.append(f)
    
    gate = ImplementationCompletenessGate()
    start = time.time()
    result = gate.check(files)
    elapsed = time.time() - start
    
    # Should complete within 30s
    assert elapsed < 30.0, f"Took {elapsed:.2f}s, expected <30s"
    
    # Should return valid results
    assert result["verdict"] in ["PASS", "WARNING", "REJECT"]
    assert "completeness_score" in result
    assert result["completeness_score"] >= 0.0


def test_large_scale_pr_2000_files():
    """Test S1 Gate on 2000 files (extended stress test)."""
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create 2000 Python files
    files = []
    for i in range(2000):
        f = temp_dir / f"large_{i:04d}.py"
        # Alternate between simple and complex functions
        if i % 2 == 0:
            content = f"def simple_{i}(): return {i}"
        else:
            content = f"""
def complex_{i}():
    try:
        return {i} * 2
    except Exception:
        return None
"""
        f.write_text(content, encoding="utf-8")
        files.append(f)
    
    gate = ImplementationCompletenessGate()
    start = time.time()
    result = gate.check(files)
    elapsed = time.time() - start
    
    # Should still complete in reasonable time (allow more for 2000 files)
    assert elapsed < 60.0, f"Took {elapsed:.2f}s, expected <60s for 2000 files"
    assert result["verdict"] in ["PASS", "WARNING", "REJECT"]


def test_large_scale_with_mock_patterns():
    """Test large-scale PR with some mock patterns mixed in."""
    temp_dir = Path(tempfile.mkdtemp())
    
    files = []
    # Create 1000 files: 950 clean, 50 with mocks
    for i in range(1000):
        f = temp_dir / f"mixed_{i:04d}.py"
        if i % 20 == 0:  # 5% with mocks
            content = """
from unittest.mock import Mock
def use_mock():
    mock_obj = Mock()
    return mock_obj.method()
"""
        else:
            content = f"def clean_{i}(): return {i}"
        f.write_text(content, encoding="utf-8")
        files.append(f)
    
    gate = ImplementationCompletenessGate()
    start = time.time()
    result = gate.check(files)
    elapsed = time.time() - start
    
    # Should complete within 30s
    assert elapsed < 30.0, f"Took {elapsed:.2f}s, expected <30s"
    
    # Should detect mock issues
    assert "details" in result
    assert "mock_score" in result["details"]
    assert result["details"]["mock_score"] < 1.0  # Should detect some mocks


def test_large_scale_empty_files():
    """Test large-scale PR with many empty files."""
    temp_dir = Path(tempfile.mkdtemp())
    
    files = []
    for i in range(1000):
        f = temp_dir / f"empty_{i:04d}.py"
        f.write_text("", encoding="utf-8")  # Empty file
        files.append(f)
    
    gate = ImplementationCompletenessGate()
    start = time.time()
    result = gate.check(files)
    elapsed = time.time() - start
    
    # Should complete quickly (empty files are fast to process)
    assert elapsed < 10.0, f"Took {elapsed:.2f}s, expected <10s for empty files"
    assert result["verdict"] == "PASS"  # No code means no issues


def test_performance_timing_breakdown():
    """Test and report timing breakdown for different file counts."""
    temp_dir = Path(tempfile.mkdtemp())
    
    timings = {}
    file_counts = [100, 500, 1000]
    
    for count in file_counts:
        files = []
        for i in range(count):
            f = temp_dir / f"perf_{count}_{i:04d}.py"
            f.write_text(f"def func_{i}(): return {i}", encoding="utf-8")
            files.append(f)
        
        gate = ImplementationCompletenessGate()
        start = time.time()
        result = gate.check(files)
        elapsed = time.time() - start
        
        timings[count] = elapsed
    
    # Verify all completed
    assert all(t > 0 for t in timings.values())
    
    # Verify scaling is sub-linear (with caching, should be better than O(n))
    # 1000 files should take less than 10x the time of 100 files
    if 100 in timings and 1000 in timings:
        ratio = timings[1000] / timings[100]
        assert ratio < 10.0, \
            f"Scaling too slow: 1000 files took {ratio:.2f}x longer than 100 files"
