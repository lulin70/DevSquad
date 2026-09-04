# Release Notes — v4.5.7

> **V4.5.7 — Coeffect Async + Risk Register UX CLI**
> Released: 2026-08-26
> Commit: TBD (P9)
> Tag: TBD

---

## Summary

V4.5.7 closes the top-2 backlog items selected by the V4.5.6 retrospective
(7-Role consensus **8.79/10**). Two tightly-scoped waves:

- **Wave 1 (P0)**: `AsyncCoeffectResolver` — coeffect execution goes
  async-native, replacing the ThreadPoolExecutor-blocking model
- **Wave 2 (P1)**: `devsquad risks` UX CLI — surfaces the V4.5.4 RiskRegister
  to shell users with Markdown/JSON output and ApprovalGate-guarded clear

Deliberately deferred to V4.5.8: `dispatcher.py` migration to
`asyncio.gather` (kept as an independent release for stability).

---

## Added

### Wave 1: `AsyncCoeffectResolver` (P0)

New module `scripts/collaboration/async_coeffect_resolver.py`:

| Aspect | Design |
|--------|--------|
| Async entry | `await resolver.aresolve(req) -> CoeffectResult` |
| Sync bridge | `resolver.resolve(req)` — zero caller modification vs V4.5.4 |
| Concurrency | `asyncio.Semaphore(max_concurrent=4)` replaces the thread pool |
| Deadlock safety | uniform lock ordering sem → lock (L-V457-004) |
| FSM | per-call 6-state lifecycle; instance state is diagnostics-only |
| Failure capture | `aresolve` never raises — timeouts/errors land in `CoeffectResult(state=FAILED)` |
| Cancellation | `CancelledError` captured as `state=CANCELLED` |

The V4.5.4 sync `CoeffectResolver` (Kahn topological sort) is **preserved
unchanged** — activation ordering and execution concurrency remain separate
concerns, and the two resolvers coexist in one process (covered by
integration + contract tests).

**Bugs fixed during implementation (P4)**:

1. `resolve()` previously swallowed its own informative RuntimeError when
   called inside a running event loop, then crashed inside `asyncio.run()`
   with a confusing nested-loop message. It now raises the informative
   error directly, steering callers to `aresolve()` (L-V457-003).
2. `_arun_one` migrated off the deprecated `asyncio.get_event_loop()`.

### Wave 2: `devsquad risks` CLI (P1)

New `scripts/cli_risks.py`, registered on the main CLI:

```
devsquad risks list [--format md|json] [--severity CAT] [--limit N]
devsquad risks show <risk_id> [--format md|json]
devsquad risks clear [--require-approval]
devsquad risks export [FILE]
```

- **list**: Markdown table (default; sorted by exposure descending) or JSON
- **show**: single-risk detail (exposure formula, status, strategy, owner)
- **clear**: wipes the in-process register; with `--require-approval`, the
  V4.5.5 `ApprovalGate` runs first — denial exits code 2 and the store is
  preserved (fail-closed)
- **export**: JSON to stdout or file

An in-process `_RISK_STORE` bridges the stateless V4.5.4 `RiskRegister` so
subcommands share items within one CLI session; `add_risk()` is exported as
the Python API for programmatic/test use.

---

## Changed

- `scripts/cli.py`: registers the `risks` subparser (alias `risk`).
- `scripts/check_module_activation.py`: anti-ghost gate extended 19 → 21
  modules (`AsyncCoeffectResolver_P12.5.1`, `CliRisks_P12.5.2`).
- `tests/smoke/test_real_llm_auto_mode.py`: the NoKey case now also clears
  `MOKA_API_KEY` — on machines whose `.env` carries a Moka key the fallback
  chain previously gained a `MokaAIBackend` and the "without keys is mock"
  assertion failed.

---

## Verification

| Gate | Status |
|------|--------|
| `ruff check` (new/changed files) | All checks passed ✅ |
| `check_module_activation.py` | 21/21 modules active ✅ |
| `check_test_pyramid.py` | healthy (74.3% unit / 15.3% integration / 5.3% contract) ✅ |
| `check_test_quality.py` | 0 MAJOR findings ✅ |
| `pytest tests/` | TBD (P6 full regression) |
| New tests | 74 passed (39 unit + 20 integration + 8 E2E + 8 contract) ✅ |

---

## E2E Real-User Simulation (P5)

Per the release-readiness rule, both waves ship with E2E suites that
simulate real usage:

- `tests/e2e/test_coeffect_async_pipeline.py` — a user dispatches a task and
  7-role setup runs concurrently; a crashing role is fail-isolated; a hung
  coeffect is cut off by timeout; a sync script bridges via `resolve()`;
  cancelling a long workflow leaves the resolver reusable.
- `tests/e2e/test_risks_cli_e2e.py` — a user runs the add → list → show →
  export → clear journey through the standalone CLI entry, verifying exit
  codes (0/1) and output formats, including a clean stderr error (no
  traceback) on a typo'd risk id.

---

## Lessons Learned (V4.5.7)

1. **L-V457-001**: Skill vs IDE boundary — HostLLMBridge 4-file protocol is
   100% implemented; async execution is fully ours to control.
2. **L-V457-003 applied**: sync-bridge detection must re-raise the
   informative error, not catch-then-crash deeper with `asyncio.run()`.
3. **Per-call FSM beats instance FSM** for concurrent re-entry: instance
   state as diagnostics-only eliminated "Invalid FSM transition" races.
4. **CLI tests should parse data rows by their distinctive prefix**
   (`"| \`R-"`), not by slicing `startswith("| ")` lists — the Markdown
   separator row (`|---|`) silently breaks index math.
5. **"No key" tests must clear every key var** the B/A/C resolver reads
   (OpenAI/Anthropic/Moka), or they fail only on machines with a `.env`.

---

## Files Changed

### New (10)

- `scripts/collaboration/async_coeffect_resolver.py`
- `scripts/cli_risks.py`
- `tests/unit/test_async_coeffect_resolver.py` (27)
- `tests/integration/test_async_coeffect_pipeline.py` (10)
- `tests/e2e/test_coeffect_async_pipeline.py` (5)
- `tests/contract/test_coeffect_api_contract.py` (6)
- `tests/unit/test_cli_risks.py` (12)
- `tests/integration/test_risk_register_cli.py` (10)
- `tests/e2e/test_risks_cli_e2e.py` (3)
- `tests/contract/test_cli_risks_api_contract.py` (2)
- `docs/RELEASE_NOTES_v4.5.7.md` (this file)

### Modified (4)

- `scripts/cli.py` (risks subparser registration)
- `scripts/check_module_activation.py` (21/21 gate + `_activate_v457_modules`)
- `tests/smoke/test_real_llm_auto_mode.py` (MOKA_API_KEY isolation)
- `CHANGELOG.md` (V4.5.7 entry)

### Docs (P7)

- `docs/planning/V4.5.7_P12_RETROSPECTIVE.md` (P9 follow-up)

---

## Next: V4.5.8

Potential scope (not committed):
- `dispatcher.py` parallel workers → `asyncio.gather` (deferred from
  V4.5.7 for release stability; `AsyncCoeffectResolver` is the prerequisite
  and is now in place)
- Persist `_RISK_STORE` across CLI invocations (file-backed store)
