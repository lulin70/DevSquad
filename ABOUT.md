# About DevSquad

## What is DevSquad?

**DevSquad** is an open-source **Multi-Agent Software Development Team** platform that transforms a single AI coding assistant into a specialized development squad.

Instead of one AI handling your entire task, DevSquad automatically dispatches to the right combination of expert roles — architect, product manager, coder, tester, security reviewer, and more — then orchestrates their parallel collaboration through a shared workspace, resolves conflicts via consensus voting, and delivers a unified, structured report.

Think of it as **assembling a virtual dev team on demand**, powered by AI agents that collaborate like real engineers.

## The Problem It Solves

| Single AI Assistant | DevSquad |
|---------------------|----------|
| One perspective on every problem | 10 specialized roles, each with domain expertise |
| Linear, sequential thinking | Parallel agent execution with real-time sharing |
| No conflict resolution | Weighted consensus with veto power |
| No memory across sessions | Cross-session memory bridge (7 types) |
| Generic output | Structured reports with action items (H/M/L priority) |

## How It Works

```
You: "Design a microservices e-commerce backend"
         │
         ▼
┌─────────────────┐
│  Intent Analysis │ ──→ Auto-match roles: architect + devops + security
└────────┬────────┘
         ▼
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│   Architect      │     │  DevOps       │     │  Security    │
│  (System Design) │     │ (Infra Plan)  │     │(Threat Model)│
└────────┬─────────┘     └──────┬───────┘     └──────┬───────┘
         │                      │                     │
         └──────────────────────┼─────────────────────┘
                                ▼
                    ┌───────────────────┐
                    │    Scratchpad      │ ◄── Shared blackboard
                    │ (Real-time sync)   │     Discoveries / Conflicts
                    └─────────┬─────────┘
                              ▼
                    ┌───────────────────┐
                    │ Consensus Engine   │ ◄── Weighted vote + veto
                    └─────────┬─────────┘
                              ▼
                    ┌───────────────────┐
                    │  Structured Report │     Findings + Action Items
                    │  (Markdown/JSON)   │     H/M/L priority + timing
                    └───────────────────┘
```

## Key Capabilities

### 10 Built-in Roles

Each role carries a specialized prompt template, domain expertise, and output format:

- **Architect** — System design, tech stack decisions, API design patterns
- **Product Manager** — Requirements analysis, user stories, acceptance criteria
- **Coder** — Implementation, code generation, refactoring strategies
- **Tester** — Test strategy, edge case identification, coverage gaps
- **UI Designer** — UX flow, interaction logic, accessibility review
- **DevOps** — CI/CD pipeline, deployment architecture, monitoring
- **Security** — Threat modeling, vulnerability assessment, OWASP alignment
- **Data Engineer** — Data modeling, schema design, migration planning
- **Code Reviewer** — Best practices, anti-patterns, maintainability audit
- **Performance Optimizer** — Caching, query optimization, profiling

### 16 Core Modules

| Module | Purpose |
|--------|---------|
| MultiAgentDispatcher | Unified entry point — one call does everything |
| Coordinator | Global orchestration: decompose → assign → collect → resolve |
| Scratchpad | Shared blackboard for inter-worker real-time communication |
| Worker | Role executor — independent instance per role |
| ConsensusEngine | Weighted voting + veto power + human escalation |
| BatchScheduler | Parallel/sequential hybrid with auto safety detection |
| ContextCompressor | 4-level compression prevents context overflow |
| PermissionGuard | 4-level safety gate (PLAN → DEFAULT → AUTO → BYPASS) |
| Skillifier | Learns from successful patterns, auto-generates new skills |
| WarmupManager | 3-layer startup preloading (cold-start < 300ms) |
| MemoryBridge | 7-type cross-session memory + TF-IDF + forgetting curve |
| MCEAdapter | Memory Classification Engine integration (v0.4, tenant-aware) |
| WorkBuddyClawSource | External knowledge bridge (INDEX search, AI news feed) |
| PromptAssembler | Dynamic prompt construction (3 variants × 5 styles) |
| PromptVariantGenerator | Closed-loop A/B testing for prompt optimization |
| TestQualityGuard | Automated test quality audit (API validation, coverage) |

## Tech Stack & Compatibility

```
Language:    Python 3.9+ (pure Python, no compiled dependencies)
Testing:     pytest (~828 tests, 100% pass rate)
Platform:    macOS / Linux / Windows (CI tested)
AI Backend:  Any LLM provider (works as a pure orchestration layer)
External:    MCE v0.4 (optional), WorkBuddy Claw (optional, graceful degrade)
```

**Cross-platform ready**: Works natively in Trae IDE, Claude Code (via CLAUDE.md), OpenClaw (via MCP server), or any Python environment.

## Project Stats

| Metric | Value |
|--------|-------|
| Version | V3.3 (2026-04-17) |
| Core Modules | 16 |
| Agent Roles | 10 |
| Test Cases | ~828 (all passing) |
| Lines of Code | ~8,000 (core collaboration layer) |
| Languages | EN / CN / JP (trilingual docs) |
| License | MIT |

## Origin Story

DevSquad evolved from **TraeMultiAgentSkill**, a Trae IDE-native skill project that started in March 2026. Over 5 weeks of rapid iteration, it grew from a simple multi-role code walkthrough tool into a full-fledged multi-agent collaboration platform with:

- **V1–V2** (Mar 2026): Dual-layer context management, Vibe Coding, MCE integration
- **V3.0** (Apr 16): Complete redesign — Coordinator/Worker/Scratchpad architecture, 11 modules, 710 tests
- **V3.1** (Apr 16): Prompt optimization system with A/B variant testing
- **V3.2** (Apr 17): E2E demo, MCE adapter, dispatcher UX enhancement
- **V3.3** (Apr 17): WorkBuddy Claw integration, cross-platform compatibility (ClaudeCode/OpenClaw), rebrand to DevSquad

## Philosophy

> **"One AI is a tool. Ten AI collaborators are a team."**

DevSquad is built on the belief that software development is inherently multi-disciplinary. No single perspective — not even the smartest AI's — can match the quality of a well-coordinated team with diverse expertise. DevSquad makes that team available on demand, in seconds, for any software task.

## Roadmap (What's Next)

- [ ] **MCP Server GA** — Production-ready MCP protocol support for all IDEs
- [ ] **Persistent Team Memory** — Long-term learning across projects
- [ ] **Custom Role Definition** — Users define their own specialist roles
- [ ] **Distributed Execution** — Workers running on separate LLM instances
- [ ] **Web Dashboard** — Real-time visualization of squad collaboration

---

*DevSquad is open source under the MIT License. Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).*
