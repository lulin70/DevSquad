#!/usr/bin/env python3
"""
check_module_activation.py — V4.5.3 Anti-Ghost CI gate.

Verifies that all V4.5.3 modules' _call_counter_er is > 0 after a representative
dispatch. Used by CI to block releases of ghost modules.

V4.5.2 P12.1: Extended to include:
    - MokaAIBackend (P12.1.1)
    - GitLabConnector (P12.1.3)
    - BackendConfig (P12.1.5)

V4.5.3 P12.2: Extended to include:
    - ArtifactStore (P12.2.1)
    - DispatchEffect Protocol (P12.2.3)
    - EffectRegistry (P12.2.4)
    - Audit CLI (P12.2.6)

V4.5.4 P12.3: Extended to include:
    - ModuleFiber (P12.3.1)
    - CoeffectResolver (P12.3.2)
    - ModulesCLI (P12.3.3)

V4.5.8: Extended to include:
    - FileRiskStore (file-backed risk persistence)
    - CliRisks mutators (add/mitigate/close/list --min-exposure)

V4.5.9: Extended to include:
    - GatherCore (shared asyncio.gather execution core, _call_counter_gather)

V4.5.13: Extended to include previously-scanned but unverified counters:
    - ApprovalGate (V4.5.1 V451-1) — request_approval (auto-approve path)
    - ConnectorFramework (V4.5.1 V451-2) — GitHubConnector simulation probe
    - DoraMetricsCollector (V4.4.0 P2-1) — collect_from_dispatch
    - GapAnalyzer (V4.4.0 P1-2) — add_gap + analyze
    - ErrorBudgetTracker (V4.4.0 P1-1) — calculate + status
    - RiskRegister (V4.4.0 P0-1) — add + assess + export_markdown
    - FileBundler (V4.5.0) — bundle (deterministic grouping)
    - ScratchpadHistoryStore (V4.4.3) — write + search_history

V4.5.13: Verified HostLLMBridge v1 counter is wired into HostLLMBridge
    (file-backed protocol in logs/host_llm_bridge/v1) — previously only
    HostBridgeBackend/HostBridgeBackendV2 + v2 were probed, leaving v1
    ghost-prone. Direct create_request() into a temp bridge_dir now bumps
    both v1 and v2 counters.

V4.5.20 (D7): the ``counter > 0`` assertion was vacuous — this gate bumped the
    counters itself, so a module with no production caller still passed. A
    production probe (real ``dispatch()`` calls, ``auto`` + ``review``) now runs
    *before* any direct call; modules listed in ``PRODUCTION_WIRED_COUNTERS``
    must be bumped by that probe or they are reported as
    ``FAIL (self-call only)`` and the gate fails. All other entries keep their
    legacy semantics but are reported as ``PASS (self-call)`` so the report no
    longer implies production evidence it does not have.

V4.5.20 (F4 delivery requirement 4): test discipline — an e2e test whose *name*
    claims activation/wiring must reach a production entry point; a test that
    only imports the module and calls it directly is exactly the "名为 e2e 实
    为直接 import" defect that hid F4 for nineteen releases. The
    ``find_unbacked_activation_claims`` scan below reports such tests and fails
    the gate.

Usage:
    python3 scripts/check_module_activation.py
    CI: python3 scripts/check_module_activation.py || exit 1
"""

from __future__ import annotations

import ast
import contextlib
import os
import re
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, ".")

# V4.5.20 (D7): counters that must be bumped by a *production pipeline entry
# point*, not by this gate's own direct calls.
#
# Why this exists: until V4.5.19 the gate called every module directly and then
# asserted ``_call_counter_er > 0``. The gate satisfied its own assertion, so
# the check was vacuous — which is exactly how ``FileBundler_V450`` stayed
# green for nineteen releases while ``Coordinator.apply_file_bundling`` had no
# production caller (finding F4). The production probe below runs *before* any
# direct call, so a counter already > 0 at that point can only have been bumped
# by production code.
#
# Keys are the report names used in ``counters``; values are the module paths
# whose ``_call_counter_er`` attribute is read. Only modules whose documented
# claim is "this runs inside the dispatch pipeline" belong here.
PRODUCTION_WIRED_COUNTERS: dict[str, str] = {
    "DoraMetricsCollector_V440.P2.1": "scripts.collaboration.dora_metrics_collector",
    "GapAnalyzer_V440.P1.2": "scripts.collaboration.gap_analyzer",
    "ErrorBudgetTracker_V440.P1.1": "scripts.collaboration.error_budget_tracker",
    "RiskRegister_V440.P0.1": "scripts.collaboration.risk_register",
    "ScratchpadHistoryStore_V443": "scripts.collaboration.scratchpad_history_store",
    "ApprovalGate_V451.1": "scripts.collaboration.approval_gate",
    "ConnectorFramework_V451.2": "scripts.collaboration.connector_framework",
    "FileBundler_V450": "scripts.collaboration.file_bundler",
}

# 6 files across 3 directories — exceeds the ``len(files) > 5`` guard inside
# ``apply_file_bundling`` so the review-mode probe yields >= 2 bundles.
REVIEW_PROBE_CHANGESET: list[str] = [
    "src/pkg_0/mod_0.py",
    "src/pkg_0/mod_1.py",
    "src/pkg_0/mod_2.py",
    "src/pkg_1/mod_3.py",
    "src/pkg_1/mod_4.py",
    "src/pkg_2/mod_5.py",
]


# V4.5.20 (F4 delivery requirement 4): an e2e test whose name claims
# activation/wiring must actually reach a production entry point. Names are the
# user-visible claim; the body is the evidence.
E2E_TEST_DIR = Path("tests/e2e")
ACTIVATION_CLAIM_RE = re.compile(
    r"activates?|_wired|anti_ghost|production|increments?.{0,20}counter",
    re.IGNORECASE,
)
# Concrete entry points a claim may be backed by:
#   * ``dispatch`` / ``MultiAgentDispatcher`` / ``AsyncCoordinator`` — the
#     dispatch pipeline itself (``AsyncCoordinator`` handles the async path).
#   * ``Scratchpad`` — the cross-session production surface used by the
#     V4.4.3 modules, which are not reached through ``dispatch()``.
#   * ``subprocess`` running this gate — the anti-ghost tests verify the gate.
PRODUCTION_ENTRY_FUNC_NAMES = frozenset({
    "dispatch",
    "MultiAgentDispatcher",
    "AsyncMultiAgentDispatcher",
    "AsyncCoordinator",
    "Scratchpad",
})
PRODUCTION_ENTRY_SUBPROCESS_TARGET = "check_module_activation"
_PRODUCTION_ENTRY_CALL_ATTRS = frozenset({"dispatch", "dispatch_sync"})
_SUBPROCESS_CALL_ATTRS = frozenset({"run", "check_output", "Popen", "call"})


def _referenced_names(node: ast.AST) -> set[str]:
    """Collect every Name/Attribute/arg identifier referenced inside ``node``."""
    found: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            found.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            found.add(sub.attr)
        elif isinstance(sub, ast.arg):
            found.add(sub.arg)
            if sub.annotation is not None:
                found |= _referenced_names(sub.annotation)
    return found


def _reaches_production_entry(fn: ast.FunctionDef) -> bool:
    """Return True if ``fn`` can reach a production entry point.

    Only real call sites / references count — a mention inside a docstring or a
    string literal does not, which is what makes this check non-vacuous.
    """
    if _referenced_names(fn) & PRODUCTION_ENTRY_FUNC_NAMES:
        return True
    for sub in ast.walk(fn):
        if not isinstance(sub, ast.Call):
            continue
        attr = getattr(sub.func, "attr", None)
        if attr in _PRODUCTION_ENTRY_CALL_ATTRS:
            return True
        if attr in _SUBPROCESS_CALL_ATTRS and (
            PRODUCTION_ENTRY_SUBPROCESS_TARGET in ast.unparse(sub)
        ):
            return True
    return False


def find_unbacked_activation_claims(
    root: Path | None = None,
) -> list[tuple[str, str]]:
    """Find e2e tests whose activation claim has no production entry point.

    Args:
        root: Directory holding e2e test files. Defaults to ``tests/e2e``
            relative to the current working directory.

    Returns:
        Sorted list of ``(relative file path, test function name)`` pairs for
        tests that claim activation yet never reach a production entry point.
        Files that cannot be parsed are skipped — a syntax error is pytest's
        problem, not this gate's.
    """
    search_root = root if root is not None else E2E_TEST_DIR
    violations: list[tuple[str, str]] = []
    for path in sorted(search_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            if not ACTIVATION_CLAIM_RE.search(node.name):
                continue
            if not _reaches_production_entry(node):
                violations.append((str(path.relative_to(search_root.parent.parent)), node.name))
    return sorted(violations)


def _production_probe() -> dict[str, int]:
    """Run real dispatch pipelines and report the counters they bumped.

    Dispatch is the production entry point (``MultiAgentDispatcher.dispatch``),
    not a module-level API call, so the deltas returned here are evidence that
    a counter is reachable from an executing pipeline.

    ``auto`` covers the V4.4.0/V4.4.3 collectors wired in the dispatch epilogue;
    ``review`` covers the V4.5.0 file bundler wired in W0-3.

    Returns:
        Mapping of report name → counter delta caused by the probe. A 0 means
        the production path did not reach that module.
    """
    import importlib

    names = list(PRODUCTION_WIRED_COUNTERS)

    def _read() -> dict[str, int]:
        return {
            name: getattr(
                importlib.import_module(PRODUCTION_WIRED_COUNTERS[name]),
                "_call_counter_er",
                0,
            )
            for name in names
        }

    before = _read()
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    dispatcher = MultiAgentDispatcher(enable_warmup=False)
    try:
        dispatcher.dispatch("anti-ghost production probe", mode="auto")
        dispatcher.dispatch(
            "anti-ghost production probe",
            mode="review",
            changeset=list(REVIEW_PROBE_CHANGESET),
        )
    except Exception as exc:  # noqa: BLE001 — surfaced as counter deltas, not raised
        print(f"  [warn] production probe failed: {exc!r}")
    finally:
        dispatcher.shutdown()
    after = _read()
    return {name: after[name] - before[name] for name in names}


def main() -> int:
    """Check all V4.5.2 modules' _call_counter_er > 0.

    Returns:
        0 if all modules activated (anti-ghost pass).
        1 if any module's counter is 0 (ghost detected).
    """
    # V4.5.20 (D7): production probe FIRST — before any direct module call, so
    # the deltas it measures cannot be contaminated by this gate's own probing.
    production_counts = _production_probe()

    # Touch each module + ensure counter is exposed via get_call_counter
    from scripts.collaboration import dora_metrics_collector as _dora_module
    from scripts.collaboration import error_budget_tracker as _error_budget_module
    from scripts.collaboration import file_bundler as _file_bundler_module
    from scripts.collaboration import gap_analyzer as _gap_module
    from scripts.collaboration import risk_register as _risk_register_module
    from scripts.collaboration import scratchpad_history_store as _scratchpad_module
    from scripts.collaboration.approval_gate import (
        get_call_count as agc,
    )
    from scripts.collaboration.backend_config import get_call_count as bcc
    from scripts.collaboration.backend_config import (
        load_backend_config,
        resolve_backend,
    )
    from scripts.collaboration.backend_paths import classify_error
    from scripts.collaboration.backend_paths import get_call_counter_er as bp
    from scripts.collaboration.connector_framework import (
        get_call_count as cfc,
    )
    from scripts.collaboration.gitlab_connector import GitLabConnector
    from scripts.collaboration.gitlab_connector import get_call_count as glc

    # Activate each module (representative call)
    from scripts.collaboration.host_llm_bridge import get_call_counter_er as hbb
    from scripts.collaboration.moka_backend import MokaAIBackend

    # V4.5.2 P12.1 modules
    from scripts.collaboration.moka_backend import get_call_counter_er as mok
    from scripts.collaboration.order_chain_detector import OrderChainDetector
    from scripts.collaboration.order_chain_detector import get_call_counter_er as ocd
    from scripts.collaboration.perf_baseline import PerfSampleCollector
    from scripts.collaboration.perf_baseline import get_call_counter_er as pb
    from scripts.collaboration.task_scale_gate import TaskScaleGate
    from scripts.collaboration.task_scale_gate import get_call_counter_er as tsg

    TaskScaleGate().decide("anti-ghost check")
    OrderChainDetector().detect("anti-ghost check")
    classify_error(TimeoutError("test"))

    col = PerfSampleCollector("mock")
    for i in range(10):
        col.add_sample(float(i))
    col.snapshot()

    # P12.1.1: MokaAIBackend — exercise is_available() to bump counter
    moka_backend = MokaAIBackend(api_key="anti-ghost-test-key")
    moka_backend.is_available()

    # P12.1.3: GitLabConnector — exercise create_mr_comment in simulation mode
    # (simulation=True guarantees no real GitLab API calls)
    gitlab = GitLabConnector(simulation=True)
    gitlab.create_mr_comment(project="anti-ghost/test", mr_iid=1, body="ghost check")

    # P12.1.5: BackendConfig — exercise resolve_backend + load_backend_config
    resolve_backend()
    load_backend_config()

    # HostBridgeBackend: counter is bumped by create_request().
    # Verify wiring via create_backend() which imports HostBridgeBackend internally.
    import os
    from unittest.mock import patch
    old_env = {
        k: os.environ.pop(k, None)
        for k in (
            "TRAE_ENV", "CLAUDE_CODE_ENV", "TRAE_AGENT_PATH", "ANTHROPIC_ENV",
            "DEVSQUAD_OPENAI_API_KEY", "DEVSQUAD_ANTHROPIC_API_KEY",
            "MOKA_API_KEY", "DEVSQUAD_LLM_BACKEND",
        )
    }
    try:
        with patch("scripts.collaboration.llm_backend._load_dotenv"):
            from scripts.collaboration.host_llm_bridge import HostLLMBridge
            from scripts.collaboration.llm_backend import create_backend
            # Exercise both create_backend (auto-fallback path) and a direct bridge
            # construction to ensure the module is wired into the resolution chain.
            create_backend("mock")  # C path
            bridge = HostLLMBridge(bridge_dir=None)
            # Directly invoke create_request — this is the only path that bumps
            # _call_counter_er in production code (generate() calls it internally).
            with contextlib.suppress(OSError, ValueError):
                # Bridge dir may not exist; the counter bump happens BEFORE that.
                bridge.create_request(
                    agent_type="anti-ghost",
                    task="anti-ghost check",
                    context={},
                    prompt="test prompt",
                )
    finally:
        for k, v in old_env.items():
            if v is not None:
                os.environ[k] = v

    # V4.5.13: HostLLMBridge v1 counter is bumped by HostLLMBridge.create_request
    # (the v1 protocol class itself, not just the V2 backend). The block above
    # already exercises that path via the unsuppressed HostLLMBridge instance,
    # but we add a deterministic tempdir probe so the gate fails closed if the
    # v1 wiring regresses (default bridge_dir depends on project root layout).
    with tempfile.TemporaryDirectory() as v1_tmp:
        v1_bridge = HostLLMBridge(bridge_dir=str(Path(v1_tmp) / "v1"))
        v1_bridge.create_request(
            agent_type="anti-ghost-v1",
            task="anti-ghost v1 counter check",
            context={},
            prompt="v1 counter probe",
        )

    # V4.5.3 P12.2 modules — touch counters in main scope so they survive module-level imports
    from scripts.cli_audit import get_call_counter_er as au_call_counter_er

    # V4.5.7 P12.5 modules — touch counters in main scope
    from scripts.cli_risks import get_call_counter_er as _get_cli_risks_counter_er
    from scripts.collaboration.artifact_store import (
        get_call_counter_er as as_call_counter_er,
    )
    from scripts.collaboration.async_coeffect_resolver import (
        get_call_counter_er as _get_async_coeffect_counter_er,
    )

    # V4.5.6 P12.4 modules — touch counters in main scope
    from scripts.collaboration.dispatcher_intent_mapper import (
        get_call_counter_er as _get_intent_counter_er,
    )
    from scripts.collaboration.dispatcher_loop_controller import (
        get_call_counter_er as _get_loop_counter_er,
    )
    from scripts.collaboration.dispatcher_transaction import (
        get_call_counter_er as _get_tx_counter_er,
    )
    from scripts.collaboration.effect_registry import (
        get_call_count as er_call_count,
    )
    from scripts.collaboration.host_llm_bridge_v2 import (
        get_call_counter_er as _get_call_counter_er_v2,
    )

    # V4.5.4 P12.3 modules — touch counters in main scope
    from scripts.collaboration.module_fiber import (
        get_call_counter_er,
    )

    # V4.5.3 P12.2 activation (ArtifactStore + EffectRegistry + DispatchEffect + AuditCLI)
    _activate_v453_modules()

    # V4.5.4 P12.3 activation
    _activate_v454_modules()

    # V4.5.6 P12.4 activation (4 new modules)
    _activate_v455_modules()

    # V4.5.8 modules — touch counters in main scope
    from scripts.collaboration.file_risk_store import (
        get_call_counter_er as _get_file_risk_store_counter_er,
    )

    # V4.5.9 modules — touch counters in main scope
    from scripts.collaboration.gather_core import (
        get_call_counter_gather as _get_gather_counter,
    )

    # V4.5.7 P12.5 activation (2 new modules)
    _activate_v457_modules()

    # V4.5.8 activation (FileRiskStore + CliRisks mutators)
    _activate_v458_modules()

    # V4.5.9 activation (GatherCore — shared asyncio.gather execution core)
    _activate_v459_modules()

    # V4.5.10 activation (HostBridge v2 production wiring)
    v4510_wiring = _activate_v4510_modules()

    # V4.5.12 activation (RiskStoreStats + risks stats CLI)
    _activate_v4512_modules()

    # V4.5.12 stats counter — touched in main scope
    from scripts.collaboration.file_risk_store import (
        get_risk_store_stats_counter_er as _get_risk_store_stats_counter_er,
    )

    # V4.5.13 activation: 8 previously-scanned but unverified counters
    _activate_v4513_modules()

    # V4.5.13 module-scope helpers — read each counter off the live module
    # attribute (never snapshot via ``from … import _call_counter_er``, which
    # would freeze the int at import time and break the monotonic guarantee
    # established in L-V454-004).
    def _get_dora_counter() -> int:
        return _dora_module._call_counter_er

    def _get_gap_counter() -> int:
        return _gap_module._call_counter_er

    def _get_error_budget_counter() -> int:
        return _error_budget_module._call_counter_er

    def _get_risk_register_counter() -> int:
        return _risk_register_module._call_counter_er

    def _get_file_bundler_counter() -> int:
        return _file_bundler_module._call_counter_er

    def _get_scratchpad_counter() -> int:
        return _scratchpad_module._call_counter_er

    counters = {
        "TaskScaleGate": tsg(),
        "PerfBaseline": pb(),
        "HostLLMBridge": hbb(),
        "BackendPaths": bp(),
        "TaskScaleGate_dual": tsg(),
        "OrderChainDetector": ocd(),
        "MokaAIBackend_P12.1.1": mok(),
        "GitLabConnector_P12.1.3": glc(),
        "BackendConfig_P12.1.5": bcc(),
        # V4.5.3 P12.2 modules
        "ArtifactStore_P12.2.1": as_call_counter_er(),
        "EffectRegistry_P12.2.4": er_call_count(),
        "AuditCLI_P12.2.6": au_call_counter_er(),
        # V4.5.4 P12.3 modules
        "ModuleFiber_P12.3.1": get_call_counter_er(),
        "CoeffectResolver_P12.3.2": get_call_counter_er(),  # shared counter
        "ModulesCLI_P12.3.3": get_call_counter_er(),  # shared counter
        # V4.5.6 P12.4 modules
        "HostLLMBridgeV2_P12.4.1": _get_call_counter_er_v2(),
        "DispatcherTransaction_P12.4.2": _get_tx_counter_er(),
        "IntentWorkflowMapper_P12.4.3": _get_intent_counter_er(),
        "DispatchLoopController_P12.4.4": _get_loop_counter_er(),
        # V4.5.7 P12.5 modules
        "AsyncCoeffectResolver_P12.5.1": _get_async_coeffect_counter_er(),
        "CliRisks_P12.5.2": _get_cli_risks_counter_er(),
        # V4.5.8 modules
        "FileRiskStore_V458.1": _get_file_risk_store_counter_er(),
        "CliRisksMutators_V458.2": _get_cli_risks_counter_er(),
        # V4.5.9 modules
        "GatherCore_V459.1": _get_gather_counter(),
        # V4.5.10 modules
        "HostBridgeV2Wiring_V4510.1": v4510_wiring,
        # V4.5.12 modules
        "RiskStoreStats_V4512.1": _get_risk_store_stats_counter_er(),
        "RisksStatsCli_V4512.2": _get_cli_risks_counter_er(),
        # V4.5.13 previously-scanned counters
        "ApprovalGate_V451.1": agc(),
        "ConnectorFramework_V451.2": cfc(),
        "DoraMetricsCollector_V440.P2.1": _get_dora_counter(),
        "GapAnalyzer_V440.P1.2": _get_gap_counter(),
        "ErrorBudgetTracker_V440.P1.1": _get_error_budget_counter(),
        "RiskRegister_V440.P0.1": _get_risk_register_counter(),
        "FileBundler_V450": _get_file_bundler_counter(),
        "ScratchpadHistoryStore_V443": _get_scratchpad_counter(),

    }

    print("V4.5.13 Anti-Ghost Verification")
    print("=" * 60)
    failed = []
    self_call_only = []
    production_verified = 0
    for name, count in counters.items():
        if name in production_counts:
            # D7 discriminator: the assertion is only meaningful when the bump
            # came from the production probe, not from this gate's direct call.
            # The absolute count is still checked — a non-positive counter means
            # the monotonic contract (L-V454-004) was violated, which must fail
            # closed even when the production delta looks healthy.
            delta = production_counts[name]
            if delta <= 0:
                status = "FAIL (self-call only)"
                failed.append(name)
                self_call_only.append(name)
            elif count <= 0:
                status = f"FAIL (non-positive counter={count})"
                failed.append(name)
            else:
                production_verified += 1
                status = f"PASS (production +{delta})"
        else:
            # No production claim for this module — the assertion remains
            # gate-driven. Reported as such rather than silently counted as
            # production evidence.
            status = "PASS (self-call)" if count > 0 else "FAIL (ghost)"
            if count <= 0:
                failed.append(name)
        print(f"  {name:25s}  counter={count:>4}  [{status}]")

    print("=" * 60)
    claim_violations = find_unbacked_activation_claims()
    if claim_violations:
        print(
            f"UNBACKED ACTIVATION CLAIMS: {len(claim_violations)} e2e test(s) "
            "claim activation without reaching a production entry point "
            "(F4 delivery requirement 4):"
        )
        for rel_path, test_name in claim_violations:
            print(f"  - {rel_path}::{test_name}")
    else:
        print(
            "Activation-claim scan: all e2e activation claims are backed by a "
            "production entry point."
        )

    if failed or claim_violations:
        if failed:
            print(f"GHOST DETECTED: {len(failed)} module(s) not activated:")
            for name in failed:
                print(f"  - {name}")
        if self_call_only:
            print(
                "The above FAIL (self-call only) modules are reachable only by "
                "this gate's own calls — the production pipeline never invokes "
                "them (D7 self-call blind spot)."
            )
        return 1

    print(
        f"Anti-ghost gate PASSED: {production_verified}/"
        f"{len(PRODUCTION_WIRED_COUNTERS)} production-verified, "
        f"{len(counters) - len(PRODUCTION_WIRED_COUNTERS)} self-call verified."
    )
    return 0


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
        next(iter(ga._gaps), "anti-ghost")
        if hasattr(ga, "_gaps") and ga._gaps
        else "anti-ghost"
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
            assert cmd_risks_stats(Namespace(
                register_id="default", root=root, format="json",
            )) == 0
        payload = _json.loads(buf.getvalue())
        assert payload["register_id"] == "default"
        with redirect_stdout(buf):
            assert cmd_risks_stats(Namespace(
                register_id="default", root=root, format="text",
            )) == 0
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
            add_rc = cmd_risks_add(Namespace(
                description="anti-ghost CLI risk",
                probability=0.6,
                impact=0.5,
                category="technical",
                owner="anti-ghost",
                register_id="default",
                root=risks_root,
            ))
        assert add_rc == 0

        # Recover the risk id from the persisted store.
        reader = FileRiskStore(root=risks_root)
        risk_id = next(iter(reader.payload_to_items(reader.load("default"))))

        with redirect_stdout(buf):
            assert cmd_risks_mitigate(Namespace(
                risk_id=risk_id,
                strategy="mitigate",
                owner="devops",
                plan="anti-ghost plan",
                register_id="default",
                root=risks_root,
            )) == 0

        # Close WITHOUT approval (require_approval=False → no gate).
        with redirect_stdout(buf):
            assert cmd_risks_close(Namespace(
                risk_id=risk_id,
                require_approval=False,
                register_id="default",
                root=risks_root,
            )) == 0

        # --min-exposure filter: high threshold hides every row, zero shows it.
        buf_hidden, buf_visible = io.StringIO(), io.StringIO()
        with redirect_stdout(buf_hidden):
            assert cmd_risks_list(Namespace(
                register_id="default", root=risks_root, format="md",
                min_exposure=0.99, category=None, limit=None,
            )) == 0
        assert "(none)" in buf_hidden.getvalue()
        with redirect_stdout(buf_visible):
            assert cmd_risks_list(Namespace(
                register_id="default", root=risks_root, format="md",
                min_exposure=0.0, category=None, limit=None,
            )) == 0
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
    store.write(
        "anti-ghost-session", "anti-ghost-role", "ghost.md", "anti-ghost content"
    )

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


if __name__ == "__main__":
    sys.exit(main())
