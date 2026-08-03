# DevSquad Vision — Why We Exist

> **Status**: Living document. Last revised 2026-08-03 (V4.4.4).
> **Audience**: New contributors, maintainers, and anyone asking "what problem does DevSquad actually solve?"

---

## 1. The Fundamental Problem

Modern AI assistants are powerful but **structurally solo**. A single LLM
instance receives a prompt, reasons in isolation, and emits a response.
This is fine for trivia and small tasks, but it breaks down the moment a
task demands what software teams call *multi-discipline rigor*.

Consider a realistic engineering request:

> "Add a multi-tenant RBAC layer to the existing auth service. Keep
> backward compatibility, don't break the audit trail, and ship behind
> a feature flag."

A single AI — however smart — tends to produce one of two failure modes:

1. **Tunnel vision.** The model optimizes hard for the dimension its
   prompt foregrounds (e.g. "ship fast") and silently under-invests in
   the others (security review, test coverage, migration safety).
2. **Diluted compromise.** The model tries to satisfy every dimension
   at once and produces a shallow, lowest-common-denominator answer that
   no specialist would accept.

The root cause is not model capacity. It is **the absence of structured
adversarial review**. A real software team avoids both failure modes by
having an architect, a security engineer, a tester, and a coder each
argue their corner, then converge through a deliberate decision
process. DevSquad exists to give an AI assistant that same structure.

---

## 2. The Core Insight: Agent as Team Member

DevSquad's foundational bet is that **one AI should become a team**.

Not "one AI pretending to be many roles" in a single monolithic prompt,
but **one AI decomposed into seven role-specialized Workers** that:

- Each have their own system prompt, scope, and voting weight.
- Write findings to a shared Scratchpad (the team's blackboard).
- Surface conflicts explicitly instead of papering over them.
- Resolve disagreements through a Consensus Engine, not a hidden
  internal compromise.
- Leave a Workflow Trace so a human can audit *why* the team decided
  what it decided.

This mirrors how block/buzz (github.com/block/buzz) frames the
human-agent relationship: an agent is a **team member with a role**,
not a generic oracle. The team metaphor is load-bearing — it shapes
the architecture, not just the marketing.

---

## 3. Why Not Just Use a Bigger Model?

This is the most common objection. "GPT-5 / Claude-4 is smart enough to
do all roles in one pass." We disagree, for three reasons:

1. **Single-shot reasoning has no internal opposition.** A bigger model
   still produces a single chain of thought. There is no agent on the
   other side saying "wait, that migration strategy violates the audit
   log invariant." Opposition requires *separate* reasoning contexts.
2. **Context window ≠ shared blackboard.** Stuffing everything into one
   context window makes every role's reasoning leak into every other
   role's. A tester should not be primed by the architect's draft; it
   should independently verify. Separation requires separate Workers.
3. **Auditability is a feature, not a byproduct.** A single LLM call is
   a black box. A seven-role dispatch produces a Scratchpad history, a
   consensus record, and a workflow trace. You can answer "why did the
   security role abstain on the OAuth decision?" three weeks later.
   That is impossible with a monolithic call.

Bigger models make each Worker better. They do **not** remove the need
for the team structure.

---

## 4. The Long-Term Vision

DevSquad's north star is a future where a developer's first instinct
for any non-trivial task is not "ask the AI" but **"assemble the team"**.

Concretely, we want:

- **Every dispatch to be auditable end-to-end.** A human reviewer can
  see the decomposition tree, the per-role reasoning, the conflict
  surface, and the final consensus — not just the final output.
- **Cross-session memory.** The agent that decided "we use Postgres
  not Mongo" last month is the *same agent* that today's dispatch can
  query. Agent identity is persistent, not per-request.
- **Branch-aware context.** The team knows which git branch, which open
  issues, which recent commits are in scope. Work happens *in context*,
  not in a vacuum.
- **Protocol-native skill layer.** Skills (create-prd, deep-shallow-
  analysis, etc.) are pluggable through a `SkillProvider` protocol, so
  the same agent team can be extended without touching the agent core.
- **Loop Engineering as the default.** Plan → Dev → Verify → Fix is
  not a manual cycle; it is the kernel the dispatcher runs on. The
  team iterates until a verification gate passes, not until tokens run
  out.

---

## 5. What DevSquad Is NOT

Equally important is what we deliberately chose not to be:

- **Not a chatbot.** DevSquad is a batch-dispatch system. You submit a
  task, the team runs, you get a structured result. There is no
  turn-by-turn conversation loop at the core.
- **Not decentralized.** We do not use Nostr, crypto signatures, or
  peer-to-peer relays. DevSquad is pure Python, single-process, and
  that is a feature: it keeps the deployment story trivial.
- **Not a replacement for humans.** The team augments a human
  developer; it does not replace code review, sign-off, or judgment.
  The Workflow Trace exists precisely so a human can veto.
- **Not model-locked.** The `LLMBackend` protocol means the same
  dispatch can run against Mock (CI), OpenAI, Anthropic, or Moka AI
  without touching agent code.

---

## 6. The "Why Now"

Three trends converged in 2025-2026:

1. **LLM quality plateaued on single-shot tasks** but kept improving on
   specialized, role-conditioned prompts. The marginal value moved
   from "bigger model" to "better orchestration."
2. **Agent frameworks matured** (block/buzz, ACP, MCP) enough to make
   protocol-native composition realistic, not theoretical.
3. **Cost economics flipped.** Running 7 small specialized calls is
   now cheaper than 1 giant context-stuffed call, and the quality is
   higher because each role's prompt is not competing for attention.

DevSquad is positioned at the intersection of these three trends.

---

## 7. Success Criteria

We will know DevSquad is succeeding when:

- A new contributor can read `docs/VISION.md` and explain *why* the
  project exists without reading the code.
- A dispatch report's Workflow Trace section is sufficient for a human
  reviewer to understand *how* the team arrived at its conclusion.
- The anti-ghost `_call_counter` guarantee holds in CI: every module
  is provably exercised, no dead code pretending to be a feature.
- Cross-session search ("what did the architect decide last week?")
  returns the actual past Scratchpad entry, not a hallucination.
- The same dispatch produces the same agent_id across sessions when
  the role + backend + model configuration is unchanged.

Each of these maps to a concrete V4.4.x → V4.5.0 acceptance criterion.
The vision is not a slide deck; it is a set of testable properties.

---

## 8. Relationship to the Three VISION Documents

This document states the problem and the long-term direction.

- **[VISION_ORCHESTRATION.md](./VISION_ORCHESTRATION.md)** explains *why*
  the architecture is Loop Engineering + Consensus Engine + Anti-Ghost,
  not just *what* those components are.
- **[VISION_AGENT_COLLABORATION.md](./VISION_AGENT_COLLABORATION.md)**
  explains *why* multi-role beats single-AI, and what the "team"
  metaphor actually commits us to.

Read this one first. Then read the other two for the design rationale.

---

## 9. The One-Sentence Summary

> DevSquad exists because **single-AI reasoning lacks structured
> opposition**, and the fix is not a bigger model but a real team —
> seven roles, a shared blackboard, an enforced consensus process, and
> a traceable workflow log that survives the session.

Everything else is implementation detail.

---

**Maintained by**: DevSquad 7-Role Team
**License**: Same as the project root
