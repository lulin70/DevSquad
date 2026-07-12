"""Real LLM smoke tests — skipped in CI, run locally with API key.

These tests verify that DevSquad works end-to-end with real LLM backends.
They are NOT meant to run in CI — only for local verification before releases.

Usage:
    LLM_API_KEY=sk-xxx LLM_BASE_URL=https://api.openai.com/v1 python -m pytest tests/smoke/ -v
    # Or with Moka AI (source .env first):
    source .env && python -m pytest tests/smoke/test_real_llm_smoke.py::TestMokaLLMSmoke -v
"""

import os

import pytest


@pytest.mark.skipif(not os.environ.get("LLM_API_KEY"), reason="LLM_API_KEY not set — smoke tests require real API key")
class TestRealLLMSmoke:
    """Quick smoke tests with real LLM backend."""

    def test_dispatch_with_real_llm(self):
        """Verify dispatch works end-to-end with real LLM."""
        import tempfile

        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import create_backend

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
        import tempfile

        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import create_backend

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
        import tempfile

        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import create_backend

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


@pytest.mark.skipif(
    not os.environ.get("MOKA_API_KEY"), reason="MOKA_API_KEY not set — Moka smoke tests require real API key"
)
class TestMokaLLMSmoke:
    """Smoke tests with Moka AI LLM backend (OpenAI-compatible).

    Moka AI provides an OpenAI-compatible API, so we reuse OpenAIBackend
    with Moka's base_url and model. This verifies the core dispatch pipeline
    works end-to-end with a real LLM provider.

    Usage:
        source .env && python -m pytest tests/smoke/test_real_llm_smoke.py::TestMokaLLMSmoke -v
    """

    def _create_moka_backend(self):
        """Create an OpenAIBackend configured for Moka AI."""
        from scripts.collaboration.llm_backend import OpenAIBackend

        return OpenAIBackend(
            api_key=os.environ["MOKA_API_KEY"],
            base_url=os.environ.get("MOKA_API_BASE", "https://api.moka-ai.com/v1"),
            model=os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6"),
        )

    def test_dispatch_with_moka_llm(self):
        """Verify dispatch works end-to-end with Moka AI LLM."""
        import tempfile

        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        backend = self._create_moka_backend()
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir, llm_backend=backend)
            result = disp.dispatch("What is 2+2?", roles=["solo-coder"])
            assert result.success
            assert result.worker_results
            disp.shutdown()

    def test_dispatch_multi_role_moka(self):
        """Verify multi-role parallel dispatch works with Moka AI."""
        import tempfile

        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        backend = self._create_moka_backend()
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir, llm_backend=backend)
            result = disp.dispatch(
                "Design a simple user login flow for a web app",
                roles=["architect", "coder"],
            )
            assert result.success
            assert len(result.worker_results) >= 2
            disp.shutdown()

    def test_moka_result_contains_findings(self):
        """Verify dispatch result structure contains worker findings."""
        import tempfile

        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        backend = self._create_moka_backend()
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir, llm_backend=backend)
            result = disp.dispatch("Analyze trade-offs between SQL and NoSQL databases", roles=["architect"])
            assert result.success
            assert result.worker_results
            # Each worker result should have required fields (dict or object)
            for wr in result.worker_results:
                if isinstance(wr, dict):
                    assert "worker_id" in wr
                    assert "success" in wr
                else:
                    assert hasattr(wr, "worker_id")
                    assert hasattr(wr, "success")
            disp.shutdown()
