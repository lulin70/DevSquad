# V4.9.0 P2-W3 registration gate — e2e evidence (anchor ⑭)

Real dispatch runs through the production pipeline (`MultiAgentDispatcher.dispatch`,
deterministic local backends, single-role task) plus the real user command
surface (`scripts/cli.py defect add/update/close/reopen`), each scenario in an
isolated temp workspace with the production default ledger path
(`.devsquad/defects.json` resolved from the workspace CWD — D5, no config knob).

Design: [V4.9.0_W3_registration-gate_DESIGN.md](../../planning/V4.9.0_W3_registration-gate_DESIGN.md) §7 ⑭.

## Scenarios

| Scenario | Runs | Result |
|---|---|---|
| **A** red → file (CLI) → tracked → green | `run_a1_report.md` failing run, empty ledger → gate FAIL (`unregistered`), run red, C19 `product_failed`; DEF-001 filed from A1's real `dispatch_end` event via `defect add`; `run_a2_report.md` same failure, DEF live → gate PASS (`tracked` by DEF-001), run still red from the defect itself — the gate never masks the run's own failure; `run_a3_report.md` fixed run → run green, gate PASS (0 mandatory signals) |
| **B** regressed → reopen (CLI) → tracked | full W1 lifecycle seeded via CLI (`add` → `update` → `close` on a clean run); `run_b1_report.md` failing run, only closed DEF-001 → gate FAIL (`regressed`) with reopen guidance in violations; `defect reopen`; `run_b2_report.md` same failing run → gate PASS (`tracked` by reopened DEF-001) |
| **C** disabled (default) | `run_c_report.md` failing run, gate off → run red from the worker failure (W2 C19 baseline intact), **zero registration-gate trace** across all five faces: details / result attribute / to_dict / Markdown / audit event |

## Runner

```bash
.venv/bin/python docs/e2e_evidence/V4.9.0_W3_registration_gate_e2e/run_e2e.py
```

`run_e2e.py` is both the scenario driver and its own verification harness —
31 assertions across the three scenarios; any failure exits non-zero. Reports
are the raw `result.to_markdown()` of each run (W4 evidence format).

One operational finding baked into the runner: `dispatcher.shutdown()` closes
the injected audit logger, so multi-run workspaces create a fresh
`DispatchAuditLogger` per dispatch (the logger reloads the chain and keeps
appending to the same sqlite file — event ids stay correct for signal refs).

## Regression coverage

- `tests/integration/test_registration_gate_pipeline.py` — ①② + ⑤ pipeline face + ⑦ mixin fail-closed conversion
- `tests/unit/test_registration_gate.py` — ③④⑤⑥⑦⑧⑨⑪ + ⑫ CLI config injection
- `tests/test_dispatch_audit.py` — ⑩ `dispatch_end` persistence
- `tests/unit/test_dispatcher_config.py` — ⑬ field-count guard (51 → 52)
