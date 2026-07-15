---
name: devsquad
slug: devsquad
version: 4.1.0
description: |
  V4.0.0 DevSquad — Enterprise Multi-Role AI Task Orchestrator.
  One task → Multi-role AI collaboration → One conclusion.
  7 core roles (architect/pm/security/tester/coder/devops/ui), real LLM backend
  (OpenAI/Anthropic/MOKA AI), CLI + MCP + Python API + REST API + Web Dashboard.
  ThreadPoolExecutor parallel, CheckpointManager, WorkflowEngine, streaming, Docker, CI.
  V4.0.0: Loop Engineering + UI/UX 巡检 + Adversarial 验证 + DAG 可视化 + Autonomous + 插件热加载.
  185+ core modules, 4651+ tests passing (CI authoritative).
---

# DevSquad V4.1.0 — Multi-Role AI Task Orchestrator (Enterprise Ready)

## 🎯 一句话理解（3 秒）

**DevSquad = 把「单个 AI 助手」升级成「7 人 AI 专业团队」**

```
传统 AI:  你 ──→ ChatGPT ──→ 一个回答（可能不全面）
DevSquad:  你 ──→ DevSquad ──→ [架构师+安全+测试+开发...] ──→ 多维度共识结论
```

## ⚡ 核心工作流（30 秒）

### Core Positioning

This Skill upgrades Trae from a "single AI assistant" to a "multi-AI team". When a task is submitted, it is no longer handled by a single role:

```
User Task → [InputValidator] → [RoleMatcher] → [Coordinator Orchestration]
           → [ThreadPoolExecutor Parallel Workers] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

### 对比：单 AI vs DevSquad

| 维度 | 单个 AI (ChatGPT/Claude) | DevSquad |
|------|---------------------------|----------|
| 视角 | 一个角色回答 | **7 个专业角色并行** |
| 质量 | 可能遗漏安全/测试 | **多维度交叉验证** |
| 可追溯 | 无 | **完整审计链 (SHA256)** |
| 适用场景 | 简单问答 | **复杂工程任务** |

### 最快上手（5 分钟）

```bash
# 安装
pip install devsquad

# 运行 - 让 AI 团队帮你设计认证系统
devsquad run "设计一个安全的用户认证系统" --roles architect,security,tester,coder

# 输出结构化报告：
# ✅ 架构师建议：采用 JWT + Refresh Token 方案...
# ✅ 安全专家审查：需防范 CSRF、XSS、SQL 注入...
# ✅ 测试策略：单元测试覆盖率达 90%+...
# ✅ 开发实现：提供完整代码框架...
# 📊 共识结论：方案可行，风险可控...
```

📚 **完整快速入门指南** → [QUICKSTART.md](QUICKSTART.md)

## Architecture Overview (185+ Core Modules)

| # | Module | File | Responsibility |
|---|-------|------|---------------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | Unified dispatch entry point (integrates all modules) |
| 1 | **Coordinator** | `coordinator.py` | Global orchestrator: decompose tasks, assign Workers, collect results, resolve conflicts |
| 2 | **Scratchpad** | `scratchpad.py` | Shared blackboard for real-time info exchange between Workers |
| 3 | **Worker** | `worker.py` | Executor: one instance per role, independent execution with Scratchpad writes |
| 4 | **ConsensusEngine** | `consensus.py` | Consensus engine: weighted voting + veto power + escalation mechanism |
| 5 | **BatchScheduler** | `batch_scheduler.py` | Parallel/sequential hybrid scheduling with auto safety check |
| 6 | **ContextCompressor** | `context_compressor.py` | 4-level context compression (NONE/SNIP/SESSION_MEMORY/FULL_COMPACT) |
| 7 | **PermissionGuard** | `permission_guard.py` | 4-level permission guard (PLAN/DEFAULT/AUTO/BYPASS) |
| 8 | **Skillifier** | `skillifier.py` | Auto-generate new Skills from successful operation patterns |
| 9 | **WarmupManager** | `warmup_manager.py` | 3-layer startup warmup (EAGER/ASYNC/LAZY) + process-level cache |
| 10 | **MemoryBridge** | `memory_bridge.py` | 7-type memory bridge + inverted index + TF-IDF + forgetting curve + MCE+Claw integration |
| 11 | **TestQualityGuard** | `test_quality_guard.py` | Test quality audit (API validation / anti-pattern detection / dimension coverage) |
| 12 | **PromptAssembler** | `prompt_assembler.py` | Dynamic prompt assembly (complexity detection / 3 variants / 5 styles / compression-aware / QC config injection / user rule injection) |
| 13 | **MCEAdapter** | `mce_adapter.py` | CarryMem integration adapter (DevSquadAdapter preferred, lazy-load / graceful-degrade / thread-safe / match_rules + format_rules_as_prompt + add_rule) |
| 14 | **WorkBuddyClawSource** | `memory_bridge.py` (class) | WorkBuddy Claw read-only bridge (INDEX search / daily logs / AI news feed) |
| 15 | **RoleMatcher** | `role_matcher.py` | Keyword-based role matching with alias resolution (extracted from Dispatcher) |
| 16 | **ReportFormatter** | `report_formatter.py` | Structured/compact/detailed report generation (extracted from Dispatcher) |
| 17 | **InputValidator** | `input_validator.py` | Security validation + 40-pattern detection (14 forbidden + 21 prompt injection + 5 suspicious) |
| 18 | **RuleCollector** | `rule_collector.py` | Natural language rule collection (intent detection / rule extraction / sanitization / CarryMem+JSON storage / prompt injection protection) |
| 19 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM-powered semantic role matching with bilingual keyword fallback |
| 20 | **CheckpointManager** | `checkpoint_manager.py` | SHA256 integrity, handoff documents, auto-cleanup, dispatch integration |
| 21 | **WorkflowEngine** | `workflow_engine.py` | Task-to-workflow auto-split, step execution, checkpointing, agent handoff, 11-phase lifecycle templates |
| 22 | **TaskCompletionChecker** | `task_completion_checker.py` | DispatchResult/ScheduleResult completion tracking + progress persistence |
| 23 | **CodeMapGenerator** | `code_map_generator.py` | Python AST-based code structure analysis + dependency graph |
| 24 | **DualLayerContextManager** | `dual_layer_context.py` | Project-level + task-level context management with TTL |
| 25 | **SkillRegistry** | `skill_registry.py` | Reusable skill registration + discovery + persistence |
| 26 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic with streaming support + 120s timeout |
| 27 | **Protocols** | `protocols.py` | Protocol interfaces (CacheProvider/RetryProvider/MonitorProvider/MemoryProvider + match_rules/format_rules_as_prompt) + exception hierarchy |
| 28 | **NullProviders** | `null_providers.py` | No-op implementations for all Protocol interfaces (incl. match_rules/format_rules_as_prompt, degradation + test mocking) |
| 29 | **EnhancedWorker** | `enhanced_worker.py` | Worker with protocol-based provider injection (cache/retry/monitor/briefing/memory) + rule injection pipeline |
| 30 | **PerformanceMonitor** | `performance_monitor.py` | P95/P99 response time, CPU/memory tracking, bottleneck detection, Markdown reports |
| 31 | **AgentBriefing** | `agent_briefing.py` | Context-aware briefing generation with priority filtering + persistence |
| 32 | **ConfidenceScorer** | `confidence_score.py` | 5-factor confidence scoring (completeness/certainty/specificity/consistency/model quality) |
| 33 | **LLMCache** | `llm_cache.py` | TTL-based LRU cache with disk persistence (60-80% cost reduction) |
| 34 | **LLMRetry** | `llm_retry.py` | Exponential backoff + circuit breaker + multi-backend fallback |
| 35 | **UsageTracker** | `usage_tracker.py` | Token/cost usage tracking and reporting |
| 36 | **Models** | `models.py` | Shared data models and type definitions |
| 37 | **AntiRationalizationEngine** | `anti_rationalization.py` | Per-role excuse→rebuttal tables (8 universal + 6-7 role-specific) injected via PromptAssembler to prevent quality shortcuts |
| 38 | **VerificationGate** | `verification_gate.py` | Mandatory evidence requirements + 7 Red Flags detection + Prove-It Pattern for completion claims |
| 39 | **IntentWorkflowMapper** | `intent_workflow_mapper.py` | User intent → workflow chain mapping (6 intents × 3 languages) with gate requirements and anti-skip messages |
| 40 | **CLI Lifecycle Commands** | `cli.py` | 6 lifecycle shortcuts (spec/plan/build/test/review/ship) with preset roles/modes/gates inspired by Agent Skills |
| 41 | **StandardizedRoleTemplate** | `standardized_role_template.py` | V2 template format with SKILL.md anatomy: overview, when_to_use, process_steps, rationalizations, red_flags, verification_requirements |
| 42 | **OperationClassifier** | `operation_classifier.py` | Three-tier operation classification (ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN) with 20+ predefined operations and custom overrides |
| 43 | **OutputSlicer** | `output_slicer.py` | Incremental output slicing for large responses: configurable slice size, headers, scratchpad integration |
| 44 | **FiveAxisConsensusEngine** | `five_axis_consensus.py` | Five-axis review consensus (correctness/readability/architecture/security/performance) with weighted voting and strict mode |
| 45 | **CIFeedbackAdapter** | `ci_feedback_adapter.py` | CI results parser (pytest/coverage/lint/build) + context generator + prompt injection for dispatch pipeline |
| 46 | **LifecycleProtocol** | `lifecycle_protocol.py` | Abstract interface for unified lifecycle management (SHORTCUT/FULL/CUSTOM modes) with 11-phase support |
| 47 | **UnifiedGateEngine** | `unified_gate_engine.py` | Unified gate engine integrating VerificationGate + LifecycleProtocol gates with pluggable checkers |
| 48 | **CheckpointManager (Enhanced)** | `checkpoint_manager.py` | Extended with lifecycle state persistence: save/restore/list/delete lifecycle states across sessions |
| 49 | **ShortcutLifecycleAdapter** | `lifecycle_protocol.py` (class) | Plan C adapter implementing LifecycleProtocol using CLI 6-command shortcuts with auto state persistence |
| 50 | **AuthManager** | `auth.py` | Authentication & Authorization: Multi-user RBAC, SHA-256 password hashing, Streamlit login UI, OAuth2 support |
| 51 | **APIServer** | `api_server.py` | FastAPI REST API server: OpenAPI/Swagger docs, CORS middleware, request timing, 10+ endpoints |
| 52 | **APIDataModels** | `api/models.py` | Pydantic validation models: LifecyclePhase, GateResult, MetricsSnapshot, PhaseActionRequest/Result |
| 53 | **LifecycleAPIRoutes** | `api/routes/lifecycle.py` | REST API endpoints: phases list/detail, status, actions execution, command mappings |
| 54 | **MetricsGatesAPIRoutes** | `api/routes/metrics_gates.py` | API endpoints: current/historical metrics, gate status/check, health check |
| 55 | **DispatchModels** | `dispatch_models.py` | DispatchResult + I18N + ROLE_TEMPLATES (extracted from dispatcher) |
| 56 | **DispatchPerformance** | `dispatch_performance.py` | PerformanceMonitor for dispatch pipeline (extracted from dispatcher) |
| 57 | **MultiLevelCache** | `multi_level_cache.py` | Multi-level cache coordinator (memory→disk→Redis) |
| 58 | **HistoryManager** | `history_manager.py` | SQLite time-series storage: metrics snapshots, alert history, API logs, lifecycle events |
| 59 | **StreamlitDashboard** | `dashboard.py` | Interactive web dashboard with authentication, real-time monitoring, phase visualization |
| 60 | **FeedbackControlLoop** | `feedback_control_loop.py` | Sense→Decide→Act→Feedback closed-loop iteration for continuous improvement |
| 61 | **ExecutionGuard** | `execution_guard.py` | Real-time abort guard (timeout/output/keywords) for safe execution |
| 62 | **PerformanceFingerprint** | `performance_fingerprint.py` | Unified fingerprint with TF-IDF similarity search for task matching |
| 63 | **SimilarTaskRecommender** | `similar_task_recommender.py` | History-based task config recommendation using performance data |
| 64 | **AdaptiveRoleSelector** | `adaptive_role_selector.py` | Success-rate-driven adaptive role selection for optimal team composition |
| 65 | **UETestFramework** | `ue_test_framework.py` | UE test framework bridging Tester+PM (Nielsen heuristics + WCAG + cognitive load) |
| 66 | **TechDebtManager** | `tech_debt_manager.py` | Tech debt tracking with CodebaseDebtScanner + knapsack remediation planning |
| 67 | **RoleSkillLoader** | `role_skill_loader.py` | Load SKILL.md methodology frameworks for roles, with security scanning and caching |
| 68 | **SkillContent** | `role_skill_loader.py` (class) | Parsed SKILL.md content with to_prompt_text() for prompt injection |
| 69 | **PM Methodology Skills** | `role_skills/product-manager/` | 5 SKILL.md frameworks: create-prd, opportunity-solution-tree, prioritization-frameworks, assumption-mapping, experiment-design |
| 70 | **EventBus** | `event_bus.py` | Event-driven decoupling for dispatch pipeline (on/emit/off/clear pattern) |
| 71 | **DispatchHooks** | `dispatch_hooks.py` | Extracted post-dispatch hooks from dispatcher (post_dispatch_hooks, post_execution_processing, slice_outputs, check_anchor_drift) |
| 72 | **ResultAssembler** | `dispatch_result_assembler.py` | Extracted result assembly logic from dispatcher |
| 73 | **TwoStageReviewGate** | `two_stage_review_gate.py` | Two-stage code review: spec compliance + code quality, critical findings block |
| 74 | **SeverityRouter** | `severity_router.py` | Severity-based routing with auto-fix loop (max 3 rounds) |
| 75 | **JudgeAgent** | `judge_agent.py` | Finding arbitration: dedup, conflict resolution, confidence filtering, history learning |
| 76 | **MicroTaskPlanner** | `micro_task_planner.py` | 2-5 min micro-task decomposition with file paths + verification commands |
| 77 | **ContentCache** | `content_cache.py` | Unified SHA-256 content cache with sensitive-data filtering |
| 78 | **CodeKnowledgeGraph** | `code_knowledge_graph.py` | Persistent SQLite code structure graph with incremental updates |
| 79 | **CodeGraphQuery** | `code_graph_query.py` | Query interface for code graph (find_symbol/callers/callees/similar) |
| 80 | **CodeGraphStorage** | `code_graph_storage.py` | SQLite storage layer for code graph (symbols/edges/files) |
| 81 | **YagniChecker** | `yagni_checker.py` | YAGNI ladder checker (6 levels, safety tasks never skipped) |
| 82 | **PromptDials** | `prompt_dials.py` | Three-dimension prompt control (verbosity/creativity/risk_tolerance) |
| 83 | **RedesignAuditor** | `redesign_auditor.py` | Third-stage simplicity audit (YAGNI/STDLIB/DUPLICATE/OVERENGINEERING) |
| 84 | **RedesignCheckers** | `redesign_checkers.py` | Detection methods for RedesignAuditor (extracted from redesign_auditor.py) |
| 85 | **DispatchRBAC** | `dispatch_rbac.py` | RBAC permission control integrated with AuthManager |
| 86 | **DispatchAuditLogger** | `dispatch_audit.py` | SHA-256 chain hash audit logging for dispatch lifecycle |
| 87 | **MultiHostAdapter** | `multi_host_adapter.py` | Multi-host adapter (Claude Code/Cursor/Codex/Cline/Trae/Generic) |
| 88 | **PonytailRuleInjector** | `ponytail_rule_injector.py` | Ponytail-style minimal-implementation rules injection (7-rung laziness ladder + never-skip boundary) — V3.10.0 Phase 1 |
| 89 | **ContentRouter + SmartCrusher** | `content_crusher.py` | Structure-aware compression: 6-type detection (JSON/CODE/LOG/HTML/DIFF/PLAIN) + per-type crushers (JSON array → representatives, log → errors+boundaries) — V3.10.0 Phase 2 |
| 90 | **BenchmarkPonytailSmart** | `benchmark_ponytail_smart.py` | Phase 1+2 A/B benchmark suite: 15-task baseline (5 simple + 5 medium + 5 complex) + 6 content-sample A/B evaluation; measures ponytail injection overhead and SMART vs SNIP compression ratio / message preservation / correctness — V3.10.0 Phase 1+2 收尾 |
| 91 | **CCRStore** | `ccr_store.py` | Reversible compression store (SQLite + LRU + TTL + thread-safe): SmartCrusher stores original content and emits trace_id marker; Workers retrieve full original via `devsquad_retrieve(trace_id=...)` — V3.10.0 Phase 3 |
| 92 | **TokenBudget + CompressedScratchpad** | `models_base.py` / `scratchpad.py` | Per-dispatch token budget enforcement + Scratchpad entries with CCRStore trace_id for lazy retrieval of original content — V3.10.0 Phase 3 |
| 93 | **LearnedRuleStore** | `learned_rule_store.py` | Two-tier rule persistence (V3.10.0 Phase 4): tier-1 (confidence ≥0.8) written to `.devsquad.yaml` `quality_control.learned_rules` for auto-injection; tier-2 (0.5–0.8) to `data/tier2/corrections.json` candidate pool; dedup by SHA256 hash; `promote_tier2_to_tier1()` for manual promotion |
| 94 | **RetrospectiveEngine.extract_learned_rules** | `retrospective.py` | Deviation → LearnedRule extraction (V3.10.0 Phase 4): maps `goal_uncovered`/`goal_drift`/`sustained_drift`/low-coverage/improvements to actionable rules with confidence scores; integrates with LearnedRuleStore for persistence. **Dispatch pipeline closed loop**: `_run_retrospective` (in `dispatch_steps_quality_mixin.py`) calls `run()` → `extract_learned_rules()` → `add_rule()` in sequence, triggered on BOTH success and failure (failed tasks prioritized per spec §5.7) |
| 95 | **PromptAssembler learned_rules injection** | `prompt_assembler.py` / `prompt_assembler_formatting_mixin.py` | Auto-injects tier-1 learned rules into Worker prompts (V3.10.0 Phase 4): loads from `.devsquad.yaml`, formats as `## Learned Rules` block, injected in both short-style `_concat_injections` and long-style `parts.append` paths |
| 96 | **LoopKernel** | `loop_engineering/kernel.py` | V4.0.0 P1-1: Loop Engineering 五步闭环核心。Discovery → Handoff → Verification → Persistence → Scheduling。dispatcher 通过 `dispatch_with_loop()` API 访问 |
| 97 | **DiscoveryProbe** | `loop_engineering/discovery_probe.py` | V4.0.0 P1-1: 发现本轮工作项（文件改动/TODO/失败测试/手工指定） |
| 98 | **HandoffAdapter** | `loop_engineering/handoff_adapter.py` | V4.0.0 P1-1: 调用 dispatcher 执行单个 cycle，桥接 loop 与 dispatch pipeline |
| 99 | **IndependentEvaluator** | `loop_engineering/independent_evaluator.py` | V4.0.0 P1-1: 独立结果校验，支持 STRICT/STANDARD/LENIENT 三种严格度 |
| 100 | **UnifiedMemory** | `loop_engineering/unified_memory.py` | V4.0.0 P1-1: 持久化层（SHA256 校验 + 断点续跑 + 备份恢复） |
| 101 | **LoopScheduler** | `loop_engineering/loop_scheduler.py` | V4.0.0 P1-1: 决策 CONTINUE/FIX/STOP_SUCCESS/STOP_FAILURE/HUMAN_CHECKPOINT |
| 102 | **LoopEngineering Models+Protocols** | `loop_engineering/models.py` / `protocols.py` | V4.0.0 P1-1: 数据模型（CycleResult/LoopEvent/RunReport 等）+ Protocol 接口 |
| 103 | **UIUXAnalyzer** | `qa/uiux_analyzer.py` | V4.0.0 P1-2: 4 维度审计（a11y/interaction/layout/ux_antipattern）。dispatcher 通过 `qa_audit_url()` API 访问 |
| 104 | **VisualRegressionChecker** | `qa/visual_regression.py` | V4.0.0 P1-2: PIL ImageChops 像素级 Diff，Playwright 软依赖。dispatcher 通过 `qa_visual_regression()` API 访问 |
| 105 | **UIUX Models** | `qa/models.py` | V4.0.0 P1-2: UIUXAuditReport/UIUXIssue/ChangedRegion/DiffResult 数据模型 |
| 106 | **AdversarialVerifier + RedBlueTeam** | `adversarial_verify.py` | V4.0.0 P2-1: 红队攻击 + 蓝队防御 + 裁判仲裁三阶段对抗验证。通过 `consensus_engine.adversarial_verify()` 访问（集成到 ConsensusEngine） |
| 107 | **DAGVisualizer** | `dashboard/dag_views.py` | V4.0.0 P2-2: Mermaid / JSON / DOT 三格式依赖图可视化，节点高亮 + 循环检测。通过 Dashboard `DAGVisualizer` 类访问 |
| 108 | **AutonomousLoopController** | `autonomous/loop_controller.py` | V4.0.0 P3-1: plan → dev → verify → fix 4 阶段自主迭代，复用 LoopKernel。dispatcher 通过 `dispatch_autonomous()` API 访问 |
| 109 | **RunState** | `autonomous/run_state.py` | V4.0.0 P3-1: 9 状态枚举运行状态管理 |
| 110 | **NotesMemory** | `autonomous/notes_memory.py` | V4.0.0 P3-1: 断点续跑记忆（SHA256 校验 + 备份恢复） |
| 111 | **SmartConfirmation** | `autonomous/smart_confirmation.py` | V4.0.0 P3-1: 三态智能确认（smart/whitelist-only/blacklist-only） |
| 112 | **GitDriver** | `autonomous/git_driver.py` | V4.0.0 P3-1: 自动 git 操作 + 风险等级评估（high/medium/low） |
| 113 | **PluginHotLoader** | `plugins/hot_loader.py` | V4.0.0 P3-2: 三种加载路径（BUILTIN_PLUGINS / Hot Register API / Drop-in 目录扫描）+ 路径穿越三层防护 + reload 回滚 + 审计日志。dispatcher 集成 7 个公共 API（register/unregister/builtin/get/list/scan/reload） |
| 114 | **SleepGuard** | `autonomous/sleep_guard.py` | V4.0.0 P3-1 增补: 无限循环防护（指数退避 + 硬停止）。三状态（NORMAL/BACKOFF/HARD_STOP），连续失败超限自动停止。集成到 AutonomousLoopController |
| 115 | **LLMRoleVoting** | `autonomous/loop_controller.py` | V4.0.0 P3-1 增补: LLM 投票替换模拟投票。`AutonomousConfig.llm_backend` 注入 LLM 后端（如 Moka AI），5 角色 role-specific prompt → JSON 响应解析为 Vote。LLM 失败自动回退 mock。|

---

## Layered Sub-Skill Architecture (V3.6.0)

> DevSquad provides **6 atomic sub-skills** that can be used independently or together.
> Each sub-skill is a thin wrapper (~50 lines) importing existing core modules — no duplicated logic.

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher (7-role orchestration)
├── intent/         → IntentSkill   — IntentWorkflowMapper (6 intents × 3 languages)
├── review/         → ReviewSkill   — FiveAxisConsensusEngine (5-axis code review)
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + test strategy generation
└── retrospective/  → RetroSkill    — RetrospectiveEngine + pattern extraction
```

### Sub-Skill Quick Reference

| Skill | Class | Core Method | Wraps |
|-------|-------|------------|-------|
| `dispatch` | `DispatchSkill` | `run(task, roles, mode)` | MultiAgentDispatcher |
| `intent` | `IntentSkill` | `detect(text, lang)` | IntentWorkflowMapper |
| `review` | `ReviewSkill` | `review(code, axes)` | FiveAxisConsensusEngine |
| `security` | `SecuritySkill` | `scan_input(text)` | InputValidator + OpClassifier |
| `test` | `TestSkill` | `generate_strategy(module)` | TestQualityGuard |
| `retrospective` | `RetrospectiveSkill` | `run_retrospective(results)` | RetrospectiveEngine |

#### Mock Mode Behavior

All 6 sub-skills work **without any API key** in Mock mode:

| Skill | Mock Return Value | Fidelity | Notes |
|-------|-------------------|----------|-------|
| **DispatchSkill** | Pre-built Markdown report with simulated worker results | High | Simulates all 7 roles with realistic content |
| **IntentSkill** | Detected intent + confidence score + workflow suggestion | High | Rule-based keyword matching, deterministic |
| **ReviewSkill** | Five-axis review scores + pass/warn/fail verdict | Medium | Scores follow Gaussian distribution around 0.75 |
| **SecuritySkill** | Scan result: safe/warning/critical + matched patterns | High | Pattern database is real (40 detection patterns) |
| **TestSkill** | Test strategy + quality score + improvement suggestions | Medium | Generated from task keywords |
| **RetrospectiveSkill** | Post-dispatch analysis + pattern extraction | Low-Medium | Empty history on first run, builds up over time |

**Key guarantees in Mock mode:**
- ✅ No network calls — fully offline
- ✅ Deterministic output for same input (except RetrospectiveSkill)
- ✅ Same data structure as real mode (`DispatchResult`, `ReviewResult`, etc.)
- ⚠️ Content is template-based — not LLM-generated
- ⚠️ RetrospectiveSkill needs ≥ 1 real dispatch before showing patterns

**Switching to real mode:**
```python
# Mock mode (default, no config needed)
result = skill.run("your task")

# Real mode (requires API key)
import os
result = skill.run("your task", backend="openai",
                    api_key=os.environ["OPENAI_API_KEY"])
```

### Usage Examples

```python
# Method A: Direct import (recommended for single skill use)
from skills.dispatch.handler import DispatchSkill
result = DispatchSkill().run("Fix login bug", roles=["coder", "tester"])
print(result["success"])  # True

# Method B: Via registry (recommended for dynamic/discovery use)
from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']

skill = get_skill("security")
result = skill.scan_input("DROP TABLE users; --")
print(result["risk_level"])  # "critical"

# Method C: Quick one-liners
from skills.intent.handler import IntentSkill
intent = IntentSkill().detect("修复登录漏洞", lang="zh")
print(intent["intent"])  # "bug_fix"
```

### Registry API

```python
from skills import discover_all
all_skills = discover_all()  # {"dispatch": <DispatchSkill>, ...}
for name, skill in all_skills.items():
    print(f"{name}: {skill.info()['description']}")
```

---

## 🔄 Cybernetics Enhancement (V3.7.2)

> Inspired by upstream TraeMultiAgentSkill v2.5's cybernetics architecture.
> 5 new modules that add feedback loops, execution guards, and intelligence to DevSquad.

| Module | File | Purpose |
|--------|------|---------|
| FeedbackControlLoop | `feedback_control_loop.py` | Sense→Decide→Act→Feedback closed-loop iteration |
| ExecutionGuard | `execution_guard.py` | Real-time abort guard (timeout/output/keywords) |
| PerformanceFingerprint | `performance_fingerprint.py` | Unified fingerprint with TF-IDF similarity search |
| SimilarTaskRecommender | `similar_task_recommender.py` | History-based task config recommendation |
| AdaptiveRoleSelector | `adaptive_role_selector.py` | Success-rate-driven adaptive role selection |

### Quick Start

```python
from scripts.collaboration import (
    FeedbackControlLoop, PerformanceFingerprint,
    SimilarTaskRecommender, AdaptiveRoleSelector, ExecutionGuard
)

# Feedback loop (auto-retry until quality gate passes)
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.run("Design auth system", max_iterations=3)

# Performance fingerprint
fp = PerformanceFingerprint()
fp.record_execution(task, result, timing, roles)
similar = fp.find_similar("Add login page")

# Smart recommendations
recommender = SimilarTaskRecommender(fp)
rec = recommender.recommend("Implement API")
print(rec["recommended_roles"])  # ["architect", "coder"]

# Adaptive role selection
selector = AdaptiveRoleSelector(fp)
roles = selector.select_roles("Fix security bug", intent="bug_fix")
```

---

## Quick Start (Must Follow)

### Installation

```bash
# Install from PyPI (recommended)
pip install devsquad

# With optional dependencies
pip install "devsquad[api]"    # Includes FastAPI + Streamlit dashboard
pip install "devsquad[all]"    # All optional dependencies

# Or install in development mode (for contributors)
pip install -e .
pip install -e ".[api]"       # With API/dashboard dependencies
```

### Method 1: One-Click Collaboration (Recommended for most scenarios)

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Mock mode (default) — returns assembled prompts, no API key needed
disp = MultiAgentDispatcher()
result = disp.dispatch("User's described task")
print(result.to_markdown())
disp.shutdown()
```

### Method 1b: Real AI Output (with LLM Backend)

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend(
    "openai",
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL"),
    model=os.environ.get("OPENAI_MODEL", "gpt-4"),
)
disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("Design user authentication system", roles=["architect", "security"])
print(result.to_markdown())
disp.shutdown()
```

**CLI equivalent**:
```bash
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "Design auth system" -r arch sec --backend openai
```

**When to use Method 1**:
- User requests like "Design XX", "Implement XX", "Analyze XX"
- Need quick multi-role collaboration results
- No need for fine-grained role control

### Method 3: Interactive Web Dashboard (V3.6.0 NEW)

```bash
# Start Streamlit dashboard with authentication
streamlit run scripts/dashboard.py

# Open http://localhost:8501
# Login with: admin / admin123
```

**Features**:
- Real-time lifecycle phase monitoring
- CLI command mapping visualization
- Gate status tracking
- Performance metrics display
- Role-based access control (Admin/Operator/Viewer)

**When to use Method 3**:
- Visual monitoring and management needed
- Team collaboration with multiple users
- Non-technical stakeholders need access

### Method 4: REST API Server (V3.6.0 NEW)

```bash
# Install API dependencies
pip install -e ".[api]"

# Start FastAPI server
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Access Swagger UI: http://localhost:8000/docs
```

**Key Endpoints**:
```bash
# Lifecycle management
curl http://localhost:8000/api/v1/lifecycle/phases | jq
curl http://localhost:8000/api/v1/lifecycle/status | jq

# Metrics & monitoring
curl http://localhost:8000/api/v1/metrics/current | jq
curl http://localhost:8000/api/v1/gates/status | jq

# Health check
curl http://localhost:8000/api/v1/health | jq
```

**When to use Method 4**:
- Integration with external systems (CI/CD, monitoring)
- Programmatic access to DevSquad capabilities
- Building custom UIs on top of DevSquad

### Method 2: Specify Roles

```python
disp = MultiAgentDispatcher()
result = disp.dispatch("Design user auth system", roles=["architect", "tester"])
print(result.to_markdown())
disp.shutdown()
```

### Method 3: Dry-Run Simulation (Analyze only, no execution)

```python
result = disp.dispatch("Test task", dry_run=True)
print(result.summary)
disp.shutdown()
```

### Method 4: Convenience Function (One-liner)

```python
from scripts.collaboration.dispatcher import quick_collaborate
result = quick_collaborate("Help me design a microservice architecture")
print(result.to_markdown())
```

### Method 5: One-Click Startup Script (V3.9.2+)

```bash
# One-click startup — runs 4 phases: env check → DB init → frontend build → service start
./scripts/start.sh

# Launch Streamlit dashboard instead of API server
./scripts/start.sh --dashboard

# Override API port
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# Show help
./scripts/start.sh --help
```

`start.sh` is the unified entry point introduced in V3.9.2 (P0-2). It validates the environment, initializes the database, builds the frontend, and starts the service in one command. Use `requirements.lock` alongside it for reproducible builds (`pip install -r requirements.lock`).

---

## Role System (7 Core Roles)

| Role ID | Name | Trigger Keywords | Core Responsibility |
|---------|------|------------------|---------------------|
| `architect` | Architect | architecture, design, selection, performance, module, interface, data architecture | System architecture, tech selection, performance/security/data architecture |
| `product-manager` | Product Manager | requirements, PRD, user story, competitor, acceptance | Requirements analysis, PRD writing, product planning |
| `security` | Security Expert | security, vulnerability, audit, threat, encryption, OWASP | Threat modeling, vulnerability audit, compliance, security review |
| `tester` | Test Expert | test, quality, acceptance, automation, defect | Test strategy, case design, quality assurance |
| `solo-coder` | Coder | implementation, development, code, fix, optimize, refactor | Feature dev, code review, performance optimization, refactoring |
| `devops` | DevOps Engineer | CI/CD, deploy, monitor, Docker, Kubernetes, infrastructure | CI/CD pipeline, containerization, monitoring, infrastructure |
| `ui-designer` | UI Designer | UI, interface, frontend, visual, prototype, accessibility | UI design, interaction design, prototyping, accessibility |

**CLI short IDs**: `arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`

**Auto-match rule**: When roles are not specified, the system automatically matches the best role combination based on task keywords.

---

## Complete Workflow (When This Skill is Invoked)

### Step 1: Create Dispatcher

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher
import tempfile

work_dir = tempfile.mkdtemp(prefix="mas_v3_")
disp = MultiAgentDispatcher(
    persist_dir=work_dir,
    enable_warmup=True,
    enable_compression=True,
    enable_permission=True,
    enable_memory=True,
    enable_skillify=True,
)
```

### Step 2: Analyze Task & Match Roles

```python
matched = disp.analyze_task(user_task)
for role in matched:
    print(f"{role['name']} (confidence: {role['confidence']:.0%}) - {role['reason']}")
```

### Step 3: Execute Collaboration

```python
result = disp.dispatch(
    task_description=user_task,
    roles=None,          # None=auto match, or specify ["architect", "tester"]
    mode="auto",         # auto/parallel/sequential/consensus
    dry_run=False,       # True=simulation only
)
```

### Step 4: Check Results

```python
print(f"Success: {result.success}")
print(f"Roles: {result.matched_roles}")
print(f"Duration: {result.duration_seconds:.2f}s")
print(result.summary)

if result.worker_results:
    for wr in result.worker_results:
        print(f"[{wr['role']}] {wr['output'][:200]}")
```

### Step 5: Output Markdown Report

```python
report = result.to_markdown()
print(report)
```

### Step 6: Cleanup

```python
disp.shutdown()
```

---

## Advanced Features Guide

### Context Compression (Prevent Long Conversation Overflow)

When conversations get too long, ContextCompressor triggers automatically:
- **Level 1 SNIP**: Fine-grained trimming of old dialogue, preserving key decisions and conclusions
- **Level 2 SessionMemory**: Extract important info to memory then clear context
- **Level 3 FullCompact**: LLM generates one-page summary (most aggressive)

Check compression status:
```python
stats = disp.coordinator.get_compression_stats()
memory = disp.coordinator.get_session_memory()
```

### Permission Guard (Secure Operation Sentinel)

PermissionGuard auto-checks dangerous operations:
- **PLAN level**: Read-only operations only
- **DEFAULT level**: Write ops require confirmation
- **AUTO level**: AI classifier auto-judgment
- **BYPASS level**: Full skip (highest trust)

Permission records stored in `result.permission_checks`.

### Memory Bridge (Cross-session Memory)

MemoryBridge provides 7 memory types:
- `knowledge` — Knowledge entries
- `episodic` — Episodic memories (task execution records)
- `semantic` — Semantic memories
- `feedback` — User feedback
- `pattern` — Successful patterns
- `analysis` — Analysis cases
- `correction` — Correction records

Forgetting curve: 7d=1.0, 30d≈0.8, 60d≈0.5, 90d≈0.3

Check memory status:
```python
status = disp.get_status()
mem_stats = status.get("memory_stats")
```

### Startup Warmup (Reduce Cold-start Latency)

WarmupManager 3-layer warmup:
- **EAGER layer**: Synchronous preload of critical resources (~15ms)
- **ASYNC layer**: Async background warmup (~300ms)
- **LAZY layer**: On-demand loading

Check warmup status:
```python
status = disp.get_status()
warmup = status.get("warmup_metrics")
```

### Skill Learning (Evolve from Success)

Skillifier auto-extracts reusable patterns from successful operation sequences:
```python
proposals = result.skill_proposals
for p in proposals:
    print(f"New Skill candidate: {p['title']} (confidence: {p['confidence']:.0%})")
```

### Consensus Decision (Multi-role Conflict Resolution)

When Workers disagree, ConsensusEngine initiates voting:
- Weighted voting (weighted by role importance)
- Veto power (key role can single-handedly block)
- Escalation to human (mark as pending human decision when consensus unreachable)

Consensus records in `result.consensus_records`.

---

## Dispatch Mode Table

| Mode | Description | Use Case |
|------|-------------|----------|
| `auto` | Auto-select optimal mode | Default recommended |
| `parallel` | All roles execute concurrently | No inter-role dependencies |
| `sequential` | Execute in order | Has dependency chain |
| `consensus` | Force consensus vote after execution | Needs unanimous decision |

---

## System Status Query

```python
status = disp.get_status()
# Returns:
# {
#   "version": "4.1.0",
#   "components": {...},        # Component enabled status
#   "dispatch_count": N,         # Completed dispatch count
#   "scratchpad_stats": {...}, # Blackboard stats
#   "warmup_metrics": {...},    # Warmup metrics (if enabled)
#   "memory_stats": {...},      # Memory stats (if enabled)
# }

history = disp.get_history(limit=10)
# Returns last N dispatch complete results
```

---

## Error Handling

All exceptions are captured inside `DispatchResult`, never thrown:

```python
result = disp.dispatch("Any task")
if not result.success:
    print("Errors:", result.errors)
    print("Summary:", result.summary)
```

Common errors and handling:
- `FILE_CREATE` / Permission related → PermissionGuard blocked, check `result.permission_checks`
- Memory write failure → MemoryBridge storage issue, check directory permissions
- Compression failure → ContextCompressor issue, usually doesn't affect main flow

---

## Language Rules

- Auto-detect user language (Chinese/English/Japanese)
- All output uses same language as user
- Role name mapping: 架构师→Architect, PM→Product Manager, etc.

---

## Testing Iron Rules (⚠️ Must Follow When AI Writes Tests)

> This section addresses three chronic issues in AI-assisted test development.
> **Violating any rule is a serious error.**

### Iron Rule 1: Documentation First — Never Write API Calls From Memory

```
❌ WRONG: Guess parameter names from memory
   result = obj.method(bad_param="value")  # Parameter name is guessed

✅ CORRECT: Read source code to confirm signature first, then write tests
   # 1. Use AST extraction or read source directly to confirm params
   # 2. Use TestQualityGuard for auto-validation
   from scripts.collaboration.test_quality_guard import quick_audit
   report = quick_audit("module.py", "module_test.py")
   print(report.to_markdown())  # Check for API param errors
```

**Mandatory requirements**:
- Before writing any test, must `import` target module and verify actual signature
- Forbidden to use non-existent parameter names (e.g., `id` vs `record_id`)
- Can use `TestQualityGuard.quick_audit()` for auto-detection

### Iron Rule 2: Failure Means Report — Never Modify Assertions to Pass

```
❌ CRITICAL ERROR: Modify assertions when test fails to "pass"
   # Original: assertEqual(result, expected_value)
   # Changed to: assertTrue(result > 0)          ← This is cheating!
   # Changed to: assertGreater(score, 0.0)      ← 0.0 threshold always passes!

✅ CORRECT: Analyze root cause on failure, fix implementation or correct test logic
   # 1. Confirm API signature is correct (Iron Rule 1)
   # 2. Verify test data is reasonable
   # 3. If implementation has real bug → report to architect/developer
   # 4. Only modify assertions if test logic itself is wrong
```

**Forbidden anti-patterns** (auto-detected by TestQualityGuard):
| Anti-pattern | Severity | Description |
|------------|----------|-------------|
| Loose assertion (`assertTrue`) | MINOR | Prefer `assertEqual/assertIn` |
| Invalid threshold (`>0.0`) | MINOR | Must set meaningful thresholds |
| Bare `except:` | MAJOR | Must specify exception type |
| Magic numbers (>999) | MINOR | Extract to named constants |

### Iron Rule 3: Dimension Completeness — Never Only Test Happy Path

Every module's test suite **must** cover these dimensions:

| Dimension | Symbol | Min % | Description |
|-----------|--------|-------|-------------|
| **Happy Path** | ✅ | ≥50% | Normal input → Expected output |
| **Error Case** | 🔴 | **≥15%** | Illegal input / empty / out-of-bounds → Exception or error return |
| **Boundary** | 🟡 | ≥10% | Empty string, zero value, max value, None |
| **Performance** | ⚡ | **≥5%** | Critical path timing baseline (e.g., `<100ms`) |
| **Configuration** | ⚙️ | ≥5% | Different config combinations |
| **Integration** | 🔗 | ≥10% | Inter-module collaboration scenarios |
| **Security** | 🔒 | As needed | Permission / injection / privilege escalation (if security-related) |

**Auto-check tool**:
```python
from scripts.collaboration.test_quality_guard import TestQualityGuard

guard = TestQualityGuard(
    module_path="scripts/collaboration/coordinator.py",
    test_path="scripts/collaboration/coordinator_test.py",
)
report = guard.audit()
print(report.to_markdown())
# Output: Score + Issue list + Dimension coverage + Anti-pattern detection
```

### Test Function Template (Must Follow Format)

```python
def test_<feature>_<scenario>(self):
    """Verify: <What exactly to verify, one sentence>

    Scenario: <What condition triggers this>
    Expected: <What should happen>
    """
    # Arrange - Prepare data and dependencies

    # Act - Execute operation under test

    # Assert - Verify results (use precise assertions, never use assertTrue to bypass)
```

---

## Project Lifecycle: 11-Phase Model (V3.6.0)

> **Definition document**: `docs/prd/lifecycle_phases_definition.md` (authoritative)
> **Review report**: `docs/prd/lifecycle_phases_review.md` (7-role review, 9 suggestions adopted)

### Phase Overview

| # | Phase | Lead | Reviewers | Optional | Gate |
|---|-------|------|-----------|----------|------|
| P1 | Requirements Analysis | pm | arch+test+sec+ui | ❌ | Acceptance criteria quantifiable |
| P2 | Architecture Design | arch | pm+sec+infra | ❌ | Weighted consensus ≥70% |
| P3 | Technical Design | arch+coder | coder+test | ❌ | API specs unambiguous |
| P4 | Data Design | arch+coder | arch+sec | ✅ | 3NF or denormalization justified |
| P5 | Interaction Design | ui | pm+test+sec | ✅ | Core flow usability verified |
| P6 | Security Review | sec | arch+infra | ✅ | No P0/P1 vulns, compliance green |
| P7 | Test Planning | test | arch+sec+infra+pm | ❌ | Test plan review passed |
| P8 | Implementation | coder | arch+sec+test+coder | ❌ | Code review passed, no P0 defects |
| P9 | Test Execution | test | arch+pm+sec+infra | ❌ | Coverage≥80% + P7 plan 100% executed |
| P10 | Deployment & Release | infra | arch+sec+test | ❌ | Deployment drill passed |
| P11 | Operations & Assurance | infra+sec | arch+infra | ✅ | P99<target, alerts 100% |

### Dependency Graph

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

### Lifecycle Templates

| Template | Phases | Use Case |
|----------|--------|----------|
| `full` | P1-P11 | Complete project |
| `backend` | No P5 | Backend services |
| `frontend` | No P4,P6 | Frontend applications |
| `internal_tool` | No P4,P5,P6,P11 | Internal tools |
| `minimal` | P1,P3,P7,P8,P9 | Minimum set |

### Gate Mechanism

- **Mandatory**: Every phase gate must be checked
- **Non-blocking on failure**: Generate gap report → user decides
- **Traceability**: All gate results recorded to checkpoints

### Requirement Change Process

```
Change Request(pm/user) → Impact Analysis(arch+sec+test) → Change Review(all roles) → Approve/Reject → Rollback to affected phase
```

---

## Meta Iron Rule: Documentation First, Trace Everything (⚠️ Supreme Law)

> **文档先行，万事留痕** — This is the supreme iron rule that governs all other rules.
> **Violating this rule is a critical error that invalidates all work done.**

### Core Principle

```
Before any code is written → Plan/Spec document must exist
Before any change is made → Impact analysis must be documented
After any work is done → Results must be recorded in docs
After any decision is made → Rationale must be traceable
```

### Mandatory Requirements

| Phase | Requirement | Verification |
|-------|-------------|--------------|
| **Pre-work** | No code without a spec/plan document | `docs/spec/` or `docs/prd/` has corresponding doc |
| **During work** | All decisions logged with rationale | Commit messages, ADRs, or inline comments explain WHY |
| **Post-work** | All affected docs updated synchronously | Version/module count/test count consistent across all docs |
| **Always** | No orphaned code without documentation origin traceable | Every file's purpose documented in at least one doc |

### What "Documentation First" Means

1. **Spec before implementation**: If there's no SPEC or PRD, write one first. Even a one-paragraph spec beats no spec.
2. **Design before coding**: Architecture decisions recorded before code written.
3. **Test plan before tests**: What to test and why, before writing test code.
4. **Change log before merge**: What changed and why, before pushing.

### What "Trace Everything" Means

1. **Every decision has a why**: Code comments, commit messages, ADRs — pick at least one.
2. **Every file has an owner/purpose**: Why does this file exist? Document it.
3. **Every change has a trail**: Git history + doc updates = full audit trail.
4. **No stealth changes**: Nothing committed without a corresponding doc update.

### Enforcement

- CI check: `docs/` directory must have updated files matching code changes
- Review gate: PR reviewer checks doc sync status
- Consensus: Coordinator verifies documentation completeness before approval
- Retroactively: Work done without prior docs must be backfilled immediately

---

## Delivery Workflow Iron Rules (⚠️ Must Execute After Every Push)

> This section defines the standard closed-loop workflow: Implement→Test→Walkthrough→Annotate→Docs→Git.
> **Violating any step is a serious error.**

### Iron Rule: Mandatory Post-push Closed Loop

```
Implement → Test(Regression All) → Code Walkthrough → Annotate → Docs Update → Cleanup → Git Push
```

**Mandatory actions per step**:

| Step | Mandatory Action | Verification Criteria |
|------|-----------------|----------------------|
| **1. Implement** | Write/modify code per Plan/Spec | Feature complete, no TODO placeholders |
| **2. Test** | New tests + full regression | 0 failure, 0 error, 100% pass |
| **3. Walkthrough** | Read every new/modified line in each file | Understand each method's I/O and edge behavior |
| **4. Annotate** | Public method docstring (Args/Returns) + key logic inline comments | No "naked methods" (public method without docstring) |
| **5. Docs Update** | **Sync ALL relevant docs** (see checklist below) | All docs have consistent version/module count/test count, no stale content |
| **6. Cleanup** | Delete process docs / temp docs / temp code | No residual `_tmp`/`_draft`/`_old` files |
| **7. Git Push** | commit message includes version+change summary+test count | push success, visible on remote |

### Iron Rule: Doc Coverage Checklist (Step 5 must check ALL categories)

> **Principle: All doc types related to the change must be updated — requirements/design/test/API/install/SKILL/etc.**

| Doc Category | Check Item | Relevant? |
|-------------|-----------|----------|
| **Requirements** | `docs/spec/*.md` — Spec status update (pending→in-progress→implemented) | ✅ Must check |
| **Design** | `docs/architecture/*.md` — Architecture evolution record, Phase additions | ✅ Must check |
| **Planning** | `docs/planning/*.md` — Consensus action items checked, extension notes | ✅ Must check |
| **SKILL Docs** | `SKILL.md` — Module table, test table, version history, rules | ✅ Must check |
| **Project Overview** | `README.md` (EN) / `README-CN.md` (CN) / `README-JP.md` (JP) — Version, modules, timeline | ✅ Must check |
| **Changelog** | `CHANGELOG.md` — New version entries (Added/Changed/Fixed) | ✅ Must check |
| **Status Doc** | `docs/PROJECT_STATUS.md` — Current version, module list, test summary | ✅ Must check |
| **Config** | `CONFIGURATION.md` — New external integration config options | 🔍 If has integrations |
| **API Docs** | Update interface docs if API changes | 🔍 If API changed |
| **Install Deps** | `INSTALL.md` / `requirements.txt` — Update if new deps | 🔍 If new deps |
| **Test Plan** | Reflect new test coverage scope | 🔍 For major changes |

### Iron Rule: Cleanup Rules (Step 6)

> **Principle: Process docs and temporary artifacts should NOT remain in codebase.**

| Cleanup Category | Action | Examples |
|-----------------|--------|---------|
| Process analysis scripts | Keep valuable ones, delete one-off | `*_review.py`, `*_analysis.py` → evaluate then decide |
| Temp debug files | **Must delete** | `test_*.py.tmp`, `debug_*.py`, `*.bak.*` |
| Draft/deprecated docs | **Must delete** | `*_DRAFT.md`, `*_old.md`, `*_tmp.md` |
| Unused placeholder code | **Must delete** or replace with real impl | `pass # TODO`, `raise NotImplementedError` |
| Duplicate/redundant files | Merge or delete | Keep only latest version of same doc |

### Annotation Standards (Language Separation)

| Category | Language |
|----------|----------|
| **Documentation (SKILL.md / README.md)** | **English** |
| **README-CN.md** | **Chinese (简体)** |
| **README-JP.md** | **Japanese (日本語)** |
| **Code docstring** | **English** (Args / Returns / Example) |
| **Inline comments** | **English** (explaining business logic) |

---

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Core (Dispatcher+Coordinator+Worker+Scratchpad+Consensus) | 39 | ✅ PASS |
| Role Mapping (RoleMatcher+alias resolution+bilingual keywords) | 25 | ✅ PASS |
| Upstream (Checkpoint+SemanticMatcher+Workflow+CompletionChecker) | 35 | ✅ PASS |
| MCEAdapter (CarryMem integration+type mapping+graceful degrade) | 30 | ✅ PASS |
| Contract Tests (Protocols+NullProviders+Cache+Monitor+Security) | 234 | ✅ PASS |
| V3.5 Integration (Lifecycle+ChangeRequest+Templates) | 7 | ✅ PASS |
| **P0-1 AntiRationalizationEngine** | **39** | **✅ PASS** |
| **P0-2 VerificationGate** | **42** | **✅ PASS** |
| **P0-3 IntentWorkflowMapper** | **58** | **✅ PASS** |
| **P0-4 CLI Lifecycle Commands** | **28** | **✅ PASS** |
| **P1-1 StandardizedRoleTemplate** | **27** | **✅ PASS** |
| **P1-2 OperationClassifier** | **29** | **✅ PASS** |
| **P1-3 OutputSlicer** | **26** | **✅ PASS** |
| **P1-4 FiveAxisConsensusEngine** | **29** | **✅ PASS** |
| **P1-5 CIFeedbackAdapter** | **22** | **✅ PASS** |
| **V3.8.0 ContentCache** | **32** | **✅ PASS** |
| **V3.8.0 StepNodeTypes (NodeType)** | **14** | **✅ PASS** |
| **V3.8.0 RetryJitter (JitterStrategy)** | **9** | **✅ PASS** |
| **V3.8.0 TwoStageReviewGate** | **40** | **✅ PASS** |
| **V3.8.0 SeverityRouter** | **51** | **✅ PASS** |
| **V3.8.0 JudgeAgent** | **33** | **✅ PASS** |
| **V3.8.0 MicroTaskPlanner** | **47** | **✅ PASS** |
| **V3.9.0 CodeKnowledgeGraph** | **40** | **✅ PASS** |
| **V3.9.0 DispatchRBAC** | **17** | **✅ PASS** |
| **V3.9.0 DispatchAuditLogger** | **24** | **✅ PASS** |
| **V3.9.0 YagniChecker** | **34** | **✅ PASS** |
| **V3.9.0 PromptDials** | **33** | **✅ PASS** |
| **V3.9.0 RedesignAuditor** | **28** | **✅ PASS** |
| **V3.9.0 E2E + Integration + Performance** | **68** | **✅ PASS** |
| **V3.10.0 PonytailRuleInjector** | **17** | **✅ PASS** |
| **V3.10.0 ContentRouter + SmartCrusher** | **46** | **✅ PASS** |
| **V3.10.0 Coordinator SMART-first Integration** | **22** | **✅ PASS** |
| **V3.10.0 Benchmark Ponytail+Smart A/B** | **20** | **✅ PASS** |
| **V4.0.0 Loop Engineering (P1-1)** | **35** | **✅ PASS** |
| **V4.0.0 UI/UX 巡检 + Visual Regression (P1-2)** | **53** | **✅ PASS** |
| **V4.0.0 Adversarial 验证 (P2-1)** | **39** | **✅ PASS** |
| **V4.0.0 DAG 可视化 (P2-2)** | **39** | **✅ PASS** |
| **V4.0.0 Autonomous (P3-1)** | **111** | **✅ PASS** |
| **V4.0.0 插件热加载 (P3-2)** | **48** | **✅ PASS** |
| **V4.0.0 E2E 用户旅程 + 集成 + 幽灵防御** | **42** | **✅ PASS** |
| **Total** | **4651+ (CI authoritative)** | **✅ ALL PASS** |

---

## Version History

- **v4.0.0** (2026-07-07): MAJOR 版本升级，借鉴上游 TraeMultiAgentSkill v2.7 理念新增 6 个特性（P1-P3），全面接入 dispatch pipeline，无幽灵功能。**P1-1 Loop Engineering** 五步闭环（Discovery→Handoff→Verification→Persistence→Scheduling，`dispatch_with_loop()` API，9 模块）。**P1-2 UI/UX 巡检**（4 维度审计 + PIL 像素 diff，`qa_audit_url()`/`qa_visual_regression()` API，3 模块）。**P2-1 Adversarial 验证**（红蓝对抗 + 裁判仲裁，通过 `consensus_engine.adversarial_verify()` 访问）。**P2-2 DAG 可视化**（Mermaid/JSON/DOT 三格式，通过 Dashboard `DAGVisualizer` 访问）。**P3-1 Autonomous**（plan→dev→verify→ fix 4 阶段自主迭代，复用 LoopKernel，不绕过 HC-2 共识门，`dispatch_autonomous()` API，5 模块，95 tests）。**P3-2 插件热加载**（3 加载路径 + 路径穿越三层防护 + reload 回滚 + 审计日志，7 dispatcher 公共 API，48 tests 覆盖 spec 8.6 全部 10 个 E2E 场景）。173+ core modules, 3400+ tests passing (CI authoritative)
- **v3.10.0-dev** (2026-07-01): PonytailRuleInjector (7-rung laziness ladder: YAGNI→reuse→stdlib→platform→installed dep→one line→minimal code, 17 tests) + PromptAssembler integration via `_concat_injections(style)` (compression styles skip ponytail) + `.devsquad.yaml` config (minimal_implementation/ponytail_markers) + ContentRouter+SmartCrusher (6-type detection + JSON/log structure-aware crush, 46 tests) + CompressionLevel.SMART (preserve all msgs, compress content only, 88.7% token reduction) + Phase 1+2 finishing items: BenchmarkPonytailSmart suite (15-task baseline + 6-sample A/B, 20 tests; measured ponytail ~240 tokens overhead, SMART 89.1% JSON / 82.0% log reduction) + Coordinator SMART-first integration (`smart_compression` flag + `apply_smart_compression()` method, 22 tests; SMART pre-compression runs before destructive compression for zero information loss) + PONYTAIL_MARKER_GUIDE.md (10-section marker convention doc) + 150+ core modules + 3007 tests passing (CI authoritative)
- **v3.9.2** (2026-06-30): Auto LLM fallback (auto backend tries real LLM first, falls back to mock) + Dashboard split (1087 lines → 8-module package) + SQLite-backed dispatch audit persistence by default + P3 cleanup (magic numbers extracted + narrowed exceptions) + P0 security fixes (PBKDF2 password hashing + start.sh + requirements.lock) + Loop Engineering implementation assessment + 149+ core modules + 2857+ tests passing (CI authoritative)
- **v3.9.1** (2026-06-23): File splits (code_knowledge_graph 511→346, redesign_auditor 550→229) + RedesignAuditor false-positive fix (builtins preserved, sequential naming, blank lines excluded from dead code) + MultiHostAdapter (6 host types: Claude Code/Cursor/Codex/Cline/Trae/Generic, 32 tests) + CI E2E release tag gate + build depends on lint+security + mypy blocking (551→0 errors) + 118 core modules + 2605 tests passing (CI authoritative)
- **v3.9.0** (2026-06-22): CodeKnowledgeGraph (SQLite-backed symbols/edges/files storage, 40 tests) + MCP codegraph_explore tools (symbol/callers/callees/traversal/status) + YagniChecker (34 tests) + PromptDials (verbosity/creativity dials, 33 tests) + RedesignAuditor third-stage simplicity audit (YAGNI/STDLIB/DUPLICATE/OVERENGINEERING, 28 tests) + DispatchRBAC integration with AuthManager (17 tests) + DispatchAuditLogger SHA-256 chain hash (24 tests) + V3.9.0 E2E/Integration/Performance (68 tests) + P0 security fixes (audit hash length-prefixed fields, RBAC open-mode warning) + P1 thread safety (CodeGraphStorage check_same_thread=False + Lock) + 94+ core modules + 2591 tests passing
- **v3.8.0** (2026-06-21): Two-Stage Review Gate (spec compliance + code quality, 40 tests) + Severity Router with auto-fix loop (51 tests) + Judge Agent with history learning (33 tests) + Micro-Task Planner (2-5 min decomposition, 47 tests) + Content Cache with sensitive-data filtering (32 tests) + Jitter Strategies (NONE/EQUAL/FULL/DECORRELATED, 9 tests) + NodeType classification (DETERMINISTIC/LLM/HYBRID, 14 tests) + V3.8 Planning Docs (5 docs, 2482 lines) + 86+ core modules + 2339 tests passing + maturity 65%→72%
- **v3.7.2** (2026-06-16): EventBus + Dispatcher split (1660→706 lines, -57%) + Mixin→Composition (3 Mixins eliminated) + f-string logger eliminated (166 fixes) + EnhancedWorker bug fix (_do_work type mismatch) + config_loader dead code removed + skillifier parasitic coupling refactored (8 _storage._xxx→public interface) + broad except narrowed (29 fixes) + DispatchPerformanceMonitor renamed + .gitignore updated + 2115 tests passing
- **v3.7.0** (2026-06-15): RoleSkillLoader + PM Methodology Skills (5 SKILL.md: create-prd/opportunity-solution-tree/prioritization-frameworks/assumption-mapping/experiment-design) + suggested_next_steps in dispatch results + SKILL.md security scanner (7 patterns) + 76 core modules + 2109 tests passing
- **v3.6.9** (2026-06-14): UETestFramework bridging Tester+PM (Nielsen heuristics + WCAG + cognitive load) + TechDebtManager with CodebaseDebtScanner + knapsack remediation planning + 75 core modules + version sync to 3.6.9
- **v3.6.8** (2026-06-13): FeedbackControlLoop auto mode + LLM refinement + AdaptiveRoleSelector/SimilarTaskRecommender integrated into RoleMatcher + ExecutionGuard integrated into EnhancedWorker + Lifecycle phase trace in dispatch pipeline + RBAC checks on get_history/audit_quality/export_metrics/clear_history + TestQualityGuard default enabled + enable_feedback_loop default False→"auto" + Removed AlertManager (unused) + 13+ files version sync to 3.6.8 + Fixed except Exception: pass silent error swallowing + Fixed assertTrue test anti-patterns + 1940 passed, 11 skipped, 3 xpassed
- **v3.6.7** (2026-06-07): Redis Cache L2 Backend + Async Dispatch (asyncio.gather) + Dispatcher Refactor (788→18 step methods) + DispatchResult Bug Fix (5 missing fields) + 1855+ tests passing
- **v3.6.6** (2026-06-02): Three-Layer Funnel Documentation + Framework Comparison (COMPARISON.md) + User Journey E2E Testing (16 tests, 100% pass) + InputValidator (40 detection patterns) + Security Fix (removed hardcoded token) + 1672+ tests passing
- **v3.6.5** (2026-05-28): RBAC Engine (Preview) + Audit Logger (Preview) + Multi-Tenancy Manager (Preview) + Sensitive Data Masker (Preview) + AsyncIO Transformation (2x throughput) + Redis Cache Integration (95%+ hit rate) + Prometheus Monitoring (12 metrics) + E2E Test Suite (27 cases, 100% pass) + 65% maturity (honest assessment)
- **v3.4.2** (2026-05-03): P1 Enhancement Complete - RoleTemplateMarket V2(27 tests) + OperationClassifier(29 tests) + OutputSlicer(26 tests) + FiveAxisConsensusEngine(29 tests) + CIFeedbackAdapter(22 tests) + 166 new tests + 53 core modules
- **v3.4.1** (2026-05-03): Agent Skills Quality Framework (P0) - AntiRationalizationEngine(39 tests) + VerificationGate(42 tests) + IntentWorkflowMapper(58 tests) + CLI Lifecycle Commands(28 tests) + 167 new tests + Google Agent Skills integration + 49 core modules
- **v3.5.0** (2026-05-02): 11-Phase Project Lifecycle (full/backend/frontend/internal_tool/minimal templates) + requirement change management + gate mechanism with gap reporting + WorkflowEngine lifecycle support + Natural Language Rule Collection (RuleCollector) + 748+ tests passing
- **v3.3** (2026-04-17): WorkBuddy Claw Integration - WorkBuddyClawSource(read-only bridge/INDEX search/daily logs/AI news feed) + Dispatcher AI News auto-inject + Annotation Standards (EN docs/docstring/inline) + Code comment audit (all EN) + MCE v0.4 support (tenant/permission) + Multi-language README (EN/CN/JP) + 33 new tests
- **v3.2** (2026-04-17): MVP Three Lines - E2E Full Demo(10-step flow/CLI) + Dispatcher UX Enhancement(structured/compact/detailed 3-format report) + MCEAdapter Memory Classification Adapter(lazy-load/graceful-degrade) + Delivery Workflow Iron Rule
- **v3.1** (2026-04-16): Prompt Optimization System - Dynamic Prompt Assembly(3 variants) + Skillify Closed-loop Feedback(A/B promotion) + Compression-Aware Adaptation
- **v3.0.1** (2026-04-16): Comprehensive code annotation (6 core modules 100% docstring coverage) + TestQualityGuard integration
- **v3.0** (2026-04-16): Complete redesign to Coordinator/Worker/Scratchpad architecture, 11 core modules (incl. Dispatcher+TestQualityGuard), ~710 tests all passing
- **v2.5** (2026-04-06): Memory Classification Engine integration
- **v2.4** (2026-04-01~03): Vibe Coding + Core Rules + Lifecycle recognition
- **v2.3** (2026-03-28): Multi-role code walkthrough + 3D visualization
- **v2.2** (2026-03-21): Long-running Agent (Checkpoint + Handoff)
- **v2.1** (2026-03-17): Dual-layer context + AI semantic matching
- **v2.0/v1.0** (2026-03-16): Initial release
