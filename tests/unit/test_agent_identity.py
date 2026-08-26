#!/usr/bin/env python3
"""Unit tests for V4.4.3 AgentIdentity — deterministic cross-session agent identity.

Iron Rules applied:
  1. Documentation-first: source docstring (scripts/collaboration/agent_identity.py)
     read before writing tests. ``derive_agent_id`` format is documented as
     ``agent-{role}-{sha256(role:backend:model)[:8]}``; ``AgentIdentity.create``
     defaults backend/model to "mock"; None backend normalizes to "unknown".
  2. Failure-means-report: no try/except swallowing — real components only.
  3. Dimension-completeness: 13 tests across 7 dimensions (see matrix below).
  4. Side-effect-verification: ``_call_counter_er`` anti-ghost verified.
  5. User-journey-first: Worker integration + audit-log integration mirror the
     real "which AI instance made this decision?" cross-session journey.
  6. e2e-release-gate: covered by tests/e2e/test_v443_persistence.py.

Dimension matrix (13 tests):
  Happy       (7): deterministic_id, different_role, different_backend,
                   different_model, id_format, worker_integration, backward_compat
  Error       (2): empty_role_raises, query_by_agent (non-existent agent)
  Boundary    (2): id_format (exact 8-hex length), none_backend_normalized
  Performance (1): derive_performance
  Config      (3): id_format, none_backend_normalized, backward_compat
  Integration (3): worker_integration, audit_log_integration, query_by_agent
  Side-Effect (1): call_counter_anti_ghost

Anti-ghost note: ``_call_counter_er`` is a module-level ``int`` rebound on every
public call (``_call_counter_er += 1``). Because ints are immutable, ``from
module import _call_counter_er`` binds a *snapshot* at import time and would NOT
reflect later increments — so we read it via module attribute access
(``agent_identity._call_counter_er``), the same pattern used by the V4.4.0
anti-ghost E2E tests.
"""

from __future__ import annotations

import os
import re
import sys
import time
import unittest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration import agent_identity as ai_module  # noqa: E402
from scripts.collaboration.agent_identity import (  # noqa: E402
    AgentIdentity,
    derive_agent_id,
)
from scripts.collaboration.dispatch_audit import DispatchAuditLogger  # noqa: E402
from scripts.collaboration.scratchpad import Scratchpad  # noqa: E402
from scripts.collaboration.worker import Worker  # noqa: E402


class TestAgentIdentity(unittest.TestCase):
    """V4.4.3 AgentIdentity unit tests (13 tests, 7 dimensions)."""

    # ------------------------------------------------------------------
    # Happy: determinism
    # ------------------------------------------------------------------

    def test_deterministic_id_same_config(self) -> None:
        """Happy: same (role, backend, model) produces identical agent_id across calls."""
        id1 = AgentIdentity.create("architect", "mock", "mock")
        id2 = AgentIdentity.create("architect", "mock", "mock")
        self.assertEqual(id1.agent_id, id2.agent_id)
        # Frozen dataclass equality also holds for identical config.
        self.assertEqual(id1, id2)

    def test_different_role_produces_different_id(self) -> None:
        """Happy: changing role_id changes agent_id."""
        arch = AgentIdentity.create("architect", "mock", "mock")
        tester = AgentIdentity.create("tester", "mock", "mock")
        self.assertNotEqual(arch.agent_id, tester.agent_id)
        self.assertTrue(arch.agent_id.startswith("agent-architect-"))
        self.assertTrue(tester.agent_id.startswith("agent-tester-"))

    def test_different_backend_produces_different_id(self) -> None:
        """Happy: changing backend changes agent_id (same role+model)."""
        mock = AgentIdentity.create("architect", "mock", "mock")
        openai = AgentIdentity.create("architect", "openai", "gpt-4")
        self.assertNotEqual(mock.agent_id, openai.agent_id)

    def test_different_model_produces_different_id(self) -> None:
        """Happy: changing model changes agent_id (same role+backend)."""
        gpt4 = AgentIdentity.create("architect", "openai", "gpt-4")
        gpt5 = AgentIdentity.create("architect", "openai", "gpt-5")
        self.assertNotEqual(gpt4.agent_id, gpt5.agent_id)

    # ------------------------------------------------------------------
    # Happy / Config / Boundary: format
    # ------------------------------------------------------------------

    def test_id_format_matches_pattern(self) -> None:
        """Happy/Config/Boundary: id matches ``agent-{role}-{8 hex chars}`` exactly."""
        aid = AgentIdentity.create("architect", "mock", "mock")
        # Exact format: agent-<role>-<exactly 8 lowercase hex chars>.
        match = re.fullmatch(r"agent-architect-[0-9a-f]{8}", aid.agent_id)
        self.assertIsNotNone(match, f"agent_id '{aid.agent_id}' does not match format")
        # Boundary: the hash segment is exactly 8 chars (not 7, not 9).
        hash_part = aid.agent_id.rsplit("-", 1)[-1]
        self.assertEqual(len(hash_part), 8)
        # And it equals the documented sha256[:8] of role:backend:model.
        import hashlib
        expected = hashlib.sha256(b"architect:mock:mock").hexdigest()[:8]
        self.assertEqual(hash_part, expected)

    # ------------------------------------------------------------------
    # Boundary / Config: None / defaults
    # ------------------------------------------------------------------

    def test_none_backend_normalized_to_unknown(self) -> None:
        """Boundary/Config: None backend is normalized to 'unknown' deterministically."""
        id_none = AgentIdentity.create("architect", None, None)
        id_unknown = AgentIdentity.create("architect", "unknown", "unknown")
        # None and explicit "unknown" produce the same hash (documented behavior).
        self.assertEqual(id_none.agent_id, id_unknown.agent_id)
        self.assertEqual(id_none.backend, "unknown")
        self.assertEqual(id_none.model, "unknown")
        # Deterministic across calls.
        self.assertEqual(id_none.agent_id, AgentIdentity.create("architect", None, None).agent_id)

    # ------------------------------------------------------------------
    # Error: validation
    # ------------------------------------------------------------------

    def test_empty_role_raises_value_error(self) -> None:
        """Error: empty role_id must raise ValueError (documented in derive_agent_id)."""
        with self.assertRaises(ValueError):
            derive_agent_id("", "mock", "mock")
        with self.assertRaises(ValueError):
            AgentIdentity.create("", "mock", "mock")

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    def test_derive_agent_id_performance(self) -> None:
        """Performance: 2000 derivations complete in < 100ms (sha256 is fast)."""
        start = time.perf_counter()
        for i in range(2000):
            derive_agent_id("architect", "mock", f"model-{i}")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 100.0, f"derive_agent_id too slow: {elapsed_ms:.2f}ms")

    # ------------------------------------------------------------------
    # Integration: Worker.agent_id
    # ------------------------------------------------------------------

    def test_worker_integration_agent_id(self) -> None:
        """Integration: Worker.agent_id matches AgentIdentity.create for the same config."""
        sp = Scratchpad()  # in-memory, isolated
        worker = Worker(
            worker_id="arch-001",
            role_id="architect",
            role_prompt="You are an architect",
            scratchpad=sp,
            llm_backend=None,  # → backend "mock", model "mock"
        )
        expected = AgentIdentity.create("architect", "mock", "mock").agent_id
        self.assertEqual(worker.agent_id, expected)
        # Deterministic across two workers with the same config.
        worker2 = Worker("arch-002", "architect", "prompt", sp, llm_backend=None)
        self.assertEqual(worker.agent_id, worker2.agent_id)

    # ------------------------------------------------------------------
    # Integration: DispatchAuditLogger
    # ------------------------------------------------------------------

    def test_audit_log_integration(self) -> None:
        """Integration: agent_id is a stable audit-log key (used as user_id, chain verifies).

        The agent_identity docstring states agent_id ``enables cross-session
        agent behavior tracking via DispatchAuditLogger``. We verify the real
        integration: an agent_id can be recorded in the audit log (here as
        user_id, the public API) and retrieved verbatim, and the HMAC chain
        remains intact.
        """
        logger = DispatchAuditLogger()  # in-memory
        identity = AgentIdentity.create("architect", "mock", "mock")
        logger.log_dispatch_start(
            user_id=identity.agent_id,
            task="Design payment gateway",
            roles=["architect"],
        )
        # Retrieve by agent_id (public query API, user_id filter).
        entries = logger.query(user_id=identity.agent_id)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].user_id, identity.agent_id)
        # Side-effect: the audit chain must still verify after recording.
        self.assertTrue(logger.verify_chain())

    def test_query_by_agent_via_audit_log(self) -> None:
        """Integration/Error: query audit entries by agent_id stored in details.

        ``DispatchAuditLogger.query_by_agent`` is a forward reference in the
        agent_identity docstring (not yet implemented). The real, equivalent
        capability today is to embed ``agent_id`` in entry ``details`` and
        filter via ``query()``. We verify that two distinct agents produce
        disjoint result sets, and that querying a non-existent agent returns
        an empty list (error/boundary dimension).
        """
        logger = DispatchAuditLogger()
        arch = AgentIdentity.create("architect", "mock", "mock")
        tester = AgentIdentity.create("tester", "mock", "mock")
        # Record one event per agent with agent_id embedded in details.
        logger._append_entry(
            "dispatch_start", arch.agent_id,
            {"agent_id": arch.agent_id, "task": "design"},
        )
        logger._append_entry(
            "dispatch_start", tester.agent_id,
            {"agent_id": tester.agent_id, "task": "test"},
        )

        all_entries = logger.query(event_type="dispatch_start")
        arch_entries = [e for e in all_entries if e.details.get("agent_id") == arch.agent_id]
        tester_entries = [e for e in all_entries if e.details.get("agent_id") == tester.agent_id]

        self.assertEqual(len(arch_entries), 1)
        self.assertEqual(len(tester_entries), 1)
        # The two agents produce disjoint result sets (distinct agent_ids).
        self.assertNotEqual(
            arch_entries[0].details.get("agent_id"),
            tester_entries[0].details.get("agent_id"),
        )
        # Error dimension: a non-existent agent returns nothing.
        ghost = [e for e in all_entries if e.details.get("agent_id") == "agent-ghost-deadbeef"]
        self.assertEqual(ghost, [])

    # ------------------------------------------------------------------
    # Config: backward compatibility
    # ------------------------------------------------------------------

    def test_backward_compat_defaults(self) -> None:
        """Config: AgentIdentity.create(role_id) defaults backend/model to 'mock'."""
        identity = AgentIdentity.create("architect")
        self.assertEqual(identity.backend, "mock")
        self.assertEqual(identity.model, "mock")
        # Must equal an explicit mock/mock call (backward-compat contract).
        self.assertEqual(identity.agent_id, derive_agent_id("architect", "mock", "mock"))
        self.assertEqual(identity.agent_id, AgentIdentity.create("architect", "mock", "mock").agent_id)

    # ------------------------------------------------------------------
    # Side-Effect: anti-ghost call counter
    # ------------------------------------------------------------------

    def test_call_counter_anti_ghost(self) -> None:
        """Side-Effect: module-level _call_counter_er increments on every public call.

        Reads via module attribute access (NOT ``from import``) because the
        counter is an int rebound on each call — a from-import would capture a
        stale snapshot and give a false negative.
        """
        before = ai_module._call_counter_er
        # Each public entry point increments the counter.
        AgentIdentity.create("architect", "mock", "mock")
        derive_agent_id("tester", "mock", "mock")
        after = ai_module._call_counter_er
        self.assertGreater(after, before, "module _call_counter_er did not increment")
        self.assertGreaterEqual(after - before, 2, "expected at least 2 increments")
        # The instance property mirrors the module global (read at call time).
        identity = AgentIdentity.create("dev", "mock", "mock")
        self.assertEqual(identity._call_counter_er, ai_module._call_counter_er)


if __name__ == "__main__":
    unittest.main()
