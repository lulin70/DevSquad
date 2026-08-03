# Vision: Agent Collaboration — Why Multi-Role Beats Single-AI

> **Status**: Living document. Last revised 2026-08-03 (V4.4.4).
> **Audience**: Anyone asking "why seven roles instead of one smart prompt?"
> **Prerequisite**: Read [VISION.md](./VISION.md) first.
> **Inspiration**: block/buzz (github.com/block/buzz) — "Agent as Team Member"

---

## 1. The Team Metaphor, Taken Seriously

Most "multi-agent" frameworks use the team metaphor as marketing. A
generic LLM is wrapped, called seven times with seven system prompts,
and the results are concatenated. That is not a team. That is a single
player wearing seven hats.

DevSquad takes the metaphor literally. A real software team has
properties that a single-AI-with-seven-prompts cannot replicate:

- **Independent reasoning contexts.** Each engineer reads the spec and
  forms their *own* view before the standup. They do not see each
  other's drafts first.
- **Structured conflict.** When the security engineer and the architect
  disagree, the disagreement is named, tracked, and resolved through a
  defined process — not averaged into a compromise no one would defend.
- **Persistent identity.** The same engineer who decided "use Postgres"
  last month is the one you ask about it today. Their past decisions are
  queryable, not lost to the void.
- **Shared workspace with history.** The team's Slack, tickets, and PRs
  are searchable months later. "Why did we pick this library?" has an
  answer.

Each of these maps to a concrete DevSquad module. The metaphor is the
architecture.

---

## 2. The Seven Roles — Why These Seven

DevSquad ships with seven default roles: Architect, Product Manager,
Security, Tester, Solo-Coder, DevOps, UI Designer. The count is not
arbitrary; it reflects the **minimum role set** that covers the
disciplines a non-trivial software task needs.

### The coverage argument

A task like "add RBAC to the auth service" touches:

- **Requirements** (PM): what does "RBAC" mean for this product?
- **Architecture** (Architect): where does the policy engine live?
- **Implementation** (Solo-Coder): the actual code.
- **Security** (Security): is the policy enforcement tamper-proof?
- **Quality** (Tester): does the test suite cover deny-paths?
- **Deployment** (DevOps): feature flag + rollback strategy.
- **Usability** (UI Designer): how does an admin assign roles?

Remove any role and you get a blind spot. Remove Security and the
crypto-scheme change ships unreviewed. Remove Tester and "it works on my
machine" becomes the CI. Remove DevOps and the feature flag is a
post-deploy afterthought.

### Why not more roles?

Seven is the sweet spot where:

- Every dimension of a real task has an owner.
- The Consensus Engine's vote math stays tractable (7 voters, weighted).
- The dispatch cost is bounded (7 LLM calls, parallelizable).

Adding roles (e.g. "Database Engineer", "SRE") is possible via
`ROLE_REGISTRY`, but each addition increases consensus coordination
cost. Seven is the default; it is not a ceiling.

---

## 3. Why Specialized Workers Beat One Generalist

The counter-argument: "A frontier model can play all seven roles in one
prompt." We have three objections.

### 3.1 Context contamination

When one LLM plays all roles in a single context, the architect's draft
primes the tester. The tester is no longer independent — it has already
seen the answer it is supposed to verify. This is the well-known
"priming effect" in cognitive science, and it destroys the value of
independent review.

DevSquad's Workers run with **separate contexts**. The Tester Worker
does not see the Architect's output until it writes its own findings to
the Scratchpad. Independence is preserved by construction, not by
prompt discipline.

### 3.2 Prompt specialization

A generalist prompt says "you are a helpful assistant." A specialist
prompt says "you are a Security Expert responsible for threat modeling
(STRIDE, DREAD), vulnerability audit (OWASP Top 10), compliance checks
(GDPR, SOC2)…" The specialist prompt activates domain-specific
reasoning patterns the generalist prompt does not.

The role-specific mock backend (`role_specific_mock_backend.py`) exists
precisely to verify that role specialization produces differentiated
output. If all seven roles emit the same template, the specialization
is fake.

### 3.3 Accountability

A generalist LLM cannot be held accountable for a dimension it
under-invested in. "The AI didn't focus on security" is un-actionable.
A Security Worker that abstained from a consensus vote is named in the
audit log. You can ask "why did security abstain?" and get a
Scratchpad entry back. Accountability requires a named agent.

---

## 4. The Scratchpad — Why a Shared Blackboard

Workers do not message each other directly. They all write to and read
from a single shared Scratchpad. This is not a performance choice; it
is a **governance** choice.

### 4.1 Auditability

If Worker A messages Worker B privately, that exchange is invisible to
the human reviewer. The dispatch report cannot show it. The Scratchpad
is the **only** communication channel, so everything is auditable:

```
Worker A writes FINDING → Worker B reads FINDING → Worker B writes CONFLICT →
Consensus Engine resolves → DECISION written back to Scratchpad
```

Every arrow is in the Scratchpad log.

### 4.2 Conflict surfacing

A FINDING that contradicts another FINDING becomes a CONFLICT entry.
The Scratchpad does not silently merge them. The conflict is a
first-class object with its own lifecycle (ACTIVE → RESOLVED). This
forces disagreement into the open where the Consensus Engine can act
on it.

### 4.3 Cross-session persistence (V4.4.3+)

The Scratchpad is in-memory for the hot path, but the
`ScratchpadHistoryStore` mirrors every write to SQLite. Three weeks
later, a human can search "what did the architect decide about the
auth migration?" and get the actual past entry. This is what
block/buzz calls "workspace persistence" — the team's history is
searchable, not ephemeral.

---

## 5. Agent Identity — Why "Which AI?" Matters

V4.4.3 introduced `AgentIdentity`: a deterministic `agent_id` derived
from (role, backend, model). The same configuration produces the same
agent_id across sessions.

This sounds like bookkeeping. It is actually the foundation of
**agent accountability**.

### The problem without identity

If the architect role uses GPT-4 today and Claude-3 tomorrow, "the
architect decided X" is meaningless — it was a different AI each time.
You cannot track behavior, debug regressions, or trust consistency.

### The identity contract

`agent_id = agent-{role}-{sha256(role:backend:model)[:8]}`. Same
config → same ID. Different config → different ID. The audit log
records the agent_id, so "which AI instance made this decision?" is a
queryable fact, not a mystery.

This is a deliberately *deterministic* identity, not a cryptographic
one. We do not need to prove the agent is who it claims to be (there is
no adversary model here). We need to **correlate** the same agent's
behavior across sessions. SHA-256 of the config tuple is sufficient.

---

## 6. Branch-as-Context — Why Git Awareness (V4.4.4)

A team that doesn't know which branch it's on is working in a vacuum.
block/buzz maps git branches to channels so context is aggregated per
branch. DevSquad's V4.4.4 `GitContext` does a simpler version: when
`dispatch(git_context=...)` is called, the Coordinator's prompt
includes the current branch, recent commits, and open issues.

### Why this matters

Without git context:

- The Architect proposes a design that conflicts with an in-flight
  refactor on another branch.
- The Tester writes cases for the wrong API shape (the one on `main`,
  not the one on the feature branch).
- The Coder suggests a fix that was already reverted in a recent commit.

With git context injected into the Coordinator prompt, every Worker
sees "we are on branch `feature/rbac`, recent commits include `revert:
old policy engine`." The team's analysis is grounded in the actual
state of the repository.

### The backward-compatibility contract

`git_context=None` is the default. Existing callers see no change. The
git context is an opt-in augmentation, not a breaking requirement.
This is why the auto_detect path catches all exceptions and returns
None on any failure — a non-git directory must not break dispatch.

---

## 7. The Workflow Trace — Why Transparency (V4.4.4)

A dispatch produces a final result. But the *process* by which that
result was reached was previously invisible. The user sees "the team
decided X" but not:

- How the task was decomposed.
- Which roles executed which steps.
- Where the Consensus Engine was invoked.
- How long each step took.

The V4.4.4 `WorkflowTrace` renders this into the dispatch report as a
`## Workflow Trace` section. This is not a debugging aid; it is a
**trust mechanism**.

### Trust requires verifiability

If a human reviewer cannot see how the team reached its conclusion, the
conclusion is a black box. The Workflow Trace turns the dispatch from a
black box into an audit log. You can:

- See the decomposition tree (task → subtasks → roles).
- Verify that every expected role actually ran (step table).
- Find the decision points where consensus was invoked.
- Spot the slow step that took 80% of the duration.

### Anti-ghost integration

The Workflow Trace is always set on the result (even if empty for
dry_run), and its construction increments the module-level
`_call_counter`. If the trace is absent from a dispatch report, CI
fails. There is no way for the trace to silently disappear.

---

## 8. What the Team Metaphor Commits Us To

Taking the team metaphor seriously means accepting obligations that a
"single AI" product does not have:

1. **Every role must be exercisable in isolation.** A role that only
   works when other roles are present is not a team member, it is a
   subroutine. The `role_specific_mock_backend` verifies each role
   produces differentiated output alone.
2. **Every decision must have a Scratchpad trail.** A decision made in
   the LLM's hidden context, never written to the Scratchpad, did not
   happen as far as the audit log is concerned.
3. **Every conflict must be resolvable, not ignorable.** The
   Consensus Engine does not have a "skip" outcome. SPLIT and ESCALATED
   are explicit states that require human attention.
4. **Every new module must be anti-ghost-instrumented.** A module
   without a `_call_counter` is a ghost. It will fail CI. There is no
   exemption.
5. **Every session must leave a queryable trace.** The Scratchpad history
   store, the audit log, and the Workflow Trace together ensure that
   "what happened in this dispatch?" is answerable weeks later.

These obligations are the cost of the team metaphor. They are also the
value.

---

## 9. The One-Paragraph Summary

> A single AI with seven prompts is not a team; it is one player wearing
> seven hats, and the hats do not actually disagree. DevSquad's seven
> Workers run in **separate contexts**, write to a **shared Scratchpad**
> that preserves history, surface conflicts as **first-class objects**
> for the Consensus Engine, carry **deterministic agent identities**
> across sessions, and leave a **Workflow Trace** so a human can audit
> the process — not just the result. The team metaphor is the
> architecture; the architecture is the metaphor.

---

**Maintained by**: DevSquad 7-Role Team (PM-led, Architect-reviewed)
**See also**: [VISION.md](./VISION.md), [VISION_ORCHESTRATION.md](./VISION_ORCHESTRATION.md)
