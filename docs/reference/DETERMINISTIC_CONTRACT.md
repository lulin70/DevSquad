# Deterministic / Agent Boundary — Engineering Contract

> **Status**: W1-0 (V4.5.20). Written **before** the implementation, as the spec for
> W1-1 … W1-7, per the maintainer's ruling that the contract comes first.
> **Source**: `docs/prd/V4.5.20_ocr-learnings_PRD.md` — E7 (this document), E1, E2,
> E3, E5, E8.
> **Drift gate**: `scripts/check_skill_contract.py` reverse-checks every clause below.
> **Audience**: whoever is calling DevSquad — a human or a host Agent — and needs to
> know what the deterministic layer promises before trusting it.

## 1. Why this document exists

`SKILL.md` discloses DevSquad's capability *layers* (prompt layer delegated to the
host LLM, script layer deterministic). It did not disclose the *contracts* inside
the deterministic layer: what each filter gate means, how a rule is selected, what
"coverage" means when some roles fail, whether a preview costs tokens, and what the
delegation mode requires of the host. A caller that does not know these four things
cannot use the layer correctly, and its failures look like bugs in DevSquad rather
than misuse of it.

This document is the spec. The code follows it, not the other way round.

## 2. What the gate does — and what it does not

`scripts/check_skill_contract.py` is a **drift alarm**, not a correctness proof:

| | |
|---|---|
| **Does verify** | Every clause id, its keywords, and its `Effective` token are still present in this file; the `Effective` token is read from the clause's **own index row**, so blanking one cell is caught even when other rows carry the same wave; every wave named in `Effective` still exists in the PRD (so an annotation cannot dangle); the four user-facing commitments in `SKILL.md` are still present. |
| **Does not verify** | That the behaviour is implemented. A keyword grep cannot prove semantics — this is the same false-green class as a gate whose scope is narrowed by a flag. Each clause below names its **Proven by** tests; those are the evidence. |

Consequence, stated plainly: a green `check_skill_contract.py` means "the contract
has not drifted", never "the contract is honoured". Do not cite it as the latter.

## 3. Clause index

`Effective` is load-bearing (PRD R7). A clause not yet shipped **must** name the
wave that ships it, because a document that promises more than the code delivers is
the same defect as a documented feature that never ran (PRD F4).

| # | Clause id | Scope | Effective |
|---|---|---|---|
| C1 | `gate.secret_exclude_priority` | Filter gates | W1-3 |
| C2 | `gate.named_exclusion_reasons` | Filter gates | W1-3 |
| C3 | `gate.exports_are_not_gates` | Filter gates | W1-3 |
| C4 | `rule.four_layer_chain` | Rule resolution | W1-1 |
| C5 | `rule.first_match_wins` | Rule resolution | W1-1 |
| C6 | `rule.system_layer_always_exists` | Rule resolution | W1-1 |
| C7 | `rule.security_exemption_hardcoded` | Rule resolution | W1-1 |
| C8 | `rule.explain_command` | Rule resolution | W1-2 |
| C9 | `coverage.nonzero_exit` | Coverage | W2-2 |
| C10 | `coverage.named_failed_roles` | Coverage | W2-1 |
| C11 | `preview.zero_llm_calls` | Preview | W1-4 |
| C12 | `preview.summary_by_default` | Preview | W1-4 |
| C13 | `preview.path_redaction` | Preview | W1-4 |
| C14 | `delegate.zero_api_key` | Delegation | shipped in V4.5.10 |
| C15 | `delegate.strict_marker_fail_closed` | Delegation | shipped in V4.5.10 |
| C16 | `delegate.degradation_ladder` | Delegation | W1-6 |
| C17 | `delegate.no_silent_mock_fallback` | Delegation | W1-6 |
| C18 | `review.multifile_input_contract` | Review input | W1-5 |

---

## 4. Filter gates (E1)

The review pipeline decides *which files it will look at* before it looks at
anything. Every decision that drops a file must be attributable to a named gate, so
that "why wasn't my file reviewed?" always has an answer in the output.

### C1 `gate.secret_exclude_priority`

**Rule.** `secret_exclude` is evaluated **before** all user configuration and
**cannot be overridden by `include`**. If a path is judged secret, no project-level
or user-level `include` can pull it back into the review set.

**Why it is not a default but a wall.** `secret_exclude` protects the user from
leaking a credential into a report, a log, or a CI transcript. A protection that a
local config file can switch off is not a protection — it is a default. This is the
same hard constraint as `InputValidator` and `rbac_fail_closed=True`: forbidden to
fail open.

**Proven by** `tests/test_review_preview.py` (negative case: a config that
`include`s a secret path must still see it excluded).

### C2 `gate.named_exclusion_reasons`

**Rule.** Exactly eight gate names exist, and each dropped path carries one of them:

| Gate | Meaning |
|---|---|
| `secret_exclude` | Path matches the secret/credential pattern set (C1). |
| `binary` | Not text (detected by content, not by extension alone). |
| `unsupported_ext` | Text, but no rule in any layer claims this type. |
| `too_large` | Exceeds the per-file size budget. |
| `user_exclude` | Matched an `exclude` pattern supplied by the caller. |
| `user_include` | Kept, but reported, because an `include` pattern named it. |
| `default_path` | Dropped by the built-in path allow/deny defaults, with no user rule involved. |
| `deleted` | Present in the diff as a removal; nothing to review. |

**Naming.** These eight strings are part of the contract — they appear in reports
and in `--preview` output, and callers may match on them. Renaming one is a
breaking change.

**Proven by** one test per gate in `tests/test_review_preview.py`.

### C3 `gate.exports_are_not_gates`

**Rule.** A path that is *kept* is not reported as passing a gate. `user_include`
above is the exception and is deliberately listed, because an explicit `include` is
a user decision worth confirming; the other seven describe drops only.

**Proven by** the summary counts in `tests/test_review_preview.py`: kept + dropped
must equal the candidate total, exactly once each.

---

## 5. Rule resolution (E2)

Two questions are answered here: *which rule applies to this path*, and *why that
one*. The second question is the whole point — PRD F3 records that DevSquad's
decisions were not inspectable, and `rules check` is the answer to it.

### C4 `rule.four_layer_chain`

**Rule.** For any path, rules are tried in this order:

| Priority | Source | Location |
|---|---|---|
| 1 (highest) | CLI argument | `--rule <path>` |
| 2 | Project | `<repo>/.devsquad/rule.json` (safe to commit) |
| 3 | User | `~/.devsquad/rule.json` |
| 4 (lowest) | Built-in system | `system_rules.json`, shipped with the package |

**A missing layer is skipped silently**, not reported as an error: layers 1–3 are
optional, and their absence is the normal case.

**A layer that exists but cannot be parsed is an error** (`RuleConfigError`), not a
silent skip. Only *absence* is silent — a corrupt `rule.json` would otherwise drop
the caller's rules without saying so.

**Matching** uses `pathlib` glob semantics (`PurePath.match`, right-anchored), with
one extension: a leading `**/` may also match zero directories, so `**/*.py` covers
a top-level Python file as well as a nested one.

**Proven by** `tests/test_rule_engine.py` (one case per layer).

### C5 `rule.first_match_wins`

**Rule.** The **first** layer whose pattern matches wins. There is **no merge and
no override**. A lower layer cannot contribute half a rule, and a higher layer
cannot add one field to a lower layer's rule. **Within** a layer, **file order**
decides: the first matching entry wins.

**Why not merge.** Merging makes the effective rule a function of the entire
configuration stack, so reasoning about "what will happen" requires reading every
layer. First-match makes it a function of one layer, and `rules check` can print
which one. Predictability beats expressiveness here.

**Proven by** `tests/test_rule_engine.py` asserting the result is byte-identical to
the winning layer's rule — not a union of two layers.

### C6 `rule.system_layer_always_exists`

**Rule.** The system layer is always present, so resolution **always** returns a
rule. There is no "no rule found" state and therefore no undefined behaviour for an
unclaimed file type — it resolves to the system default.

**Proven by** `tests/test_rule_engine.py`: resolution with layers 1–3 all absent
still returns a rule, and that rule is the system one.

### C7 `rule.security_exemption_hardcoded`

**Rule.** Safety rules — the sensitive-path protections behind C1 — are evaluated
**before layers 1–3 and cannot be overridden by any of them**, including via
`include`. This exemption is **hardcoded, not configurable**.

**Why hardcoded.** `rule.json` at the project level is a committable file and at the
user level a locally writable one. Both are attack surfaces: without a hardcoded
exemption, a user layer could either force a sensitive path into the review set or
switch the protection off. Nothing that a local file can rewrite may guard against
that local file.

**Proven by** negative tests in `tests/test_rule_engine.py` that attempt each
bypass and must fail.

### C8 `rule.explain_command`

**Rule.** `devsquad rules check <path>` prints the **winning layer**, the **pattern**
that matched, and the **rule body**. For the same path under different layer
configurations it must print different output — a command that always prints the
same thing explains nothing.

**Proven by** `tests/test_rule_engine.py`: same path, two configurations, two
different printed layers.

---

## 6. Coverage (E3)

### C9 `coverage.nonzero_exit`

**Rule.** If the requested coverage was not achieved, DevSquad exits **non-zero**.

This is a deliberate divergence from the OCR pipeline it was learned from, where a
budget-exhausted run stops dispatching, marks the skipped files as `failed(budget)`,
**still returns the partial result, and exits 0**. As an interactive tool that is
reasonable — the user can see the `failed` markers. As a CI gate it is a false
green: the build passes while part of the code was never examined.

A caller that wants the interactive behaviour should treat the partial result as
data and ignore the exit code. The default must be the safe one, because the
dangerous consumer (CI) is the one that will not read the report.

**Proven by** `tests/test_coverage_exit_codes.py`, three assertions together: all
succeed → `0`; some roles fail → non-zero **and** the report names them; the
infrastructure fails → non-zero. One assertion alone cannot distinguish "the
contract works" from "something happened to fail".

### C10 `coverage.named_failed_roles`

**Rule.** Every role that failed is listed **by name**, with its reason. A count of
failures is not sufficient: the caller's next action (re-run, narrow the request,
fix a credential) depends on *which* role failed.

**Proven by** `tests/test_report_formatter.py` with an injected always-failing
worker: the report must contain that role's name and its reason.

---

## 7. Preview (E1)

### C11 `preview.zero_llm_calls`

**Rule.** `review --preview` makes **zero LLM calls**. It reports the plan — which
files will be reviewed, which were dropped, and under which gate — and nothing else.
It exists so a caller can find out what a review would cost *without* paying for it.

**Proven by** test that patches the **underlying HTTP client** (`httpx` /
`requests` send methods) and asserts zero invocations. Patching only the backend
layer is explicitly insufficient: a `MockBackend` call counter proves the backend
interface was not entered, not that no request left the process.

### C12 `preview.summary_by_default`

**Rule.** The default output is **counts per gate plus totals**. `--verbose` expands
to the per-path detail. A large repository must not turn a preview into hundreds of
lines of output.

**Proven by** test asserting the default output has no per-path lines.

### C13 `preview.path_redaction`

**Rule.** When preview output would name a sensitive path, it is **redacted or
reduced to a count**. A path such as `.env.production` must not appear in plaintext
in a log, a report, or CI output.

**Why this is a delivery requirement, not polish.** The preview exists to be printed
and pasted — that is its purpose. Output designed to be pasted into an issue is
exactly where a leaked path does damage, so redaction belongs in the feature, not in
a follow-up.

**Proven by** test asserting the sensitive path from a fixture appears in no
plaintext form in preview output.

---

## 8. Delegation (E5)

Delegation is the mode where **DevSquad supplies the deterministic scaffolding and
the host Agent supplies the LLM**. It is the cheapest correct mode for anyone
already paying for a subscription coding Agent, because it needs no provider
credential at all — and requiring one anyway is pure friction.

### C14 `delegate.zero_api_key`

**Rule.** In delegated mode DevSquad reads **no** API-key environment variable. The
path works with `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `MOKA_API_KEY` all unset.

**Honest consequence.** "No key required" does **not** mean "real LLM output without
a key". The output quality is the host Agent's. A caller who reads this clause as
"DevSquad runs a real model for free" will form a wrong expectation about the
output — which is why the clause is stated as a boundary and not as a feature.

**Proven by** test running the delegated path with all provider credentials cleared
from the environment.

### C15 `delegate.strict_marker_fail_closed`

**Rule.** The v2 protocol uses a **strict seven-field marker**. Any missing field is
**rejected**, with no attempt to infer the missing value. Fail-closed, never
guess-and-continue.

**Proven by** negative test: a marker missing one field must raise, not proceed.

### C16 `delegate.degradation_ladder`

**Rule.** Degradation follows `host` → `auto` → `auto-fallback`, and **each step is
visible to the user**. Silent degradation is what makes a caller believe it is
talking to the host Agent when it is not.

**Proven by** one test per step asserting the user-visible notice.

### C17 `delegate.no_silent_mock_fallback`

**Rule.** A **protocol violation raises**. It never quietly falls back to
`MockBackend`. A silent fallback produces plausible-looking text from a mock while
the user believes the host Agent wrote it — the most damaging possible failure for
this mode, because it is undetectable from the output.

**Proven by** negative test forging a bad marker and asserting an error, not a mock
response.

### C18 `review.multifile_input_contract`

**Rule.** Review accepts a **diff or multiple files**, and the original single
`code` string remains supported with unchanged behaviour. The compatible path is a
requirement, not a courtesy: callers pinned to the single-string form must not have
to change.

**Proven by** a back-compat test asserting the single-`code` call behaves as before,
alongside the new multi-file tests.

---

## 9. Delegation is the default path

**Effective: W1-6.** Delegation is to be documented as the **default** mode rather
than as one option among several, in `SKILL.md` — a caller already inside an AI IDE
should start there.

**Proven by** `SKILL.md` (declaration) plus the W1-6 end-to-end run. The declaration
is checked by the drift gate; the behaviour is not.

## 10. Related documents

- `SKILL.md` — the three commitments a caller must know before choosing a mode.
- `docs/prd/V4.5.20_ocr-learnings_PRD.md` — the findings behind each clause (E1, E2,
  E3, E5, E7, E8) and the wave plan.
- `docs/reference/MODULE_REFERENCE.md` — where each capability lives in code.