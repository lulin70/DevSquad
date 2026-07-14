# DevSquad Project Constitution

> **Document Type**: Project Constitution
> **Responsible**: Multi-Role Consensus
> **Location**: `docs/spec/CONSTITUTION.md`
> **Version**: V2.0 | **Status**: Approved
> **活文档原则**: 本文档与代码同步演进，每次版本发布时同步更新所有数据点。

---

## Document Info

| Item | Content |
|------|---------|
| Project Name | DevSquad — Multi-Role AI Task Orchestrator |
| Version | V4.0.11 (Production-Ready with 185+ Core Modules) |
| Created | 2026-03-16 |
| Last Updated | 2026-07-14 |
| Status | Active |

---

## Change History

| Version | Date | Author | Changes | Status |
|---------|------|--------|---------|--------|
| v2.0 | 2026-07-14 | DevSquad 7-Role Team | V4.0.11 活文档同步：更新版本/模块数/Python版本/生命周期阶段定义/生命周期模板；移除 SUPERSEDED 标注 | Approved |
| v1.1 | 2026-05-03 | DevSquad 7-Role Team | Added P0 Agent Skills Quality Framework implementation record | Approved |
| v1.0 | 2026-05-02 | DevSquad 7-Role Team | Initial constitution with iron rules | Approved |

---

## 0. Supreme Iron Rule: Documentation First, Trace Everything (文档先行，万事留痕)

> **This is the supreme law that governs all other rules in this project.**
> **Violating this rule is a critical error that invalidates all work done.**

### Core Principle

```
Before any code is written  → Plan/Spec document must exist
Before any change is made   → Impact analysis must be documented
After any work is done      → Results must be recorded in docs
After any decision is made   → Rationale must be traceable
```

### Mandatory Requirements (Non-Negotiable)

| Phase | Requirement | Verification |
|-------|-------------|--------------|
| **Pre-work** | No code without a spec/plan document | `docs/spec/` or `docs/prd/` has corresponding doc |
| **During work** | All decisions logged with rationale | Commit messages, ADRs, or inline comments explain WHY |
| **Post-work** | All affected docs updated synchronously | Version/module count/test count consistent across all docs |
| **Always** | No orphaned code without documentation origin traceable | Every file's purpose documented in at least one doc |

### Enforcement Mechanism

- CI check: `docs/` directory must have updated files matching code changes
- Review gate: PR reviewer checks doc sync status before approval
- Consensus: Coordinator verifies documentation completeness before consensus vote
- Retroactively: Work done without prior docs MUST be backfilled immediately

### Origin

Established: 2026-05-02 by project owner mandate.
Rationale: Without documentation-first discipline, knowledge evaporates, decisions become untraceable, and technical debt compounds invisibly.

---

## 1. Project Vision

### 1.1 Mission
- Transform single AI tasks into multi-role AI collaboration with quality guarantees
- Make AI-assisted development as reliable as senior engineer-led development
- Bridge the gap between "AI can write code" and "AI can write production-quality code"

### 1.2 Core Values
- **Quality over speed**: Correctness > Speed. Fast wrong code is worse than slow right code.
- **Evidence over assertion**: "Seems right" is never sufficient. Proof required.
- **Collaboration over isolation**: Multiple perspectives catch what one misses.
- **Documentation over memory**: If it's not written down, it doesn't exist.

### 1.3 Non-Negotiable Principles

| # | Principle | Description |
|---|-----------|-------------|
| NNP-1 | Documentation First | No code without a plan/spec doc (Supreme Iron Rule) |
| NNP-2 | Test Before Trust | No code accepted without tests proving it works |
| NNP-3 | Security by Default | All inputs treated as hostile until validated |
| NNP-4 | Evidence Required | Every completion claim needs verifiable evidence |
| NNP-5 | Anti-Rationalization | Common AI excuses are pre-emptively blocked |
| NNP-6 | Incremental Delivery | Changes in ~100-line slices, each tested independently |

---

## 2. Technical Non-Negotiables

### 2.1 Quality Standards

| Standard | Requirement | Source |
|----------|-------------|--------|
| Python version | ≥3.10 (pure Python, no compiled deps) | pyproject.toml |
| Test coverage | Core modules >= 80%, overall >= 75% (CI gate) | pytest --cov --cov-fail-under=75 |
| Code comments | English only for all code comments | Style guide |
| Docstrings | All public methods must have Args/Returns | Lint check |
| Type hints | All function signatures typed | mypy/mypy compatible |

### 2.2 Security Standards

| Standard | Requirement | Source |
|----------|-------------|--------|
| Input validation | 53 detection patterns (15 forbidden + 13 SSRF + 5 suspicious + 20 prompt injection) | input_validator.py |
| API key protection | Environment variables ONLY, never CLI args | llm_backend.py |
| Path traversal | User IDs validated against base directory | rule_collector.py |
| Thread safety | Shared resources protected by locks | mce_adapter.py, scratchpad.py |

### 2.3 Architecture Standards

| Standard | Requirement | Source |
|----------|-------------|--------|
| Module pattern | Coordinator/Worker/Scratchpad three-layer | dispatcher.py |
| Role system | 7 core roles with weighted consensus | consensus.py |
| Graceful degradation | All integrations degrade safely when unavailable | protocols.py, null_providers.py |
| i18n support | ZH/EN/JP output matching user language | cli.py, dispatcher.py |

---

## 3. Process Non-Negotiables

### 3.1 Development Lifecycle

```
P1(Requirements Analysis) → P2(Architecture Design) → P3(Technical Design)
→ P4(Data Design, opt) → P5(Interaction Design, opt) → P6(Security Review, opt)
→ P7(Test Planning) → P8(Implementation) → P9(Test Execution)
→ P10(Deployment & Release) → P11(Operations & Assurance, opt)
```

**11 阶段生命周期** (P4/P5/P6/P11 为可选阶段):

| # | Phase | Lead | Optional | Gate Condition |
|---|-------|------|----------|----------------|
| P1 | Requirements Analysis | pm | ❌ | Acceptance criteria quantifiable |
| P2 | Architecture Design | architect | ❌ | Weighted consensus ≥70% |
| P3 | Technical Design | architect+coder | ❌ | API specs unambiguous |
| P4 | Data Design | architect | ✅ | 3NF or denormalization justified |
| P5 | Interaction Design | ui-designer | ✅ | Core flow usability verified |
| P6 | Security Review | security | ✅ | No P0/P1 vulns, compliance green |
| P7 | Test Planning | tester | ❌ | Test plan review passed |
| P8 | Implementation | solo-coder | ❌ | Code review passed, no P0 defects |
| P9 | Test Execution | tester | ❌ | Coverage≥80% + P7 plan 100% executed |
| P10 | Deployment & Release | devops | ❌ | Deployment drill passed |
| P11 | Operations & Assurance | devops+sec | ✅ | P99<target, alerts 100% |

**5 种生命周期模板**:

| Template | Phases | Use Case |
|----------|--------|----------|
| `full` | P1-P11 | Complete project |
| `backend` | No P5 | Backend services |
| `frontend` | No P4, P6 | Frontend applications |
| `internal_tool` | No P4, P5, P6, P11 | Internal tools |
| `minimal` | P1, P3, P7, P8, P9 | Minimum set |

> **真相源**: `scripts/collaboration/workflow_engine_base.py:233-385` (PHASE_TEMPLATES + LIFECYCLE_TEMPLATES)

Each phase has:
- **Entry gate**: Requirements from previous phase
- **Exit gate**: Deliverables that must be produced
- **Gate strictness**: MANDATORY — non-compliance blocks advancement

### 3.2 Delivery Workflow (Closed Loop)

```
Implement → Test(Regression ALL) → Code Walkthrough → Annotate 
→ Docs Update → Cleanup → Git Push
```

**All 7 steps mandatory after every push.**

### 3.3 Decision Recording

Every significant decision must be recorded in at least ONE of:
- Architecture Decision Record (ADR) in `docs/architecture/`
- Commit message with decision rationale
- Inline comment explaining the `why` (not just `what`)
- SPEC/PRD document update

---

## 4. Governance Mechanism

### 4.1 Role Responsibilities

| Role | Weight | Primary Responsibility | Veto Power |
|------|--------|---------------------|------------|
| Architect | 1.5 | System design, tech selection, architecture review | Yes (design) |
| Product Manager | 1.2 | Requirements, PRD, user stories, acceptance criteria | Yes (scope) |
| Security Expert | 1.1 | Threat modeling, vulnerability audit, OWASP compliance | Yes (security) |
| Tester | 1.0 | Test strategy, quality gates, coverage analysis | Yes (quality) |
| Coder | 1.0 | Implementation, code review, optimization | No |
| DevOps | 1.0 | CI/CD, deployment, monitoring, infrastructure | No |
| UI Designer | 0.9 | UX design, interaction, accessibility | No |

### 4.2 Change Management

| Change Type | Approval Required | Documentation Required |
|-------------|------------------|---------------------|
| New module | Architect + PM | SPEC + SKILL.md update |
| Bug fix | Affected role(s) | Changelog entry |
| Feature enhancement | PM + relevant roles | PRD/SPEC update + GUIDE update |
| Breaking change | Full 7-role consensus | Full documentation cycle |
| Documentation only | Self-approved | Version bump in docs |

### 4.3 Consensus Rules

- Weighted voting (role weights above)
- Any role with veto power can block
- Unresolved conflicts escalate to human
- Quorum: ≥50% of total weight must participate

---

## 5. Iron Rules Summary

All iron rules are documented in [SKILL.md](../SKILL.md). Quick reference:

| # | Iron Rule | Category | Penalty |
|---|----------|----------|---------|
| **0** | **Documentation First, Trace Everything** | Supreme Law | Critical — invalidates work |
| 1 | Documentation First — Never Write API Calls From Memory | Testing | Serious |
| 2 | Failure Means Report — Never Modify Assertions to Pass | Testing | Serious |
| 3 | Dimension Completeness — Never Only Test Happy Path | Testing | Serious |
| 4 | Mandatory Post-push Closed Loop (7 steps) | Delivery | Serious |
| 5 | Doc Coverage Checklist (Step 5 checks ALL categories) | Delivery | Serious |
| 6 | Cleanup Rules (no residual temp files) | Delivery | Serious |

---

## 6. Appendix

### 6.1 Key References

| Document | Location | Purpose |
|----------|----------|---------|
| SKILL.md | Root | Complete skill manual with iron rules |
| GUIDE.md | Root | User guide (Chinese) |
| CLAUDE.md | Root | Claude Code integration instructions |
| INSTALL.md | Root | Installation guide |
| CHANGELOG.md | Root | Version history |
| CONSTITUTION.md | docs/spec/ | This file — supreme project rules |

### 6.2 Terminology

| Term | Definition |
|------|-----------|
| Iron Rule (铁律) | Non-negotiable requirement; violation is a serious/critical error |
| Supreme Iron Rule (最高铁律) | Documentation First, Trace Everything — governs all other rules |
| Anti-Rationalization (反合理化) | Pre-emptive blocking of common AI excuses for skipping quality steps |
| Red Flag (红旗) | Early warning signal indicating a problem pattern |
| Verification Gate (验证门禁) | Mandatory evidence requirement before accepting completion |
| Intent→WorkflowChain (意图→工作流链) | Automatic workflow activation based on user intent detection |
| Consensus (共识) | Weighted voting mechanism with veto power for multi-role decisions |

---

**Document End**

> This constitution is established by DevSquad 7-Role Team consensus.
> Any modification requires full 7-role review and >80% weighted approval.
> The Supreme Iron Rule (Section 0) may NOT be modified or weakened under any circumstance.
