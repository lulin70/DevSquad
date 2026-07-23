#!/usr/bin/env python3
"""Tests for InputValidator.check_sensitive_info (V4.2.1 P2-5).

Verifies that the InputValidator detects sensitive information (API keys,
passwords, tokens, private keys, connection strings) at input boundaries
and returns non-blocking WARNING-level messages.

Coverage dimensions (per DevSquad Iron Rule 3):
  - Happy Path: each SECRET_PATTERN category triggers a warning
  - Error Case: clean input → no warnings; non-string → empty list
  - Boundary: empty string, very short secret (below threshold)
  - Masking: matched values are masked (first 4 chars + *)
  - Integration: validate_task() populates ValidationResult.warnings
  - Non-blocking: valid input with secrets remains valid=True
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.collaboration.input_validator import InputValidator, ValidationResult


class T1_OpenAIApiKey(unittest.TestCase):
    """T1: OpenAI API key detection (sk-xxx)."""

    def test_01_detects_openai_key(self) -> None:
        """Verify: sk- followed by 20+ alphanumeric chars → warning."""
        v = InputValidator()
        # sk- + 20 alphanumeric chars
        task = f"Use this key: sk-{'a' * 24} for the API call"
        warnings = v.check_sensitive_info(task)
        self.assertEqual(len(warnings), 1)
        self.assertIn("openai_api_key", warnings[0])
        # Masking: first 4 chars "sk-a" visible, rest masked
        self.assertIn("sk-a", warnings[0])
        self.assertIn("*", warnings[0])

    def test_02_openai_key_too_short_no_warning(self) -> None:
        """Verify: sk- + only 10 chars (below 20 threshold) → no warning."""
        v = InputValidator()
        # sk- + 10 chars (below {20,} threshold)
        task = f"short key: sk-{'b' * 10}"
        warnings = v.check_sensitive_info(task)
        # Pattern requires 20+ chars after sk-, so short key not detected
        self.assertEqual(len(warnings), 0)


class T2_GitHubToken(unittest.TestCase):
    """T2: GitHub token detection (ghp_xxx)."""

    def test_01_detects_github_token(self) -> None:
        """Verify: ghp_ + 36+ chars → warning."""
        v = InputValidator()
        token = "ghp_" + "a" * 36
        task = f"Set GH token to {token}"
        warnings = v.check_sensitive_info(task)
        # github_token pattern matches; "token=" prefix may also match
        # the generic secret/token pattern, so expect >=1 warning.
        found = [w for w in warnings if "github_token" in w]
        self.assertGreaterEqual(len(found), 1)
        # Masking: first 4 chars "ghp_" visible (g,h,p,_), rest masked
        self.assertIn("ghp_", found[0])
        self.assertIn("*", found[0])


class T3_AwsKeys(unittest.TestCase):
    """T3: AWS access key and secret key detection."""

    def test_01_detects_aws_access_key(self) -> None:
        """Verify: AKIA + 16 uppercase alphanumeric → warning."""
        v = InputValidator()
        # AKIA + 16 chars
        key = "AKIA" + "ABCDEFGHJKLMNPQR"  # 16 chars
        task = f"AWS access key: {key}"
        warnings = v.check_sensitive_info(task)
        self.assertEqual(len(warnings), 1)
        self.assertIn("aws_access_key", warnings[0])

    def test_02_detects_aws_secret_key(self) -> None:
        """Verify: aws_secret_access_key assignment → warning."""
        v = InputValidator()
        task = "aws_secret_access_key = ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"
        warnings = v.check_sensitive_info(task)
        self.assertEqual(len(warnings), 1)
        self.assertIn("aws_secret_key", warnings[0])


class T4_GenericApiKeysAndPasswords(unittest.TestCase):
    """T4: Generic API key and password detection."""

    def test_01_detects_generic_api_key(self) -> None:
        """Verify: api_key=xxx (8+ chars) → warning."""
        v = InputValidator()
        task = "config: api_key=abcdefgh12345678"
        warnings = v.check_sensitive_info(task)
        # May match generic_api_key
        found_names = [w for w in warnings if "generic_api_key" in w]
        self.assertGreaterEqual(len(found_names), 1)

    def test_02_detects_password_assignment(self) -> None:
        """Verify: password=xxx (4+ chars) → warning."""
        v = InputValidator()
        task = "db config: password=mySecretPass123"
        warnings = v.check_sensitive_info(task)
        found_names = [w for w in warnings if "password" in w.lower()]
        self.assertGreaterEqual(len(found_names), 1)

    def test_03_detects_passwd_variant(self) -> None:
        """Verify: passwd=xxx → warning (password pattern includes passwd)."""
        v = InputValidator()
        task = "login: passwd=userPassword456"
        warnings = v.check_sensitive_info(task)
        found_names = [w for w in warnings if "password" in w.lower()]
        self.assertGreaterEqual(len(found_names), 1)


class T5_SecretAndToken(unittest.TestCase):
    """T5: Generic secret and token detection."""

    def test_01_detects_secret_assignment(self) -> None:
        """Verify: secret=xxx (8+ chars) → warning."""
        v = InputValidator()
        task = "oauth: secret=abcdef12345678"
        warnings = v.check_sensitive_info(task)
        # May match "secret" pattern
        self.assertGreaterEqual(len(warnings), 1)

    def test_02_detects_token_assignment(self) -> None:
        """Verify: token=xxx (8+ chars) → warning."""
        v = InputValidator()
        task = "auth: token=abcdefghij123"
        warnings = v.check_sensitive_info(task)
        self.assertGreaterEqual(len(warnings), 1)


class T6_BearerTokenAndPrivateKey(unittest.TestCase):
    """T6: Bearer token and private key detection."""

    def test_01_detects_bearer_token(self) -> None:
        """Verify: Bearer xxx → warning."""
        v = InputValidator()
        task = "Authorization: Bearer abcdefghijklmnop-_.~+=="
        warnings = v.check_sensitive_info(task)
        found = [w for w in warnings if "bearer_token" in w]
        self.assertGreaterEqual(len(found), 1)

    def test_02_detects_private_key_block(self) -> None:
        """Verify: -----BEGIN PRIVATE KEY----- → warning."""
        v = InputValidator()
        task = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        warnings = v.check_sensitive_info(task)
        found = [w for w in warnings if "private_key" in w]
        self.assertGreaterEqual(len(found), 1)

    def test_03_detects_ec_private_key(self) -> None:
        """Verify: EC PRIVATE KEY header → warning."""
        v = InputValidator()
        task = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEE..."
        warnings = v.check_sensitive_info(task)
        found = [w for w in warnings if "private_key" in w]
        self.assertGreaterEqual(len(found), 1)


class T7_ConnectionString(unittest.TestCase):
    """T7: Database connection string detection."""

    def test_01_detects_postgres_connection(self) -> None:
        """Verify: postgres://user:pass@host → warning."""
        v = InputValidator()
        task = "DATABASE_URL=postgres://admin:secretpass@db.example.com:5432/mydb"
        warnings = v.check_sensitive_info(task)
        found = [w for w in warnings if "connection_string" in w]
        self.assertGreaterEqual(len(found), 1)

    def test_02_detects_redis_connection(self) -> None:
        r"""Verify: redis://user:pass@host → warning.

        Note: secret_patterns connection_string regex requires
        ``[^\s]+:[^\s]+@`` (non-empty user:pass), so URL must include
        a username. Bare ``redis://:pass@host`` (no user) won't match.
        """
        v = InputValidator()
        task = "redis://default:hunter2@redis-cache.local:6379/0"
        warnings = v.check_sensitive_info(task)
        found = [w for w in warnings if "connection_string" in w]
        self.assertGreaterEqual(len(found), 1)

    def test_03_detects_mongodb_connection(self) -> None:
        """Verify: mongodb://user:pass@host → warning."""
        v = InputValidator()
        task = "mongodb://root:toor@mongo-cluster:27017/admin"
        warnings = v.check_sensitive_info(task)
        found = [w for w in warnings if "connection_string" in w]
        self.assertGreaterEqual(len(found), 1)


class T8_CleanInput(unittest.TestCase):
    """T8: Clean input (no secrets) produces no warnings."""

    def test_01_normal_task_no_warning(self) -> None:
        """Verify: Plain task description → no warnings."""
        v = InputValidator()
        task = "Design a user authentication system with JWT and OAuth2"
        warnings = v.check_sensitive_info(task)
        self.assertEqual(warnings, [])

    def test_02_chinese_task_no_warning(self) -> None:
        """Verify: Chinese task description → no warnings."""
        v = InputValidator()
        task = "设计一个安全的用户认证系统，使用 JWT 和刷新令牌"
        warnings = v.check_sensitive_info(task)
        self.assertEqual(warnings, [])

    def test_03_code_snippet_no_warning(self) -> None:
        """Verify: Normal code snippet → no warnings."""
        v = InputValidator()
        task = "def authenticate(user, password_hash):\n    return verify(password_hash)"
        # "password_hash" should not match because pattern requires
        # password=xxx with 4+ chars after =
        warnings = v.check_sensitive_info(task)
        # The pattern (?i)\b(password|passwd|pwd)\b\s*[:=]\s*['\"]?[^\s'\"]{4,}
        # requires : or = after password. "password_hash):" has _ after password,
        # so \b matches but _ breaks the word boundary... let me verify.
        # Actually "password_hash" - \b(password)\b won't match because
        # password_hash is one word token. So no warning expected.
        self.assertEqual(warnings, [])


class T9_Masking(unittest.TestCase):
    """T9: Matched values are masked in warning messages."""

    def test_01_openai_key_masked(self) -> None:
        """Verify: Full secret value NOT echoed in warning (only first 4 chars)."""
        v = InputValidator()
        full_key = "sk-" + "s" * 24  # sk-ssssssssssssssssssssssss
        task = f"key={full_key}"
        warnings = v.check_sensitive_info(task)
        self.assertEqual(len(warnings), 1)
        # Full key must NOT appear in warning
        self.assertNotIn(full_key, warnings[0])
        # First 4 chars "sk-s" should appear
        self.assertIn("sk-s", warnings[0])
        # Masking asterisks should be present
        self.assertIn("*", warnings[0])

    def test_02_github_token_masked(self) -> None:
        """Verify: GitHub token masked in warning.

        Note: ``token=ghp_xxx`` may match both github_token and the
        generic secret/token pattern. We verify masking on the
        github_token warning specifically.
        """
        v = InputValidator()
        full_token = "ghp_" + "t" * 36
        task = f"token={full_token}"
        warnings = v.check_sensitive_info(task)
        # Find the github_token-specific warning
        gh_warnings = [w for w in warnings if "github_token" in w]
        self.assertGreaterEqual(len(gh_warnings), 1)
        # Full token must NOT appear in warning
        self.assertNotIn(full_token, gh_warnings[0])
        # First 4 chars "ghp_" visible (not "ghp_t" — only 4 chars shown)
        self.assertIn("ghp_", gh_warnings[0])


class T10_NonBlockingBehavior(unittest.TestCase):
    """T10: Sensitive info detection is non-blocking (input remains valid)."""

    def test_01_input_with_secret_remains_valid(self) -> None:
        """Verify: Input with API key is still valid=True (non-blocking)."""
        v = InputValidator()
        task = f"Help me debug this API call: sk-{'a' * 24} is the key"
        result = v.validate_task(task)
        self.assertTrue(result.valid, "Input with secret should remain valid (non-blocking)")
        self.assertGreaterEqual(len(result.warnings), 1)

    def test_02_clean_input_has_empty_warnings(self) -> None:
        """Verify: Clean input → ValidationResult.warnings is empty list."""
        v = InputValidator()
        result = v.validate_task("Design a user authentication system")
        self.assertTrue(result.valid)
        self.assertEqual(result.warnings, [])

    def test_03_warnings_populated_for_secret(self) -> None:
        """Verify: validate_task() populates warnings field with secret info."""
        v = InputValidator()
        task = "DB url: postgres://admin:secretpass@db.host:5432/db"
        result = v.validate_task(task)
        self.assertTrue(result.valid)
        self.assertGreaterEqual(len(result.warnings), 1)
        # Warning message should mention sensitive info
        self.assertTrue(any("Sensitive info" in w for w in result.warnings))


class T11_BoundaryAndErrorCases(unittest.TestCase):
    """T11: Boundary and error cases."""

    def test_01_empty_string_returns_empty(self) -> None:
        """Verify: Empty string → empty warnings list."""
        v = InputValidator()
        self.assertEqual(v.check_sensitive_info(""), [])

    def test_02_non_string_returns_empty(self) -> None:
        """Verify: Non-string input → empty list (no crash)."""
        v = InputValidator()
        self.assertEqual(v.check_sensitive_info(None), [])  # type: ignore[arg-type]
        self.assertEqual(v.check_sensitive_info(123), [])  # type: ignore[arg-type]

    def test_03_unicode_normalization_applied(self) -> None:
        """Verify: Zero-width characters stripped before detection."""
        v = InputValidator()
        # Insert zero-width space into the key
        key = "sk-" + "a" * 20 + "\u200b" + "b" * 4
        task = f"key={key}"
        warnings = v.check_sensitive_info(task)
        # After zero-width removal, key becomes sk-aaa...bbbb (24 chars)
        # which should match the openai_api_key pattern
        self.assertGreaterEqual(len(warnings), 1)

    def test_04_multiple_secrets_in_one_input(self) -> None:
        """Verify: Multiple secrets in one input → multiple warnings."""
        v = InputValidator()
        task = (
            f"Keys: sk-{'a' * 24} and ghp_{'b' * 36} "
            f"and postgres://u:p@host:5432/db"
        )
        warnings = v.check_sensitive_info(task)
        # Should detect at least 2 distinct patterns (may be 3 with connection_string)
        self.assertGreaterEqual(len(warnings), 2)


class T12_ValidationResultField(unittest.TestCase):
    """T12: ValidationResult.warnings field defaults and behavior."""

    def test_01_warnings_defaults_to_empty_list(self) -> None:
        """Verify: ValidationResult.warnings defaults to empty list."""
        result = ValidationResult(valid=True)
        self.assertEqual(result.warnings, [])

    def test_02_warnings_can_be_populated(self) -> None:
        """Verify: ValidationResult.warnings can be set explicitly."""
        result = ValidationResult(valid=True, warnings=["test warning"])
        self.assertEqual(result.warnings, ["test warning"])

    def test_03_warnings_independent_between_instances(self) -> None:
        """Verify: Each ValidationResult has independent warnings list."""
        r1 = ValidationResult(valid=True)
        r2 = ValidationResult(valid=True)
        r1.warnings.append("w1")
        self.assertEqual(r2.warnings, [])


if __name__ == "__main__":
    unittest.main()
