"""Tests for scripts.collaboration.secret_patterns.

Covers SECRET_PATTERNS, SQL_INJECTION_PATTERNS constants and
is_sensitive(), find_secrets(), mask_secrets() functions.
"""

from __future__ import annotations

import re

from scripts.collaboration.secret_patterns import (
    _SENSITIVE_QUICK_CHECK,
    SECRET_PATTERNS,
    SQL_INJECTION_PATTERNS,
    find_secrets,
    is_sensitive,
    mask_secrets,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_secret_patterns_is_tuple(self):
        assert isinstance(SECRET_PATTERNS, tuple)
        assert len(SECRET_PATTERNS) == 10

    def test_secret_patterns_entries_are_name_pattern_pairs(self):
        for entry in SECRET_PATTERNS:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            name, pattern = entry
            assert isinstance(name, str)
            assert isinstance(pattern, re.Pattern)

    def test_sql_injection_patterns_is_tuple(self):
        assert isinstance(SQL_INJECTION_PATTERNS, tuple)
        assert len(SQL_INJECTION_PATTERNS) == 4

    def test_sensitive_quick_check_is_compiled(self):
        assert isinstance(_SENSITIVE_QUICK_CHECK, re.Pattern)

    def test_known_pattern_names(self):
        names = {name for name, _ in SECRET_PATTERNS}
        expected = {
            "openai_api_key",
            "github_token",
            "aws_access_key",
            "aws_secret_key",
            "generic_api_key",
            "password",
            "secret",
            "bearer_token",
            "private_key",
            "connection_string",
        }
        assert names == expected


# ---------------------------------------------------------------------------
# is_sensitive
# ---------------------------------------------------------------------------


class TestIsSensitive:
    def test_openai_key_detected(self):
        assert is_sensitive("api_key=sk-abcdefghijklmnopqrstuvwxyz1234567890") is True

    def test_github_token_detected(self):
        assert is_sensitive("token=ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD") is True

    def test_aws_access_key_detected(self):
        assert is_sensitive("AKIAIOSFODNN7EXAMPLE") is True

    def test_password_detected(self):
        assert is_sensitive("password=secret123") is True

    def test_passwd_detected(self):
        assert is_sensitive("passwd: mypass") is True

    def test_pwd_detected(self):
        assert is_sensitive("pwd=mypassword") is True

    def test_secret_keyword_detected(self):
        assert is_sensitive("secret: mysecretvalue123") is True

    def test_token_keyword_detected(self):
        assert is_sensitive("token: mytokenvalue12345") is True

    def test_api_key_keyword_detected(self):
        assert is_sensitive("api_key: myapikey12345678") is True

    def test_private_key_detected(self):
        text = "-----BEGIN RSA PRIVATE KEY-----"
        assert is_sensitive(text) is True

    def test_clean_text_not_sensitive(self):
        assert is_sensitive("This is a normal text without secrets") is False

    def test_empty_string_not_sensitive(self):
        assert is_sensitive("") is False

    def test_case_insensitive_password(self):
        assert is_sensitive("PASSWORD=mypass1234") is True

    def test_case_insensitive_secret(self):
        assert is_sensitive("SECRET=mysecret12345678") is True


# ---------------------------------------------------------------------------
# find_secrets
# ---------------------------------------------------------------------------


class TestFindSecrets:
    def test_no_secrets_returns_empty(self):
        assert find_secrets("clean text") == []

    def test_finds_openai_key(self):
        text = "key=sk-abcdefghijklmnopqrstuvwxyz1234567890"
        results = find_secrets(text)
        names = [name for name, _ in results]
        assert "openai_api_key" in names

    def test_finds_multiple_secrets(self):
        text = (
            "openai: sk-abcdefghijklmnopqrstuvwxyz1234567890 "
            "github: ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
        )
        results = find_secrets(text)
        assert len(results) >= 2

    def test_returns_name_and_matched_value(self):
        text = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        results = find_secrets(text)
        assert len(results) == 1
        name, value = results[0]
        assert name == "openai_api_key"
        assert value.startswith("sk-")

    def test_finds_password(self):
        text = "password=mypassword123"
        results = find_secrets(text)
        names = [name for name, _ in results]
        assert "password" in names

    def test_finds_bearer_token(self):
        text = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890"
        results = find_secrets(text)
        names = [name for name, _ in results]
        assert "bearer_token" in names

    def test_finds_connection_string(self):
        text = "mongodb://user:pass@localhost:27017/db"
        results = find_secrets(text)
        names = [name for name, _ in results]
        assert "connection_string" in names

    def test_finds_private_key_block(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
        results = find_secrets(text)
        names = [name for name, _ in results]
        assert "private_key" in names

    def test_finds_aws_secret_key(self):
        text = "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        results = find_secrets(text)
        names = [name for name, _ in results]
        assert "aws_secret_key" in names

    def test_empty_string(self):
        assert find_secrets("") == []


# ---------------------------------------------------------------------------
# mask_secrets
# ---------------------------------------------------------------------------


class TestMaskSecrets:
    def test_no_secrets_returns_unchanged(self):
        text = "clean text nothing to mask"
        assert mask_secrets(text) == text

    def test_masks_openai_key(self):
        text = "key=sk-abcdefghijklmnopqrstuvwxyz1234567890"
        masked = mask_secrets(text)
        assert "sk-" not in masked
        assert "*" in masked

    def test_masks_multiple_secrets(self):
        text = (
            "openai: sk-abcdefghijklmnopqrstuvwxyz1234567890 "
            "github: ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
        )
        masked = mask_secrets(text)
        assert "sk-" not in masked
        assert "ghp_" not in masked

    def test_custom_mask_char(self):
        text = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        masked = mask_secrets(text, mask_char="X")
        assert "sk-" not in masked
        assert "X" in masked

    def test_preserves_non_secret_text(self):
        text = "The key is sk-abcdefghijklmnopqrstuvwxyz1234567890 and that's it"
        masked = mask_secrets(text)
        assert "The key is" in masked
        assert "and that's it" in masked
        assert "sk-" not in masked

    def test_mask_length_matches_secret_length(self):
        text = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        original_secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        masked = mask_secrets(text)
        # The masked portion should be all asterisks of the same length
        assert "*" * len(original_secret) in masked

    def test_empty_string(self):
        assert mask_secrets("") == ""

    def test_masks_password(self):
        text = "password=mypassword123"
        masked = mask_secrets(text)
        assert "mypassword123" not in masked
