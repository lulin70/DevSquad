"""Real LLM smoke tests — skipped in CI, run locally with API key.

These tests verify that DevSquad works end-to-end with real LLM backends.
They are NOT meant to run in CI — only for local verification before releases.

Usage:
    LLM_API_KEY=sk-xxx LLM_BASE_URL=https://api.openai.com/v1 python -m pytest tests/smoke/ -v
"""

import os
import pytest

# Skip entire module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("LLM_API_KEY"),
    reason="LLM_API_KEY not set — smoke tests require real API key"
)


class TestRealLLMSmoke:
    """Quick smoke tests with real LLM backend."""

    def test_dispatch_with_real_llm(self):
        """Verify dispatch works end-to-end with real LLM."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import create_backend
        import tempfile

        backend = create_backend(
            "openai",
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL"),
            model=os.environ.get("LLM_MODEL", "gpt-4"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir, llm_backend=backend)
            result = disp.dispatch("What is 2+2?", roles=["solo-coder"])
            assert result.success
            assert result.worker_results
            disp.shutdown()

    def test_dispatch_with_ue_testing(self):
        """Verify Step 19 UE testing works with real LLM."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import create_backend
        import tempfile

        backend = create_backend(
            "openai",
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL"),
            model=os.environ.get("LLM_MODEL", "gpt-4"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir, llm_backend=backend)
            result = disp.dispatch("Design a user login flow", roles=["tester", "product-manager"])
            assert result.success
            # Step 19 should generate UE test plan
            if "ue_test_plan" in result.details:
                assert "heuristic_checks" in result.details["ue_test_plan"]
            disp.shutdown()

    def test_dispatch_tech_debt_scan(self):
        """Verify Step 20 tech debt scan works with real LLM."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import create_backend
        import tempfile

        backend = create_backend(
            "openai",
            api_key=os.environ["LLM_API_KEY"],
            base_url=os.environ.get("LLM_BASE_URL"),
            model=os.environ.get("LLM_MODEL", "gpt-4"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir, llm_backend=backend)
            result = disp.dispatch("Review code architecture", roles=["architect"])
            assert result.success
            # Step 20 should generate tech debt report
            if "tech_debt_report" in result.details:
                assert "total_debts" in result.details["tech_debt_report"]
            disp.shutdown()
