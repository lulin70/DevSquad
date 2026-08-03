#!/usr/bin/env python3
"""E2E tests for V4.4.3 cross-session persistence.

Verifies the three V4.4.3 user-journey promises end-to-end:
  1. Cross-session Scratchpad search — entries written in one session are
     discoverable from a later session via the SQLite archive.
  2. Agent identity is persistent across sessions — the same (role, backend,
     model) produces the same agent_id in two *separate Python processes*
     (true cross-session determinism, not just in-memory caching).
  3. Anti-ghost — both new modules' ``_call_counter`` are > 0 after a real
     operation, proving they are wired in and not dead code.

Iron Rules:
  1. Documentation-first: source modules read before writing these tests.
  2. Failure-means-report: real SQLite file + real subprocess, no Mock.
  3. Dimension-completeness: Happy (2) + Side-Effect (1) + Integration (2).
  4. Side-effect-verification: file persistence + call counters verified.
  5. User-journey-first: the "what did some AI instance decide weeks ago?"
     journey is exercised in full.
  6. e2e-release-gate: this file IS the release gate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration import agent_identity as ai_module  # noqa: E402
from scripts.collaboration import scratchpad_history_store as shs_module  # noqa: E402
from scripts.collaboration.agent_identity import AgentIdentity  # noqa: E402
from scripts.collaboration.models_base import EntryType, ScratchpadEntry  # noqa: E402
from scripts.collaboration.scratchpad import Scratchpad  # noqa: E402
from scripts.collaboration.scratchpad_history_store import ScratchpadHistoryStore  # noqa: E402


def test_e2e_cross_session_scratchpad_search():
    """Journey-1: an entry written in session-1 is found by a search in session-2.

    Two separate ScratchpadHistoryStore instances opened against the SAME
    SQLite file simulate two sessions. The file is the cross-session medium,
    so re-opening in a new instance is a faithful session simulation.
    """
    tmpdir = tempfile.mkdtemp(prefix="devsquad_e2e_v443_")
    db_path = Path(tmpdir) / "history.db"
    try:
        # --- Session 1: write an entry via Scratchpad (mirrors to SQLite). ---
        store1 = ScratchpadHistoryStore(db_path)
        sp1 = Scratchpad(scratchpad_id="session-2026-08-01", history_store=store1)
        entry = ScratchpadEntry(
            worker_id="arch-1",
            role_id="architect",
            entry_type=EntryType.DECISION,
            content="Decision: adopt PostgreSQL as the primary OLTP database.",
            confidence=0.9,
            tags=["db", "decision"],
        )
        sp1.write(entry)
        store1.close()  # end session 1

        # --- Session 2: a brand-new store/scratchpad, search the archive. ---
        store2 = ScratchpadHistoryStore(db_path)
        sp2 = Scratchpad(scratchpad_id="session-2026-09-15", history_store=store2)

        # Session 2 has no in-memory entries of its own for the old decision.
        own = sp2.read(query="PostgreSQL")
        assert own == [], "session-2 scratchpad should be empty for the old decision"

        # But the cross-session archive finds session-1's decision.
        archived = store2.search_history(query="PostgreSQL")
        assert len(archived) == 1
        assert "adopt PostgreSQL" in archived[0].content
        assert archived[0].role_id == "architect"
        assert archived[0].entry_type == EntryType.DECISION
        store2.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_e2e_agent_identity_persistent_across_sessions():
    """Journey-2: same (role, backend, model) yields same agent_id across processes.

    Agent identity is a pure deterministic function with no state, so the only
    honest "cross-session" proof is to compute it in two separate Python
    processes and compare. This rules out any in-memory caching trickery.
    """
    env = {**os.environ, "PYTHONPATH": _PROJECT_ROOT}
    script = (
        "from scripts.collaboration.agent_identity import derive_agent_id;"
        "print(derive_agent_id('architect','openai','gpt-4'))"
    )

    proc1 = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, env=env, cwd=_PROJECT_ROOT, timeout=30,
    )
    proc2 = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, env=env, cwd=_PROJECT_ROOT, timeout=30,
    )

    assert proc1.returncode == 0, f"session-1 subprocess failed: {proc1.stderr}"
    assert proc2.returncode == 0, f"session-2 subprocess failed: {proc2.stderr}"
    id1 = proc1.stdout.strip()
    id2 = proc2.stdout.strip()
    assert id1 == id2, f"agent_id not deterministic across sessions: {id1!r} vs {id2!r}"
    assert id1.startswith("agent-architect-"), f"unexpected agent_id format: {id1}"

    # And it matches the in-process derivation (consistency contract).
    assert id1 == AgentIdentity.create("architect", "openai", "gpt-4").agent_id


def test_e2e_anti_ghost_all_v443_modules_activated():
    """Journey-3: a real cross-session operation activates both new modules.

    After writing+searching via ScratchpadHistoryStore and deriving an
    AgentIdentity, both modules' module-level ``_call_counter`` must be > 0,
    proving they executed real code paths (not ghost/dead code).
    """
    tmpdir = tempfile.mkdtemp(prefix="devsquad_e2e_ghost_")
    db_path = Path(tmpdir) / "ghost.db"
    try:
        # Snapshot counters BEFORE the operation.
        ai_before = ai_module._call_counter
        shs_before = shs_module._call_counter

        # Real operation exercising both modules.
        identity = AgentIdentity.create("architect", "mock", "mock")
        store = ScratchpadHistoryStore(db_path)
        sp = Scratchpad(scratchpad_id="ghost-session", history_store=store)
        sp.write(ScratchpadEntry(
            worker_id="arch-1",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content=f"Finding recorded by {identity.agent_id}",
        ))
        results = store.search_history(query="Finding")
        assert len(results) == 1
        store.close()

        # Anti-ghost: both counters must have incremented.
        assert ai_module._call_counter > ai_before, "AgentIdentity never activated"
        assert shs_module._call_counter > shs_before, "ScratchpadHistoryStore never activated"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
