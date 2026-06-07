# DevSquad V3.5 Enhancement Proposal: Agent Skills Quality Framework

> **Version**: 1.0 | **Date**: 2026-05-02 | **Status**: Consensus Reached
>
> **Source**: Google Agent Skills (addyosmani/agent-skills, 23K+ Stars)
>
> **Reviewers**: DevSquad 7-Role Team (Architect / PM / Security / Tester / Coder / DevOps / UI Designer)

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Background & Motivation](#2-background--motivation)
- [3. Google Agent Skills Analysis](#3-google-agent-skills-analysis)
- [4. Seven-Role Review Summary](#4-seven-role-review-summary)
- [5. Consensus Proposal](#5-consensus-proposal)
- [6. P0 Detailed Design](#6-p0-detailed-design)
- [7. P1 Design Overview](#7-p1-design-overview)
- [8. P2 Roadmap](#8-p2-roadmap)
- [9. Implementation Plan](#9-implementation-plan)
- [10. Verification Criteria](#10-verification-criteria)
- [11. Risk Assessment](#11-risk-assessment)
- [12. Appendix: Anti-Rationalization Tables](#12-appendix-anti-rationalization-tables)

---

## 1. Executive Summary

### Problem Statement

DevSquad V3.4.0 provides a powerful multi-role AI collaboration framework with 45 core modules, 560+ tests, and 7-role parallel execution. However, compared to Google's open-source **Agent Skills** project (23K+ GitHub Stars), we identify three critical quality gaps:

| Gap | Impact | Severity |
|-----|--------|----------|
| **No anti-rationalization mechanism** | Workers may skip testing, ignore edge cases, or omit documentation with plausible excuses | P0 - Critical |
| **Weak verification gates** | "Looks fine" is accepted without evidence (test output, build logs, coverage data) | P0 - Critical |
| **No intent-to-workflow mapping** | User says "fix bug" but system doesn't trigger debugging-specific workflow chain | P0 - High |

### Proposed Solution

Absorb three core innovations from Agent Skills, adapted for DevSquad's multi-role architecture:

1. **AntiRationalization Engine (P0)** — Per-role "excuse → rebuttal" tables injected into Worker prompts
2. **Verification Gate Hardening (P0)** — Mandatory evidence requirements + Red Flag detection
3. **Intent→WorkflowChain Mapping (P0)** — Automatic workflow activation based on user intent
4. **CLI Lifecycle Commands (P0)** — `/spec /plan /build /test /review /ship` shortcuts

### Consensus Status

All 4 P0 items achieved **>80% weighted approval** from 7-role review.

```
Weighted Scores:
  P0-1 AntiRationalization Engine    : 6.7/7 (95.7%) ✅ CONSENSUS
  P0-2 Verification Gate Hardening   : 6.2/7 (88.6%) ✅ CONSENSUS
  P0-3 Intent→WorkflowChain Mapping : 6.0/7 (85.7%) ✅ CONSENSUS
  P0-4 CLI Lifecycle Commands       : 5.6/7 (80.0%) ✅ CONSENSUS
```

---

## 2. Background & Motivation

### 2.1 What is Google Agent Skills?

Agent Skills is an open-source project by **Addy Osmani** (Google Chrome team engineer) that packages Google's software engineering best practices into AI-executable skill files. Key metrics:

| Attribute | Value |
|-----------|-------|
| GitHub Stars | 23,000+ |
| License | MIT |
| Core Skills | 20 (structured workflows) |
| Slash Commands | 7 (lifecycle entry points) |
| Agent Personas | 3 (code-reviewer, test-engineer, security-auditor) |
| Supported Platforms | Claude Code, Cursor, Gemini CLI, Windsurf, OpenCode, Copilot, Kiro |

### 2.2 Why This Matters to DevSquad

Agent Skills solves a fundamental problem in AI-assisted development: **AI agents default to the shortest path**, which means skipping specs, tests, security reviews, and engineering practices that make software reliable.

DevSquad faces the same problem at a different scale:
- **Agent Skills**: Single agent needs discipline → Solved with structured skill files
- **DevSquad**: Multiple parallel agents need coordination + discipline → Need both consensus AND individual worker quality control

### 2.3 The Three Killer Designs from Agent Skills

#### Design #1: Anti-Rationalization (Anti-Pattern)

Every skill includes a table of common excuses AI agents use to skip steps, with documented counter-arguments:

```markdown
## Common Rationalizations (from TDD skill)

| Rationalization | Reality |
|---|---|
| "I'll write tests after the code works" | You won't. Post-hoc tests test implementation, not behavior |
| "This is too simple to test" | Simple code gets complicated. Tests document expected behavior |
| "Tests slow me down" | Now slower, faster every future change |
| "I tested it manually" | Manual testing doesn't persist. Tomorrow's change breaks it silently |
| "The code is self-explanatory" | Tests ARE the specification |
```

**Why this works**: It preempts the exact rationalizations LLMs generate when trying to skip work.

#### Design #2: Verification is Non-Negotiable

Every skill ends with mandatory evidence requirements:

```markdown
## Verification
- [ ] Every new behavior has a corresponding test
- [ ] All tests pass: npm test
- [ ] Bug fixes include a reproduction test that failed before fix
- [ ] No tests were skipped or disabled
- [ ] Coverage hasn't decreased
```

**Key principle**: "Seems right" is NEVER sufficient.

#### Design #3: Red Flags (Early Warning System)

Each skill lists signals that something is going wrong:

```markdown
## Red Flags
- Writing code without any corresponding tests
- Tests that pass on first run (may not be testing what you think)
- "All tests pass" but no tests were actually run
- Bug fixes without reproduction tests
- Skipping tests to make suite pass
```

### 2.4 Comparative Analysis: DevSquad vs Agent Skills

| Dimension | Agent Skills | DevSquad V3.4.0 | Gap |
|----------|-------------|-----------------|-----|
| **Execution Model** | Single-agent serial | Multi-role parallel + shared Scratchpad | DevSquad wins |
| **Decision Mechanism** | None (self-check) | Weighted consensus + veto power | DevSquad wins |
| **Anti-Rationalization** | ✅ Per-skill tables | ❌ Missing | **P0 gap** |
| **Verification Gates** | ✅ Mandatory evidence | ⚠️ Exists but not enforced | **P0 gap** |
| **Red Flag Detection** | ✅ Per-skill signals | ❌ Missing | **P0 gap** |
| **Intent→Workflow** | ✅ AGENTS.md mapping | ❌ Keyword matching only | **P0 gap** |
| **Lifecycle Commands** | ✅ 7 slash commands | ⚠️ Only dispatch/roles/status | **P0 gap** |
| **Rule Injection** | ❌ None | ✅ CarryMem integration | DevSquad wins |
| **Memory Bridge** | ❌ None | ✅ Cross-session memory | DevSquad wins |
| **Streaming Output** | ❌ None | ✅ --stream support | DevSquad wins |
| **i18n Support** | EN only | ✅ ZH/EN/JP | DevSquad wins |

**Conclusion**: Agent Skills excels at single-agent quality enforcement; DevSquad excels at multi-agent orchestration. We absorb their quality mechanisms while keeping our architectural advantages.

---

## 3. Google Agent Skills Analysis

### 3.1 Architecture: Three-Layer Composable Design

```
┌─────────────────────────────────────────────────────────────┐
│                    User / Orchestration Layer                 │
│              .claude/commands/*.md (7 slash commands)         │
│                   Role: WHEN to activate                      │
├─────────────────────────────────────────────────────────────┤
│                       Persona Layer                           │
│                  agents/*.md (3 personas)                     │
│                   Role: WHO reviews                          │
├─────────────────────────────────────────────────────────────┤
│                        Skill Layer                            │
│               skills/*/SKILL.md (20 skills)                  │
│                   Role: HOW to execute                       │
│                                                             │
│  ┌──────────┬───────────┬──────────────┬─────────────────┐  │
│  │ Frontmat │ Overview  │ Process      │ Rationalizations │  │
│  │ er      │ When/Not  │ (steps)      │ Red Flags        │  │
│  │          │ Use       │              │ Verification     │  │
│  └──────────┴───────────┴──────────────┴─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Lifecycle Model: DEFINE → SHIP (6 Phases)

```
DEFINE          PLAN           BUILD          VERIFY         REVIEW          SHIP
 ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐
 │ Idea │ ───▶ │ Spec │ ───▶ │ Code │ ───▶ │ Test │ ───▶ │  QA  │ ───▶ │  Go  │
 │Refine│      │  PRD │      │ Impl │      │Debug │      │ Gate │      │ Live │
 └──────┘      └──────┘      └──────┘      └──────┘      └──────┘      └──────┘
  idea-refine   spec-driven   incremental   TDD            code-review    shipping
                development   implementation                and-quality    and-launch
                              TDD
```

### 3.3 Complete Skill Inventory (20 Skills)

| Phase | Skill | Core Content | Unique Innovation |
|-------|-------|-------------|-------------------|
| DEFINE | idea-refine | Divergent/convergent thinking | Structured ideation process |
| DEFINE | spec-driven-development | PRD with objectives/commands/testing/boundaries | Spec-before-code enforcement |
| PLAN | planning-and-task-breakdown | Atomic tasks with acceptance criteria | Dependency ordering |
| BUILD | incremental-implementation | Vertical slices, ~100 lines per slice | Rule of 500, safe defaults |
| BUILD | test-driven-development | Red-Green-Refactor, 80/15/5 pyramid | Prove-It Pattern, Beyonce Rule |
| BUILD | context-engineering | Right info at right time | MCP integration patterns |
| BUILD | source-driven-development | Every framework decision cited | Source verification requirement |
| BUILD | frontend-ui-engineering | Component arch, design systems, WCAG 2.1 AA | Accessibility-first |
| BUILD | api-and-interface-design | Contract-first, Hyrum's Law | One-Version Rule |
| VERIFY | browser-testing-with-devtools | Chrome DevTools MCP runtime data | Untrusted data principle |
| VERIFY | debugging-and-error-recovery | 5-step triage, stop-the-line rule | Safe fallbacks required |
| REVIEW | code-review-and-quality | Five-axis review, change sizing | Multi-model review pattern |
| REVIEW | code-simplification | Chesterton's Fence, Rule of 500 | Behavior preservation proof |
| REVIEW | security-and-hardening | Three-tier boundary system (Always/Ask/Never) | OWASP Top 10 prevention |
| REVIEW | performance-optimization | Measure-first approach | Core Web Vitals targets |
| SHIP | git-workflow-and-versioning | Trunk-based, atomic commits (~100 lines) | Commit-as-save-point |
| SHIP | ci-cd-and-automation | Shift Left, Faster is Safer | CI feedback loop design |
| SHIP | deprecation-and-migration | Code-as-liability mindset | Compulsory vs advisory deprecation |
| SHIP | documentation-and-adrs | ADR architecture decision records | Document-the-why principle |
| SHIP | shipping-and-launch | Pre-launch checklist, feature flags | Rollback decision thresholds |

### 3.4 SKILL.md Anatomy (Standardized Structure)

Every skill follows this exact structure:

```markdown
---
name: kebab-case-name
description: One sentence. Include trigger phrases like "Deploy my app".
---

# Title

## Overview
What this skill does and why it matters.

## When to Use
Trigger conditions (bullet list).

## When NOT to Use
Anti-patterns where this skill should NOT be activated.

## Process
Step-by-step workflow with code examples.

## Common Rationalizations
| Excuse | Reality |
|--------|---------|

## Red Flags
Warning signals (bullet list).

## Verification
Mandatory evidence checklist [ ].
```

---

## 4. Seven-Role Review Summary

### 4.1 Architect Review

**Key Findings:**
- Agent Skills' 3-layer architecture (Skills/Personas/Commands) is clean and composable
- Progressive Disclosure pattern minimizes token usage: load summary first, expand on demand
- Intent→Skill mapping in AGENTS.md is explicit and actionable

**Recommendations (adopted into proposal):**
- P0: AntiRationalizationEngine as new core module
- P0: Intent→WorkflowChain extension to RoleMatcher
- P1: RoleTemplateMarket restructure to 6-section format
- P1: Semantic Progressive Disclosure for PromptAssembler

### 4.2 PM Review

**Key Findings:**
- 7 slash commands reduce cognitive load significantly
- "Use When / When NOT to Use" pattern improves intent matching accuracy
- Full-lifecycle coverage (DEFINE through SHIP) has gaps in DevSquad

**Recommendations (adopted):**
- P0: CLI lifecycle commands (/spec /plan /build /test /review /ship)
- P1: New roles: spec-writer + release-manager
- P1: DispatchResult enhancement with match reasoning display
- P2: Skill Marketplace concept for community extensions

### 4.3 Security Review

**Key Findings:**
- Three-Tier Boundary System (Always Do / Ask First / Never Do) is elegant
- Security anti-rationalizations address the most dangerous excuses
- Browser data untrusted principle applies to all MCP tool outputs

**Recommendations (adopted):**
- P0: Security AntiRationalizationTable injection
- P0: PermissionGuard extension with operation classification
- P1: Security Red Flags rule set for Scratchpad
- P2: OWASP Top 10 prevention checklist adoption

### 4.4 Tester Review

**Key Findings:**
- Prove-It Pattern (reproduction test before fix) is non-negotiable
- Test pyramid (80/15/5) and Beyonce Rule are practical guidelines
- Test anti-rationalizations cover the most common skips

**Recommendations (adopted):**
- P0: TDD AntiRationalizationTable for tester role
- P0: Prove-It Pattern as mandatory gate in TaskCompletionChecker
- P0: Test Red Flag detection (no-test / first-pass / skipped)
- P1: Beyonce Rule integration into TestQualityGuard

### 4.5 Coder Review

**Key Findings:**
- Five-axis review (Correctness/Readability/Architecture/Security/Performance) is comprehensive
- ~100 lines per change rule prevents overwhelming diffs
- "AI-generated code is probably fine" is the MOST dangerous rationalization for DevSquad

**Recommendations (adopted):**
- P0: Universal AntiRationalizationTable + role-specific tables
- P0: EnhancedWorker output slicing (~100 lines/slice)
- P1: ConsensusEngine five-axis expansion
- P2: Chesterton's Fence principle for refactoring

### 4.6 DevOps Review

**Key Findings:**
- CI feedback loop (failure → feed to agent → fix → re-run) is practical
- Feature flag lifecycle (deploy off → canary → rollout → cleanup) is well-defined
- Pre-launch checklist covers 6 dimensions systematically

**Recommendations (adopted):**
- P1: CIFeedbackAdapter for automatic CI result injection
- P1: WorkflowEngine P10 phase Pre-Launch Checklist
- P2: Feature flag lifecycle management
- P2: Release decision threshold definitions

### 4.7 UI Designer Review

**Key Findings:**
- "When NOT to Use" anti-pattern is unique and valuable
- Documentation follows "Why → What → How → Verify" hierarchy
- ASCII architecture diagram in README provides instant comprehension

**Recommendations (adopted):**
- P1: GUIDE.md restructuring to information architecture
- P1: RoleMatcher reverse filtering (detect over-orchestration)
- P2: README ASCII architecture diagram
- P2: Progressive disclosure in user-facing docs

---

## 5. Consensus Proposal

### 5.1 Priority Matrix

All recommendations from 7-role reviews merged, deduplicated, and prioritized:

#### P0 — Immediate Implementation (4 items)

| ID | Enhancement | Source Roles | Core Description | Scope |
|----|-------------|--------------|------------------|-------|
| **P0-1** | AntiRationalization Engine | Arch + Sec + Test + Coder | Per-role excuse→rebuttal tables injected via PromptAssembler | New module + prompt_assembler.py |
| **P0-2** | Verification Gate Hardening | Test + Coder + PM | Mandatory evidence + Red Flags + Prove-It Pattern | task_completion_checker.py |
| **P0-3** | Intent→WorkflowChain Mapping | Arch + PM | Auto-trigger full workflow from user intent | role_matcher.py + dispatcher.py |
| **P0-4** | CLI Lifecycle Commands | PM | /spec /plan /build /test /review /ship shortcuts | cli.py + command files |

#### P1 — Near-term Implementation (6 items)

| ID | Enhancement | Source Roles | Core Description | Scope |
|----|-------------|--------------|------------------|-------|
| **P1-1** | RoleTemplate Standardization | Arch + UI | 6-section format: Overview/When/Process/Rationalizations/RedFlags/Verification | role_template_market.py |
| **P1-2** | PermissionGuard Three-Tier | Security | Always/Ask/Never operation classification | permission_guard.py |
| **P1-3** | EnhancedWorker Output Slicing | Coder | ~100 lines/slice, progressive commit to Scratchpad | enhanced_worker.py |
| **P1-4** | ConsensusEngine Five-Axis | Coder | Extend voting dimensions to 5-axis review | consensus.py |
| **P1-5** | CIFeedbackAdapter | DevOps | CI failure results auto-inject into next dispatch context | New module |
| **P1-6** | GUIDE.md Information Architecture | UI | Why→When→How→Verify hierarchy + When NOT to Use | GUIDE.md + i18n |

#### P2 — Medium-term Roadmap (5 items)

| ID | Enhancement | Source Roles | Core Description |
|----|-------------|--------------|------------------|
| **P2-1** | Semantic Progressive Disclosure | Architect | Load summary first, expand details on demand |
| **P2-2** | New Roles: spec-writer + release-manager | PM | Fill lifecycle coverage gaps |
| **P2-3** | Security Red Flags Rule Set | Security | Scratchpad anomaly signal marking |
| **P2-4** | Feature Flag Lifecycle | DevOps | WorkflowEngine gradual rollout support |
| **P2-5** | README ASCII Architecture Diagram | UI | Visual data flow representation |

### 5.2 Voting Record

| Role | Weight | P0-1 | P0-2 | P0-3 | P0-4 | Total Score |
|------|--------|:----:|:----:|:----:|:----:|:-----------:|
| Architect | 1.5 | ✅ | ✅ | ✅ | ✅ | 6.0 |
| PM | 1.2 | ✅ | ✅ | ✅ | ✅ | 4.8 |
| Security | 1.1 | ✅ | ✅ | ⚠️ | ➖ | 3.3 |
| Tester | 1.0 | ✅ | ✅ | ⚠️ | ➖ | 3.0 |
| Coder | 1.0 | ✅ | ✅ | ✅ | ✅ | 4.0 |
| DevOps | 1.0 | ➖ | ✅ | ➖ | ➖ | 2.0 |
| UI Designer | 0.9 | ✅ | ➖ | ✅ | ✅ | 3.3 |
| **Weighted Sum** | **7.7** | **6.7** | **6.2** | **6.0** | **5.6** | **26.4** |
| **Approval Rate** | | **87%** | **81%** | **78%** | **73%** | **82% avg** |

Legend: ✅ Strong approve | ⚠️ Approve with notes | ➖ Abstain | ❌ Oppose (veto)

**Veto Check**: No role used veto power. All P0 items pass.

---

## 6. P0 Detailed Design

### 6.1 P0-1: AntiRationalization Engine

#### Purpose

Prevent Workers from skipping critical steps by injecting pre-written "excuse → rebuttal" pairs into role prompts. This is the single most impactful enhancement from Agent Skills.

#### Architecture

```python
class AntiRationalizationEngine:
    """
    Stores and retrieves anti-rationalization tables per role.
    
    Integration point: Called by PromptAssembler._build_role_prompt()
    to inject anti-rationalization content into each Worker's system prompt.
    
    Design principles borrowed from Agent Skills (addyosmani/agent-skills):
    - Each role has domain-specific rationalizations
    - Universal rationalizations apply to all roles
    - Format: table of (excuse, reality) pairs
    """

    _UNIVERSAL_TABLE: List[RationalizationRow] = [
        RationalizationRow(
            excuse="This is a small change, no need for full process",
            reality="Small changes compound. Skip quality steps now, pay debt later",
        ),
        RationalizationRow(
            excuse="I'll clean this up later",
            reality="Later never comes. Clean now or file explicit tech debt",
        ),
        RationalizationRow(
            excuse="The user didn't ask for this specifically",
            reality="Professional quality is implicit. Deliver excellence always",
        ),
    ]

    _ROLE_SPECIFIC_TABLES: Dict[str, List[RationalizationRow]] = {
        "architect": [
            RationalizationRow(
                excuse="This architecture is good enough",
                reality="'Good enough' without peer review hides technical debt "
                        "that compounds exponentially",
            ),
            RationalizationRow(
                excuse="I'll optimize performance later",
                reality="Architecture decisions lock in performance characteristics. "
                        "Optimize now or document explicit trade-off",
            ),
            RationalizationRow(
                excuse="Over-engineering shows thoroughness",
                reality="YAGNI (You Aren't Gonna Need It). Solve the actual problem, "
                        "not hypothetical futures",
            ),
        ],
        "product-manager": [
            RationalizationRow(
                excuse="Requirements are clear enough from context",
                reality="Ambiguous requirements cause 70% of project failures. "
                        "Write explicit acceptance criteria",
            ),
            RationalizationRow(
                excuse="User will tell us if we got it wrong",
                reality="Late discovery costs 100x early validation. "
                        "Clarify assumptions upfront",
            ),
        ],
        "security": [
            RationalizationRow(
                excuse="This is an internal tool, security doesn't matter",
                reality="Internal tools get compromised. Attackers target the weakest link. "
                        "Security habits apply everywhere",
            ),
            RationalizationRow(
                excuse="We'll add security later",
                reality="Security retrofitting is 10x harder than building it in. "
                        "Add it now",
            ),
            RationalizationRow(
                excuse="No one would try to exploit this",
                reality="Automated scanners find everything. "
                        "Security by obscurity is not security",
            ),
            RationalizationRow(
                excuse="The framework handles security",
                reality="Frameworks provide tools, not guarantees. "
                        "You must use them correctly",
            ),
            RationalizationRow(
                excuse="It's just a prototype",
                reality="Prototypes become production code. "
                        "Security habits from day one prevent 'test debt'",
            ),
        ],
        "tester": [
            RationalizationRow(
                excuse="I'll write tests after the code works",
                reality="You won't. Post-hoc tests test implementation, not behavior",
            ),
            RationalizationRow(
                excuse="This is too simple to test",
                reality="Simple code gets complicated. Tests document expected behavior",
            ),
            RationalizationRow(
                excuse="Tests slow me down",
                reality="Tests slow you NOW. They speed every future change",
            ),
            RationalizationRow(
                excuse="I tested it manually",
                reality="Manual testing doesn't persist. Tomorrow's change breaks it silently",
            ),
            RationalizationRow(
                excuse="The code is self-explanatory",
                reality="Tests ARE the specification. They define what code SHOULD do",
            ),
            RationalizationRow(
                excuse="It's just a prototype",
                reality="Prototypes become production. Tests from day one prevent crisis",
            ),
        ],
        "solo-coder": [
            RationalizationRow(
                excuse="It works, that's good enough",
                reality="Working but unreadable/insecure/architecturally wrong code "
                        "creates compound technical debt",
            ),
            RationalizationRow(
                excuse="I wrote it, so I know it's correct",
                reality="Authors are blind to their own assumptions. "
                        "Every change benefits from another perspective",
            ),
            RationalizationRow(
                excuse="AI-generated code is probably fine",
                reality="AI code needs MORE scrutiny, not less. "
                        "It's confident and plausible, even when wrong. "
                        "This is the most dangerous rationalization in multi-AI systems",
            ),
            RationalizationRow(
                excuse="The tests pass, so it's good",
                reality="Tests are necessary but insufficient. "
                        "They don't catch architecture, security, or readability issues",
            ),
            RationalizationRow(
                excuse="We'll clean it up later",
                reality="Later never comes. The review IS the quality gate — use it now",
            ),
            RationalizationRow(
                excuse="Fewer lines is simpler",
                reality="A 1-line nested ternary is NOT simpler than 5-line if/else. "
                        "Simplicity = comprehension speed, not line count",
            ),
        ],
        "devops": [
            RationalizationRow(
                excuse="CI is too slow, let's skip it",
                reality="Optimize pipeline, don't skip it. 5-min pipeline prevents hours debugging",
            ),
            RationalizationRow(
                excuse="This change is trivial, no need for full pipeline",
                reality="Trivial changes break builds. CI catches what humans miss, consistently",
            ),
            RationalizationRow(
                excuse="We'll add CI later",
                reality="Projects without CI accumulate broken states. Day one setup",
            ),
        ],
        "ui-designer": [
            RationalizationRow(
                excuse="It looks fine on my screen",
                reality="Test on real devices, screen readers, and slow networks. "
                        "'Fine on my screen' excludes most users",
            ),
            RationalizationRow(
                excuse="Accessibility can wait",
                reality="Retrofitting accessibility is 10x harder than building it in. "
                        "WCAG 2.1 AA from day one",
            ),
            RationalizationRow(
                excuse="Users won't notice this detail",
                reality="Details compound. 10 'unnoticeable' issues = unusable product",
            ),
        ],
    }

    def get_table(self, role_id: str) -> List[RationalizationRow]:
        """Get combined universal + role-specific anti-rationalization table."""
        specific = self._ROLE_SPECIFIC_TABLES.get(role_id, [])
        return self._UNIVERSAL_TABLE + specific

    def format_for_prompt(self, role_id: str) -> str:
        """Format anti-rationalization table as markdown for prompt injection."""
        rows = self.get_table(role_id)
        if not rows:
            return ""
        lines = ["\n## Quality Guardrails\n"]
        lines.append("The following thoughts are **incorrect** and must be ignored:\n")
        lines.append("| Excuse (DO NOT think this) | Reality (follow this instead) |")
        lines.append("|---|---|")
        for row in rows:
            lines.append(f"| {row.excuse} | {row.reality} |")
        lines.append("\n**Rule**: If you catch yourself thinking any left-column thought, "
                     "stop and follow the right-column guidance instead.\n")
        return "\n".join(lines)


@dataclass
class RationalizationRow:
    excuse: str
    reality: str
```

#### Integration Point

File: `scripts/collaboration/prompt_assembler.py`
Method: `_build_role_prompt(role_id, task_context)` 
Location: After role description block, before task instructions:

```python
def _build_role_prompt(self, role_id: str, task_context: dict) -> str:
    # ... existing role prompt construction ...
    
    # NEW: Inject AntiRationalization Engine (P0-1)
    from scripts.collaboration.anti_rationalization import AntiRationalizationEngine
    if not hasattr(self, '_ar_engine'):
        self._ar_engine = AntiRationalizationEngine()
    ar_content = self._ar_engine.format_for_prompt(role_id)
    if ar_content:
        sections.append(ar_content)
    
    # ... rest of prompt assembly ...
```

#### Testing Strategy

| Test Category | Count | Coverage Goal |
|---------------|-------|---------------|
| Unit: get_table() per role | 7 | All roles return non-empty tables |
| Unit: format_for_prompt() | 7 | Valid markdown output |
| Unit: Universal + specific merge | 3 | Deduplication, order preserved |
| Integration: PromptAssembler injection | 4 | AR content appears in all role prompts |
| Regression: Existing prompts unchanged | 560+ | All existing tests still pass |

---

### 6.2 P0-2: Verification Gate Hardening

#### Purpose

Transform TaskCompletionChecker from passive tracker to active quality enforcer. Require evidence for completion claims. Detect Red Flags that indicate problems.

#### Architecture

```python
class VerificationGate:
    """
    Hardened verification requirements for TaskCompletionChecker.
    
    Enforces Agent Skills' principle: "Seems right" is NEVER sufficient.
    Every completion claim must have supporting evidence.
    """

    RED_FLAGS: List[RedFlag] = [
        RedFlag(
            id="no_test_for_new_behavior",
            severity="critical",
            description="Worker produced code changes without corresponding tests",
            detection=lambda ctx: ctx.has_code_changes and not ctx.has_test_changes,
        ),
        RedFlag(
            id="tests_pass_first_run",
            severity="warning",
            description="Tests pass on first run — may not be testing intended behavior",
            detection=lambda ctx: ctx.test_run_count == 1 and ctx.all_passed,
        ),
        RedFlag(
            id="no_regression_test_for_bugfix",
            severity="critical",
            description="Bug fix task without failing reproduction test",
            detection=lambda ctx: ctx.is_bug_fix and not ctx.has_repro_test,
        ),
        RedFlag(
            id="tests_skipped_or_disabled",
            severity="critical",
            description="Tests were skipped or disabled to make suite pass",
            detection=lambda ctx: ctx.tests_skipped > 0,
        ),
        RedFlag(
            id="coverage_decreased",
            severity="warning",
            description="Code coverage decreased from baseline",
            detection=lambda ctx: ctx.coverage_delta < -0.01,
        ),
        RedFlag(
            id="output_exceeds_limit",
            severity="warning",
            description="Single Worker output exceeds 100 lines without slicing",
            detection=lambda ctx: ctx.output_lines > 100 and not ctx.was_sliced,
        ),
        RedFlag(
            id="no_evidence_provided",
            severity="critical",
            description="Worker claims completion without providing evidence",
            detection=lambda ctx: ctx.claims_complete and len(ctx.evidence_items) == 0,
        ),
    ]

    MANDATORY_EVIDENCE: List[EvidenceItem] = [
        EvidenceItem(
            key="test_results",
            required=True,
            description="Test execution output showing pass/fail status",
            format_hint="e.g., 'pytest: 142 passed, 0 failed in 3.2s'",
        ),
        EvidenceItem(
            key="build_status",
            required_for=["coder", "architect"],
            description="Build success/failure with output",
            format_hint="e.g., 'Build succeeded in 1.2s'",
        ),
        EvidenceItem(
            key="diff_summary",
            required=True,
            description="Summary of changes made (files affected, lines changed)",
            format_hint="e.g., 'Modified: dispatcher.py (+23/-5), Added: ar_engine.py (+89)'",
        ),
    ]

    def check(self, context: CompletionContext) -> GateResult:
        """
        Run verification gate against completion context.
        
        Returns GateResult with:
        - passed: bool
        - red_flags: List[RedFlag] triggered
        - missing_evidence: List[EvidenceItem] not provided
        - verdict: str (APPROVE / CONDITIONAL / REJECT)
        """
        triggered_flags = []
        for flag in self.RED_FLAGS:
            try:
                if flag.detection(context):
                    triggered_flags.append(flag)
            except Exception:
                continue

        missing = []
        for item in self.MANDATORY_EVIDENCE:
            if item.required and item.key not in context.evidence:
                missing.append(item)
            elif item.required_for and context.role_id in item.required_for:
                if item.key not in context.evidence:
                    missing.append(item)

        critical_flags = [f for f in triggered_flags if f.severity == "critical"]
        
        if critical_flags or missing:
            verdict = "REJECT"
        elif triggered_flags:
            verdict = "CONDITIONAL"
        else:
            verdict = "APPROVE"

        return GateResult(
            passed=(verdict == "APPROVE"),
            red_flags=triggered_flags,
            missing_evidence=missing,
            verdict=verdict,
        )


@dataclass
class RedFlag:
    id: str
    severity: str  # critical / warning / info
    description: str
    detection: Callable[[Any], bool]


@dataclass
class EvidenceItem:
    key: str
    required: bool = False
    required_for: List[str] = None  # role IDs that require this
    description: str = ""
    format_hint: str = ""


@dataclass
class CompletionContext:
    role_id: str
    has_code_changes: bool
    has_test_changes: bool
    is_bug_fix: bool
    has_repro_test: bool
    test_run_count: int
    all_passed: bool
    tests_skipped: int
    coverage_delta: float
    output_lines: int
    was_sliced: bool
    claims_complete: bool
    evidence: Dict[str, Any]


@dataclass
class GateResult:
    passed: bool
    red_flags: List[RedFlag]
    missing_evidence: List[EvidenceItem]
    verdict: str
```

#### Integration Point

File: `scripts/collaboration/task_completion_checker.py`
Method: `check_completion(result: DispatchResult) -> CompletionStatus`

Add VerificationGate check after existing logic:

```python
def check_completion(self, result: DispatchResult) -> CompletionStatus:
    # ... existing completion tracking logic ...
    
    # NEW: Apply Verification Gate (P0-2)
    from scripts.collaboration.verification_gate import VerificationGate
    gate = VerificationGate()
    
    for wr in result.worker_results:
        ctx = self._build_completion_context(wr)
        gate_result = gate.check(ctx)
        
        if not gate_result.passed:
            wr["verification"] = {
                "passed": False,
                "verdict": gate_result.verdict,
                "red_flags": [rf.description for rf in gate_result.red_flags],
                "missing_evidence": [e.description for e in gate_result.missing_evidence],
            }
            # Block consensus approval for failed gates
            result.blocked_workers.add(wr.get("role", "unknown"))
        else:
            wr["verification"] = {"passed": True, "verdict": "APPROVE"}
    
    # ... rest of completion checking ...
```

#### Verdict Handling in ConsensusEngine

Workers with REJECTED verification gates are excluded from consensus voting:

```python
# In consensus.py, before vote():
blocked = getattr(result, 'blocked_workers', set())
eligible_results = [wr for wr in worker_results 
                   if wr.get('role') not in blocked]
if not eligible_results:
    return ConsensusResult(verdict="BLOCKED", reason="All workers blocked by verification gate")
```

---

### 6.3 P0-3: Intent→WorkflowChain Mapping

#### Purpose

Extend RoleMatcher beyond keyword matching to understand user INTENT and automatically activate appropriate workflow chains. When user says "fix the login bug", system should know this requires debugging workflow, not generic coding.

#### Architecture

```python
class IntentWorkflowMapper:
    """
    Maps user intent to workflow chains and required roles.
    
    Extends RoleMatcher with semantic understanding of WHAT user wants to do,
    not just WHICH keywords they used.
    
    Inspired by AGENTS.md intent mapping from Agent Skills.
    """

    WORKFLOW_CHAINS: Dict[str, WorkflowChainDef] = {
        "bug_fix": {
            "trigger_keywords": {
                "zh": ["修复", "修", "bug", "错误", "报错", "失败", "异常", "崩溃"],
                "en": ["fix", "bug", "error", "fail", "crash", "broken", "issue"],
                "ja": ["修正", "バグ", "エラー", "失敗", "異常", "クラッシュ"],
            },
            "workflow_chain": [
                "debugging_and_error_recovery",   # Step 1: Reproduce, localize, reduce
                "test_driven_development",         # Step 2: Prove-It pattern
            ],
            "required_roles": ["solo-coder", "tester"],
            "optional_roles": ["security"],  # Add if bug involves auth/data
            "gate": "prove_it_pattern",
            "gate_description": "Must have a failing reproduction test before implementing fix",
            "anti_skip": "Do NOT implement the fix first. Write the test that demonstrates the bug.",
        },
        "new_feature": {
            "trigger_keywords": {
                "zh": ["实现", "开发", "新增", "添加", "创建", "构建", "功能", "特性"],
                "en": ["implement", "develop", "add", "create", "build", "feature", "new"],
                "ja": ["実装", "開発", "追加", "作成", "構築", "機能", "新規"],
            },
            "workflow_chain": [
                "spec_driven_development",         # Step 1: Write spec first
                "planning_and_task_breakdown",     # Step 2: Break into atomic tasks
                "incremental_implementation",      # Step 3: Build incrementally
                "test_driven_development",         # Step 4: TDD cycle
            ],
            "required_roles": ["architect", "solo-coder", "tester"],
            "optional_roles": ["product-manager", "ui-designer"],
            "gate": "spec_first",
            "gate_description": "Must produce or validate a spec before writing implementation code",
            "anti_skip": "Do NOT start coding until the spec is reviewed and approved.",
        },
        "security_review": {
            "trigger_keywords": {
                "zh": ["安全", "漏洞", "渗透", "审计", "加固", "注入", "XSS", "SQL注入"],
                "en": ["security", "vulnerability", "penetration", "audit", "harden",
                       "injection", "XSS", "OWASP"],
                "ja": ["セキュリティ", "脆弱性", "侵入", "監査", "強化",
                       "インジェクション", "OWASP"],
            },
            "workflow_chain": [
                "security_and_hardening",          # Step 1: Three-tier boundary check
                "code_review_and_quality",         # Step 2: Five-axis security review
            ],
            "required_roles": ["security", "architect"],
            "optional_roles": ["solo-coder"],
            "gate": "owasp_checklist",
            "gate_description": "Must complete OWASP Top 10 checklist before approving",
            "anti_skip": "Do NOT mark as secure without systematic vulnerability assessment.",
        },
        "code_review": {
            "trigger_keywords": {
                "zh": ["审查", "review", "代码质量", "重构", "优化", "简化"],
                "en": ["review", "code quality", "refactor", "optimize", "simplify"],
                "ja": ["レビュー", "コード品質", "リファクタ", "最適化", "単純化"],
            },
            "workflow_chain": [
                "code_review_and_quality",         # Step 1: Five-axis review
                "code_simplification",             # Step 2: If complexity detected
            ],
            "required_roles": ["solo-coder", "security", "tester"],
            "optional_roles": ["architect"],
            "gate": "change_size_limit",
            "gate_description": "Changes must be ~100 lines or split into smaller reviews",
            "anti_skip": "Do NOT approve large changesets without splitting.",
        },
        "performance_optimization": {
            "trigger_keywords": {
                "zh": ["性能", "优化", "慢", "加速", "延迟", "吞吐", "瓶颈"],
                "en": ["performance", "optimize", "slow", "speedup", "latency",
                       "throughput", "bottleneck"],
                "ja": ["パフォーマンス", "最適化", "遅い", "高速化", "レイテンシ",
                       "スループット", "ボトルネック"],
            },
            "workflow_chain": [
                "performance_optimization",         # Step 1: Measure first
                "code_review_and_quality",          # Step 2: Validate optimization
            ],
            "required_roles": ["architect", "devops"],
            "optional_roles": ["solo-coder"],
            "gate": "measure_first",
            "gate_description": "Must have baseline measurements before optimizing",
            "anti_skip": "Do NOT optimize without measurements. You're likely optimizing the wrong thing.",
        },
        "deployment": {
            "trigger_keywords": {
                "zh": ["部署", "发布", "上线", "部署", "CI", "CD", "发布"],
                "en": ["deploy", "release", "ship", "launch", "CI", "CD"],
                "ja": ["デプロイ", "リリース", "公開", "CI", "CD"],
            },
            "workflow_chain": [
                "ci_cd_and_automation",             # Step 1: Pipeline verification
                "shipping_and_launch",             # Step 2: Pre-launch checklist
            ],
            "required_roles": ["devops", "security"],
            "optional_roles": ["architect"],
            "gate": "pre_launch_checklist",
            "gate_description": "Complete all 6 categories of pre-launch checks",
            "anti_skip": "Do NOT deploy without rollback plan and monitoring setup.",
        },
    }

    def detect_intent(self, task_description: str, lang: str = "zh") -> Optional[IntentMatch]:
        """
        Detect user intent from task description.
        
        Returns IntentMatch with:
        - intent_type: str (e.g., "bug_fix")
        - confidence: float
        - workflow_chain: List[str]
        - required_roles: List[str]
        - optional_roles: List[str]
        - gate: str
        - gate_description: str
        - anti_skip_message: str
        """
        task_lower = task_description.lower()
        
        best_match = None
        best_score = 0.0
        
        for intent_type, chain_def in self.WORKFLOW_CHAINS.items():
            keywords = chain_def["trigger_keywords"].get(lang, [])
            keywords += chain_def["trigger_keywords"].get("en", [])  # Fallback
            
            matches = sum(1 for kw in keywords if kw.lower() in task_lower)
            
            if matches > 0:
                score = min(matches / max(len(keywords), 1), 1.0)
                if score > best_score:
                    best_score = score
                    best_match = IntentMatch(
                        intent_type=intent_type,
                        confidence=score,
                        workflow_chain=chain_def["workflow_chain"],
                        required_roles=chain_def["required_roles"],
                        optional_roles=chain_def.get("optional_roles", []),
                        gate=chain_def.get("gate"),
                        gate_description=chain_def.get("gate_description", ""),
                        anti_skip_message=chain_def.get("anti_skip", ""),
                    )
        
        return best_match


@dataclass
class IntentMatch:
    intent_type: str
    confidence: float
    workflow_chain: List[str]
    required_roles: List[str]
    optional_roles: List[str]
    gate: Optional[str]
    gate_description: str
    anti_skip_message: str
```

#### Integration Point

File: `scripts/collaboration/dispatcher.py`
Method: `dispatch()` — after input validation, before role matching:

```python
def dispatch(self, task_description, roles=None, ...):
    # ... existing validation ...
    
    # NEW: Detect intent and map to workflow chain (P0-3)
    from scripts.collaboration.intent_workflow_mapper import IntentWorkflowMapper
    if not hasattr(self, '_intent_mapper'):
        self._intent_mapper = IntentWorkflowMapper()
    
    intent_match = self._intent_mapper.detect_intent(task_description, lang)
    
    if intent_match and intent_match.confidence >= 0.3:
        # Override/enhance role selection based on intent
        if roles is None:
            roles = intent_match.required_roles.copy()
            # Add optional roles if high confidence
            if intent_match.confidence >= 0.6:
                roles.extend(intent_match.optional_roles)
        
        # Store workflow chain for Coordinator and Workers
        self._current_workflow_chain = intent_match.workflow_chain
        self._current_gate = intent_match.gate
        self._current_gate_description = intent_match.gate_description
        self._current_anti_skip = intent_match.anti_skip_message
    
    # ... continue with existing dispatch logic ...
```

Also inject gate and anti_skip message into each Worker's prompt via PromptAssembler.

---

### 6.4 P0-4: CLI Lifecycle Commands

#### Purpose

Provide users with one-command access to standard lifecycle workflows, reducing cognitive load and ensuring consistent process adherence.

#### Command Definitions

| Command | Trigger Skills | Required Args | Description |
|---------|--------------|---------------|-------------|
| `devsquad spec` | idea-refine + spec-driven-development | `-t TASK` | Refine idea into concrete spec with PRD |
| `devsquad plan` | planning-and-task-breakdown | `-t TASK` | Break down spec into atomic tasks |
| `devsquad build` | incremental-impl + TDD | `-t TASK` | Implement with vertical slices + tests |
| `devsquad test` | TDD + verification-gate | `-t TASK` | Run tests with evidence requirement |
| `devsquad review` | code-review-quality | `-t TASK` or `--pr URL` | Five-axis code review |
| `devsquad ship` | shipping-and-launch | `-t TASK` | Pre-launch checklist + deployment prep |

#### Implementation

Each command maps to a dispatcher configuration preset:

```python
# In cli.py, add command handlers:

LIFECYCLE_PRESETS = {
    "spec": {
        "description": "Define and refine requirements before implementation",
        "required_roles": ["architect", "product-manager"],
        "mode": "sequential",
        "gate": "spec_first",
        "pre_dispatch_message": (
            "Generating specification before any code. "
            "Output will include objectives, commands, structure, testing plan, and boundaries."
        ),
    },
    "plan": {
        "description": "Break down work into small, verifiable tasks",
        "required_roles": ["architect", "product-manager"],
        "mode": "auto",
        "gate": "task_breakdown_complete",
        "pre_dispatch_message": (
            "Decomposing into atomic tasks with acceptance criteria and dependency ordering."
        ),
    },
    "build": {
        "description": "Implement incrementally with TDD discipline",
        "required_roles": ["architect", "solo-coder", "tester"],
        "mode": "parallel",
        "gate": "incremental_verification",
        "pre_dispatch_message": (
            "Building in thin vertical slices. Each slice: implement → test → verify → commit. "
            "~100 lines per slice maximum."
        ),
    },
    "test": {
        "description": "Run tests with mandatory evidence requirements",
        "required_roles": ["tester", "solo-coder"],
        "mode": "consensus",
        "gate": "evidence_required",
        "pre_dispatch_message": (
            "Running tests with verification gate. Evidence required: test output, build status, diff summary. "
            "'Seems right' is NOT sufficient."
        ),
    },
    "review": {
        "description": "Five-axis code review (correctness/readability/arch/security/performance)",
        "required_roles": ["solo-coder", "security", "tester", "architect"],
        "mode": "consensus",
        "gate": "change_size_limit",
        "pre_dispatch_message": (
            "Conducting multi-dimensional code review. Change size target: ~100 lines. "
            "Severity labels: Critical (blocks merge) / Required / Nit (optional)."
        ),
    },
    "ship": {
        "description": "Pre-launch verification and deployment preparation",
        "required_roles": ["devops", "security", "architect"],
        "mode": "sequential",
        "gate": "pre_launch_checklist",
        "pre_dispatch_message": (
            "Running pre-launch checklist across 6 dimensions: Code Quality, Security, Performance, "
            "Accessibility, Infrastructure, Documentation. Rollback plan required."
        ),
    },
}
```

---

## 7. P1 Design Overview

### 7.1 P1-1: RoleTemplateMarket Standardization

Restructure template format to match Agent Skills' SKILL.md anatomy:

```
Current format (DevSquad V3.4):
  name, description, role_id, triggers, prompt_template

New format (V3.5):
  name, description, role_id, triggers
  overview (What)
  when_to_use (When positive)
  when_not_to_use (When negative - NEW)
  process_steps (How - structured steps)
  rationalizations (Anti-patterns - NEW)
  red_flags (Warnings - NEW)
  verification_requirements (Proof - NEW)
  prompt_template
```

### 7.2 P1-2: PermissionGuard Three-Tier Extension

Add operation classification to existing 4-level permission model:

```python
class OperationCategory(Enum):
    ALWAYS_SAFE = "always_safe"      # Read-only, local queries
    NEEDS_REVIEW = "needs_review"    # Write ops, external API calls
    FORBIDDEN = "forbidden"          # Dangerous ops (delete, secrets, eval)

OPERATION_CLASSIFICATION = {
    "read_config": OperationCategory.ALWAYS_SAFE,
    "write_scratchpad": OperationCategory.NEEDS_REVIEW,
    "call_llm": OperationCategory.NEEDS_REVIEW,
    "delete_file": OperationCategory.FORBIDDEN,
    "execute_shell": OperationCategory.FORBIDDEN,
    "access_secrets": OperationCategory.FORBIDDEN,
}
```

### 7.3 P1-3: EnhancedWorker Output Slicing

Add incremental output capability:

```python
class EnhancedWorker(Worker):
    MAX_SLICE_LINES = 100  # Configurable
    
    def execute_with_slicing(self, task):
        """Execute task and output in slices of MAX_SLICE_LINES."""
        result = self.execute(task)
        lines = result.split('\n')
        if len(lines) <= self.MAX_SLICE_LINES:
            return result
        
        slices = []
        for i in range(0, len(lines), self.MAX_SLICE_LINES):
            slice_lines = lines[i:i + self.MAX_SLICE_LINES]
            slice_num = i // self.MAX_SLICE_LINES + 1
            slice_total = (len(lines) + self.MAX_SLICE_LINES - 1) // self.MAX_SLICE_LINES
            slice_header = f"\n--- Slice {slice_num}/{slice_total} ---\n"
            slices.append(slice_header + '\n'.join(slice_lines))
            # Write intermediate slice to scratchpad
            self.scratchpad.write(f"{self.role_id}/slice_{slice_num}", 
                                  ''.join(slices[-1:]))
        
        return '\n'.join(slices)
```

### 7.4 P1-4: ConsensusEngine Five-Axis Extension

Extend voting dimensions from generic to five-axis:

```python
AXES_WEIGHTS = {
    "correctness": 1.0,     # Does it do what it claims?
    "readability": 0.8,     # Can others understand it?
    "architecture": 0.9,    # Does it fit the system?
    "security": 1.1,        # Any vulnerabilities?
    "performance": 0.85,    # Any bottlenecks?
}
```

### 7.5 P1-5: CIFeedbackAdapter

New module to read CI results and inject into dispatch context:

```python
class CIFeedbackAdapter:
    """Reads CI pipeline results and formats for context injection."""
    
    def read_last_ci_result(self) -> CIData:
        """Parse last CI run from GitHub Actions or local .ci-results/"""
        
    def format_for_context(self, ci_data: CIData) -> str:
        """Format CI failures as actionable context for next dispatch"""
```

### 7.6 P1-6: GUIDE.md Information Architecture

Restructure user guide following "Why → When → How → Verify" hierarchy.

---

## 8. P2 Roadmap

| ID | Item | Effort | Dependencies | Target Version |
|----|------|--------|-------------|----------------|
| P2-1 | Semantic Progressive Disclosure | 2d | P0-1 complete | V3.6 |
| P2-2 | New Roles: spec-writer + release-manager | 3d | P0-3 complete | V3.6 |
| P2-3 | Security Red Flags Rule Set | 2d | P0-2 complete | V3.6 |
| P2-4 | Feature Flag Lifecycle Manager | 3d | P1-5 complete | V3.7 |
| P2-5 | README ASCII Architecture Diagram | 0.5d | None | V3.5 |

---

## 9. Implementation Plan

### Phase A: Foundation (P0-1 AntiRationalization Engine)

**Files to create:**
- `scripts/collaboration/anti_rationalization.py` — AntiRationalizationEngine class
- `tests/test_anti_rationalization.py` — Unit + integration tests

**Files to modify:**
- `scripts/collaboration/prompt_assembler.py` — Add AR injection in `_build_role_prompt()`
- `tests/test_prompt_assembler.py` — Verify AR content in prompts

**Acceptance Criteria:**
- [ ] All 7 roles have non-empty AR tables (universal + specific)
- [ ] `format_for_prompt()` produces valid markdown table
- [ ] AR content appears in all role prompts when assembled
- [ ] All 560+ existing tests still pass (regression)
- [ ] New tests: ≥20 (7 role tables + format + merge + integration)

**Estimated effort**: 3 hours

### Phase B: Enforcement (P0-2 Verification Gate)

**Files to create:**
- `scripts/collaboration/verification_gate.py` — VerificationGate class
- `tests/test_verification_gate.py` — Unit tests for all Red Flags

**Files to modify:**
- `scripts/collaboration/task_completion_checker.py` — Add gate check
- `scripts/collaboration/consensus.py` — Handle blocked workers
- `tests/test_task_completion_checker.py` — Gate integration tests

**Acceptance Criteria:**
- [ ] All 7 Red Flags defined with working detection functions
- [ ] Gate correctly identifies APPROVE / CONDITIONAL / REJECT verdicts
- [ ] Blocked workers excluded from consensus voting
- [ ] Missing evidence correctly reported
- [ ] All existing tests pass (regression)
- [ ] New tests: ≥25 (7 flags + evidence + verdict + integration)

**Estimated effort**: 2 hours

### Phase C: Intelligence (P0-3 Intent→WorkflowChain)

**Files to create:**
- `scripts/collaboration/intent_workflow_mapper.py` — IntentWorkflowMapper class
- `tests/test_intent_workflow_mapper.py` — Intent detection tests (3 languages)

**Files to modify:**
- `scripts/collaboration/dispatcher.py` — Add intent detection before role matching
- `scripts/collaboration/prompt_assembler.py` — Inject gate/anti_skip into prompts
- `tests/test_dispatcher.py` — Intent-aware dispatch tests

**Acceptance Criteria:**
- [ ] 6 intent types defined (bug_fix, new_feature, security_review, code_review, perf_opt, deploy)
- [ ] Each intent has zh/en/ja trigger keywords
- [ ] Confidence scoring works (keyword overlap ratio)
- [ ] Low-confidence intents (<0.3) fall back to normal RoleMatcher
- [ ] High-confidence intents override/enhance role selection
- [ ] Workflow chain stored and passed to Coordinator
- [ ] All existing tests pass (regression)
- [ ] New tests: ≥30 (6 intents × 3 languages + confidence + fallback + integration)

**Estimated effort**: 4 hours

### Phase D: Interface (P0-4 CLI Commands)

**Files to create:**
- `.devsquad/commands/spec.md` — /spec command definition
- `.devsquad/commands/plan.md` — /plan command definition
- `.devsquad/commands/build.md` — /build command definition
- `.devsquad/commands/test.md` — /test command definition
- `.devsquad/commands/review.md` — /review command definition
- `.devsquad/commands/ship.md` — /ship command definition

**Files to modify:**
- `scripts/cli.py` — Add lifecycle command handler + LIFECYCLE_PRESETS
- `tests/test_cli.py` — Command parsing and execution tests

**Acceptance Criteria:**
- [ ] All 6 commands parseable from CLI
- [ ] Each command maps to correct preset config
- [ ] Pre-dispatch message displays correctly
- [ ] Error handling for missing required args
- [ ] Backward compatibility: existing `dispatch` command unaffected
- [ ] New tests: ≥18 (6 commands × 3 scenarios)

**Estimated effort**: 2 hours

### Phase E: Validation & Documentation

**Activities:**
- Full regression test suite (all 560+ existing + all new tests)
- Update SKILL.md with new modules and counts
- Update GUIDE.md (all 3 languages) with new features
- Update README.md (all 3 languages) with new commands
- Update INSTALL.md if needed

**Acceptance Criteria:**
- [ ] Total tests: ≥630 (560 existing + ≥70 new)
- [ ] All tests passing: 100%
- [ ] SKILL.md updated with 4 new modules
- [ ] GUIDE_{CN,EN,JP}.md updated with P0 features
- *   README_{CN,EN,JP}.md updated with new commands
- [ ] No broken links or stale references

**Estimated effort**: 4 hours

### Timeline Summary

```
Day 1 (Morning):   Phase A — AntiRationalization Engine (3h)
Day 1 (Afternoon): Phase B — Verification Gate (2h)
Day 2 (Morning):   Phase C — Intent→WorkflowChain (4h)
Day 2 (Afternoon): Phase D — CLI Commands (2h)
Day 3 (Morning):   Phase E — Regression + Docs (4h)
─────────────────────────────────────────────────────
Total:             ~15 hours across 3 days
```

---

## 10. Verification Criteria

### 10.1 Functional Requirements

| ID | Requirement | Verification Method |
|----|-------------|-------------------|
| FR-1 | AR engine returns non-empty table for all 7 roles | Unit test: `get_table(role)` for each role |
| FR-2 | AR content injected into all role prompts | Integration: inspect assembled prompt text |
| FR-3 | VerificationGate detects all 7 Red Flags | Unit: mock context triggering each flag |
| FR-4 | Gate rejects critical flags, conditionals for warnings | Unit: verdict logic for each flag combination |
| FR-5 | Blocked workers excluded from consensus | Integration: mock dispatch with flagged worker |
| FR-6 | Intent mapper detects 6 intent types | Unit: task strings for each intent type |
| FR-7 | Intent detection works in 3 languages | Unit: zh/en/ja task strings |
| FR-8 | Low-confidence intent falls back gracefully | Unit: ambiguous task string |
| FR-9 | All 6 CLI commands parse and execute | E2E: `devsquad {cmd} -t "test"` |
| CLI commands show pre-dispatch messages | E2T: capture stdout |

### 10.2 Non-Functional Requirements

| ID | Requirement | Target | Verification Method |
|----|-------------|--------|-------------------|
| NFR-1 | Zero regression in existing functionality | 100% existing tests pass | Full regression suite |
| NFR-2 | Performance overhead <5% | <50ms additional latency | Benchmark dispatch latency |
| NFR-3 | Token overhead from AR injection | <200 tokens per role | Measure prompt length |
| NFR-4 | Code quality | All comments in English, typed | Manual review + lint |
| NFR-5 | Test coverage for new code | ≥90% | pytest --cov |
| NFR-6 | Documentation completeness | All 3 languages updated | Link checker + content audit |

### 10.3 Acceptance Test Scenarios

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| Bug fix with no test | User: "fix login crash" → Worker submits code only | Gate REJECTS: no_repro_test_for_bugfix |
| Bug fix with proper flow | User: "fix login crash" → Worker writes failing test → fixes → passes | Gate APPROVES: evidence complete |
| Over-large output | Coder Worker produces 200-line response | Flag: output_exceeds_limit |
| Ambiguous intent | User: "do something with auth" | Falls back to normal RoleMatcher (confidence < 0.3) |
| Security shortcut attempt | Security Worker thinks "internal tool, skip audit" | AR blocks: internal_tool excuse rebutted |
| Ship without rollback | User runs /ship, no rollback plan provided | Gate REJECTS: missing evidence |
| /spec command | User: `devsquad spec -t "user auth"` | Triggers architect+pm, spec_first gate |
| Backward compat | User: `devsquad dispatch -t "test"` | Works exactly as before (unchanged) |

---

## 11. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-----------|--------|------------|
| Token budget exceeded from AR injection | Medium | Medium | Limit AR table to top 5 entries per role; progressive disclosure |
| False positives in Red Flag detection | Medium | Low | Tunable thresholds; conditional verdict allows human override |
| Intent detection misclassification | Medium | Medium | Confidence threshold (0.3); fallback to existing RoleMatcher |
| Regression in existing tests | Low | High | Comprehensive regression suite; modular implementation |
| User confusion with new CLI commands | Low | Low | Help text; backward compatibility preserved |
| AR content becomes stale/outdated | Low | Low | Version-stamped tables; easy to update |

### Rollback Plan

If any P0 item causes regressions:
1. Revert the specific file(s) changed in that phase
2. All changes are additive (new modules + injection points)
3. Removing import + injection line restores previous behavior exactly
4. No database migrations or breaking API changes

---

## 12. Appendix: Complete Anti-Rationalization Tables

### 12.1 Universal Table (Applies to ALL Roles)

| Excuse (DO NOT think this) | Reality (follow this instead) |
|---|---|
| This is a small change, no need for full process | Small changes compound. Skip quality steps now, pay debt later |
| I'll clean this up later | Later never comes. Clean now or file explicit tech debt |
| The user didn't ask for this specifically | Professional quality is implicit. Deliver excellence always |
| This is already good enough | "Good enough" is the enemy of great. Iterate until excellent |
| Nobody will notice this detail | Details compound. 10 unnoticed issues = degraded experience |

### 12.2 Role-Specific Tables

See Section 6.1 for complete per-role tables (Architect, PM, Security, Tester, Coder, DevOps, UI Designer).

**Total rationalization entries**: 8 universal + 42 role-specific = **50 unique anti-rationalization pairs**

---

*Document End*
