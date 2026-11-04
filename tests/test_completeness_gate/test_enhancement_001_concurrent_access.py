"""Test Enhancement 001: Concurrent File Access Testing (AC-007)."""

import pytest
import tempfile
import threading
from pathlib import Path
from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate


def test_concurrent_gate_execution():
    """Test multiple S1 Gate instances on same files simultaneously.
    
    Acceptance Criteria: AC-007
    - Multiple S1 Gate instances access same files concurrently
    - No race conditions or file lock conflicts
    - All instances return consistent results
    """
    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "shared.py"
    test_file.write_text("def test(): pass", encoding="utf-8")
    
    results = []
    errors = []
    
    def run_gate():
        try:
            gate = ImplementationCompletenessGate()
            result = gate.check([test_file])
            results.append(result)
        except Exception as e:
            errors.append(str(e))
    
    # Run 5 concurrent gates
    threads = [threading.Thread(target=run_gate) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All should succeed without errors
    assert len(errors) == 0, f"Concurrent execution had errors: {errors}"
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"
    
    # All should return PASS verdict
    verdicts = [r["verdict"] for r in results]
    assert all(v == "PASS" for v in verdicts), f"Not all verdicts were PASS: {verdicts}"
    
    # All should have same completeness score
    scores = [r["completeness_score"] for r in results]
    assert all(abs(s - scores[0]) < 0.001 for s in scores), \
        f"Scores not consistent: {scores}"


def test_concurrent_gate_different_files():
    """Test concurrent gates on different files (isolation check)."""
    temp_dir = Path(tempfile.mkdtemp())
    
    results = []
    
    def run_gate_on_file(file_index):
        test_file = temp_dir / f"file_{file_index}.py"
        test_file.write_text(f"def func_{file_index}(): pass", encoding="utf-8")
        
        gate = ImplementationCompletenessGate()
        result = gate.check([test_file])
        results.append((file_index, result))
    
    # Run 10 concurrent gates on different files
    threads = [threading.Thread(target=run_gate_on_file, args=(i,)) 
               for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All should succeed
    assert len(results) == 10
    
    # Each should have unique file processed
    file_counts = {}
    for idx, result in results:
        files = result.get("files_analyzed", [])
        for f in files:
            file_counts[f] = file_counts.get(f, 0) + 1
    
    # Each file should be processed exactly once
    assert all(count == 1 for count in file_counts.values()), \
        f"File processing not isolated: {file_counts}"


def test_concurrent_gate_stress_test():
    """Stress test: 50 concurrent gate instances."""
    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "stress.py"
    test_file.write_text("def stress_test(): return True", encoding="utf-8")
    
    results = []
    
    def run_gate():
        gate = ImplementationCompletenessGate()
        result = gate.check([test_file])
        results.append(result["verdict"])
    
    # Run 50 concurrent gates
    threads = [threading.Thread(target=run_gate) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All should succeed
    assert len(results) == 50
    assert all(v == "PASS" for v in results)
