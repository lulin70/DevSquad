# Release Notes — v4.5.8

> **V4.5.8 — FileRiskStore Persistence + Risks CLI Completeness**
> Released: 2026-08-29
> Commit: TBD (P9)
> Tag: TBD

---

## Summary

V4.5.8 delivers 3 of the 4 backlog items selected by the V4.5.7 retrospective
(7-Role consensus **6.5/10**, split decision). Three tightly-scoped waves:

- **Wave 1 (P1)**: `FileRiskStore` — risk registers become file-backed,
  cross-process persistent (JSON schema v1 + flock + atomic writes)
- **Wave 2 (P2)**: risks CLI mutators — `add` / `assess` / `mitigate` /
  `close` complete the shell surface of the RiskRegister API
- **Wave 3 (P2)**: exposure filtering — `--min-exposure` canonical threshold,
  `--severity` numeric alias + legacy category mode, new `--category`

Deliberately deferred: `Coordinator._execute_parallel` → `asyncio.gather`
(V4.5.9) and `Worker.execute` native async (V4.5.10) — architect score 5.5/10
failed the consensus gate; the sync boundary and 11-Phase lifecycle stay
untouched.

---

## Added

### Wave 1: `FileRiskStore` (P1)

New module `scripts/collaboration/file_risk_store.py`:

| Aspect | Design |
|--------|--------|
| Layout | `.devsquad_data/risks/<register_id>.json` + sibling `.lock` |
| Schema | JSON v1: `{"version": 1, "register_id": ..., "items": [...]}` |
| Locking | `fcntl.flock(LOCK_EX \| LOCK_NB)` retry loop (Unix) / `msvcrt` (Windows), `lock_timeout` → `RiskStoreLockError` |
| Writes | same-dir temp file → fsync → `os.replace()` → directory fsync |
| Transactions | `store.transaction(rid)` context manager: locked load → mutate → validate → save |
| Path safety | `register_id` allowlist, `resolve()` + `commonpath`, symlink refusal (root / canonical / lock) |
| Corruption | bad JSON / wrong schema / id mismatch → `RiskStoreCorruptError`, exit 3 |

**Hardening added during implementation**:

1. `lock_timeout` NaN/±Inf/negative rejected in `__init__` — a NaN deadline
   would never be reached by `time.monotonic() >= deadline` and hang the lock
   loop (L-V458-002-adjacent: default-argument binding also bit here, see
   retrospective).
2. Transaction re-entry guard: `load()`/`save()` on a register_id held by an
   active transaction of the same instance raise `RiskStoreError` — flock is
   per-fd, so re-acquiring inside the transaction would self-deadlock.
3. `DEFAULT_ROOT` bound as a default parameter at import time: callers must
   pass an explicit `root` for tests (default-param binding evaluated once at
   module load — L-V458-002).

### Wave 2: risks CLI mutators (P2)

```
devsquad risks add "desc" --probability 0.7 --impact 0.9 --category technical --owner devops
devsquad risks assess R-xxx --votes '{"architect":[0.6,0.8]}'   # or --votes-file
devsquad risks mitigate R-xxx --strategy mitigate --owner devops --plan "..."
devsquad risks close R-xxx [--require-approval]
```

- All subcommands accept `--register-id` (logic register) and hidden `--root`
  (tests/advanced use).
- `close` maps onto `RiskRegister.track(id, RiskStatus.CLOSED)` — no second
  close vocabulary.
- Stable exit codes: domain error 1, argparse/approval 2, store corrupt /
  lock timeout 3; single-line `ERROR: ...` on stderr, never a traceback.

### Wave 3: exposure filtering (P2)

| Flag | Behavior |
|------|----------|
| `--min-exposure FLOAT` | canonical numeric threshold, `>=` boundary inclusive, NaN/Inf/±out-of-range rejected |
| `--severity FLOAT` | numeric alias of `--min-exposure` (back-compat) |
| `--severity <category>` | legacy category match, prints deprecation warning to stderr |
| `--category STRING` | explicit category filter (new) |

---

## Changed

### Breaking contract change: fail-closed approvals

V4.5.5's auto-approve fallback is **removed** on the risks CLI destructive
paths. `close --require-approval` / `clear --require-approval` without an
available approval callback now prints `ERROR: approval unavailable` and
exits **2** with the store preserved — silent auto-approval is no longer
possible (R-458-005 mitigated). Non-approval semantics of ApprovalGate for
other dispatch callers are unchanged.

### Approval moved out of the lock

`close` / `clear` perform the existence check / count read BEFORE opening the
store transaction; the human approval decision can no longer hold the
cross-process file lock (deadlock eliminated, R-458-003 follow-up).

### Test isolation fix

CLI/store test suites now pass explicit temporary roots (`tmp_path` +
`--root`) instead of exercising the real `.devsquad_data` directory — the
V4.5.7 `add_risk()` default leaked risk state across runs and machines.

---

## Verification

| Gate | Status |
|------|--------|
| `ruff check scripts/ tests/` | 0 errors ✅ |
| `check_module_activation.py` | 23/23 modules active ✅ |
| `check_version_consistency.py` | 51/51 (version fields + PRD + 8 TRAE cache content diffs) ✅ |
| Risks gate tests (`pytest` targeted) | 134 collected: 62 unit + 22 integration + 29 contract + 5 E2E + 16 ApprovalGate ✅ |
| E2E real-user simulation | independent-process full journey PASS ✅ |

---

## E2E Real-User Simulation (P5)

Per the release-readiness rule, `tests/e2e/test_v458_risks_cli_real_user.py`
simulates two independent shell processes sharing one store root:

- full journey add → list → show → assess → mitigate → close → export →
  clear with exit-code assertions at every step;
- cross-process exposure-threshold filtering (`--min-exposure` hides/shows
  rows consistently between writer and reader processes).

`tests/e2e/test_risks_cli_e2e.py` keeps the V4.5.7 standalone-CLI journey
green under the file-backed contract.

---

## Lessons Learned (V4.5.8)

1. **L-V458-001**: Trae sandbox foreground long commands hang in `T` state —
   run every gate via `nohup <cmd> > /tmp/xxx.log 2>&1 & disown; sleep N;
   tail /tmp/xxx.log` (background + poll), never in the foreground.
2. **L-V458-002**: `DEFAULT_ROOT` as a default parameter binds one `Path` at
   import time; per-call roots must be passed explicitly or tests share the
   same directory.
3. **L-V458-003**: fail-closed must be uniform — one CLI contract for
   "approval required but unavailable" (exit 2) across `close`/`clear`
   instead of a per-command guess.
4. **L-V458-004**: `monkeypatch.setattr` binds names at patch time; code
   that re-imports inside a function needs runtime name lookup (patch the
   module attribute, not a captured local).

---

## Files Changed

### New (9)

- `scripts/collaboration/file_risk_store.py`
- `tests/unit/test_file_risk_store.py` (37)
- `tests/unit/test_cli_risks_mutators.py` (11)
- `tests/integration/test_file_risk_store_integration.py` (6)
- `tests/integration/test_cli_risks_persistence.py` (8)
- `tests/contract/test_file_risk_store_contract.py` (14)
- `tests/contract/test_cli_risks_v458_contract.py` (13)
- `tests/e2e/test_v458_risks_cli_real_user.py` (2)
- `docs/RELEASE_NOTES_v4.5.8.md` (this file)

### Modified

- `scripts/cli_risks.py` (file-backed store + mutators + exposure filters)
- `scripts/collaboration/risk_register.py` (from_store / from_items seams)
- `scripts/check_module_activation.py` (23/23 gate + `_activate_v458_modules`)
- `scripts/cli.py` (risks mutator subcommand registration)
- `tests/unit/test_cli_risks.py`, `tests/integration/test_risk_register_cli.py`,
  `tests/contract/test_cli_risks_api_contract.py`, `tests/e2e/test_risks_cli_e2e.py`,
  `tests/test_approval_gate.py` (file-backed contract updates)
- `CHANGELOG.md` (V4.5.8 entry), `VERSION`, `pyproject.toml`,
  `scripts/collaboration/_version.py`, `skill-manifest.yaml`, `SKILL.md`,
  `Dockerfile`, `helm/devsquad/Chart.yaml`, `README.md`, `README-CN.md`,
  `README-JP.md`, `CLAUDE.md`, `COMPARISON.md`, `config/deployment.yaml`,
  `skills/__init__.py`, `docs/spec/SPEC.md`,
  `docs/architecture/ARCHITECTURE_V4.md` + 4 TRAE cache layers

### Docs (P7)

- `docs/planning/V4.5.8_P12_RETROSPECTIVE.md` (P12 closure)
- `docs/planning/V4.5.8_DESIGN.md` (status → implemented)

---

## Next: V4.5.9

Potential scope (not committed):
- `Coordinator._execute_parallel` → `asyncio.gather` (deferred twice;
  prerequisite: `httpx.AsyncClient` decision for `Worker.execute`)
- `_RISK_STORE` SQLite backend (JSON covers ≤10k items today)
