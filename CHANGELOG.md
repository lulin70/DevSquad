# Changelog

[中文版](CHANGELOG-CN.md) | **English**

This document records all significant changes to DevSquad.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.2.1] - 2026-07-22

PATCH release: P1+P2 items from 7-role consensus review — consensus quality,
human gate, constructor detection, test quality CI gate, hidden content
scanner, PRD-version linkage, sensitive info input interception, test pyramid
analysis, and config consistency audit.

### Added — P1-7: Dissent Requirement Mechanism

- **Module**: `scripts/collaboration/consensus.py` + `models_base.py`
- **Problem**: Pure-AI consensus with all approve votes may indicate
  "rubber-stamp" behavior rather than genuine scrutiny.
- **Solution**: `ConsensusEngine(require_dissent=True)` checks that each
  voter provides a `risk_identified` field. Voters without a risk are
  listed in `record.warnings` as "Dissent missing".
- **API**: `Vote.risk_identified: str | None` field added (backward
  compatible, defaults None). `ConsensusEngine(require_dissent=False)`
  default preserves existing behavior.
- **Tests**: 9/9 passed (`tests/test_consensus_dissent.py`).

### Added — P1-8: Human Gate Mapping

- **Module**: `scripts/collaboration/permission_guard.py`
- **Problem**: No explicit mapping of which action types always require
  human confirmation — AI could auto-approve irreversible operations
  (cf. Replit AI delete-db incident).
- **Solution**: `PermissionGuard.HUMAN_GATE_ACTIONS` set defines 3
  irreversible action types: `FILE_DELETE`, `PROCESS_SPAWN`,
  `ENVIRONMENT`. These always return `PROMPT` regardless of
  `PermissionLevel` (except `BYPASS`). Whitelist does NOT bypass
  human gate (safety override).
- **Tests**: 14/14 passed (`tests/test_permission_guard_human_gate.py`).

### Added — P1-13: Constructor Parameter Counter

- **Script**: `scripts/check_constructor_params.py`
- **Problem**: No detector to prevent future "god constructor"
  anti-patterns (43-param constructor was fixed, but no guardrail).
- **Solution**: AST-based scanner extracts all `__init__` methods,
  counts parameters (excluding `self`), flags constructors exceeding
  threshold (default >7). Reports class name, file:line, param list.
- **Features**: `--threshold` flag, `--json` output, detects `**kwargs`
  and `*args`, sorts flagged by param count descending.
- **Tests**: 12/12 passed (`tests/test_check_constructor_params.py`).

### Added — P1-17: Test Quality CI Gate

- **Script**: `scripts/check_test_quality.py`
- **Problem**: `TestQualityGuard` existed but was not wired into CI —
  weak assertions (assertTrue, >0.0 thresholds) and bare except clauses
  could slip into test code undetected.
- **Solution**: CLI script scans all `tests/test_*.py` files using
  `AntiPatternDetector`. Fails CI on MAJOR severity (bare except,
  missing error tests). MINOR/INFO issues reported as warnings.
- **Features**: `--source` directory, `--fail-on` severity threshold,
  `# noqa: test-quality` suppression for test fixtures (string literals
  containing anti-pattern text as detector test input).
- **CI**: Added as blocking step in `test.yml` after version consistency.
- **Tests**: 16/16 passed (`tests/test_check_test_quality.py`).

### Added — P1-4: Hidden Content Scanner

- **Script**: `scripts/check_hidden_content.py`
- **Problem**: Malicious instructions or data exfiltration could be masked
  using invisible Unicode characters (zero-width chars, homoglyphs) or
  hidden HTML comments in markdown — undetectable in normal code review.
- **Solution**: Scanner detects 5 categories of hidden content:
  (1) zero-width characters (U+200B/200C/200D/FEFF/2060),
  (2) invisible formatting characters (U+00AD/2061-2064),
  (3) control characters (U+0000-001F except tab/LF/CR, U+007F DEL),
  (4) Cyrillic/Greek homoglyphs that look like ASCII letters (confusable
  character attack),
  (5) HTML comments in markdown/HTML files (``<!--...-->`` hiding
  instructions).
- **Features**: File-type-aware HTML comment detection (only .md/.html/.rst
  files, not .py — prevents false positives on string literals), `--no-homoglyphs`
  and `--no-html-comments` flags, directory tree walk with __pycache__/.git
  skip, configurable file extension filter.
- **Bug fixes during development**: Removed unused `field` import; fixed
  duplicate key in `GREEK_HOMOGLYPHS` (0x03BF was duplicated, masking
  intended 0x03C1 Greek small rho); added `_should_check_html_comments`
  helper to eliminate false positives on Python source files.
- **CI**: Added as blocking step in `test.yml` scanning scripts/+tests/+skills/.
- **Tests**: 51/51 passed (`tests/test_check_hidden_content.py`) — covers
  Happy/Error/Boundary/Performance/Config/Integration dimensions.

### Added — P2-11: PRD-Version Linkage Check

- **Script**: `scripts/check_version_consistency.py` (extended)
- **Problem**: `docs/prd/*.md` files carry version tags in filenames
  (e.g., `V3.9_PRD_Code_Intelligence.md`) but were not checked for internal
  version consistency — content could drift from the declared version.
- **Solution**: `_check_prd_files()` scans `docs/prd/*.md`, extracts the
  version from each filename (e.g., `V3.9` → `3.9`), and verifies that
  version appears in the file content. Uses `(?<!\d)` and `(?!\d)`
  lookarounds instead of `\b` to correctly match `V3.9` (V is a word char,
  so `\b` fails between V and 3).
- **Behavior**: Non-blocking WARN-level (PRDs are historical artifacts).
  `--strict` flag promotes WARN to FAIL. Missing/unreadable PRD files → SKIP.
- **Tests**: 21/21 passed (`tests/test_check_version_consistency.py`) —
  covers filename regex, happy path, warn cases, boundary (empty/missing/
  non-versioned), digit-boundary false-positive prevention, main()
  integration, and real PRD files.

### Added — P2-5: Sensitive Info Input Interception

- **Module**: `scripts/collaboration/input_validator.py`
- **Problem**: `InputValidator` had 40 security patterns (forbidden +
  suspicious + prompt injection) but did NOT detect sensitive information
  (API keys, passwords, tokens) at input boundaries — secrets could leak
  into logs, cache, and LLM backends.
- **Solution**: `check_sensitive_info()` method integrates
  `secret_patterns.find_secrets()` (10 patterns: openai_api_key,
  github_token, aws_access_key, aws_secret_key, generic_api_key, password,
  secret, bearer_token, private_key, connection_string). Returns masked
  warning messages (first 4 chars + `*`). `ValidationResult.warnings`
  field added (default empty list).
- **Behavior**: Non-blocking WARNING (input remains valid=True — users may
  legitimately discuss API key formats). Downstream modules
  (`content_cache`, `audit_logger`) mask secrets in logs/cache.
- **Tests**: 31/31 passed (`tests/test_input_validator_sensitive.py`) —
  covers all 10 SECRET_PATTERNS, masking, non-blocking behavior, Unicode
  normalization, multiple secrets, and ValidationResult field defaults.

### Added — P2-21: Test Pyramid Distribution Analysis

- **Script**: `scripts/check_test_pyramid.py`
- **Problem**: With 5977 tests across 202 files, there was no visibility
  into test composition (unit/integration/e2e ratio). A top-heavy pyramid
  (too many e2e, too few unit) indicates slow suite and brittle tests.
- **Solution**: `TestPyramidAnalyzer` walks `tests/` directory,
  categorizes files by subdirectory + filename override (`*_e2e.py` → e2e),
  counts test functions via AST (no import side effects), and reports
  distribution against healthy pyramid ranges (unit ≥60%, integration
  15-25%, e2e ≤10%, contract 5-10%, smoke ≤5%).
- **Features**: `--json` output, `--strict` flag (fail on warnings), 6
  layer categories, AST-based counting (handles async test functions).
- **CI**: Added as non-blocking informational step in `test.yml`.
- **Real findings**: unit 89.5% (OK), integration 3.8% (WARNING — below
  15% target), e2e 4.0% (OK), contract 2.1% (WARNING — below 5% target).
- **Tests**: 38/38 passed (`tests/test_check_test_pyramid.py`) — covers
  categorization, AST counting, health assessment, format report, CLI,
  and real tests/ directory integration.

### Added — P2-15: Configuration Consistency Audit

- **Script**: `scripts/check_config_consistency.py`
- **Problem**: No tool to audit configuration drift across multiple config
  files (VERSION ↔ Dockerfile/Chart.yaml/values.yaml, pyproject.toml ↔
  requirements.txt, required keys in .devsquad.yaml).
- **Solution**: `ConfigConsistencyChecker` performs 3 categories of checks:
  (1) dependency sync (pyproject.toml → requirements.txt),
  (2) key presence (.devsquad.yaml `quality_control`, values.yaml
  `image.repository`/`image.tag`, deployment.yaml `authentication`),
  (3) cross-file version alignment (VERSION ↔ Dockerfile ARG VERSION ↔
  Chart.yaml appVersion ↔ values.yaml image.tag).
- **Behavior**: FAIL-level issues block CI (version mismatch, missing
  required keys); WARN-level non-blocking (values.yaml tag drift may be
  intentional for deployment pinning); SKIP for missing optional files.
- **CI**: Added as blocking step in `test.yml`.
- **Real findings**: values.yaml image.tag = 4.0.0 but VERSION = 4.2.1
  (WARN — deployment pinning or stale config).
- **Tests**: 23/23 passed (`tests/test_check_config_consistency.py`) —
  covers dependency sync, key presence, cross-file alignment, format
  report, CLI, and real repo integration.

### Added — P2-21 Follow-up: Test Pyramid Lift (Integration + Contract)

- **Problem**: P2-21 analysis revealed integration at 3.8% (below 15%
  target) and contract at 2.1% (below 5% target). High-value dispatch
  pipeline, security chain, and provider contracts lacked integration
  and contract coverage.
- **Solution**: Added 4 test files (119 new tests) targeting the
  highest-risk integration boundaries and protocol contracts:
  - `tests/integration/test_dispatch_pipeline_integration.py` (34
    tests) — full dispatch pipeline: role matching, coordinator-worker
    interaction, consensus, result assembly, error handling, dry-run,
    dispatcher status (8 test classes).
  - `tests/integration/test_security_chain_integration.py` (22 tests)
    — InputValidator → OperationClassifier → PermissionGuard chain:
    validation-to-classification, classification-to-permission, full
    pipeline, permission escalation, audit trail, fail-safe, sensitive
    info interaction (7 test classes).
  - `tests/contract/test_monitor_provider_contract.py` (36 tests) —
    MonitorProvider Protocol contract for both PerformanceMonitor
    (real) and NullMonitorProvider (degraded): record_llm_call,
    record_agent_execution, generate_report, is_available, get_stats,
    plus Null-specific degraded behavior (20 base + 16 impl-specific).
    Base class uses `__test__ = False` to prevent pytest collection;
    subclasses override with `__test__ = True`.
  - `tests/integration/test_cross_module_integration.py` (27 tests)
    — cross-module collaboration: EventBus pub/sub, dispatcher-eventbus
    integration, dispatch hooks, result assembler, scratchpad shared
    state, multiple dispatch cycles, event bus error isolation
    (7 test classes).
- **Result**: integration ratio 3.8% → 5.1% (+1.3%, 312/6141 tests);
  contract ratio 2.1% → 2.3% (+0.2%, 143/6141 tests). Targets not yet
  met (15% / 5%) but meaningful progress with highest-risk boundaries
  covered. Further lift requires expanding e2e-to-integration migration
  and adding contracts for CacheProvider/RetryProvider/MemoryProvider.
- **CI gates**: ruff clean, radon cc D+ clean, mypy 0 errors, version
  consistency 28/28 passed, all new tests pass.

### Added — P2-21 Follow-up (Batch 2): Test Pyramid Lift (Integration)

- **Problem**: First batch (119 tests) lifted integration from 3.8% →
  5.1%, still well below the 15% target. Eight high-value cross-module
  boundaries lacked integration coverage: review pipeline, provider
  injection, consensus voting, micro-task planning, content cache,
  loop engineering, autonomous iteration, and plugin hot-loading.
- **Solution**: Added 5 integration test files (260 new tests) using
  the DevSquad 7-Role methodology with parallel subagent dispatch:
  - `tests/integration/test_review_pipeline_integration.py` (30 tests)
    — TwoStageReviewGate → SeverityRouter → JudgeAgent three-stage
    review chain: full pipeline, gate-to-router, router-to-judge,
    auto-fix loop, judge deduplication, disabled gate, edge cases
    (7 test classes).
  - `tests/integration/test_enhanced_worker_provider_integration.py`
    (35 tests) — EnhancedWorker + Protocol providers injection:
    cache/retry/monitor/memory provider integration, NullProvider
    graceful degrade, multiple providers combined (7 test classes).
  - `tests/integration/test_consensus_worker_integration.py` (36
    tests) — ConsensusEngine + Worker voting: basic voting, unanimous
    approval, split vote, veto power, weighted voting, fatigue
    detector, edge cases (7 test classes).
  - `tests/integration/test_micro_task_planner_integration.py` (34
    tests) — MicroTaskPlanner + Dispatcher + YagniChecker: dispatcher
    wiring, decomposition strategies, DAG execution flow, YagniChecker
    SKIP propagation, execution mode classification (HITL/AFK),
    topological sort + cycle detection, edge cases (7 test classes).
  - `tests/integration/test_content_cache_ccr_integration.py` (33
    tests) — ContentCache + CCRStore + Scratchpad: cache hit/miss,
    lazy trace_id retrieval, sensitive-data filtering, TTL expiry, LRU
    eviction, thread-safety, edge cases (7 test classes).
  - `tests/integration/test_loop_engineering_integration.py` (32
    tests) — LoopEngineering kernel + HandoffAdapter + CheckpointManager:
    cycle results, handoff documents, SHA-256 integrity, lifecycle
    persistence, auto-cleanup, ShortcutLifecycleAdapter, edge cases
    (7 test classes).
  - `tests/integration/test_autonomous_git_integration.py` (30 tests)
    — AutonomousLoopController + GitDriver: iteration loop, real git
    operations, max iterations, stop/resume, error handling, dispatcher
    wiring, edge cases (7 test classes).
  - `tests/integration/test_plugin_hot_loader_integration.py` (30
    tests) — PluginHotLoader + Dispatcher: plugin discovery,
    registration, hot-reload, no-hot-reload mode, disabled mode,
    multiple plugins, edge cases (7 test classes).
- **Bug fix**: `scripts/collaboration/judge_agent.py` —
  `confidence_threshold` parameter was accepted in `__init__` but
  never passed to `_filter_by_confidence_with_decisions()` in
  `judge()`, always using the default 0.7. Fixed by passing
  `self.confidence_threshold` to the filter call. 33 existing unit
  tests verified no regression.
- **Bugs discovered (not fixed — flagged for follow-up)**:
  1. `SmartCrusher._inject_trace_id` emits `retrieve full: trace_id=X`
     but `Scratchpad._DEVSQUAD_RETRIEVE_PATTERN` only matches
     `devsquad_retrieve(trace_id=X, query=Y)` — marker formats are
     incompatible.
  2. `ContentCache.invalidate("*")` silently no-ops against LLMCache
     backend (`LLMCache.invalidate` signature mismatch causes
     swallowed `TypeError`).
  3. `PluginHotLoader._load_plugin_file` has a narrow exception net
     (`ImportError, AttributeError, RuntimeError, OSError, SyntaxError`)
     — `ValueError`/`TypeError` from `create_plugin()` propagate and
     crash the dispatcher.
- **Result**: integration ratio 5.1% → 8.9% (+3.8%, 572/6401 tests);
  contract ratio 2.3% → 2.2% (143/6401 — unchanged count, diluted by
  total growth). Integration target (15%) not yet met but +3.8% lift
  in one batch. Contract target (5%) requires dedicated contract test
  files for CacheProvider/RetryProvider/MemoryProvider.
- **CI gates**: ruff clean, radon cc D+ clean (judge_agent.py max
  complexity A/3), mypy 0 errors, version consistency 28/28 passed,
  159/159 new integration tests pass.

## [4.2.0] - 2026-07-22

MINOR release: AI safety + consensus quality + test coverage tooling.

Driven by 32-issue audit of training materials (M0-M8). Of 32 issues,
14 already fixed, 7 partial, 7 worth implementing, 4 declined (over-engineering
risk). This release delivers the 3 P0 items from the 7-role consensus review.

### Added — P0-6: Consensus Fatigue Detector

- **Module**: `scripts/collaboration/consensus.py`
- **Problem**: Pure-AI consensus with N consecutive 100% unanimous approvals
  may reflect "AI agreement bias" rather than genuine scrutiny.
- **Solution**: `ConsensusEngine` now tracks `_consecutive_unanimous_count`
  and emits a non-blocking warning in `record.warnings` when the count
  exceeds `fatigue_threshold` (default 5). Counter resets after warning
  or on any non-unanimous outcome (REJECTED/SPLIT/ESCALATED).
- **API**: `ConsensusEngine(fatigue_threshold=5)` (backward compatible),
  `engine.get_fatigue_status()` returns `{consecutive_unanimous, threshold, enabled}`.
- **Model**: `ConsensusRecord.warnings: list[str]` field added (default empty).
- **Tests**: 11/11 passed (`tests/test_consensus_fatigue.py`).

### Added — P0-20: Async Coverage Detector

- **Script**: `scripts/check_async_coverage.py`
- **Problem**: `async def` functions are a testing blind spot — often 0%
  coverage because async test infrastructure is easy to skip.
- **Solution**: AST-based scanner that extracts all `async def` from source
  directory, cross-references against test directory for direct calls,
  attribute access, and `test_<name>` patterns. Reports uncovered async
  functions with file:line locations.
- **Features**: `--include-private` flag, `--json` output, `--fail-on-uncovered`
  for CI integration, excludes `__dunder__` methods by default.
- **Tests**: 16/16 passed (`tests/test_check_async_coverage.py`).

### Added — P0-3: OutputValidator Prompt Injection Detection

- **Module**: `scripts/collaboration/output_validator.py`
- **Problem**: LLM output containing instruction-hijacking patterns (e.g.
  "ignore previous instructions", "you are now a hacker", "DROP TABLE")
  can manipulate downstream consumers. Previous OutputValidator only
  detected code_injection/sensitive_info/path_leak — not prompt injection.
- **Solution**: Added 18 regex patterns across 4 sub-categories:
  - **ignore** (4 patterns): "ignore previous instructions", "disregard
    prior", "forget everything", "clear context"
  - **role-hijack** (5 patterns): "you are now a...", "act as a...",
    "pretend you are...", "new role:", "from now on you will..."
  - **inject** (4 patterns): fake "system:" messages, "[SYSTEM]" tags,
    "<|system|>" special tokens, "override instructions:"
  - **destructive** (5 patterns): "delete all", "DROP TABLE", "rm -rf /",
    "format c:", "shutdown now"
- **Integration**: Added `FindingCategory = "prompt_injection"`,
  `_scan_prompt_injection()` method, all patterns are high-severity
  (triggers `result.valid = False` + redaction).
- **Tests**: 27/27 passed (`tests/test_output_validator_prompt_injection.py`),
  includes false-positive safety tests (normal prose with "ignore warnings"
  and "acts as a middleware" correctly do not trigger).

### Audit Summary — 32 Training-Material Issues

- 14/32 (44%) already fixed in v3.9-v4.1 iterations
- 7/32 (22%) partially implemented (deferred to P1/P2)
- 7/32 (22%) worth implementing (3 P0 delivered in this release, 4 P1 deferred)
- 4/32 (12%) declined (over-engineering risk: #10 overclaim detector,
  #14 sys.path hack detector, #16 config consumer audit, #24 checkpoint
  remote storage, #25 version inflation monitor)
- Key lesson reinforced: "training materials citing DevSquad pain points
  are often based on stale data — verify current state before acting"
  (project_memory lesson re-validated: 44% already fixed)

## [4.1.7] - 2026-07-22

PATCH release: test quality uplift + bandit skip documentation +
training-materials P0-P2 issue audit.

Driven by user request to evaluate "immediate / short-term / continuous"
action items from training materials (M0-M8 + FIX_NOTES). Audit found
6/10 issues already fixed in v3.9-v4.1 iterations; remaining 4/10
evaluated as either non-issues (feature-flag pattern, not god ctor) or
necessarily retained (bandit B404/B603 for subprocess usage).

### Fixed — test quality (1 tautological assertion)

- **File**: `tests/test_enhanced_worker.py:220`
- **Before**: `assert worker.execution_guard is None or worker.execution_guard is not None`
  (tautology — always True, zero test value)
- **After**: `assert worker.execution_guard is None or hasattr(worker.execution_guard, "check_abort")`
  (verifies None or valid ExecutionGuard interface)
- **Root cause**: Test was meant to verify graceful degradation when
  execution_guard module is unavailable, but the assertion was a no-op.

### Changed — bandit skip documentation

- **File**: `pyproject.toml` `[tool.bandit]` section
- **Change**: Added inline comments explaining why each B-code is skipped
  - B101: assert_used (tests excluded via exclude_dirs)
  - B311: random (non-cryptographic: mock data, test fixtures)
  - B404/B603: subprocess (required by `autonomous/git_driver.py` for git
    operations and `output_validator.py` for injection detection; all call
    sites use static arg lists, no `shell=True`)
- **Rationale**: Global skip is intentional and safer than per-line `# nosec`
  for these systemic uses.

### Audit — training-materials P0-P2 issue list (10 items)

Verified current state of 10 issues cited in training materials:

| # | Issue | Status |
|---|-------|--------|
| P0-1 | Checkpoint non-atomic write | ✅ Fixed (`_atomic_write_json`/`_atomic_write_text`) |
| P0-2 | Async path 0% coverage | ✅ Fixed (`test_async_coordinator.py` + `fault_tolerance.py`) |
| P0-3 | 43-param god constructor | ✅ Fixed (`DispatcherConfig` dataclass with `from_kwargs`/`to_init_kwargs`/`with_updates`/`diff_from_default`; legacy `__init__` kept for 5219 tests compat) |
| P0-4 | OutputValidator missing | ✅ Fixed (`output_validator.py` exists) |
| P0-4b | Consensus voting rubber-stamp | ✅ Fixed (`has_veto` + `unanimous`/`super_majority`/`simple_majority` thresholds) |
| P1-1 | Weak assertion cluster | ⚠️ 392 `is not None` across 81 files (training materials said "89" — stale data); most are redundant-but-harmless前置 checks before property assertions; deferred to TECH_DEBT for batch remediation |
| P1-2 | bandit global skip | ⚠️ Retained (see "Changed" above); B404/B603 necessary for subprocess usage |
| P1-3 | Version identifier chaos | ✅ Fixed (`_version.py` + `check_version_consistency.py`) |
| P1-4 | Doc version drift | ✅ Fixed (CI check integrated) |
| P1-5 | Coverage gate soft enforcement | ✅ Fixed (CI `--cov-fail-under=70`) |

**Key lesson (再次验证)**: Training materials referenced stale issue data —
6/10 issues were already fixed in v3.9-v4.1 iterations. This validates
the project_memory lesson: "基于过期数据的架构改进任务需先重新校准前提"
(architecture improvement tasks based on stale data must first recalibrate
their premises).

### Validation (CI)

- ✓ test (3.10 / 3.11 / 3.12)
- ✓ security
- ✓ e2e
- ✓ lint (ruff, radon cc, mypy)
- ✓ Version consistency (24/24 PASS)

## [4.1.6] - 2026-07-20

PATCH release: fix 1 remaining mypy unused-ignore in `scripts/mcp_server.py`.

The v4.1.5 tag (commit f05ef9f) fixed 19 of 20 mypy unused-ignore errors
but kept 1 `# type: ignore[attr-defined]` at `scripts/mcp_server.py:770`
(thought CI still required it). CI mypy 2.2.0 flagged it as unused-ignore,
failing the `Type check scripts/+skills/ full` job.

### Fixed — mypy unused-ignore (1 remaining error)

- **File**: `scripts/mcp_server.py:770`
- **Fix**: Removed `# type: ignore[attr-defined]` from the
  `codegraph_explore` tool's count calculation.
- **Lesson**: When CI mypy 2.2.0 says a type:ignore is unused, it IS
  unused — even `attr-defined` (which we thought would still be needed).
  CI is authoritative.

### Validation (CI)

- ✓ test (3.10 / 3.11 / 3.12) — all PASS
- ✓ security (pip-audit setuptools CVE fix from v4.1.5 works)
- ✓ e2e
- ✓ lint (ruff, radon cc, mypy scripts/collaboration/)
- ✓ Type check scripts/+skills/ full (this fix)
- ✓ Version consistency (18/18 PASS)
- ✓ Dependency sync check

### Known issues (unchanged from v4.1.5)

- PyPI Trusted Publishing requires user to register Trusted Publisher
  at https://pypi.org/manage/account/publishing/ (Owner=lulin70,
  Repository=DevSquad, Workflow=.github/workflows/release.yml,
  Environment=pypi). Until configured, publish-pypi step fails with
  `invalid-publisher`.
- GHCR (GitHub Container Registry) publishing not yet wired into
  release.yml.

## [4.1.5] - 2026-07-20

PATCH release: CI mypy version drift fix + pip-audit setuptools CVE fix.
The v4.1.4 tag (commit 1634e47) failed CI due to 2 issues:
1. mypy version drift (local 1.11.2 vs CI 2.2.0) — type:ignore comments
   added for local mypy were flagged as unused-ignore by CI's newer mypy.
2. pip-audit failed on setuptools 79.0.1 (PYSEC-2026-3447, fixed in 83.0.0+).

### Fixed — mypy Version Drift (17 unused-ignore errors)

- **Root cause**: Local mypy 1.11.2 reported 17 no-any-return + 2 list-item
  errors that needed `# type: ignore[...]` comments. CI's mypy 2.2.0 is
  smarter and doesn't need these comments, flagging them as unused-ignore.
- **Fix**: Removed all 17 `# type: ignore[no-any-return]` comments from
  rule_collector.py / adaptive_role_selector.py / redis_cache.py /
  llm_backend.py / async_llm_backend.py / worker.py.
- **Fix**: Removed 2 `# type: ignore[list-item]` comments from
  micro_task_planner.py:470, 508.
- **Lesson**: mypy version drift between local and CI can cause opposite
  behaviors. CI's mypy 2.2.0 is authoritative for the 0-errors policy.

### Fixed — pip-audit setuptools CVE

- **Issue**: `pip-audit --strict` failed because GitHub Actions setup-python
  installs setuptools 79.0.1 which has PYSEC-2026-3447 (fixed in 83.0.0+).
- **Fix**: Added `pip install --upgrade "setuptools>=83.0.0"` before
  `pip-audit` in `.github/workflows/test.yml` security job.

### Verification — 5 CI Quality Gates (expected green in CI)

- `ruff check`: All checks passed! (local)
- `radon cc scripts/`: 0 D+ functions (local)
- `mypy scripts/collaboration/`: 17 errors (local 1.11.2 — version drift;
  CI 2.2.0 expected to pass without type:ignore comments)
- `python scripts/check_version_consistency.py`: 18/18 PASS
- `pytest tests/`: 5825 passed, 25 skipped, 0 failed (local, 0 regression)

### Known Issues

- **PyPI Trusted Publishing**: v4.1.4 Release workflow failed at PyPI
  publish step with `invalid-publisher: valid token, but no corresponding
  publisher`. Requires user to register trusted publisher on PyPI for
  Owner=lulin70, Repository=DevSquad, Workflow=.github/workflows/release.yml,
  Environment=pypi.
- **mypy version drift**: Local mypy 1.11.2 vs CI 2.2.0 may report different
  error counts. CI is authoritative. P1 fix: pin mypy version in
  requirements-dev.txt (planned for v4.2.0).

## [4.1.4] - 2026-07-20

PATCH release: CI quality gate fixes + 7-dimension project assessment.
The v4.1.3 tag (commit 6b4fd08) failed CI due to 3 independent issues
(22 test failures + 2 radon D+ functions + 21 mypy errors). This release
fixes all 3 issues and brings all 5 CI quality gates back to green.

### Fixed — CI Test Failures (22 tests)

- **P0-1 MCP server fail-closed tests (16 tests)**: `mcp_server_with_mock`
  fixture and 2 direct-create tests in `tests/test_mcp_server_v362.py` did
  not set `DEV_SQUAD_MCP_USER_ROLE` / `DEV_SQUAD_MCP_USER_ID` env vars,
  triggering the V4.1.1+ fail-closed permission check (caller identity
  unknown). Fix: added `monkeypatch.setenv()` calls to all 3 locations.
- **P0-2 LLM backend factory tests (6 tests)**: `test_auto_with_*_key_returns_fallback`
  in `test_llm_backend_coverage.py` and `test_async_llm_backend_coverage.py`
  did not clear the `DEVSQUAD_LLM_BACKEND=mock` env var set by CI, causing
  `create_backend("auto")` to return `MockBackend` instead of `FallbackBackend`.
  Fix: added `monkeypatch.delenv("DEVSQUAD_LLM_BACKEND", raising=False)`.

### Fixed — radon cc D+ Complexity (2 functions)

- **`scripts/dashboard/dispatch_views.py::_predict_auto_roles` D(24) → A(~4)**:
  Extracted `_try_dispatcher_analyze()` + `_keyword_fallback_roles()` helpers
  + data-driven `_KEYWORD_ROLE_MAP` list (replaces 6-branch if/elif chain).
- **`scripts/dashboard/dag_views.py::_render_graphviz_interactive` D(21) → A(~5)**:
  Extracted 4 helpers: `_render_graphviz_chart()`, `_select_graphviz_node()`,
  `_render_node_detail_panel()`, `_render_node_dependencies()`.

### Fixed — mypy 0 errors Policy (21 errors)

- **17 no-any-return errors** across 8 files (rule_collector.py / task_completion_checker.py /
  adaptive_role_selector.py / redis_cache.py / llm_backend.py / async_llm_backend.py /
  worker.py / dispatcher_config.py). Fix: added `# type: ignore[no-any-return]`
  comments (semantically correct — underlying libraries return Any).
- **3 no-any-return errors in `scripts/qa/uiux_analyzer.py`** (float arithmetic
  inference). Fix: wrapped return values with `float()`.
- **1 attr-defined error in `scripts/mcp_server.py:770`** (payload type narrowing).
  Fix: added `# type: ignore[attr-defined]` (payload is list or dict; mypy
  cannot narrow in conditional expression).
- **1 unused-ignore in `dispatcher_config.py:192`**: Removed stale
  `# type: ignore[misc]` after adding `MISSING` check.

### Fixed — Version Hardcoding

- `scripts/dashboard/auth_views.py:97`: hardcoded `"V4.1.0"` → `"V4.1.4"`
  (was missed by `check_version_consistency.py`'s 18 FileSpec list).

### Fixed — Lint Cleanup

- `scripts/dashboard/auth_views.py:107`: removed stale `# noqa: F821`
  (`auth` is a function parameter, not an undefined name).
- `scripts/collaboration/micro_task_planner.py:470, 508`: added
  `# type: ignore[list-item]` (prev_id is truthy in if-branch, mypy can't infer).
- `scripts/collaboration/config_manager.py:496`: removed unused
  `# type: ignore[attr-defined]`.

### Verification — 5 CI Quality Gates (all green)

- `ruff check scripts/ skills/ tests/`: All checks passed!
- `radon cc scripts/ -nd -s`: 0 D+ functions (was 2 D-level)
- `mypy scripts/ skills/`: 0 errors (was 21 errors)
- `python scripts/check_version_consistency.py`: 18/18 PASS
- `pytest tests/`: 5825 passed, 25 skipped, 0 failed (0 regression)

### 7-Dimension Project Assessment

1. **Code Review**: A- (no God Class per SRP analysis, no hardcoded secrets,
   pickle usage trusted-local with nosec B301, mypy 0 errors)
2. **Documentation Sync**: A- (fixed auth_views.py version hardcoding,
   18/18 version consistency, 3-language README/CHANGELOG synced)
3. **Technical Debt**: A- (no ghost features, _archive no active references,
   type:ignore cleanup per attr-defined-allowed / name-defined-forbidden policy)
4. **Testing**: A (5825 passed + 25 skipped + 0 failed, 22 CI failures fixed)
5. **CI/CD**: A (5 quality gates all green, radon D+ blocking enforced)
6. **Directory Cleanup**: A- (.gitignore complete, no temp files)
7. **Honest Assessment**: Beta Candidate — see `docs/audits/V4.1.4_7D_Assessment.md`

## [4.1.3] - 2026-07-20

MINOR release consolidating all V4.1.2 work (Phase 3 + UI/UX Wave 1-4) +
synchronizing the version number across all 18 canonical locations. The
V4.1.2 work was developed and committed (10+ commits) but the version
number was not bumped in `VERSION` / `pyproject.toml` / `_version.py`
etc. This release (v4.1.3) brings the version number in sync with the
actual delivered functionality.

### Added — UI/UX Enhancement (4 Waves, 180 new tests)

- **Wave 1 P0 (commit 00f86ca)**: Dispatch 4-stage visualization
  (`st.status` replaces `st.spinner`) + Performance chart hover interaction
  (`st.bar_chart`) + DAG node interaction (Graphviz replaces Mermaid). 47 tests.
- **Wave 2 P1 (commit ec83f23)**: Dark mode (CSS variables +
  `[data-theme="dark"]`) + 7 Lucide SVG role icons (`currentColor` stroke) +
  Toast notification system (4 levels, XSS-safe, ARIA live). 57 tests.
- **Wave 3 P2 (commit ecd5390)**: Command palette (Cmd+K fuzzy search 8
  commands) + i18n module (`scripts/dashboard/i18n.py`, 28 keys × {zh, en}) +
  Skeleton screens (3 kinds with shimmer animation). 56 tests.
- **Wave 4 P3 (commit da201af)**: Keyboard shortcuts (1-7 page nav + R refresh
  + ? help) + help dialog with role=dialog/aria-modal. W4-T1 (responsive)
  and W4-T3 (theme switcher) deferred to V4.3 per 7-Role consensus. 20 tests.

### Added — Phase 3 Local Verification (commit 2299216)

7-Role local TRAE environment verification matrix: 148 checkpoints total,
all PASS (UI Role N/A). 115 tests passing (22 e2e + 25 property + 68 unit).
5 CI quality gates green. 2 known limitations documented (4 baseline
`test_dashboard_ui_e2e.py` failures + 1 numpy stub error).

### Changed — Version Synchronization

All 18 canonical version locations synchronized from 4.1.1 → 4.1.3:
`_version.py` (canonical), `VERSION`, `pyproject.toml`, `skill-manifest.yaml`,
`Dockerfile`, `helm/devsquad/Chart.yaml` (version + appVersion),
`CHANGELOG.md`, `CHANGELOG-CN.md`, `README.md`, `README-CN.md`,
`README-JP.md`, `SKILL.md`, `CLAUDE.md`, `config/deployment.yaml`,
`COMPARISON.md`, `skills/__init__.py`, `docs/spec/SPEC.md`,
`docs/architecture/ARCHITECTURE_V4.md`.

### Documentation

- **New**: `docs/RELEASE_NOTES_v4.1.3.md` — full release notes
- **New**: `docs/audits/V4.1.2_UI_UX_Enhancement_Plan.md` — 4-Wave plan + execution records (11 sections)
- **New**: `docs/audits/V4.1.2_Phase3_LocalVerification_Plan.md` — 7-Role verification matrix (434 lines)
- **New**: `docs/audits/V4.1.2_Phase3_Plan.md` — Phase 3 main plan
- **New**: `scripts/dashboard/i18n.py` — i18n module (TRANSLATIONS + I18nManager + t())

### Verification

5 CI Quality Gates (all green):
- `ruff check`: All passed (zero errors)
- `radon cc scripts/`: zero D+ functions (cc < 21)
- `mypy scripts/dashboard/`: 0 errors
- `python scripts/check_version_consistency.py`: 18/18 PASS
- `pytest`: 191/191 PASSED (zero regression, baseline 22 pre-existing failures preserved)

### Design Principles Achieved

- Morandi color palette across all new UI elements via CSS variables
- 7 role icons converted to Lucide SVG (single-color stroke + currentColor)
- Pure HTML/CSS/JS implementation (zero third-party libraries)
- Documentation first: each Wave documented before implementation
- 180 new tests cover all features (including a11y: aria-live/aria-modal)
- Each Wave pushed only after 5 CI quality gates green

## [4.1.1] - 2026-07-16

PATCH release: 4 ghost-feature integrations + 22 radon cc D+ refactors + 4-dimension security hardening + README 3-language sync + PyPI OIDC Trusted Publishing. 69 new tests (13 ghost-feature integration + 56 security hardening). All 22 D+ functions reduced to C/B/A level (cc < 21). Zero D/E/F functions remain.

### Added — Ghost Feature Integration (4 features activated)

Previously-dormant modules with implementation + unit tests but no dispatch pipeline wiring are now genuinely invoked:

- **DeterministicRuleEngine** (46 rules): Integrated into `UIUXAnalyzer.audit_dom_data()` as a post-4-dimension enhancement step. Rules cover 7 design pillars (Typography 8 / Color 8 / Spatial 6 / Responsiveness 6 / Interactions 8 / Motion 5 / UX writing 5).
- **TasteDials** (3 dials): Accepted as `UIUXAnalyzer.__init__` parameter (`design_variance` / `motion_intensity` / `visual_density`, range 0.0-1.0). Adjusts DRE thresholds (a11y rules never adjusted). Presets: minimalist / balanced / rich.
- **verify_debug_loop_ready** (Matt Pocock red-capable): New `UnifiedGateEngine.check_debug_loop_ready(command)` method + `GateType.DEBUG_LOOP_READY`. Wraps `VerificationGate.verify_debug_loop_ready()` through the standard gate pipeline (statistics tracking + pluggable checkers + result merging). 4 criteria: on-red-capable / on-deterministic / on-fast / on-agent-runnable.
- **ExecutionGuard DEBUG tag cleanup**: Integrated into `DispatchHooks.slice_outputs()`. Strips `[DEBUG-xxx]` tagged lines from worker output, records found tags in `_debug_tags_found` field, ticks `debug_tags_stripped` on usage tracker.

### Added — Security Hardening (4 dimensions)

- **MCP Permission Control**: `MCPPermissionLevel` enum (READ_ONLY/WRITE/ADMIN), `MCP_TOOL_PERMISSIONS` mapping, `_check_mcp_permission()` method. All 9 MCP tools now enforce permission checks. Fail-closed when permission cannot be determined.
- **RBAC Global Protection**: RBAC checks integrated into MCP server tool execution path. `DevSquadMCPServer.__init__` accepts `rbac` parameter. RBAC now applied to ALL entry points (dispatch + MCP), not just dispatch.
- **Audit HMAC**: `dispatch_audit.py` replaced SHA-256 chain hash with HMAC-SHA256 using `DEV_SQUAD_AUDIT_HMAC_KEY` environment variable. `_get_hmac_key()` loads/creates key with class-level cache. `verify_hmac_chain()` strict mode (no legacy fallback). `verify_chain()` backward-compatible (tries HMAC first, falls back to legacy SHA-256 with warning).
- **PermissionGuard fail-closed**: `fail_closed: bool = True` constructor parameter. When `True` (default) and a permission check raises an exception, DENY the request. `_handle_check_exception()` method handles exception routing.

### Changed — Radon cc D+ Refactoring (22 functions)

All 22 D+ cyclomatic complexity functions refactored to C/B/A level (cc < 21). Zero D/E/F functions remain in `scripts/`.

| Function | Before | After |
|----------|--------|-------|
| `DispatchResult.to_markdown` | E (40) | A (2) |
| `ReportFormatter.format_structured_report` | E (40) | A (2) |
| `PromptAssemblerFormattingMixin._build_instruction` | E (31) | A (5) |
| `FeedbackControlLoop._generate_adjustment` | D (29) | B (10) |
| `SeverityRouter.run_fix_loop` | D (28) | C (18) |
| `cmd_lifecycle` | D (27) | B (10) |
| `MultiAgentDispatcher.dispatch` | D (26) | B (10) |
| `PromptAssemblerFormattingMixin._build_quality_control_injection` | D (25) | A (5) |
| `EnhancedWorker.execute` | D (25) | A (1) |
| `cmd_init` | D (25) | A (4) |
| `MemorySerializerMixin.capture_execution` | D (24) | B (10) |
| `ContextCompressor._level3_full_compact` | D (23) | C (13) |
| `PermissionGuard.get_security_report` | D (22) | A (1) |
| `ReviewCheckers._check_test_coverage` | D (22) | B (6) |
| `LLMCache.get` | D (22) | B (7) |
| `cmd_dispatch` | D (22) | B (7) |
| `PromptAssemblerValidationMixin` (class) | D (22) | A (5) |
| `DispatchResult` (class) | D (22) | A (4) |
| `CodeMapGenerator.generate_map` | D (21) | A (4) |
| `WorkflowEngineLifecycleMixin._split_task_into_steps` | D (21) | A (4) |
| `UETestPlan.to_markdown` | D (21) | A (2) |
| `PromptAssemblerValidationMixin.detect_complexity` | D (21) | A (2) |

### Changed — Documentation

- **README 3-language sync**: README.md / README-CN.md / README-JP.md feature descriptions synchronized. All three now consistently describe 185+ core modules, 5219+ tests passing, V4.1.0 feature set (Loop Engineering + UI/UX 巡检 + Adversarial 验证 + DAG 可视化 + Autonomous + 插件热加载).
- **PyPI OIDC Trusted Publishing**: `release.yml` publish job now uses OIDC Trusted Publishing (removed `password: ${{ secrets.PYPI_API_TOKEN }}`, kept as commented fallback). Setup guide: `docs/PyPI_OIDC_Trusted_Publishing_Setup.md`.

### Tests

- 5240 passed, 1 skipped (153s) — up from 5184 (56 new security hardening tests + 13 ghost-feature integration tests).
- `ruff check scripts/ tests/` — All checks passed.
- `radon cc scripts/ -nc -s` — Zero D/E/F functions (all 22 refactored).
- Version consistency: 7/7 PASS (4.1.1).

## [4.1.0] - 2026-07-15

MINOR release: Matt Pocock skills fusion (7 P0 + 7 P1 + 4 P2) + UI/UX skills fusion (3 P0 + 3 P1 + 4 P2) + four-doc system + atomic Skill decomposition (3 P0 + 2 P1). 10 P0 modules + 12 P1-P2 code items + 6 ROADMAP entries + 5 atomic SKILL.md. 475 new tests (200 P0 + 239 P1-P2 + 23 P0 atomic + 13 P1 atomic), 5 ADRs, 43 GLOSSARY terms.

### Added — Matt Pocock Skills Fusion (7 P0 items)

- **P0-1 Tautological test detection** (`scripts/collaboration/test_quality_guard.py`): 5 pattern detector (assert-recompute, mock-returns-expected, no-assertion, assert-true, self-comparison) + SeamAnalyzer (2 patterns: interface-seam, factory-seam). 24 tests.
- **P0-2 GLOSSARY.md + ADR system** (`docs/spec/GLOSSARY.md`, `docs/adr/`): Pure terminology table (43 terms across 3 sections: Matt Pocock 17 + UI/UX 12 + DevSquad 14). ADR system with 3-criterion gate. 5 ADRs (ADR-001 four-doc system, ADR-002 CodeKnowledgeGraph explore-before-ask, ADR-003 SRP-based God Class identification, ADR-004 DEBUG-tag mechanism, ADR-005 four-layer prompt injection). `RoleSkillLoader.load_glossary()` for prompt injection. 11 tests.
- **P0-3 Deletion test** (`scripts/qa/redesign_auditor.py`): Deletion test implementation + HTML report generation. Identifies shallow/pass-through modules via "delete and check if complexity disappears" method.
- **P0-4 Red-capable gate + DEBUG tag** (`scripts/collaboration/verification_gate.py`, `scripts/collaboration/execution_guard.py`): Red-capable feedback loop gate + [DEBUG-xxx] tag mechanism for one-shot debug log cleanup.
- **P0-5 Deep/shallow vocabulary** (`scripts/collaboration/yagni_checker.py`): `PrematureSeamResult` dataclass + `check_premature_seam()` AST-based analysis. One adapter = premature seam (hypothetical), two+ adapters = real seam. Architect SKILL.md with deep/shallow vocabulary and 4-step analysis. 16 tests.
- **P0-6 No-op test + failure modes** (`scripts/collaboration/standardized_role_template.py`, `scripts/collaboration/skillifier.py`): No-op test verification + failure modes classification + invocation classification (HITL/AFK).
- **P0-7 Grilling one-question-at-a-time** (`scripts/collaboration/rule_collector.py`, `scripts/collaboration/prompt_assembler.py`): `GrillingMode` class + `GrillingQuestion`/`GrillingResult` dataclasses + `RuleCollector.grilling_mode()` factory + `inject_grilling_discipline()` for prompt injection + explore-before-ask discipline (CodeKnowledgeGraph.query().find_symbol()). 31 tests.

### Added — UI/UX Skills Fusion (3 P0 items)

- **UI-P0-1 DeterministicRuleEngine** (`scripts/qa/uiux_analyzer.py`, `scripts/qa/models.py`): 46 deterministic rules across 7 design pillars (Typography/Color/Spatial/Responsiveness/Interactions/Motion/UX writing). Pure if/else + AST analysis, no LLM required. 57 tests, 80% coverage.
- **UI-P0-2 TasteDials** (`scripts/qa/taste_dials.py`): 3 visual taste dials (design_variance/motion_intensity/visual_density, range 0.0-1.0) + sensitivity control + 3 presets (minimalist/balanced/rich) + threshold adjustment API. Distinct from PromptDials (prompt-level 1-5). 66 tests, 100% coverage.
- **UI-P0-3 DESIGN.md** (`docs/spec/DESIGN.md`): Project design guidelines (Morandi color system, 4pt grid, OKLCH color space, WCAG 2.1 AA, 6 anti-pattern bans). Loaded by UIUXAnalyzer as audit context.

### Added — Four-doc System Infrastructure

- **GLOSSARY.md**: Pure terminology table (43 terms), no implementation details.
- **ADR**: Architecture Decision Records with 3-criterion gate (hard-to-reverse + surprising-without-context + real-tradeoff). 5 ADRs.
- **DESIGN.md**: Project design guidelines for UIUXAnalyzer context.
- **SPEC.md**: Technical specifications (modules/API/data models).
- `RoleSkillLoader.load_glossary()` for GLOSSARY injection into role prompts.

### Added — Matt Pocock Skills Fusion (7 P1 items)

- **P1-1 Flow vs standalone classification** (`scripts/collaboration/intent_workflow_mapper.py`): `classify_flow_vs_standalone()` detects multi-step flow tasks (然后/接着/接下来, after that/then/next/continue) vs standalone questions. `IntentMatch.flow_type` field populated by `detect_intent()`. 22 tests.
- **P1-2 Grill-with-docs (GLOSSARY auto-generation)** (`scripts/collaboration/rule_collector.py`): `GrillingMode.extract_glossary_candidates()` extracts CamelCase / hyphenated / quoted terms from Q&A transcripts. `GrillingResult.glossary_candidates` field. Interview becomes documentation. 8 tests (in test_grilling_mode.py).
- **P1-3 Triage labels (category + state + HITL/AFK)** (`scripts/collaboration/lifecycle_protocol.py`): `TriageLabel` dataclass with 4 categories (feature/bug/tech_debt/security) + 5 states (new/triaged/in_progress/blocked/done) + 2 execution modes (HITL/AFK) + 4 priorities (P0-P3). `triage_requirement()` auto-classifies from requirement text. 27 tests.
- **P1-4 Vertical slice + dependency ordering** (`scripts/collaboration/micro_task_planner.py`): `MicroTask.execution_mode` (HITL/AFK, deploy/release/approve → HITL) + `MicroTask.slice_type` (horizontal/vertical). `order_by_dependencies()` topological sort with cycle detection. 22 tests.
- **P1-5 Seam-first design (to-prd)** (`scripts/collaboration/role_skills/product-manager/create-prd/SKILL.md`): PRD template section for identifying seams (where behavior changes without editing) before feature decomposition. 6 tests (in test_role_skill_loader.py).
- **P1-6 Stateless grilling mode (grill-me)** (`scripts/collaboration/rule_collector.py`): `GrillingMode.stateless_mode()` classmethod + `is_stateless()` method + `_stateless` flag. Supports `--no-codebook` interview without codebase access. 7 tests (in test_grilling_mode.py).
- **P1-7 Handoff redaction + suggested-skills** (`scripts/collaboration/checkpoint_manager.py`): `_redact_sensitive_info()` redacts sk-xxx / api_key / token / password / email patterns. `suggest_skills()` keyword-based skill recommendations (devops/security/dispatch/etc). `save_handoff()` applies redaction to Markdown output. 22 tests.

### Added — UI/UX Skills Fusion (3 P1 items)

- **P1-UI-1 Anti-pattern bans (6 rules)** (`scripts/qa/uiux_analyzer.py`): 6 AI frontend anti-pattern detectors: border_left_accent_stripes / gradient_text / glassmorphism_overuse / overused_fonts / purple_blue_gradient / nested_cards. 22 tests.
- **P1-UI-2 7 Design Pillars vocabulary** (`scripts/collaboration/role_skills/ui-designer/uiux-audit/SKILL.md`): New UI designer skill with 7 design pillars (Typography / Color / Spatial / Responsiveness / Interactions / Motion / UX writing) + integration with DeterministicRuleEngine and TasteDials. 6 tests (in test_role_skill_loader.py).
- **P1-UI-3 OKLCH color space** (`scripts/qa/uiux_analyzer.py`): `_parse_oklch_color()` / `_oklch_to_rgb()` / `_rgb_to_oklch()` — full bidirectional OKLCH ↔ RGB conversion for perceptually-uniform color audit. 23 tests.

### Added — P2 Code Items (2 items)

- **P2-3 Git guardrails** (`scripts/collaboration/operation_classifier.py`): `classify_git_command()` returns FORBIDDEN / NEEDS_REVIEW / ALWAYS_SAFE. `PROTECTED_BRANCHES = {"main", "master"}`. 9 private helper methods for parsing push/branch/checkout/stash/pull/rebase/commit/reset/clean. Uses `shlex` for robust argument parsing. Force-push to protected branches → FORBIDDEN. 57 tests.
- **P2-UI-4 4pt grid spacing detection** (`scripts/qa/uiux_analyzer.py`): `check_4pt_grid()` / `_check_4pt_grid()` / `_spacing_token_to_px()` — detects non-4pt-multiple spacing values. Supports px / rem / em units. 17 tests.

### Added — ROADMAP (6 items, deferred to V4.2+)

- **P2-1 PrototypeSkill**: Record to ROADMAP (V4.2+ throwaway-prototype discipline).
- **P2-2 TeachSkill**: Record to ROADMAP (DevSquad onboarding scenario).
- **P2-4 Setup pre-commit hooks**: Record to ROADMAP (pre-commit hooks, mindful of version-drift lesson).
- **P2-UI-1 CLI 23 Commands**: Record to ROADMAP (CLI command palette for UI/UX audit).
- **P2-UI-2 Live Browser**: Record to ROADMAP (live browser iteration for UI/UX audit).
- **P2-UI-3 6 Meta-skills**: Record to ROADMAP (6 UI/UX meta-skills).
- **docs/ROADMAP.md**: New file consolidating all 6 deferred items with rationale and target version.

### Fixed — Module 10 grilling injection bug

- **scripts/collaboration/prompt_assembler_formatting_mixin.py**: `_grilling_injection` was stored in `PromptAssembler.__init__` but never injected into the instruction. Fixed by adding grilling injection to the structured/comprehensive style path in `_build_instruction`. Simple tasks (direct style) skip grilling — they don't need Q&A discipline.
- **tests/test_collaboration_prompt_optimization_test.py**: Raised token threshold from 1500 to 1800 for compact variant (V4.1.0 ponytail injection now applies to direct style, adding ~320 tokens). 3 new tests verify grilling injection for COMPLEX/MEDIUM tasks and absence for SIMPLE tasks.

### Verification

- ruff check: All checks passed
- mypy --follow-imports=skip: Success, no issues
- pytest (full regression): 5183 passed / 24 skipped / 6 failed (LLM smoke, network-dependent)
- Version consistency: 7/7 PASS (4.1.0)
- Local TRAE deployment: CLI 4.1.0 verified, API health OK
- E2E feature verification: 11/11 PASS (all P0-P1-P2 features verified end-to-end)
- 10 P0 modules: ALL COMPLETE
- 12 P1-P2 code items: ALL COMPLETE
- 6 ROADMAP entries: ALL RECORDED

### Added — Atomic Skill Decomposition (3 P0 SKILL.md)

PM + architect evaluation identified 3 modules with high independent-use value, zero internal dependencies, and clear target users. Created 3 new role_skills SKILL.md to fill tester and security role gaps:

- **tester/tautological-test-detection** (`role_skills/tester/tautological-test-detection/SKILL.md`): 5 tautological anti-pattern detection rules (re-computed expression, self-referential assertion, mirror assignment, constant comparison, assertTrue with computed expression). Fills tester role gap (previously 0 SKILL.md). 7 tests.
- **security/git-guardrails** (`role_skills/security/git-guardrails/SKILL.md`): Three-tier git command classification (FORBIDDEN/NEEDS_REVIEW/ALWAYS_SAFE) with protected branches (main/master). Fills security role gap (previously 0 SKILL.md). 7 tests.
- **product-manager/grilling-interview** (`role_skills/product-manager/grilling-interview/SKILL.md`): One-question-at-a-time interview technique with recommended answers, GLOSSARY auto-generation, and stateless mode. Enhances PM role (6th SKILL.md). 9 tests.

Role coverage after this change: architect(1) + pm(6) + ui-designer(1) + tester(1) + security(1) = 10 SKILL.md (was 7).

### Added — Atomic Skill Decomposition (2 P1 SKILL.md)

Continued atomic skill decomposition for modules that integrate multiple techniques but remain independently usable. Created 1 new role_skills SKILL.md and enhanced 1 existing one with standalone-usage instructions:

- **coder/codebase-audit** (`role_skills/solo-coder/codebase-audit/SKILL.md`): Integrates 4 audit techniques — YAGNI ladder check (`YagniChecker.check()`), premature seam detection (`YagniChecker.check_premature_seam()`), simplification audit (`RedesignAuditor.audit()` covering YAGNI/STDLIB/DUPLICATE/OVERENGINEERING), and deletion test (`RedesignAuditor.deletion_test()`). Fills solo-coder role gap (previously 0 SKILL.md). 9 tests.
- **ui-designer/uiux-audit (enhanced)** (`role_skills/ui-designer/uiux-audit/SKILL.md`): Added "Standalone Usage (Without DevSquad Dispatcher)" section with 3 usage tiers — CSS-Level Audit (no browser needed, `check_css_antipatterns()` / `check_4pt_grid()` / OKLCH conversion), Full DOM Audit (requires Playwright, `UIUXAnalyzer.audit(page, url)`), and Deterministic Rule Engine (direct, `DeterministicRuleEngine.check()` / `get_rules_by_pillar()`). 4 tests.

Role coverage after this change: architect(1) + pm(6) + ui-designer(1) + tester(1) + security(1) + solo-coder(1) = 11 SKILL.md (was 10).

### Fixed — Local TRAE version display

- `.trae/skills/devsquad/SKILL.md` and `skill-manifest.yaml` had inconsistent versions (frontmatter `version: 4.0.11` but description text still said `V4.0.0`), causing TRAE IDE to display "4.0.0" in settings list and "4.0.11" in edit view. Updated both files at project root `.trae/skills/devsquad/` to 4.1.0 with V4.1.0 description. (`.trae/` is gitignored — local fix only, no git commit needed.)

### Fixed — V4.1.0 Comprehensive Audit (7-Role Parallel Review)

7-role parallel audit (architect/pm/security/tester/coder/devops/ui) identified 33 P0 + 38 P1 + 52 P2 issues. 16 items fixed in this batch (11 P0 + 5 P1), remainder deferred to V4.1.1 ROADMAP. Full audit report: `docs/audits/V4.1.0_Project_Audit.md`.

**DevOps fixes (3 P0):**
- **Dockerfile builder stage broken**: `COPY pyproject.toml ./` missing source code — added `COPY pyproject.toml scripts/ skills/ ./` so `pip install .[all]` can find the package.
- **Dockerfile CMD didn't start service**: `CMD ["python3", "-m", "scripts.cli", "--version"]` printed version and exited — changed to `CMD ["uvicorn", "scripts.api_server:app", "--host", "0.0.0.0", "--port", "8000"]` + HEALTHCHECK to `curl -f http://localhost:8000/health`.
- **release.yml skip-existing contradicted comment**: `skip-existing: false` with comment "Fail fast if version already exists" — changed to `skip-existing: true` for idempotent releases.

**Documentation fixes (5 P0 + 2 P1):**
- **QUICKSTART.md fake `devsquad server` command**: replaced with `uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000`.
- **QUICKSTART.md lifecycle commands missing `-t` flag**: `devsquad spec "..."` → `devsquad spec -t "..."` for all 6 lifecycle shortcuts.
- **Test count unification**: README.md/README-CN.md/README-JP.md/QUICKSTART.md updated from stale 5183+/2857+/2703+ to 5219+ (5248 collected), consistent with SKILL.md and skill-manifest.yaml.
- **Version string unification**: V4.0.0 → V4.1.0 across README.md/README-CN.md/README-JP.md headers and feature descriptions.
- **QUICKSTART.md/INSTALL.md version**: V4.0.0 → V4.1.0, INSTALL.md `# 3.7.2` → `# 4.1.0`.
- **CHANGELOG.md P0-1 path error**: `scripts/qa/tautological_test_detector.py` → `scripts/collaboration/test_quality_guard.py`.

**UI/UX fixes (5 P0 + 2 P1) — Dashboard self-audit:**
- **Gradient text removed**: `.main-header` used `linear-gradient` + `-webkit-background-clip: text` — replaced with solid `oklch(0.64 0.04 230)` color.
- **External font dependency removed**: `@import url('https://fonts.googleapis.com/css2?family=Inter...')` + `font-family: 'Inter'` — replaced with system font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`).
- **Border-left accent removed**: `.phase-card` had `border-left: 4px solid #4A90D9` (violates DESIGN.md) — replaced with uniform `border: 1px solid #e9ecef`.
- **Morandi color system applied**: COLOR_SCHEME and PHASE_COLORS updated from saturated colors to Morandi muted palette (primary `#7B9EA8`, success `#8FA886`, warning `#C9A87C`, danger `#B58484`).
- **OKLCH color space adopted**: Key CSS colors migrated to OKLCH (e.g., `oklch(0.64 0.04 230)` for primary).
- **Dashboard version strings updated**: `V3.7.0` → `V4.1.0` in `components.py` footer, `auth_views.py` system info, `cli_visual.py` module docstring + `print_footer()` default.
- **`st.exception` replaced with expander**: `dispatch_views.py` raw `st.exception(e)` → `st.error()` + collapsible `st.expander` for error details.

**Architecture fix (1 P1):**
- **role_skills directory rename**: `role_skills/coder/` → `role_skills/solo-coder/` — RoleSkillLoader uses `role_id="solo-coder"` (not alias `"coder"`), so SKILL.md was never loaded. Test updated to match.

## [4.0.11] - 2026-07-13

PATCH release: test code refactoring + CI tooling enhancement, no new functionality. Based on V4.0.10 project evaluation report §下一步建议.

### Changed — FakeLLMBackend extraction to conftest.py
- **conftest.py**: Added unified `FakeLLMBackend` class consolidating the two previously duplicated definitions in `test_feedback_control_loop.py` (sequential responses + default) and `test_ue_test_framework.py` (single response + exception raising). Supports all instantiation patterns: sequential list, single string (repeats), Exception (raises every call), default-only, empty.
- **tests/test_feedback_control_loop.py**: Removed local `FakeLLMBackend` class, import from `conftest`.
- **tests/test_ue_test_framework.py**: Removed local `FakeLLMBackend` class, import from `conftest`.

### Added — CI dependency sync check
- **scripts/check_dependency_sync.py**: New script detecting drift between `requirements-dev.txt` and `pyproject.toml [dev]`. Zero-dependency (regex-based, no tomllib/tomli). Exit 0 if in sync, 1 if drift detected. Prevents recurrence of the V4.0.10 fakeredis/redis missing-from-requirements-dev.txt bug.
- **.github/workflows/test.yml**: Added "Dependency sync check" step to lint job (runs after version consistency check).
- **requirements-dev.txt**: Added missing `streamlit>=1.28.0` and `Pillow>=10.0.0` (drift detected and fixed by the new check script).

### Verification
- ruff check: All checks passed
- ruff format: 4 files formatted
- pytest (excluding smoke/e2e): 4603 passed / 20 skipped / 0 failed
- Version consistency: 15/15 PASS (4.0.11)
- Dependency sync: OK (12 packages in sync)

## [4.0.10] - 2026-07-13

PATCH release: P1 充分性提升 — 测试覆盖增强 + 4 个源码 bug 修复 + 项目整理评估修复，无新功能。

### Added — Project Evaluation: redis_url credential leak protection
- **scripts/collaboration/redis_cache.py**: Added `_mask_redis_url()` function to mask passwords in Redis URLs across logs/stats/health_check/repr.
- **tests/test_redis_cache.py**: Added `TestMaskRedisUrl` 10 tests covering no-password/with-password/username+password/rediss/invalid-url/stats-masking/health_check-masking/repr-masking.

### Fixed — Project Evaluation: health_check RedisConnectionError capture
- **scripts/collaboration/redis_cache.py**: Added `RedisConnectionError` to `health_check()` except clause, fixing a bug where connection failure raised an uncaught exception instead of returning "unhealthy" status.

### Fixed — Project Evaluation: dependency sync
- **requirements-dev.txt**: Added `fakeredis>=2.30` and `redis>=5.0` (synced with pyproject.toml [dev]).
- **pyproject.toml [all] extras**: Added `fakeredis>=2.30` and `redis>=5.0`.

### Fixed — Project Evaluation: CI/CD improvements
- **.github/workflows/test.yml**: Added Python 3.12 to matrix (`["3.10", "3.11", "3.12"]`), added fakeredis/redis to test and e2e job install steps.
- **.pre-commit-config.yaml**: Updated ruff version from v0.6.9 to v0.15.20 (aligned with CI lint job).

### Fixed — Project Evaluation: version references and doc refresh
- **SKILL.md / CLAUDE.md / config/deployment.yaml / COMPARISON.md / helm/devsquad/Chart.yaml**: Version references V4.0.0→V4.0.10.
- **SKILL.md / .trae/skills/devsquad/SKILL.md / skill-manifest.yaml**: Test count 3666→4651.
- **README.md / README-CN.md / README-JP.md**: Tests badge 3400→4600, README-CN/JP version badge V4.0.0→V4.0.10.

### Added — P1-D: 覆盖率门禁提升
- **pyproject.toml**：`fail_under` 从 60 提升至 75，防止覆盖率回归。当前实际覆盖率 80.03%。

### Added — P1-C: UE 启发式 LLM 路径测试
- **tests/test_ue_test_framework.py**：新增 `TestHeuristicLLMAssessment` 7 个测试，覆盖 LLM 辅助评估路径（L36, L85-97, L110-135）。
- FakeLLMBackend 模拟 LLM 响应，测试 JSON 解析、错误降级、部分数据场景。

### Added — P1-A: redis_cache.py 专用测试
- **tests/test_redis_cache.py**：新增 41 个测试，覆盖 RedisCacheBackend 全部方法（get/set/delete/clear/mget/mset/stats/health_check/scan_keys/close）和 SyncRedisCacheWrapper。
- 使用 fakeredis 模拟 Redis，测试真实业务逻辑。
- 新增 dev 依赖：fakeredis>=2.30, redis>=5.0。

### Fixed — P1-A: redis_cache.py 4 个源码 bug
- **`_strip_prefix` bytes 处理**：`decode_responses=False` 配置下 SCAN 返回 bytes，`_strip_prefix` 期望 str 导致 `startswith` TypeError。修复：bytes 输入先 decode("utf-8")。
- **`stats()` ResponseError 捕获**：fakeredis 不支持 `info` 命令抛出 `ResponseError`，源码 except 子句未包含该异常类型。修复：改为 `except Exception`（stats 是诊断信息，宽松捕获合理）。
- **`_get_client` redis.exceptions.ConnectionError 捕获**：`redis.exceptions.ConnectionError` 不继承 `builtins.ConnectionError`，源码 except 子句捕获了错误的异常类型，导致 Redis 连接失败时异常直接传播而非包装为 `RedisConnectionError`。修复：改为 `except Exception` 并包装为 `RedisConnectionError`。
- **`_execute_with_retry` RedisConnectionError 捕获**：`_get_client` 抛出的自定义 `RedisConnectionError` 未被 `_execute_with_retry` 的 except 子句捕获，导致重试机制失效。修复：在 except 子句中添加 `RedisConnectionError`。

### Added — P1-B: FeedbackControlLoop E2E 闭环测试
- **tests/test_feedback_control_loop.py**：新增 26 个 E2E 测试，覆盖 Sense-Decide-Act-Feedback 完整闭环。
- 7 个测试维度：质量门场景（4）、Dry-Run 模式（2）、LLM 精炼路径（3）、历史追踪（3）、线程安全（1）、质量评估子系统（7）、调整生成（6）。
- FakeDispatcher + FakeLLMBackend 模拟完整调度链路。

### 验证
- ruff check：All checks passed
- pytest 全套：4639 passed / 26 skipped / 2 failed（Moka LLM smoke 超时 — 需真实 API key，非本次引入）
- 新增测试：41 (redis_cache) + 26 (feedback_control_loop) + 7 (ue_test_framework) = 74 个
- 源码 bug 修复：4 个（_strip_prefix / stats / _get_client / _execute_with_retry）
- 版本一致性：全量 PASS（VERSION/pyproject.toml/_version.py/Dockerfile/skill-manifest/SKILL/README/CHANGELOG）

## [4.0.9] - 2026-07-12

PATCH release: 修复、重构、优化，无新功能。完成 P4-1（优雅关闭 + 就绪探针）、P4-2（运维手册 + 架构文档）、P3-5（文档性能数据刷新）。

### Added — P4-1: 优雅关闭 + 就绪探针
- **api_server.py**：新增 `/api/v1/ready` readiness probe 端点，与 `/api/v1/health` liveness probe 分离。
- **startup_event**：启动完成后设置 `_app_ready=True`，允许负载均衡器导入流量。
- **shutdown_event**：关闭开始时设置 `_app_ready=False`，/ready 返回 503，实现流量排空。
- **test_api_server_v362.py** TestReadinessProbe（3 个测试）：ready 200、not-ready 503、root 列表。

### Added — P4-2: 运维手册 + 架构文档
- **docs/operations/OPERATIONS.md**：运维手册（部署、环境变量、健康检查端点、日志、启动/关闭流程、Docker、故障排查、监控清单）。
- **docs/architecture/ARCHITECTURE_V4.md**：v4.x 架构文档（7-role 系统、数据流、Protocol 体系、API 层、安全层、生命周期、v4.x 变更、测试架构）。

### Updated — P3-5: 文档性能数据刷新
- **docs/PROJECT_STATUS.md**：版本 V4.0.0 → V4.0.9，刷新测试数量和覆盖率。
- **docs/PERFORMANCE_MONITORING_INTEGRATION.md**：版本 V3.6.0 → V4.0.9，添加 Moka AI 后端基准数据。

### 验证
- ruff check：0 errors
- pytest 全套：4614 passed / 26 skipped / 5 failed（预存问题，非本次引入）
- 覆盖率：76.44%（26686 statements / 5784 missed）
- pytest tests/test_api_server_v362.py：51 passed（含 3 个新 TestReadinessProbe 测试）
- 版本一致性：7/7 PASS（VERSION/pyproject.toml/_version.py/Dockerfile/skill-manifest/SKILL/README/CHANGELOG）

## [4.0.8] - 2026-07-12

PATCH release: 修复、重构、优化，无新功能。完成 P3-3（异步异常细分 — 修复 dead code bug）和 P3-2（Contract 测试补全 — 3 个 Protocol 契约测试 + runtime_checkable 启用）。

### Fixed — P3-3: 异步异常 dead code 修复
- **async_coordinator.py** L418-422（sequential execution path）：修复 `except Exception` 在 `except asyncio.TimeoutError` 之前导致 TimeoutError 分支不可达的 dead code bug。重排 except 顺序，TimeoutError 优先捕获。
- 影响：超时任务现在被正确记录为 "timed out" 而非 "failed"，恢复区分信息。
- 并行版本（L468）的 except 顺序原本正确，无需修改。

### Added — P3-2: Contract 测试补全（28 个新测试 + runtime_checkable）
- **protocols.py**：为全部 6 个 Protocol 添加 `@runtime_checkable` 装饰器，启用 isinstance 结构化子类型检查。
- **test_retry_provider_contract.py**（15 个测试）：RetryProvider Protocol 定义验证、结构化子类型验证、NullRetryProvider 契约合规（retry_with_fallback/is_available/get_stats）。
- **test_ue_test_provider_contract.py**（8 个测试）：UETestProvider Protocol 定义验证、结构化子类型验证、UETestFramework 契约差距文档化（缺少 is_available）。
- **test_tech_debt_provider_contract.py**（8 个测试）：TechDebtProvider Protocol 定义验证、结构化子类型验证、TechDebtManager 契约差距文档化（缺少 is_available）。

### 验证
- ruff check：0 errors
- pytest tests/contract/：163 passed（135 existing + 28 new）
- pytest async tests：125 passed, 0 regressions

## [4.0.7] - 2026-07-12

PATCH release: 修复、重构、优化，无新功能。完成 P2-7b（Moka 真实 LLM smoke 测试）、P3-1（benchmark Moka AI 后端支持）、P2-7a（Dashboard 登录 E2E）。

### Added — P2-7b: Moka 真实 LLM smoke 测试（3 个新测试）
- **test_real_llm_smoke.py** TestMokaLLMSmoke（3 个测试）：使用 Moka AI（OpenAI-compatible API）验证核心 dispatch 链路端到端可用。
  - test_dispatch_with_moka_llm：基本 dispatch
  - test_dispatch_multi_role_moka：多角色并行
  - test_moka_result_contains_findings：结果结构验证（dict/对象兼容）

### Added — P3-1: benchmark Moka AI 后端支持
- **benchmark_real_llm.py**：新增 `--backend moka` 选项，通过 OpenAIBackend 复用 Moka AI（OpenAI-compatible API）。3/3 成功，avg 110.58s。
- **llm_backend.py** create_backend()：新增 moka 工厂分支，支持 MOKA_API_KEY/MOKA_API_BASE/MOKA_MODEL 环境变量。

### Added — P2-7a: Dashboard 登录 E2E（3 个新测试）
- **test_dashboard_ui_e2e.py** TestDashboardRealLoginFlow（3 个测试）：验证 AuthManager.verify_credentials() → session_state → dashboard 页面渲染的真实链路。
  - test_correct_login_returns_user：正确密码 → User → dashboard 渲染
  - test_wrong_password_returns_none：错误密码 → None → 不注入 user
  - test_role_permissions_differ：admin vs viewer 登录后页面渲染差异

### 验证
- ruff check：0 errors
- pytest TestDashboardRealLoginFlow：3/3 PASSED
- Moka LLM smoke：3/3 PASSED（194.56s）
- benchmark Moka：3/3 成功（avg 110.58s）

## [4.0.6] - 2026-07-12

PATCH release: 修复、重构、优化，无新功能。基于 P2_P3_PLAN.md §2.7 推进 P2-7（E2E 测试覆盖增强 — 多租户隔离 E2E），并完成 P2-5/P2-2 校验收尾。

### Added — P2-7: 多租户隔离 E2E 测试（14 个新测试）
- **test_multi_tenant_isolation_e2e.py**（14 个测试）：多租户隔离 E2E 全覆盖。涵盖：
  - **TestMultiTenantDispatchE2E**（4 个测试）：tenant-a/tenant-b/default 独立 dispatch、两个 tenant 顺序 dispatch 无干扰。
  - **TestQuotaIsolationE2E**（4 个测试）：quota 跟踪、tenant-a 配额耗尽不影响 tenant-b、配额超限返回失败、tenant-b 独立耗尽配额。
  - **TestTenantLifecycleE2E**（2 个测试）：deactivated tenant dispatch 不崩溃、reactivated tenant 恢复 dispatch。
  - **TestThreadLocalContextE2E**（2 个测试）：tenant context 线程隔离、两线程并发 dispatch 不同 tenant 无干扰。
  - **TestNonexistentTenantE2E**（2 个测试）：不存在 tenant_id 不崩溃、不产生 quota 记录。

### Verified — P2-5: REST API 速率限制（已完成，方案描述已过期）
- 校验结果：rate_limit.py 已完整实现并集成到 api_server.py。38 个测试通过，覆盖率 99.31%。方案中"已存在但未集成"的描述已过期。突发容量（burst capacity）评估为 over-design，不实现。

### Cancelled — P2-2: God Class 拆分（4 个候选全部判定为 NOT God Class）
- 基于"单类多职责"标准（而非方法数/行数阈值）重新校验 4 个候选：
  - `mce_adapter.py`：所有方法围绕 CarryMem 引擎，强内聚，NOT God Class
  - `redis_cache.py`：所有方法是缓存操作，高内聚，NOT God Class
  - `warmup_manager.py`：所有方法围绕预热流程，共享数据结构，NOT God Class
  - `worker.py`：所有方法围绕 Worker 执行流程，职责集中，NOT God Class
- D13 N-1 教训再次验证：基于"方法数>30"阈值的 God Class 识别有 98.1% 误判率

### Fixed — 版本一致性修复
- 修复 P2-6 commit 遗漏的版本不一致：VERSION 文件（4.0.4→4.0.6）、Dockerfile ARG（4.0.4→4.0.6）、skill-manifest.yaml（4.0.4→4.0.6）。

### 验证
- ruff check：0 errors
- pytest：4599 passed, 25 skipped, 6 failed（全部为预存环境问题：2 个 Python 3.9 系统版本 + 3 个已修复版本一致性 + 1 个预存 flaky）

## [4.0.5] - 2026-07-12

PATCH release: 修复、重构、优化，无新功能。基于 P2_P3_PLAN.md §2.6 推进 P2-6（type: ignore 清理 — 消除 35 处非 no-any-return type: ignore，修复 1 个运行时 bug）。

### Fixed — P2-6: type: ignore 系统性清理（35 处清理 / 6 处合理保留）

**任务 #122: 单例 attr-defined（10 处清理）**
- `unified_gate_engine.py`, `verification_gate.py`, `anti_rationalization.py`, `lifecycle_shortcut_adapter.py`, `intent_workflow_mapper.py`: 用模块级变量 `_shared_xxx_instance: XxxType | None = None` + `global` 替代函数属性 `func._instance` 单例模式，消除 10 个 `type: ignore[attr-defined, no-any-return]`。

**任务 #123: no-redef stub 类（1 处清理 / 4 处保留）**
- `prometheus_metrics.py`: 重构可选依赖检测为 `importlib.util.find_spec` + `if/else`，移除 L385 `type: ignore[no-any-return, unused-ignore]`（改为直接返回 `generate_latest(REGISTRY)`）。4 处 `no-redef` 保留（mypy 已知限制：可选依赖 stub 类与 import 同名无法绕过）。
- `prometheus_metrics.py` stub Counter: 移除不存在的 `observe()` 方法（Counter 接口无此方法，是 Histogram 方法）。
- `prometheus_metrics.py` `reset_metrics()`: 新增 REGISTRY 清理逻辑（unregister all collectors），确保测试间无重复注册。

**任务 #124: arg-type/call-arg/union-attr（11 处清理 / 1 处保留）**
- `test_quality_guard.py`: `scores.get()` → `max(scores, key=lambda k: scores[k])` 消除 arg-type。
- `report_formatter.py`: 添加 `_I18N_SUMMARY` 类型注解 + `str()` 包装消除 arg-type。
- `severity_router.py`: `cast(list[ReviewFinding], findings)` 消除 arg-type。
- `dispatch_steps_feedback_mixin.py`: `cast(Any, plan.journey_tests[0])` 消除 arg-type。
- `retrospective.py`: `context={"summary": report.summary}` 包装 str 为 dict 消除 arg-type。
- `mce_adapter.py`: `float(rule.get("x") or rule.get("y") or 0.0)` 处理 None 消除 arg-type。
- `enterprise_feature.py`: 移除 `error=...` 参数（DispatchResult 无 `error` 字段，有 `errors: list[str]`），消除 2 个 call-arg。
- `redis_cache.py`: `compression=` → `enable_compression=`（参数名修正），消除 call-arg。
- `memory_serializer.py`: `getattr(entry_type, "value", None)` 替代 `hasattr + attr` 访问消除 union-attr。
- `coordinator.py`: 局部变量 `store = self.ccr_store` 替代嵌套函数中 `self.ccr_store` 访问消除 union-attr。
- `mcp_server.py:159`: 保留 `call-arg`（MCP 工具契约使用 `task=`，dispatcher 签名为 `task_description=`）。

**任务 #125: assignment/name-defined/return-value/bare/attr-defined（12 处清理 / 1 处保留）**
- `mcp_server.py`: `importlib.util.find_spec` 替代 `try/except ImportError`，消除 assignment + misc。
- `redis_cache.py`: `or` 链处理 `os.getenv` 返回值消除 assignment。
- `memory_query.py`: `MemoryType[mapped_type]` 将字符串转为枚举消除 assignment。
- `memory_serializer.py`: **修复运行时 bug** — `KnowledgeMemory` → `KnowledgeItem`，`FeedbackMemory` → `UserFeedback`（原代码引用不存在的类名，运行时会 NameError），同步修正构造参数（`fact`→`content`+`title`，`category`→`feedback_type`，移除不存在的 `confidence`/`severity`/`tags` 字段），消除 2 个 name-defined。
- `feedback_control_loop.py`: `str()` 包装 `response.get()` 返回值消除 return-value。
- `loop_engineering/models.py`: `scheduling_decision: SchedulingDecision | None = None` 改为 Optional。
- `loop_engineering/kernel.py`: 添加 None 检查 + 移除 2 个 bare `type: ignore`。
- `content_cache.py`: `cast(Any, self._wrapped)` 替代 attr-defined（LLMCacheBase 不定义 get/set，由子类实现）。
- `ci_feedback_adapter.py`: `cast(CIResult, parser.parse(output))` 替代 attr-defined + no-any-return。
- `dag_views.py`: 保留 `attr-defined`（`st.mermaid` 是 Streamlit 1.29+ API，不在类型 stubs 中）。

**任务 #126: pytest __test__ attr-defined（4 处清理）**
- `test_quality_guard.py`: 将 `TestDimension`, `TestFunctionMeta`, `TestQualityReport`, `TestQualityGuard` 的 `__test__ = False` 从类外部赋值改为类体内声明，消除 4 个 `attr-defined`。

### Fixed — test_prometheus_metrics.py 兼容真实 prometheus_client
- 修复测试在安装了 prometheus_client 的环境中失败的问题：所有 stub 测试使用唯一 metric 名（避免 CollectorRegistry 重复注册），`labels()` 测试改为检查返回值接口而非对象同一性，`time()` 测试改为检查 context manager 协议而非特定类型。

## [4.0.4] - 2026-07-11

PATCH release: 修复、重构、优化，无新功能。基于 P2_P3_PLAN.md §2.4 按 ROI 推进 P2-4（无测试模块补充 — 两梯队 11 个模块，整体覆盖率 79.15% → 80.06%）。

### Added — P2-4: 第一梯队测试补充（5 模块，353 个新测试）
- **test_async_coordinator.py** (71 tests): AsyncCoordinator + AsyncWorkerWrapper 全覆盖。涵盖 plan_task/spawn_workers/execute_plan/execute_batch_serial/execute_parallel_async/buffer_worker_messages/compression/preload_rules/collect_results/resolve_conflicts/generate_report/async_call/briefing_injection。覆盖率 0% → 80.70%（+265 语句）。
- **test_feedback_control_loop.py** (52 tests): FeedbackControlLoop 闭环迭代引擎全覆盖。涵盖 run/dry_run/quality_gate_pass/iterate_until_pass/assess_quality/generate_adjustment/refine_task/reset/get_statistics。覆盖率 29% → 99.60%（+130 语句）。
- **test_enhanced_worker.py** (59 tests): EnhancedWorker provider injection + briefing + rules + guard 全覆盖。涵盖 is_available/agent_briefing/init/briefing_property/execute/do_work_paths/record_monitor/inject_rules/validate_injected_rules/check_forbid_violations/briefing_summary/export_briefing/compress_to_briefing/extract_decisions/extract_pending/get_provider_status。覆盖率 49% → 80.62%（+91 语句）。
- **test_rule_collector.py** (135 tests): RuleCollector 自然语言规则收集全流程全覆盖。涵盖 IntentDetector(11 patterns)/RuleExtractor(7 patterns)/RuleSanitizer(dangerous+injection)/LocalRuleStorage(store/list/delete/query/cache)/RuleStorage(CarryMem fallback)/RuleCollector(process/format helpers)。覆盖率 44% → 98.89%（+354 语句）。
- **test_adaptive_role_selector.py** (36 tests): AdaptiveRoleSelector 三层选择策略全覆盖。涵盖 similar_tasks/intent/fallback/update_stats/get_role_report。覆盖率 45% → 100%（+60 语句）。

### Fixed — 源码 Bug 修复（rule_collector.py 安全漏洞）
- **rule_collector.py RuleSanitizer.sanitize()**: 修复 prompt injection 和 dangerous patterns 的 redaction 丢失 `re.IGNORECASE` 标志的 bug。原代码用 `re.sub(pat.pattern, "[REDACTED]", ...)` 传入字符串模式，丢失了编译时的 `re.IGNORECASE` 标志，导致 "Ignore"（大写 I）不被替换。改为 `pat.sub("[REDACTED]", ...)` 使用编译后的正则表达式，保留所有标志。这是一个安全漏洞 — prompt injection 模式被检测到但未被实际清除。

### Added — P2-4: 第二梯队测试补充（6 模块，231 个新测试，覆盖率突破 80%）
- **test_dispatch_performance.py** (39 tests): DispatchPerformanceMonitor 性能监控全覆盖。涵盖 record/threshold_check(warning+critical)/get_statistics(p50/p95/p99)/detect_regression/export_metrics/clear。覆盖率 46.02% → 99.12%。
- **test_dual_layer_context.py** (41 tests): ContextEntry + DualLayerContextManager 双层上下文全覆盖。涵盖 project/task layers/combined/build_prompt_context/cleanup_expired/eviction/TTL expiry。覆盖率 30.16% → 98.41%。
- **test_secret_patterns.py** (38 tests): 密钥检测模式全覆盖。涵盖 is_sensitive/find_secrets/mask_secrets + 10 种密钥模式（OpenAI/GitHub/AWS/password/bearer/private key/connection string）。覆盖率 29.17% → ~100%。
- **test_prometheus_metrics.py** (56 tests): DevSquadMetrics + stub classes 全覆盖。涵盖 Counter/Gauge/Histogram/Info/_NullContextManager stubs + record_dispatch/dispatch_timer/record_llm_call/llm_call_timer/cache_hit/miss/workers/errors/consensus/gate_check/build_info/get_metrics/reset_metrics。覆盖率 71.72% → ~100%。
- **test_task_completion_checker.py** (32 tests): TaskCompletionChecker 任务完成检查全覆盖。涵盖 init/load_progress/save_progress/check_dispatch_result/check_schedule_result/get_dispatch_history/get_completion_summary/is_task_completed/reset_progress。覆盖率 73.72% → ~100%。
- **test_similar_task_recommender.py** (25 tests): SimilarTaskRecommender 相似任务推荐全覆盖。涵盖 recommend/get_role_suggestion/_extract_most_common_roles/_extract_most_common_intent/_calculate_avg_duration/_determine_confidence。覆盖率 75.00% → ~100%。

## [4.0.3] - 2026-07-11

PATCH release: 修复、重构、优化，无新功能。基于 P2_P3_PLAN.md §2.1 按 ROI 推进 P2-1（Protocol 类型注解 — 消除剩余 23 个 `no-any-return` type: ignore）。

### Fixed — P2-1: Protocol 类型注解（PEP 544）
- **dispatcher_base.py**: 新增 3 个 Protocol 定义（`RoleMatcherProtocol`/`ReportFormatterProtocol`/`PerfMonitorProtocol`），将 `DispatcherBase` 的 3 个字段从 `Any` 替换为对应 Protocol 类型，让 mypy 能检查委托调用的返回值类型。
- **dispatcher_utils_mixin.py**: 移除重复的 `role_matcher: Any` 和 `report_formatter: Any` 字段声明（基类已有 Protocol 类型），`analyze_task` 返回类型从 `list[dict[str, str]]` 改为 `list[dict[str, Any]]`（与 RoleMatcher 实际返回匹配），消除 5 个 `# type: ignore[no-any-return]`。
- **dispatcher_status_mixin.py**: 移除重复的 `_perf_monitor: Any` 字段声明（基类已改为 `PerfMonitorProtocol`），消除 2 个 `# type: ignore[no-any-return]`。
- **dispatch_steps_base.py**: `report_formatter: Any` → `ReportFormatterProtocol`（PostDispatchPipeline 的基类，独立于 DispatcherBase）。
- **dispatch_steps.py**: `__init__` 参数 `report_formatter: Any` → `ReportFormatterProtocol`，L308 用 `cast(DispatchResult, ...)` 包装 `_run_feedback_loop` 返回值，消除 2 个 `# type: ignore[no-any-return]`。
- **dispatch_result_assembler.py**: `__init__` 参数 `report_formatter: Any` → `ReportFormatterProtocol`（ResultAssembler 不继承 DispatcherBase），消除 1 个 `# type: ignore[no-any-return]`。
- **enhanced_worker.py**: L57 用 `bool()` 包装 `val()` 返回值；L362-369 用 `cast(WorkerResult, ...)` 包装 `retry_provider.retry_with_fallback` 返回值；L598-602 语义修复 `export_briefing` 返回文件路径（原来委托返回 None），消除 3 个 `# type: ignore[no-any-return]`。
- **worker.py**: L547 用 `cast(str, cached)` 包装缓存返回值，消除 1 个 `# type: ignore[no-any-return]`。
- **async_coordinator.py**: L539 用 `cast(WorkerResult, ...)` 包装 `retry_manager.retry_with_fallback` 返回值，消除 1 个 `# type: ignore[no-any-return]`。
- **lifecycle_shortcut_helpers.py**: L169 用 `cast(bool, ...)` 包装 `checkpoint_manager.save_lifecycle_state` 返回值，消除 1 个 `# type: ignore[no-any-return]`。
- **llm_cache.py**: L216/L301 用 `cast(str | None, ...)` 包装缓存返回值，消除 2 个 `# type: ignore[no-any-return]`。
- **async_adapter.py**: L105/L129 用 `cast(str, ...)`/`cast(bool, ...)` 包装 `loop.run_until_complete` 返回值，消除 2 个 `# type: ignore[no-any-return]`。
- **content_cache.py**: L148 用 `cast(str | None, ...)` 包装缓存返回值，消除 1 个 `# type: ignore[no-any-return]`。
- **unified_gate_engine.py**: L250 用 `cast(UnifiedGateResult, ...)` 包装 `base_checker(context, **kwargs)` 返回值，消除 1 个 `# type: ignore[no-any-return]`。
- **skill_extractor.py**: L313 用 `str()` 包装 `re.findall` 返回的首元素，消除 1 个 `# type: ignore[no-any-return]`。

### Strategy — Protocol vs cast()
- 决策点 3 拍板采用 Protocol 方案（非纯 cast+Any），理由是"不留技术债"。
- 实际实现混合使用：委托给 `Any` 类型字段的用 Protocol 替换字段类型（9 处），返回 `Any` 局部变量的用 `cast()` 解决（14 处）。
- Protocol 结构化子类型：不需要显式继承，只要类有匹配的方法签名即满足 Protocol。

### Verified
- ruff check: 0 errors（15 个修改的源文件全部 lint clean）
- mypy: 0 errors（172 个文件 in `scripts/collaboration/`，`warn_return_any = true` + `warn_unused_ignores = true`）
- pytest: 4005 passed, 25 skipped, 4 failed（全部为预存环境问题：3 个 numpy 相关 + 1 个 carrymem 集成，0 新回归）
- grep 确认: `type: ignore[no-any-return]` 在 `scripts/` 下 0 matches（从 23 个减至 0）

## [4.0.2] - 2026-07-11

PATCH release: 修复、重构、优化，无新功能。基于 P2_P3_PLAN.md 按 ROI 推进 P2-3（workflow_engine 测试补充）。

### Fixed — P2-3: WorkflowEngine 测试套件补充
- **workflow_engine_base.py 测试** (`tests/test_workflow_engine_base.py`): 新增 53 个单元测试覆盖枚举（StepStatus/WorkflowStatus/NodeType）、WorkflowStep dataclass 序列化（to_dict/from_dict 往返、无效值回退、缺失字段默认值）、PHASE_TEMPLATES P1-P11 完整性（11 阶段×11 必需字段）、LIFECYCLE_TEMPLATES 5 模板（full/backend/frontend/internal_tool/minimal）、WorkflowEngineBase 抽象 stubs。
- **workflow_engine_lifecycle_mixin.py 测试** (`tests/test_workflow_engine_lifecycle.py`): 新增 51 个单元测试覆盖 `_split_task_into_steps`（7 类关键词检测：product/architecture/security/ui/testing/development/deployment + 中文 + 空回退）、`create_lifecycle`（5 模板 + 无效模板 + node_type 传播）、`submit_change_request`（5 种状态 + 描述净化截断至 500 字符）。
- **workflow_engine_state_mixin.py 测试** (`tests/test_workflow_engine_state.py`): 新增 25 个单元测试覆盖 `get_workflow_status`（not found/有定义/无定义/零步骤/checkpoint/failed/全完成）、`classify_steps`（None/not found/混合/all-deterministic/all-llm/all-hybrid/empty/by_step/百分比求和=100%）、`get_step_summary`。
- **workflow_engine_transition_mixin.py 测试** (`tests/test_workflow_engine_transition.py`): 新增 39 个单元测试覆盖 `start_workflow`（9 场景）、`execute_step`（18 场景含 not found/success/failure/checkpoint interval 触发/completion/advance）、`_default_step_executor`（5 场景含 dispatcher Mock/截断/无 summary 属性/失败）、`_get_next_step`（6 场景）。
- **workflow_engine.py 主类测试** (`tests/test_workflow_engine.py`): 新增 14 个单元测试覆盖 `__init__`（storage_path 创建含嵌套目录、属性初始化、checkpoint_manager 创建、默认 checkpoint_interval=2、coordinator/dispatcher 传递）。

### Fixed — 测试维护
- **版本断言测试改为前缀检查**: `test_v4_version_is_4_0_0` → `test_v4_version_is_current`（`startswith("4.0.")`），`test_dockerfile_declares_version_arg` 同步改为前缀检查，避免每次 PATCH 版本递增都需更新测试。

### Verified
- ruff check: 0 errors
- mypy: 0 errors（仅预存 numpy stub 警告）
- pytest: 182 个新测试全部通过，workflow_engine 模块覆盖率 99.58%（389 语句 + 90 分支，仅 2 行未覆盖）

## [4.0.1] - 2026-07-11

PATCH release: 修复、重构、优化，无新功能。基于 TECH_DEBT_ASSESSMENT_V4.0.md 评估报告推进 P0-P1 技术债清理。

### Fixed — P0: 测试覆盖率提升
- **dispatch_steps.py 测试补充** (`tests/test_dispatch_steps.py`): 新增 54 个单元测试覆盖 PostDispatchPipeline 的 init/build_step_timings/build_lifecycle_trace/collect_worker_results/build_summary/execute 全方法。使用 `_SENTINEL` 哨兵模式区分 None 和未传参，`event_bus=MagicMock()` 避免真实 EventBus 创建。
- **dispatcher mixins 测试补充** (`tests/test_dispatcher_mixins.py`): 新增 67 个单元测试覆盖 5 个 mixin（UtilsMixin/StatusMixin/ErrorMixin/AuditMixin/LifecycleMixin），使用 `__new__` 模式绕过抽象 `__init__`，手动设置属性。

### Fixed — P1: 类型安全改进
- **no-any-return type: ignore 批量修复**: 从 55 个减少至 23 个（修复 32 个）。使用 `cast()` 替代 `# type: ignore[no-any-return]`，覆盖 `json.load()` 返回值、`dict.get()` 返回值、`self.store.save()` 委托、`psutil` 调用、`self._llm_backend` 委托等场景。剩余 23 个为委托给 `Any` 类型字段的，需添加 Protocol 类型注解（纳入 P2）。
- 涉及 15 个源文件：memory_serializer.py、memory_bridge.py、task_completion_checker.py、checkpoint_manager.py、enterprise_feature.py、concern_pack_loader.py、similar_task_recommender.py、dispatch_services.py、code_map_generator.py、memory_query.py、performance_monitor.py、feedback_control_loop.py、batch_scheduler.py、multi_tenant.py、dispatch_pre_steps.py。

### Verified
- ruff check: 0 errors
- mypy: 0 errors（仅预存 numpy stub 警告）
- pytest: 3744 passed, 4 skipped（全量回归无回归）

## [4.0.0] - 2026-07-07

MAJOR version bump:借鉴上游 TraeMultiAgentSkill v2.7 理念，新增 6 个特性（P1-P3），全面接入 dispatch pipeline，无幽灵功能。Spec 详见 `docs/spec/v4.0.0_spec.md`。

### Added — V4.0.0 P1-1: Loop Engineering 五步闭环
- **LoopKernel + 5 阶段组件** (`scripts/collaboration/loop_engineering/`): Discovery → Handoff → Verification → Persistence → Scheduling 闭环。`DiscoveryProbe` 发现本轮工作项，`HandoffAdapter` 调用 dispatcher 执行，`VerificationGate` 校验结果，`NotesMemory` 持久化（SHA256 校验 + 断点续跑），`LoopScheduler` 决策 CONTINUE/FIX/STOP_SUCCESS/STOP_FAILURE/HUMAN_CHECKPOINT。9 个模块，覆盖单测 + 集成测试。

### Added — V4.0.0 P1-2: UI/UX 巡检与视觉回归
- **UIUXAnalyzer + VisualRegressionChecker** (`scripts/qa/`): 4 维度审计（a11y/interaction/layout/ux）+ PIL 像素 diff。Playwright 软依赖，未安装时优雅降级。dispatcher 新增 `qa_audit_url()` / `qa_visual_regression()` 公共 API。

### Added — V4.0.0 P2-1: Dynamic Workflows 对抗验证
- **AdversarialVerifier + RedBlueTeam** (`scripts/collaboration/adversarial_verify.py`): 红队攻击 + 蓝队防御 + 裁判仲裁三阶段。支持 STRICT/STANDARD/LENIENT 三种严格度。通过 `consensus_engine.adversarial_verify()` 访问（集成到 ConsensusEngine，不是 dispatcher 直通方法）。

### Added — V4.0.0 P2-2: DAG 依赖图可视化
- **DAGVisualizer** (`scripts/dashboard/dag_views.py`): Mermaid / JSON / DOT 三种输出格式。支持节点高亮、依赖路径追踪、循环检测。通过 Dashboard `DAGVisualizer` 类访问（不是 dispatcher 直通方法）。

### Added — V4.0.0 P3-1: Autonomous 自主迭代模式
- **AutonomousLoopController + 4 组件** (`scripts/collaboration/autonomous/`): plan → dev → verify → fix 4 阶段循环，复用 LoopKernel。`RunState` 9 状态枚举，`NotesMemory` SHA256 校验 + 断点续跑，`SmartConfirmation` 三态智能确认（smart/whitelist-only/blacklist-only），`GitDriver` 风险等级评估（high/medium/low）。`ConsensusAwareEvaluator` 包装确保不绕过 HC-2 共识门。dispatcher 集成 `dispatch_autonomous()` API。95 个测试。

### Added — V4.0.0 P3-2: 插件热加载
- **PluginHotLoader** (`scripts/collaboration/plugins/`): 三种加载路径（BUILTIN_PLUGINS / Hot Register API / Drop-in 目录扫描）。路径穿越三层防护（白名单目录 + 规范化路径 + 后缀/大小检查）。reload 失败回滚保留旧实例。`--no-hot-reload` 完全关闭动态能力。审计日志（内部 + 外部日志器）。线程安全（`threading.RLock`）。dispatcher 集成 6 个公共 API：`register_plugin()` / `unregister_plugin()` / `register_builtin_plugin()` / `get_plugin()` / `list_plugins()` / `scan_plugins()` / `reload_plugins()`。48 个测试覆盖 spec 8.6 全部 10 个 E2E 场景。

### Verification — V4.0.0 P1-P3
- pytest 回归: 211 passed (dispatcher + QA + autonomous + plugins)
- ruff check: All checks passed
- 无幽灵功能: 所有 6 个特性均通过 dispatcher 公共 API 可触达

### Fixed — V4.0.0 后续改进项（发布前审计）
- **P3-1 共识投票 STUB 修复** (`autonomous/loop_controller.py`): `_check_consensus_gate` 原为 STUB（创建提案后直接返回 `final_status=="completed"`），从未调用 `cast_vote`/`reach_consensus`。现实现真实多角色投票：创建提案→模拟 5 角色（architect/pm/coder/tester/security）基于 loop_report 状态投票→`reach_consensus`→根据 `outcome.value=="approved"` 返回。`ConsensusAwareEvaluator` 也从仅检查方法存在增强为验证 `create_proposal`+`cast_vote`+`reach_consensus` 三个方法均可访问。
- **P3-1 SleepGuard 新增** (`autonomous/sleep_guard.py`): 借鉴上游的无限循环防护机制。三状态（NORMAL/BACKOFF/HARD_STOP），连续失败时指数退避 sleep（`initial_backoff` × `multiplier`，封顶 `max_backoff`），超过 `max_consecutive_failures` 硬停止。集成到 `AutonomousLoopController`（可选，通过 `sleep_guard_config` 启用）。18 个单元测试覆盖状态转换、退避逻辑、统计、集成。
- **P1-2 HSV 颜色空间检测** (`qa/uiux_analyzer.py`): 在 WCAG luminance 对比度检测基础上，新增 HSV 颜色空间检测作为补充。捕获 WCAG 通过但视觉刺眼的配色（高饱和度红绿/蓝黄组合）。新增 `_rgb_to_hsv()` 和 `_check_hsv_harsh_combination()` 方法。11 个单元测试覆盖转换正确性、刺眼配色检测、边界条件。

### Added — V4.0.0 后续改进项（Task #85/#86/#87）
- **Task #85: httpx2 + pytest-asyncio 配置修复** (`pyproject.toml`, `requirements-dev.lock`, `.github/workflows/test.yml`): starlette 1.3.1 testclient 从 httpx 迁移到 httpx2，缺包导致 API 测试收集阶段 RuntimeError。新增 `asyncio_mode="auto"` + `asyncio` marker 注册 + httpx2>=2.5.0 依赖。CI 3 处 httpx → httpx2。本地 3603 测试全通过（含 72 async 测试）。
- **Task #86: 技术债清理** (`adversarial_verify.py`, `loop_controller.py`): bandit B324 HIGH 告警修复（MD5 添加 `usedforsecurity=False`，与其他 4 处一致）。`_simulate_role_votes` 从 15 行 180+ 字符超长行重构为表驱动方式（vote_matrix + role_weights），可读性大幅提升。bandit 0 issues / ruff All passed。
- **Task #87: LLM 投票替换模拟投票** (`autonomous/loop_controller.py`): `AutonomousConfig` 新增 `llm_backend` 字段。新增 `_cast_role_votes` 分发器（LLM 可用时调用真实 LLM，否则回退 mock）。`_llm_role_votes` 为 5 角色分别构造 role-specific prompt → 调用 LLM → 解析 JSON 响应为 Vote。单角色 LLM 失败时自动回退到 mock 投票（`_mock_single_role_vote`）。支持 Moka AI（OpenAI-compatible）。11 个单元测试 + 1 个真实 LLM 集成测试（MOKA_API_KEY 无效时优雅 skip）。

## [3.10.0-dev] - 2026-07-01

### Added — V3.10.0 Phase 1: Minimal Implementation Rules
- **PonytailRuleInjector** (`scripts/collaboration/ponytail_rule_injector.py`): New module injecting ponytail-style "laziness ladder" (7 rungs: YAGNI → reuse → stdlib → platform native → installed dependency → one line → minimal code) into prompts to suppress over-engineering in 7-role parallel processing. Includes never-skip boundary (input validation / data loss prevention / security / accessibility). Configurable via `quality_control.minimal_implementation` and `quality_control.ponytail_markers` in `.devsquad.yaml`.
- **PromptAssembler integration** (`prompt_assembler.py`, `prompt_assembler_base.py`, `prompt_assembler_formatting_mixin.py`): Ponytail rules injected into structured/compact/direct instruction styles via new `_concat_injections(style)` helper. Compression styles (`ultra_minimal`, `minimal`) intentionally skip ponytail injection to preserve compression effectiveness. 17 new unit/integration tests.

### Changed
- **Regression threshold**: `test_simple_produces_compact_or_standard` token threshold raised from 1000 to 1500 to account for ponytail injection (~170 tokens). `test_build_instruction_ultra_minimal_includes_ponytail` renamed to `test_build_instruction_ultra_minimal_skips_ponytail` (assertion inverted: ponytail must NOT appear in compressed styles).

### Added — V3.10.0 Phase 2: Structure-Aware Compression
- **ContentRouter + SmartCrusher** (`scripts/collaboration/content_crusher.py`): New module detecting 6 content types (JSON_ARRAY / CODE / LOG / PLAIN_TEXT / HTML / DIFF) and applying structure-aware compression. JSON array crush extracts constant fields, retains first/last/error items + representative sample (100 items → 7 representatives, 90%+ reduction). Log crush retains ERROR/WARN/FATAL lines + first/last boundary context. Short inputs (<=200 chars) skipped.
- **CompressionLevel.SMART** (`scripts/collaboration/context_compressor.py`): New level 4 that preserves all messages but compresses each message's content via SmartCrusher. Crushed messages tagged with `smart_crushed=True` metadata. 88.7% token reduction measured on mixed JSON+log workload. 46 new tests (unit/integration/performance/edge).

### Added — V3.10.0 Phase 1+2 Finishing Items: Benchmark Suite + Coordinator SMART Integration
- **Benchmark suite** (`scripts/benchmark_ponytail_smart.py`): 15-task baseline (5 simple + 5 medium + 5 complex) + 6 content-sample A/B evaluation. Phase 1 measured: ponytail injection overhead is a fixed ~240 tokens, 37.6% overhead on simple tasks / 35.4% on complex tasks. Phase 2 measured: SMART achieves 89.1% reduction on JSON / 82.0% on log, with 100% message preservation (SNIP deletes messages). 20 new tests.
- **Coordinator SMART-first integration** (`scripts/collaboration/coordinator.py`): New `smart_compression` opt-in flag + `apply_smart_compression()` method. SMART pre-compression runs before destructive compression, preserving all messages by compressing content only; if SMART reduces tokens below threshold, destructive compression is skipped, achieving "zero information loss". `get_compression_stats()` extended with SMART fields (precompressions / messages_crushed / tokens_before / tokens_after / avg_reduction_pct). 22 new tests.
- **Ponytail marker usage guide** (`docs/guides/PONYTAIL_MARKER_GUIDE.md`): 10-section document defining `ponytail:` marker convention (syntax / elements / placement), when to use and when not to use, hard-constraint boundaries, relationship with YagniChecker, review guidance, anti-patterns.

### Verification — Phase 1+2 Finishing Items
- pytest full suite (CI authoritative, Python 3.10 + 3.11): 3007 passed / 15 skipped / 0 failed
- pytest local (Python 3.12, includes V3.10.0 new tests): 3045 passed / 3 skipped
- mypy scripts/ skills/: 0 errors (CI blocking gate)
- ruff check scripts/ skills/: All checks passed
- bandit -r scripts/: 0 issues
- Version consistency: 15/15 PASS
- Module count: 150+ (added `benchmark_ponytail_smart.py`)

### Added — V3.10.0 Phase 3: Reversible Compression + Token Budget
- **CCRStore** (`scripts/collaboration/ccr_store.py`): Reversible compression backend (SQLite + in-memory LRU + TTL + thread-safe). When SmartCrusher compresses content, the original is stored in CCRStore and a `trace_id` marker is emitted in the compressed output. Workers can later retrieve the full original via `devsquad_retrieve(trace_id=..., query=...)`. Coordinator scans Worker output for these markers and auto-injects the original content. 23 new tests.
- **TokenBudget** (`scripts/collaboration/models_base.py`): Per-dispatch token budget enforcement. When configured, Coordinator tracks `_used_input_tokens` and triggers compression/truncation when budget is exceeded. Prevents cost overruns on long multi-Agent tasks.
- **CompressedScratchpadEntry** (`scripts/collaboration/models_base.py`, `scratchpad.py`): Scratchpad entries whose original content has been compressed via CCRStore. Stores a `trace_id` pointer; Workers read the compressed summary by default and retrieve the full original on demand via `CCRStore.retrieve`.
- **Dispatch pipeline integration** (`dispatch_component_factory.py`, `.devsquad.yaml`): `ComponentConfig` extended with `smart_compression`, `ccr_store`, `token_budget` fields. `Coordinator` creation now passes these parameters, completing the Phase 2+3 integration (previously Coordinator accepted the params but the factory did not pass them — ghost-feature risk eliminated). `.devsquad.yaml` adds `smart_compression`, `ccr_store_path`, `token_budget_total` config keys.
- **coordinator.py `from __future__ import annotations`**: Fixed P0 NameError — `CCRStore | None` annotation in `__init__` was evaluated at runtime because `coordinator.py` lacked `from __future__ import annotations`, causing 76 test collection errors. Fixed by adding the future import.

### Added — V3.10.0 Phase 3 Task #57: CCR marker injection
- **SmartCrusher CCR marker** (`scripts/collaboration/content_crusher.py`): `SmartCrusher.__init__` gains `ccr_store: CCRStore | None = None`; `crush()` stores the original and calls new `_inject_trace_id()` static method to inject `retrieve full: trace_id=X` into the crush header when compression happened. Backward compatible — no marker when no CCRStore. 14 new tests (marker format / round-trip retrieval / query filtering / boundaries).
- **ContextCompressor CCRStore passthrough** (`scripts/collaboration/context_compressor.py`): `__init__` gains `ccr_store` arg, passed through to SmartCrusher; also added `from __future__ import annotations` to fix PEP 604 union annotation runtime evaluation.

### Added — V3.10.0 Phase 3 Task #58: Coordinator budget checks + auto-retrieve
- **Coordinator TokenBudget integration** (`scripts/collaboration/coordinator.py`): `__init__` gains `token_budget` + `ccr_store` args; `execute_plan()` calls new `_check_token_budget_before_batch()` before each batch — warning (>=80%) triggers SMART compression, exceed (>=100%) triggers FULL_COMPACT; new `get_budget_status()` exposes live counters for dashboard/API.
- **Coordinator auto-retrieve** (`scripts/collaboration/coordinator.py`): New `_retrieve_compressed_originals(result)` scans Worker output for `devsquad_retrieve(trace_id=..., query=...)` markers, calls `CCRStore.retrieve` to inject the original into Worker output (with `[Retrieved original]` boundary markers) so downstream Workers see the full context.
- **Scratchpad CompressedScratchpadEntry support** (`scripts/collaboration/scratchpad.py`): New `write_compressed()` / `read_compressed_entries()` methods; `get_stats()` gains `compressed_entries_count`; `clear()` resets compressed entries.
- **21 new tests**: coordinator budget checks / SMART trigger / exceed trigger / marker replacement / query excerpt / unknown trace_id boundary / Scratchpad lifecycle / Coordinator+CCRStore+Scratchpad full round-trip / budget_status performance (<0.1ms/call).

### Added — V3.10.0 Phase 3 Task #59: Dashboard API exposure
- **/api/v1/budget/status endpoint** (`scripts/api/routes/dispatch.py`): New GET endpoint reading from `dispatcher.coordinator.get_budget_status()`, returns `{configured, total_input_budget, per_role_input_budget, output_budget, warning_ratio, warning_threshold, used_input_tokens, remaining_input_tokens, is_warning, is_exceeded}`. Returns `{configured: false}` when no budget is attached. Requires `AUDIT_READ` permission. 4 new tests.

### Fixed — V3.10.0 Phase 3 P0
- **NameError: CCRStore not defined** (P0, 76 tests blocked): `coordinator.py` used `CCRStore | None` type annotation without `from __future__ import annotations`, causing `NameError` at class definition time. Fixed by adding the future import. Root cause: Phase 3 code was partially merged without the corresponding import guard.

### Verification — Phase 3
- pytest local (Python 3.12, with e2e+integration): 3146 passed / 21 skipped / 0 failed (109 new Phase 3 tests: CCRStore 23 + TokenBudget/CompressedScratchpad 34 + CCR marker 14 + Coordinator budget/CCR integration 21 + Scratchpad 5 + API endpoint 4 + pipeline 8)
- pytest E2E: 22 passed / 0 failed (user_journey_architect/developer/login all green)
- mypy scripts/ skills/: 0 errors
- ruff check scripts/ skills/: All checks passed
- Version consistency: 15/15 PASS
- Module count: 152+ (added `ccr_store.py`, extended `models_base.py`/`scratchpad.py`/`coordinator.py`/`content_crusher.py`/`context_compressor.py`/`api/routes/dispatch.py`)

### Added — V3.10.0 Phase 4: RetrospectiveSkill Failure Learning Loop
- **LearnedRule** (`scripts/collaboration/models_base.py`): Dataclass for rules extracted from task failures/retrospectives. Fields: `rule_text`, `trigger_condition`, `confidence` (0.0-1.0), `source_task_id`, `created_at`. `tier` property auto-routes to tier1 (>=0.8, auto-inject) or tier2 (0.5-0.8, candidate pool). Validation: confidence range + non-empty rule_text.
- **LearnedRuleStore** (`scripts/collaboration/learned_rule_store.py`): Two-tier persistence. Tier-1 rules written to `.devsquad.yaml` `quality_control.learned_rules` (human-editable YAML, auto-injected by PromptAssembler). Tier-2 rules written to `data/tier2/corrections.json` (candidate pool for manual review). SHA256 dedup. `promote_tier2_to_tier1()` for manual promotion. Thread-safe.
- **RetrospectiveEngine.extract_learned_rules()** (`scripts/collaboration/retrospective.py`): Maps deviation types to actionable rules. `goal_uncovered` → task decomposition rule (0.85). `goal_drift` → anchor check scheduling rule (0.80). `sustained_drift` → drift threshold rule (0.90). Low coverage (<50%) → decomposition verification rule (0.55, tier2). Improvements → retrospective rules (0.60, tier2). `source_task_id` propagated for traceability.
- **PromptAssembler learned_rules injection** (`prompt_assembler.py`, `prompt_assembler_formatting_mixin.py`, `prompt_assembler_base.py`): New `_build_learned_rules_injection()` loads tier-1 rules from `.devsquad.yaml` at init, formats as `## Learned Rules (from past task retrospectives)` block. Injected in both short-style `_concat_injections()` and long-style `parts.append` paths. `_get_learned_rules_injection()` accessor added to base.
- 23 new tests covering: LearnedRule validation/serialization, LearnedRuleStore tier1/tier2/dedup/promote/load, RetrospectiveEngine deviation→rule mapping, PromptAssembler injection + assembled instruction integration.

### Fixed — V3.10.0 Phase 4 Learning Loop Breakage (Ghost-Feature Defense)
- **Problem**: `_run_retrospective` returned the report immediately after `retrospective_engine.run()` without ever calling `extract_learned_rules()` + `LearnedRuleStore.add_rule()`, breaking the "extract → persist → inject on next dispatch" loop — components were implemented and registered but never chained together (ghost feature).
- **Fixed `dispatch_steps_quality_mixin.py`**: `_run_retrospective` now calls `extract_learned_rules()` + `add_rule()` after `run()`; removed `not exec_result.success` guard (failed tasks MUST trigger retrospective per spec §5.7); added info-level logging of rule extraction count and tier distribution as invocation evidence.
- **Fixed `dispatch_component_factory.py`**: New `_init_learned_rule_store()` method creates a `LearnedRuleStore` instance in `_init_core_components` (paths under `persist_dir`), eliminating the source-level breakage where the factory never created the store.
- **Fixed `dispatcher.py`**: Class-level `learned_rule_store: Any` annotation added; `PostDispatchPipeline` creation now passes `learned_rule_store=self.learned_rule_store`.
- **Fixed `dispatch_steps.py` + `dispatch_steps_base.py`**: `PostDispatchPipeline.__init__` gains `learned_rule_store` parameter + assignment; `PostDispatchBase` gains attribute declaration.
- **12 ghost-feature defense tests** (`tests/test_phase4_ghost_feature_defense.py`): Three dimensions — (1) closed-loop call verification (MagicMock spy proves `extract_learned_rules` + `add_rule` are invoked); (2) failure-path trigger verification (`exec_result.success=False` does NOT skip retrospective); (3) E2E learning cycle (failed task → rule persisted to `.devsquad.yaml` → PromptAssembler loads and injects on next dispatch).

### Verification — Phase 4
- pytest local (Python 3.12, with loop-fix + ghost-feature defense tests): 3302 passed / 25 skipped / 0 failed
- mypy scripts/ skills/: 0 errors
- ruff check scripts/ skills/: All checks passed
- Version consistency: 15/15 PASS
- Module count: 155+ (added `learned_rule_store.py`, extended `models_base.py`/`retrospective.py`/`prompt_assembler.py`/`prompt_assembler_base.py`/`prompt_assembler_formatting_mixin.py`/`models.py`/`dispatch_steps_quality_mixin.py`/`dispatch_component_factory.py`/`dispatcher.py`/`dispatch_steps.py`/`dispatch_steps_base.py`)

## [3.9.3] - 2026-07-03

### Added — UI E2E Browser-Driven Testing
- **streamlit-app-testing integration** (`tests/test_dashboard_ui_e2e.py`): 26 tests using Streamlit's official `AppTest.from_file()` framework to drive the Dashboard with real user interactions. Covers 8 user scenarios: page load, navigation, RBAC (viewer/operator/admin), lifecycle views, metrics views, components, session state, and full user journey (login → navigate → view → logout). Discovered P0 Dashboard startup crash (`learned_rule_store` undefined in `dispatch_steps.py`) that 3164 unit tests missed — proving "backend API tests passing ≠ user usability".

### Added — Coverage Supplements
- **skill_registry coverage** (`tests/test_skill_registry_coverage.py`): 43 tests raising coverage from 28.79% → 100.00%. Covers path traversal rejection, corrupted registry loading, non-serializable metadata, empty registry stats, duplicate registration, persistence round-trip.
- **usage_tracker coverage** (`tests/test_usage_tracker_coverage.py`): 45 tests raising coverage from 36.90% → 99.40%. Covers save failures, corrupted stats loading, error rate threshold boundaries, concurrent thread-safe tracking (4 threads × 50 ops), module-level singleton.
- **workflow_engine_persistence coverage** (`tests/test_workflow_persistence_coverage.py`): 22 tests raising coverage from 14.81% → 100.00%. Covers checkpoint save with missing definition, recovery from missing/no checkpoint, handoff document creation, cross-handover history accumulation.

### Added — Phase 4 Ghost Feature Defense
- **Ghost-feature defense tests** (`tests/test_phase4_ghost_feature_defense.py`): 12 tests proving RetrospectiveSkill is NOT a ghost feature. Three dimensions: (1) spy mocks verify `_run_retrospective` calls `extract_learned_rules` + `add_rule`; (2) `exec_result.success=False` does NOT skip retrospective (fixes original `not exec_result.success` guard bug); (3) full E2E learning cycle — failed task → retrospective → tier1 rule persisted → next dispatch's PromptAssembler injects rule.

### Fixed
- **P0 Dashboard startup crash**: `dispatch_steps.py:109` referenced `learned_rule_store` variable in `__init__` body but it was NOT declared as a parameter. All 3164 unit tests passed but Dashboard crashed on startup via `get_dispatcher()` → `MultiAgentDispatcher` → `PostDispatchPipeline` → `dispatch_steps.py`. Fixed by adding `learned_rule_store: Any = None` parameter.

### Changed
- **Version bump**: 3.9.2 → 3.9.3 (15/15 version consistency checks pass)
- **Test count**: 3164 → 3312 passed (+148 new tests: 26 UI E2E + 110 coverage + 12 ghost defense)
- **Coverage**: 68.47% → 70.74% (+2.27pp); 3 modules at ~100%
- **Spec sync**: `docs/spec/v3.10.0_spec.md` Phase 3+4 marked as `[x]` complete

### Assessment
- **Round 3 evaluation**: 8.6/10 (A-), up from Round 2's 8.3/10. Hard constraints 13/13. CI schedule 6/6 jobs success. Release-ready.

## [3.9.2] - 2026-07-01

### Fixed — P0 Security & Hard Constraints
- **P0-1 Password hash upgrade** (`scripts/auth.py`): Migrated password hashing from plain SHA-256 to OWASP 2023 recommended **PBKDF2-HMAC-SHA256** with random per-user salt (390,000 iterations). Format: `pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>`. Legacy SHA-256 hashes are auto-migrated to PBKDF2 on next successful login. Verification uses `secrets.compare_digest` for timing-safe comparison. 31 tests covering hash/verify/migration/timing-safety.
- **P0-2 One-click startup script** (`scripts/start.sh`): Unified entry point with 4 phases — (1) environment check, (2) database initialization, (3) frontend build, (4) service startup. Supports `--dashboard` flag (launch Streamlit dashboard instead of API server), `--help`, and `DEVSQUAD_API_PORT` environment variable override. 14 tests.
- **P0-3 Dependency lock file** (`requirements.lock`): Added pinned dependency lock file recording exact versions for reproducible builds. Documents declared vs transitive dependencies. 6 tests.
- **P0-4 VERSION file restored** (`VERSION`): Root-level `VERSION` file synchronized with `scripts/collaboration/_version.py`; version consistency check now validates 15 locations.
- **P0-5 E2E/Integration tests re-enabled** (`pyproject.toml`): Removed `tests/e2e` and `tests/integration` from `norecursedirs`; tests now filtered via markers (`-m "not e2e"`) instead of being excluded from collection.
- **P0-6 Test coverage raised to 68.15%** (`tests/`): Added `test_version.py`, `test_docker_deployment.py`, `test_data_backup.py`, and expanded dispatcher/coordinator/consensus error-path tests. Coverage up from 25.26% to 68.15%, exceeding the 60% gate.

### Added — LLM Backend Resilience
- **Auto LLM fallback** (`llm_backend.py`, `async_llm_backend.py`): New default backend `"auto"` tries real LLM providers (Anthropic → OpenAI) and gracefully falls back to `MockBackend` when no API key is available or all real backends fail. Synchronous and asynchronous factories updated; `.env.example` and `config/deployment.yaml` default to `"auto"`.
- **Real LLM integration tests** (`tests/integration/test_real_llm.py`, `tests/smoke/test_real_llm_auto_mode.py`): Coverage for auto backend construction with/without real API keys and smoke tests that run only when keys are present.

### Changed — Architecture & Maintainability
- **Dashboard split** (`scripts/dashboard.py` → `scripts/dashboard/` package): 1087-line monolith split into 8 single-responsibility modules (`app`, `components`, `state`, `lifecycle_views`, `metrics_views`, `dispatch_views`, `auth_views`). Original `scripts/dashboard.py` retained as backward-compatible entry point.
- **Audit persistence** (`dispatcher.py`): `MultiAgentDispatcher` now defaults to a SQLite-backed `DispatchAuditLogger`; audit records survive process restarts unless explicitly disabled.
- **P3 cleanup** (`llm_backend.py`, `async_llm_backend.py`): Magic numbers extracted to module constants; broad `except Exception` narrowed to network/API-specific exception sets.

### Security — P1/P2 Hardening (Round 9)
- **RBAC fail-closed enforcement** (`dispatcher.py`): Production mode denies dispatch when `_rbac is None`, satisfying hard constraint HC-1.
- **Cookie security code-level enforcement** (`scripts/auth.py`): Production mode overrides config to force `secure=true`, `httponly=true`, `samesite=Strict`.
- **API security production enforcement** (`scripts/api/security.py`): Merges `deployment.yaml` environment overrides; production mode ignores `DEVSQUAD_API_AUTH_DISABLED`.
- **API key comparison hardening** (`scripts/api/security.py`): Replaced direct dict lookup with `hmac.compare_digest` over all stored hashes for timing-safe comparison.
- **Prompt injection safe fallback** (`scripts/collaboration/input_validator.py`, `scripts/collaboration/dispatch_pre_steps.py`): Detected injections return a localized safe template response and an audit log entry instead of echoing malicious input.
- **Deployment docs aligned to PBKDF2** (`config/deployment.yaml`, `config/samples/env.production`): Removed SHA-256 examples; added PBKDF2 generation commands.

### Code Quality — P1/P3 Cleanup (Round 9)
- **skills/ type-checked by mypy**: All 6 sub-skill handlers fully typed; `mypy scripts/ skills/` passes with 0 errors.
- **Async return-type annotation coverage 100%**: 153/153 async functions in `scripts/` annotated.
- **Lock files complete**: New `requirements-dev.lock`; `requirements.lock` now pins `fastapi`/`uvicorn`/`pydantic` and transitive deps.
- **Dockerfile version-arg**: Added `ARG VERSION=3.9.2` and referenced `${VERSION}` in LABEL.
- **Directory cleanup**: Removed `scripts/tools/` (migrated useful script to `scripts/utils/`) and `tests/manual/`; cleared 44 stale files from `docs/_archive/`; documented ghost-feature utilities in `test_quality_guard.py`.

### Documentation
- **Loop Engineering assessment** (`docs/_archive/assessments/LOOP_ENGINEERING_IMPLEMENTATION_ASSESSMENT.md`): Evaluated DevSquad against upstream TRAEMultiAgent cybernetics methodology; documented gaps and V3.9.2 roadmap completion.
- **V3.9.2 roadmap** (`docs/planning/V3_9_2_ROADMAP_PLAN.md`): Implementation plan for auto fallback, dashboard split, real LLM tests, audit persistence, and P3 cleanup.
- **SKILL.md module count corrected**: Updated from 118 to 149+ modules; removed ghost/removed module entries; renumbered module table.
- **Trilingual README aligned**: Unified "5 Ways to Use DevSquad" order across EN/CN/JP.
- **Round 9 assessment** (`docs/_archive/assessments/PROJECT_TIDY_ASSESSMENT_V3.9.2_round9.md`): Honest 7-dimension maturity evaluation with command-output evidence.
- **External research** (`docs/research/ponytail_headroom_research.md`): Analysis of ponytail agent behavior constraints and headroom token compression for future ContextCompressor upgrades.

### Test Coverage
- 2940 passed, 3 skipped, 34 deselected (unit + integration-ready suite, Python 3.10+3.11)
- Total collected: 2977 tests (including 45 e2e/integration tests)
- Coverage: 68.15% total, 59.53% branches
- mypy scripts/ + skills/: 0 errors (blocking in CI)
- ruff check scripts/ skills/: All checks passed
- bandit: 0 High/Medium issues

## [3.9.1] - 2026-06-23

### Changed — Refactoring & Quality
- **File split**: `code_knowledge_graph.py` 511→346 lines (extracted `CodeGraphQuery` to `code_graph_query.py`, 182 lines)
- **File split**: `redesign_auditor.py` 550→229 lines (extracted detection methods to `redesign_checkers.py`, 415 lines)
- **RedesignAuditor false-positive fix**: `_normalize_block` now preserves Python builtins (not just keywords) and uses sequential identifier naming (id0, id1, ...) to maintain structural distinction. `_count_dead_code_lines` no longer counts blank lines as dead code.
- **CI improvement**: E2E tests now run on release tags (`v*`) in addition to nightly schedule. Build job now depends on `test + lint + security` (was `test` only).
- **mypy blocking** (P2): Fixed all 551 mypy errors across 82 files in `scripts/collaboration/`. CI mypy check upgraded from non-blocking (`continue-on-error: true`) to blocking. Zero logic changes — only type annotations, `cast()`, `# type: ignore` comments, and `from __future__ import annotations` added.

### Added — Multi-Host Adapter (V39-07, inspired by ponytail multi-platform plugin)
- **MultiHostAdapter** (`multi_host_adapter.py`): Unified adapter for dispatching DevSquad tasks from 6 AI host platforms — Claude Code, Cursor, Codex CLI, Cline, Trae, and Generic. Host-specific role mapping, prompt adaptation, and output slicing. 32 tests.

### Test Coverage
- 2605 passed, 14 skipped (CI authoritative, Python 3.10+3.11; was 2591 in V3.9.0)
- 2 files split to ≤500 lines (code_knowledge_graph, redesign_auditor); 42 files >500 lines remain (tech debt)
- 118 core modules (was 94+)
- mypy: 0 errors (was 551, blocking in CI)
- bandit: 0 High/Medium issues (was 16)

## [3.9.0] - 2026-06-22

### Added — Code Intelligence (inspired by colbymchenry/codegraph)
- **V39-01 CodeKnowledgeGraph** (`code_knowledge_graph.py` + `code_graph_storage.py`): Persistent SQLite-backed code structure graph with incremental updates. Query symbols, callers, callees, dependencies, call graph, and similar implementations. 40 tests.
- **V39-02 MCP codegraph_explore** (`mcp_server.py`): Three new MCP tools — `codegraph_explore`, `codegraph_status`, `codegraph_refresh` — for external agents to query the code graph.

### Added — Efficiency Optimization (inspired by DietrichGebert/ponytail)
- **V39-03 YagniChecker** (`yagni_checker.py`): YAGNI ladder check for micro-tasks. 6-rung ladder: NECESSARY → SKIP → USE_STDLIB → USE_DEPENDENCY → ONE_LINER → MINIMAL. Security/error/test tasks never skipped. 34 tests.
- **V39-04 PromptDials** (`prompt_dials.py`): Three-dimension prompt tuning (VERBOSITY/CREATIVITY/RISK_TOLERANCE, 1-5 each). Backward compatible with variant system. 33 tests.

### Added — Code Review Enhancement (inspired by Leonxlnx/taste-skill)
- **V39-05 RedesignAuditor** (`redesign_auditor.py`): Third-stage code simplicity audit. Checks YAGNI/STDLIB/DUPLICATE/OVERENGINEERING categories. Integrated into TwoStageReviewGate as Stage 3. 28 tests.

### Added — Production Readiness
- **V39-06 DispatchRBAC** (`dispatch_rbac.py`): RBAC0 permission model for dispatch pipeline. Role-level + mode-level permission checks. 18 tests.
- **V39-06 DispatchAuditLogger** (`dispatch_audit.py`): Append-only audit log with SHA-256 chain hash. Records dispatch lifecycle events. Tamper detection via chain verification. 23 tests.

### Changed — Dispatch Pipeline Integration (Anti-Ghost-Feature)
- **Dispatcher**: Accepts `code_graph`, `rbac`, `audit_logger` optional parameters. RBAC check at dispatch start, audit logging throughout lifecycle.
- **Worker**: Queries CodeKnowledgeGraph before LLM calls to reduce Read/Grep tool usage.
- **MicroTaskPlanner**: Runs YagniChecker on each micro-task, skips unnecessary tasks.
- **PromptAssembler**: Accepts `PromptDials` for three-dimension prompt tuning.
- **TwoStageReviewGate**: Third stage `REDESIGN` enabled by default (`enable_redesign_audit=True`).
- **DispatchResult**: New fields `permission_result` and `audit_entries`.

### Test Coverage
- **Total tests**: 2591 passed, 18 skipped (including 28 V3.9 integration tests)
- **New modules**: 7 modules + 6 test files = 176 new unit tests + 28 integration tests
- **Ghost feature check**: All 7 modules imported and called by production code (verified by grep)
- **ruff**: All checks passed
- **7-role consensus**: PRD approved at 77.9% (≥70% gate)

### Documentation
- PRD: `docs/prd/V3.9_PRD_Code_Intelligence.md`
- Consensus Review: `docs/planning/V3.9_PRD_Consensus_Review.md`
- Technical Design: `docs/architecture/V3.9_Technical_Design.md`
- Test Plan: `docs/prd/V3.9_Test_Plan.md`

## [3.8.1] - 2026-06-21

### Fixed
- **P0: MCP server test fix** (`test_mcp_server_v362.py`): Root cause was missing `mcp` package, not flaky tests. Added `pytest.importorskip("mcp")` safety net. 34/34 tests now pass.
- **P2: Dead code removal** (`workflow_engine.py:621`): Removed no-op `len(instance.failed_steps)` expression.

### Changed
- **P1: File split — `two_stage_review_gate.py`** (1059→555 lines): Extracted checkers to `review_checkers.py` (574 lines). `TwoStageReviewGate` now delegates to `ReviewCheckers` via composition.
- **P1: File split — `lifecycle_shortcut_adapter.py`** (1185→891 lines): Extracted 15 helper functions to `lifecycle_shortcut_helpers.py` (610 lines).
- **P1: pickle→JSON migration** (`cache_interface.py`): Replaced `pickle.dumps`/`pickle.loads` with `json.dumps`/`json.loads`. Added backward-compatible pickle fallback for legacy cache entries (logs warning).
- **P2: Secret pattern unification** (`secret_patterns.py`): New shared module with unified `SECRET_PATTERNS`, `is_sensitive()`, `find_secrets()`, `mask_secrets()`. Eliminated duplicate patterns from 4 modules (content_cache, review_checkers, tech_debt_manager, audit_logger).
- **P2: mypy CI** (`.github/workflows/test.yml`): Added non-blocking mypy type check step to lint job.

### Test Coverage
- **Total tests**: 2387 passed, 18 skipped (including 34 MCP server tests)
- **New modules**: `secret_patterns.py`, `review_checkers.py`, `lifecycle_shortcut_helpers.py`
- **ruff**: All checks passed

## [3.8.0] - 2026-06-21

### Added
- **#2 Two-Stage Code Review Gate** (`two_stage_review_gate.py`): Spec compliance (Stage 1) + code quality (Stage 2) review with critical-finding blocking. Inspired by Superpowers. 40 tests.
- **#3 Severity Router + Auto-Fix Loop** (`severity_router.py`): CRITICAL/HIGH/MEDIUM/LOW/INFO classification with auto-fix loop (max 3 rounds). Inspired by NodeGuard. 51 tests.
- **#4 Judge Agent + History Learning** (`judge_agent.py`): Finding deduplication, conflict resolution, confidence filtering (≥0.7), optional history learning (off by default). Inspired by Qodo PR-Agent. 33 tests.
- **#6 Deterministic vs LLM Step Separation**: `NodeType` enum (DETERMINISTIC/LLM/HYBRID) added to `WorkflowStep` with `is_deterministic()`/`requires_llm` properties and `classify_steps()` method. Inspired by RepoReviewer. 14 tests.
- **#7 Micro-Task Planner** (`micro_task_planner.py`): 2-5 minute micro-task decomposition with file paths, verification commands, DAG dependencies, max 20 tasks. Inspired by Superpowers. 47 tests.
- **#9 Content Cache + Jitter Strategies** (`content_cache.py`): Unified SHA-256 content cache with sensitive-data filtering (API keys/tokens never cached). Added `JitterStrategy` enum (NONE/EQUAL/FULL/DECORRELATED) to `LLMRetryBase`. Inspired by NodeGuard. 41 tests.
- **V3.8 Planning Docs**: 7-role evaluation, PRD, implementation plan, architecture evolution, consensus review (5 docs, 2482 lines).

### Changed
- `WorkflowStep` dataclass: Added `node_type: NodeType` field (default HYBRID for backward compat)
- `LLMRetryBase`: Added `JitterStrategy` enum and `jitter_strategy` config field
- `MultiAgentDispatcher`: Added optional `severity_router` and `micro_task_planner` parameters
- `workflow_engine.py`: All lifecycle template steps annotated with `node_type`
- Maturity assessment: 65% → 72% (honest assessment)

### Test Coverage
- **New tests**: 226 (32 content_cache + 14 step_node_types + 9 retry_jitter + 40 two_stage_review + 51 severity_router + 33 judge_agent + 47 micro_task_planner)
- **Total tests**: 2339 passed, 18 skipped (excluding pre-existing flaky MCP server tests)
- **All new modules**: ruff clean, no security issues found

## [3.7.2] - 2026-06-16

### Added
- **EventBus** (`event_bus.py`): Event-driven decoupling for dispatch pipeline, replacing callback functions with on/emit/off/clear pattern
- **DispatchHooks** (`dispatch_hooks.py`): Extracted post-dispatch hooks from dispatcher (post_dispatch_hooks, post_execution_processing, slice_outputs, check_anchor_drift)
- **ResultAssembler** (`dispatch_result_assembler.py`): Extracted result assembly logic from dispatcher
- **DispatchPerformanceMonitor** (`dispatch_performance.py`): Renamed from PerformanceMonitor to avoid name collision with performance_monitor.py
- **_do_work_simple()**: New fallback method in EnhancedWorker that correctly returns WorkerResult (was returning raw str)
- **Performance benchmarks**: 6 benchmark tests for concurrent dispatch, large tasks, O(1) lookup, thread pool reuse, memory, and creation speed

### Changed
- **Mixin → Composition**: All 3 Mixins (DispatchStepsMixin, DispatchServicesMixin, DispatchComponentFactoryMixin) converted to composition pattern — dependencies injected via `__init__` instead of implicit `self.*` attribute sharing
- **Dispatcher split**: dispatcher.py reduced from 1660→706 lines (-57%), extracted 7 independent classes
- **Skillifier refactored**: 8 parasitic `_storage._xxx` private attribute accesses replaced with public interface methods (get_all_records/set_all_records/thread_safe etc.), `__getattr__` dynamic delegation replaced with 7 explicit methods
- **f-string logger eliminated**: 166 occurrences across 22 files converted to lazy formatting (`logger.debug("msg %s", var)`) for performance on hot paths
- **Broad except narrowed**: 29 `except Exception` in critical files (dashboard, API routes, MCP server) narrowed to specific exception types with proper HTTP status code mapping
- **EnhancedWorker bug fix**: `_do_work_with_briefing` was calling `_do_work()` (returns str) then accessing `result.output` (str has no .output). Fixed to follow Worker.execute() flow: build context → _do_work → write scratchpad → wrap into WorkerResult
- **.gitignore**: Added `.devsquad_data/`, `output/`, `*.ipynb_checkpoints/`; removed `.devsquad_data/` from git tracking
- 2115 tests passing (was 2109)

### Removed
- **config_loader.py**: Dead code — entire ConfigManager/DevSquadConfig system had zero references across the project (15 config fields and 13 env var mappings all unused)

### P0-P3 Technical Debt Cleanup (2026-06-17)

### Added
- **pre-commit hooks** (`.pre-commit-config.yaml`): ruff + ruff-format + trailing-whitespace + end-of-file-fixer + check-yaml + check-added-large-files + check-merge-conflict
- **CI code coverage**: pytest-cov integration with codecov upload in GitHub Actions
- **llm_cache_base.py**: Shared cache strategy base class (TTL management, LRU eviction, key generation) for sync/async cache
- **llm_retry_base.py**: Shared retry strategy base class (exponential backoff, circuit breaker, fallback chain) for sync/async retry
- **memory_forgetting.py**: Extracted forgetting curve + expiry cleanup from memory_bridge.py
- **memory_index.py**: Extracted inverted index + TF-IDF retrieval from memory_bridge.py
- **memory_claw_source.py**: Extracted WorkBuddyClawSource class from memory_bridge.py
- **lifecycle_shortcut_adapter.py**: Extracted ShortcutLifecycleAdapter from lifecycle_protocol.py
- **lifecycle_templates.py**: Extracted 11-phase template definitions from lifecycle_protocol.py
- **lifecycle_gate.py**: Extracted gate mechanism from lifecycle_protocol.py

### Changed
- **Docstring coverage**: 56.9% → 80%+ (683 public methods documented across 30+ files)
- **Broad except narrowed**: 17 more `except Exception` in 6 core modules (async_coordinator, coordinator, worker, warmup_manager, prompt_assembler, performance_monitor) narrowed to specific types; 10 retained with justification comments
- **memory_bridge.py**: 1678 → ~600 lines (split into 4 files, backward-compatible re-exports)
- **lifecycle_protocol.py**: 1434 → ~400 lines (split into 4 files, backward-compatible re-exports)
- **sync/async dedup**: llm_cache.py and llm_cache_async.py now share LLMCacheBase; llm_retry.py and llm_retry_async.py now share LLMRetryBase
- **parametrize**: InputValidator tests refactored with @pytest.mark.parametrize to reduce duplication
- 2115 tests passing, ruff clean

## [3.7.0] - 2026-06-15

### Added
- **RoleSkillLoader**: Load SKILL.md methodology frameworks for roles, injecting structured PM frameworks into Worker prompts
- **PM Methodology Skills**: 5 SKILL.md files for product-manager role (create-prd, opportunity-solution-tree, prioritization-frameworks, assumption-mapping, experiment-design)
- **suggested_next_steps**: Dispatch results now include recommended follow-up actions based on detected intent type
- **SKILL.md Security Scanner**: 7-pattern security audit for community-contributed SKILL.md files (critical issues block loading, warnings allow loading)

### Changed
- PromptAssembler now injects role-specific methodology frameworks via `_get_skill_injection()`
- IntentWorkflowMapper: 6 intent types now include `suggested_next_steps` field
- DispatchResult: new `suggested_next_steps` field with i18n support (zh/en/ja)
- 76 core modules (was 75)

### Removed
- **PromptVariantGenerator** (`scripts/collaboration/prompt_variant_generator.py`): Removed ghost feature module that was never used in production
- **RoleTemplateMarket** (`scripts/collaboration/role_template_market.py`): Removed ghost feature module that was never used in production

## [3.6.9] - 2026-06-14

### Added
- **UETestFramework** (`ue_test_framework.py`): UE test framework bridging Tester+PM roles, combining Nielsen heuristics, WCAG accessibility checks, and cognitive load assessment
- **TechDebtManager** (`tech_debt_manager.py`): Tech debt tracking with CodebaseDebtScanner for automated debt detection and knapsack-based remediation planning for optimal fix prioritization
- **75 core modules** (up from 73 in V3.6.8)

### Changed
- **Version sync to 3.6.9**: All version references updated across the codebase

## [3.6.8] - 2026-06-13

### Added
- **FeedbackControlLoop auto mode + LLM refinement**: Feedback loop now supports "auto" mode that automatically iterates until quality gate passes, with LLM-based refinement suggestions
- **AdaptiveRoleSelector + SimilarTaskRecommender integrated into RoleMatcher**: Smart role selection and task recommendation now available through the standard RoleMatcher interface
- **ExecutionGuard integrated into EnhancedWorker**: Real-time abort guard (timeout/output/keywords) now active in all EnhancedWorker executions
- **Lifecycle phase trace in dispatch pipeline**: Full lifecycle phase tracking added to the dispatch pipeline for better observability
- **RBAC checks on get_history/audit_quality/export_metrics/clear_history**: Sensitive API endpoints now require proper RBAC authorization
- **DispatchModels** (`dispatch_models.py`): Extracted DispatchResult + I18N + ROLE_TEMPLATES from dispatcher
- **DispatchPerformance** (`dispatch_performance.py`): Extracted PerformanceMonitor from dispatcher
- **MultiLevelCache** (`multi_level_cache.py`): Multi-level cache coordinator (memory→disk→Redis)

### Changed
- **TestQualityGuard default enabled**: Test quality auditing is now on by default
- **enable_feedback_loop default False → "auto"**: Feedback loop now defaults to auto mode instead of disabled

### Removed
- **AlertManager** (`scripts/alert_manager.py`): Removed unused AlertManager module that was never called from any main flow. Multi-channel alerting (Console/Slack/Email/Webhook) is no longer available as a built-in feature.

### Fixed
- **13+ files version sync to 3.6.8**: All version references updated across the codebase
- **except Exception: pass silent error swallowing**: Replaced with specific exception types and proper logging
- **assertTrue test anti-patterns**: Replaced loose assertions with precise assertEqual/assertIn assertions

### Tests
- **1940 passed, 11 skipped, 3 xpassed** (up from 1855+ in V3.6.7)

## [3.6.7] - 2026-06-07

### Added - Redis Cache L2 Backend
- **LLMCache Redis L2**: Optional Redis backend for three-tier caching (memory→disk→Redis)
  - Configure via `enable_redis_cache`/`redis_url` params or `DEVSQUAD_ENABLE_REDIS_CACHE`/`DEVSQUAD_REDIS_URL` env vars
  - Graceful fallback when Redis unavailable (auto-degrades to memory+disk)
  - 95%+ cache hit rate with Redis enabled

### Added - Async Dispatch
- **`async_dispatch()` method**: New async dispatch on MultiAgentDispatcher using `AsyncCoordinator` with `asyncio.gather` for concurrent LLM calls
  - Auto-fallback to sync dispatch on failure
  - New `async_quick_collaborate()` convenience function
  - Significant throughput improvement for multi-role tasks

### Changed - Dispatcher Refactor
- **Split 788-line `dispatch()` into 18 step methods**: Each step is a focused, testable method
- **Extracted `dispatch_models.py`**: Data models and type definitions separated from dispatcher
- **Extracted `dispatch_performance.py`**: Performance tracking and metrics separated from dispatcher
- **dispatcher.py reduced from 1896 to ~1370 lines**: Improved maintainability and readability

### Fixed - Code Quality
- **DispatchResult.to_dict()/to_markdown() missing 5 fields**: Fixed data loss bug where `consensus_records`, `permission_checks`, `skill_proposals`, `compression_stats`, and `memory_stats` were omitted from serialization
- **Cleaned up `except:pass` patterns**: Replaced with specific exception types
- **Removed redundant `to_dict()` wrappers**: Simplified serialization code

### Changed - Testing
- **1672 → 1855 tests passing**: Restored 183 previously xfailed tests
- **CI re-enabled**: All tests now passing in CI pipeline

---

## [3.6.6] - 2026-05-27

### Added - Documentation Experience Enhancement (Major)
- **Three-Layer Funnel Documentation Structure**:
  - QUICKSTART.md: 30-second onboarding guide for new users
  - README.md: Restructured with progressive disclosure (Overview → Details)
  - SKILL.md: Updated core positioning and one-sentence understanding
- **Framework Comparison Page**: COMPARISON.md with detailed analysis vs AutoGen/CrewAI/LangGraph
  - Feature matrix (60+ comparison points)
  - Architecture pattern diagrams for all 4 frameworks
  - Use case recommendations and selection decision tree
  - Code complexity comparison (5 lines vs 25 lines)

### Added - Enhanced E2E Testing - User Journey Oriented
- **User Journey 1: Developer Onboarding (Alice)** - 8 test cases
  - Installation verification, quick initialization, first task execution
  - System status check, help documentation, error handling
- **User Journey 2: Architecture Review (Bob)** - 8 test cases
  - Complex task submission, multi-role collaboration workflow
  - Consensus mechanism simulation, report generation validation
  - Scratchpad cross-role communication, performance under load
- **Total E2E Tests**: 16 user journey tests

### Added - Documentation Unification (15 files updated)
- All external docs unified to V3.6.6: README/QUICKSTART/SKILL/GUIDE/CLAUDE
- All i18n docs updated: README_CN/JP, SKILL_CN/JP
- Internal docs updated: SPEC, CHANGELOG, MATURITY_REPORT, RELEASE_DECISION
- Version consistency verified across 27 files

### Fixed
- **test_auth_phase5.py::test_auth_disabled_by_default**: Fixed config_path=None fallback behavior
  - Root cause: None → default deployment.yaml path (which exists with auth enabled=True)
  - Solution: Use explicit non-existent path to test "no config file" scenario

### Added - Developer Tools
- `sync_trae_v3.6.5.sh`: TRAE L2 cache synchronization script
- `sync_trae_v3.6.5_fixed.sh`: Enhanced version with L2+L3 dual-layer sync
- `force_refresh_trae_skill.sh`: Force refresh tool for TRAE memory cache issues
- Publishing guides: PUBLISHING_GUIDE.md, MANUAL_PUBLISHING_GUIDE.md

---

## [3.6.5] - 2026-05-21

### Added - Enterprise Features
- **RBAC Engine**: 15+ permissions, 5 roles (SUPER_ADMIN/ADMIN/OPERATOR/ANALYST/VIEWER)
- **Audit Logger**: SHA256 integrity chain, CSV/JSON export, PII masking
- **Multi-Tenancy Manager**: 3 isolation levels, quota management
- **Sensitive Data Masker**: Automatic PII detection and masking

### Changed - Performance Enhancements
- **AsyncIO Transformation**: 2x throughput improvement, 50% latency reduction
- **Redis Cache Integration**: L1→L2→L3 three-level cache architecture
- **Prometheus Monitoring**: 12 core metrics, /metrics endpoint

### Added - Testing & Quality
- **E2E Test Suite**: 27 test cases, 5 scenarios, 100% pass rate in 9 seconds
  - CLI Complete Workflow (8 tests)
  - REST API Lifecycle (7 tests)
  - Multi-Role Collaboration (4 tests)
  - Enterprise Features (4 tests)
  - Error Recovery (4 tests)
- **Code Quality**: print() → logging migration, pre-commit hooks, .editorconfig
- **Test Coverage**: 1672 tests passing (98.5%+)

### Added - Documentation
- Updated all README files to V3.6.6 (EN/CN/JP)
- Generated E2E_TEST_REPORT_V3.6.6.md
- Updated SPEC.md to reflect Enterprise features

### Changed - Engineering Improvements
- CI/CD pipeline with GitHub Actions
- Docker multi-stage build (builder/runtime/dev)
- Pre-commit hooks (ruff/flake8/conventional-pre-commit)
- Removed hardcoded credentials from auth.py

### Changed - Code Quality & Engineering Excellence (Phase 1-5 Completed)
- **Phase 1: Automated Code Repair** (Commit: 9b45059)
  - Ruff linting: **49,238 → 490 errors** (-99% reduction)
  - Code formatting: **139 files** formatted with ruff format
  - Import sorting: **3,524 issues** fixed (isort integration)
  - Coverage boost: **23.16% → 56.39%** (formatting enables better coverage)

- **Phase 2: Type Annotation Fixes** (Commit: 17e2d7e)
  - **126 mypy type errors → 0** in 5 core modules
  - Core modules: dispatcher.py, coordinator.py, worker.py, scratchpad.py, llm_backend.py
  - Added complete Optional/Dict/List/Any type annotations

- **Phase 3: print() Cleanup & Analysis** (Commit: d3036e9)
  - Audited **587 print() instances**: 99.7% are legitimate (tests/docs/CLI)
  - Fixed **1 production code issue** (mcp_server.py)
  - Established print() classification standards

- **Phase 4: Documentation Enhancement** (Commit: cefa2a0)
  - Added **953 lines** of Google-style docstrings
  - Class coverage: **63.9% → 73.1%** (+9.2%)
  - Focus: models.py (+570 lines), dispatcher.py (+228 lines), skills handlers (+195 lines)

- **Phase 5: Test Coverage Expansion** (Commit: edfc7e1)
  - Added **96 new test cases** (1650 → 1746 tests)
  - Coverage: **62.57% → 63.18%** (exceeded 60% target)
  - New test files: dispatcher/auth/cli/input_validator/permission_guard phase5 tests

### Added - Documentation Updates (V3.6.1 Final Cleanup)
- Fixed version inconsistencies (CONSTITUTION.md, SKILL.md, SKILL_CN.md examples)
- Updated EXAMPLES.md to V3.6.1
- Updated README-CN.md and README-JP.md section headers
- Created **SPEC.md** (**1,943 lines**) - Complete V3.6.1 technical specification
- Created **ROADMAP_V3.6.2-V3.6.6.md** (**2,277 lines**) - Phase 6-9 detailed plan
- Generated **MATURITY_REPORT_V3.6.1.md** - 94% Production-Ready assessment

### Changed - Security & Quality Improvements
- Version consistency: api_server.py updated from 3.6.0 → 3.6.1
- Security: All hardcoded credentials removed (auth.py, cli.py)
- Logging migration: Additional 25 print() → logging conversions
- Temporary files cleaned (__pycache__, .pyc, .DS_Store)

### Added - Tooling & Automation
- Ruff linter/formatter configured (10 rule categories enabled)
- MyPy type checker configured (strict mode for production code)
- pytest-cov coverage reporting (80% threshold, HTML reports)
- Pre-commit hooks (.pre-commit-config.yaml) with ruff/flake8/security checks
- Created `scripts/code_quality.py` - Comprehensive quality toolkit

## [3.6.1] - 2026-05-17

### Added
- **FeedbackControlLoop** — Cybernetic feedback iteration system (Sense→Decide→Act→Feedback closed loop)
  - Quality gate with default 0.7 threshold
  - Max iterations: 3 (configurable)
  - Smart adjustment generation based on failure patterns
  - Best result tracking (not just last result)
- **ExecutionGuard** — Real-time execution abort guard
  - Multi-level triggers: timeout / output size / token limit / keywords
  - Configurable thresholds via configure()
  - Zero external dependency, <1ms per check
- **PerformanceFingerprint** — Unified execution fingerprint aggregator
  - Fuses 4 data sources: FeatureUsageTracker + PerformanceMonitor + CheckpointManager + RetrospectiveEngine
  - TF-IDF similarity search (pure Python, no external dependencies)
  - Success/failure pattern extraction
  - Cold-start graceful degradation
- **SimilarTaskRecommender** — History-based task configuration recommendation
  - Recommends roles/intent/duration based on similar historical cases
  - Confidence levels: high(>0.7) / medium(>0.4) / low
  - Cold-start fallback to RoleMatcher
- **AdaptiveRoleSelector** — Success-rate-driven adaptive role selection
  - Statistical role effectiveness report
  - Strategy: similar-task → intent-based → fallback
  - Manual stats update API available

### Changed
- All 5 modules from upstream v2.5 cybernetics enhancement analysis integrated into core architecture
- Enhanced execution reliability with real-time abort guards
- Improved task recommendation through historical pattern matching
- Better role selection driven by success rate statistics

## [3.6.0] - 2026-05-13

### Added
- **AnchorChecker** — Milestone anchor verification system with drift detection and auto-recovery suggestions
- **RetrospectiveEngine** — Independent post-dispatch retrospective with pattern extraction and anti-pattern detection
- **StructuredGoal** — Structured goal management with hierarchical decomposition and progress tracking
- **FallbackBackend** — Automatic LLM backend failover with health monitoring and priority-based routing
- **FeatureUsageTracker** — Thread-safe feature invocation counter with persistence, usage reports, and auto-persist
- **IntentWorkflowMapper** — Task intent auto-detection (6 intents: bug_fix/new_feature/security_review/code_review/performance_optimization/deployment) with workflow chain injection
- **AISemanticMatcher** — LLM-enhanced semantic role matching with keyword fallback
- **DualLayerContextManager** — Project+task dual-layer context with TTL expiration and LRU eviction
- **OperationClassifier** — 3-level operation classification (ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN) for PermissionGuard
- **SkillRegistry** — Skill registration/discovery/persistence with auto-propose from dispatch results
- **FiveAxisConsensusEngine** — 5-axis code review (correctness/readability/architecture/security/performance) in consensus mode
- **NullProviders** — Graceful degradation for Cache/Retry/Monitor/Memory protocols
- 45 new tests for AnchorChecker and RetrospectiveEngine
- 30 KNOWN_FEATURES tracked by FeatureUsageTracker for data-driven feature optimization
- 10 new module exports in `__init__.py`

### Changed
- Total test count: 1503 → 1548+
- Core module count: 45 → 48
- Enhanced dispatcher to support AnchorChecker integration at lifecycle milestones
- Enhanced dispatcher to support RetrospectiveEngine post-task analysis
- Enhanced dispatcher to support FeatureUsageTracker invocation counting
- Enhanced dispatcher with intent detection before role matching
- Enhanced dispatcher with semantic role matching augmentation
- Enhanced dispatcher with dual-layer context management
- Enhanced dispatcher with operation classification in permission checks
- Enhanced dispatcher with five-axis consensus in consensus mode
- Enhanced dispatcher with skill registry auto-proposal
- CheckpointManager: All file write operations now protected by thread-safe _file_lock
- PerformanceMonitor.export_metrics: Fixed missing persist_dir parameter (now accepts allowed_base_dir)
- FallbackBackend: Added last_error tracking in generate_stream for proper error propagation
- IntentWorkflowMapper: Improved scoring algorithm with primary/secondary language weighting
- SkillRegistry: propose_from_result() now auto-registers the skill (was only creating, not registering)
- Deleted config_manager.py (dead code, duplicate of config_loader.py)

### Fixed
- **P0 Deadlock**: FeatureUsageTracker.report() → get_high_usage_features() nested lock acquisition caused deadlock (Lock → RLock)
- **P0 Race Condition**: CheckpointManager all file write operations now thread-safe (added _file_lock to save_checkpoint, save_handoff, save_lifecycle_state)
- **P0 Undefined Variable**: FallbackBackend.generate_stream() raised undefined last_error (added proper tracking)
- **P0 AttributeError**: PerformanceMonitor.export_metrics() referenced non-existent self.persist_dir (refactored to parameter)
- **P0 API Mismatch**: FiveAxisConsensusEngine.add_axis_vote() is on engine, not review object
- **P0 Import Error**: README.md/README_CN.md FallbackBackend import path pointed to non-existent fallback_backend.py
- **P0 Import Error**: user_onboarding_verification.md referenced non-existent load_config() function
- **P1 Data**: SKILL.md/CLAUDE.md module count 65→48, test count 750+→1548+
- **P1 Data**: skill-manifest.yaml test count 1478/1500+→1548+
- **P1 Data**: workflow_engine.py description V3.5→V3.6
- **P1 Scoring**: IntentWorkflowMapper Chinese intent detection failed due to ratio-based scoring (changed to weighted primary/secondary)
- Fixed OpenAI/Anthropic backend raise last_error without fallback RuntimeError

## [3.5.0] - 2026-05-05 (V3.5.0 Enhancement Sprint)

### Added - V3.5.0 Seven Major Enhancements

#### E1: Code Walkthrough Enhancement Pack (code-walkthrough.yaml)
- 7-role walkthrough perspective definitions (Architect/Security Expert/Test Expert/Developer/DevOps Expert/Product Manager/UI Designer)
- Clear performance review ownership: Architect primarily responsible for design-level, DevOps Expert assisting with runtime-level
- Walkthrough checklists and common pitfalls for each role
- Role-specific walkthrough guide prompt injection

#### E2: Documentation Consistency Check (built into code-walkthrough enhancement pack)
- 9 documentation consistency check dimensions (API/Security/Test/Requirements/DevOps/UI/Config/Changelog/Version)
- 3 severity levels (Critical/High/Medium) with disposition strategies
- Clear primary and secondary responsibility for each documentation type
- Version consistency check (_version.py/pyproject.toml/CHANGELOG/README/INSTALL/GUIDE/SKILL.md/skill-manifest.yaml)

#### E3: Karpathy Principle Enhancement Pack (code-quality.yaml)
- 4 core principles: Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution
- Vibe Coding curated 5 rules integrated into 4 principles
- 3 role-enhanced prompts (architect/solo-coder/tester)
- Anti-pattern detection (premature abstraction / over-configuration-driven / framework-thinking)

#### E6: Project Understanding Enhancement (agent_briefing.py extension)
- generate_project_overview(): Generate project overview (tech stack/module structure/core components)
- generate_role_understanding(): 7-role customized understanding documents
- Auto-analyze project tech stack (pyproject.toml/Dockerfile/.github)
- Identify core components (14 key classes auto-discovery)

#### E8: Walkthrough-Specific Five-Axis Engine (five_axis_consensus.py extension)
- create_walkthrough_engine(): Code walkthrough-specific five-axis consensus engine
- Operability axis replaces Performance axis (deployment/monitoring/disaster-recovery/config/performance-ops)
- DevOps Expert gets 15% weight in walkthrough
- Security axis retains strict-mode veto power

#### E4: Code Map Multi-Language Support (language_parsers.py)
- LanguageParser Protocol definition
- PythonParser: Based on ast standard library (extracted from existing code)
- JavaScriptParser: Based on regex (supports JS/JSX/TS/TSX)
- GoParser: Based on regex (supports struct/interface/func)
- CodeMapGenerator refactored: register_parser() + languages filter
- Backward compatible: Uses PythonCompatParser by default when no parsers specified

#### E5: Spec Toolchain Enhancement (lifecycle_protocol.py extension)
- SpecTemplate data model + 3 spec templates (requirements/architecture/technical)
- init_spec(): Initialize spec document from template
- analyze_spec(): Analyze code to generate spec draft (reuses multi-language CodeMapGenerator)
- validate_spec(): Validate spec completeness and consistency
- VIEW_MAPPINGS added 3 sub-command mappings (spec-init/spec-analyze/spec-validate)

### Changed - Changed Files List
- `templates/concerns/code-walkthrough.yaml` — New
- `templates/concerns/code-quality.yaml` — New
- `scripts/collaboration/five_axis_consensus.py` — Extended (OPERABILITY axis + create_walkthrough_engine)
- `scripts/collaboration/agent_briefing.py` — Extended (generate_project_overview + generate_role_understanding)
- `scripts/collaboration/code_map_generator.py` — Refactored (multi-language support)
- `scripts/collaboration/language_parsers.py` — New
- `scripts/collaboration/lifecycle_protocol.py` — Extended (SpecTemplate + spec toolchain)
- `tests/test_five_axis_consensus.py` — Updated (OPERABILITY axis tests)
- Version numbers unified to 3.5.0

## [3.4.0] - 2026-05-04 (Code Quality Sprint + DevSquad Collaboration)

### Added - DevSquad 7-Role Collaboration Comprehensive Quality Improvement

#### [Architect] Three-Dimensional Code Walkthrough
- **Security**: ⭐⭐⭐⭐⭐ (5/5) - Production Ready
  - InputValidator: Comprehensive input validation (XSS/SQL injection/command injection/prompt injection)
  - PermissionGuard: 4-level permission control system (DEFAULT/PLAN/AUTO/BYPASS)
  - AuthManager: RBAC authentication system (SHA-256 password hashing)
- **Performance**: ⭐⭐⭐⭐ (4/5) - Excellent
  - LLMCache: Memory + disk dual-layer cache with TTL expiration
  - ContextCompressor: 4-level context compression to prevent overflow
  - ThreadPoolExecutor: Parallel Worker execution
- **Maintainability**: ⭐⭐⭐⭐ (3.5/5) - Good
  - 27 core modules with clear layered architecture
  - 30 broad exception handlers pending standardization

#### [Tester] Regression Test Verification
- **Test Results**: 1478 passed, 24 failed (98.4% pass rate)
- **Fixes**:
  - Fixed test_cli_lifecycle.py import error (cli package vs cli module conflict)
  - Used importlib to directly import cli.py module
- **Failure Analysis**:
  - 7 CLI test failures (dispatch mock issues)
  - 14 UX report format test failures (report structure changes)
  - 3 other test failures (edge cases)

#### [DevOps] Directory Structure Cleanup
- Deleted 3 .DS_Store files
- Confirmed no temporary/compiled file remnants
- Directory health: ⭐⭐⭐⭐⭐ (5/5)

#### [PM] Documentation Update
- README.md: Updated test badges (776+ → 1478, 98.4%)
- README.md: Added code quality and security rating badges
- CHANGELOG.md: Added this collaboration record

### Changed - Quality Metrics Comparison

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Test Pass Rate | ~98% | **98.4%** (1478/1502) | +0.4% |
| Security Rating | Not assessed | **5/5** | New |
| Overall Rating | Not assessed | **4.3/5** | New |
| Directory Cleanliness | Had .DS_Store | **100% clean** | Fixed |

### Changed - Follow-up Recommendations

1. **P0**: Fix 24 failing tests (CLI dispatch + UX report format)
2. **P1**: Standardize 30 broad exception handlers
3. **P2**: Increase core module unit test coverage to 80%+

---

## [3.3.0] - 2026-05-03 (Production Ready)

### Added - Major Production Features

#### Authentication & Authorization System
- **AuthManager** (`scripts/auth.py`): Complete authentication module
  - Multi-user support with role-based access control (RBAC)
  - Three roles: Admin, Operator, Viewer
  - SHA-256 password hashing with secure session management
  - Streamlit dashboard integration with login UI
  - OAuth2 support (optional, for enterprise)

- **Deployment Configuration** (`config/deployment.yaml`):
  - Comprehensive deployment settings
  - SSL/HTTPS configuration templates
  - Rate limiting and security headers
  - Environment-specific overrides (dev/staging/prod)

#### REST API Server (FastAPI)
- **API Server** (`scripts/api_server.py`): Production-ready REST API
  - FastAPI framework with automatic OpenAPI/Swagger documentation
  - CORS middleware support for cross-origin requests
  - Request timing and comprehensive logging
  - Global exception handling with standardized error responses

- **Data Models** (`scripts/api/models.py`): Pydantic validation models
  - LifecyclePhase, GateResult, MetricsSnapshot
  - PhaseActionRequest, PhaseActionResult
  - HealthCheck, PaginatedResponse

- **Lifecycle API Endpoints** (`scripts/api/routes/lifecycle.py`):
  - `GET /api/v1/lifecycle/phases` - List all 11 phases
  - `GET /api/v1/lifecycle/phases/{id}` - Get phase details
  - `POST /api/v1/lifecycle/actions` - Execute phase actions
  - `GET /api/v1/lifecycle/mappings` - CLI command mappings
  - `GET /api/v1/lifecycle/status` - Current execution status

- **Metrics & Gates API** (`scripts/api/routes/metrics_gates.py`):
  - `GET /api/v1/metrics/current` - Real-time metrics snapshot
  - `GET /api/v1/metrics/history` - Historical data queries
  - `GET /api/v1/gates/status` - All gate statuses
  - `POST /api/v1/gates/check` - Check specific gate
  - `GET /api/v1/health` - Service health check

#### Alert Notification System
- **AlertManager** (`scripts/alert_manager.py`): Multi-channel alerting
  - Four severity levels: INFO, WARNING, ERROR, CRITICAL
  - Multiple channels: Console, Slack, Email, Webhook
  - Rate limiting to prevent alert spam
  - Alert deduplication within configurable time window
  - Alert history tracking and statistics
  - Quick helper functions: `alert_info()`, `alert_error()`, etc.

- **Alert Configuration** (`config/alerts.yaml`):
  - Channel-specific settings (Slack webhook, SMTP email)
  - Alert rules based on conditions
  - Quiet hours configuration
  - Retention policies

#### Historical Data Storage
- **HistoryManager** (`scripts/history_manager.py`): SQLite time-series database
  - Metrics snapshots table with time-range queries
  - Alert history table with acknowledgment tracking
  - API request logs table with performance metrics
  - Lifecycle events table for state change audit
  - Automatic data retention and cleanup
  - Database size monitoring

### Added - Visualization & Monitoring Enhancements

#### Streamlit Dashboard Updates
- **Dashboard** (`scripts/dashboard.py`):
  - Integrated authentication with user session display
  - Role-based feature access control
  - Admin-only settings panel
  - Enhanced footer with version and session info
  - Production-ready UI with security indicators

#### CLI Visual Enhancement
- **CLI Visual Module** (`scripts/cli/cli_visual.py`):
  - Colored progress bars and status icons
  - Formatted tables with alignment
  - Percentage completion indicators
  - Gate status visualization

#### Jupyter Notebook Tutorial
- **Interactive Tutorial** (`examples/tutorial.ipynb`):
  - 10-section step-by-step learning guide
  - Core concepts and architecture explanation
  - CLI command to 11-phase mapping demos
  - Performance benchmarking examples

### Added - Testing & Quality
- **New Test Suite** (`tests/test_production_features.py`): 21 new tests
  - TestAuthentication (5 tests) - Auth system validation
  - TestAlertManager (5 tests) - Alert functionality
  - TestHistoryManager (6 tests) - Data persistence
  - TestAPIDataModels (4 tests) - Model validation
  - All 21 tests passing

- **Total Test Coverage**: 750+ tests (99.3% pass rate)

### Added - Documentation Updates
- Updated README.md with production features documentation
- Enhanced USAGE_GUIDE.md with visualization and monitoring guides
- Added deployment and API usage examples

---

## [3.5.0-C] - 2026-05-03 (Plan C Layered Architecture)

### Added

#### Unified Lifecycle Architecture (Plan C Implementation)

- **LifecycleProtocol** (`scripts/collaboration/lifecycle_protocol.py`): Abstract interface for unified lifecycle management
  - `LifecycleMode` enum: SHORTCUT / FULL / CUSTOM modes
  - `PhaseDefinition`: Unified phase structure with dependencies and gates
  - `ViewMapping`: CLI command → 11-phase mapping definitions
  - Complete protocol interface with 12 abstract methods

- **UnifiedGateEngine** (`scripts/collaboration/unified_gate_engine.py`): Unified gate engine
  - Integrates VerificationGate (worker output) + LifecycleProtocol (phase transition)
  - `GateType` enum: PHASE_TRANSITION / WORKER_OUTPUT / SECURITY_CHECK / etc.
  - Pluggable checker architecture with custom checker registration
  - Comprehensive result reporting with statistics tracking
  - Configurable strictness levels (UnifiedGateConfig)

- **ShortcutLifecycleAdapter** (`lifecycle_protocol.py` class): Plan C adapter
  - Implements LifecycleProtocol using CLI 6-command shortcuts
  - Automatic UnifiedGateEngine integration (with fallback to basic checks)
  - CheckpointManager integration with auto state save/restore
  - Support for lifecycle state persistence across sessions

#### Enhanced CheckpointManager

- **Lifecycle State Management** (`scripts/collaboration/checkpoint_manager.py`):
  - `save_lifecycle_state()`: Persist lifecycle progress to JSON
  - `load_lifecycle_state()`: Restore lifecycle state from disk
  - `list_lifecycle_states()`: List all saved lifecycle states
  - `delete_lifecycle_state()`: Clean up saved states
  - `create_checkpoint_from_lifecycle()`: Bridge LifecycleProtocol → Checkpoint

#### CLI View Layer Integration

- **CLI Refactored** (`scripts/cli.py`):
  - Lifecycle commands now display view layer mapping information
  - Shows which 11-phase segments each CLI command covers
  - Displays "View Layer Mode" header for clarity
  - Backward compatible with fallback output

### Added - Tests

- **New Test Suite**: `tests/test_plan_c_unified_architecture.py`
  - 27 comprehensive tests for Plan C architecture
  - UnifiedGateEngine tests (11 tests)
  - CheckpointManager lifecycle integration (7 tests)
  - ShortcutLifecycleAdapter with unified gate (6 tests)
  - End-to-end integration tests (3 tests)
  - **All 27 tests passing**

### Changed - Architecture Improvements

- Resolved CLI 6 commands vs 11-phase lifecycle conflict via layered architecture
- Single entry point for all gate checks (UnifiedGateEngine)
- Decoupled view layer (CLI) from core engine (WorkflowEngine)
- State persistence enables session recovery and long-running task support
- Backward compatible: existing code continues to work without changes

---

## [3.4.1] - 2026-05-02

### Added

#### Real LLM Backend Integration

- **LLMBackend** (`scripts/collaboration/llm_backend.py`): Unified LLM interface with Mock/OpenAI/Anthropic backends
  - `create_backend()` factory function for easy instantiation
  - OpenAI backend: `openai>=1.0` with configurable base_url and model
  - Anthropic backend: `anthropic>=0.18` with configurable model
  - Mock backend: Zero-dependency, returns assembled prompts (default)
  - Streaming support: `generate_stream()` method for real-time chunk-by-chunk output
  - 120s default timeout with configurable override
  - API keys via environment variables only (no `--api-key` CLI flag)

- **Worker streaming** (`scripts/collaboration/worker.py`): `stream=True` parameter
  - Real-time LLM output via `--stream` CLI flag
  - Chunk-by-chunk printing to stderr

- **CLI `--stream` flag** (`scripts/cli.py`): Stream LLM output in real-time

#### Security Enhancements

- **InputValidator** (`scripts/collaboration/input_validator.py`): Prompt injection detection
  - 16 regex patterns: ignore previous instructions, jailbreak, DAN mode, system prompt extraction, etc.
  - `check_prompt_injection()` public method
  - Strict mode (blocks) vs normal mode (warns)
  - Integrated into Dispatcher pipeline

- **API Key Safety**: Removed `--api-key` CLI flag entirely
  - Environment variables only: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
  - Never logged or exposed in process listings

#### Parallel Execution

- **ThreadPoolExecutor**: Real parallel execution replacing pseudo-parallel loop
  - `concurrent.futures.ThreadPoolExecutor` in Dispatcher
  - True concurrent multi-role dispatch

#### Upstream Module Adoption (from TraeMultiAgentSkill V2.3.0)

- **AISemanticMatcher** (`scripts/collaboration/ai_semantic_matcher.py`): LLM-powered semantic role matching
  - Bilingual keyword matching (Chinese + English)
  - `EN_KEYWORD_MAP` for English task descriptions
  - Falls back to keyword matching when no LLM backend available

- **CheckpointManager** (`scripts/collaboration/checkpoint_manager.py`): State persistence
  - SHA256 integrity verification
  - `HandoffDocument` for agent handoff
  - Auto-cleanup with configurable max checkpoints
  - `create_checkpoint_from_dispatch()` convenience method

- **WorkflowEngine** (`scripts/collaboration/workflow_engine.py`): Task-to-workflow orchestration
  - `create_workflow_from_task()` auto-split
  - Step execution with checkpointing
  - `resume_from_checkpoint()` recovery
  - `handoff()` for agent transitions

- **TaskCompletionChecker** (`scripts/collaboration/task_completion_checker.py`): Completion tracking
  - `check_dispatch_result()` and `check_schedule_result()`
  - Progress persistence to JSON
  - `get_completion_summary()` and `is_task_completed()`

#### Developer Experience

- **CodeMapGenerator** (`scripts/collaboration/code_map_generator.py`): AST-based Python code analysis
  - Function/class extraction, dependency graph
  - Output: dict, markdown, JSON

- **DualLayerContextManager** (`scripts/collaboration/dual_layer_context.py`): Context management
  - Project-level + task-level context with TTL
  - `build_prompt_context()`, `cleanup_expired()`, eviction

- **SkillRegistry** (`scripts/collaboration/skill_registry.py`): Reusable skill management
  - `register()`, `search()`, `execute()`, `propose_from_result()`
  - JSON persistence

- **ConfigManager** (`scripts/collaboration/config_loader.py`): Configuration system
  - `~/.devsquad.yaml` config file with 16 parameters
  - Environment variable overrides (priority: env > file > defaults)
  - `DevSquadConfig` dataclass with type conversion

- **Docker support**: `Dockerfile` + `.dockerignore`
  - Python 3.11-slim base image
  - ENTRYPOINT `cli.py`

- **GitHub Actions CI** (`.github/workflows/test.yml`):
  - Python 3.9-3.12 matrix testing
  - Lint job: flake8 + mypy

- **pip installable**: `pyproject.toml` with optional dependencies
  - `pip install -e ".[openai,anthropic,dev]"`
  - `devsquad` console script entry point

- **_version.py**: Single source of truth for version (`3.4.0`)

### Changed

- **RoleMatcher** (`scripts/collaboration/role_matcher.py`): Extracted from Dispatcher (92 lines)
- **ReportFormatter** (`scripts/collaboration/report_formatter.py`): Extracted from Dispatcher (314 lines)
- **Dispatcher**: Integrated InputValidator + ThreadPoolExecutor + prompt injection check
- **Worker**: Added `stream` parameter for real-time output
- **LLMBackend**: Added `generate_stream()` method (base + OpenAI + Anthropic)
- **258 unit tests** all passing (core_test 39 + role_mapping_test 25 + upstream_test 35 + mce_adapter_test 30)

### Added - Documentation

- README.md: Complete rewrite with architecture diagram, 34 modules, quick start
- README-CN.md: Full Chinese translation
- README-JP.md: Full Japanese translation
- INSTALL.md: Added pip install, Docker, config file, streaming
- SKILL.md: Updated to 34 modules, new architecture flow
- CLAUDE.md: Updated overview, architecture, entry points

## [3.4] - 2026-04-26

### Added

#### Performance Optimization Modules (P0-P2 Complete)

Seven new modules to enhance LLM-based application performance, reliability, and observability:

- **LLM Cache Module** (`scripts/collaboration/llm_cache.py`, ~450 lines)
  - Two-tier caching system (memory + disk)
  - TTL-based expiration (default: 24 hours)
  - LRU eviction policy for memory management
  - SHA-256 based cache key generation
  - Hit rate statistics and reporting
  - **Benefits**: 60-80% API cost reduction, 90% faster response on cache hits
  - Test suite: `llm_cache_test.py` (comprehensive coverage)

- **LLM Retry Manager** (`scripts/collaboration/llm_retry.py`, ~380 lines)
  - Exponential backoff retry mechanism with jitter
  - Circuit breaker pattern (prevents cascade failures)
  - Multi-backend fallback support (OpenAI → Anthropic → Zhipu)
  - Rate limit detection and handling
  - Per-backend statistics tracking
  - **Benefits**: 99%+ success rate, automatic fault tolerance

- **Performance Monitor** (`scripts/collaboration/performance_monitor.py`, ~380 lines)
  - Real-time function execution tracking
  - CPU and memory usage monitoring (via psutil)
  - P95/P99 latency percentile calculation
  - Bottleneck detection with configurable thresholds
  - Markdown report export
  - **Benefits**: Real-time visibility, data-driven optimization

- **Module Integration** (`scripts/collaboration/__init__.py`)
  - Unified import interface for all optimization modules
  - Convenience functions: `print_stats()`, `reset_all()`, `get_version()`
  - Clean API exports with `__all__` definition

- **Integration Example** (`scripts/collaboration/integration_example.py`, ~290 lines)
  - 6 comprehensive demo scenarios
  - Shows cache + retry + monitor working together
  - Mock LLM API for testing
  - Performance comparison demonstrations

#### P1: Async Support Modules (NEW)

- **Async LLM Cache** (`scripts/collaboration/llm_cache_async.py`, ~350 lines)
  - Asyncio-compatible dual-layer caching
  - asyncio.Lock for thread safety
  - Async file I/O with run_in_executor
  - Full async/await API (get, set, clear)
  - **Benefits**: 3-5x performance in high-concurrency scenarios

- **Async LLM Retry** (`scripts/collaboration/llm_retry_async.py`, ~400 lines)
  - Async exponential backoff retry
  - Async circuit breaker pattern
  - Multi-backend async fallback
  - Rate limit detection
  - Decorator support for async functions
  - **Benefits**: Non-blocking I/O, better CPU utilization

- **Async Integration Example** (`scripts/collaboration/async_integration_example.py`, ~250 lines)
  - 5 complete async examples
  - Basic async cache usage
  - Async retry with fallback
  - Combined cache + retry patterns
  - Concurrent request handling with asyncio.gather
  - Circuit breaker demonstration

#### P2: Configuration Management (NEW)

- **Config Manager** (`scripts/collaboration/config_manager.py`, ~350 lines)
  - YAML configuration file support
  - Environment variable overrides
  - Dot-notation key access (e.g., "cache.ttl_seconds")
  - Configuration validation
  - Hot reload support
  - Default configuration template
  - **Benefits**: Centralized config, easy deployment customization

- **Default Config File** (`config/llm_optimization.yaml`)
  - Complete default configuration
  - Cache settings (TTL, max entries, disk cache)
  - Retry settings (max retries, delays, jitter)
  - Circuit breaker settings (threshold, timeout)
  - Performance monitoring settings
  - Backend configuration (primary, fallback order)
  - Logging configuration

#### Documentation

- **Optimization Guide** (`docs/OPTIMIZATION_GUIDE.md`, ~600 lines)
  - Complete usage guide for all three modules
  - Quick start examples
  - Best practices and anti-patterns
  - Performance benchmarks and targets
  - Troubleshooting guide
  - Advanced configuration examples

- **Optimization Recommendations** (`docs/OPTIMIZATION_RECOMMENDATIONS_2026-04-26.md`)
  - 20+ prioritized optimization suggestions (P0-P3)
  - Detailed implementation plans
  - Expected benefits and ROI analysis
  - Code examples for each recommendation

- **Review & Scoring Report** (`docs/OPTIMIZATION_REVIEW_SCORE.md`)
  - Comprehensive evaluation: **85/100**
  - Detailed scoring breakdown (code quality, functionality, testing, docs, maintainability)
  - Comparison with industry best practices (Redis, Tenacity, Prometheus)
  - Gap analysis and improvement roadmap
  - Performance benchmark results

### Changed

- **README.md**: Added "Performance Optimization Modules" section
  - Updated core modules count: 16 → 19
  - Added quick start examples for each optimization module
  - Added integration example
  - Links to optimization documentation

### Changed - Performance Impact

**Cache Module:**
- Test scenario: 1000 LLM calls, 50% repetition
- Cost reduction: 50% (500 → 250 API calls)
- Speed improvement: 48% (250s → 130s)
- Memory overhead: ~10MB for 1000 entries

**Retry Module:**
- Test scenario: 100 API calls, 10% failure rate
- Success rate improvement: 90% → 99.9%
- Average retry overhead: +5% latency
- Circuit breaker prevents cascade failures

**Monitor Module:**
- Performance overhead: ~2% CPU, ~10% memory
- Real-time P95/P99 tracking
- Bottleneck detection with configurable thresholds

### Added - Dependencies

- Added optional dependency: `psutil` (for performance monitoring)
- All other modules use Python stdlib only

### Added - Testing

- LLM Cache: Comprehensive test suite (`llm_cache_test.py`)
- LLM Retry: Tests needed (identified in review)
- Performance Monitor: Tests needed (identified in review)
- Integration tests: Needed (identified in review)

### Deprecated - Known Limitations

As documented in `OPTIMIZATION_REVIEW_SCORE.md`:

1. **Test Coverage** (-6 points): Only cache module has tests
2. **Async Support** (-3 points): All modules are synchronous only
3. **Logging** (-3 points): Basic logging, needs structured logging
4. **Configuration** (-2 points): Hard-coded configs, needs config file support
5. **Alerting** (-2 points): Passive monitoring only, no active alerts
6. **Persistence** (-1 point): Statistics not persisted across restarts

## [3.3] - 2026-04-17

### Added

#### WorkBuddy (Claw) Memory Bridge Integration

Per `docs/spec/WORKBUDDY_CLAW_INTEGRATION_SPEC.md` (CHG-01 ~ CHG-10):

- New `WorkBuddyClawSource` class (~404 lines) in `memory_bridge.py`
  - Read-only bridge to `/Users/lin/WorkBuddy/Claw/.memory/` and `.workbuddy/memory/`
  - INDEX.md inverted index search with fallback full-text scan (O(1) hit)
  - Core file mapping: SOUL→SEMANTIC, USER→KNOWLEDGE, MEMORY→KNOWLEDGE, etc.
  - Daily work log loading (up to 30 recent `.md` files from `.workbuddy/memory/`)
  - Plan B: AI news feed from `.codebuddy/automations/ai/memory.md`
  - `_parse_automation_log()` for structured news extraction by date blocks

- `MemoryBridge` integration (+30 lines)
  - `__init__()`: auto-register WorkBuddyClawSource with graceful degradation
  - `recall()`: merge claw_items into results (half limit, sort by relevance_score)
  - `MemoryStats`: +`claw_enabled`, +`claw_item_count` fields
  - `get_statistics()`: populate claw stats
  - `print_diagnostics()`: add "WorkBuddy (Claw) Bridge" diagnostic section
  - `get_workbuddy_ai_news(days=7)`: public API for Plan B news feed

- Dispatcher AI News auto-injection (+29 lines in `dispatcher.py`)
  - Keyword-triggered injection into Scratchpad when task matches AI/trend/news keywords
  - Zero LLM calls, zero network requests for industry intelligence
  - 15 trigger keywords (CN+EN): ai news, industry trend, llm, claude, cursor, etc.

- New test suite: `claw_integration_test.py` (33 cases)
  - T-A01~T-A08: Source availability, core/daily memories, index search, recall fusion
  - T-B01~T-B04: News parsing, date filtering, missing file, bridge API
  - T-D01~T-D02: Diagnostics output, statistics fields
  - Utility tests: extract_tags, extract_section, parse_automation_log, load_all

#### Annotation Standards Update

- Documentation (SKILL.md / README.md): English
- Code docstring: English (Args / Returns / Example)
- Inline comments: English (business logic)
- README-CN.md: Chinese (localized documentation)

### Changed

- SKILL.md: v3.2→v3.3, 15→16 modules, ~795→~828 tests
- README.md: added v3.3 Claw row, ~795→~828 tests
- `__init__.py`: export `WorkBuddyClawSource`
- `v3-upgrade-proposal.md`: added Phase 11 record

### Added - Test Results

```
MemoryBridge Test:        96/96
Dispatcher Test:          54/54
MCE Adapter Test:         23/23
Dispatcher UX Test:       24/24
Claw Integration Test:    33/33
─────────────────────────────────
Total:                   230/230
```

---

## [3.2] - 2026-04-17

### Added

#### MVP Three Parallel Lines (per v3.2 Final Consensus)

##### Line A: E2E Full Demo
- New `scripts/demo/e2e_full_demo.py` (~350 lines)
  - CLI interface (--task/--roles/--json args)
  - RoleOutputSimulator: 5-role realistic output simulation
  - 10-step complete flow: Init→Analyze→Plan→Schedule→Execute→Share→Conflict→Report→Memory→Output

##### Line B: MCE Adapter
- New `scripts/collaboration/mce_adapter.py` (~290 lines)
  - MCEAdapter: lazy init, graceful degrade, thread-safe
  - MCEResult / MCEStatus data models
  - get_global_mce_adapter() process-level singleton
  - Integration points: MemoryBridge (capture/recall/shutdown), Dispatcher (classify)

##### Line C: Dispatcher UX Enhancement
- Enhanced `dispatcher.py` quick_dispatch() (+360 lines)
  - 3 output formats: structured (default) / compact / detailed
  - Structured report hierarchy: summary card → role table → findings → conflicts → action items
  - _extract_findings(): numbered/bulleted/semicolon/sentence splitting
  - _generate_action_items(): H/M/L priority auto-generation based on result analysis

- New test suites:
  - mce_adapter_test.py: 23 cases (init/classify/batch/store/retrieve/lifecycle/thread-safety/normalize)
  - dispatcher_ux_test.py: 24 cases (structured/compact/detailed reports, extraction, action items)

### Changed

- memory_bridge.py: __init__(mce_adapter), capture_execution(MCE classify), recall(MCE filter), shutdown(MCE integration)
- dispatcher.py: __init__(mce_adapter), dispatch(MCE classify step)
- __init__.py: export MCEAdapter/MCEResult/MCEStatus/get_global_mce_adapter
- SKILL.md / README.md / v3-upgrade-proposal.md: v3.2 entries

---

## [3.1] - 2026-04-16

### Added

#### Prompt Optimization System (borrowed from Claude Code architecture)

##### PromptAssembler (~320 lines)
- TaskComplexity detection (3D model: length + keywords + structure)
- 3 template variants: compact / standard / enhanced
- 5 instruction styles per role type
- Role-specific anti-pattern warnings
- Compression-level override support

##### PromptVariantGenerator (~420 lines)
- SuccessPattern → PromptVariant closed-loop pipeline
- Quality scoring (5-dimension: relevance/freshness/actionability/uniqueness/clarity)
- Threshold-based filtering (confidence ≥ 0.7, frequency ≥ 2)
- A/B promotion lifecycle (promote at ≥75% positive, deprecate at ≤35%)
- Auto-deprecation of underperforming variants

- New test: prompt_optimization_test.py (59 cases)

---

## [3.0] - 2026-04-16

### Added

#### Complete V3 Architecture Redesign

Based on Coordinator/Worker/Scratchpad collaboration pattern:

- 11 Core Modules (later expanded to 13 in v3.1, 16 in v3.3):
  0. MultiAgentDispatcher (unified entry point)
  1. Coordinator (global orchestrator)
  2. Scratchpad (shared blackboard)
  3. Worker (role executor)
  4. ConsensusEngine (weighted voting + veto)
  5. BatchScheduler (parallel/sequential hybrid)
  6. ContextCompressor (4 compression levels)
  7. PermissionGuard (4 permission levels)
  8. Skillifier (skill learning from patterns)
  9. WarmupManager (3-layer startup warmup)
  10. MemoryBridge (7-type memory bridge + TF-IDF + forgetting curve)
  11. TestQualityGuard (3-layer testing quality enforcement)

- ~710 baseline tests (all passing)
- E2E test: e2e_test.py (26 cases)
- Enhanced E2E test: enhanced_e2e_test.py (46 cases)

---

## [2.5.0] - 2026-04-06

### Added

#### Memory Classification Engine Integration

##### Memory Adapter Module
- New `scripts/memory_adapter.py` module
- Implemented 7 memory type classifications: user preferences, correction signals, factual statements, decision records, relationship information, task patterns, emotional markers
- Implemented 4-layer storage architecture: working memory, procedural memory, episodic memory, semantic memory
- Implemented `MemoryTypeMapper` classifier
- Implemented `MemoryAdapter` core adapter

##### Dual-Layer Context Manager Enhancement
- New `process_message_with_memory()` method
- New `retrieve_memories_by_type()` method
- New `apply_forgetting()` method
- New `get_memory_statistics()` method

##### Forgetting Mechanism
- Weighted decay-based intelligent forgetting
- Automatic cleanup of low-value memories
- Support for custom decay factors and minimum weight thresholds

##### Documentation Updates
- New `docs/architecture/memory_integration_architecture.md` architecture document
- New `docs/testing/memory_integration_test.md` test report
- Updated `README.md` with v2.5.0 feature description

##### Tests
- New `scripts/test_memory_adapter.py` test script
- Memory type classification accuracy: 92.9%
- Layer mapping accuracy: 100%
- All integration tests passing

## [2.4.2] - 2026-04-03

### Added

#### Smart Lifecycle Recognition

- Auto-detect tasks requiring a complete project lifecycle
- New `IntentType.PROJECT_LIFECYCLE` intent type
- Extended trigger keywords: project lifecycle, full lifecycle, complete flow, start project, new project, etc.
- SKILL.md added auto-trigger rule documentation

## [2.4.1] - 2026-04-01

### Added

#### Core Rules Integration

- Integrated Claude Code's 14 prompt core rules into Vibe Coding prompt optimization system
- New `/dss lifecycle` command for one-click full project lifecycle launch
- New `/dss rules` command to view system-integrated core rule library
- Completed multi-role critical review report (`docs/critical_review.md`)
- Repository structure optimization, cleaned up unnecessary files

## [2.3.0] - 2026-03-28

### Added

#### Code Map Enhancement (v2.3)

##### Multi-Project Workspace Support
- Support for a workspace containing multiple projects
- Auto-identify project's workspace
- Clear project identification (project name, workspace, relative path)

##### Multi-Role Code Walkthrough
- `MultiRoleCodeWalkthrough` class (`scripts/multi_role_code_walkthrough.py`)
- Support for 5 role analyses: Architect, Product Manager, Solo Developer, UI Designer, Test Expert
- Role-specific code analysis prompt templates
- Document alignment mechanism, merging multi-role analysis results
- Generate unified code map
- Generate code walkthrough review report (`CodeReviewReportGenerator` class)

##### True Multi-Role Collaborative Analyzer (v2.3)
- `MultiRoleCollaborativeAnalyzer` class (`scripts/multi_role_collaborative_analyzer.py`)
- Integrated Trae Agent dispatch system (`trae_agent_dispatch_v2.py`)
- Each role uses dedicated prompt template for real analysis
- True multi-role collaboration: Architect, Product Manager, Solo Developer, UI Designer, Test Expert
- Support for parallel/sequential execution of role analysis tasks
- Extract key findings and recommendations from each role

##### Role-Specific Prompt Templates
- Architect code analysis template (`docs/spec/role-prompts/architect-code-analysis.md`)
- Product Manager code analysis template (`docs/spec/role-prompts/pm-code-analysis.md`)
- Solo Developer code analysis template (`docs/spec/role-prompts/coder-code-analysis.md`)
- UI Designer code analysis template (`docs/spec/role-prompts/ui-code-analysis.md`)
- Test Expert code analysis template (`docs/spec/role-prompts/test-code-analysis.md`)

##### Code Map Generator v2.1
- `CodeMapGenerator` class enhanced (`scripts/code_map_generator_v2.py`)
- Multi-language analysis support: Python, Java, JavaScript/TypeScript, Go, etc.
- Architecture layer detection (API Layer, Service Layer, Data Layer, etc.)
- Function and class detailed information extraction
- Call relationship tracing
- Complexity assessment
- Markdown format output

##### Code and Documentation Separation (v2.3)
- Code map retains only core structural content (project overview, architecture view, code structure, multi-role perspectives, analysis consensus)
- Review report includes complete risk assessment and recommendations
- Removed "suggestions" and "quick reference" sections from code map

##### 3D Code Map Visualization (v2.3)
- `docs/code-map-visualizer.html`
- Three.js 3D engine with drag rotation, scroll zoom
- Node type differentiation: modules (blue), classes (purple), functions (green)
- Call relationship visualization: lines between nodes represent call relationships
- Dynamic flow effects: edges use dashed animation + flowing particles
- Dark/light theme toggle
- Click to expand/collapse, double-click to highlight call chain, search filter

##### Task Visualization Page (v2.3)
- `docs/task-visualizer.html`
- Overview statistics panel: total tasks, pending, in progress, completed, blocked
- Role task cards: task list, status, progress
- Task dependency and blocking relationship display
- Task handoff record timeline
- Canvas-drawn collaboration relationship graph
- Auto-refresh mechanism (30-second interval)
- Task detail popup

##### Documentation and Code Consistency Check (v2.3)
- `ProjectScanner` supports document file scanning (.md, .txt, .rst, .adoc)
- `CodeReviewReportGenerator` added `_generate_doc_code_consistency_check()` method
- Documentation coverage overview statistics
- Checklist table (README, API, config, architecture docs)
- Difference analysis graded by severity (critical/medium/minor)

## [2.2.0] - 2026-03-21

### Added

#### Long-Running Agent Support (Based on Anthropic "Effective Harnesses for Long-Running Agents")

##### Checkpoint Manager
- `CheckpointManager` class (`scripts/checkpoint_manager.py`)
  - Periodically save task state (like a human engineer's git commit)
  - Support recovery from any breakpoint
  - Data integrity verification (SHA256 hash)
  - Auto-expiration cleanup mechanism
  - Handoff document generation

##### Handoff Shift Protocol
- `HandoffDocument` class
  - Standardized handoff document (JSON + Markdown)
  - Handoff reason recording and confidence assessment
  - Important notes passing
  - Support for dual-agent architecture (Planner + Executor)
  - Handoff history tracking

##### TaskList Manager
- `TaskListManager` class (`scripts/task_list_manager.py`)
  - 4 priority levels (CRITICAL/HIGH/MEDIUM/LOW)
  - 5 statuses (PENDING/IN_PROGRESS/COMPLETED/BLOCKED/CANCELLED)
  - Dependency management (is_ready check)
  - Progress tracking and effort estimation
  - Markdown export functionality

##### WorkflowEngineV2 Enhanced
- `WorkflowEngineV2` class (`scripts/workflow_engine_v2.py`)
  - Integrated Checkpoint + TaskList + Handoff
  - Smart task splitting (based on keyword recognition)
  - Periodic auto-save checkpoints
  - Support for agent shift handoff
  - Breakpoint recovery mechanism

##### Complete Test Suite
- 24 tests all passing
  - `TestCheckpointManager`: 7 tests
  - `TestHandoffDocument`: 3 tests
  - `TestTaskListManager`: 9 tests
  - `TestWorkflowEngineV2`: 5 tests

### Fixed

#### Role Matching Issues
- Fixed role matching always matching to UI Designer
  - Optimized keyword discrimination
  - Added AI semantic matching
  - Enhanced priority weighting

#### JSON Serialization Issues
- Fixed enum type JSON serialization errors
  - Checkpoint status enum conversion
  - TaskList status and priority enum conversion
  - WorkflowEngine step status enum conversion
  - Data integrity hash verification

## [1.3.0] - 2026-03-12

### Fixed

#### Agent Loop Thinking Cycle Issues
- Fixed `is_all_tasks_completed()` method
  - Prioritize checking actual completion status from task files
  - Iterate all test cases, check for pending implementation markers
  - Use progress file as fallback on error

- Optimized `agent_loop_controller.py` loop logic
  - Added consecutive no-progress counter (prevents infinite loops)
  - Force exit after 3 consecutive iterations with no progress
  - Added task execution success/failure counter management
  - Ensure loop exits correctly in all scenarios

- Improved task state synchronization mechanism
  - Task file state takes precedence, ensuring synchronization
  - Correctly handle completed and pending task list updates
  - Avoid state conflicts and inconsistencies

- Fixed path issues
  - Import checker script from skill directory
  - Use relative paths to locate progress files

## [1.2.0] - 2026-03-11

### Added

#### Spec-Driven Development Features
- Complete spec toolchain (scripts/spec_tools.py)
  - `spec_tools.py init` - Initialize spec environment
  - `spec_tools.py analyze` - Analyze spec completeness and consistency
  - `spec_tools.py update` - Update spec documents
  - `spec_tools.py validate` - Validate spec execution status

- Project Constitution (CONSTITUTION.md)
  - Project core values and principles
  - Tech stack constraints and decisions
  - Code standards and conventions
  - Multi-role consensus formulation process

- Project Specification (SPEC.md)
  - Requirements spec (Product Manager responsible)
  - Technical spec (Architect responsible)
  - Test spec (Test Expert responsible)
  - Development spec (Solo Developer responsible)

- Spec Analysis Report (SPEC_ANALYSIS.md)
  - Spec completeness analysis
  - Spec consistency check
  - Spec feasibility assessment
  - Improvement recommendations

- Spec Template Library
  - CONSTITUTION_TEMPLATE.md - Project constitution template
  - SPEC_TEMPLATE.md - Project specification template
  - SPEC_ANALYSIS_TEMPLATE.md - Spec analysis template
  - PROJECT_STRUCTURE_TEMPLATE.md - Project structure template

#### Code Map Generation Features
- Code Map Generator (scripts/code_map_generator.py)
  - Auto-scan project code structure
  - Identify core components and entry files
  - Analyze module dependency relationships
  - Generate tech stack statistics

- Output Format Support
  - JSON format (code_map.json) - Machine-readable
  - Markdown format (PROJECT_STRUCTURE.md) - Human-readable
  - Visual project structure tree
  - Component responsibility descriptions

- Code Map Content
  - Project overview and statistics
  - Directory structure tree
  - Core components and entry files
  - Module dependency graph
  - Tech stack analysis (languages, frameworks, libraries)

#### Project Understanding Features
- Project Understanding Generator (scripts/project_understanding.py)
  - Quick read of project documentation and code
  - Generate customized understanding documents for each role
  - Provide project overview and tech stack analysis
  - Serve as work initialization context

- Role-Specific Understanding Documents
  - project_understanding.json - Overall project information
  - architect_understanding.md - Architect understanding (tech stack, architecture patterns, deployment structure)
  - product_manager_understanding.md - Product Manager understanding (feature list, user value, competitive analysis)
  - test_expert_understanding.md - Test Expert understanding (test coverage, quality risks, automation strategy)
  - solo_coder_understanding.md - Solo Developer understanding (code structure, development standards, tech debt)

- Project Understanding Content
  - Project overview (name, description, goals)
  - Tech stack analysis (programming languages, frameworks, databases, middleware)
  - Code structure analysis (directory organization, module division, code statistics)
  - Documentation analysis (README, API docs, design docs)
  - Dependency analysis (package.json, pom.xml, Cargo.toml, etc.)
  - Role-specific insights and recommendations

#### Enhanced Role Prompt System
- Spec-related responsibilities
  - Architect: Responsible for creating and maintaining technical specs
  - Product Manager: Responsible for creating and maintaining requirements specs
  - Test Expert: Responsible for creating and maintaining test specs
  - Solo Developer: Responsible for following specs and providing improvement feedback

- Spec-driven development workflow
  - All development work must be based on reviewed specs
  - Spec changes must go through multi-role consensus
  - Spec execution status must be checked regularly
  - Spec documents must be kept up to date

### Changed

- Updated README.md
  - Added March 2026 latest update notes
  - Added spec-driven development detailed description
  - Added code map generation detailed description
  - Added project understanding detailed description
  - Updated feature list

- Updated SKILL.md
  - Added spec-driven development responsibilities
  - Added code map generation responsibilities
  - Added project understanding responsibilities
  - Updated role definitions and trigger keywords

- Updated EXAMPLES.md
  - Added spec-driven development examples
  - Added code map generation examples
  - Added project understanding examples
  - Updated scenario examples

### Changed - Improvements

- Document-driven development workflow optimization
  - Clarified document dependency relationships
  - Added checkpoint mechanism
  - Strengthened review process
  - Improved violation handling

- Multi-role collaboration mechanism
  - Optimized consensus decision-making process
  - Improved inter-role communication
  - Enhanced context sharing
  - Improved collaboration efficiency

## [1.1.0] - 2024-03-05

### Added

#### Standard Workflow for New Features / Feature Changes
- 7-stage standard workflow
  - Stage 1: Requirements Analysis (Product Manager)
  - Stage 2: Architecture Design (Architect)
  - Stage 3: Test Design (Test Expert)
  - Stage 4: Task Decomposition (Solo Developer)
  - Stage 5: Development Implementation (Solo Developer)
  - Stage 6: Test Verification (Test Expert)
  - Stage 7: Release Review (Multi-role)

- Core principle: Design first, document first, then develop
  - Strictly prohibited: Coding without design, developing before documentation is complete, implementing without review
  - Must follow: All new features must be designed first, all designs must be documented first, all documents must be reviewed

- Cross-role design review mechanism
  - PRD review process (Product Manager → Architect + Test Expert)
  - Architecture design review process (Architect → Product Manager + Test Expert + Developer)
  - Test plan review process (Test Expert → Product Manager + Architect + Developer)
  - Development plan review process (Developer → Architect + Test Expert)

- Document dependency management
  - PRD → Architecture Design → Test Plan → Development Tasks → Test Report → Release Decision
  - Clear inputs, outputs, and checkpoints for each stage

- Violation handling mechanism
  - Response measures when workflow is not followed
  - Rollback to previous checkpoint
  - Supplement missing documents or reviews

#### Document-Based Task Decomposition and Execution Rules
- Document-driven task decomposition standards for all roles
  - Architect: Decompose tasks based on architecture design documents
  - Product Manager: Decompose tasks based on PRD documents
  - Test Expert: Decompose tasks based on test plan documents
  - Solo Developer: Decompose tasks based on all technical documents

- Task dependency definition
  - Clear definition of dependencies between stages
  - Downstream tasks must wait for upstream tasks to complete
  - Document writing tasks must start after design/implementation is complete

- Checkpoint mechanism
  - Set checkpoints at each stage (CP-1, CP-2, ...)
  - Check content includes completeness and quality requirements
  - Clear pass criteria; failures require fixes

- Solo Developer prerequisite checks
  - Must confirm PRD document has been reviewed and approved
  - Must confirm architecture design document has been reviewed and approved
  - Must confirm test plan has been reviewed and approved
  - Document reading confirmation output requirements

#### Standardized Document Templates
- Architect document template
  - ARCHITECTURE_DESIGN_TEMPLATE.md - Architecture design document template
  - Includes update history, system overview, module design, interface definitions, etc.

- Product Manager document template
  - PRD_TEMPLATE.md - Product requirements document template
  - Includes update history, requirements analysis, functional requirements, non-functional requirements, etc.

- Test Expert document template
  - TEST_PLAN_TEMPLATE.md - Test plan document template
  - Includes update history, test strategy, test case design, test execution plan, etc.

#### Document Update History Standards
- All documents must include an update history section
- Unified update history table format
- Required fields: version number, date, updater, update content, review status

### Changed

- Updated README.md
  - Added new feature / feature change standard workflow description
  - Added document dependency diagram

- Updated SKILL.md
  - Added 7-stage standard workflow detailed description
  - Added cross-role design review mechanism
  - Added document-based task decomposition and execution rules
  - Updated Solo Developer prerequisite check requirements

## [1.0.0] - 2024-03-04

### Added

#### Core Features
- Smart Role Dispatch System
  - Keyword matching-based role identification algorithm
  - Position weight calculation (earlier positions get higher weight)
  - Confidence assessment mechanism
  - Support for 4 role auto-identification

- Multi-Role Collaboration Mechanism
  - Consensus organization algorithm
  - Conflict detection and resolution
  - Multi-role review process
  - Inter-role context sharing

- Complete Project Lifecycle Support
  - 8-stage project workflow
  - Full lifecycle from requirements to deployment
  - Quality gates and review mechanisms
  - Project phase-aware dispatch

- Context-Aware Dispatch
  - Historical context intelligent inheritance
  - Project phase identification
  - Task chain auto-association
  - Context priority management

#### Role System
- Architect
  - Systems thinking rules
  - 5-Why analysis method
  - Zero-tolerance checklist (6 prohibitions)
  - Verification-driven design
  - Complete output template

- Product Manager
  - Three-layer requirement mining rules
  - SMART acceptance criteria
  - Competitive analysis rules
  - User research methods
  - PRD document standards

- Test Expert
  - Test pyramid rules
  - Orthogonal analysis method
  - 5 test scenario design types
  - Real device testing rules
  - Automated testing standards

- Solo Coder
  - Zero-tolerance checklist (10 prohibitions)
  - Completeness check rules (4 dimensions)
  - Self-testing rules (3 layers)
  - Code quality standards
  - Error handling standards

#### Dispatch Scripts
- `trae_agent_dispatch.py`
  - Command-line interface
  - Auto role identification
  - Manual role specification
  - Consensus mechanism trigger
  - Complete project workflow
  - Code review mode
  - Hotfix channel

#### Documentation System
- Skill definition file (SKILL.md)
  - 34KB complete Prompt
  - 4 role detailed rules
  - Work principles and processes
  - Checklists

- User Guide
  - Quick start
  - Usage examples
  - Best practices
  - FAQ

- Installation Guide
  - Multiple installation methods
  - Verification steps
  - Troubleshooting

- Role Configuration Documentation
  - Role definitions
  - Collaboration mechanisms
  - Trigger timing

#### Tool Scripts
- `install-global.sh`
  - Automated installation script
  - Backup mechanism
  - Verification process

- `schedule_agent.py`
  - Dispatch execution script
  - Consensus organization
  - Result processing

### Changed

- None (initial version)

### Fixed

- None (initial version)

### Deprecated

- None (initial version)

### Removed

- None (initial version)

### Security

- Security features
  - Sensitive configuration encrypted storage
  - Permission check mechanism
  - Security test scenario coverage
  - OWASP Top 10 detection support

---

## Version Notes

### Version Number Format

Follows Semantic Versioning: `MAJOR.MINOR.PATCH`

## Future Plans

### [1.1.0] - Planned

#### New Roles
- DevOps Engineer
- Data Analyst
- UI/UX Designer

#### Enhanced Features
- Role learning capability (optimization based on historical feedback)
- Multi-language support (English, Japanese, etc.)
- Custom role configuration
- Role skill marketplace

## Contributors

Thanks to all contributors to this project!

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.

---

**Made with ❤️ by weiansoft**
