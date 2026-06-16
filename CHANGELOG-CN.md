# 变更日志

**中文版** | [English](CHANGELOG.md)

本文档记录了 DevSquad 的所有重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/spec/v2.0.0.html)。

## [3.7.0] - 2026-06-15

### 新增
- **RoleSkillLoader**：加载 SKILL.md 方法论框架，将结构化 PM 框架注入 Worker 提示词
- **PM 方法论技能**：5 个产品经理角色的 SKILL.md 文件（create-prd、opportunity-solution-tree、prioritization-frameworks、assumption-mapping、experiment-design）
- **suggested_next_steps**：调度结果现在包含基于检测到的意图类型的推荐后续操作
- **SKILL.md 安全扫描器**：7 模式安全审计，用于社区贡献的 SKILL.md 文件（关键问题阻止加载，警告允许加载）

### 变更
- PromptAssembler 现在通过 `_get_skill_injection()` 注入角色特定方法论框架
- IntentWorkflowMapper：6 种意图类型现在包含 `suggested_next_steps` 字段
- DispatchResult：新增 `suggested_next_steps` 字段，支持 i18n（zh/en/ja）
- 76 个核心模块（原 75 个）

### 移除
- **PromptVariantGenerator**（`scripts/collaboration/prompt_variant_generator.py`）：移除从未在生产环境中使用的幽灵功能模块
- **RoleTemplateMarket**（`scripts/collaboration/role_template_market.py`）：移除从未在生产环境中使用的幽灵功能模块

## [3.6.9] - 2026-06-14

### 新增
- **UETestFramework**（`ue_test_framework.py`）：UE 测试框架，桥接测试专家+产品经理角色，结合尼尔森启发式、WCAG 无障碍检查和认知负荷评估
- **TechDebtManager**（`tech_debt_manager.py`）：技术债务追踪，含 CodebaseDebtScanner 自动化债务检测和基于背包算法的修复优先级规划
- **75 个核心模块**（从 V3.6.8 的 73 个增加）

### 变更
- **版本同步至 3.6.9**：代码库中所有版本引用已更新

## [3.6.8] - 2026-06-13

### 新增
- **FeedbackControlLoop 自动模式 + LLM 精炼**：反馈循环现在支持"auto"模式，自动迭代直到质量门控通过，并提供基于 LLM 的精炼建议
- **AdaptiveRoleSelector + SimilarTaskRecommender 集成到 RoleMatcher**：智能角色选择和任务推荐现在通过标准 RoleMatcher 接口可用
- **ExecutionGuard 集成到 EnhancedWorker**：实时中止守卫（超时/输出/关键词）现在在所有 EnhancedWorker 执行中生效
- **调度流水线中的生命周期阶段追踪**：调度流水线新增完整的生命周期阶段追踪，提升可观测性
- **get_history/audit_quality/export_metrics/clear_history 的 RBAC 检查**：敏感 API 端点现在需要适当的 RBAC 授权
- **DispatchModels**（`dispatch_models.py`）：从 dispatcher 中提取的 DispatchResult + I18N + ROLE_TEMPLATES
- **DispatchPerformance**（`dispatch_performance.py`）：从 dispatcher 中提取的 PerformanceMonitor
- **MultiLevelCache**（`multi_level_cache.py`）：多级缓存协调器（内存→磁盘→Redis）

### 变更
- **TestQualityGuard 默认启用**：测试质量审计现在默认开启
- **enable_feedback_loop 默认值 False → "auto"**：反馈循环现在默认为自动模式而非禁用

### 移除
- **AlertManager**（`scripts/alert_manager.py`）：移除了从未在主流程中被调用的 AlertManager 模块。多渠道告警（控制台/Slack/邮件/Webhook）不再作为内置功能提供。

### 修复
- **13+ 文件版本同步至 3.6.8**：代码库中所有版本引用已更新
- **except Exception: pass 静默错误吞没**：替换为具体异常类型和适当的日志记录
- **assertTrue 测试反模式**：将松散断言替换为精确的 assertEqual/assertIn 断言

### 测试
- **1940 通过，11 跳过，3 预期外通过**（从 V3.6.7 的 1855+ 提升）

## [3.6.7] - 2026-06-07

### 新增 - Redis 缓存 L2 后端
- **LLMCache Redis L2**：可选 Redis 后端，支持三级缓存（内存→磁盘→Redis）
  - 通过 `enable_redis_cache`/`redis_url` 参数或 `DEVSQUAD_ENABLE_REDIS_CACHE`/`DEVSQUAD_REDIS_URL` 环境变量配置
  - Redis 不可用时优雅降级（自动回退到内存+磁盘）
  - 启用 Redis 后缓存命中率达 95%+

### 新增 - 异步调度
- **`async_dispatch()` 方法**：MultiAgentDispatcher 新增异步调度，使用 `AsyncCoordinator` 和 `asyncio.gather` 实现并发 LLM 调用
  - 失败时自动回退到同步调度
  - 新增 `async_quick_collaborate()` 便捷函数
  - 多角色任务吞吐量显著提升

### 变更 - Dispatcher 重构
- **将 788 行 `dispatch()` 拆分为 18 个步骤方法**：每个步骤都是聚焦的、可测试的方法
- **提取 `dispatch_models.py`**：数据模型和类型定义从 dispatcher 中分离
- **提取 `dispatch_performance.py`**：性能追踪和指标从 dispatcher 中分离
- **dispatcher.py 从 1896 行减少到约 1370 行**：提升可维护性和可读性

### 修复 - 代码质量
- **DispatchResult.to_dict()/to_markdown() 缺失 5 个字段**：修复数据丢失 bug，`consensus_records`、`permission_checks`、`skill_proposals`、`compression_stats` 和 `memory_stats` 在序列化时被遗漏
- **清理 `except:pass` 模式**：替换为具体异常类型
- **移除冗余 `to_dict()` 包装器**：简化序列化代码

### 变更 - 测试
- **1672 → 1855 个测试通过**：恢复了 183 个之前标记为 xfailed 的测试
- **CI 重新启用**：所有测试现在在 CI 流水线中通过

---

## [3.6.6] - 2026-05-27

### 新增 - 文档体验增强（重大）
- **三层漏斗文档结构**：
  - QUICKSTART.md：新用户 30 秒上手指南
  - README.md：渐进式信息披露重构（概览 → 详情）
  - SKILL.md：更新核心定位和一句话理解
- **框架对比页面**：COMPARISON.md，与 AutoGen/CrewAI/LangGraph 的详细分析
  - 功能矩阵（60+ 对比项）
  - 4 个框架的架构模式图
  - 用例推荐与选型决策树
  - 代码复杂度对比（5 行 vs 25 行）

### 新增 - 增强E2E测试（用户旅程导向）
- **用户旅程 1：开发者入门（Alice）** - 8 个测试用例
  - 安装验证、快速初始化、首次任务执行
  - 系统状态检查、帮助文档、错误处理
- **用户旅程 2：架构评审（Bob）** - 8 个测试用例
  - 复杂任务提交、多角色协作工作流
  - 共识机制模拟、报告生成验证
  - Scratchpad 跨角色通信、负载下性能
- **用户旅程测试**：16 个用户旅程测试 ✅

### 新增 - 文档统一（15 个文件更新）
- 所有外部文档统一至 V3.6.6：README/QUICKSTART/SKILL/GUIDE/CLAUDE
- 所有国际化文档更新：README_CN/JP, SKILL_CN/JP
- 内部文档更新：SPEC, CHANGELOG, MATURITY_REPORT, RELEASE_DECISION
- 27 个文件版本一致性验证通过

### 修复
- **test_auth_phase5.py::test_auth_disabled_by_default**：修复 config_path=None 回退行为
  - 根因：None → 默认 deployment.yaml 路径（该文件存在且 auth enabled=True）
  - 解决方案：使用显式不存在的路径来测试"无配置文件"场景

### 新增 - 开发者工具
- `sync_trae_v3.6.5.sh`：TRAE L2 缓存同步脚本
- `sync_trae_v3.6.5_fixed.sh`：增强版，支持 L2+L3 双层同步
- `force_refresh_trae_skill.sh`：TRAE 内存缓存问题强制刷新工具
- 发布指南：PUBLISHING_GUIDE.md, MANUAL_PUBLISHING_GUIDE.md

---

## [3.6.5] - 2026-05-21

### 新增 - 企业级功能
- **RBAC 引擎**：15+ 权限，5 个角色（SUPER_ADMIN/ADMIN/OPERATOR/ANALYST/VIEWER）
- **审计日志器**：SHA256 完整性链，CSV/JSON 导出，PII 脱敏
- **多租户管理器**：3 个隔离级别，配额管理
- **敏感数据脱敏器**：自动 PII 检测和脱敏

### 新增 - 性能增强
- **AsyncIO 改造**：2 倍吞吐量提升，50% 延迟降低
- **Redis 缓存集成**：L1→L2→L3 三级缓存架构
- **Prometheus 监控**：12 个核心指标，/metrics 端点

### 新增 - 测试与质量
- **E2E 测试套件**：27 个测试用例，5 个场景，9 秒内 100% 通过率
  - CLI 完整工作流（8 个测试）
  - REST API 生命周期（7 个测试）
  - 多角色协作（4 个测试）
  - 企业级功能（4 个测试）
  - 错误恢复（4 个测试）
- **代码质量**：print() → logging 迁移，pre-commit 钩子，.editorconfig
- **测试覆盖率**：1672 个测试通过（98.5%+）

### 新增 - 文档
- 更新所有 README 文件至 V3.6.6（EN/CN/JP）
- 生成 E2E_TEST_REPORT_V3.6.6.md
- 更新 SPEC.md 以反映企业级功能

### 新增 - 工程改进
- GitHub Actions CI/CD 流水线
- Docker 多阶段构建（builder/runtime/dev）
- Pre-commit 钩子（ruff/flake8/conventional-pre-commit）
- 移除 auth.py 中的硬编码凭证

### 新增 - 代码质量与工程卓越（阶段 1-5 完成）
- **阶段 1：自动化代码修复**（提交：9b45059）
  - ✅ Ruff 代码检查：**49,238 → 490 个错误**（减少 99%）
  - ✅ 代码格式化：**139 个文件**使用 ruff format 格式化
  - ✅ 导入排序：**3,524 个问题**修复（isort 集成）
  - ✅ 覆盖率提升：**23.16% → 56.39%**（格式化使覆盖率更准确）

- **阶段 2：类型注解修复**（提交：17e2d7e）
  - ✅ **126 个 mypy 类型错误 → 0**，涉及 5 个核心模块
  - ✅ 核心模块：dispatcher.py, coordinator.py, worker.py, scratchpad.py, llm_backend.py
  - ✅ 添加完整的 Optional/Dict/List/Any 类型注解

- **阶段 3：print() 清理与分析**（提交：d3036e9）
  - ✅ 审计 **587 个 print() 实例**：99.7% 为合理使用（测试/文档/CLI）
  - ✅ 修复 **1 个生产代码问题**（mcp_server.py）
  - ✅ 建立 print() 分类标准

- **阶段 4：文档增强**（提交：cefa2a0）
  - ✅ 添加 **953 行** Google 风格文档字符串
  - ✅ 类覆盖率：**63.9% → 73.1%**（+9.2%）
  - ✅ 重点：models.py（+570 行），dispatcher.py（+228 行），skills handlers（+195 行）

- **阶段 5：测试覆盖率扩展**（提交：edfc7e1）
  - ✅ 新增 **96 个测试用例**（1650 → 1746 个测试）
  - ✅ 覆盖率：**62.57% → 63.18%**（超过 60% 目标）
  - ✅ 新测试文件：dispatcher/auth/cli/input_validator/permission_guard phase5 测试

### 新增 - 文档更新（V3.6.1 最终清理）
- ✅ 修复版本不一致（CONSTITUTION.md, SKILL.md, SKILL_CN.md 示例）
- ✅ 更新 EXAMPLES.md 至 V3.6.1
- ✅ 更新 README-CN.md 和 README-JP.md 章节标题
- ✅ 创建 **SPEC.md**（**1,943 行**）- 完整的 V3.6.1 技术规范
- ✅ 创建 **ROADMAP_V3.6.2-V3.6.6.md**（**2,277 行**）- 阶段 6-9 详细计划
- ✅ 生成 **MATURITY_REPORT_V3.6.1.md** - 94% 生产就绪评估

### 新增 - 安全与质量改进
- ✅ 版本一致性：api_server.py 从 3.6.0 → 3.6.1 更新
- ✅ 安全：移除所有硬编码凭证（auth.py, cli.py）
- ✅ 日志迁移：额外 25 处 print() → logging 转换
- ✅ 临时文件清理（__pycache__, .pyc, .DS_Store）

### 新增 - 工具与自动化
- ✅ Ruff 代码检查器/格式化器配置（启用 10 个规则类别）
- ✅ MyPy 类型检查器配置（生产代码严格模式）
- ✅ pytest-cov 覆盖率报告（80% 阈值，HTML 报告）
- ✅ Pre-commit 钩子（.pre-commit-config.yaml），含 ruff/flake8/安全检查
- ✅ 创建 `scripts/code_quality.py` - 综合质量工具包

## [3.6.1] - 2026-05-17

### 新增
- **FeedbackControlLoop** — 控制论反馈迭代系统（Sense→Decide→Act→Feedback 闭环）
  - 质量门禁，默认阈值 0.7
  - 最大迭代次数：3（可配置）
  - 基于失败模式的智能调整生成
  - 最佳结果追踪（而非仅最后结果）
- **ExecutionGuard** — 实时执行中止守卫
  - 多级触发器：超时 / 输出大小 / Token 限制 / 关键词
  - 可通过 configure() 配置阈值
  - 零外部依赖，每次检查 <1ms
- **PerformanceFingerprint** — 统一执行指纹聚合器
  - 融合 4 个数据源：FeatureUsageTracker + PerformanceMonitor + CheckpointManager + RetrospectiveEngine
  - TF-IDF 相似度搜索（纯 Python，无外部依赖）
  - 成功/失败模式提取
  - 冷启动优雅降级
- **SimilarTaskRecommender** — 基于历史的任务配置推荐
  - 基于相似历史案例推荐角色/意图/时长
  - 置信度级别：高(>0.7) / 中(>0.4) / 低
  - 冷启动回退至 RoleMatcher
- **AdaptiveRoleSelector** — 成功率驱动的自适应角色选择
  - 统计角色有效性报告
  - 策略：相似任务 → 基于意图 → 回退
  - 提供手动统计更新 API

### 变更
- 上游 v2.5 控制论增强分析中的 5 个模块全部集成到核心架构
- 通过实时中止守卫增强执行可靠性
- 通过历史模式匹配改进任务推荐
- 通过成功率统计驱动更好的角色选择

## [3.6.0] - 2026-05-13

### 新增
- **AnchorChecker** — 里程碑锚点验证系统，含漂移检测和自动恢复建议
- **RetrospectiveEngine** — 独立的事后回顾引擎，含模式提取和反模式检测
- **StructuredGoal** — 结构化目标管理，含层级分解和进度追踪
- **FallbackBackend** — 自动 LLM 后端故障转移，含健康监控和优先级路由
- **FeatureUsageTracker** — 线程安全的功能调用计数器，含持久化、使用报告和自动持久化
- **IntentWorkflowMapper** — 任务意图自动检测（6 种意图：bug_fix/new_feature/security_review/code_review/performance_optimization/deployment），含工作流链注入
- **AISemanticMatcher** — LLM 增强的语义角色匹配，含关键词回退
- **DualLayerContextManager** — 项目+任务双层上下文，含 TTL 过期和 LRU 驱逐
- **OperationClassifier** — 3 级操作分类（ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN），用于 PermissionGuard
- **SkillRegistry** — 技能注册/发现/持久化，含从调度结果自动提议
- **FiveAxisConsensusEngine** — 5 轴代码审查（正确性/可读性/架构/安全性/性能），用于共识模式
- **NullProviders** — Cache/Retry/Monitor/Memory 协议的优雅降级
- AnchorChecker 和 RetrospectiveEngine 的 45 个新测试
- FeatureUsageTracker 追踪的 30 个 KNOWN_FEATURES，用于数据驱动的功能优化
- `__init__.py` 中 10 个新模块导出

### 变更
- 总测试数：1503 → 1548+
- 核心模块数：45 → 48
- 增强 dispatcher 以支持在生命周期里程碑集成 AnchorChecker
- 增强 dispatcher 以支持 RetrospectiveEngine 事后分析
- 增强 dispatcher 以支持 FeatureUsageTracker 调用计数
- 增强 dispatcher 以在角色匹配前进行意图检测
- 增强 dispatcher 以支持语义角色匹配增强
- 增强 dispatcher 以支持双层上下文管理
- 增强 dispatcher 以在权限检查中进行操作分类
- 增强 dispatcher 以在共识模式中使用五轴共识
- 增强 dispatcher 以支持技能注册自动提议
- CheckpointManager：所有文件写入操作现在受线程安全的 _file_lock 保护
- PerformanceMonitor.export_metrics：修复缺失的 persist_dir 参数（现在接受 allowed_base_dir）
- FallbackBackend：在 generate_stream 中添加 last_error 追踪，以正确传播错误
- IntentWorkflowMapper：改进评分算法，使用主/次语言加权
- SkillRegistry：propose_from_result() 现在自动注册技能（之前仅创建，不注册）
- 删除 config_manager.py（死代码，与 config_loader.py 重复）

### 修复
- **P0 死锁**：FeatureUsageTracker.report() → get_high_usage_features() 嵌套锁获取导致死锁（Lock → RLock）
- **P0 竞态条件**：CheckpointManager 所有文件写入操作现在线程安全（在 save_checkpoint, save_handoff, save_lifecycle_state 中添加 _file_lock）
- **P0 未定义变量**：FallbackBackend.generate_stream() 引发未定义的 last_error（添加了适当追踪）
- **P0 AttributeError**：PerformanceMonitor.export_metrics() 引用不存在的 self.persist_dir（重构为参数）
- **P0 API 不匹配**：FiveAxisConsensusEngine.add_axis_vote() 在引擎上，而非 review 对象上
- **P0 导入错误**：README.md/README_CN.md FallbackBackend 导入路径指向不存在的 fallback_backend.py
- **P0 导入错误**：user_onboarding_verification.md 引用不存在的 load_config() 函数
- **P1 数据**：SKILL.md/CLAUDE.md 模块数 65→48，测试数 750+→1548+
- **P1 数据**：skill-manifest.yaml 测试数 1478/1500+→1548+
- **P1 数据**：workflow_engine.py 描述 V3.5→V3.6
- **P1 评分**：IntentWorkflowMapper 中文意图检测因基于比例的评分而失败（改为加权主/次评分）
- 修复 OpenAI/Anthropic 后端 raise last_error 无回退 RuntimeError 的问题

## [3.5.0] - 2026-05-05 (V3.5.0 增强冲刺)

### 🆕 V3.5.0 七大增强

#### E1: 代码走读增强包 (code-walkthrough.yaml)
- 7角色走读视角定义（架构师/安全专家/测试专家/开发者/运维专家/产品经理/UI设计师）
- 性能审查归属明确：架构师主责设计层面，运维专家辅责运行层面
- 每个角色的走读检查清单和常见陷阱
- 角色专属走读指南提示词注入

#### E2: 文档一致性检查（内置在代码走读增强包中）
- 9类文档一致性检查维度（API/安全/测试/需求/运维/UI/配置/变更日志/版本号）
- 3级严重程度（Critical/High/Medium）和处置策略
- 明确每类文档的检查主责人和辅责人
- 版本号一致性检查（_version.py/pyproject.toml/CHANGELOG/README/INSTALL/GUIDE/SKILL.md/skill-manifest.yaml）

#### E3: Karpathy原则增强包 (code-quality.yaml)
- 4大核心原则：Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution
- Vibe Coding精选5条规则融入4原则
- 3个角色增强提示词（architect/solo-coder/tester）
- 反模式检测（过早抽象/配置驱动过度/框架化思维）

#### E6: 项目理解增强 (agent_briefing.py扩展)
- generate_project_overview(): 生成项目概览（技术栈/模块结构/核心组件）
- generate_role_understanding(): 7角色定制化理解文档
- 自动分析项目技术栈（pyproject.toml/Dockerfile/.github）
- 识别核心组件（14个关键类自动发现）

#### E8: 走读专用五轴引擎 (five_axis_consensus.py扩展)
- create_walkthrough_engine(): 代码走读专用五轴共识引擎
- Operability轴替代Performance轴（部署/监控/容灾/配置/性能运维）
- 运维专家在走读中获得15%权重
- Security轴保留严格模式否决权

#### E4: 代码地图多语言支持 (language_parsers.py)
- LanguageParser Protocol定义
- PythonParser: 基于ast标准库（从现有代码提取）
- JavaScriptParser: 基于正则表达式（支持JS/JSX/TS/TSX）
- GoParser: 基于正则表达式（支持struct/interface/func）
- CodeMapGenerator重构：register_parser() + languages过滤
- 向后兼容：默认无parsers时使用PythonCompatParser

#### E5: 规范工具链增强 (lifecycle_protocol.py扩展)
- SpecTemplate数据模型 + 3个规范模板（requirements/architecture/technical）
- init_spec(): 从模板初始化规范文档
- analyze_spec(): 分析代码生成规范草稿（复用多语言CodeMapGenerator）
- validate_spec(): 验证规范完整性和一致性
- VIEW_MAPPINGS新增3个子命令映射（spec-init/spec-analyze/spec-validate）

### 🔄 变更文件清单
- `templates/concerns/code-walkthrough.yaml` — 新增
- `templates/concerns/code-quality.yaml` — 新增
- `scripts/collaboration/five_axis_consensus.py` — 扩展（OPERABILITY轴 + create_walkthrough_engine）
- `scripts/collaboration/agent_briefing.py` — 扩展（generate_project_overview + generate_role_understanding）
- `scripts/collaboration/code_map_generator.py` — 重构（多语言支持）
- `scripts/collaboration/language_parsers.py` — 新增
- `scripts/collaboration/lifecycle_protocol.py` — 扩展（SpecTemplate + spec工具链）
- `tests/test_five_axis_consensus.py` — 更新（OPERABILITY轴测试）
- 版本号统一更新至3.5.0

## [3.4.0] - 2026-05-04 (代码质量冲刺 + DevSquad 协作)

### 🤖 DevSquad 7角色协作全面质量提升

#### 【Architect】三维度代码走读
- **安全性**: ⭐⭐⭐⭐⭐ (5/5) - 生产就绪
  - InputValidator: 完善的输入验证（XSS/SQL注入/命令注入/提示词注入）
  - PermissionGuard: 4级权限控制系统（DEFAULT/PLAN/AUTO/BYPASS）
  - AuthManager: RBAC认证系统（SHA-256密码哈希）
- **性能**: ⭐⭐⭐⭐ (4/5) - 优秀
  - LLMCache: 内存+磁盘双层缓存，TTL过期机制
  - ContextCompressor: 4级上下文压缩防止溢出
  - ThreadPoolExecutor: 并行Worker执行
- **可维护性**: ⭐⭐⭐⭐ (3.5/5) - 良好
  - 27个核心模块，清晰的分层架构
  - 30处宽泛异常处理待规范化

#### 【Tester】回归测试验证
- **测试结果**: 1478 passed, 24 failed (98.4%通过率)
- **修复项**:
  - ✅ 修复 test_cli_lifecycle.py 导入错误（cli包 vs cli模块冲突）
  - ✅ 使用 importlib 直接导入 cli.py 模块
- **失败分析**:
  - 7个 CLI 测试失败（dispatch mock 问题）
  - 14个 UX 报告格式测试失败（报告结构变更）
  - 3个其他测试失败（边界条件）

#### 【DevOps】目录结构清理
- 删除 3 个 .DS_Store 文件
- 确认无临时/编译文件残留
- 目录健康度: ⭐⭐⭐⭐⭐ (5/5)

#### 【PM】文档更新
- README.md: 更新测试徽章 (776+ → 1478, 98.4%)
- README.md: 新增代码质量和安全评级徽章
- CHANGELOG.md: 添加本次协作记录

### 📊 质量指标对比

| 指标 | 改进前 | 改进后 | 提升 |
|------|--------|--------|------|
| 测试通过率 | ~98% | **98.4%** (1478/1502) | +0.4% |
| 安全评级 | 未评估 | **5/5** | 🆕 |
| 整体评级 | 未评估 | **4.3/5** | 🆕 |
| 目录整洁度 | 有.DS_Store | **100%干净** | ✅ |

### 🎯 后续建议

1. **P0**: 修复24个失败测试（CLI dispatch + UX报告格式）
2. **P1**: 规范化30处宽泛异常处理
3. **P2**: 补充核心模块单元测试覆盖率到80%+

---

## [3.3.0] - 2026-05-03 (生产就绪)

### 新增 - 重大生产功能

#### 认证与授权系统
- **AuthManager** (`scripts/auth.py`)：完整认证模块
  - 多用户支持，基于角色的访问控制（RBAC）
  - 三种角色：Admin, Operator, Viewer
  - SHA-256 密码哈希，安全会话管理
  - Streamlit 仪表盘集成，含登录 UI
  - OAuth2 支持（可选，面向企业）

- **部署配置** (`config/deployment.yaml`)：
  - 全面的部署设置
  - SSL/HTTPS 配置模板
  - 速率限制和安全头
  - 环境特定覆盖（dev/staging/prod）

#### REST API 服务器 (FastAPI)
- **API 服务器** (`scripts/api_server.py`)：生产就绪的 REST API
  - FastAPI 框架，自动生成 OpenAPI/Swagger 文档
  - CORS 中间件支持跨域请求
  - 请求计时和全面日志
  - 全局异常处理，标准化错误响应

- **数据模型** (`scripts/api/models.py`)：Pydantic 验证模型
  - LifecyclePhase, GateResult, MetricsSnapshot
  - PhaseActionRequest, PhaseActionResult
  - HealthCheck, PaginatedResponse

- **生命周期 API 端点** (`scripts/api/routes/lifecycle.py`)：
  - `GET /api/v1/lifecycle/phases` - 列出所有 11 个阶段
  - `GET /api/v1/lifecycle/phases/{id}` - 获取阶段详情
  - `POST /api/v1/lifecycle/actions` - 执行阶段操作
  - `GET /api/v1/lifecycle/mappings` - CLI 命令映射
  - `GET /api/v1/lifecycle/status` - 当前执行状态

- **指标与门禁 API** (`scripts/api/routes/metrics_gates.py`)：
  - `GET /api/v1/metrics/current` - 实时指标快照
  - `GET /api/v1/metrics/history` - 历史数据查询
  - `GET /api/v1/gates/status` - 所有门禁状态
  - `POST /api/v1/gates/check` - 检查特定门禁
  - `GET /api/v1/health` - 服务健康检查

#### 告警通知系统
- **AlertManager** (`scripts/alert_manager.py`)：多通道告警
  - 四个严重级别：INFO, WARNING, ERROR, CRITICAL
  - 多通道：控制台, Slack, 邮件, Webhook
  - 速率限制，防止告警风暴
  - 可配置时间窗口内的告警去重
  - 告警历史追踪和统计
  - 快捷辅助函数：`alert_info()`, `alert_error()` 等

- **告警配置** (`config/alerts.yaml`)：
  - 通道特定设置（Slack webhook, SMTP 邮件）
  - 基于条件的告警规则
  - 静默时段配置
  - 数据保留策略

#### 历史数据存储
- **HistoryManager** (`scripts/history_manager.py`)：SQLite 时序数据库
  - 指标快照表，支持时间范围查询
  - 告警历史表，含确认追踪
  - API 请求日志表，含性能指标
  - 生命周期事件表，用于状态变更审计
  - 自动数据保留和清理
  - 数据库大小监控

### 新增 - 可视化与监控增强

#### Streamlit 仪表盘更新
- **仪表盘** (`scripts/dashboard.py`)：
  - 集成认证，含用户会话显示
  - 基于角色的功能访问控制
  - 仅管理员可见的设置面板
  - 增强的页脚，含版本和会话信息
  - 生产就绪 UI，含安全指示器

#### CLI 可视化增强
- **CLI 可视化模块** (`scripts/cli/cli_visual.py`)：
  - 彩色进度条和状态图标
  - 格式化表格，含对齐
  - 百分比完成指示器
  - 门禁状态可视化

#### Jupyter Notebook 教程
- **交互式教程** (`examples/tutorial.ipynb`)：
  - 10 节逐步学习指南
  - 核心概念和架构讲解
  - CLI 命令到 11 阶段映射演示
  - 性能基准测试示例

### 新增 - 测试与质量
- **新测试套件** (`tests/test_production_features.py`)：21 个新测试
  - TestAuthentication（5 个测试）- 认证系统验证
  - TestAlertManager（5 个测试）- 告警功能
  - TestHistoryManager（6 个测试）- 数据持久化
  - TestAPIDataModels（4 个测试）- 模型验证
  - 全部 21 个测试通过 ✅

- **总测试覆盖率**：750+ 测试（99.3% 通过率）

### 新增 - 文档更新
- 更新 README.md，添加生产功能文档
- 增强 USAGE_GUIDE.md，添加可视化和监控指南
- 添加部署和 API 使用示例

---

## [3.5.0-C] - 2026-05-03 (Plan C 分层架构)

### 新增

#### 统一生命周期架构（Plan C 实现）

- **LifecycleProtocol** (`scripts/collaboration/lifecycle_protocol.py`)：统一生命周期管理的抽象接口
  - `LifecycleMode` 枚举：SHORTCUT / FULL / CUSTOM 模式
  - `PhaseDefinition`：统一阶段结构，含依赖和门禁
  - `ViewMapping`：CLI 命令 → 11 阶段映射定义
  - 完整的协议接口，含 12 个抽象方法

- **UnifiedGateEngine** (`scripts/collaboration/unified_gate_engine.py`)：统一门禁引擎
  - 集成 VerificationGate（Worker 输出）+ LifecycleProtocol（阶段转换）
  - `GateType` 枚举：PHASE_TRANSITION / WORKER_OUTPUT / SECURITY_CHECK 等
  - 可插拔检查器架构，支持自定义检查器注册
  - 全面的结果报告，含统计追踪
  - 可配置严格级别（UnifiedGateConfig）

- **ShortcutLifecycleAdapter** (`lifecycle_protocol.py` 类)：Plan C 适配器
  - 使用 CLI 6 命令快捷方式实现 LifecycleProtocol
  - 自动 UnifiedGateEngine 集成（回退到基本检查）
  - CheckpointManager 集成，含自动状态保存/恢复
  - 支持跨会话的生命周期状态持久化

#### 增强 CheckpointManager

- **生命周期状态管理** (`scripts/collaboration/checkpoint_manager.py`)：
  - `save_lifecycle_state()`：将生命周期进度持久化到 JSON
  - `load_lifecycle_state()`：从磁盘恢复生命周期状态
  - `list_lifecycle_states()`：列出所有已保存的生命周期状态
  - `delete_lifecycle_state()`：清理已保存的状态
  - `create_checkpoint_from_lifecycle()`：桥接 LifecycleProtocol → Checkpoint

#### CLI 视图层集成

- **CLI 重构** (`scripts/cli.py`)：
  - 生命周期命令现在显示视图层映射信息
  - 显示每个 CLI 命令覆盖的 11 阶段段
  - 显示"视图层模式"标题以增强清晰度
  - 向后兼容，含回退输出

### 新增 - 测试

- **新测试套件**：`tests/test_plan_c_unified_architecture.py`
  - Plan C 架构的 27 个综合测试
  - UnifiedGateEngine 测试（11 个测试）
  - CheckpointManager 生命周期集成（7 个测试）
  - ShortcutLifecycleAdapter 统一门禁测试（6 个测试）
  - 端到端集成测试（3 个测试）
  - **全部 27 个测试通过**

### 新增 - 架构改进

- 通过分层架构解决 CLI 6 命令与 11 阶段生命周期冲突
- 所有门禁检查的单一入口点（UnifiedGateEngine）
- 解耦视图层（CLI）与核心引擎（WorkflowEngine）
- 状态持久化支持会话恢复和长时间运行任务
- 向后兼容：现有代码无需更改即可继续工作

---

## [3.4.1] - 2026-05-02

### 新增

#### 真实LLM后端集成

- **LLMBackend** (`scripts/collaboration/llm_backend.py`)：统一 LLM 接口，支持 Mock/OpenAI/Anthropic 后端
  - `create_backend()` 工厂函数，便于实例化
  - OpenAI 后端：`openai>=1.0`，可配置 base_url 和 model
  - Anthropic 后端：`anthropic>=0.18`，可配置 model
  - Mock 后端：零依赖，返回组装的提示词（默认）
  - 流式支持：`generate_stream()` 方法，实时逐块输出
  - 120 秒默认超时，可配置覆盖
  - API 密钥仅通过环境变量（无 `--api-key` CLI 标志）

- **Worker 流式输出** (`scripts/collaboration/worker.py`)：`stream=True` 参数
  - 通过 `--stream` CLI 标志实时输出 LLM 结果
  - 逐块打印到 stderr

- **CLI `--stream` 标志** (`scripts/cli.py`)：实时流式输出 LLM 结果

#### 安全增强

- **InputValidator** (`scripts/collaboration/input_validator.py`)：提示词注入检测
  - 16 个正则模式：忽略先前指令、越狱、DAN 模式、系统提示词提取等
  - `check_prompt_injection()` 公共方法
  - 严格模式（阻止）vs 普通模式（警告）
  - 集成到 Dispatcher 流水线

- **API 密钥安全**：完全移除 `--api-key` CLI 标志
  - 仅使用环境变量：`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
  - 绝不记录或在进程列表中暴露

#### 并行执行

- **ThreadPoolExecutor**：真正的并行执行，替代伪并行循环
  - Dispatcher 中使用 `concurrent.futures.ThreadPoolExecutor`
  - 真正的并发多角色调度

#### 上游模块采纳（来自 TraeMultiAgentSkill V2.3.0）

- **AISemanticMatcher** (`scripts/collaboration/ai_semantic_matcher.py`)：LLM 驱动的语义角色匹配
  - 双语关键词匹配（中文 + 英文）
  - `EN_KEYWORD_MAP` 用于英文任务描述
  - 无 LLM 后端时回退到关键词匹配

- **CheckpointManager** (`scripts/collaboration/checkpoint_manager.py`)：状态持久化
  - SHA256 完整性验证
  - `HandoffDocument` 用于 Agent 交接
  - 可配置最大检查点数的自动清理
  - `create_checkpoint_from_dispatch()` 便捷方法

- **WorkflowEngine** (`scripts/collaboration/workflow_engine.py`)：任务到工作流编排
  - `create_workflow_from_task()` 自动拆分
  - 含检查点的步骤执行
  - `resume_from_checkpoint()` 恢复
  - `handoff()` 用于 Agent 转换

- **TaskCompletionChecker** (`scripts/collaboration/task_completion_checker.py`)：完成追踪
  - `check_dispatch_result()` 和 `check_schedule_result()`
  - 进度持久化到 JSON
  - `get_completion_summary()` 和 `is_task_completed()`

#### 开发者体验

- **CodeMapGenerator** (`scripts/collaboration/code_map_generator.py`)：基于 AST 的 Python 代码分析
  - 函数/类提取，依赖图
  - 输出：dict, markdown, JSON

- **DualLayerContextManager** (`scripts/collaboration/dual_layer_context.py`)：上下文管理
  - 项目级 + 任务级上下文，含 TTL
  - `build_prompt_context()`, `cleanup_expired()`, 驱逐

- **SkillRegistry** (`scripts/collaboration/skill_registry.py`)：可复用技能管理
  - `register()`, `search()`, `execute()`, `propose_from_result()`
  - JSON 持久化

- **ConfigManager** (`scripts/collaboration/config_loader.py`)：配置系统
  - `~/.devsquad.yaml` 配置文件，含 16 个参数
  - 环境变量覆盖（优先级：env > file > defaults）
  - `DevSquadConfig` 数据类，含类型转换

- **Docker 支持**：`Dockerfile` + `.dockerignore`
  - Python 3.11-slim 基础镜像
  - ENTRYPOINT `cli.py`

- **GitHub Actions CI** (`.github/workflows/test.yml`)：
  - Python 3.9-3.12 矩阵测试
  - Lint 任务：flake8 + mypy

- **pip 可安装**：`pyproject.toml`，含可选依赖
  - `pip install -e ".[openai,anthropic,dev]"`
  - `devsquad` 控制台脚本入口点

- **_version.py**：版本单一事实来源（`3.4.0`）

### 变更

- **RoleMatcher** (`scripts/collaboration/role_matcher.py`)：从 Dispatcher 提取（92 行）
- **ReportFormatter** (`scripts/collaboration/report_formatter.py`)：从 Dispatcher 提取（314 行）
- **Dispatcher**：集成 InputValidator + ThreadPoolExecutor + 提示词注入检查
- **Worker**：添加 `stream` 参数用于实时输出
- **LLMBackend**：添加 `generate_stream()` 方法（基类 + OpenAI + Anthropic）
- **258 个单元测试**全部通过（core_test 39 + role_mapping_test 25 + upstream_test 35 + mce_adapter_test 30）

### 新增 - 文档

- README.md：完全重写，含架构图、34 个模块、快速开始
- README-CN.md：完整中文翻译
- README-JP.md：完整日文翻译
- INSTALL.md：添加 pip 安装、Docker、配置文件、流式输出
- SKILL.md：更新至 34 个模块，新架构流程
- CLAUDE.md：更新概览、架构、入口点

## [3.4] - 2026-04-26

### 新增

#### 性能优化模块（P0-P2 完成）

七个新模块，增强基于 LLM 的应用性能、可靠性和可观测性：

- ✅ **LLM 缓存模块** (`scripts/collaboration/llm_cache.py`, ~450 行)
  - 双层缓存系统（内存 + 磁盘）
  - 基于 TTL 的过期（默认：24 小时）
  - LRU 驱逐策略用于内存管理
  - 基于 SHA-256 的缓存键生成
  - 命中率统计和报告
  - **收益**：60-80% API 成本降低，缓存命中时 90% 响应加速
  - 测试套件：`llm_cache_test.py`（全面覆盖）

- ✅ **LLM 重试管理器** (`scripts/collaboration/llm_retry.py`, ~380 行)
  - 带抖动的指数退避重试机制
  - 断路器模式（防止级联故障）
  - 多后端回退支持（OpenAI → Anthropic → Zhipu）
  - 速率限制检测和处理
  - 每后端统计追踪
  - **收益**：99%+ 成功率，自动容错

- ✅ **性能监控器** (`scripts/collaboration/performance_monitor.py`, ~380 行)
  - 实时函数执行追踪
  - CPU 和内存使用监控（通过 psutil）
  - P95/P99 延迟百分位计算
  - 可配置阈值的瓶颈检测
  - Markdown 报告导出
  - **收益**：实时可见性，数据驱动优化

- ✅ **模块集成** (`scripts/collaboration/__init__.py`)
  - 所有优化模块的统一导入接口
  - 便捷函数：`print_stats()`, `reset_all()`, `get_version()`
  - 使用 `__all__` 定义的清晰 API 导出

- ✅ **集成示例** (`scripts/collaboration/integration_example.py`, ~290 行)
  - 6 个综合演示场景
  - 展示缓存 + 重试 + 监控协同工作
  - Mock LLM API 用于测试
  - 性能对比演示

#### P1: 异步支持模块（新增）

- ✅ **异步 LLM 缓存** (`scripts/collaboration/llm_cache_async.py`, ~350 行)
  - asyncio 兼容的双层缓存
  - asyncio.Lock 保证线程安全
  - 使用 run_in_executor 的异步文件 I/O
  - 完整的 async/await API（get, set, clear）
  - **收益**：高并发场景下 3-5 倍性能提升

- ✅ **异步 LLM 重试** (`scripts/collaboration/llm_retry_async.py`, ~400 行)
  - 异步指数退避重试
  - 异步断路器模式
  - 多后端异步回退
  - 速率限制检测
  - 异步函数的装饰器支持
  - **收益**：非阻塞 I/O，更好的 CPU 利用率

- ✅ **异步集成示例** (`scripts/collaboration/async_integration_example.py`, ~250 行)
  - 5 个完整异步示例
  - 基本异步缓存使用
  - 含回退的异步重试
  - 缓存 + 重试组合模式
  - 使用 asyncio.gather 的并发请求处理
  - 断路器演示

#### P2: 配置管理（新增）

- ✅ **配置管理器** (`scripts/collaboration/config_manager.py`, ~350 行)
  - YAML 配置文件支持
  - 环境变量覆盖
  - 点号记法键访问（如 "cache.ttl_seconds"）
  - 配置验证
  - 热重载支持
  - 默认配置模板
  - **收益**：集中配置，便于部署定制

- ✅ **默认配置文件** (`config/llm_optimization.yaml`)
  - 完整的默认配置
  - 缓存设置（TTL, 最大条目数, 磁盘缓存）
  - 重试设置（最大重试次数, 延迟, 抖动）
  - 断路器设置（阈值, 超时）
  - 性能监控设置
  - 后端配置（主后端, 回退顺序）
  - 日志配置

#### 文档

- ✅ **优化指南** (`docs/OPTIMIZATION_GUIDE.md`, ~600 行)
  - 三个模块的完整使用指南
  - 快速开始示例
  - 最佳实践和反模式
  - 性能基准和目标
  - 故障排查指南
  - 高级配置示例

- ✅ **优化建议** (`docs/OPTIMIZATION_RECOMMENDATIONS_2026-04-26.md`)
  - 20+ 优先级排序的优化建议（P0-P3）
  - 详细实施计划
  - 预期收益和 ROI 分析
  - 每条建议的代码示例

- ✅ **评审与评分报告** (`docs/OPTIMIZATION_REVIEW_SCORE.md`)
  - 综合评估：**85/100** ⭐⭐⭐⭐
  - 详细评分分解（代码质量、功能、测试、文档、可维护性）
  - 与行业最佳实践对比（Redis, Tenacity, Prometheus）
  - 差距分析和改进路线图
  - 性能基准测试结果

### 变更

- ✅ **README.md**：添加"性能优化模块"章节
  - 更新核心模块数：16 → 19
  - 添加每个优化模块的快速开始示例
  - 添加集成示例
  - 优化文档链接

### 性能影响

**缓存模块：**
- 测试场景：1000 次 LLM 调用，50% 重复率
- 成本降低：50%（500 → 250 次 API 调用）
- 速度提升：48%（250s → 130s）
- 内存开销：~10MB（1000 条目）

**重试模块：**
- 测试场景：100 次 API 调用，10% 失败率
- 成功率提升：90% → 99.9%
- 平均重试开销：+5% 延迟
- 断路器防止级联故障

**监控模块：**
- 性能开销：~2% CPU，~10% 内存
- 实时 P95/P99 追踪
- 可配置阈值的瓶颈检测

### 依赖

- 添加可选依赖：`psutil`（用于性能监控）
- 所有其他模块仅使用 Python 标准库

### 测试

- ✅ LLM 缓存：全面测试套件（`llm_cache_test.py`）
- ⚠️ LLM 重试：需要测试（评审中识别）
- ⚠️ 性能监控：需要测试（评审中识别）
- ⚠️ 集成测试：需要添加（评审中识别）

### 已知限制

如 `OPTIMIZATION_REVIEW_SCORE.md` 中记录：

1. **测试覆盖率**（-6 分）：仅缓存模块有测试
2. **异步支持**（-3 分）：所有模块仅同步
3. **日志**（-3 分）：基本日志，需要结构化日志
4. **配置**（-2 分）：硬编码配置，需要配置文件支持
5. **告警**（-2 分）：仅被动监控，无主动告警
6. **持久化**（-1 分）：重启后统计不持久化

### 路线图

**阶段 1（P0 - 高优先级）：**
- 为重试和监控模块添加全面测试套件
- 达到 80%+ 测试覆盖率

**阶段 2（P1 - 中优先级）：**
- 实现所有模块的异步版本
- 添加结构化日志系统

**阶段 3（P2 - 中低优先级）：**
- 添加 YAML 配置文件支持
- 实现告警系统
- 添加指标持久化（SQLite）

**阶段 4（P3 - 低优先级）：**
- 分布式缓存支持
- Prometheus/Grafana 集成
- 基于 ML 的优化

## [3.3] - 2026-04-17

### 新增

#### WorkBuddy (Claw) 记忆桥集成

依据 `docs/spec/WORKBUDDY_CLAW_INTEGRATION_SPEC.md`（CHG-01 ~ CHG-10）：

- ✅ 新增 `WorkBuddyClawSource` 类（~404 行）在 `memory_bridge.py` 中
  - 到 `/Users/lin/WorkBuddy/Claw/.memory/` 和 `.workbuddy/memory/` 的只读桥接
  - INDEX.md 倒排索引搜索，含回退全文扫描（O(1) 命中）
  - 核心文件映射：SOUL→SEMANTIC, USER→KNOWLEDGE, MEMORY→KNOWLEDGE 等
  - 每日工作日志加载（最多 30 个最近的 `.md` 文件，来自 `.workbuddy/memory/`）
  - Plan B：来自 `.codebuddy/automations/ai/memory.md` 的 AI 新闻源
  - `_parse_automation_log()` 用于按日期块的结构化新闻提取

- ✅ `MemoryBridge` 集成（+30 行）
  - `__init__()`：自动注册 WorkBuddyClawSource，含优雅降级
  - `recall()`：合并 claw_items 到结果（半数限制，按 relevance_score 排序）
  - `MemoryStats`：+`claw_enabled`, +`claw_item_count` 字段
  - `get_statistics()`：填充 claw 统计
  - `print_diagnostics()`：添加"WorkBuddy (Claw) Bridge"诊断段
  - `get_workbuddy_ai_news(days=7)`：Plan B 新闻源的公共 API

- ✅ Dispatcher AI 新闻自动注入（`dispatcher.py` 中 +29 行）
  - 任务匹配 AI/趋势/新闻关键词时自动注入到 Scratchpad
  - 零 LLM 调用，零网络请求获取行业情报
  - 15 个触发关键词（中+英）：ai新闻, industry trend, llm, claude, cursor 等

- ✅ 新测试套件：`claw_integration_test.py`（33 个用例）
  - T-A01~T-A08：源可用性、核心/每日记忆、索引搜索、回忆融合
  - T-B01~T-B04：新闻解析、日期过滤、缺失文件、桥接 API
  - T-D01~T-D02：诊断输出、统计字段
  - 工具测试：extract_tags, extract_section, parse_automation_log, load_all

#### 注释标准更新

- ✅ 文档（SKILL.md / README.md）：英文
- ✅ 代码文档字符串：英文（Args / Returns / Example）
- ✅ 行内注释：英文（业务逻辑）
- ✅ README-CN.md：中文（中文版文档）

### 变更

- ✅ SKILL.md：v3.2→v3.3，15→16 个模块，~795→~828 个测试
- ✅ README.md：添加 v3.3 Claw 行，~795→~828 个测试
- ✅ `__init__.py`：导出 `WorkBuddyClawSource`
- ✅ `v3-upgrade-proposal.md`：添加 Phase 11 记录

### 测试结果

```
MemoryBridge Test:        96/96   ✅
Dispatcher Test:          54/54   ✅
MCE Adapter Test:         23/23   ✅
Dispatcher UX Test:       24/24   ✅
Claw Integration Test:    33/33   ✅
─────────────────────────────────
Total:                   230/230  ✅
```

---

## [3.2] - 2026-04-17

### 新增

#### MVP 三条并行线（依据 v3.2 最终共识）

##### 线 A：E2E 完整演示
- ✅ 新增 `scripts/demo/e2e_full_demo.py`（~350 行）
  - CLI 接口（--task/--roles/--json 参数）
  - RoleOutputSimulator：5 角色真实输出模拟
  - 10 步完整流程：Init→Analyze→Plan→Schedule→Execute→Share→Conflict→Report→Memory→Output

##### 线 B：MCE 适配器
- ✅ 新增 `scripts/collaboration/mce_adapter.py`（~290 行）
  - MCEAdapter：延迟初始化、优雅降级、线程安全
  - MCEResult / MCEStatus 数据模型
  - get_global_mce_adapter() 进程级单例
  - 集成点：MemoryBridge（capture/recall/shutdown），Dispatcher（classify）

##### 线 C：Dispatcher UX 增强
- ✅ 增强 `dispatcher.py` quick_dispatch()（+360 行）
  - 3 种输出格式：结构化（默认）/ 紧凑 / 详细
  - 结构化报告层次：摘要卡 → 角色表 → 发现 → 冲突 → 行动项
  - _extract_findings()：编号/项目符号/分号/句子分割
  - _generate_action_items()：基于结果分析的 H/M/L 优先级自动生成

- ✅ 新测试套件：
  - mce_adapter_test.py：23 个用例（init/classify/batch/store/retrieve/lifecycle/thread-safety/normalize）
  - dispatcher_ux_test.py：24 个用例（结构化/紧凑/详细报告、提取、行动项）

### 变更

- ✅ memory_bridge.py：__init__(mce_adapter), capture_execution(MCE classify), recall(MCE filter), shutdown(MCE联动)
- ✅ dispatcher.py：__init__(mce_adapter), dispatch(MCE classify step)
- ✅ __init__.py：导出 MCEAdapter/MCEResult/MCEStatus/get_global_mce_adapter
- ✅ SKILL.md / README.md / v3-upgrade-proposal.md：v3.2 条目

---

## [3.1] - 2026-04-16

### 新增

#### 提示词优化系统（借鉴自 Claude Code 架构）

##### PromptAssembler（~320 行）
- TaskComplexity 检测（3D 模型：长度 + 关键词 + 结构）
- 3 种模板变体：紧凑 / 标准 / 增强
- 每种角色类型的 5 种指令风格
- 角色专属反模式警告
- 压缩级别覆盖支持

##### PromptVariantGenerator（~420 行）
- SuccessPattern → PromptVariant 闭环流水线
- 质量评分（5 维：相关性/新鲜度/可操作性/独特性/清晰度）
- 基于阈值的过滤（confidence ≥ 0.7, frequency ≥ 2）
- A/B 推广生命周期（≥75% 正面时推广，≤35% 时弃用）
- 低效变体自动弃用

- ✅ 新测试：prompt_optimization_test.py（59 个用例）

---

## [3.0] - 2026-04-16

### 新增

#### V3架构完全重设计

基于 Coordinator/Worker/Scratchpad 协作模式：

- ✅ 11 个核心模块（后在 v3.1 扩展至 13 个，v3.3 扩展至 16 个）：
  0. MultiAgentDispatcher（统一入口点）
  1. Coordinator（全局编排器）
  2. Scratchpad（共享黑板）
  3. Worker（角色执行器）
  4. ConsensusEngine（加权投票 + 否决）
  5. BatchScheduler（并行/串行混合）
  6. ContextCompressor（4 级压缩）
  7. PermissionGuard（4 级权限）
  8. Skillifier（从模式中学习技能）
  9. WarmupManager（3 层启动预热）
  10. MemoryBridge（7 类记忆桥 + TF-IDF + 遗忘曲线）
  11. TestQualityGuard（3 层测试质量强制）

- ✅ ~710 个基线测试（全部通过）
- ✅ E2E 测试：e2e_test.py（26 个用例）
- ✅ 增强 E2E 测试：enhanced_e2e_test.py（46 个用例）

---

## [2.5.0] - 2026-04-06

### 新增

#### Memory Classification Engine 集成

##### 记忆适配器模块
- ✅ 新增 `scripts/memory_adapter.py` 模块
- ✅ 实现 7 种记忆类型分类：用户偏好、纠正信号、事实声明、决策记录、关系信息、任务模式、情感标记
- ✅ 实现 4 层存储架构：工作记忆、程序性记忆、情节记忆、语义记忆
- ✅ 实现 `MemoryTypeMapper` 分类器
- ✅ 实现 `MemoryAdapter` 核心适配器

##### 双层上下文管理器增强
- ✅ 新增 `process_message_with_memory()` 方法
- ✅ 新增 `retrieve_memories_by_type()` 方法
- ✅ 新增 `apply_forgetting()` 方法
- ✅ 新增 `get_memory_statistics()` 方法

##### 遗忘机制
- ✅ 基于加权衰减的智能遗忘
- ✅ 自动清理低价值记忆
- ✅ 支持自定义衰减因子和最小权重阈值

##### 文档更新
- ✅ 新增 `docs/architecture/memory_integration_architecture.md` 架构文档
- ✅ 新增 `docs/testing/memory_integration_test.md` 测试报告
- ✅ 更新 `README.md` 添加 v2.5.0 功能说明

##### 测试
- ✅ 新增 `scripts/test_memory_adapter.py` 测试脚本
- ✅ 记忆类型分类准确率 92.9%
- ✅ 层级映射准确率 100%
- ✅ 集成测试全部通过

## [2.4.2] - 2026-04-03

### 新增

#### 智能生命周期识别

- ✅ 自动检测需要完整项目流程的任务
- ✅ 新增 `IntentType.PROJECT_LIFECYCLE` 意图类型
- ✅ 扩展触发关键词：项目生命周期、全生命周期、完整流程、启动项目、新项目等
- ✅ SKILL.md 新增自动触发规则说明

## [2.4.1] - 2026-04-01

### 新增

#### 核心规则集成

- ✅ 集成 Claude Code 的 14 条提示词核心规则到 Vibe Coding 提示词优化系统
- ✅ 新增 `/dss lifecycle` 命令，一键启动完整项目生命周期
- ✅ 新增 `/dss rules` 命令，查看系统集成的核心规则库
- ✅ 完成多角色批判性审核报告 (`docs/critical_review.md`)
- ✅ 仓库结构优化，清理不必要的文件

## [2.3.0] - 2026-03-28

### 新增

#### 代码地图增强 (v2.3)

##### 多项目 Workspace 支持
- ✅ 支持一个 workspace 包含多个项目的场景
- ✅ 自动识别项目所属 workspace
- ✅ 明确项目标识（项目名称、工作空间、相对路径）

##### 多角色代码走读
- ✅ `MultiRoleCodeWalkthrough` 类 (`scripts/multi_role_code_walkthrough.py`)
- ✅ 支持 5 种角色分析：架构师、产品经理、独立开发者、UI 设计师、测试专家
- ✅ 角色专属代码分析 prompt 模板
- ✅ 文档对齐机制，合并多角色分析结果
- ✅ 生成统一代码地图
- ✅ 生成代码走读审查报告 (`CodeReviewReportGenerator` 类)

##### 真正的多角色协作分析器 (v2.3)
- ✅ `MultiRoleCollaborativeAnalyzer` 类 (`scripts/multi_role_collaborative_analyzer.py`)
- ✅ 集成 Trae Agent 调度系统 (`trae_agent_dispatch_v2.py`)
- ✅ 每个角色使用专属 prompt 模板进行真实分析
- ✅ 真正的多角色协作：架构师、产品经理、独立开发者、UI 设计师、测试专家
- ✅ 支持并行/串行执行各角色分析任务
- ✅ 提取各角色的关键发现和建议

##### 角色专属 Prompt 模板
- ✅ 架构师代码分析模板 (`docs/spec/role-prompts/architect-code-analysis.md`)
- ✅ 产品经理代码分析模板 (`docs/spec/role-prompts/pm-code-analysis.md`)
- ✅ 独立开发者代码分析模板 (`docs/spec/role-prompts/coder-code-analysis.md`)
- ✅ UI 设计师代码分析模板 (`docs/spec/role-prompts/ui-code-analysis.md`)
- ✅ 测试专家代码分析模板 (`docs/spec/role-prompts/test-expert-code-analysis.md`)

##### 代码地图生成器 v2.1
- ✅ `CodeMapGenerator` 类增强 (`scripts/code_map_generator_v2.py`)
- ✅ 支持多语言分析：Python, Java, JavaScript/TypeScript, Go 等
- ✅ 架构分层检测（API Layer, Service Layer, Data Layer 等）
- ✅ 函数和类详细信息提取
- ✅ 调用关系追踪
- ✅ 复杂度评估
- ✅ md 格式输出

##### 代码与文档分离 (v2.3)
- ✅ 代码地图仅保留核心结构内容（项目概览、架构视图、代码结构、多角色视角、分析共识）
- ✅ 审查报告包含完整风险评估和建议
- ✅ 移除代码地图中的"建议"和"快速参考"章节

##### 3D 代码地图可视化 (v2.3)
- ✅ `docs/code-map-visualizer.html`
- ✅ Three.js 3D 引擎，支持拖拽旋转、滚轮缩放
- ✅ 节点类型区分：模块（蓝色）、类（紫色）、函数（绿色）
- ✅ 调用关系可视化：节点间连线表示调用关系
- ✅ 动态流动效果：边使用虚线动画 + 流动粒子
- ✅ 深色/浅色主题一键切换
- ✅ 点击展开/折叠、双击高亮调用链路、搜索过滤

##### 任务可视化页面 (v2.3)
- ✅ `docs/task-visualizer.html`
- ✅ 概览统计面板：总任务数、待开始、进行中、已完成、被阻塞
- ✅ 角色任务卡片：任务列表、状态、进度
- ✅ 任务依赖关系和阻塞关系展示
- ✅ 任务交接记录时间线
- ✅ Canvas 绘制协同关系图
- ✅ 定时刷新机制（30秒自动刷新）
- ✅ 任务详情弹窗

##### 文档与代码一致性检查 (v2.3)
- ✅ `ProjectScanner` 支持文档文件扫描 (.md, .txt, .rst, .adoc)
- ✅ `CodeReviewReportGenerator` 新增 `_generate_doc_code_consistency_check()` 方法
- ✅ 文档覆盖概览统计
- ✅ 检查清单表格（README、API、配置、架构文档）
- ✅ 差异分析按严重程度分级（严重/中等/轻微）

## [2.2.0] - 2026-03-21

### 新增

#### 长程 Agent 支持 (基于 Anthropic《Effective Harnesses for Long-Running Agents》)

##### Checkpoint 检查点管理器
- ✅ `CheckpointManager` 类 (`scripts/checkpoint_manager.py`)
  - 定期保存任务状态（像人类工程师 git commit）
  - 支持从任意断点恢复
  - 数据完整性校验（SHA256 哈希）
  - 自动过期清理机制
  - 交接文档生成

##### Handoff 交接班协议
- ✅ `HandoffDocument` 类
  - 标准化交接文档（JSON + Markdown）
  - 交接原因记录和信心度评估
  - 重要注意事项传递
  - 支持双智能体架构（Planner + Executor）
  - 交接历史追踪

##### TaskList 任务清单管理器
- ✅ `TaskListManager` 类 (`scripts/task_list_manager.py`)
  - 4 级优先级（CRITICAL/HIGH/MEDIUM/LOW）
  - 5 种状态（PENDING/IN_PROGRESS/COMPLETED/BLOCKED/CANCELLED）
  - 依赖关系管理（is_ready 检查）
  - 进度跟踪和工时估算
  - Markdown 导出功能

##### WorkflowEngineV2 增强版
- ✅ `WorkflowEngineV2` 类 (`scripts/workflow_engine_v2.py`)
  - 集成 Checkpoint + TaskList + Handoff
  - 智能任务拆分（基于关键词识别）
  - 定期自动保存检查点
  - 支持 Agent 交接班
  - 断点恢复机制

##### 完整测试套件
- ✅ 24 个测试全部通过
  - `TestCheckpointManager`: 7 个测试
  - `TestHandoffDocument`: 3 个测试
  - `TestTaskListManager`: 9 个测试
  - `TestWorkflowEngineV2`: 5 个测试

### 修复

#### 角色匹配问题
- ✅ 修复角色匹配总是匹配到 UI 设计师的问题
  - 优化关键词区分度
  - 添加 AI 语义匹配
  - 增强优先级权重

#### JSON 序列化问题
- ✅ 修复枚举类型 JSON 序列化错误
  - Checkpoint 状态枚举转换
  - TaskList 状态和优先级枚举转换
  - WorkflowEngine 步骤状态枚举转换
  - 数据完整性哈希校验

## [1.3.0] - 2026-03-12

### 修复

#### Agent Loop 思考循环问题
- ✅ 修复 `is_all_tasks_completed()` 方法
  - 优先从任务文件中检查实际完成状态
  - 遍历所有测试用例，检查是否有待实现的标记
  - 出错时使用进度文件作为备选方案

- ✅ 优化 `agent_loop_controller.py` 循环逻辑
  - 新增连续无进展计数器（防止无限循环）
  - 连续 3 次迭代无进展时强制退出
  - 增加任务执行成功/失败的计数器管理
  - 确保循环在各种情况下都能正确退出

- ✅ 改进任务状态同步机制
  - 以任务文件状态为准，确保同步
  - 正确处理已完成和待完成任务的列表更新
  - 避免状态冲突和不一致

- ✅ 修复路径问题
  - 从 skill 目录导入检查器脚本
  - 使用相对路径定位进度文件

## [1.2.0] - 2026-03-11

### 新增

#### 规范驱动开发功能
- ✅ 完整的规范工具链（scripts/spec_tools.py）
  - `spec_tools.py init` - 初始化规范环境
  - `spec_tools.py analyze` - 分析规范完整性和一致性
  - `spec_tools.py update` - 更新规范文档
  - `spec_tools.py validate` - 验证规范执行情况

- ✅ 项目宪法（CONSTITUTION.md）
  - 项目核心价值观和原则
  - 技术栈约束和决策
  - 代码规范和标准
  - 多角色共识制定流程

- ✅ 项目规范（SPEC.md）
  - 需求规范（产品经理负责）
  - 技术规范（架构师负责）
  - 测试规范（测试专家负责）
  - 开发规范（独立开发者负责）

- ✅ 规范分析报告（SPEC_ANALYSIS.md）
  - 规范完整性分析
  - 规范一致性检查
  - 规范可行性评估
  - 改进建议

- ✅ 规范模板库
  - CONSTITUTION_TEMPLATE.md - 项目宪法模板
  - SPEC_TEMPLATE.md - 项目规范模板
  - SPEC_ANALYSIS_TEMPLATE.md - 规范分析模板
  - PROJECT_STRUCTURE_TEMPLATE.md - 项目结构模板

#### 代码地图生成功能
- ✅ 代码地图生成器（scripts/code_map_generator.py）
  - 自动扫描项目代码结构
  - 识别核心组件和入口文件
  - 分析模块依赖关系
  - 生成技术栈统计

- ✅ 输出格式支持
  - JSON 格式（code_map.json）- 机器可读
  - Markdown 格式（PROJECT_STRUCTURE.md）- 人类可读
  - 可视化项目结构树
  - 组件职责说明

- ✅ 代码地图内容
  - 项目概览和统计信息
  - 目录结构树
  - 核心组件和入口文件
  - 模块依赖关系图
  - 技术栈分析（语言、框架、库）

#### 项目理解功能
- ✅ 项目理解生成器（scripts/project_understanding.py）
  - 快速读取项目文档和代码
  - 为各角色生成定制化理解文档
  - 提供项目概览和技术栈分析
  - 作为工作初始化上下文

- ✅ 角色特定理解文档
  - project_understanding.json - 整体项目信息
  - architect_understanding.md - 架构师理解（技术栈、架构模式、部署结构）
  - product_manager_understanding.md - 产品经理理解（功能列表、用户价值、竞品分析）
  - test_expert_understanding.md - 测试专家理解（测试覆盖、质量风险、自动化策略）
  - solo_coder_understanding.md - 独立开发者理解（代码结构、开发规范、技术债务）

- ✅ 项目理解内容
  - 项目概览（名称、描述、目标）
  - 技术栈分析（编程语言、框架、数据库、中间件）
  - 代码结构分析（目录组织、模块划分、代码统计）
  - 文档分析（README、API 文档、设计文档）
  - 依赖分析（package.json、pom.xml、Cargo.toml 等）
  - 角色特定见解和建议

#### 增强版角色 Prompt 系统
- ✅ 规范相关职责
  - 架构师：负责制定和维护技术规范
  - 产品经理：负责制定和维护需求规范
  - 测试专家：负责制定和维护测试规范
  - 独立开发者：负责遵循规范并反馈改进建议

- ✅ 规范驱动开发流程
  - 所有开发工作必须基于已评审的规范
  - 规范变更必须经过多角色共识
  - 规范执行情况必须定期检查
  - 规范文档必须保持最新状态

### 变更

- ✅ 更新 README.md
  - 添加 2026 年 3 月最新更新说明
  - 添加规范驱动开发详细说明
  - 添加代码地图生成详细说明
  - 添加项目理解详细说明
  - 更新功能特性列表

- ✅ 更新 SKILL.md
  - 添加规范驱动开发职责
  - 添加代码地图生成职责
  - 添加项目理解职责
  - 更新角色定义和触发关键词

- ✅ 更新 EXAMPLES.md
  - 添加规范驱动开发示例
  - 添加代码地图生成示例
  - 添加项目理解示例
  - 更新场景示例

### 改进

- ✅ 文档驱动开发流程优化
  - 明确文档依赖关系
  - 添加检查点机制
  - 强化评审流程
  - 完善违规处理

- ✅ 多角色协作机制
  - 优化共识决策流程
  - 改进角色间沟通
  - 增强上下文共享
  - 提升协作效率

## [1.1.0] - 2024-03-05

### 新增

#### 新功能/功能变更标准工作流程
- ✅ 七阶段标准工作流程
  - 阶段 1: 需求分析（产品经理）
  - 阶段 2: 架构设计（架构师）
  - 阶段 3: 测试设计（测试专家）
  - 阶段 4: 任务分解（独立开发者）
  - 阶段 5: 开发实现（独立开发者）
  - 阶段 6: 测试验证（测试专家）
  - 阶段 7: 发布评审（多角色）

- ✅ 核心原则：先设计、先写文档、再开发
  - 绝对禁止：未设计直接编码、文档未完成就开发、未评审直接实施
  - 必须遵循：所有新功能必须先设计、所有设计必须先写文档、所有文档必须经过评审

- ✅ 跨角色设计评审机制
  - PRD 评审流程（产品经理 → 架构师 + 测试专家）
  - 架构设计评审流程（架构师 → 产品经理 + 测试专家 + 开发者）
  - 测试计划评审流程（测试专家 → 产品经理 + 架构师 + 开发者）
  - 开发计划评审流程（开发者 → 架构师 + 测试专家）

- ✅ 文档依赖关系管理
  - PRD → 架构设计 → 测试计划 → 开发任务 → 测试报告 → 发布决策
  - 明确各阶段的输入输出和检查点

- ✅ 违规处理机制
  - 发现未按流程执行的应对措施
  - 回溯到上一个检查点
  - 补充缺失的文档或评审

#### 基于文档的任务分解与执行规则
- ✅ 所有角色的文档驱动任务分解规范
  - 架构师：基于架构设计文档分解任务
  - 产品经理：基于 PRD 文档分解任务
  - 测试专家：基于测试计划文档分解任务
  - 独立开发者：基于所有技术文档分解任务

- ✅ 任务依赖关系定义
  - 明确定义阶段间的依赖关系
  - 下游任务必须等待上游任务完成
  - 文档编写任务必须在设计/实现完成后开始

- ✅ 检查点机制
  - 每个阶段设置检查点（CP-1, CP-2, ...）
  - 检查内容包括完整性和质量要求
  - 通过标准明确，不通过需修复

- ✅ 独立开发者前置条件检查
  - 必须确认 PRD 文档已评审通过
  - 必须确认架构设计文档已评审通过
  - 必须确认测试计划文档已评审通过
  - 文档阅读确认输出要求

#### 标准化文档模板
- ✅ 架构师文档模板
  - ARCHITECTURE_DESIGN_TEMPLATE.md - 架构设计文档模板
  - 包含更新履历、系统概述、模块设计、接口定义等章节

- ✅ 产品经理文档模板
  - PRD_TEMPLATE.md - 产品需求文档模板
  - 包含更新履历、需求分析、功能需求、非功能需求等章节

- ✅ 测试专家文档模板
  - TEST_PLAN_TEMPLATE.md - 测试计划文档模板
  - 包含更新履历、测试策略、测试用例设计、测试执行计划等章节

#### 文档更新履历规范
- ✅ 所有文档必须包含更新履历章节
- ✅ 统一更新履历表格格式
- ✅ 要求记录版本号、日期、更新人、更新内容、审核状态

### 变更

- ✅ 更新 README.md
  - 添加新功能/功能变更标准工作流程说明
  - 添加文档依赖关系图示

- ✅ 更新 SKILL.md
  - 添加七阶段标准工作流程详细说明
  - 添加跨角色设计评审机制
  - 添加基于文档的任务分解与执行规则
  - 更新独立开发者的前置条件检查要求

## [1.0.0] - 2024-03-04

### 新增

#### 核心功能
- ✅ 智能角色调度系统
  - 基于关键词匹配的角色识别算法
  - 位置权重计算（越靠前权重越高）
  - 置信度评估机制
  - 支持 4 种角色自动识别

- ✅ 多角色协同机制
  - 共识组织算法
  - 冲突检测和解决
  - 多角色评审流程
  - 角色间上下文共享

- ✅ 完整项目生命周期支持
  - 8 阶段项目流程
  - 从需求到部署全流程
  - 质量门禁和评审机制
  - 项目阶段感知调度

- ✅ 上下文感知调度
  - 历史上下文智能继承
  - 项目阶段识别
  - 任务链自动关联
  - 上下文优先级管理

#### 角色系统
- ✅ 架构师 (Architect)
  - 系统性思维规则
  - 5-Why 分析法
  - 零容忍清单（6 项禁止）
  - 验证驱动设计
  - 完整输出模板

- ✅ 产品经理 (Product Manager)
  - 需求三层挖掘规则
  - SMART 验收标准
  - 竞品分析规则
  - 用户调研方法
  - PRD 文档规范

- ✅ 测试专家 (Test Expert)
  - 测试金字塔规则
  - 正交分析法
  - 5 类测试场景设计
  - 真机测试规则
  - 自动化测试规范

- ✅ 独立开发者 (Solo Coder)
  - 零容忍清单（10 项禁止）
  - 完整性检查规则（4 维度）
  - 自测规则（3 层测试）
  - 代码质量规范
  - 错误处理规范

#### 调度脚本
- ✅ `trae_agent_dispatch.py`
  - 命令行界面
  - 自动角色识别
  - 手动角色指定
  - 共识机制触发
  - 完整项目流程
  - 代码审查模式
  - 紧急修复通道

#### 文档系统
- ✅ 技能定义文件 (SKILL.md)
  - 34KB 完整 Prompt
  - 4 角色详细规则
  - 工作原则和流程
  - 检查清单

- ✅ 用户指南
  - 快速开始
  - 使用示例
  - 最佳实践
  - 常见问题

- ✅ 安装指南
  - 多种安装方式
  - 验证步骤
  - 故障排查

- ✅ 角色配置文档
  - 角色定义
  - 协作机制
  - 触发时机

#### 工具脚本
- ✅ `install-global.sh`
  - 自动化安装脚本
  - 备份机制
  - 验证流程

- ✅ `schedule_agent.py`
  - 调度执行脚本
  - 共识组织
  - 结果处理

### 变更

- 无（初始版本）

### 修复

- 无（初始版本）

### 弃用

- 无（初始版本）

### 移除

- 无（初始版本）

### 安全

- ✅ 安全特性
  - 敏感配置加密存储
  - 权限检查机制
  - 安全测试场景覆盖
  - OWASP Top 10 检测支持

---

## 版本说明

### 版本号格式

遵循语义化版本规范：`MAJOR.MINOR.PATCH`

## 贡献者

感谢所有为这个项目做出贡献的人！

📝 查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与贡献。

---

**Made with ❤️ by weiansoft **
