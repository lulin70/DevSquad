# Vision: Orchestration — Why Loop Engineering + Consensus + Anti-Ghost

> **Status**: Living document. Last revised 2026-08-03 (V4.4.4).
> **Audience**: Architects and contributors asking "why these three pillars, and not something else?"
> **Prerequisite**: Read [VISION.md](./VISION.md) first.

---

## 1. The Three Pillars

DevSquad's orchestration layer is built on three deliberately chosen
pillars. They are not features; they are **design constraints** that
shape every other decision in the codebase.

1. **Loop Engineering** — the dispatch is a closed-loop
   Plan → Dev → Verify → Fix cycle, not a single forward pass.
2. **Consensus Engine** — disagreements between roles are surfaced and
   resolved through weighted voting, never silently averaged away.
3. **Anti-Ghost** — every module increments a module-level
   `_call_counter` on its public API, and CI fails if any module's
   counter is zero after a sample dispatch.

Each pillar exists to close a specific failure mode that the previous
pillar leaves open. They are **composable defenses**, not redundant ones.

---

## 2. Why Loop Engineering (Not Single-Pass)

A naive multi-agent system does this:

```
task → spawn N workers → collect outputs → return
```

This is single-pass. It has a fundamental flaw: **verification has no
teeth**. If a tester role says "this design fails the load test," there
is no structured way to feed that back into the architect's next pass.
The disagreement is recorded but not *resolved*.

Loop Engineering closes this by making the dispatch a **kernel**:

```
plan → dev → verify → fix → (loop until gate passes or budget exhausted)
```

The `LoopKernel` is the only entry point for tasks that need rigor.
Single-pass is still available for trivial tasks (the `dispatch()` method
without `dispatch_with_loop`), but the default for non-trivial work is
the loop.

### Why not just retry on failure?

A bare retry ("if the output is bad, try again") is not a loop — it is
a gambler's fallacy. Loop Engineering differs in three ways:

1. **The handoff is explicit.** `HandoffAdapter` carries the *reason*
   for the loop forward, so the next iteration's planner sees "verify
   failed because of X" not just "try again."
2. **The budget is bounded.** `max_iterations` is not a suggestion; the
   kernel enforces it. A loop that never terminates is a bug, not a
   feature.
3. **The gate is independent.** The `IndependentEvaluator` that decides
   "pass" or "fail" is not the same component that produced the work.
   This is why `independent_evaluator.py` exists as a separate module.

---

## 3. Why a Consensus Engine (Not Voting)

Voting is the wrong word. Voting implies "majority wins." DevSquad's
Consensus Engine is deliberately **not** majority-rule.

### The problem with majority rule

If the architect, coder, and tester vote 2-1 to ship, the security role
being outvoted does not make the security concern disappear. A
majority-rule system would silently lose the objection. That is
exactly the "diluted compromise" failure mode VISION.md warns about.

### What the Consensus Engine does instead

1. **Weighted votes.** Each role has a weight (architect 1.5, security
   1.1, tester 1.0, etc.). The weights are public and configurable.
   Security is not outvoted by quantity.
2. **Veto power.** Some decisions require unanimity among affected
   roles. A security veto on a crypto-scheme change is binding, not
   advisory.
3. **Escalation, not suppression.** When consensus fails, the engine
   emits a `SPLIT` or `ESCALATED` outcome. It does **not** silently
   pick the majority. The conflict is surfaced to the dispatch report
   and the human reviewer.
4. **Five-axis review.** `FiveAxisConsensus` evaluates decisions across
   five orthogonal axes (correctness, completeness, risk, cost,
   timeline) so a "yes" on one axis does not paper over a "no" on
   another.

The Consensus Engine is the **only** legitimate path to a team
decision. There is no back-channel where the architect can override the
tester.

---

## 4. Why Anti-Ghost (Not Just Tests)

"Anti-ghost" sounds like a testing quirk. It is not. It is a **systemic
guarantee that code is actually wired in**.

### The ghost module problem

A common failure in large codebases: a module is imported, its tests
pass in isolation, but **no production code path actually calls it**.
The module is a ghost. It looks alive in CI, but it is dead in
production.

Standard test coverage cannot catch this. A unit test of the ghost
module passes because the test calls it directly. Integration tests
miss it because the integration path doesn't route through the ghost.

### The anti-ghost contract

Every V4.4.x module declares a module-level `_call_counter: int`. The
constructor or primary public method increments it. The CI gate
`scripts/check_module_activation.py` runs a sample dispatch and asserts
that **every** module's counter is > 0 after the dispatch.

This converts "is the module wired in?" from a code-review judgment
call into a **machine-checked invariant**. A module that survives a
dispatch without incrementing its counter is provably dead code,
regardless of how many unit tests it has.

### Why this matters for trust

If a user reads the dispatch report and sees a "## Risk Management"
section, they trust that the RiskRegister actually ran. The
`_call_counter` guarantee is what makes that trust verifiable, not
assumed. The same applies to WorkflowTrace (V4.4.4) and GitContext
(V4.4.4): their sections in the report are evidence the modules ran,
because the counter would fail CI otherwise.

---

## 5. How the Three Pillars Compose

The pillars are not independent; they reinforce each other.

- **Loop + Consensus**: A loop iteration that ends in `SPLIT` does not
  crash — it feeds the split outcome into the next plan phase as
  structured input. The Consensus Engine's escalation is the loop's
  signal to re-plan.
- **Consensus + Anti-Ghost**: The Consensus Engine records every vote
  in the Scratchpad. If the Scratchpad's `_call_counter` is 0 after a
  dispatch, the consensus path is provably dead and CI fails.
- **Anti-Ghost + Loop**: The LoopKernel itself has activation tracking.
  A "loop" that never iterated more than once is suspect — the
  anti-ghost counter on the fix phase exposes that.

Remove any one pillar and the other two lose their teeth. A loop
without consensus hides disagreements. A consensus without anti-ghost
may be dead code. Anti-ghost without a loop is just a coverage metric.

---

## 6. What This Rules Out

The three-pillar design deliberately rejects some alternatives:

- **No hidden system-2 reasoning.** We do not let the LLM "think
  longer" internally and trust the result. The reasoning is external
  (Scratchpad, Workflow Trace) and checkable.
- **No silent retries.** A retry that does not pass through the
  Consensus Engine is a bug. The HandoffAdapter enforces this.
- **No uninstrumented modules.** A new feature that does not bump a
  `_call_counter` will fail CI. There is no "I'll add tests later"
  escape hatch.
- **No single-role override.** The Coordinator orchestrates; it does
  not vote. A coordinator that could outvote the security role would
  defeat the entire point of the team.

---

## 7. The Long-Term Commitment

These three pillars are not V1 scaffolding to be refactored away. They
are the **constitutional invariants** of the project. V4.5.0's
SkillProvider protocol refactor, V5.0.0's planned MCP integration, and
any future work must preserve all three:

- Any new module ships with a `_call_counter`.
- Any new decision path goes through Consensus.
- Any non-trivial task runs through LoopKernel.

If a future change weakens any of these, the change is wrong, not the
pillar. The pillar stays; the change is reworked.

---

## 8. The One-Paragraph Summary

> DevSquad orchestrates with three pillars because **a single forward
> pass hides disagreement, a majority vote silences minority risk, and
> a module that is not provably called is a module that does not
> exist.** Loop Engineering makes verification binding, the Consensus
> Engine makes conflict visible, and Anti-Ghost makes "is it actually
> wired in?" a CI-checkable fact rather than a code-review hope.

---

**Maintained by**: DevSquad 7-Role Team (Architect-led)
**See also**: [VISION.md](./VISION.md), [VISION_AGENT_COLLABORATION.md](./VISION_AGENT_COLLABORATION.md)
