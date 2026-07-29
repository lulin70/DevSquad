# DevSquad P0-P3 Enhancement Review — 7-Role Consensus Report

> **Document Type**: 7-Role Review Report (Analysis)
> **Version**: v1.0
> **Date**: 2026-07-29
> **Author**: DevSquad 7-Role Consensus (Architect / PM / Security / Tester / Coder / DevOps / UI)
> **Review Method**: DevSquad 7-Role parallel evaluation (weighted voting + veto rules)
> **Status**: Approved — Consensus reached 7/7
> **Related Docs**: [V4.4.0 PRD](../prd/V4.4.0_PRD.md) | [V4.4.0 Architecture](../architecture/V4.4.0_ARCHITECTURE.md) | [V4.4.0 Test Plan](../testing/V4.4.0_TEST_PLAN.md) | [V4.4.0 Roadmap](../planning/V4.4.0_ROADMAP.md)

---

## 1. Background

DevSquad V4.3.2 is a multi-role AI orchestration Skill (159+ modules, 7 roles, 11-phase lifecycle). During the V4.3.2 retrospective, 8 enhancement candidates were surfaced from three domains (PMP risk management, SRE reliability engineering, TOGAF enterprise architecture). The 7 roles were tasked to review each candidate and decide one of three outcomes: **DO NOW** (implement in V4.4.0), **DEFER** (postpone to V4.5.0+), or **SKIP** (reject with rationale).

This document records the 7-role review opinions, the consensus conclusion, and the version-path decision that splits the work into V4.3.3 (documentation + E2E skeleton) and V4.4.0 (implementation).

---

## 2. Review Object — 8 Candidates

| ID | Domain | Source | Candidate | Estimated LOC |
|----|--------|--------|-----------|---------------|
| P0-1 | PMP | PMP Risk Register + 4 strategies | Risk Register | ~250 |
| P0-2 | TOGAF | TOGAF Architecture Views & Viewpoints | Viewpoint Registry | ~200 |
| P1-1 | SRE | SRE Error Budget | Error Budget Tracker | ~180 |
| P1-2 | TOGAF | TOGAF Gap Analysis + Roadmap | Gap Analyzer | ~220 |
| P2-1 | SRE | DORA Metrics (4 metrics) | DORA Metrics Collector | ~200 |
| P3-1 | PMP | PMP Earned Value Management | EVM Tracker | ~300 |
| P3-2 | SE | Mutation Testing | Mutation Testing Gate | ~400 + toolchain |
| P3-3 | TOGAF | TOGAF ADM Cycle | ADM Lifecycle Adapter | ~500 |

---

## 3. 7-Role Review Opinion Matrix

Voting legend: **DO** = DO NOW (V4.4.0), **DF** = DEFER (V4.5.0+), **SK** = SKIP. Weights: Architect 3.0, Security 2.5, PM 2.0, Tester 1.5, Coder 1.5, DevOps 1.0, UI 1.0.

| Candidate | Architect (3.0) | Security (2.5) | PM (2.0) | Tester (1.5) | Coder (1.5) | DevOps (1.0) | UI (1.0) | Weighted Outcome |
|-----------|-----------------|----------------|----------|--------------|-------------|--------------|----------|------------------|
| P0-1 Risk Register | DO | DO | DO | DO | DO | DO | DO | **DO NOW (7/7)** |
| P0-2 Viewpoint Registry | DO | DO | DO | DF | DO | DO | DO | **DO NOW (6/7)** |
| P1-1 Error Budget Tracker | DO | DO | DF | DO | DO | DO | DF | **DO NOW (5/7)** |
| P1-2 Gap Analyzer | DO | DF | DO | DO | DO | DF | DF | **DO NOW (5/7)** |
| P2-1 DORA Metrics | DO | DO | DF | DO | DF | DO | DF | **DO NOW (5/7)** |
| P3-1 EVM | SK | SK | DO | SK | SK | SK | SK | **SKIP (1/7)** |
| P3-2 Mutation Testing | SK | SK | SK | DO | SK | SK | SK | **SKIP (1/7)** |
| P3-3 TOGAF ADM | SK | SK | DF | SK | SK | SK | SK | **SKIP (0/7 DO)** |

### 3.1 Detailed Role Opinions

#### P0-1 Risk Register (PMP-1)
- **Architect (DO)**: Fills a real gap — current `UnifiedGateEngine` has no risk gate; phase gates cannot reason about probability × impact. Integrates cleanly via a new `GateType.RISK_CHECK`.
- **Security (DO)**: Risk register is the natural home for threat-modeling findings that currently have no persistent store. 4 strategies (avoid/transfer/mitigate/accept) map directly to security control selection.
- **PM (DO)**: PMP-1 is the highest-value PMP enhancement; user-visible Markdown "Risk Management" section increases stakeholder trust.
- **Tester (DO)**: Testable in isolation; data model is pure dataclass; xfail E2E skeleton is straightforward.
- **Coder (DO)**: ~250 LOC, single-file module, low integration surface, no God Class risk (SRP clean).
- **DevOps (DO)**: Markdown report section requires no dashboard changes; CI only needs to run the new module counter check.
- **UI (DO)**: Markdown output is enough for V4.4.0; no UI panel required (deferred to V4.5.0 if needed).

#### P0-2 Viewpoint Registry (TOGAF-2)
- **Architect (DO)**: Viewpoint orthogonality is the missing arbiter for `ConsensusEngine` conflicts — currently arbitration is role-weight only, viewpoint gives a structural axis.
- **Security (DO)**: Threat viewpoint formalizes what security already does ad hoc; gives a stable injection point via `PromptAssembler`.
- **PM (DO)**: Helps PM understand which stakeholder concern each role owns.
- **Tester (DF)**: Concerned that 7 viewpoints × consistency matrix may produce brittle tests; prefers deferring consistency check. Overruled — consistency check can be minimal in V4.4.0.
- **Coder (DO)**: Clean data model; 7 viewpoint definitions are static config.
- **DevOps (DO)**: No infra impact.
- **UI (DO)**: Interaction viewpoint is the UI role's formal hook into the architecture.

#### P1-1 Error Budget Tracker (SE-2)
- **Architect (DO)**: Error budget is the objective signal for the P10 deployment gate; replaces today's binary compliance check with a quantitative one.
- **Security (DO)**: Burn-rate status is a leading indicator for security-incident fatigue.
- **PM (DF)**: Worried SLO target tuning requires product input that V4.4.0 cannot afford. Overruled — default SLO target is conservative (99.9%) and configurable.
- **Tester (DO)**: Pure arithmetic module; easy to test boundary conditions (budget exactly 0, negative drift).
- **Coder (DO)**: ~180 LOC, no external dependencies.
- **DevOps (DO)**: Native fit — DevOps owns SRE practice.
- **UI (DF)**: Dashboard panel is extra work. Overruled — Dashboard panel is a thin read-only view, not a UI design task.

#### P1-2 Gap Analyzer (TOGAF-3)
- **Architect (DO)**: Closes the loop between P2 (target architecture) and P3 (gap identification); today the loop is implicit.
- **Security (DF)**: Concerned gap analysis without a security control catalog is shallow. Overruled — security gaps are a subset, not blocked.
- **PM (DO)**: Roadmap output is directly consumable by stakeholders.
- **Tester (DO)**: Gap prioritization logic is unit-testable.
- **Coder (DO)**: Clean data model.
- **DevOps (DF)**: No direct ops value. Overruled — deployment work-packages are a gap category.
- **UI (DF)**: No UI value. Overruled — Markdown roadmap is enough.

#### P2-1 DORA Metrics Collector (SE-1)
- **Architect (DO)**: DORA is the industry-standard delivery-performance signal; pairs with Error Budget (P1-1) to complete the reliability picture.
- **Security (DO)**: Change failure rate is a security-adjacent signal (failed changes often carry security regressions).
- **PM (DF)**: DORA is engineering metrics, not product. Overruled — PM consumes the report.
- **Tester (DO)**: Git-history extraction is deterministic; easy to test with fixture repos.
- **Coder (DF)**: Worried about git-history parsing edge cases (shallow clones, rebase). Overruled — graceful degradation on parse errors.
- **DevOps (DO)**: Native fit — DevOps owns DORA.
- **UI (DF)**: Dashboard panel only. Overruled — thin read-only panel.

#### P3-1 EVM (PMP-2) — SKIP
- **Architect (SKIP)**: EVM (Earned Value Management) assumes a project-plan baseline with PV/EV/AC; DevSquad tasks are ad-hoc dispatches with no stable WBS. Forcing EVM onto dispatch creates synthetic numbers.
- **Security (SKIP)**: No security value.
- **PM (DO)**: EVM is a PMP standard. Overruled — the standard assumes a plan-driven project; DevSquad is dispatch-driven.
- **Tester (SKIP)**: Hard to test meaningfully — EVM values are only as good as the WBS, which does not exist.
- **Coder (SKIP)**: ~300 LOC for synthetic numbers; not worth the maintenance.
- **DevOps (SKIP)**: No ops value.
- **UI (SKIP)**: No UI value.

#### P3-2 Mutation Testing (SE-4) — SKIP
- **Architect (SKIP)**: Mutation testing requires a mutation runner (mutmut / cosmic-ray) that multiplies test runtime by 10-50x. DevSquad's 8165+ tests already take meaningful CI time; mutation testing is not affordable in CI.
- **Security (SKIP)**: No direct security value.
- **PM (SKIP)**: ROI too low for V4.4.0.
- **Tester (DO)**: Mutation testing is the gold standard for test-suite quality. Overruled — the CI cost is prohibitive for V4.4.0; revisit when test count stabilizes.
- **Coder (SKIP)**: Toolchain integration is heavy and brittle.
- **DevOps (SKIP)**: CI runtime explosion.
- **UI (SKIP)**: No UI value.

#### P3-3 TOGAF ADM (TOGAF-1) — SKIP
- **Architect (SKIP)**: TOGAF ADM (Architecture Development Method) is an 8-phase enterprise cycle (Preliminary → A-H → Requirements Management). DevSquad's 11-phase lifecycle already covers the equivalent flow at a finer grain; bolting ADM on top creates a dual-lifecycle conflict.
- **Security (SKIP)**: No security value.
- **PM (DEFER)**: ADM has stakeholder value in enterprise contexts. Overruled — defer to V5.0.0 enterprise edition if ever.
- **Tester (SKIP)**: ADM is a process, not a testable unit.
- **Coder (SKIP)**: ~500 LOC of lifecycle mapping that duplicates `WorkflowEngine`.
- **DevOps (SKIP)**: No ops value.
- **UI (SKIP)**: No UI value.

---

## 4. Consensus Conclusion

**7/7 consensus reached** on the following split:

| Outcome | Count | Candidates |
|---------|-------|------------|
| **DO NOW (V4.4.0)** | 5 | P0-1 Risk Register, P0-2 Viewpoint Registry, P1-1 Error Budget Tracker, P1-2 Gap Analyzer, P2-1 DORA Metrics Collector |
| **SKIP** | 3 | P3-1 EVM, P3-2 Mutation Testing, P3-3 TOGAF ADM |
| **DEFER** | 0 | (none — all DEFER candidates were either overruled to DO NOW or downgraded to SKIP) |

### 4.1 Priority Ordering (DO NOW items)

```
P0-1 Risk Register  >  P0-2 Viewpoint Registry  >  P1-1 Error Budget  >  P1-2 Gap Analyzer  >  P2-1 DORA Metrics
       (1)                   (2)                       (3)                  (4)                   (5)
```

Rationale: Risk Register is the foundation (defines probability × impact vocabulary used by Error Budget and Gap Analyzer). Viewpoint Registry is next (defines the structural axis used by Gap Analyzer's target architecture). Error Budget before DORA because Error Budget gates P10 deployment directly, while DORA only reports. Gap Analyzer before DORA because Gap Analyzer feeds the LoopScheduler CONTINUE decision which is upstream of delivery performance.

---

## 5. Version Path Decision

The 7 roles agreed to split the work into two versions to respect the **document-first iron rule** and the **xfail TDD** discipline:

### 5.1 V4.3.3 (PATCH) — Documentation + E2E Skeleton

| Deliverable | Description |
|-------------|-------------|
| Review report | This file (`2026-07-29_P0P3_enhancement_review.md`) |
| Landing plan | `V4.4.0_PRD.md` + `V4.4.0_ARCHITECTURE.md` + `V4.4.0_TEST_PLAN.md` + `V4.4.0_ROADMAP.md` |
| E2E skeleton | 10-15 xfail TDD tests across 5 features (see Test Plan §3) |
| Code changes | **None** — no production modules added in V4.3.3 |

**Why PATCH (not MINOR)?** V4.3.3 adds no new module; it only adds documentation and xfail tests. SemVer permits PATCH for test additions.

### 5.2 V4.4.0 (MINOR) — Implementation

| Deliverable | Description |
|-------------|-------------|
| 5 new modules | `risk_register.py`, `viewpoint_registry.py`, `error_budget_tracker.py`, `gap_analyzer.py`, `dora_metrics_collector.py` |
| Integration points | `UnifiedGateEngine` (RISK_CHECK + P10 budget gate), `ConsensusEngine` (viewpoint arbitration), `WorkflowEngine` (phase risk check), `PromptAssembler` (viewpoint spec injection), `LoopScheduler` (gap-based CONTINUE), `Dashboard` (budget + DORA panels) |
| Anti-ghost | Module-level `_call_counter` + dispatch hook auto-trigger + CI `check_module_activation.py` |
| Tests | Turn xfail → xpass; full 7-dimension coverage |

**Why MINOR (not MAJOR)?** All 5 modules are additive — no existing API is broken. New `GateType.RISK_CHECK` is an enum extension (backward compatible). Dashboard panels are new (additive).

---

## 6. SKIP Rationale Summary

| Candidate | Skip Reason | Revisit Trigger |
|-----------|-------------|-----------------|
| P3-1 EVM (PMP-2) | Dispatch-driven model has no WBS baseline; EVM values would be synthetic | If DevSquad adds a project-plan mode (V5.0.0) |
| P3-2 Mutation Testing (SE-4) | CI runtime 10-50x explosion; toolchain brittle | When test count stabilizes and CI budget allows (V5.0.0+) |
| P3-3 TOGAF ADM (TOGAF-1) | Duplicates `WorkflowEngine` 11-phase lifecycle; dual-lifecycle conflict | If DevSquad ships an enterprise edition (V5.0.0) |

---

## 7. Anti-Ghost Feature Hard Constraints (Carry-Forward to V4.4.0)

The 7 roles explicitly recorded the anti-ghost constraints that V4.4.0 must satisfy. These are non-negotiable:

| # | Constraint | Verification |
|---|------------|--------------|
| AG-1 | Each of the 5 modules must have a module-level `_call_counter` | `check_module_activation.py` reports counter > 0 for each module after a real dispatch |
| AG-2 | Each module must be auto-triggered by a dispatch hook (not only by direct CLI) | E2E test: a full `dispatch()` call increments every module's counter |
| AG-3 | Risk Register, Error Budget, and DORA must surface in the Markdown report | Report contains "Risk Management" / "Reliability" / "Delivery Performance" sections |
| AG-4 | Viewpoint Registry must inject viewpoint spec into prompts via `PromptAssembler` | Integration test asserts prompt contains viewpoint section |
| AG-5 | Gap Analyzer must feed `LoopScheduler` CONTINUE decision | Integration test asserts CONTINUE/STOP reflects gap-closure delta |
| AG-6 | No module may be "orphan" (defined but never called) | CI gate fails if any module counter == 0 over a 7-day window |

---

## 8. Change History

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-07-29 | v1.0 | Initial creation; 8 candidates reviewed; 5 DO NOW + 3 SKIP; V4.3.3/V4.4.0 split decided; 6 anti-ghost constraints recorded | DevSquad 7-Role Consensus |

---

> **Document Status**: Approved — 7/7 consensus
> **Next Step**: V4.3.3 creates the 4 landing-plan documents (PRD / Architecture / Test Plan / Roadmap) + xfail E2E skeleton; V4.4.0 implements the 5 modules.
