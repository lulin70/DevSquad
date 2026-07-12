# DevSquad V4.x Architecture

> **Version**: V4.1.0
> **Last Updated**: 2026-07-12
> **Status**: Active (supersedes V3.8/V3.9 architecture docs)

---

## 1. Component Overview

DevSquad is a multi-role AI task orchestrator that transforms a single AI assistant into a 7-person professional team.

### 7-Role System

| Role | Responsibility | Module |
|------|---------------|--------|
| **Architect** | System design, technical decisions | `scripts/collaboration/roles/` |
| **PM** | Requirements analysis, user stories | `scripts/collaboration/roles/` |
| **Security** | Threat modeling, vulnerability assessment | `scripts/collaboration/roles/` |
| **Tester** | Test strategy, coverage analysis | `scripts/collaboration/roles/` |
| **Coder** | Implementation, code review | `scripts/collaboration/roles/` |
| **DevOps** | Deployment, CI/CD, monitoring | `scripts/collaboration/roles/` |
| **UI** | Interface design, UX evaluation | `scripts/collaboration/roles/` |

### Dispatch Core

| Component | File | Purpose |
|-----------|------|---------|
| `MultiAgentDispatcher` | `scripts/collaboration/dispatcher.py:49` | Entry point — decomposes task, orchestrates pipeline |
| `Coordinator` | `scripts/collaboration/coordinator.py:55` | Matches roles to task, coordinates parallel execution |
| `Worker` | `scripts/collaboration/worker.py:29` | Executes a single role's analysis |
| `WorkerFactory` | `scripts/collaboration/worker.py:601` | Creates workers based on role requirements |
| `WorkerPool` | `scripts/collaboration/worker.py:670` | Manages parallel worker execution |
| `ConsensusEngine` | `scripts/collaboration/consensus.py:26` | Aggregates worker outputs into consensus decision |

### Support Modules

| Category | Modules |
|----------|---------|
| **Context** | `ContextCompressor`, `DualLayerContextManager`, `Scratchpad` |
| **Security** | `PermissionGuard`, `InputValidator`, `AuthManager`, `OperationClassifier` |
| **Performance** | `PerformanceMonitor`, `WarmupManager`, `LLMCache`, `LLMRetry` |
| **Lifecycle** | `LifecycleProtocol`, `UnifiedGateEngine`, `WorkflowEngine` |
| **Control** | `FeedbackControlLoop`, `ExecutionGuard`, `AdaptiveRoleSelector` |
| **Integration** | API Server (FastAPI), Dashboard (Streamlit), `HistoryManager` |

---

## 2. Data Flow

```
User Task
    │
    ▼
┌──────────────────┐
│  InputValidator   │  Sanitize input, detect prompt injection
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  RoleMatcher     │  Select 1-7 roles based on task type
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Coordinator     │  Create Worker instances, prepare Scratchpad
└────────┬─────────┘
         │
    ┌────┼────┬────────┐ (parallel)
    ▼    ▼    ▼        ▼
┌──────┐┌──────┐┌──────┐┌──────┐
│Worker││Worker││Worker││Worker│  Each role executes independently
│  (A) ││  (P) ││  (S) ││  (T) │  Results written to shared Scratchpad
└──┬───┘└──┬───┘└──┬───┘└──┬───┘
   │       │       │       │
   └───────┴───┬───┴───────┘
               │
               ▼
    ┌──────────────────┐
    │ ConsensusEngine   │  Aggregate, resolve conflicts, build consensus
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │   Report         │  Structured output with findings, decisions
    └──────────────────┘
```

**Key principle**: Workers execute in **parallel** (`asyncio.gather`), not serial pipeline. The three-sage system (ConsensusEngine) uses **parallel voting**, not sequential review.

---

## 3. Protocol System

DevSquad uses `typing.Protocol` (structural subtyping) to define provider contracts. All protocols are in `scripts/collaboration/protocols.py` and decorated with `@runtime_checkable` (v4.0.8+) for `isinstance` validation.

### 6 Protocols

| Protocol | File Line | Purpose | Real Implementation | Null Implementation |
|----------|-----------|---------|---------------------|---------------------|
| `CacheProvider` | L57 | LLM response caching | `LLMCache` (filesystem) | `NullCacheProvider` |
| `RetryProvider` | L100 | Retry with fallback | `LLMRetry` | `NullRetryProvider` |
| `MonitorProvider` | L136 | Performance monitoring | `PerformanceMonitor` | `NullMonitorProvider` |
| `MemoryProvider` | L188 | User rules/memory | `MemoryManager` | `NullMemoryProvider` |
| `UETestProvider` | L260 | UE test framework | `UETestFramework` | (gap: no NullUETestProvider) |
| `TechDebtProvider` | L286 | Tech debt tracking | `TechDebtManager` | (gap: no NullTechDebtProvider) |

### Null Providers

Null providers (`scripts/collaboration/null_providers.py`) provide no-op implementations for graceful degradation:

- All methods succeed silently (no side effects)
- `is_available()` returns `False`
- Used when real provider is unavailable or in test mode

### Contract Tests

Contract tests (`tests/contract/`) verify that all implementations conform to their Protocol:

- Protocol definition validation (methods exist with correct signatures)
- Structural subtyping verification (`isinstance` with `@runtime_checkable`)
- Null provider contract compliance
- Real implementation round-trip behavior

**Test files**: `test_cache_provider_contract.py`, `test_retry_provider_contract.py`, `test_ue_test_provider_contract.py`, `test_tech_debt_provider_contract.py`

---

## 4. API Layer

### FastAPI Application

**Entry point**: `scripts/api_server.py`

### Middleware Chain

Requests pass through middleware in this order:

```
Request → CORS → HTTPS Redirect → Rate Limit → Timing → Endpoint Handler
```

| Middleware | File | Purpose |
|-----------|------|---------|
| CORS | `api_server.py` L134 | Cross-origin requests (no wildcard with credentials) |
| HTTPS Redirect | `scripts/api/rate_limit.py` | 308 redirect when `X-Forwarded-Proto: http` |
| Rate Limit | `scripts/api/rate_limit.py` | 60 req/min per IP (configurable) |
| Timing | `api_server.py` L144 | `X-Process-Time` response header |

### Route Modules

| Router | File | Endpoints |
|--------|------|-----------|
| Lifecycle | `scripts/api/routes/lifecycle.py` | `/api/v1/lifecycle/*` |
| Metrics & Gates | `scripts/api/routes/metrics_gates.py` | `/api/v1/metrics/*`, `/api/v1/gates/*`, `/api/v1/health` |
| Dispatch | `scripts/api/routes/dispatch.py` | `/api/v1/tasks/*` |
| Prometheus | `scripts/api/routes/metrics.py` | `/metrics` |

### Health Endpoints (v4.1.0)

| Endpoint | Type | Purpose |
|----------|------|---------|
| `/api/v1/health` | Liveness | Component status (lifecycle, database) |
| `/api/v1/ready` | Readiness | Traffic readiness (503 during startup/shutdown) |
| `/metrics` | Prometheus | Metrics scraping |

---

## 5. Security Layer

### Authentication

**Module**: `scripts/auth.py` → `AuthManager`

- Password hashing: PBKDF2-HMAC-SHA256 with per-user salt
- Legacy SHA-256 hashes auto-migrated on login
- Credentials stored in `config/deployment.yaml`

### Authorization (RBAC)

**Module**: `scripts/api/security.py`

- Role-based access control (admin, viewer)
- Permission model: `TASK_EXECUTE`, `TASK_READ`, `TASK_UPDATE`, `AUDIT_READ`
- Production mode (`DEVSQUAD_ENV=production`): auth cannot be disabled

### Security Middleware

| Component | Purpose |
|-----------|---------|
| `PermissionGuard` | 4-level permission checks |
| `InputValidator` | 16-pattern prompt injection detection |
| `AuditLogger` | Operation audit trail |
| `OperationClassifier` | Classifies operations by risk level |

### API Key Authentication

- `X-API-Key` header required when auth enabled
- Dev mode: `DEVSQUAD_API_AUTH_DISABLED=1` bypasses auth
- Production mode: auth is mandatory (cannot be disabled)

---

## 6. Lifecycle Management

### 11-Phase Lifecycle

**Module**: `scripts/collaboration/lifecycle_protocol.py`

| Phase | ID | Purpose |
|-------|-----|---------|
| Requirements | P1 | Task analysis and decomposition |
| Design | P2 | Architecture and technical design |
| Implementation | P3 | Code writing |
| Testing | P4 | Test execution and validation |
| Review | P5 | Code review and quality checks |
| Integration | P6 | Component integration |
| Deployment | P7 | Production deployment |
| Monitoring | P8 | Runtime monitoring |
| Feedback | P9 | User feedback collection |
| Optimization | P10 | Performance tuning |
| Retirement | P11 | End-of-life |

### Gate Engine

**Module**: `scripts/collaboration/unified_gate_engine.py`

Quality gates enforce criteria before phase transitions:
- Test coverage thresholds
- Lint/type check passes
- Security scan results
- Performance benchmarks

---

## 7. v4.x Key Changes (vs V3.x)

### V4.0.0 — Major Release
- 7-role system with parallel worker execution
- ConsensusEngine as core decision mechanism (parallel voting, not serial)
- Protocol-based provider architecture
- Contract test framework

### V4.0.7 — Moka AI Backend
- `MOKA_API_KEY` support via OpenAI-compatible API
- `benchmark_real_llm.py --backend moka` option
- Moka LLM smoke tests (3 tests)

### V4.0.8 — Contract Test Completion
- `@runtime_checkable` on all 6 Protocols
- 28 new contract tests (163 total)
- Async exception dead code fix (`async_coordinator.py`)

### V4.1.0 — Operations & Readiness
- `/api/v1/ready` readiness probe (separated from `/health` liveness)
- `_app_ready` lifecycle flag (startup=True, shutdown=False)
- Traffic draining during graceful shutdown
- Operations manual (`docs/operations/OPERATIONS.md`)
- This architecture document

---

## 8. Testing Architecture

### Test Categories

| Category | Location | Count | Purpose |
|----------|----------|-------|---------|
| Unit/Integration | `tests/` | 3600+ | Core functionality |
| Contract | `tests/contract/` | 163 | Protocol compliance |
| E2E | `tests/e2e/` | 48+ | User journey |
| UI E2E | `tests/` (streamlit-app-testing) | 37+ | Dashboard |
| Performance | `tests/` (benchmark) | 23+ | Baseline metrics |
| Real LLM Smoke | `tests/` | 3+ | Moka/OpenAI integration |

### Test Philosophy

- **No Mock anti-patterns**: Use real components (e.g., real `pygame.Surface`) when API requires底层 objects
- **No skip tests**: If a test can be skipped, it shouldn't exist
- **xfail strict**: No `strict=False` (hides XPASS)
- **TestQualityGuard**: Automated audit for test quality violations

---

## 9. Module Dependencies

```
scripts/
├── api_server.py              # FastAPI app, middleware, /ready endpoint
├── auth.py                    # AuthManager (PBKDF2)
├── cli.py                     # Command-line interface
├── api/
│   ├── rate_limit.py          # Rate limit + HTTPS redirect middleware
│   ├── security.py            # RBAC, AuditLogger, PermissionGuard
│   └── routes/
│       ├── dispatch.py        # Task dispatch endpoints
│       ├── lifecycle.py       # Lifecycle management
│       └── metrics_gates.py   # Metrics, gates, /health
└── collaboration/
    ├── dispatcher.py          # MultiAgentDispatcher
    ├── coordinator.py         # Coordinator
    ├── worker.py              # Worker, WorkerFactory, WorkerPool
    ├── consensus.py           # ConsensusEngine
    ├── protocols.py           # 6 Protocol definitions
    ├── null_providers.py      # Null provider implementations
    ├── async_coordinator.py   # Async task execution
    └── _version.py            # Version string
```
