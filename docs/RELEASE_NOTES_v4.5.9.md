# Release Notes — v4.5.9

> **V4.5.9 — Unified Gather Execution Core + Native Async Worker（执行层统一 gather 化 + Worker 原生异步）**
> Released: 2026-08-29
> Commit: TBD (P9)
> Tag: TBD

---

## Summary

V4.5.9 merges the two backlogs deferred from V4.5.8 — `Coordinator._execute_parallel`
gather migration (originally V4.5.9) and `Worker` native async (originally V4.5.10) —
into a single release (user decision 2026-08-29). Splitting them would have produced
an intermediate state where gather bridges synchronous workers ("fake async"), so the
sync/async dual track is collapsed in one cycle.

Three-sage consensus gate: **8.9/10 ≥ 8.5 → PASS** (architect 9.2, tester 8.9,
security 9.0). Two hard constraints added by the gate: ① the gather core must have a
single source of truth; ② behavior-consistency contract tests are TDD-first (R4).

- **Wave 1 (P0)**: `gather_core.py` — shared `asyncio.gather` execution core
  (Semaphore + `return_exceptions=True` + submission order + BaseException defense)
- **Wave 2 (P0)**: `Worker.aexecute` / `_ado_work` — native async backend await,
  sync-backend `run_in_executor` bridge only at the Worker boundary
- **Wave 3 (P1)**: verification — 45 new tests, core 56 tests zero-modification gate,
  registered benchmark-test contract update

---

## Added

### `gather_core.py` — shared execution core (P0)

New module `scripts/collaboration/gather_core.py` with a single public coroutine:

| Aspect | Design |
|--------|--------|
| Concurrency cap | `asyncio.Semaphore(max_concurrency)` — default 10 preserved (AC-C5) |
| Fault isolation | `asyncio.gather(..., return_exceptions=True)` — one worker failure never drops sibling results (AC-C3 hard constraint) |
| Result order | submission order (`batch.tasks` order) — behavior change vs the old completion order, registered as PRD R1 |
| BaseException defense | task-wrapper layer converts `KeyboardInterrupt`/`SystemExit` into `WorkerResult(success=False)` (see Fixed: CPython bpo-32528) |
| Anti-ghost | module-level `_call_counter_gather`, asserted active by `check_module_activation.py` |

The core owns only the gather mechanism; worker routing / briefing / timeout / retry
stay in each coordinator's `run_one` callback injection point (no core bloat).

### `Worker.aexecute` — native async (P0)

- `async def aexecute(task)` mirrors `execute()` semantics; context building,
  Scratchpad writes, ArtifactStore persistence, and failure fallback are shared
  extracted helpers (single implementation — R4 anti-drift, AC-W1).
- Async backends (`AsyncLLMBackendInterface`: AsyncOpenAI / AsyncAnthropic,
  httpx.AsyncClient core) are awaited natively — no thread hop (AC-W2).
- Sync backends (Mock / HostBridge) bridge via `run_in_executor` — behavior
  byte-identical to the legacy path (AC-W3).
- `AsyncWorkerWrapper` prefers the native `aexecute` path; the legacy
  `run_in_executor` bridge remains only as fallback (AC-W4).

### Dispatch report executor marker

Execution stats expose `executor: "gather"` in the dispatch report — user-visible
evidence that the unified path is active (anti-ghost visibility rule).

---

## Changed

### `Coordinator._execute_parallel`: ThreadPoolExecutor → asyncio.gather

- Sync bridge: running-loop detection fails fast with an informative error when
  called inside a running event loop ("use AsyncCoordinator / async_dispatch",
  L-V457-002 pattern); otherwise `asyncio.run` enters the gather core (AC-C1, AC-C4).
- Sync API signature unchanged: `dispatch(task) → dispatch(task)` — callers need
  zero changes (AC-C2, enforced by the core-56 zero-modification gate).
- Failure semantics preserved: a failed task yields
  `WorkerResult(success=False, worker_id="unknown", error=...)` exactly as before.

### `AsyncCoordinator._execute_parallel_async` delegates to the shared core

The gather mechanism (Semaphore + gather + per-task catch) is replaced by a
`execute_batch_gather()` call; the `_execute_with_semaphore` shell keeps its
timeout / retry / briefing behavior. **71 existing tests pass with zero
modifications** — the proof of refactor correctness.

### Thread-pool lifecycle removed

`self._executor` and the executor-shutdown branch are removed; `shutdown()` keeps
its remaining responsibilities. Registered change (PRD R2).

---

## Fixed

### CPython bpo-32528 (discovered by real E2E)

Real E2E runs surfaced that `asyncio.gather(return_exceptions=True)` does **not**
capture `KeyboardInterrupt` / `SystemExit` raised inside child tasks (CPython
bpo-32528). The initial design placed the BaseException defense in the gather core;
it was moved to the per-task wrapper layer, where the exit-type exceptions are
converted into `WorkerResult(success=False)`. The gather core semantics stay clean
and the defense applies to both coordinators.

---

## Known Behavior Changes

| Change | Impact | Reference |
|--------|--------|-----------|
| Parallel result order: completion order → submission order | Callers relying on completion order must read results by `task_id` instead of position | PRD R1 |
| `Coordinator._executor` attribute removed | External code touching the private `_executor` attribute or thread-pool `shutdown` semantics must migrate | PRD R2 |
| Sync bridge raises inside a running event loop | Jupyter / async hosts must call `async_dispatch` instead of `dispatch` | PRD R3 |

No breaking API changes: `dispatch()` / `async_dispatch()` signatures are unchanged.

---

## Verification

| Gate | Status |
|------|--------|
| New test suite | 172 collected, **169 passed** ✅ (45 new: 15 gather unit + 14 worker-async unit + 9 integration + 2 E2E + 5 contract; remainder = registered contract updates) |
| Regression | core 56 tests zero-modification PASS (AC-C2); AsyncCoordinator 71 tests zero-modification PASS; **full regression 9408 passed, 0 failed** ✅ (first pass caught the API async-endpoint flaw, fixed in `scripts/api/routes/dispatch.py`, then re-run clean) |
| Anti-ghost | `check_module_activation.py` — GatherCore_V459.1 PASS ✅ |
| CLI real-user journeys | Journey A sync `dispatch` (gather bridge) + Journey B `DEVSQUAD_USE_ASYNC=1` async journey — both exit 0 with full 7-role reports and `executor: gather` ✅ |
| Concurrency stress | 50 concurrent tasks × {AsyncOpenAI mock transport, Mock} × {sync bridge, native async} — no deadlock, no result loss, Semaphore cap respected ✅ |

---

## Upgrade Notes

- **No breaking API changes.** `dispatch()`, `async_dispatch()`, `Worker.execute()`
  signatures are unchanged; the sync path remains the default.
- The private `Coordinator._executor` attribute and its thread-pool `shutdown`
  lifecycle are gone. If your tooling inspected this private attribute, switch to
  the dispatch report's `executor` marker.
- Inside a running event loop (Jupyter, async hosts), `Coordinator._execute_parallel`
  now raises an informative error instead of deadlocking — use `async_dispatch`.
- `test_thread_pool_reuse` was rewritten as a gather concurrency contract
  (`tests/test_performance_benchmarks.py`); the change is registered per
  PRD V4.5.9 §3.3.

---

## Files Changed

### New

- `scripts/collaboration/gather_core.py`
- `tests/unit/test_v459_gather_core.py` (15)
- `tests/unit/test_v459_worker_async.py` (14)
- `tests/integration/test_v459_async_pipeline.py` (9)
- `tests/e2e/test_v459_real_user_journey.py` (2)
- `tests/contract/test_v459_backend_contract.py` (5)
- `docs/RELEASE_NOTES_v4.5.9.md` (this file)

### Modified

- `scripts/collaboration/coordinator.py` (gather bridge + executor removal)
- `scripts/collaboration/async_coordinator.py` (shared-core delegation + AsyncWorkerWrapper native path)
- `scripts/collaboration/worker.py` (`aexecute` / `_ado_work` + shared helpers)
- `scripts/check_module_activation.py` (GatherCore_V459.1 counter registration)
- `tests/test_performance_benchmarks.py` (registered: `test_thread_pool_reuse` → gather contract)
- `CHANGELOG.md` (V4.5.9 entry), `VERSION`, `pyproject.toml`,
  `scripts/collaboration/_version.py`, `skill-manifest.yaml`, `SKILL.md`,
  `Dockerfile`, `helm/devsquad/Chart.yaml`, `README.md`, `README-CN.md`,
  `README-JP.md`, `CLAUDE.md`, `COMPARISON.md`, `config/deployment.yaml`,
  `skills/__init__.py`, `docs/spec/SPEC.md`,
  `docs/architecture/ARCHITECTURE_V4.md` + 4 TRAE cache layers

### Docs (P7)

- `docs/planning/V4.5.9_P12_RETROSPECTIVE.md` (P12 closure)
- `docs/prd/V4.5.9_PRD.md`, `docs/planning/V4.5.9_DESIGN.md` (planning inputs)

---

## Next

Backlog candidates (not committed — see retrospective §8):
`_RISK_STORE` SQLite backend (deferred again, JSON covers ≤10k items),
`--async` CLI flag candidate (verify `DEVSQUAD_USE_ASYNC=1` first),
further `Worker.execute`/`aexecute` merge evaluation.
