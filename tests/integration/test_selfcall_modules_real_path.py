"""Real user-path assertions for the 27 "self-call verified" modules.

Background: ``scripts/check_module_activation.py`` splits the module inventory
into "production-verified" and "self-call verified".  A self-call probe only
proves that a module can call itself; it does not prove that a user path can
reach it.  This file closes that gap by driving real entry points and then
asserting that the module counters moved.

Entry points exercised here (all offline, ``DEVSQUAD_LLM_BACKEND=mock``):

* ``MultiAgentDispatcher.dispatch()`` — pre/post dispatch pipeline
* ``WorkerFactory.create()`` + ``Worker.execute()`` — the worker API used by
  the coordinator (ArtifactStore + EffectRegistry persistence)
* ``devsquad`` CLI (``scripts.cli.main``) — ``modules``/``backend``/``risks``
* ``create_backend()`` — public LLM backend factory (moka / host v1+v2 /
  auto-fallback degradation)
* ``scripts/collect_baseline.py`` — maintainer performance-baseline command

Modules with NO user-reachable entry point are marked ``xfail`` below.  They
have zero production importers outside ``scripts/check_module_activation*.py``
(verified by a repo-wide search); covering them would require either calling
their internal methods directly (forbidden) or changing production code to
invent reachability (forbidden).
"""

from __future__ import annotations

import contextlib
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from scripts import collect_baseline as collect_baseline_module
from scripts.cli_audit import get_call_counter_er as audit_cli_counter
from scripts.cli_risks import get_call_counter_er as risks_cli_counter
from scripts.collaboration import (
    artifact_store,
    backend_config,
    backend_paths,
    effect_registry,
    gather_core,
    host_llm_bridge,
    host_llm_bridge_v2,
    llm_backend,
    module_fiber,
    moka_backend,
    order_chain_detector,
    perf_baseline,
    task_scale_gate,
)
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.file_risk_store import (
    get_call_counter_er as file_risk_store_counter,
)
from scripts.collaboration.file_risk_store import (
    get_risk_store_stats_counter_er as risk_store_stats_counter,
)
from scripts.collaboration.llm_backend import (
    FallbackBackend,
    MockBackend,
    create_backend,
)
from scripts.collaboration.models_base import TaskDefinition
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import WorkerFactory
from tests.fakes.fake_host_runner import FakeHostRunner
from tests.fakes.fake_host_runner_v2 import FakeHostRunnerV2

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# -- Modules that cannot be reached from any user entry point (xfail) --------
# Each entry is (module name from check_module_activation.py, evidence).
UNREACHABLE_MODULES = [
    (
        "GitLabConnector_P12.1.3",
        "No production importer: only check_module_activation*.py references it. "
        "ConnectorFramework (the dispatch-wired connector) has no GitLab backend.",
    ),
    (
        "DispatcherTransaction_P12.4.2",
        "No production importer: the dispatcher never opens a DispatchTransaction; "
        "only check_module_activation*.py constructs it.",
    ),
    (
        "IntentWorkflowMapper_P12.4.3",
        "dispatcher_intent_mapper.py has no production importer. The CLI uses the "
        "separate scripts.collaboration.intent_workflow_mapper module instead.",
    ),
    (
        "DispatchLoopController_P12.4.4",
        "No production importer: nothing creates a DispatchLoopController, so "
        "should_stop() is never consulted by a dispatch.",
    ),
    (
        "AsyncCoeffectResolver_P12.5.1",
        "No production importer: the async resolver is not wired into the "
        "dispatcher or any async pipeline; coverable only via its own API.",
    ),
]


def _dispatch_task(description: str) -> MultiAgentDispatcher:
    """Run one real dispatch with a mock backend; return the dispatcher."""
    dispatcher = MultiAgentDispatcher(llm_backend=create_backend("mock"), enable_warmup=False)
    try:
        result = dispatcher.dispatch(description)
    finally:
        dispatcher.shutdown()
    assert result.success, "mock dispatch must succeed"
    return dispatcher


def _run_cli(argv: list[str], monkeypatch: pytest.MonkeyPatch, capsys) -> tuple[int, str]:
    """Invoke the real ``devsquad`` CLI entry point in-process."""
    from scripts.cli import main

    monkeypatch.setattr(sys, "argv", ["devsquad", *argv])
    rc = main()
    return rc, capsys.readouterr().out


@contextlib.contextmanager
def _fake_host_thread(runner):
    """Run a fake host runner in a daemon thread until the block exits."""
    stop = threading.Event()

    def _loop() -> None:
        while not stop.is_set():
            # The fake host must never kill the test thread.
            with contextlib.suppress(Exception):
                runner.process_one()
            time.sleep(0.005)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    try:
        yield runner
    finally:
        stop.set()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _offline_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test on the offline mock path."""
    monkeypatch.setenv("DEVSQUAD_LLM_BACKEND", "mock")


# ---------------------------------------------------------------------------
# Real dispatch path
# ---------------------------------------------------------------------------


def test_dispatch_reaches_pre_dispatch_and_activation_modules() -> None:
    """One real dispatch must bump 4 module families and wire 8 fibers."""
    before = {
        "task_scale_gate": task_scale_gate.get_call_counter_er(),
        "order_chain_detector": order_chain_detector.get_call_counter_er(),
        "module_fiber": module_fiber.get_call_counter_er(),
        "gather_core": gather_core.get_call_counter_gather(),
    }

    dispatcher = _dispatch_task("Design a microservice architecture with a security review and test strategy")

    assert task_scale_gate.get_call_counter_er() > before["task_scale_gate"]
    assert order_chain_detector.get_call_counter_er() > before["order_chain_detector"]
    assert module_fiber.get_call_counter_er() > before["module_fiber"]
    assert gather_core.get_call_counter_gather() > before["gather_core"]

    # ModuleFiber: the dispatcher registered the wired module set.
    assert len(dispatcher._module_fiber_registry.all_fibers()) == 8

    # CoeffectResolver: topological activation order was resolved during dispatch.
    order = dispatcher._coeffect_resolver.resolve_activation_order()
    assert "artifact_store" in order
    assert order.index("effect_registry") < order.index("artifact_store")


def test_task_scale_gate_dual_counter_increases_on_each_dispatch() -> None:
    """``TaskScaleGate_dual`` shares the scale-gate counter: two dispatches, +2."""
    before = task_scale_gate.get_call_counter_er()
    _dispatch_task("Design the service architecture")
    _dispatch_task("Review the service architecture")
    assert task_scale_gate.get_call_counter_er() - before >= 2


def test_worker_execute_persists_artifact_and_registers_effect() -> None:
    """The coordinator's worker API must reach ArtifactStore and EffectRegistry."""
    # Unique per run: effect ids derive from the artifact, so a fixed task_id
    # would collide with an effect left on the stack by an earlier test.
    task_id = f"selfcall-realpath-worker-{uuid.uuid4().hex[:8]}"
    artifact_dir = PROJECT_ROOT / "artifacts" / task_id
    before_artifacts = artifact_store.get_call_counter_er()
    # The registry is a process-global singleton: its constructor counter does
    # not move once created, so assert on the effect stack instead.
    registry = artifact_store._get_global_registry()
    before_pending = registry.pending_count()

    try:
        worker = WorkerFactory.create(
            "w-architect",
            "architect",
            "You are an architect",
            Scratchpad(),
            llm_backend=MockBackend(),
        )
        result = worker.execute(
            TaskDefinition(
                task_id=task_id,
                description="Design the login flow",
                role_id="architect",
            )
        )
    finally:
        shutil.rmtree(artifact_dir, ignore_errors=True)

    assert result.success
    assert result.output["finding_summary"], "worker must produce a finding to persist"
    assert artifact_store.get_call_counter_er() > before_artifacts
    assert registry.pending_count() > before_pending
    assert effect_registry.get_call_count() > 0, "registry must have been constructed"


# ---------------------------------------------------------------------------
# Real CLI path
# ---------------------------------------------------------------------------


def test_cli_modules_status_reaches_modules_cli(monkeypatch, capsys) -> None:
    """``devsquad modules status`` runs the module CLI against a real registry."""
    before = module_fiber.get_call_counter_er()
    rc, out = _run_cli(["modules", "status"], monkeypatch, capsys)

    assert rc == 0
    assert "MODULE" in out and "STATE" in out
    assert module_fiber.get_call_counter_er() > before


def test_cli_backend_get_reaches_backend_config(monkeypatch, capsys) -> None:
    """``devsquad backend get`` resolves the persisted backend configuration."""
    before = backend_config._call_counter_er
    rc, out = _run_cli(["backend", "get"], monkeypatch, capsys)

    assert rc == 0
    assert out.strip()
    assert backend_config._call_counter_er > before


def test_cli_risks_add_reaches_mutators_store_and_stats(tmp_path: Path, monkeypatch, capsys) -> None:
    """``devsquad risks add`` writes through FileRiskStore + stats instrumentation."""
    root = tmp_path / "risks"
    before_cli = risks_cli_counter()
    before_store = file_risk_store_counter()
    before_stats = risk_store_stats_counter()

    rc, out = _run_cli(
        [
            "risks",
            "add",
            "Demo risk",
            "--probability",
            "0.5",
            "--impact",
            "0.8",
            "--category",
            "tech",
            "--owner",
            "alice",
            "--root",
            str(root),
            "--register-id",
            "real-path",
        ],
        monkeypatch,
        capsys,
    )

    assert rc == 0
    assert '"id": "R-' in out
    assert risks_cli_counter() > before_cli  # CliRisksMutators_V458.2
    assert file_risk_store_counter() > before_store  # FileRiskStore_V458.1
    assert risk_store_stats_counter() > before_stats  # RiskStoreStats_V4512.1


def test_cli_risks_list_reaches_cli_risks(tmp_path: Path, monkeypatch, capsys) -> None:
    """``devsquad risks list`` reads the persisted register through CliRisks."""
    root = tmp_path / "risks"
    _run_cli(
        [
            "risks",
            "add",
            "Listed risk",
            "--probability",
            "0.4",
            "--impact",
            "0.6",
            "--category",
            "tech",
            "--owner",
            "bob",
            "--root",
            str(root),
            "--register-id",
            "real-path",
        ],
        monkeypatch,
        capsys,
    )

    before = risks_cli_counter()
    rc, out = _run_cli(
        [
            "risks",
            "list",
            "--format",
            "json",
            "--root",
            str(root),
            "--register-id",
            "real-path",
        ],
        monkeypatch,
        capsys,
    )

    assert rc == 0
    assert "Listed risk" in out
    assert risks_cli_counter() > before  # CliRisks_P12.5.2


def test_cli_risks_stats_reaches_stats_cli(tmp_path: Path, monkeypatch, capsys) -> None:
    """``devsquad risks stats`` selects the RisksStatsCli handler."""
    root = tmp_path / "risks"
    _run_cli(
        [
            "risks",
            "add",
            "Stats risk",
            "--probability",
            "0.3",
            "--impact",
            "0.9",
            "--category",
            "tech",
            "--owner",
            "carol",
            "--root",
            str(root),
            "--register-id",
            "real-path",
        ],
        monkeypatch,
        capsys,
    )

    before = risks_cli_counter()
    rc, out = _run_cli(
        ["risks", "stats", "--root", str(root), "--register-id", "real-path"],
        monkeypatch,
        capsys,
    )

    assert rc == 0
    assert "Risk Store Stats" in out
    assert risks_cli_counter() > before  # RisksStatsCli_V4512.2


# ---------------------------------------------------------------------------
# Real backend factory path
# ---------------------------------------------------------------------------


def test_backend_factory_builds_moka_backend() -> None:
    """``create_backend("moka")`` selects MokaAIBackend and its availability probe runs."""
    before = moka_backend.get_call_counter_er()
    backend = create_backend("moka", api_key="offline-test-key")

    assert type(backend).__name__ == "MokaAIBackend"
    assert backend.is_available() is True
    assert moka_backend.get_call_counter_er() > before


def test_backend_factory_builds_host_bridge_v2(tmp_path: Path, monkeypatch) -> None:
    """Default host backend is HostBridgeBackendV2 and completes a v2 round-trip."""
    monkeypatch.setenv("TRAE_ENV", "1")
    before_v2 = host_llm_bridge_v2.get_call_counter_er()

    backend = create_backend("host", bridge_dir=str(tmp_path / "bridge_v2"))

    # HostBridgeV2Wiring_V4510.1: the factory returns the v2 adapter.
    assert type(backend).__name__ == "HostBridgeBackendV2"
    runner = FakeHostRunnerV2(backend.bridge.bridge_dir, behaviour="success", poll_interval=0.01)
    with _fake_host_thread(runner):
        output = backend.generate("ping")

    assert "FAKE HOST V2" in output
    assert host_llm_bridge_v2.get_call_counter_er() > before_v2


def test_backend_factory_builds_legacy_host_bridge_v1(tmp_path: Path, monkeypatch) -> None:
    """Rollback flag selects HostBridgeBackend (v1) and completes a v1 round-trip."""
    monkeypatch.setenv("TRAE_ENV", "1")
    monkeypatch.setenv("DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2", "1")
    before_v1 = host_llm_bridge.get_call_counter_er()

    backend = create_backend("host", bridge_dir=str(tmp_path / "bridge_v1"))

    assert type(backend).__name__ == "HostBridgeBackend"
    runner = FakeHostRunner(backend.bridge.bridge_dir, behaviour="success", poll_interval=0.01)
    with _fake_host_thread(runner):
        output = backend.generate("ping")

    assert "FAKE HOST" in output
    assert host_llm_bridge.get_call_counter_er() > before_v1


def test_auto_fallback_chain_classifies_host_failure(tmp_path: Path, monkeypatch) -> None:
    """A failing host bridge is classified and degrades to the mock tail."""
    monkeypatch.setenv("TRAE_ENV", "1")
    monkeypatch.delenv("MOKA_API_KEY", raising=False)
    monkeypatch.delenv("DEVSQUAD_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEVSQUAD_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm_backend, "_moka_file_config", lambda: {})

    before = backend_paths.get_call_counter_er()
    chain = create_backend("auto-fallback", bridge_dir=str(tmp_path / "bridge"), timeout_seconds=5)
    assert isinstance(chain, FallbackBackend)

    host_backend = next(b for b in chain._backends if "Host" in type(b).__name__)
    runner = FakeHostRunnerV2(host_backend.bridge.bridge_dir, behaviour="fail", poll_interval=0.01)
    with _fake_host_thread(runner):
        output = chain.generate("ping")

    assert "[MOCK MODE]" in output, "failing host bridge must degrade to the mock tail"
    assert backend_paths.get_call_counter_er() > before


# ---------------------------------------------------------------------------
# Real maintainer script path
# ---------------------------------------------------------------------------


def test_collect_baseline_script_reaches_perf_baseline(tmp_path: Path, monkeypatch) -> None:
    """``scripts/collect_baseline.py`` measures the mock path via PerfBaseline."""
    # The host/API branches would reach the network on a developer machine.
    # Stub them exactly as the script does when credentials are absent.
    monkeypatch.setattr(
        collect_baseline_module,
        "_collect_api",
        lambda: (
            collect_baseline_module._collect_stub("api", collect_baseline_module.SAMPLE_COUNTS["api"], 1500.0, 400.0),
            "no provider credentials configured",
        ),
    )
    monkeypatch.setattr(
        collect_baseline_module,
        "_collect_host",
        lambda: (
            collect_baseline_module._collect_stub("host", collect_baseline_module.SAMPLE_COUNTS["host"], 200.0, 80.0),
            False,
        ),
    )
    out_path = tmp_path / "perf_baseline.json"
    monkeypatch.setattr(collect_baseline_module, "DEFAULT_BASELINE_PATH", str(out_path))

    before = perf_baseline.get_call_counter_er()
    rc = collect_baseline_module.main()

    assert rc == 0
    assert out_path.exists()
    assert perf_baseline.get_call_counter_er() > before


def test_cli_audit_reaches_audit_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """`devsquad audit` must run cmd_audit(), not print help."""
    # V4.10.0: the subparser registered func=cmd_audit, but _dispatch_args()
    # had no 'audit' branch, so the handler never ran. Regression guard.
    db_path = tmp_path / "dispatch_audit.db"
    before = audit_cli_counter()

    rc, out = _run_cli(["audit", "--limit", "1", "--db-path", str(db_path)], monkeypatch, capsys)

    assert rc == 0
    assert audit_cli_counter() == before + 1
    assert out.strip(), "audit must print a result, not the generic help"


# ---------------------------------------------------------------------------
# Documented gaps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_name,evidence", UNREACHABLE_MODULES)
def test_unreachable_modules_are_documented(module_name: str, evidence: str) -> None:
    """No user path reaches these modules today; see the reason string."""
    pytest.xfail(f"{module_name}: {evidence}")
