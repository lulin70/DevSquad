"""Test Case 011: SecurityFeatureChecker Edge Cases"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate.detectors.security_feature_checker import SecurityFeatureChecker


class TestSecurityFeatureEdgeCases:
    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def checker(self):
        return SecurityFeatureChecker()

    def test_syntax_error(self, checker, temp_dir):
        code = temp_dir / "broken.py"
        code.write_text("def bad(\n")
        result = checker.check([code])
        assert "security_score" in result

    def test_empty_file(self, checker, temp_dir):
        code = temp_dir / "empty.py"
        code.write_text("")
        result = checker.check([code])
        assert result["security_score"] >= 0.0
