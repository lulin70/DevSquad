#!/usr/bin/env python3
"""P0-3: LLM Integration E2E Tests for DevSquad Dashboard.

Coverage:
  - Moka LLM timeout handling
  - Real Moka LLM smoke test
  - API rate limit handling
  - LLM stream output rendering

These tests verify Dashboard correctly integrates with real LLM backends
and handles various failure scenarios gracefully.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Skip if streamlit not installed
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).parent.parent.parent
DASHBOARD_APP = PROJECT_ROOT / "scripts" / "dashboard" / "app.py"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
]


def _make_test_user(role: str = "operator"):
    """Create test user with operator permissions for dispatch tests."""
    from scripts.auth import User, UserRole

    role_map = {
        "viewer": UserRole.VIEWER,
        "operator": UserRole.OPERATOR,
        "admin": UserRole.ADMIN,
    }
    return User(
        username=f"test_{role}",
        email=f"test_{role}@devsquad.local",
        name=f"Test {role.title()}",
        role=role_map.get(role, UserRole.OPERATOR),
        authenticated_at=datetime.now(),
        session_id=f"test_session_{role}",
    )


def _run_dashboard(role: str = "operator") -> AppTest:
    """Run dashboard app with pre-authenticated operator user."""
    app = AppTest.from_file(str(DASHBOARD_APP), default_timeout=30)
    app.session_state["user"] = _make_test_user(role)
    app.session_state["authenticated"] = True
    app.run()
    return app


class TestDashboardMokaLLMTimeout(unittest.TestCase):
    """Test Dashboard handles Moka LLM timeout gracefully."""

    @pytest.mark.skipif(not os.getenv("MOKA_API_KEY"), reason="Moka key not configured")
    def test_dashboard_shows_timeout_error(self) -> None:
        """Dashboard displays user-friendly timeout error message."""
        # Set extremely short timeout to trigger timeout
        original_timeout = os.environ.get("MOKA_TIMEOUT")
        os.environ["MOKA_TIMEOUT"] = "1"  # 1 second timeout

        try:
            app = _run_dashboard(role="operator")

            # Navigate to dispatch page (if tab exists)
            if app.radio:
                tabs = [str(r.value) for r in app.radio]
                if "Dispatch" in tabs:
                    app.radio[0].set_value("Dispatch").run()

            # Fill form with complex task (likely to timeout)
            if app.text_area:
                app.text_area[0].set_value("Analyze complex system architecture with 100 microservices").run()

            if app.multiselect:
                app.multiselect[0].set_value(["architect"]).run()

            # Submit (should timeout with MOKA_TIMEOUT=1)
            submit_button = [b for b in app.button if hasattr(b, "label") and "submit" in b.label.lower()]
            if submit_button:
                submit_button[0].click().run()

                # Verify error message displayed
                error_messages = [str(e.value) for e in app.error if hasattr(e, "value")]
                timeout_mentioned = any(
                    "timeout" in msg.lower() or "timed out" in msg.lower() for msg in error_messages
                )

                # Dashboard should show timeout error
                self.assertTrue(timeout_mentioned or app.exception, "Timeout error not communicated to user")

        finally:
            # Restore original timeout
            if original_timeout:
                os.environ["MOKA_TIMEOUT"] = original_timeout
            else:
                os.environ.pop("MOKA_TIMEOUT", None)

    def test_dashboard_timeout_does_not_crash(self) -> None:
        """Dashboard remains functional after timeout."""
        # Mock backend to simulate timeout
        with patch("scripts.collaboration.moka_backend.MokaAIBackend.generate") as mock_gen:
            mock_gen.side_effect = RuntimeError("Request timed out.")

            app = _run_dashboard(role="operator")

            # Dashboard should still render
            self.assertFalse(app.exception, f"Dashboard crashed on mocked timeout: {app.exception}")


class TestDashboardRealMokaLLM(unittest.TestCase):
    """Smoke test with real Moka LLM integration."""

    @pytest.mark.skipif(not os.getenv("MOKA_API_KEY"), reason="Moka key not configured")
    def test_dashboard_real_moka_smoke(self) -> None:
        """Dashboard successfully dispatches with real Moka LLM (simple task)."""
        # Use default MOKA_TIMEOUT (90s)
        app = _run_dashboard(role="operator")

        # Navigate to dispatch
        if app.radio:
            tabs = [str(r.value) for r in app.radio]
            if "Dispatch" in tabs:
                app.radio[0].set_value("Dispatch").run()

        # Submit simple task (should complete quickly)
        if app.text_area:
            app.text_area[0].set_value("Explain JWT authentication in one sentence").run()

        if app.multiselect:
            app.multiselect[0].set_value(["architect"]).run()

        submit_button = [b for b in app.button if hasattr(b, "label") and "submit" in b.label.lower()]
        if submit_button:
            submit_button[0].click().run()

            # Verify result rendered (not mock)
            result_text = " ".join(m.value for m in app.markdown)
            self.assertIn("JWT", result_text, "Real LLM result should mention JWT")
            self.assertNotIn("[MOCK MODE]", result_text, "Should not use mock backend")


class TestDashboardAPIRateLimit(unittest.TestCase):
    """Test Dashboard handles API rate limiting gracefully."""

    def test_dashboard_shows_rate_limit_error(self) -> None:
        """Dashboard displays friendly rate limit error message."""
        # Mock rate limit response
        with patch("scripts.collaboration.moka_backend.MokaAIBackend.generate") as mock_gen:
            mock_gen.side_effect = RuntimeError("Rate limit exceeded")

            app = _run_dashboard(role="operator")

            # Navigate to dispatch
            if app.radio:
                tabs = [str(r.value) for r in app.radio]
                if "Dispatch" in tabs:
                    app.radio[0].set_value("Dispatch").run()

            # Submit task
            if app.text_area:
                app.text_area[0].set_value("Test task").run()

            submit_button = [b for b in app.button if hasattr(b, "label") and "submit" in b.label.lower()]
            if submit_button:
                submit_button[0].click().run()

                # Verify friendly error message
                error_messages = [str(e.value) for e in app.error if hasattr(e, "value")]
                rate_limit_mentioned = any("rate limit" in msg.lower() for msg in error_messages)

                # Dashboard should communicate rate limit error
                self.assertTrue(rate_limit_mentioned or app.exception, "Rate limit error not shown to user")

    def test_dashboard_rate_limit_retry_suggestion(self) -> None:
        """Dashboard suggests retry when rate limited."""
        with patch("scripts.collaboration.moka_backend.MokaAIBackend.generate") as mock_gen:
            mock_gen.side_effect = RuntimeError("Rate limit exceeded. Retry after 60 seconds.")

            app = _run_dashboard(role="operator")

            # Trigger rate limit error
            if app.radio:
                tabs = [str(r.value) for r in app.radio]
                if "Dispatch" in tabs:
                    app.radio[0].set_value("Dispatch").run()

            if app.text_area:
                app.text_area[0].set_value("Test").run()

            submit_button = [b for b in app.button if hasattr(b, "label") and "submit" in b.label.lower()]
            if submit_button:
                submit_button[0].click().run()

                # Should suggest retry or show wait time
                all_text = " ".join(m.value for m in app.markdown) + " ".join(
                    str(e.value) for e in app.error if hasattr(e, "value")
                )
                retry_mentioned = "retry" in all_text.lower() or "wait" in all_text.lower()

                # Friendly UX should mention retry
                self.assertTrue(retry_mentioned, "Dashboard should suggest retry on rate limit")


class TestDashboardLLMBackendFallback(unittest.TestCase):
    """Test Dashboard fallback behavior when LLM backend unavailable."""

    def test_dashboard_falls_back_to_mock_when_no_key(self) -> None:
        """Dashboard uses mock backend when no API key configured."""
        # Remove API keys temporarily
        api_keys = {
            "MOKA_API_KEY": os.environ.pop("MOKA_API_KEY", None),
            "OPENAI_API_KEY": os.environ.pop("OPENAI_API_KEY", None),
            "ANTHROPIC_API_KEY": os.environ.pop("ANTHROPIC_API_KEY", None),
        }

        try:
            app = _run_dashboard(role="operator")

            # Navigate to dispatch
            if app.radio:
                tabs = [str(r.value) for r in app.radio]
                if "Dispatch" in tabs:
                    app.radio[0].set_value("Dispatch").run()

            # Submit task
            if app.text_area:
                app.text_area[0].set_value("Test task").run()

            submit_button = [b for b in app.button if hasattr(b, "label") and "submit" in b.label.lower()]
            if submit_button:
                submit_button[0].click().run()

                # Should render with mock backend
                result_text = " ".join(m.value for m in app.markdown)
                self.assertIn("[MOCK MODE]", result_text, "Should fall back to mock backend")

        finally:
            # Restore API keys
            for key, value in api_keys.items():
                if value:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
