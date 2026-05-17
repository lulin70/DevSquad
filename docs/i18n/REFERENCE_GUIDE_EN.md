# DevSquad Reference Guide

> **Version**: V3.6.0 | **Updated**: 2026-05-05
>
> Complete feature manual for developers who need deep understanding of DevSquad capabilities.
> For quick start, see [QUICK_START_EN.md](QUICK_START_EN.md).

---

## Table of Contents

- [1. Core Architecture](#1-core-architecture)
- [2. Task Dispatch](#2-task-dispatch)
- [3. Full Lifecycle Development](#3-full-lifecycle-development)
- [4. Multi-Role Collaboration](#4-multi-role-collaboration)
- [5. Review and Consensus](#5-review-and-consensus)
- [6. Prompt Optimization](#6-prompt-optimization)
- [7. Inter-Agent Coordination](#7-inter-agent-coordination)
- [8. Rule Injection and Security](#8-rule-injection-and-security)
- [9. Quality Assurance](#9-quality-assurance)
- [10. Performance Monitoring](#10-performance-monitoring)
- [11. Role Template Market](#11-role-template-market)
- [12. Configuration System](#12-configuration-system)
- [13. Deployment Methods](#13-deployment-methods)
- [14. Agent Skills Quality Framework](#14-agent-skills-quality-framework)
- [15. FAQ](#15-faq)
- [Appendix A: CarryMem Integration](#appendix-a-carrymem-integration)
- [Appendix B: Complete Module List](#appendix-b-complete-module-list)

---

## 1. Core Architecture

DevSquad is built on a **Coordinator/Worker/Scratchpad** three-layer architecture:

```
User Task → [InputValidator Security Check]
           → [RoleMatcher Role Matching]
           → [Coordinator Global Orchestration]
             ├─ [preload_rules Rule Preloading]
             ├─ [ThreadPoolExecutor Parallel Workers]
             │   └─ Worker(Role Prompt + Rule Injection + Related Findings + QC Injection)
             │       ├─ [PromptAssembler Dynamic Assembly]
             │       ├─ [EnhancedWorker Enhancement: Cache/Retry/Monitor/Rules]
             │       └─ [Scratchpad Real-time Sharing]
             ├─ [ConsensusEngine Weighted Consensus]
             └─ [ReportFormatter Report Formatting]
           → Structured Report
```

**7 Core Roles**:

| Role | Short ID | Responsibility |
|------|----------|----------------|
| Architect | `arch` | System design, tech selection, architecture decisions |
| Product Manager | `pm` | Requirements analysis, user stories, prioritization |
| Security Expert | `sec` | Threat modeling, vulnerability audit, compliance |
| Tester | `test` | Test strategy, quality assurance, coverage |
| Coder | `coder` | Implementation, code review, performance optimization |
| DevOps Expert | `infra` | CI/CD, containerization, monitoring, infrastructure |
| UI Designer | `ui` | Interaction design, user experience, accessibility |

> 💡 **Quick installation guide**: See [QUICK_START_EN.md](QUICK_START_EN.md#installation) for setup instructions.

### Role Details and Typical Scenarios

**🏗️ Architect (arch)** — Weight 3.0, Veto Power

> The "chief designer" of the system, responsible for global technical decisions.

- **Scenario 1**: Building a SaaS platform from scratch — evaluates monolith vs microservices
- **Scenario 2**: Performance bottlenecks — analyzes root causes, proposes solutions
- **Scenario 3**: Tech selection debate — decides based on long-term maintainability

**📋 Product Manager (pm)** — Weight 2.0

> The "user advocate", ensuring technical solutions serve business goals.

- **Scenario 1**: Vague requirement "build a user growth system" — breaks down into modules
- **Scenario 2**: Refactoring assessment — ensures core functionality isn't disrupted
- **Scenario 3**: Conflicting requirements — prioritizes MVP scope

**🔒 Security Expert (sec)** — Weight 2.5, Veto Power

> The "gatekeeper" of the system for security-related decisions.

- **Scenario 1**: User authentication — evaluates OAuth2/JWT security
- **Scenario 2**: Third-party payments — reviews encryption, PCI-DSS compliance
- **Scenario 3**: Pre-launch audit — performs threat modeling (STRIDE)

**🧪 Tester (test)** — Weight 1.5

> The "quality gatekeeper", ensuring solutions withstand edge cases.

**💻 Coder (coder)** — Weight 1.5

> The "implementer", transforming designs into runnable code.

**🔧 DevOps Expert (infra)** — Weight 1.0

> The "infrastructure lead", ensuring stable production operations.

**🎨 UI Designer (ui)** — Weight 0.9

> The "experience shaper", ensuring user-friendly solutions.

### Role Selection Quick Reference

| Task Type | Recommended Roles | Notes |
|-----------|-------------------|-------|
| Quick code review | `coder` | Single role sufficient |
| API design | `arch coder` | Architect decides approach, coder defines interfaces |
| Security audit | `sec coder` | Security finds vulnerabilities, coder provides fixes |
| New feature development | `arch pm coder test` | Design → Requirements → Implementation → Verification |
| System launch | `arch sec infra test` | Architecture → Security → Deployment → Verification |
| Full project | All 7 roles | Complete lifecycle coverage |

---

## 2. Task Dispatch

> **When to use**: When you have a development task that requires multi-role collaborative analysis.

### Dispatch Method Comparison

| Method | Best For | Roles | Time | Example |
|--------|----------|-------|------|---------|
| Basic dispatch | Single question quick analysis | 1-3 | Seconds | "How to optimize this API" |
| Batch dispatch | Multiple independent tasks in parallel | 1-3 each | Parallel | Sprint requirement evaluation |
| Workflow engine | Complex project phased progression | 2-5 per phase | Minutes | "Build e-commerce platform" |

### 2.1 Basic Dispatch

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()

# Auto role matching
result = disp.dispatch("Design microservice architecture")

# Specify roles
result = disp.dispatch("Optimize API performance", roles=["architect", "coder"])

# Quick dispatch (simplified interface)
result = disp.quick_dispatch("Design database", output_format="structured")
```

> 📖 **See examples**: [examples/quick_demo.py](../../examples/quick_demo.py) for interactive demo.

### 2.2 Three Output Formats

- **structured** (default): Complete multi-role analysis report
- **compact**: Core conclusions + action items
- **detailed**: Includes analysis process and risk assessment

### 2.3 Batch Dispatch

```python
from scripts.collaboration.batch_scheduler import BatchScheduler

scheduler = BatchScheduler()
results = scheduler.schedule([
    "Design user authentication system",
    "Optimize database queries",
    "Implement REST API",
])
```

### 2.4 Workflow Engine

```python
from scripts.collaboration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.create_workflow("Build e-commerce platform")
result = engine.execute(workflow, checkpoint_dir="./checkpoints")
```

---

## 3. Full Lifecycle Development

> **When to use**: Projects spanning multiple phases requiring progress tracking and checkpoint recovery.

### 11-Phase Model

```
P1 Requirements ──→ P2 Architecture ──┬──→ P3 Technical Design ──→ ... ──→ P11 Operations
     [pm]               [arch]         │      [arch+coder]
                                       ├──→ P4 Data Design (optional)
                                       └──→ P5 Interaction Design (optional)
```

| # | Phase | Lead | Gate |
|---|-------|------|------|
| P1 | Requirements Analysis | pm | Acceptance criteria quantifiable |
| P2 | Architecture Design | arch | Consensus passed |
| P3 | Technical Design | arch+coder | API specs unambiguous |
| P4 | Data Design | arch+coder | Data model justified |
| P5 | Interaction Design | ui | Usability verified |
| P6 | Security Review | sec | No P0/P1 vulnerabilities |
| P7 | Test Planning | test | Test plan reviewed |
| P8 | Implementation | coder | Code review passed |
| P9 | Test Execution | test | Coverage≥80% |
| P10 | Deployment & Release | infra | Rollback verified |
| P11 | Operations & Assurance | infra+sec | Alert coverage 100% |

### 5 Predefined Templates

| Template | Phases | Use Case |
|----------|--------|----------|
| `full` | P1-P11 | Complete project |
| `backend` | No P5 | Backend services |
| `frontend` | No P4,P6 | Frontend applications |
| `internal_tool` | No P4,P5,P6,P11 | Internal tools |
| `minimal` | P1,P3,P7,P8,P9 | Minimum set |

### 3.1 Checkpoint Management

```python
from scripts.collaboration.checkpoint_manager import CheckpointManager

cm = CheckpointManager()
cm.save("architecture_complete", {"task_id": "t1", "phase": "architecture"})
state = cm.load("architecture_complete")
```

### 3.2 Task Completion Tracking

```python
from scripts.collaboration.task_completion_checker import TaskCompletionChecker

checker = TaskCompletionChecker()
report = checker.check(task_definition, worker_results)
```

---

## 4. Multi-Role Collaboration

> **When to use**: Multiple roles participating simultaneously with real-time information sharing.

### 4.1 Scratchpad (Shared Workspace)

```python
from scripts.collaboration.scratchpad import Scratchpad

sp = Scratchpad()
sp.write("architect", "decision", "Use microservice architecture")
sp.write_shared("consensus", "final_decision", "Approved: microservice")
sp.write_private("security", "vulnerability_found", "SQL injection in /api/users")
```

| Zone | Purpose | Rules |
|------|---------|-------|
| READONLY | Other agents' output | Read-only |
| WRITE | Your own output | Isolated namespace |
| SHARED | Consensus conclusions | Requires voting |
| PRIVATE | Sensitive data | Invisible to others |

### 4.2 Agent Briefing

Automatically injects preceding agents' output into current Worker's prompt.

### 4.3 Dual-Layer Context

- **Project-level**: Long-term context (tech stack, coding standards)
- **Task-level**: Temporary context (auto-expires after task completion)

---

## 5. Review and Consensus

> **When to use**: Automatic consensus resolution when roles have conflicting opinions.

### 5.1 Weighted Voting

```python
from scripts.collaboration.consensus import ConsensusEngine

engine = ConsensusEngine()
views = {
    "architect": {"decision": "microservice", "confidence": 0.9},
    "security": {"decision": "monolith", "confidence": 0.7},
}
result = engine.resolve(views)
```

**Weights**: architect=3.0, security=2.5, pm=2.0, coder/tester=1.5, devops/ui=1.0

### 5.2 Veto Power

Security and architect roles can veto decisions, triggering automatic escalation.

### 5.3 Five-Axis Consensus Engine

```python
from scripts.collaboration.five_axis_consensus import FiveAxisConsensusEngine

engine = FiveAxisConsensusEngine()
# Axes: Correctness, Security, Performance, Maintainability, Test Coverage
```

---

## 6. Prompt Optimization

### 6.1 Dynamic Prompt Assembly

Auto-selects template variant based on task complexity (SIMPLE/MEDIUM/COMPLEX).

### 6.2 QC Configuration Injection

Prevents hallucination, overconfidence, enforces alternatives and failure scenarios.

```yaml
quality_control:
  ai_quality_control:
    hallucination_check:
      enabled: true
    overconfidence_check:
      enabled: true
```

---

## 7. Inter-Agent Coordination

### 7.1 Coordinator

Manages execution order and context passing between phases.

### 7.2 EnhancedWorker

Provides cache, retry, monitoring, and rule injection capabilities.

### 7.3 Skill Registry

Register and reuse common analysis patterns as skills.

---

## 8. Rule Injection and Security

### 8.1 Natural Language Rule Collection

Supports 4 rule types: `always`, `forbid`, `avoid`, `prefer`.

### 8.2 Input Validation (21+ Patterns)

Detects SQL injection, XSS, command injection, path traversal, etc.

### 8.3 Permission Guard

4 levels: PLAN → DEFAULT → AUTO → BYPASS

---

## 9. Quality Assurance

### 9.1 Confidence Scoring

5-factor response quality assessment (completeness, certainty, specificity, etc.)

### 9.2 Test Quality Guard

Validates test coverage, error case ratio, mock reasonableness.

---

## 10. Performance Monitoring

P95/P99 metrics, bottleneck detection, CPU/memory tracking.

---

## 11. Role Template Market

Publish, share, and discover custom role prompts.

---

## 12. Configuration System

### 12.1 .devsquad.yaml

> 📖 **Full config example**: See [QUICK_START_EN.md](QUICK_START_EN.md#configuration-optional) for basic setup.

### 12.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | None | OpenAI API key |
| `ANTHROPIC_API_KEY` | None | Anthropic API key |
| `DEVSQUAD_LLM_BACKEND` | mock | LLM backend type |
| `DEVSQUAD_LOG_LEVEL` | WARNING | Logging level |

---

## 13. Deployment Methods

### 13.1 CLI / Python API / MCP / Docker

> 📖 **Quick start commands**: See [QUICK_START_EN.md](QUICK_START_EN.md#first-dispatch-3-lines-of-code)

### 13.2 Kubernetes (Helm)

```bash
helm install devsquad ./helm/devsquad
kubectl port-forward svc/devsquad-api 8000:8000
```

> 📖 **Full Helm documentation**: [helm/devsquad/README.md](../../helm/devsquad/README.md)

---

## 14. Agent Skills Quality Framework

### 14.1 Anti-Rationalization Engine

Blocks common excuses like "This is a small change" or "AI code is probably fine".

### 14.2 Verification Gate

Mandatory evidence requirements before accepting work as "done".

### 14.3 Intent→Workflow Mapper

Maps natural language intent to structured workflow chains (6 intents × 3 languages).

### 14.4 CLI Lifecycle Commands

| Command | Description |
|---------|-------------|
| `spec` | Generate specification |
| `plan` | Decompose into tasks |
| `build` | Implement with TDD |
| `test` | Run tests with evidence |
| `review` | Five-axis code review |
| `ship` | Pre-launch + deploy |

---

## 15. FAQ

**Q: Can I use DevSquad without an API Key?**
Yes. Mock mode works without any API Key.

**Q: Does missing CarryMem affect DevSquad?**
No. Graceful degradation via NullProvider.

**Q: How do I choose roles?**
Simple tasks: 1-2 roles, complex tasks: 3-5 roles, full workflow: all 7 roles.

**Q: How do I switch output language?**
CLI: `--lang en`, Python: `MultiAgentDispatcher(lang="en")`

**Q: How do I customize role prompts?**
Via Role Template Market or modify `ROLE_TEMPLATES`.

---

## Appendix A: CarryMem Integration

Optional cross-session memory system for rule injection.

```bash
pip install carrymem[devsquad]>=0.2.8
```

---

## Appendix B: Complete Module List

| # | Module | Purpose |
|---|--------|---------|
| 1 | MultiAgentDispatcher | Unified entry point |
| 2 | Coordinator | Global orchestration |
| 3 | Scratchpad | Shared workspace protocol |
| 4 | Worker | Role executor |
| 5 | ConsensusEngine | Weighted voting + veto |
| 6 | BatchScheduler | Batch scheduling |
| 7 | ContextCompressor | Context compression |
| 8 | PermissionGuard | Permission control |
| 9 | Skillifier | Skill learning |
| 10 | WarmupManager | Startup optimization |
| 11 | MemoryBridge | Cross-session memory |
| 12 | TestQualityGuard | Test quality guard |
| 13 | PromptAssembler | Prompt assembly + QC |
| 14 | MCEAdapter | CarryMem integration |
| 15 | RoleMatcher | Keyword matching |
| 16 | ReportFormatter | Report generation |
| 17 | InputValidator | Input validation |
| 18 | AISemanticMatcher | Semantic matching |
| 19 | CheckpointManager | State persistence |
| 20 | WorkflowEngine | Workflow + lifecycle |
| 21 | TaskCompletionChecker | Completion tracking |
| 22 | CodeMapGenerator | Code analysis |
| 23 | DualLayerContextManager | Dual-layer context |
| 24 | SkillRegistry | Skill registry |
| 25 | IntentWorkflowMapper | Intent mapping |
| 26 | OperationClassifier | Operation classification |
| 27 | FiveAxisConsensusEngine | Five-axis consensus |
| 28 | LLMBackend | LLM backends |
| 29 | LLMCache | Response caching |
| 30 | LLMRetry | Retry logic |
| 31 | ConfigManager | Configuration |
| 32 | Protocols | Interface definitions |
| 33 | NullProviders | Null implementations |
| 34 | EnhancedWorker | Enhanced worker |
| 35 | PerformanceMonitor | Performance monitoring |
| 36 | AgentBriefing | Context briefing |
| 37 | ConfidenceScorer | Confidence scoring |
| 38 | RoleTemplateMarket | Template market |
| 39 | UsageTracker | Token/cost tracking |
| 40 | Models | Data models |
| 41-47 | Async modules | Async variants |

---

*DevSquad V3.6.0 — Complete Reference Guide*
