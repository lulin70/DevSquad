# Module Reference — DevSquad Core Modules (193+)

> This document is the authoritative reference for DevSquad's 193+ core modules, test coverage matrix, and advanced feature behaviors. It was extracted from `SKILL.md` during the V4.5.0 modular split (PRD §10.2) so that `SKILL.md` remains a concise overview.

## Architecture Overview (193+ Core Modules)

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
| 44 | **FiveAxisConsensusEngine** | `five_axis_consensus.py` | Five-axis review consensus (correctness/readability/architecture/security/performance) with weighted voting and strict mode. **V4.3.0 Phase 3 P3-4**: 新增 `evaluate(artifacts, reviewer_id="heuristic")` 实例方法 + `FiveAxisEvaluationResult` dataclass + `evaluate_artifacts()` 模块函数 + 5 个 heuristic 评估器（`_evaluate_correctness` / `_evaluate_readability` / `_evaluate_architecture` / `_evaluate_security` / `_evaluate_performance`），支持非 LLM heuristic 5 轴评估 + Markdown 报告章节（`to_markdown()`）。E2E-07 脱 xfail |
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
| 116 | **TodoDriftMonitor** | `collaboration/todo_drift_monitor.py` | V4.3.0 P0-2: 技术债持续监控。`scan_tech_debt()` / `diff_with_tracker()` / `report_new_debts()` 三函数，tokenize 区分真实注释，pre-commit 阻塞 + CI lint 集成 |
| 117 | **PonytailDebtCollector** | `collaboration/ponytail_debt_collector.py` | V4.3.0 P1-1: `# ponytail:` 注释标记扫描 + 债务分类（UPGRADABLE 有升级路径 / ROT_RISK 腐烂风险） |
| 118 | **RequirementTracer** | `collaboration/requirement_tracer.py` | V4.3.0 P1-1: `[REQ-XXX]` 标记解析 + 中文关键词提取 + 实现检测 |
| 119 | **RollbackStrategy** | `loop_engineering/rollback_strategy.py` | V4.3.0 P1-4: LoopKernel 失败阶段精准回退映射（D1/D2/D4/D5/D6→DEV, D3→TEST）+ 独立硬上限 `max_rollback_iterations=3` + `_accumulated_artifacts` 跨迭代传递 |
| 120 | **UIUXSubitems** | `qa/uiux_subitems.py` | V4.3.0 P1-5: 4 维度 20 子项注册表（a11y/interaction/layout/ux_antipattern）+ `audit_subitems()` 返回 PASS/WARN/FAIL/NOT_IMPLEMENTED |
| 121 | **V43DashboardPanels** | `dashboard/v43_panels.py` | V4.3.0 P1-6: Dashboard 状态可视化 4 面板（Ponytail 模式 / Loop 回退 / Plugin 事件 / 技术债状态） |
| 122 | **DeploymentComplianceChecker** | `deployment_compliance_checker.py` | V4.3.0 P0-3 (Phase 0): P10 lifecycle gate 部署合规检查。3 条硬约束规则（基础版禁云端 / 专业版仅受控主机 / nginx 默认 server 服务官网）+ `lifecycle_gate_check()` API + 集成到 `UnifiedGateEngine.check_compliance()`。防违规部署兜底（2026-07-12 事故后续） |
| 123 | **DependencyHallucinationChecker** | `dependency_hallucination_checker.py` | V4.3.0 P1-7 (Phase 1): 防 Slopsquatting 供应链攻击。6 步检测流水线（黑名单>白名单>Levenshtein typo>混淆规则>后缀模式>UNKNOWN）+ 三级分类（KNOWN_GOOD/SUSPICIOUS/UNKNOWN）+ fail-secure 数据集加载 + `security_scan_dependencies()` API。集成到 SecuritySkill.scan_dependencies() + dispatch post-worker hook（`scan_worker_outputs_for_hallucinated_deps`），自动扫描 worker 输出代码 + 调用计数器防幽灵 + Markdown 报告"安全检查"章节。来源：USENIX 2025 + arXiv:2605.17062 + Socket/Snyk 研究 |
| 124 | **OutputValidator (Full Integration)** | `output_validator.py` + `dispatch_steps.py::PostDispatchPipeline` + `dispatch_hooks.py` (re-export) | V4.3.0 P1-8 (Phase 2): LLM 输出安全检测完整集成（升级 V4.1.2 骨架为生产级）。4 类检测：`code_injection` / `sensitive_info` (API keys / DB passwords / JWT) / `path_leak` / `prompt_injection`（18 子模式）。双模式：`blocking`（high-severity 阻断 + raise `OutputValidationBlockedError`）+ `non_blocking`（redact + 继续）。集成到 `PostDispatchPipeline._validate_outputs()` post-worker hook，支持 `list[str]` (E2E 契约) + `list[dict]` (向后兼容) 双模式输入。`OutputValidationPipelineResult` 聚合 blocked/findings/audit_logged/redacted_outputs。审计日志复用 `DispatchAuditLogger`，新增 `output_validation_finding` / `output_validation_blocked` 事件类型。E2E-05 脱 xfail。防幽灵：post-worker hook 自然触发 + 集成测试 `test_dispatch_with_output_validation.py` 9 测试类 + 红队 `test_output_validator_redteam.py` 25 用例 |
| 125 | **QualityCalibrationGate** | `quality_calibration_gate.py` | V4.3.2 Gate 0: 仪器校准门。验证 ConfidenceScorer + FiveAxisConsensusEngine 能否正确排序 4 个已知质量输出（gold > llm > filler > empty）+ gap ≥ 0.15。`run_calibration_gate()` 返回 `CalibrationGateResult`（passed/scores/ordering_correct/gap_gold_filler/diagnostics）+ `to_markdown()`。是 Slice 1 薄切片探针的前置条件。fail-secure 数据集加载。防幽灵：`_call_counter` 计数器 |
| 126 | **RoleSpecificMockBackend** | `role_specific_mock_backend.py` | V4.3.2: 角色特定 Mock 后端。三臂对照中的第二臂（frozen_mock vs role_specific_mock vs llm）。`role_specific=False` 时与 MockBackend 行为一致（向后兼容）；`role_specific=True` 时追加 7 角色模板片段（architect/product-manager/security/tester/solo-coder/devops/ui-designer）。不修改现有 MockBackend |
| 127 | **QualityProbeSlice** | `quality_probe_slice.py` | V4.3.2 Slice 1: 薄切片质量探针。3 任务 × 3 臂 × n 采样对比，量化 LLM vs Mock 输出质量差距。`run_probe_slice(llm_backend, n_samples)` 返回 `ProbeSliceReport`（gate_passed/task_results/mean_stddev/signal_strength/conclusion/llm_arm_skipped）+ `to_markdown()`。信号强度判定：significant (>0.15) / marginal (>0.05) / noise (≤0.05) / calibration_failed。Gate 0 前置检查 |
| 128 | **QualityDecisionReportGenerator** | `generate_quality_decision_report.py` | V4.3.2: CLI 入口，运行 Gate 0 + Slice 1，生成 Markdown 决策报告到 `docs/analysis/{date}_LLM_vs_Mock_Quality_Report.md`。`--no-llm` flag 支持 2 臂对比。支持 MOKA_API_KEY 环境变量自动注入 LLM 后端 |
| 129 | **RiskRegister** | `collaboration/risk_register.py` | V4.4.0 P0-1: PMP 风险管理。风险注册 + 7 角色加权评估（probability × impact）+ 4 种响应策略（规避/转移/减轻/接受）+ `GateType.RISK_CHECK` 门禁（exposure ≥ 0.36 阻断）+ `export_markdown()` 报告章节。集成到 dispatcher `_activate_v440_modules()` + `UnifiedGateEngine._check_risk` |
| 130 | **ViewpointRegistry** | `collaboration/viewpoint_registry.py` | V4.4.0 P0-2: TOGAF 架构视点。7 角色绑定正式视点（architect=functional+data / security=threat / tester=quality / solo-coder=implementation / devops=deployment / product-manager=requirements / ui-designer=interaction）+ `is_orthogonal()` 正交性判断 + `check_consistency()` 矛盾检测。ConsensusEngine SPLIT 仲裁依据 |
| 131 | **ErrorBudgetTracker** | `collaboration/error_budget_tracker.py` | V4.4.0 P1-1: SRE 错误预算。SLO 99.9% 默认 + `calculate()` 计算 remaining_budget + `GateType.ERROR_BUDGET` P10 门禁（预算耗尽阻断功能部署）+ `burn_rate()` 消耗速率。集成到 `UnifiedGateEngine.check_deployment()` |
| 132 | **GapAnalyzer** | `collaboration/gap_analyzer.py` | V4.4.0 P1-2: TOGAF 差距分析。`analyze(current, target)` 识别架构差距 + `prioritize()` 按优先级排序 + `generate_roadmap()` Markdown 路线图 + `track()` 记录闭环进度 + `suggest_scheduler_decision()` 驱动 LoopScheduler CONTINUE/STOP。可读 gap id（基于 work_package 关键词）|
| 133 | **DoraMetricsCollector** | `collaboration/dora_metrics_collector.py` | V4.4.0 P2-1: DORA 指标。4 个交付指标（Deployment Frequency / Lead Time / Change Failure Rate / MTTR）+ `collect_from_git()` 从 git log 解析 + `collect_from_dispatch()` 从 dispatch 记录 + `GateType.DORA_CHECK` P11 门禁（CFR > 15% 触发架构评审）+ `rating()` Elite/High/Medium/Low 评级 |
| 134-184 | *(V4.5.0 cross-session continuity modules)* | `collaboration/scratchpad_history_store.py` etc. | V4.5.0: ScratchpadHistoryStore / AgentIdentity / WorkflowTrace / GitContext / SkillProvider (Builtin + MCP) / OutputStyle / FileBundler / SessionResume CLI + supporting modules. See `CHANGELOG.md` [4.5.0] section for the full list. (Numbering reserved for future detailed entries; behavior documented in V4.5.0 release notes.) |
| 186 | **ApprovalGate** | `collaboration/approval_gate.py` | V4.5.1: 用户级审批门。外部操作（PR 评论 / Issue 状态变更 / PR 评审）的用户级审批机制。`ApprovalCallback` Protocol + `ApprovalRequest`/`ApprovalResult` dataclass。回调异常时 **fail-closed**（拒绝操作并记录错误原因）。无回调配置时自动批准（向后兼容，不影响现有工作流）。所有审批决策记入 `_records` 审计链 + `export_markdown()` 报告章节。防幽灵：模块级 `_call_counter` + 16 单元测试（`tests/test_approval_gate.py`）。集成到 dispatcher `_activate_approval_gate()`（early_return + normal 双路径） |
| 187 | **ConnectorFramework** | `collaboration/connector_framework.py` | V4.5.1: 外部系统连接器框架。Protocol-based 接口（`Connector` Protocol：`create_pr_comment` / `update_issue_state` / `submit_pr_review` / `get_operations` / `export_markdown`）。首个具体实现 `GitHubConnector` 支持 api/cli/simulation 三种模式：① `simulation=True` 强制仿真（安全，无网络）② `GITHUB_TOKEN` 环境变量或 `token` 参数 → api 模式（REST API）③ `gh` CLI 可用 → cli 模式（subprocess）④ fallback → simulation。`ConnectorOperation` dataclass 记录操作。防幽灵：模块级 `_call_counter` + 12 E2E 测试（AG-1 到 AG-8 反幽灵验证）。集成到 dispatcher `_activate_connector()`（强制 `simulation=True`，无网络调用） |

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
| **V4.1.0 P0-1 Tautological test detection** | **24** | **✅ PASS** |
| **V4.1.0 P0-2 GLOSSARY + ADR system** | **11** | **✅ PASS** |
| **V4.1.0 P0-3 Deletion test** | **10** | **✅ PASS** |
| **V4.1.0 P0-4 Red-capable gate + DEBUG tag** | **12** | **✅ PASS** |
| **V4.1.0 P0-5 Deep/shallow vocabulary** | **16** | **✅ PASS** |
| **V4.1.0 P0-6 No-op test + failure modes** | **10** | **✅ PASS** |
| **V4.1.0 P0-7 Grilling one-question-at-a-time** | **31** | **✅ PASS** |
| **V4.1.0 UI-P0-1 DeterministicRuleEngine (46 rules)** | **57** | **✅ PASS** |
| **V4.1.0 UI-P0-2 TasteDials** | **66** | **✅ PASS** |
| **V4.1.0 UI-P0-3 DESIGN.md protocol** | **8** | **✅ PASS** |
| **V4.1.0 Module 10 grilling injection fix** | **3** | **✅ PASS** |
| **V4.1.0 P1-1 Flow vs standalone** | **22** | **✅ PASS** |
| **V4.1.0 P1-2 Grill-with-docs + P1-6 Stateless** | **15** | **✅ PASS** |
| **V4.1.0 P1-3 Triage labels** | **27** | **✅ PASS** |
| **V4.1.0 P1-4 Vertical slice + dep ordering** | **22** | **✅ PASS** |
| **V4.1.0 P1-5 Seam-first design + P1-UI-2 7 Pillars** | **12** | **✅ PASS** |
| **V4.1.0 P1-7 Handoff redaction + suggested-skills** | **22** | **✅ PASS** |
| **V4.1.0 P1-UI-1 Anti-pattern bans (6 rules)** | **22** | **✅ PASS** |
| **V4.1.0 P1-UI-3 OKLCH color space** | **23** | **✅ PASS** |
| **V4.1.0 P2-3 Git guardrails** | **57** | **✅ PASS** |
| **V4.1.0 P2-UI-4 4pt grid spacing** | **17** | **✅ PASS** |
| **V4.1.0 Atomic Skill: tautological-test-detection** | **7** | **✅ PASS** |
| **V4.1.0 Atomic Skill: git-guardrails** | **7** | **✅ PASS** |
| **V4.1.0 Atomic Skill: grilling-interview** | **9** | **✅ PASS** |
| **V4.1.0 Atomic Skill: codebase-audit (coder)** | **9** | **✅ PASS** |
| **V4.1.0 Atomic Skill: uiux-audit standalone usage (enhanced)** | **4** | **✅ PASS** |
| **V4.2.1 P2-1 PrototypeSkill** | **28** | **✅ PASS** |
| **V4.2.1 P2-2 TeachSkill** | **57** | **✅ PASS** |
| **V4.2.1 P2-4 Pre-commit Hook Version Lock** | **34** | **✅ PASS** |
| **V4.2.1 P2-UI-1 CLI Command Classifier** | **61** | **✅ PASS** |
| **V4.2.1 P2-UI-2 Dashboard Live Browser Mode** | **28** | **✅ PASS** |
| **V4.2.1 P2-UI-3 Meta-skill Layering** | **27** | **✅ PASS** |
| **V4.2.1 Test Pyramid Lift (Contract + Integration)** | **+727** | **✅ PASS** |
| **V4.3.0 P0-1 pickle Migration Phase 1** | **15+** | **✅ PASS** |
| **V4.3.0 P0-2 TodoDriftMonitor** | **15+** | **✅ PASS** |
| **V4.3.0 P1-1 Ponytail dual-mode + DebtCollector + RequirementTracer** | **40+** | **✅ PASS** |
| **V4.3.0 P1-4 LoopKernel RollbackStrategy** | **12+** | **✅ PASS** |
| **V4.3.0 P1-5 UIUX Subitems Audit** | **26** | **✅ PASS** |
| **V4.3.0 P1-6 Dashboard V4.3.0 Panels** | **15** | **✅ PASS** |
| **V4.3.0 P2-1 pickle Fallback Complete Removal** | **5+** | **✅ PASS** |
| **V4.3.0 P0-3 DeploymentComplianceChecker (unit)** | **32** | **✅ PASS** |
| **V4.3.0 P0-3 P10 Gate Integration (T6)** | **12** | **✅ PASS** |
| **V4.3.0 P0-4 SDLC E2E Skeletons (Phase 0)** | **8 (2 passed, 6 xfail)** | **✅ PASS** |
| **V4.3.0 P1-7 DependencyHallucinationChecker (unit)** | **50** | **✅ PASS** |
| **V4.3.0 P1-7 SecuritySkill Integration** | **15** | **✅ PASS** |
| **V4.3.0 P1-7 Dispatch Hook Integration** | **15** | **✅ PASS** |
| **V4.3.0 P1-7 Red-team Tests (22 vectors)** | **22** | **✅ PASS** |
| **V4.3.0 P1-8 OutputValidator Pipeline Result + Exception** | **10+ classes** | **✅ PASS** |
| **V4.3.0 P1-8 PostDispatchPipeline Integration** | **9 classes** | **✅ PASS** |
| **V4.3.0 P1-8 Red-team Tests (25 vectors)** | **25** | **✅ PASS** |
| **V4.3.0 P1-8 E2E-05 Un-xfail** | **1 (was xfail)** | **✅ PASS** |
| **V4.3.0 P3-1 Async Coverage Enhancement** | **14 (5 classes)** | **✅ PASS** |
| **V4.3.0 P3-2 Red-team Library (4 scenarios × 5 modules)** | **20** | **✅ PASS** |
| **V4.3.0 P3-3 DispatchAuditLogger Markdown/Query/Tamper** | **10 (3 classes)** | **✅ PASS** |
| **V4.3.0 P3-4 FiveAxisConsensusEngine.evaluate() Heuristic** | **29 (8 classes)** | **✅ PASS** |
| **V4.3.0 P3-4 E2E-07 Un-xfail** | **1 (was xfail)** | **✅ PASS** |
| **V4.3.0 P3-5 Real User Journey E2E (PM/Dev/Ops)** | **9 (3 classes)** | **✅ PASS** |
| **V4.3.2 QualityCalibrationGate (Gate 0)** | **8 (4 classes)** | **✅ PASS** |
| **V4.3.2 QualityProbeSlice (Slice 1)** | **8 (4 classes)** | **✅ PASS** |
| **V4.3.2 RoleSpecificMockBackend** | **8 (4 classes)** | **✅ PASS** |
| **V4.3.3 P0-P3 Enhancement E2E Skeletons (xfail TDD)** | **13 (6 files, V4.4.0 xfail)** | **✅ XFAIL→XPASS** |
| **V4.4.0 P0-P3 Enhancement Modules (5 new modules)** | **13 E2E xpass + anti-ghost** | **✅ PASS** |
| **Total** | **8200+ CI / 107 e2e + 1244 integration** | **✅ ALL PASS** |

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
#   "version": "4.1.3",
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

Back to [SKILL.md](../../SKILL.md)
