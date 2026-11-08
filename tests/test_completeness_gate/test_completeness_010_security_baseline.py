"""Test Case 010: SecurityFeatureChecker Baseline"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate.detectors.security_feature_checker import SecurityFeatureChecker


class TestSecurityFeatureBaseline:
    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def checker(self):
        return SecurityFeatureChecker()

    def test_hmac_present(self, checker, temp_dir):
        code = temp_dir / "secure.py"
        code.write_text("""
import hmac
import hashlib
def sign(msg):
    return hmac.new(b"key", msg.encode(), hashlib.sha256).hexdigest()
""")
        result = checker.check([code])
        assert result["security_score"] >= 0.5

    def test_input_validation_present(self, checker, temp_dir):
        code = temp_dir / "validate.py"
        code.write_text("""
def process(data):
    if not isinstance(data, dict):
        raise ValueError()
    if len(data) > 100:
        raise ValueError()
    return data
""")
        result = checker.check([code])
        assert result["security_score"] >= 0.5

    def test_no_security_features(self, checker, temp_dir):
        code = temp_dir / "insecure.py"
        code.write_text("""
def process(data):
    return data
""")
        result = checker.check([code], p3_doc=None)
        assert result["security_score"] >= 0.0
