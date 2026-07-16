#!/usr/bin/env python3
"""V4.1.0 P1-7 handoff — sensitive info redaction + suggested skills.

Tests for ``CheckpointManager._redact_sensitive_info`` and
``CheckpointManager.suggest_skills`` added as part of V4.1.0 Matt Pocock
handoff principle. Also verifies that ``save_handoff`` applies redaction to
the Markdown output.

Acceptance criteria (PRD §3.1 P1-7): >=12 tests covering API key / token /
password / email redaction, mixed content, case-insensitivity, empty input,
and all suggest_skills keyword branches.
"""

from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.checkpoint_manager import CheckpointManager, HandoffDocument

# ======================================================================
# P1-7: _redact_sensitive_info
# ======================================================================


class TestRedactSensitiveInfo(unittest.TestCase):
    """Redaction of API keys, tokens, passwords, and emails."""

    def test_redact_api_key_sk_prefix(self) -> None:
        """Verify: sk-xxx style API keys are replaced with [REDACTED]."""
        text = "Use the key sk-abc123XYZ for authentication."
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("sk-abc123XYZ", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redact_api_key_key_value_pair(self) -> None:
        """Verify: api_key: <value> is masked, keeping the key name."""
        text = "Config: api_key: secret_live_key_999"
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("secret_live_key_999", redacted)
        self.assertIn("api_key: [REDACTED]", redacted)

    def test_redact_token_key_value_pair(self) -> None:
        """Verify: token: <value> is masked."""
        text = "Headers: token: bearer_eyJhbGciOiJIUzI1"
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("bearer_eyJhbGciOiJIUzI1", redacted)
        self.assertIn("token: [REDACTED]", redacted)

    def test_redact_password(self) -> None:
        """Verify: password: <value> is masked."""
        text = "DB config: password: hunter2pass"
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("hunter2pass", redacted)
        self.assertIn("password: [REDACTED]", redacted)

    def test_redact_passwd(self) -> None:
        """Verify: passwd: <value> is masked (preserving 'passwd' label)."""
        text = "passwd: p@ssw0rd!"
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("p@ssw0rd!", redacted)
        self.assertIn("passwd: [REDACTED]", redacted)

    def test_redact_email_preserves_domain(self) -> None:
        """Verify: email local-part is masked but domain is preserved."""
        text = "Contact: alice@company.com for details."
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("alice@company.com", redacted)
        self.assertIn("***@company.com", redacted)

    def test_no_sensitive_info_returns_unchanged(self) -> None:
        """Verify: text without secrets is returned verbatim."""
        text = "The architect completed the design review with no issues."
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertEqual(redacted, text)

    def test_multiple_sensitive_patterns_redacted_together(self) -> None:
        """Verify: multiple secret types in one string are all redacted."""
        text = (
            "Use sk-live_key_abc; api_key: kv_secret; "
            "token: tok_99; password: pw123; admin@admin.io"
        )
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("sk-live_key_abc", redacted)
        self.assertNotIn("kv_secret", redacted)
        self.assertNotIn("tok_99", redacted)
        self.assertNotIn("pw123", redacted)
        self.assertNotIn("admin@admin.io", redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("***@admin.io", redacted)

    def test_case_insensitive_api_key(self) -> None:
        """Verify: API_KEY and Api-Key are matched case-insensitively."""
        text = "API_KEY: secret_one and Api-Key: secret_two"
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("secret_one", redacted)
        self.assertNotIn("secret_two", redacted)
        self.assertEqual(redacted.count("[REDACTED]"), 2)

    def test_case_insensitive_password(self) -> None:
        """Verify: PASSWORD and Password are matched case-insensitively."""
        text = "PASSWORD: pw_one and Password: pw_two"
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("pw_one", redacted)
        self.assertNotIn("pw_two", redacted)
        self.assertEqual(redacted.count("[REDACTED]"), 2)

    def test_empty_string_returns_empty(self) -> None:
        """Verify: empty string input returns empty string."""
        self.assertEqual(CheckpointManager._redact_sensitive_info(""), "")

    def test_api_key_with_equals_sign(self) -> None:
        """Verify: api_key=<value> (equals separator) is also redacted."""
        text = "api_key=sk_equals_form"
        redacted = CheckpointManager._redact_sensitive_info(text)
        self.assertNotIn("sk_equals_form", redacted)
        self.assertIn("[REDACTED]", redacted)


# ======================================================================
# P1-7: suggest_skills
# ======================================================================


class TestSuggestSkills(unittest.TestCase):
    """Skill recommendation based on handoff content keywords."""

    def setUp(self) -> None:
        self._tmp = Path(__file__).parent / ".tmp_suggest_skills"
        self._tmp.mkdir(exist_ok=True)
        self.manager = CheckpointManager(storage_path=str(self._tmp))

    def tearDown(self) -> None:
        for sub in ("checkpoints", "handoffs", "lifecycle"):
            target = self._tmp / sub
            if target.exists():
                shutil.rmtree(target)
        if self._tmp.exists():
            self._tmp.rmdir()

    def test_suggest_test_keyword_chinese(self) -> None:
        """Verify: '测试' keyword → ['test', 'retrospective']."""
        result = self.manager.suggest_skills("下一步需要完成测试任务")
        self.assertEqual(result, ["test", "retrospective"])

    def test_suggest_test_keyword_english(self) -> None:
        """Verify: 'test' keyword → ['test', 'retrospective']."""
        result = self.manager.suggest_skills("Run the test suite next")
        self.assertEqual(result, ["test", "retrospective"])

    def test_suggest_deploy_keyword(self) -> None:
        """Verify: '部署'/'deploy' keyword → ['devops']."""
        self.assertEqual(self.manager.suggest_skills("准备部署到生产环境"), ["devops"])
        self.assertEqual(self.manager.suggest_skills("Ready to deploy"), ["devops"])

    def test_suggest_security_keyword(self) -> None:
        """Verify: '安全'/'security' keyword → ['security']."""
        self.assertEqual(self.manager.suggest_skills("进行安全审计"), ["security"])
        self.assertEqual(self.manager.suggest_skills("Run security scan"), ["security"])

    def test_suggest_design_keyword(self) -> None:
        """Verify: '设计'/'design' keyword → ['dispatch', 'intent']."""
        self.assertEqual(self.manager.suggest_skills("重新设计架构"), ["dispatch", "intent"])
        self.assertEqual(self.manager.suggest_skills("Design the API"), ["dispatch", "intent"])

    def test_suggest_default_when_no_keyword(self) -> None:
        """Verify: no keyword match → ['dispatch']."""
        result = self.manager.suggest_skills("Code review completed, merge the PR.")
        self.assertEqual(result, ["dispatch"])

    def test_suggest_skills_empty_string(self) -> None:
        """Verify: empty handoff content → ['dispatch']."""
        self.assertEqual(self.manager.suggest_skills(""), ["dispatch"])

    def test_suggest_skills_case_insensitive_english(self) -> None:
        """Verify: English keywords match regardless of case."""
        self.assertEqual(self.manager.suggest_skills("DEPLOY NOW"), ["devops"])
        self.assertEqual(self.manager.suggest_skills("Security Review"), ["security"])


# ======================================================================
# P1-7: save_handoff integration — markdown is redacted
# ======================================================================


class TestSaveHandoffRedaction(unittest.TestCase):
    """Integration: save_handoff writes redacted markdown but preserves JSON."""

    def setUp(self) -> None:
        self._tmp = Path(__file__).parent / ".tmp_handoff_redact"
        self._tmp.mkdir(exist_ok=True)
        self.manager = CheckpointManager(storage_path=str(self._tmp))

    def tearDown(self) -> None:
        for sub in ("checkpoints", "handoffs", "lifecycle"):
            target = self._tmp / sub
            if target.exists():
                shutil.rmtree(target)
        if self._tmp.exists():
            self._tmp.rmdir()

    def test_markdown_file_contains_redacted_secrets(self) -> None:
        """Verify: the .md file has secrets masked."""
        handoff = HandoffDocument(
            task_id="task-redact",
            from_agent="coder",
            to_agent="devops",
            completed_work=["Deployed with api_key: super_secret_123"],
            next_steps=["Run sk-prod-key-abc checks"],
        )
        self.assertTrue(self.manager.save_handoff(handoff))

        md_path = self.manager.handoffs_dir / f"{handoff.handoff_id}.md"
        md_content = md_path.read_text(encoding="utf-8")
        self.assertNotIn("super_secret_123", md_content)
        self.assertNotIn("sk-prod-key-abc", md_content)
        self.assertIn("[REDACTED]", md_content)

    def test_json_file_preserves_original_values(self) -> None:
        """Verify: the .json file keeps original values for machine use."""
        handoff = HandoffDocument(
            task_id="task-keep",
            from_agent="coder",
            to_agent="devops",
            completed_work=["Config api_key: original_value_456"],
        )
        self.assertTrue(self.manager.save_handoff(handoff))

        json_path = self.manager.handoffs_dir / f"{handoff.handoff_id}.json"
        json_content = json_path.read_text(encoding="utf-8")
        self.assertIn("original_value_456", json_content)


if __name__ == "__main__":
    unittest.main()
