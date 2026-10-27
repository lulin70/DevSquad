# Defect Ledger — Engineering Contract

> **Status**: V4.9.0 complete (W1-W4 shipped). This document is the PRD §8
> release-readiness deliverable that W1 design §10 scheduled for the release
> closeout: "docs/reference ledger contract doc (schema + state machine +
> two hazard guards)".
> **Source**: PRD `docs/prd/V4.9.0_defect-ledger_PRD.md` (§4.2 mapping);
> designs `docs/planning/V4.9.0_W1_defect-ledger_DESIGN.md`,
> `V4.9.0_W2_signal-write_DESIGN.md`, `V4.9.0_W3_registration-gate_DESIGN.md`.
> **Implementation**: `scripts/collaboration/defect_ledger.py` (ledger),
> `registration_gate.py` (gate), `scripts/cli_defect.py` (CLI).
> **Audience**: whoever files, tracks, or gates on defects — a human or a
> host Agent — and needs the exact contract before trusting the ledger.

## 1. Why this document exists

The ledger closes the cross-run defect loop:
**signal (audit event) → file (open) → fix (fixed) → clean regression
(close) → regression failure (reopen)**. Every signal originates in the
dispatch audit SQLite database; the ledger never owns audit data — it
resolves references into it read-only. The registration gate (W3) then
makes the ledger *enforceable*: a dispatch whose mandatory signals carry
no live ticket fails, so silence about a defect is no longer an option.

## 2. Storage and schema

| | |
|---|---|
| Ledger store | **JSON file**, default `.devsquad/defects.json` (cwd-relative), `schema_version: 1` |
| Audit source | `audit/dispatch_audit.db` SQLite, opened `mode=ro` — read-only, never written by the ledger |
| Record fields | `id` (`DEF-NNN`, monotonic — never reused after deletes), `state`, `signal`, `fix`, `regression`, `reopen_reason`, `created_at`, `history` (current state = tail of history) |

W1 `39 unit tests` run on fixtures DDL-identical to production; zero skips.

## 3. State machine (closed set)

`open | fixed | closed` — no state outside the set. `regressed` is a
**reopen reason**, not a state (the W3 gate derives it at evaluation time).

| From | Transition | To |
|---|---|---|
| open | `fix` (with `--commit` SHA) | fixed |
| fixed | `refix` | fixed |
| fixed | `close` (with `--run-ref` clean regression run) | closed |
| closed | `reopen` (mandatory `--reason`) | open |

Any other transition raises `DefectLedgerError` — fail-closed.

## 4. Two hazard guards (and one)

1. **Atomic writes**: tempfile in the same directory + `fsync` +
   `os.replace` — a crash never leaves a partial ledger on disk.
2. **Fail-closed load validation**: a corrupted ledger fails the load; it
   is never silently reset to empty. (Gate-side corollary, W3 D7: a
   corrupted ledger cannot prove registration → FAIL.)
3. **Monotonic `next_id`**: deleting the last defect does not let a later
   add reuse its `DEF-NNN` id.

## 5. `signal_ref` resolution contract

Two legal shapes, both parsed and resolved against the audit database:

```
audit:event=<N>&finding=<i>     # event N, finding index i
audit:event=<N>&failure=<class> # event N, failure_class (e.g. product_failed)
```

Any other shape raises `DefectLedgerError` ("W1 supports `audit:` refs
only"). The ledger stores the parsed signal dict; re-resolution at read
time queries the audit db read-only.

## 6. Mandatory signal mapping (PRD §4.2)

`mandatory_signal_types()` is the single source of truth shared by the
filing path and the registration gate:

- `failure:product_failed` — **forced filing** (product defect, exit 1 class)
- `review:break-vuln:BREAK-1` / `BREAK-5` / `VULN-1` / `VULN-4` — the four
  BV-critical categories

Mapping for review findings: BV finding → `review:break-vuln:<ID>`; non-BV
→ `review:spec:<category>` (advisory scope). `failure:environment_blocked`
is **refused** by the ledger (exit 2 class is an environment problem, not a
product defect — filing it would poison the ledger with non-defects).

## 7. Registration gate (Step 23.6)

Switch: `.devsquad.yaml` → `defect_ledger.enabled` (default **false** —
absent section = disabled = dispatch behavior byte-identical to 4.8.x,
zero trace on five surfaces: details / result attr / Markdown / audit /
success).

With the gate on, after the feature gate (23.5) and before the verdict
(24), every mandatory signal from the run is cross-checked against the
ledger:

| State | Meaning | Outcome |
|---|---|---|
| `tracked` | open or fixed ticket live (`fixed` still counts — W3 D4, avoids the deadlock where a fixed defect keeps the build red forever) | PASS |
| `unregistered` | no ticket at all; missing ledger = unregistered (not internal_error) | FAIL |
| `regressed` | closed-only ticket for a signal that fired again — gate output carries reopen guidance (`devsquad defect reopen DEF-NNN --reason ...`) | FAIL |

Fail-closed: an internal error in the gate itself is also FAIL.
`unfiled_signal_report` is advisory-only — warning/spec signals are listed
in the report without changing the exit code. Exit semantics follow
failure-taxonomy C19: `0` pass, `1` product_failed, `2`
environment_blocked.

## 8. CLI surface (six subcommands)

All subcommands accept `--ledger <path>` (default
`.devsquad/defects.json`). Verified against the argparse registry
(`scripts/cli_defect.py`, probed 2026-10-27):

| Command | Key arguments | Effect |
|---|---|---|
| `defect add` | `--signal-ref <ref>` (required), `--summary` (required) | File from a real signal: create → open |
| `defect update <DEF-NNN>` | `--commit <sha>` (required), `--summary` (required) | Register a fix: open → fixed (or refix) |
| `defect close <DEF-NNN>` | `--run-ref <audit:event=N>` (required) | Close after a clean regression run: fixed → closed |
| `defect reopen <DEF-NNN>` | `--reason` (required) | Reopen a regressed defect: closed → open |
| `defect list` | `--state open\|fixed\|closed` | List defects (filtered) |
| `defect audit` | — | Cross-check ledger invariants, fail-closed; missing audit db downgrades the advisory scan to a skip (probed: `ADVISORY: audit DB not found … — no advisory scan`, `ledger audit: OK`, exit 0) |

## 9. Dogfood status

This repository enabled `defect_ledger.enabled: true` on 2026-10-27
(v4.9.0 release closeout, P2 retrospective batch) — the registration gate
now runs on every dispatch in this repo, closing the loop the gate was
built to enforce.

---

*Every clause above names its implementation anchor and, where stated,
its probe evidence. The code follows the designs; where this document and
the code disagree, the code wins and this document must be fixed.*
