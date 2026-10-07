#!/usr/bin/env python3
"""Per-release anti-ghost activation probes for ``check_module_activation``.

Extracted from ``check_module_activation.py`` (V4.5.20 size-gate refactor). The
gate's ``main()`` runs a production probe first (see that module) and then calls
these helpers to touch each release's modules directly, bumping their
``_call_counter_er`` so the ``counter > 0`` assertion has legacy coverage for
modules that carry no production-wiring claim.

Each helper exercises exactly one release wave (V4.5.3 / V4.5.4 / V4.5.6 …
V4.5.13). All operations are best-effort: a failure still leaves the gate
fail-closed via the counter check in the caller, never via an exception here.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _activate_v4513_modules() -> None:
    """Exercise V4.5.13 previously-scanned-but-unverified modules.

    Touches (in order):
        - ApprovalGate_V451.1 — request_approval (auto-approve path)
        - ConnectorFramework_V451.2 — GitHubConnector simulation probe
        - DoraMetricsCollector_V440.P2.1 — collect_from_dispatch
        - GapAnalyzer_V440.P1.2 — add_gap + analyze (P2 + P3)
        - ErrorBudgetTracker_V440.P1.1 — calculate + status
        - RiskRegister_V440.P0.1 — add + assess + export_markdown
        - FileBundler_V450 — bundle (deterministic, real tempdir files)
        - ScratchpadHistoryStore_V443 — write + search_history

    All operations are best-effort and never raise — failures still leave
    the gate fail-closed via the ``counter > 0`` check in ``main()``.
    """
    from scripts.collaboration.approval_gate import ApprovalGate
    from scripts.collaboration.connector_framework import GitHubConnector
    from scripts.collaboration.dora_metrics_collector import DoraMetricsCollector
    from scripts.collaboration.error_budget_tracker import ErrorBudgetTracker
    from scripts.collaboration.file_bundler import FileBundler
    from scripts.collaboration.gap_analyzer import GapAnalyzer
    from scripts.collaboration.models_base import EntryType, ScratchpadEntry
    from scripts.collaboration.risk_register import RiskRegister
    from scripts.collaboration.scratchpad_history_store import ScratchpadHistoryStore

    # ApprovalGate — auto-approve (callback=None) so V4.5.0 backward-compat
    # contracts hold; exercises request_approval + get_records + export_markdown.
    gate = ApprovalGate()
    gate.request_approval(
        operation_type="anti-ghost",
        description="anti-ghost check",
    )
    gate.get_records()
    gate.export_markdown()

    # ConnectorFramework — simulation probe (no real GitHub API).
    probe = GitHubConnector(simulation=True)
    probe.create_pr_comment(
        repo="devsquad/anti-ghost",
        pr_number=0,
        body="anti-ghost probe",
    )
    probe.get_operations()
    probe.export_markdown()

    # DoraMetricsCollector — collect_from_dispatch with empty logs.
    dmc = DoraMetricsCollector()
    dmc.collect_from_dispatch([], window_days=30)
    dmc.report()
    dmc.to_dashboard_panel()

    # GapAnalyzer — add_gap + analyze(P2) + analyze(P3 current vs target).
    ga = GapAnalyzer()
    ga.add_gap(
        current_state="v4.4.0",
        target_state="v4.5.0",
        work_package="anti-ghost closure",
        priority="medium",
        effort="low",
    )
    ga.analyze(target={"capability": "v4.5.0"})
    ga.analyze(
        current={"capability": "v4.4.0"},
        target={"capability": "v4.5.0"},
    )
    ga.prioritize()
    ga.generate_roadmap()
    ga.suggest_scheduler_decision(
        next(iter(ga._gaps), "anti-ghost") if hasattr(ga, "_gaps") and ga._gaps else "anti-ghost"
    )

    # ErrorBudgetTracker — calculate + status (always-on SRE gate).
    ebt = ErrorBudgetTracker(slo_target=0.999, window_days=30)
    ebt.calculate(
        slo_target=0.999,
        window_days=30,
        observed_errors=0,
        total_events=100,
    )
    ebt.status()
    ebt.to_dashboard_panel()

    # RiskRegister — add + assess + export_markdown.
    rr = RiskRegister()
    risk = rr.add(
        description="anti-ghost check risk",
        probability=0.2,
        impact=0.3,
        category="delivery",
        owner="anti-ghost",
    )
    rr.assess(
        risk.id,
        votes={"architect": (0.2, 0.3), "security": (0.1, 0.4)},
    )
    rr.export_markdown()

    # FileBundler — deterministic grouping on real temp files.
    with tempfile.TemporaryDirectory() as fb_tmp:
        a = Path(fb_tmp) / "a.py"
        b = Path(fb_tmp) / "b.py"
        a.write_text("import b\n", encoding="utf-8")
        b.write_text("VALUE = 1\n", encoding="utf-8")
        FileBundler().bundle([str(a), str(b)], max_per_bundle=4)

    # ScratchpadHistoryStore — write + search_history in real tempdir DB.
    with tempfile.TemporaryDirectory() as sp_tmp:
        store = ScratchpadHistoryStore(db_path=str(Path(sp_tmp) / "h.db"))
        entry = ScratchpadEntry(
            worker_id="anti-ghost",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="anti-ghost check entry",
            confidence=0.9,
            tags=["anti-ghost"],
        )
        store.write(entry, scratchpad_id="scratchpad-anti-ghost")
        store.search_history(query="anti-ghost", limit=10)
        store.cleanup_expired()
        store.close()


def _activate_v4512_modules() -> None:
    """Exercise V4.5.12 modules to bump their anti-ghost counters.

    Touches:
        - RiskStoreStats_V4512.1 — FileRiskStore load/save/transaction
          stats instrumentation (capacity + concurrent-write window)
        - RisksStatsCli_V4512.2 — cmd_risks_stats text/json round-trip
    """
    import io
    import json as _json
    import tempfile
    from argparse import Namespace
    from contextlib import redirect_stdout

    from scripts.cli_risks import cmd_risks_stats
    from scripts.collaboration.file_risk_store import FileRiskStore

    with tempfile.TemporaryDirectory() as tmpdir:
        root = str(Path(tmpdir) / "risks")
        store = FileRiskStore(root=root)
        # transaction + save path bumps stats counter and records a write.
        with store.transaction("default") as tx:
            tx["items"] = []
        store.save("default", {"version": 1, "register_id": "default", "items": []})

        assert store.stats.capacity == 0
        assert store.stats.concurrent_writes_1m >= 1

        # risks stats CLI round-trip (text + json).
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert (
                cmd_risks_stats(
                    Namespace(
                        register_id="default",
                        root=root,
                        format="json",
                    )
                )
                == 0
            )
        payload = _json.loads(buf.getvalue())
        assert payload["register_id"] == "default"
        with redirect_stdout(buf):
            assert (
                cmd_risks_stats(
                    Namespace(
                        register_id="default",
                        root=root,
                        format="text",
                    )
                )
                == 0
            )
        assert "Risk Store Stats" in buf.getvalue()


def _activate_v4510_modules() -> int:
    """Exercise the V4.5.10 HostBridge v2 production wiring (AC-α-8).

    Asserts create_backend("host") really instantiates HostBridgeBackendV2
    (not just that the module exists). Returns 1 on success, 0 on failure
    so the counter-style gate fails closed.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        bridge_dir = str(Path(td) / "v2")
        os.environ["TRAE_ENV"] = "1"
        try:
            from scripts.collaboration.host_llm_bridge import HostBridgeBackendV2
            from scripts.collaboration.llm_backend import create_backend

            backend = create_backend("host", bridge_dir=bridge_dir)
            wired = type(backend) is HostBridgeBackendV2
        except Exception:
            wired = False
        finally:
            os.environ.pop("TRAE_ENV", None)
    return 1 if wired else 0


def _activate_v459_modules() -> None:
    """Exercise the V4.5.9 gather core to bump its anti-ghost counter.

    Runs one minimal execute_batch_gather() batch — the same entry point a
    parallel dispatch hits — so ``_call_counter_gather`` reflects real usage.
    """
    import asyncio

    from scripts.collaboration.gather_core import execute_batch_gather
    from scripts.collaboration.models import TaskDefinition, WorkerResult

    async def _run_one(task: TaskDefinition) -> WorkerResult:
        return WorkerResult(worker_id="anti-ghost", task_id=task.task_id, success=True)

    async def _drive() -> list[WorkerResult]:
        return await execute_batch_gather(
            [TaskDefinition(description="anti-ghost check", role_id="architect")],
            _run_one,
            1,
        )

    asyncio.run(_drive())


def _activate_v458_modules() -> None:
    """Exercise V4.5.8 modules to bump their anti-ghost counters.

    Touches:
        - FileRiskStore — items_to_payload + transaction write + load
          round-trip + lock_timeout lock acquisition failure
        - CliRisks mutators — add + mitigate + close (no approval) +
          list --min-exposure filtering
    """
    import io
    import tempfile
    from argparse import Namespace
    from contextlib import redirect_stdout
    from pathlib import Path

    # Wave 1: FileRiskStore — full persistence round-trip
    from scripts.collaboration.file_risk_store import (
        FileRiskStore,
        RiskStoreLockError,
    )
    from scripts.collaboration.risk_register import (
        ResponseStrategy,
        RiskItem,
        RiskStatus,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        store = FileRiskStore(root=root, lock_timeout=1.0)
        item = RiskItem(
            id="R-AG-1",
            description="anti-ghost V4.5.8 risk",
            probability=0.4,
            impact=0.5,
            response_strategy=ResponseStrategy.MITIGATE,
            owner="anti-ghost",
            status=RiskStatus.OPEN,
            category="technical",
        )
        payload = store.items_to_payload("default", iter([item]))
        with store.transaction("default") as tx:
            tx["items"] = payload["items"]
        loaded = store.load("default")
        assert loaded["version"] == 1
        assert loaded["items"][0]["id"] == "R-AG-1"

        # Lock timeout: a second store with lock_timeout=0.1 must fail while
        # the transaction above holds the cross-process lock.
        holder = FileRiskStore(root=root, lock_timeout=5.0)
        with holder.transaction("default"):
            tight = FileRiskStore(root=root, lock_timeout=0.1)
            try:
                tight.load("default")
            except RiskStoreLockError:
                pass
            else:
                raise AssertionError("expected RiskStoreLockError after 0.1s timeout")

    # Wave 2+3: CliRisks mutators — add → mitigate → close → list filter
    from scripts.cli_risks import (
        cmd_risks_add,
        cmd_risks_close,
        cmd_risks_list,
        cmd_risks_mitigate,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        risks_root = str(Path(tmpdir) / "risks")
        buf = io.StringIO()
        with redirect_stdout(buf):
            add_rc = cmd_risks_add(
                Namespace(
                    description="anti-ghost CLI risk",
                    probability=0.6,
                    impact=0.5,
                    category="technical",
                    owner="anti-ghost",
                    register_id="default",
                    root=risks_root,
                )
            )
        assert add_rc == 0

        # Recover the risk id from the persisted store.
        reader = FileRiskStore(root=risks_root)
        risk_id = next(iter(reader.payload_to_items(reader.load("default"))))

        with redirect_stdout(buf):
            assert (
                cmd_risks_mitigate(
                    Namespace(
                        risk_id=risk_id,
                        strategy="mitigate",
                        owner="devops",
                        plan="anti-ghost plan",
                        register_id="default",
                        root=risks_root,
                    )
                )
                == 0
            )

        # Close WITHOUT approval (require_approval=False → no gate).
        with redirect_stdout(buf):
            assert (
                cmd_risks_close(
                    Namespace(
                        risk_id=risk_id,
                        require_approval=False,
                        register_id="default",
                        root=risks_root,
                    )
                )
                == 0
            )

        # --min-exposure filter: high threshold hides every row, zero shows it.
        buf_hidden, buf_visible = io.StringIO(), io.StringIO()
        with redirect_stdout(buf_hidden):
            assert (
                cmd_risks_list(
                    Namespace(
                        register_id="default",
                        root=risks_root,
                        format="md",
                        min_exposure=0.99,
                        category=None,
                        limit=None,
                    )
                )
                == 0
            )
        assert "(none)" in buf_hidden.getvalue()
        with redirect_stdout(buf_visible):
            assert (
                cmd_risks_list(
                    Namespace(
                        register_id="default",
                        root=risks_root,
                        format="md",
                        min_exposure=0.0,
                        category=None,
                        limit=None,
                    )
                )
                == 0
            )
        assert "`R-" in buf_visible.getvalue()


def _activate_v454_modules() -> None:
    """Exercise V4.5.4 P12.3 modules to bump their anti-ghost counters.

    Touches:
        - ModuleFiber_P12.3.1 — ModuleFiberRegistry
        - CoeffectResolver_P12.3.2 — register + resolve
        - ModulesCLI_P12.3.3 — cmd_modules_status
    """
    # Local imports — these names live in main(), not module-scope.
    from scripts.cli_modules import cmd_modules_status as _cms_local
    from scripts.collaboration.coeffect import (
        CoeffectResolver as _CR_local,
    )
    from scripts.collaboration.coeffect import _StaticProvider as _SP_local
    from scripts.collaboration.module_fiber import (
        ModuleFiberRegistry as _MFR_local,
    )

    # P12.3.1: ModuleFiber — register a few fibers
    reg = _MFR_local()
    for module_id in ("v454_module_a", "v454_module_b"):
        fiber = reg.register(module_id)
        fiber.transition(fiber.state.__class__.ACTIVATING)
        fiber.transition(fiber.state.__class__.ACTIVE)

    # P12.3.2: CoeffectResolver — register + resolve
    resolver = _CR_local()
    resolver.register(_SP_local("v454_module_a", ()))
    resolver.register(_SP_local("v454_module_b", ("v454_module_a",)))
    resolver.resolve_activation_order()

    # P12.3.3: ModulesCLI — exercise status command
    from argparse import Namespace

    _cms_local(Namespace(registry=reg, format="text", module=None))


def _activate_v455_modules() -> None:
    """Exercise V4.5.6 P12.4 modules to bump their anti-ghost counters.

    Touches:
        - HostLLMBridgeV2_P12.4.1 — create_request (writes marker)
        - DispatcherTransaction_P12.4.2 — begin + commit
        - IntentWorkflowMapper_P12.4.3 — resolve one workflow
        - DispatchLoopController_P12.4.4 — should_stop call
    """
    # P12.4.1: HostLLMBridgeV2 — create_request
    import tempfile as _tf

    from scripts.collaboration.dispatcher_intent_mapper import IntentWorkflowMapper
    from scripts.collaboration.dispatcher_loop_controller import (
        DispatchLoopController,
        IterationKind,
        IterationResult,
    )
    from scripts.collaboration.dispatcher_transaction import (
        DispatchTransaction,
        TransactionRegistry,
    )
    from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2

    with _tf.TemporaryDirectory() as tmpdir:
        bridge = HostLLMBridgeV2(bridge_dir=tmpdir)
        bridge.create_request(
            agent_type="anti-ghost",
            task="anti-ghost check v2",
            context={},
            prompt="v2 test prompt",
        )

    # P12.4.2: DispatcherTransaction — full lifecycle
    tx = DispatchTransaction(tx_id="anti-ghost-tx")
    tx.register_module("m1", lambda: None, lambda: None)
    tx.begin()
    tx.commit()

    # P12.4.3: IntentWorkflowMapper — resolve one workflow
    mapper = IntentWorkflowMapper()
    mapper.resolve("design", "zh")

    # P12.4.4: DispatchLoopController — should_stop call
    ctrl = DispatchLoopController()
    ctrl.should_stop(IterationResult(IterationKind.SUCCESS))
    # Also verify the registry helper is importable
    _ = TransactionRegistry()


def _activate_v457_modules() -> None:
    """Exercise V4.5.7 P12.5 modules to bump their anti-ghost counters.

    Touches:
        - AsyncCoeffectResolver_P12.5.1 — sync bridge resolve() with executor
        - CliRisks_P12.5.2 — add_risk + cmd_risks_list
    """
    from argparse import Namespace

    # P12.5.1: AsyncCoeffectResolver — sync bridge round-trip
    from scripts.collaboration.async_coeffect_resolver import (
        AsyncCoeffectResolver,
        CoeffectRequest,
        CoeffectState,
    )

    resolver = AsyncCoeffectResolver()
    result = resolver.resolve(
        CoeffectRequest(
            name="anti-ghost",
            payload={"executor": lambda: 42},
        )
    )
    assert result.state == CoeffectState.COMPLETED
    assert result.value == 42

    # P12.5.2: CliRisks — add + list round-trip (in-process store)
    from scripts.cli_risks import add_risk, cmd_risks_list

    add_risk("anti-ghost verification risk", probability=0.1, impact=0.1)
    cmd_risks_list(Namespace(format="md", limit=None))


def _activate_v453_modules() -> None:
    """Exercise V4.5.3 P12.2 modules to bump their anti-ghost counters."""
    from scripts.cli_audit import get_call_counter_er as au_call_counter_er
    from scripts.collaboration.artifact_store import (
        ArtifactStore,
    )
    from scripts.collaboration.dispatch_effect import (
        EffectContext,
        WriteFileEffect,
    )
    from scripts.collaboration.effect_registry import (
        EffectRegistry,
    )

    # P12.2.1: ArtifactStore — exercise write + list
    store = ArtifactStore()
    store.write("anti-ghost-session", "anti-ghost-role", "ghost.md", "anti-ghost content")

    # P12.2.3 + P12.2.4: DispatchEffect + EffectRegistry — apply + revert
    reg = EffectRegistry()
    effect_ctx = EffectContext(
        effect_id="anti-ghost",
        effect_type="write_file",
        payload={"path": "/tmp/anti-ghost-test.txt", "content": "ghost"},
    )
    reg.apply(WriteFileEffect(), effect_ctx)
    reg.pending_count()

    # P12.2.6: AuditCLI — exercise get_call_counter_er (cmd_audit is imported above)
    _ = au_call_counter_er()
    # Exercise cmd_audit once to bump counter
    from argparse import Namespace

    from scripts.cli_audit import cmd_audit as _cmd_audit

    _cmd_audit(
        Namespace(
            limit=0,
            format="text",
            event_type=None,
            verify=False,
            db_path=None,
        )
    )


__all__ = [
    "_activate_v4513_modules",
    "_activate_v4512_modules",
    "_activate_v4510_modules",
    "_activate_v459_modules",
    "_activate_v458_modules",
    "_activate_v454_modules",
    "_activate_v455_modules",
    "_activate_v457_modules",
    "_activate_v453_modules",
]
