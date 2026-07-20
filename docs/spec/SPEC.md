# DevSquad V4.1.5 完整技术规范

> **文档类型**: 项目技术规范 (Technical Specification)
> **版本**: V4.1.5 (Enterprise Edition)
> **成熟度**: 8.9/10 (诚实评估)
> **最后更新**: 2026-07-19
> **文档位置**: `docs/spec/SPEC.md`
> **活文档原则**: 本文档与代码同步演进，每次版本发布时同步更新所有数据点。

---

## 目录索引

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [核心模块清单](#3-核心模块清单)
4. [API 规范](#4-api-规范)
   - 4.1 [CLI 命令规范](#41-cli-命令规范)
   - 4.2 [REST API 端点](#42-rest-api-端点)
   - 4.3 [Python API](#43-python-api)
   - 4.4 [MCP 协议接口](#44-mcp-协议接口)
5. [数据模型](#5-数据模型)
6. [配置系统](#6-配置系统)
7. [部署方案](#7-部署方案)
8. [测试策略](#8-测试策略)
9. [性能指标](#9-性能指标)
10. [安全要求](#10-安全要求)
11. [附录](#11-附录)

---

## 1. 项目概述

### 1.1 基本信息

| 属性 | 值 |
|------|-----|
| **项目名称** | DevSquad |
| **版本号** | V4.0.11 |
| **成熟度等级** | 8.9/10 (honest assessment) |
| **项目描述** | Production-Ready Multi-Role AI Task Orchestrator |
| **开发语言** | Python 3.10+ |
| **开源协议** | MIT License |
| **代码仓库** | https://github.com/lulin70/DevSquad |
| **PyPI 包名** | `devsquad` |

### 1.2 项目定位

DevSquad 是一个**生产级多角色 AI 任务编排框架**，采用**控制论增强的多智能体协作范式**，实现：

- **7 个专业角色**协作（架构师、产品经理、安全专家、测试专家、独立开发者、DevOps工程师、UI设计师）
- **4 种执行模式**（auto/parallel/sequential/consensus）
- **5 轴共识机制**（正确性/可读性/架构/安全性/性能）
- **11 阶段生命周期管理**（P1:需求分析 → P2:架构设计 → P3:技术设计 → P4:数据设计(opt) → P5:交互设计(opt) → P6:安全审查(opt) → P7:测试规划 → P8:实现 → P9:测试执行 → P10:部署发布 → P11:运维保障(opt)）
- **5 种生命周期模板**（full/backend/frontend/internal_tool/minimal）
- **6 个原子技能**（dispatch/intent/retrospective/review/security/test）
- **V4.0.0 六大特性**（Loop Engineering/UI-UX 巡检/对抗验证/DAG 可视化/自主迭代/插件热加载）

### 1.3 技术栈概览

| 技术领域 | 选型 | 版本要求 | 用途 |
|----------|------|----------|------|
| **语言** | Python | ≥3.10 | 核心开发语言 |
| **Web 框架** | FastAPI | ≥0.100.0 | REST API 服务 |
| **ASGI 服务器** | Uvicorn | ≥0.23.0 | API 服务运行时 |
| **数据验证** | Pydantic | ≥2.0 | 数据模型验证 |
| **配置解析** | PyYAML | ≥6.0 | YAML 配置文件 |
| **UI 框架** | Streamlit | ≥1.28.0 | Web Dashboard |
| **MCP 协议** | MCP SDK | ≥0.9 | Model Context Protocol |
| **LLM 后端** | OpenAI / Anthropic / Moka AI | ≥1.0 / ≥0.18 / V4.0.7+ | 大模型调用（Moka AI 为 V4.0.7+ 新增） |
| **测试框架** | pytest | ≥7.0 | 单元/集成测试 |
| **代码质量** | Ruff / Mypy | ≥0.4 / ≥1.0 | Linting / 类型检查 |

### 1.4 核心特性矩阵

| 特性类别 | 特性名称 | 成熟度 | 说明 |
|----------|----------|--------|------|
| **协作引擎** | Multi-Agent Dispatcher | ✅ 生产级 | 支持 7 角色 + 4 模式 |
| **共识机制** | Five-Axis Consensus | ✅ 生产级 | 权重投票 + 否决权 |
| **生命周期** | Lifecycle Protocol | ✅ 生产级 | 11 阶段门禁控制 |
| **质量控制** | Verification Gate | ✅ 生产级 | 证据驱动验收 |
| **目标锚定** | Anchor Checker | ✅ 生产级 | V3.6.0 新增 |
| **回顾引擎** | Retrospective Engine | ✅ 生产级 | V3.6.0 新增 |
| **缓存系统** | LLM Cache (L1+L2) | ✅ 生产级 | 内存+磁盘双层 |
| **安全防护** | Permission Guard (4级) | ✅ 生产级 | 53种注入检测 (15 forbidden+13 SSRF+5 suspicious+20 prompt injection) |
| **可观测性** | Performance Monitor | ✅ 生产级 | P95/P99 延迟监控 + Markdown 报告 |
| **API 服务** | REST API (FastAPI) | ✅ 生产级 | Swagger/ReDoc 文档 |
| **MCP 集成** | MCP Server | ✅ 生产级 | 5 个工具端点 |
| **Dashboard** | Streamlit UI | ✅ 生产级 | 可视化监控 + DAG 可视化 (V4.0.0) |
| **Loop Engineering** | Loop Kernel (V4.0.0) | ✅ 生产级 | Discovery→Handoff→Verification→Persistence→Scheduling |
| **UI/UX 巡检** | UIUXAnalyzer (V4.0.0) | ✅ 生产级 | 4 维度审计 (a11y/interaction/layout/ux_antipattern) |
| **对抗验证** | AdversarialVerifier (V4.0.0) | ✅ 生产级 | 红蓝对抗 + 裁判仲裁三阶段 |
| **自主迭代** | AutonomousLoopController (V4.0.0) | ✅ 生产级 | plan→dev→verify→fix 4 阶段自主循环 |
| **插件热加载** | PluginHotLoader (V4.0.0) | ✅ 生产级 | 3 加载路径 + 路径穿越三层防护 |

---

## 2. 架构设计

### 2.1 三层架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │   CLI    │  │ REST API │  │   MCP    │  │ Dashboard   │ │
│  │ (cli.py) │  │(FastAPI) │  │ (Server) │  │(Streamlit)  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘ │
└───────┼────────────┼────────────┼───────────────┼─────────┘
        │            │            │               │
┌───────▼────────────▼────────────▼───────────────▼─────────┐
│                    Orchestration Layer                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              MultiAgentDispatcher                    │  │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │  │
│  │  │Coordinator│ │ Worker   │ │   Scratchpad       │  │  │
│  │  │          │ │ Pool     │ │   (Shared Memory)  │  │  │
│  │  └──────────┘ └──────────┘ └────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐  │
│  │ConsensusEngine│ │BatchScheduler│ │WorkflowEngine     │  │
│  └─────────────┘ └──────────────┘ └───────────────────┘  │
└───────┬───────────────────────────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────┐
│                       Core Layer                           │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ │
│  │ LLM Backend│ │Permission  │ │Input      │ │Execution │ │
│  │ (Adapter)  │ │ Guard      │ │Validator  │ │ Guard    │ │
│  └────────────┘ └────────────┘ └──────────┘ └──────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐ │
│  │ LLM Cache  │ │Performance │ │Config    │ │Auth      │ │
│  │ (L1+L2)    │ │ Monitor    │ │ Loader   │ │ Manager  │ │
│  └────────────┘ └────────────┘ └──────────┘ └──────────┘ │
└───────────────────────────────────────────────────────────┘
```

### 2.2 分层子技能架构 (Skill Architecture)

```
DevSquad Skills System (V4.0.11)
│
├── skills/
│   ├── dispatch/          # 任务调度技能 (~50行)
│   │   ├── handler.py
│   │   └── skill-manifest.yaml
│   ├── intent/            # 意图识别技能 (~50行)
│   │   ├── handler.py
│   │   └── skill-manifest.yaml
│   ├── retrospective/     # 回顾分析技能 (V3.6.0新增)
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   └── skill-manifest.yaml
│   ├── review/            # 代码审查技能
│   │   ├── handler.py
│   │   └── skill-manifest.yaml
│   ├── security/          # 安全扫描技能
│   │   ├── handler.py
│   │   └── skill-manifest.yaml
│   └── test/              # 测试执行技能
│       ├── __init__.py
│       ├── handler.py
│       └── skill-manifest.yaml
│
└── skills/registry.py     # 技能注册中心
```

**技能特性**：
- **原子化设计**：每个技能 ~50 行代码，单一职责
- **声明式配置**：`skill-manifest.yaml` 定义元数据
- **动态加载**：通过 `SkillRegistry` 运行时注册
- **独立可测试**：每个 skill 有独立 handler 和测试

### 2.3 控制论增强模块 (Cybernetics Enhancement - V3.6.0)

```
Control Loop Architecture (Feedback Systems)
│
├── Anchor Checker (目标锚定器)
│   ├── 功能: 实时检测任务执行是否偏离原始目标
│   ├── 触发时机: STEP_COMPLETE / PHASE_GATE / CONFLICT / MILESTONE
│   ├── 输出: AnchorResult (aligned, drift_score, recommendation)
│   └── 集成点: Coordinator.plan_task() → Worker.execute()
│
├── Retrospective Engine (回顾引擎)
│   ├── 功能: 任务完成后自动生成改进建议报告
│   ├── 分析维度: 偏差检测 / 冗余识别 / 改进建议
│   ├── 输出: RetrospectiveReport (Markdown + Dict)
│   └── 集成点: Coordinator.post_process()
│
├── Feedback Control Loop (反馈控制环)
│   ├── 功能: 基于历史反馈调整后续行为
│   ├── 数据源: CI 反馈 / 用户评价 / 测试结果
│   └── 输出: 自适应参数调整
│
└── Anti-Rationalization (反合理化机制)
    ├── 功能: 防止 AI 自我合理化错误决策
    ├── 检测模式: Confirmation Bias / Sunk Cost / Groupthink
    └── 输出: 警告 + 纠正建议
```

---

## 3. 核心模块清单

### 3.1 协作引擎模块 (Collaboration Core) - 70 个文件

#### 3.1.1 编排调度 (Orchestration & Dispatch)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `coordinator.py` | ~400 | 任务编排器，负责任务分解和 Worker 分配 | 67% |
| `dispatcher.py` | ~350 | 多智能体调度入口，统一调度接口 | 63% |
| `worker.py` | ~300 | 工作单元，执行具体任务 | 75% |
| `enhanced_worker.py` | ~250 | 增强型 Worker，支持上下文压缩 | 70% |
| `batch_scheduler.py` | ~200 | 批量任务调度器，支持并行/串行 | 65% |
| `workflow_engine.py` | ~300 | 工作流引擎，DAG 执行 | 60% |
| `adaptive_role_selector.py` | ~180 | 自适应角色选择器 | 55% |
| `intent_workflow_mapper.py` | ~150 | 意图到工作流映射 | 60% |

#### 3.1.2 共享状态 (Shared State)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `scratchpad.py` | ~350 | 共享记忆板，Worker 间信息交换 | **91%** |
| `models.py` | **1215** | 核心数据模型定义 (dataclass/Enum) | 85% |
| `dual_layer_context.py` | ~200 | 双层上下文管理 | 68% |
| `context_compressor.py` | ~180 | 上下文压缩器，减少 token 消耗 | 72% |
| `memory_bridge.py` | ~250 | 记忆桥接，外部存储集成 | 62% |

#### 3.1.3 共识与决策 (Consensus & Decision)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `consensus.py` | ~300 | 共识引擎，五轴投票机制 | 70% |
| `five_axis_consensus.py` | ~250 | 五轴共识实现（正确性/可读性/架构/安全/性能） | 65% |
| `verification_gate.py` | ~200 | 验证门禁，证据驱动验收 | **65%** |
| `unified_gate_engine.py` | ~220 | 统一门禁引擎 | 75% |
| `test_quality_guard.py` | ~180 | 测试质量门禁 | **92%** |
| `execution_guard.py` | ~150 | 执行守卫，实时安全检查 | 78% |

#### 3.1.4 LLM 集成 (LLM Integration)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `llm_backend.py` | ~280 | LLM 后端适配器（OpenAI/Anthropic/Mock） | 72% |
| `llm_cache.py` | ~220 | LLM 缓存（内存 L1 + 磁盘 L2） | 68% |
| `llm_cache_async.py` | ~180 | 异步 LLM 缓存 | 45% |
| `llm_retry.py` | ~150 | LLM 调用重试机制 | 70% |
| `llm_retry_async.py` | ~130 | 异步重试机制 | 40% |
| `null_providers.py` | ~120 | 空 Provider（测试用） | **95%** |
| `prompt_assembler.py` | ~200 | Prompt 组装器 | 65% |

#### 3.1.5 安全与权限 (Security & Permission)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `permission_guard.py` | ~280 | 权限守卫（4级权限） | 73% |
| `input_validator.py` | ~250 | 输入验证器（53种检测模式） | 68% |
| `anti_rationalization.py` | ~180 | 反合理化机制 | 62% |
| `execution_guard_test.py` | ~150 | 执行守卫测试 | 80% |

#### 3.1.6 质量控制 (Quality Control)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `anchor_checker.py` | ~220 | 目标锚定器 (V3.6.0) | 65% |
| `retrospective.py` | ~250 | 回顾引擎 (V3.6.0) | 60% |
| `confidence_score.py` | ~150 | 置信度评分 | 72% |
| `task_completion_checker.py` | ~130 | 任务完成检查器 | 68% |
| `output_slicer.py` | ~140 | 输出切片器 | 65% |
| `operation_classifier.py` | ~160 | 操作分类器 | 70% |
| `rule_collector.py` | **400** | 规则收集器 | 36% |
| `role_matcher.py` | ~170 | 角色匹配器 | 75% |
| `ai_semantic_matcher.py` | ~190 | AI 语义匹配器 | 58% |

#### 3.1.7 监控与可观测性 (Monitoring & Observability)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `performance_monitor.py` | ~250 | 性能监控器 | 68% |
| `performance_fingerprint.py` | ~180 | 性能指纹采集 | 62% |
| `feature_usage_tracker.py` | ~160 | 功能使用追踪 | 55% |
| `usage_tracker.py` | ~140 | 使用统计 | 50% |
| `report_formatter.py` | ~130 | 报告格式化 | 70% |

#### 3.1.8 配置与工具 (Configuration & Utilities)

| 模块文件 | 行数估计 | 功能描述 | 覆盖率 |
|----------|----------|----------|--------|
| `config_loader.py` | - | *(V3.7.2 已移除)* 死代码 — 零引用 | - |
| `standardized_role_template.py` | ~200 | 标准化角色模板 | 72% |
| `skill_registry.py` | ~150 | 技能注册表 | 65% |
| `skillifier.py` | ~170 | 技能化转换器 | 68% |
| `concern_pack_loader.py` | ~140 | 关注点包加载器 | 60% |
| `similar_task_recommender.py` | ~190 | 相似任务推荐 | 52% |
| `user_friendly_error.py` | ~120 | 用户友好错误 | 78% |
| `language_parsers.py` | ~160 | 语言解析器 | 65% |
| `agent_briefing.py` | ~200 | Agent 简报生成 | 58% |
| `checkpoint_manager.py` | ~150 | 检查点管理 | 62% |
| `ci_feedback_adapter.py` | ~170 | CI 反馈适配 | 55% |
| `mce_adapter.py` | ~140 | MCE 适配器 | 48% |
| `protocols.py` | ~200 | 协议定义 | 72% |
| `lifecycle_protocol.py` | ~250 | 生命周期协议 | 66% |
| `_version.py` | ~5 | 版本定义 | N/A |

### 3.2 API 服务模块 (API Services) - 8 个文件

| 模块文件 | 功能描述 | 覆盖率 |
|----------|----------|--------|
| `api_server.py` | FastAPI 应用主入口 | ~10% |
| `api/__init__.py` | API 包初始化 | N/A |
| `api/models.py` | API 数据模型 | 45% |
| `api/routes/dispatch.py` | 调度路由 | 35% |
| `api/routes/lifecycle.py` | 生命周期路由 | 40% |
| `api/routes/metrics_gates.py` | 指标门禁路由 | 38% |
| `api/routes/__init__.py` | 路由包初始化 | N/A |
| `auth.py` | 认证管理 | 40% |

### 3.3 CLI 模块 (Command Line Interface) - 3 个文件

| 模块文件 | 功能描述 | 覆盖率 |
|----------|----------|--------|
| `cli.py` | CLI 入口，argparse 命令解析 | 27% |
| `cli/cli_visual.py` | CLI 可视化输出 | 35% |
| `cli/__init__.py` | CLI 包初始化 | N/A |

### 3.4 辅助服务模块 (Auxiliary Services) - 4 个文件

| 模块文件 | 功能描述 | 覆盖率 |
|----------|----------|--------|
| `dashboard.py` | Streamlit Web Dashboard | **0%** |
| `mcp_server.py` | MCP 协议服务器 | **0%** |
| `history_manager.py` | 历史记录管理 | 38% |
| `generate_benchmark_report.py` | 基准测试报告生成 | 30% |

### 3.5 技能模块 (Skills) - 12 个文件

| 技能路径 | 功能描述 | 代码行数 |
|----------|----------|----------|
| `skills/__init__.py` | 技能包初始化 | 10 |
| `skills/registry.py` | 技能注册中心 | 80 |
| `skills/dispatch/handler.py` | 调度技能处理器 | ~50 |
| `skills/dispatch/skill-manifest.yaml` | 调度技能元数据 | 25 |
| `skills/intent/handler.py` | 意图识别处理器 | ~50 |
| `skills/intent/skill-manifest.yaml` | 意图技能元数据 | 25 |
| `skills/retrospective/handler.py` | 回顾技能处理器 | ~60 |
| `skills/retrospective/skill-manifest.yaml` | 回顾技能元数据 | 28 |
| `skills/review/handler.py` | 审查技能处理器 | ~50 |
| `skills/review/skill-manifest.yaml` | 审查技能元数据 | 25 |
| `skills/security/handler.py` | 安全扫描处理器 | ~50 |
| `skills/security/skill-manifest.yaml` | 安全技能元数据 | 25 |
| `skills/test/handler.py` | 测试执行处理器 | ~55 |
| `skills/test/skill-manifest.yaml` | 测试技能元数据 | 26 |

**模块总计**：
- 协作核心模块：**113+ 个文件** (scripts/collaboration/)
- API 服务模块：**8 个文件** (scripts/api/)
- CLI 模块：**3 个文件** (scripts/cli/)
- QA 模块：**3 个文件** (scripts/qa/, V4.0.0 新增)
- Dashboard 模块：**8 个文件** (scripts/dashboard/, V4.0.0 拆分)
- 辅助服务：**4 个文件**
- 技能模块：**14 个文件**
- **总计：185+ 个 Python/YAML 文件**

> **完整模块清单**：参见 [SKILL.md](../../SKILL.md) 模块表（113 个核心模块详细描述）。

---

## 4. API 规范

### 4.1 CLI 命令规范

#### 4.1.1 命令结构

```bash
devsquad [COMMAND] [OPTIONS]
```

#### 4.1.2 核心命令列表

| 命令 | 用途 | 关键参数 | 示例 |
|------|------|----------|------|
| `dispatch` | 执行多智能体协作任务 | `-t`, `-r`, `-m`, `-f`, `--backend` | `devsquad dispatch -t "design auth" -r arch coder` |
| `demo` | 快速演示（Mock 模式） | `--scenario` | `devsquad demo --scenario intent` |
| `status` | 查看系统状态 | (无) | `devsquad status` |
| `roles` | 列出可用角色 | (无) | `devsquad roles` |
| `--version` | 显示版本号 | (无) | `devsquad --version` |

#### 4.1.3 Lifecycle 子命令

| 命令 | 描述 | 必需角色 | 默认模式 | 门禁条件 |
|------|------|----------|----------|----------|
| `spec` | 定义需求规格 | architect, pm | sequential | spec_first |
| `plan` | 任务分解规划 | architect, pm | auto | task_breakdown_complete |
| `build` | 增量实现 (TDD) | arch, coder, tester | parallel | incremental_verification |
| `test` | 运行测试验证 | tester, coder | consensus | evidence_required |
| `review` | 五轴代码审查 | coder, sec, tester, arch | consensus | change_size_limit |
| `ship` | 发布准备 | devops, sec, arch | sequential | pre_launch_checklist |

#### 4.1.4 Dispatch 命令详细参数

```bash
devsquad dispatch \
  -t "任务描述" \                          # 必需：任务文本
  -r architect coder tester \             # 可选：角色列表（空格分隔）
  -m auto \                               # 模式：auto/parallel/sequential/consensus
  -f markdown \                           # 输出格式：markdown/json/compact/structured/detailed
  --backend mock \                        # LLM后端：mock/openai/anthropic
  --base-url https://api.openai.com \     # 自定义 API 地址
  --model gpt-4 \                         # 指定模型
  --dry-run \                             # 仅分析不执行
  --verbose \                             # 详细输出
  --config ./config.yaml \                # 自定义配置文件
  --output result.md \                    # 输出文件路径
```

#### 4.1.5 全局选项

| 选项 | 环境变量 | 默认值 | 描述 |
|------|----------|--------|------|
| `--backend` | `DEVSQUAD_LLM_BACKEND` | `mock` | LLM 后端类型 |
| `--lang` | `DEVSQUAD_LANG` | `auto` | 界面语言 (en/cn/jp/auto) |
| `--persist-dir` | `DEVSQUAD_PERSIST_DIR` | `.devsquad_data` | 持久化目录 |
| `--log-level` | `DEVSQUAD_LOG_LEVEL` | `INFO` | 日志级别 |
| `--version` | - | - | 显示版本号 |
| `--help` | - | - | 显示帮助信息 |

---

### 4.2 REST API 端点

#### 4.2.1 基础信息

| 属性 | 值 |
|------|-----|
| **Base URL** | `/api/v1` |
| **协议** | HTTP/1.1, HTTPS (生产环境) |
| **认证方式** | Optional Bearer Token (AuthManager) |
| **限流策略** | 60 requests/min/IP |
| **CORS** | 已启用（开发环境） |
| **文档** | Swagger UI: `/docs`, ReDoc: `/redoc` |

#### 4.2.2 端点列表

##### Task Dispatch (任务调度)

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/v1/tasks/dispatch` | 执行多智能体任务 | TaskDispatchRequest | DispatchResponse |
| `POST` | `/api/v1/tasks/quick` | 快速调度 | QuickDispatchRequest | DispatchResponse |
| `GET` | `/api/v1/tasks/history` | 获取历史记录 | - | DispatchHistoryResponse |
| `GET` | `/api/v1/roles` | 可用角色列表 | - | RolesListResponse |

##### Lifecycle Management (生命周期)

| Method | Endpoint | Description | Parameters | Response |
|--------|----------|-------------|------------|----------|
| `GET` | `/api/v1/lifecycle/phases` | 获取所有阶段 | status_filter, include_details | list[LifecyclePhase] |
| `GET` | `/api/v1/lifecycle/phases/{phase_id}` | 获取阶段详情 | phase_id | LifecyclePhase |
| `POST` | `/api/v1/lifecycle/actions` | 执行阶段操作 (advance/complete/reset/skip) | PhaseActionRequest | PhaseActionResult |
| `GET` | `/api/v1/lifecycle/status` | 当前生命周期状态 | - | LifecycleStatusResponse |
| `GET` | `/api/v1/lifecycle/mappings` | CLI 命令映射 | - | list[CommandMapping] |

##### Metrics & Gates (指标与门禁)

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/api/v1/metrics/current` | 当前指标快照 | MetricsSnapshot |
| `GET` | `/api/v1/metrics/history` | 历史指标数据 | MetricsHistoryResponse |
| `GET` | `/api/v1/gates/status` | 门禁状态列表 | GateStatusListResponse |
| `POST` | `/api/v1/gates/check` | 执行门禁检查 | GateCheckRequest | GateResult |

##### System (系统)

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/api/v1/health` | 健康检查 | HealthCheck |
| `GET` | `/metrics` | Prometheus 指标 | PlainText (exposition format) |

#### 4.2.3 请求/响应模型示例

**TaskDispatchRequest**:
```python
class TaskDispatchRequest(BaseModel):
    task: str                              # 任务描述
    roles: list[str] | None = None         # 角色列表（可选）
    mode: str = "auto"                     # 执行模式
    output_format: str = "markdown"        # 输出格式
    backend: str = "mock"                  # LLM 后端
    dry_run: bool = False                  # 干跑模式
```

**DispatchResponse**:
```python
class DispatchResponse(BaseModel):
    success: bool                          # 是否成功
    task_description: str                  # 任务描述
    matched_roles: list[str]               # 匹配的角色
    summary: str                           # 摘要
    duration_seconds: float                # 总耗时
    worker_results: list[WorkerResultItem] # Worker 结果列表
    errors: list[str]                      # 错误列表
    intent_match: IntentMatchInfo | None   # 意图匹配
    five_axis_result: FiveAxisResult | None # 五轴共识结果
    anchor_result: AnchorResult | None     # 锚定结果
    timestamp: str                         # 完成时间戳
```

---

### 4.3 Python API

#### 4.3.1 核心类签名

```python
# ===== 核心编排类 =====

class MultiAgentDispatcher:
    """多智能体调度器 - 统一入口"""

    def __init__(
        self,
        backend_type: str = "mock",
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        config_path: str | None = None,
        persist_dir: str = ".devsquad_data",
    ): ...

    def dispatch(
        self,
        task: str,
        roles: list[str] | None = None,
        mode: str = "auto",
        output_format: str = "markdown",
        dry_run: bool = False,
    ) -> dict[str, Any]: ...

    def quick_dispatch(
        self,
        task: str,
        format: str = "compact",
    ) -> str: ...

    def analyze_intent(self, task: str) -> IntentAnalysisResult: ...

    def get_status(self) -> SystemStatus: ...

    def get_available_roles(self) -> list[RoleDefinition]: ...

    def shutdown(self): ...


class Coordinator:
    """任务协调器 - 负责任务分解和分配"""

    def __init__(
        self,
        scratchpad: Scratchpad,
        llm_backend: LLMBackend,
        config: dict[str, Any],
    ): ...

    def plan_task(
        self,
        task_description: str,
        roles: list[str],
        mode: str = "auto",
    ) -> ExecutionPlan: ...

    def execute_plan(
        self,
        plan: ExecutionPlan,
    ) -> ScheduleResult: ...

    def post_process(
        self,
        result: ScheduleResult,
        goal: StructuredGoal | None = None,
    ) -> RetrospectiveReport: ...


class Worker:
    """工作单元 - 执行具体任务"""

    def __init__(
        self,
        worker_id: str,
        role: RoleDefinition,
        scratchpad: Scratchpad,
        llm_backend: LLMBackend,
    ): ...

    def execute(self, task: TaskDefinition) -> WorkerResult: ...

    def read_scratchpad(self) -> list[ScratchpadEntry]: ...

    def write_entry(self, entry: ScratchpadEntry) -> bool: ...

    def send_notification(self, notification: TaskNotification) -> bool: ...


class Scratchpad:
    """共享记忆板 - Worker 间信息交换"""

    def write(self, entry: ScratchpadEntry) -> str: ...

    def read(
        self,
        role_filter: str | None = None,
        entry_type: EntryType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ScratchpadEntry]: ...

    def update_entry(
        self,
        entry_id: str,
        updates: dict[str, Any],
    ) -> bool: ...

    def query_by_tags(self, tags: list[str]) -> list[ScratchpadEntry]: ...

    def get_timeline(self) -> list[ScratchpadEntry]: ...


class ConsensusEngine:
    """共识引擎 - 多 Worker 决策协调"""

    def __init__(
        self,
        threshold: float = 0.67,
        enable_veto: bool = True,
    ): ...

    def create_proposal(
        self,
        topic: str,
        content: str,
        options: list[str] | None = None,
    ) -> DecisionProposal: ...

    def cast_vote(
        self,
        proposal: DecisionProposal,
        vote: Vote,
    ) -> DecisionProposal: ...

    def reach_consensus(
        self,
        proposal: DecisionProposal,
    ) -> ConsensusRecord: ...


class BatchScheduler:
    """批量任务调度器"""

    def __init__(
        self,
        max_concurrency: int = 5,
        timeout_seconds: int = 600,
    ): ...

    def schedule(
        self,
        batches: list[TaskBatch],
    ) -> ScheduleResult: ...


# ===== 控制论增强类 (V3.6.0) =====

class AnchorChecker:
    """目标锚定器 - 检测目标偏移"""

    def __init__(self, tolerance: float = 0.2): ...

    def check(
        self,
        goal: StructuredGoal,
        current_state: dict[str, Any],
        trigger: AnchorTrigger = AnchorTrigger.STEP_COMPLETE,
    ) -> AnchorResult: ...


class RetrospectiveEngine:
    """回顾引擎 - 任务后分析"""

    def analyze(
        self,
        goal: StructuredGoal,
        execution_log: list[dict[str, Any]],
        results: list[WorkerResult],
    ) -> RetrospectiveReport: ...


# ===== 安全与验证类 =====

class PermissionGuard:
    """权限守卫 - 4级权限控制"""

    class PermissionLevel(Enum):
        DEFAULT = "default"    # 默认：写操作需确认
        PLAN = "plan"          # 计划：只读操作
        AUTO = "auto"          # 自动：AI 分类器自动判断
        BYPASS = "bypass"      # 绕过：完全跳过（最高信任）

    def check_permission(
        self,
        level: PermissionLevel,
        action: str,
    ) -> bool: ...

    def validate_input(
        self,
        input_data: str,
        context: str = "general",
    ) -> ValidationResult: ...


class InputValidator:
    """输入验证器 - 53种注入检测 (15 forbidden + 13 SSRF + 5 suspicious + 20 prompt injection)"""

    def validate(self, text: str) -> ValidationResult: ...

    def detect_injection_patterns(self, text: str) -> list[str]: ...

    def sanitize(self, text: str) -> str: ...


class VerificationGate:
    """验证门禁 - 证据驱动验收"""

    def verify(
        self,
        evidence: dict[str, Any],
        criteria: dict[str, Any],
    ) -> GateResult: ...

    def check_test_evidence(
        self,
        test_output: str,
    ) -> TestGateResult: ...
```

#### 4.3.2 主要方法调用示例

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# 创建调度器实例
dispatcher = MultiAgentDispatcher(
    backend_type="openai",
    model="gpt-4"
)

# 执行完整协作任务
result = dispatcher.dispatch(
    task="设计用户认证系统的微服务架构",
    roles=["architect", "security", "devops"],
    mode="consensus",
    output_format="json"
)

# 快速调度
quick_result = dispatcher.quick_dispatch(
    task="review code quality"
)

# 意图分析（干跑）
analysis = dispatcher.analyze_intent(
    task="优化数据库查询性能"
)

# 获取系统状态
status = dispatcher.get_status()
print(f"Active workers: {status.active_workers}")
print(f"Success rate: {status.success_rate:.1%}")

# 清理资源
dispatcher.shutdown()
```

---

### 4.4 MCP 协议接口

#### 4.4.1 Server 信息

| 属性 | 值 |
|------|-----|
| **Server Name** | `DevSquad` |
| **Transport** | stdio (default), SSE (optional) |
| **Tools Count** | 5 |

#### 4.4.2 Tool 列表

| Tool Name | 参数 | 返回值 | 描述 |
|-----------|------|--------|------|
| `multiagent_dispatch` | task, roles, mode, output_format, dry_run | `str` | 执行完整多智能体协作任务 |
| `multiagent_quick` | task, format | `str` | 快速调度（简化参数） |
| `multiagent_roles` | (无) | `str` | 列出可用角色及描述 |
| `multiagent_status` | (无) | `str` | 系统状态和能力 |
| `multiagent_analyze` | task | `str` | 分析任务意图（干跑模式） |

#### 4.4.3 使用示例

```python
# 启动 MCP Server (stdio 模式)
python scripts/mcp_server.py

# 启动 MCP Server (SSE 模式，端口 8080)
python scripts/mcp_server.py --port 8080

# 在 Claude Code / Cursor 中使用
# Tool: multiagent_dispatch
# Args: {"task": "design REST API", "roles": ["arch", "coder"], "mode": "consensus"}
```

---

## 5. 数据模型

### 5.1 核心枚举 (Enums)

#### EntryType - 记录类型

| 枚举值 | 值 | 描述 |
|--------|-----|------|
| `FINDING` | `"finding"` | Worker 发现或输出（默认） |
| `DECISION` | `"decision"` | 共识决策或协议 |
| `CONFLICT` | `"conflict"` | 检测到的冲突 |
| `QUESTION` | `"question"` | 查询或澄清请求 |
| `SUGGESTION` | `"suggestion"` | 改进提案或建议 |
| `WARNING` | `"warning"` | 警告或注意通知 |

#### EntryStatus - 记录状态

| 枚举值 | 值 | 描述 |
|--------|-----|------|
| `ACTIVE` | `"active"` | 活跃状态，对 Worker 可见 |
| `RESOLVED` | `"resolved"` | 问题或冲突已解决 |
| `SUPERSEDED` | `"superseded"` | 被新版本替代 |
| `REJECTED` | `"rejected"` | 已拒绝或驳回 |

#### ReferenceType - 引用关系

| 枚举值 | 值 | 描述 |
|--------|-----|------|
| `SUPPORTS` | `"supports"` | 支持证据 |
| `CONTRADICTS` | `"contradicts"` | 矛盾或反驳 |
| `EXTENDS` | `"extends"` | 扩展或构建 |
| `CLARIFIES` | `"clarifies"` | 澄清说明 |

#### BatchMode - 批处理模式

| 枚举值 | 值 | 描述 |
|--------|-----|------|
| `PARALLEL` | `"parallel"` | 并行执行（最多 max_concurrency） |
| `SERIAL` | `"serial"` | 串行执行（有序重试） |

#### DecisionOutcome - 决策结果

| 枚举值 | 值 | 描述 |
|--------|-----|------|
| `APPROVED` | `"approved"` | 通过所有阈值 |
| `REJECTED` | `"rejected"` | 未达最低阈值 |
| `SPLIT` | `"split"` | 票数过于接近（40-60%） |
| `ESCALATED` | `"escalated"` | 否决权或不可调和冲突 |
| `TIMEOUT` | `"timeout"` | 超时自动解决 |

#### GoalItemStatus - 目标项状态 (V3.6.0)

| 枚举值 | 值 | 描述 |
|--------|-----|------|
| `PENDING` | `"pending"` | 未开始 |
| `PARTIALLY_COVERED` | `"partially_covered"` | 部分完成 |
| `FULLY_COVERED` | `"fully_covered"` | 完全覆盖 |
| `EXCEEDED` | `"exceeded"` | 超出预期 |

#### AnchorTrigger - 锚定触发时机 (V3.6.0)

| 枚举值 | 值 | 描述 |
|--------|-----|------|
| `STEP_COMPLETE` | `"step_complete"` | 步骤完成时 |
| `PHASE_GATE` | `"phase_gate"` | 阶段转换点 |
| `DIRECTION_CHANGE` | `"direction_change"` | 方向显著变化 |
| `CONFLICT` | `"conflict"` | 检测到冲突 |
| `MILESTONE` | `"milestone"` | 预定义里程碑 |

#### DriftSeverity - 偏移严重程度 (V3.6.0)

| 枚举值 | 值 | 阈值范围 | 描述 |
|--------|-----|----------|------|
| `NONE` | `"none"` | < 0.1 | 无偏移 |
| `LOW` | `"low"` | 0.1-0.2 | 轻微偏差 |
| `MEDIUM` | `"medium"` | 0.2-0.3 | 中等偏移 |
| `HIGH` | `"high"` | 0.3-0.5 | 显著偏移 |
| `CRITICAL` | `"critical"` | >= 0.5 | 严重偏移 |

### 5.2 核心 DataClass

#### ScratchpadEntry - 共享记录条目

```python
@dataclass
class ScratchpadEntry:
    entry_id: str                                    # 唯一标识（自动生成）
    worker_id: str = ""                              # 创建者 Worker ID
    role_id: str = ""                                # 角色标识
    timestamp: datetime                              # 创建时间
    entry_type: EntryType = EntryType.FINDING        # 类型分类
    content: str = ""                                # 主内容
    confidence: float = 0.5                          # 置信度 0.0-1.0
    tags: list[str]                                  # 可搜索标签
    references: list[Reference]                      # 交叉引用
    status: EntryStatus = EntryStatus.ACTIVE         # 生命周期状态
    version: int = 1                                 # 版本号（冲突解决）
```

#### TaskDefinition - 任务定义

```python
@dataclass
class TaskDefinition:
    task_id: str                                     # 唯一标识（自动生成）
    description: str                                 # 任务描述
    role_id: str                                     # 目标角色 ID
    role_prompt: str = ""                            # 角色指令
    stage_id: str | None = None                      # 工作流阶段
    input_data: dict[str, Any]                       # 附加上下文
    dependencies: list[str]                          # 前置任务 ID
    is_read_only: bool = True                        # 是否只读
    timeout_seconds: int = 300                       # 超时时间（秒）
    retry_count: int = 3                             # 重试次数
```

#### WorkerResult - Worker 结果

```python
@dataclass
class WorkerResult:
    worker_id: str                                   # Worker ID
    task_id: str                                     # 任务 ID
    success: bool                                    # 是否成功
    output: Any = None                               # 输出内容
    error: str | None = None                         # 错误信息
    scratchpad_entries_written: int = 0              # 写入的记录数
    notifications_sent: int = 0                      # 发送的通知数
    duration_seconds: float = 0.0                    # 执行耗时
```

#### Vote - 共识投票

```python
@dataclass
class Vote:
    voter_id: str                                    # 投票者 ID
    voter_role: str                                  # 投票者角色
    decision: bool                                   # 决策方向（True=赞成）
    reason: str = ""                                 # 投票理由
    weight: float = 1.0                              # 投票权重
    confidence: float = 0.7                          # 置信度
    timestamp: datetime                              # 投票时间
```

#### DecisionProposal - 决策提案

```python
@dataclass
class DecisionProposal:
    proposal_id: str                                 # 唯一标识
    topic: str                                       # 提案主题
    proposer_id: str                                 # 提案人 ID
    proposal_content: str                            # 提案内容
    options: list[str]                               # 投票选项
    deadline: datetime | None = None                 # 投票截止时间
    votes: list[Vote]                                # 已投票列表
    status: str = "open"                             # 状态（open/closed/cancelled）
```

#### ConsensusRecord - 共识记录

```python
@dataclass
class ConsensusRecord:
    record_id: str                                   # 记录 ID
    topic: str                                       # 决策主题
    outcome: DecisionOutcome                         # 最终结果
    final_decision: str                              # 最终决策摘要
    votes_for: int                                   # 赞成票数
    votes_against: int                               # 反对票数
    votes_abstain: int                               # 弃权票数
    total_weight_for: float                          # 赞成权重和
    total_weight_against: float                      # 反对权重和
    participants: list[str]                          # 参与者列表
    escalation_reason: str | None = None             # 升级原因
    timestamp: datetime                              # 达成时间
```

#### ExecutionPlan - 执行计划

```python
@dataclass
class ExecutionPlan:
    plan_id: str                                     # 计划 ID
    batches: list[Any]                               # 任务批次列表
    total_tasks: int                                 # 总任务数
    estimated_parallelism: float                     # 预估并行度 0.0-1.0
```

#### TaskBatch - 任务批次

```python
@dataclass
class TaskBatch:
    batch_id: str                                    # 批次 ID
    mode: BatchMode = BatchMode.PARALLEL             # 执行模式
    tasks: list[TaskDefinition]                      # 任务列表
    max_concurrency: int = 5                         # 最大并行数
    dependencies: list[str]                          # 前置批次 ID
    timeout_seconds: int = 600                       # 批次超时
```

#### ScheduleResult - 调度结果

```python
@dataclass
class ScheduleResult:
    success: bool = False                            # 是否全部成功
    total_tasks: int = 0                             # 总任务数
    completed_tasks: int = 0                         # 已完成任务
    failed_tasks: int = 0                            # 失败任务数
    results: list[WorkerResult]                      # 结果列表
    duration_seconds: float = 0.0                    # 总耗时
    errors: list[str]                                # 错误列表
```

### 5.3 V3.6.0 新增数据模型 (Cybernetics Enhancement)

#### StructuredGoal - 结构化目标

```python
@dataclass
class StructuredGoal:
    goal_id: str = ""                                # 目标 ID
    original_description: str = ""                   # 原始描述
    items: list[GoalItem]                            # 目标项列表
    created_at: str = ""                             # 创建时间

    @property
    def overall_coverage(self) -> float: ...         # 平均覆盖率 0.0-1.0

    @property
    def uncovered_items(self) -> list[GoalItem]: ... # 未覆盖项列表
```

#### GoalItem - 目标项

```python
@dataclass
class GoalItem:
    item_id: str                                     # 项 ID
    description: str                                 # 描述
    keywords: list[str]                              # 匹配关键词
    status: GoalItemStatus = GoalItemStatus.PENDING  # 状态
    coverage_score: float = 0.0                      # 覆盖分数 0.0-1.0
    evidence: list[str]                              # 证据列表
```

#### AnchorResult - 锚定结果

```python
@dataclass
class AnchorResult:
    aligned: bool = True                             # 是否对齐
    trigger: AnchorTrigger = AnchorTrigger.STEP_COMPLETE  # 触发事件
    coverage: float = 1.0                            # 当前覆盖率
    drift_score: float = 0.0                         # 偏移分数
    drifts: list[DriftItem]                          # 偏移列表
    uncovered_goals: list[str]                        # 未覆盖目标
    recommendation: str = ""                         # 建议措施
    checked_at: str = ""                             # 检查时间

    @property
    def severity(self) -> DriftSeverity: ...         # 计算严重程度
```

#### RetrospectiveReport - 回顾报告

```python
@dataclass
class RetrospectiveReport:
    task_goal: str = ""                              # 任务目标
    goal_id: str = ""                                # 目标 ID
    deviations: list[DeviationRecord]                 # 偏差列表
    redundant_steps: list[str]                        # 冗余步骤
    improvements: list[str]                           # 改进建议
    anchor_check_count: int = 0                      # 锚定检查次数
    anchor_drift_count: int = 0                      # 偏移检测次数
    final_coverage: float = 1.0                      # 最终覆盖率
    summary: str = ""                                # 执行摘要
    created_at: str = ""                             # 创建时间

    def to_dict(self) -> dict[str, Any]: ...         # 序列化为字典

    def to_markdown(self) -> str: ...                # 生成 Markdown 报告
```

### 5.4 角色定义 (Role Registry)

| role_id | 名称 | 别名 | 权重 | 关键词示例 |
|---------|------|------|------|------------|
| `architect` | 架构师 | ["arch"] | **1.5** | 架构, 设计, 选型, 微服务, performance |
| `product-manager` | 产品经理 | ["pm"] | **1.2** | 需求, PRD, 用户故事, acceptance, feature |
| `security` | 安全专家 | ["sec"] | **1.1** | 安全, 漏洞, OWASP, 加密, compliance |
| `tester` | 测试专家 | ["test", "qa"] | **1.0** | 测试, 质量, 自动化, coverage, validation |
| `solo-coder` | 独立开发者 | ["coder", "dev"] | **1.0** | 实现, 开发, 代码, 优化, refactor |
| `devops` | DevOps工程师 | ["infra"] | **1.0** | CI/CD, Docker, K8s, deploy, monitoring |
| `ui-designer` | UI设计师 | ["ui"] | **0.9** | UI, 界面, 前端, prototype, UX |

---

## 6. 配置系统

### 6.1 环境变量

#### LLM 后端配置

| 变量名 | 必需 | 默认值 | 描述 |
|--------|------|--------|------|
| `OPENAI_API_KEY` | 条件* | - | OpenAI API 密钥（使用 openai 后端时必需） |
| `OPENAI_BASE_URL` | 否 | - | OpenAI API 自定义地址 |
| `OPENAI_MODEL` | 否 | `gpt-4` | OpenAI 模型名称 |
| `ANTHROPIC_API_KEY` | 条件* | - | Anthropic API 密钥（使用 anthropic 后端时必需） |
| `ANTHROPIC_MODEL` | 否 | `claude-sonnet-4-20250514` | Anthropic 模型名称 |
| `MOKA_API_KEY` | 条件* | - | Moka AI API 密钥（使用 moka 后端时必需，V4.0.7+） |
| `MOKA_BASE_URL` | 否 | - | Moka AI 自定义地址 |
| `MOKA_MODEL` | 否 | - | Moka AI 模型名称 |
| `DEVSQUAD_LLM_BACKEND` | 否 | `mock` | 默认后端：mock/openai/anthropic/moka/auto/fallback/trae |

#### 系统配置

| 变量名 | 默认值 | 描述 |
|--------|--------|------|
| `DEVSQUAD_PERSIST_DIR` | `.devsquad_data` | 持久化数据目录 |
| `DEVSQUAD_LANG` | `auto` | 界面语言：en/cn/jp/auto |
| `DEVSQUAD_LOG_LEVEL` | `INFO` | 日志级别：DEBUG/INFO/WARNING/ERROR |
| `WORKBUDDY_CLAW_PATH` | - | WorkBuddy Claw 路径（自动检测） |

#### 认证配置（可选）

| 变量名 | 描述 |
|--------|------|
| `DEVSQUAD_DEMO_ADMIN_PASSWORD` | Demo 管理员密码 |
| `DEVSQUAD_DEMO_OPERATOR_PASSWORD` | Demo 操作员密码 |
| `DEVSQUAD_DEMO_VIEWER_PASSWORD` | Demo 查看者密码 |

### 6.2 YAML 配置文件

#### 项目配置 (.devsquad.yaml)

```yaml
# DevSquad Project Configuration
project:
  name: "my-project"
  version: "1.0.0"

collaboration:
  default_mode: "auto"
  max_workers: 7
  timeout_seconds: 300
  retry_count: 3

consensus:
  threshold: 0.67           # super_majority
  enable_veto: true
  timeout_seconds: 60

caching:
  enable_l1: true           # 内存缓存
  enable_l2: true           # 磁盘缓存
  l2_dir: ".devsquad_data/cache"
  ttl_seconds: 3600

security:
  permission_level: "default"  # DEFAULT/PLAN/AUTO/BYPASS
  input_validation: true
  injection_detection: true    # 53 patterns (15 forbidden+13 SSRF+5 suspicious+20 prompt injection)

monitoring:
  enable_performance_monitor: true
  metrics_interval: 30      # seconds
  log_format: "text"        # text | json (Phase 8)

lifecycle:
  enabled: true
  auto_advance: false       # 手动推进
```

#### 部署配置 (config/deployment.yaml)

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  log_level: "info"

api:
  cors_origins: ["*"]
  rate_limit: 60            # requests/min
  auth_enabled: false       # 生产环境建议开启

dashboard:
  enabled: true
  port: 8501

mcp:
  enabled: true
  transport: "stdio"        # stdio | sse
  sse_port: 8080
```

### 6.3 配置优先级

```
环境变量 > 命令行参数 > YAML 配置文件 > 默认值
```

**加载顺序**：
1. 内置默认值
2. `.devsquad.yaml`（项目根目录）
3. `config/deployment.yaml`（全局配置）
4. 环境变量覆盖
5. 命令行参数（最高优先级）

---

## 7. 部署方案

### 7.1 本地开发环境

#### 前置条件

```bash
# Python 3.10+
python3 --version  # >= 3.10

# 克隆仓库
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -e ".[all]"   # 安装所有可选依赖

# 或最小安装
pip install -e .
```

#### 快速启动

```bash
# 验证安装
devsquad --version
# 输出: DevSquad V4.0.11

# Mock 模式演示（无需 API Key）
devsquad demo --scenario all

# 执行实际任务（需要 API Key）
export OPENAI_API_KEY="sk-..."
devsquad dispatch -t "design user auth system" -r architect security coder

# 启动 API 服务
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# 启动 Dashboard
streamlit run scripts/dashboard.py

# 启动 MCP Server
python scripts/mcp_server.py
```

### 7.2 Docker 部署

#### 构建镜像

```bash
# 多阶段构建（推荐，镜像更小）
docker build -t devsquad:4.0.11 .

# 查看镜像大小（预计 ~200MB）
docker images devsquad:4.0.11
```

#### 运行容器

```bash
# 基本运行
docker run -d \
  --name devsquad \
  -p 8000:8000 \
  -p 8501:8501 \
  -e DEVSQUAD_LLM_BACKEND=mock \
  devsquad:4.0.11

# 带 API Key 的生产运行
docker run -d \
  --name devsquad \
  -p 8000:8000 \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  -e DEVSQUAD_LLM_BACKEND=openai \
  -v $(pwd)/.devsquad_data:/app/.devsquad_data \
  devsquad:4.0.11

# 进入开发容器
docker run -it --rm devsquad:4.0.11-dev bash
```

#### Docker Compose

```yaml
# docker-compose.yml (项目已提供)
version: '3.8'
services:
  devsquad-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEVSQUAD_LLM_BACKEND=${DEVSQUAD_LLM_BACKEND:-mock}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
    volumes:
      - .devsquad_data:/app/.devsquad_data
    healthcheck:
      test: ["CMD", "python3", "-c", "from scripts.collaboration._version import __version__; print(__version__)"]
      interval: 30s
      timeout: 5s
      retries: 3

  devsquad-dashboard:
    build: .
    ports:
      - "8501:8501"
    environment:
      - DEVSQUAD_API_URL=http://devsquad-api:8000
    depends_on:
      - devsquad-api
```

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 7.3 Kubernetes 部署 (Helm Chart)

#### Helm Chart 结构

```
helm/devsquad/
├── Chart.yaml              # Chart 元数据 (version: 4.0.11)
├── README.md               # 使用说明
├── values.yaml             # 默认配置值
└── templates/
    ├── _helpers.tpl        # 模板辅助函数
    ├── configmap.yaml      # ConfigMap（配置注入）
    ├── deployment.yaml     # Deployment（工作负载）
    ├── ingress.yaml        # Ingress（路由规则）
    ├── pvc.yaml            # PVC（持久化存储）
    ├── service.yaml        # Service（集群内访问）
    └── serviceaccount.yaml # ServiceAccount（RBAC）
```

#### 部署命令

```bash
# 添加 Helm 仓库（如果有）
# helm repo add devsquad https://github.com/lulin70/DevSquad/charts

# 安装 Release
helm install my-devsquad ./helm/devsquad \
  --namespace devsquad \
  --create-namespace \
  --set image.tag=4.0.11 \
  --set env.OPENAI_API_KEY="${OPENAI_API_KEY}" \
  --set persistence.enabled=true

# 升级 Release
helm upgrade my-devsquad ./helm/devsquad \
  --set image.tag=4.0.11

# 查看 Release 状态
helm status my-devsquad -n devsquad

# 卸载
helm uninstall my-devsquad -n devsquad
```

#### values.yaml 关键配置

```yaml
replicaCount: 1

image:
  repository: ghcr.io/lulin70/devsquad
  tag: 4.0.11
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8000

dashboard:
  enabled: true
  port: 8501
  service:
    type: LoadBalancer

resources:
  limits:
    cpu: "2"
    memory: 4Gi
  requests:
    cpu: "500m"
    memory: 1Gi

persistence:
  enabled: true
  size: 10Gi
  storageClass: standard

env:
  DEVSQUAD_LLM_BACKEND: "mock"
  DEVSQUAD_LOG_LEVEL: "INFO"

nodeSelector: {}
tolerations: []
affinity: {}
```

### 7.4 生产环境检查清单

- [ ] **基础设施**
  - [ ] Kubernetes 集群 (≥3 nodes, ≥8CPU, ≥16GB RAM)
  - [ ] PersistentVolume (≥10GB for .devsquad_data)
  - [ ] Ingress Controller (nginx/traefik)
  - [ ] Certificate Manager (TLS termination)

- [ ] **配置管理**
  - [ ] Secrets 管理 (Kubernetes Secrets / Vault)
  - [ ] API Keys 注入 (非硬编码)
  - [ ] 环境变量完整配置

- [ ] **可观测性**
  - [ ] Prometheus + Grafana (Phase 8 增强)
  - [ ] 日志聚合 (ELK/Loki)
  - [ ] 告警通道 (Slack/PagerDuty)

- [ ] **安全加固**
  - [ ] 网络策略 (NetworkPolicy)
  - [ ] RBAC 配置 (最小权限原则)
  - [ ] 认证开启 (`auth_enabled: true`)
  - [ ] CORS 限制 (仅允许信任域名)

- [ ] **高可用**
  - [ ] Pod 反亲和 (分布在不同节点)
  - [ ] HPA (水平自动伸缩)
  - [ ] PDB (Pod 中断预算)

---

## 8. 测试策略

### 8.1 测试金字塔

```
                    ╱╲
                   ╱ E2E ╲                  5%  (端到端测试)
                  ╱────────╲
                 ╱ Integration ╲            20% (集成测试)
                ╱────────────────╲
               ╱    Unit Tests    ╲         75% (单元测试)
              ╱──────────────────────╲
```

### 8.2 测试分类

| 类别 | 标记 | 数量 | 占比 | 描述 |
|------|------|------|------|------|
| **Unit Tests** | `@pytest.mark.unit` | ~3450 | 75% | 单函数/方法测试 |
| **Integration Tests** | `@pytest.mark.integration` | ~920 | 20% | 模块间交互测试 |
| **E2E Tests** | `@pytest.mark.e2e` | ~200 | 4% | 完整流程测试 |
| **Contract Tests** | (tests/contract/) | ~234 | 1% | 接口契约测试 |
| **Smoke Tests** | (tests/smoke/) | ~30 | <1% | 冒烟测试 |
| **版本一致性测试** | (tests/test_version_consistency.py) | ~15 | <1% | 跨文件版本号一致性 |
| **总计** | - | **4603+** | 100% | CI 权威 |

### 8.3 测试覆盖率现状

| 指标 | 当前值 | 目标值 | 状态 |
|------|--------|--------|------|
| **总体覆盖率** | **80.03%+** | 75% (CI gate) | ✅ 超过门禁 |
| **测试总数** | **4603+** | 持续增长 | ✅ 良好 |
| **通过率** | **100%** (4603/4603) | >99% | ✅ 达标 |
| **CI 门禁** | `--cov-fail-under=75` | 75% | ✅ 已启用 |
| **失败测试** | 0 | 0 | ✅ 达标 |

#### 模块覆盖率明细

| 模块 | 覆盖率 | 等级 | 备注 |
|------|--------|------|------|
| `verification_gate.py` | **65%** | ✅✅ | 优秀 |
| `test_quality_guard.py` | **92%** | ✅✅ | 优秀 |
| `scratchpad.py` | **91%** | ✅✅ | 优秀 |
| `null_providers.py` | **95%** | ✅✅ | 优秀 |
| `dispatcher.py` | 63% | ✅ | 良好 |
| `coordinator.py` | 67% | ✅ | 良好 |
| `permission_guard.py` | 73% | ✅ | 良好 |
| `llm_backend.py` | 72% | ✅ | 良好 |
| `dashboard.py` | **0%** | ❌ | 需 E2E 测试 |
| `mcp_server.py` | **0%** | ❌ | 需集成测试 |
| `api_server.py` | ~10% | ❌ | 需 FastAPI TestClient |
| `rule_collector.py` | 36% | ⚠️ | 文件较大 |

### 8.4 测试命令

```bash
# 运行所有测试（带覆盖率）
pytest --cov=scripts --cov-report=term-missing --cov-report=html:htmlcov

# 仅运行单元测试
pytest -m unit -v

# 仅运行集成测试
pytest -m integration -v

# 排除慢速测试
pytest -m "not slow" -v

# 运行特定测试文件
pytest tests/test_collaboration_core_test.py -v

# 生成覆盖率 HTML 报告
pytest --cov=scripts --cov-report=html:htmlcov
open htmlcov/index.html

# CI 模式（严格）
pytest -x -q --cov=scripts --cov-report=term --cov-fail-under=75
```

### 8.5 Mock 与 Fixture

#### Mock 后端

```python
from scripts.collaboration.llm_backend import MockLLMBackend

# 使用 Mock 后端（无需 API Key）
dispatcher = MultiAgentDispatcher(backend_type="mock")
result = dispatcher.dispatch(task="test task")
```

#### 主要 Fixture

| Fixture 名称 | 提供内容 | 所在文件 |
|--------------|----------|----------|
| `sample_task` | TaskDefinition 实例 | conftest.py |
| `sample_entry` | ScratchpadEntry 实例 | conftest.py |
| `mock_backend` | MockLLMBackend | conftest.py |
| `scratchpad` | Scratchpad 实例 | conftest.py |
| `worker` | Worker 实例 | conftest.py |
| `coordinator` | Coordinator 实例 | conftest.py |

---

## 9. 性能指标

### 9.1 SLA 定义 (Service Level Agreement)

| 指标类别 | 指标名称 | 目标值 | 测量方法 |
|----------|----------|--------|----------|
| **可用性** | 系统可用率 | ≥ 99.9% | Uptime 监控 |
| **延迟** | API P50 响应时间 | < 200ms | Prometheus histogram |
| **延迟** | API P99 响应时间 | < 1000ms | Prometheus histogram |
| **吞吐量** | 调度 QPS | ≥ 10 req/s | Counter metric |
| **错误率** | API 错误率 | < 0.1% | Error counter |
| **成功率** | 任务成功率 | ≥ 98% | Result tracking |

### 9.2 性能基准 (Baseline Metrics)

| 场景 | 并发数 | 平均延迟 | P99 延迟 | 吞吐量 | 内存占用 |
|------|--------|----------|----------|--------|----------|
| 单任务 Mock | 1 | ~50ms | ~100ms | 20 req/s | ~150MB |
| 单任务 OpenAI | 1 | ~3-8s | ~15s | 0.2 req/s | ~200MB |
| 3 角色并行 | 3 | ~5-12s | ~20s | 0.5 req/s | ~300MB |
| 7 角色共识 | 7 | ~15-30s | ~45s | 0.3 req/s | ~450MB |
| 批量调度 (10) | 10 | ~20-40s | ~60s | 0.5 req/s | ~500MB |

### 9.3 性能优化措施 (已实施)

| 优化项 | 技术 | 效果 | 状态 |
|--------|------|------|------|
| **LLM Cache (L1)** | 内存缓存 (dict) | 命中时 < 1ms | ✅ 已实施 |
| **LLM Cache (L2)** | 磁盘缓存 (JSON) | 跨会话复用 | ✅ 已实施 |
| **Context Compressor** | Token 截断/摘要 | 减少 30-50% token | ✅ 已实施 |
| **Batch Scheduler** | ThreadPoolExecutor | 并行执行提升 2-3x | ✅ 已实施 |
| **Connection Reuse** | Session 复用 | 减少连接开销 | ✅ 已实施 |

### 9.4 性能瓶颈与优化方向 (Phase 7)

| 瓶颈模块 | 当前问题 | 优化方案 | 预期提升 |
|----------|----------|----------|----------|
| `llm_backend.py` | 同步阻塞 I/O | asyncio + aiohttp | 延迟降低 50% |
| `llm_cache.py` | 单进程内存限制 | Redis 分布式缓存 | 吞吐量提升 3x |
| `coordinator.py` | 串行任务分解 | 异步流水线 | 延迟降低 30% |
| `batch_scheduler.py` | GIL 限制并发 | multiprocessing | CPU 密集任务 2x |

### 9.5 监控指标 (Key Metrics)

```python
# PerformanceMonitor 暴露的核心指标
METRICS = {
    # 业务指标
    "dispatch_count": "counter",           # 总调度次数
    "success_rate": "gauge",               # 成功率 (0.0-1.0)
    "avg_latency_ms": "histogram",         # 平均延迟分布
    "cache_hit_rate": "gauge",             # 缓存命中率

    # 资源指标
    "active_workers": "gauge",             # 活跃 Worker 数
    "queue_depth": "gauge",                # 任务队列深度
    "memory_usage_mb": "gauge",            # 内存使用 (MB)
    "cpu_usage_percent": "gauge",          # CPU 使用率 (%)

    # 质量指标
    "consensus_rounds": "counter",         # 共识轮次
    "conflict_count": "counter",           # 冲突次数
    "escalation_count": "counter",         # 升级次数
}
```

---

## 10. 安全要求

### 10.1 认证方式

#### AuthManager 认证系统

| 认证方式 | 适用场景 | 实现状态 | 安全等级 |
|----------|----------|----------|----------|
| **Demo Auth** | 开发/演示 | ✅ 已实施 | 低（仅本地） |
| **Bearer Token** | API 调用 | ✅ 已实施 | 中（生产建议） |
| **API Key** | 服务间调用 | ✅ 已实施 | 中 |
| **OAuth2/OIDC** | 企业 SSO | 🔄 Phase 9 | 高（待实施） |

#### User Roles (用户角色)

| 角色 | 权限范围 | 描述 |
|------|----------|------|
| `VIEWER` | 只读访问 | 查看状态、结果、日志 |
| `OPERATOR` | 操作权限 | 执行任务、查看详情 |
| `ADMIN` | 管理权限 | 用户管理、配置修改 |
| `SUPERADMIN` | 超级管理员 | 所有权限、系统配置 |

### 10.2 权限模型 (PermissionGuard - 4级执行权限)

```python
class PermissionLevel(Enum):
    DEFAULT = "default"    # 默认：写操作需确认
    PLAN = "plan"          # 计划：只读操作
    AUTO = "auto"          # 自动：AI 分类器自动判断
    BYPASS = "bypass"      # 绕过：完全跳过（最高信任）
```

**权限矩阵**:

| 操作 | PLAN | DEFAULT | AUTO | BYPASS |
|------|------|---------|------|--------|
| 查看状态 | ✅ | ✅ | ✅ | ✅ |
| 读取文件 | ✅ | ✅ | ✅ | ✅ |
| 创建文件 | ❌ | ⚠️ 需确认 | ✅ AI 判断 | ✅ |
| 修改文件 | ❌ | ⚠️ 需确认 | ✅ AI 判断 | ✅ |
| 删除文件 | ❌ | ⚠️ 需确认 | ✅ AI 判断 | ✅ |
| Shell 执行 | ❌ | ⚠️ 需确认 | ✅ AI 判断 | ✅ |
| 网络请求 | ❌ | ⚠️ 需确认 | ✅ AI 判断 | ✅ |
| Git 操作 | ❌ | ⚠️ 需确认 | ✅ AI 判断 | ✅ |

> **真相源**: `scripts/collaboration/permission_guard.py:31-35`

### 10.3 输入验证 (InputValidator - 53种检测模式)

| 类别 | 数量 | 检测内容 | 风险等级 |
|------|------|----------|----------|
| **Forbidden Patterns** | 15 | XSS(4) + SQL注入(3) + 命令注入(3) + HTML注入(3) + 数据URI(2) | 🔴 Critical |
| **SSRF Patterns** | 13 | localhost + 云元数据(169.254.169.254/metadata.google.internal/100.100.100.200) + IPv6 + Hex/Octal/Decimal IP + file/gopher/dict协议 | 🟠 High |
| **Suspicious Patterns** | 5 | 警告但不阻止的可疑模式 | 🟡 Medium |
| **Prompt Injection** | 20 | "Ignore previous"/"Disregard"/"New instruction" 等 AI 提示注入 | 🟡 Medium |
| **总计** | **53** | 完整安全防护 | - |

> **真相源**: `scripts/collaboration/input_validator.py:31` (FORBIDDEN_PATTERNS + SUSPICIOUS_PATTERNS)

### 10.4 数据加密

| 数据类型 | 加密方式 | 存储位置 | 密钥管理 |
|----------|----------|----------|----------|
| 用户密码 | SHA-256 Hash | 内存/文件 | Salt 随机生成 |
| API Keys | 环境变量 | OS Env | 外部密钥管理器 |
| 会话 Token | JWT (HS256) | Cookie/Header | Secret 环境变量 |
| 缓存数据 | 明文 (内存) | L1 Cache | N/A (易失性) |
| 持久化数据 | 明文 (JSON) | .devsquad_data/ | 文件系统权限 |
| 传输数据 | TLS 1.3 | Network | Let's Encrypt / 企业 CA |

### 10.5 安全最佳实践 (已实施)

- ✅ **零硬编码凭证**: 所有密码/API Key 通过环境变量注入
- ✅ **SHA-256 密码哈希**: 不可逆加密存储
- ✅ **53 种注入检测**: InputValidator 全面防护 (15 forbidden+13 SSRF+5 suspicious+20 prompt injection)
- ✅ **4 级权限控制**: 最小权限原则
- ✅ **Anti-Rationalization**: 防 AI 合理化攻击
- ✅ **ExecutionGuard**: 实时执行守卫
- ✅ **CORS 配置**: 可配置跨域策略
- ✅ **Rate Limiting**: 60 req/min/IP 限流
- ✅ **Health Check**: Docker HEALTHCHECK 集成
- ✅ **.gitignore 保护**: 敏感文件排除

### 10.6 安全审计建议 (Phase 9)

- [ ] **OWASP Top 10 扫描**: 使用 ZAP/Burp Suite
- [ ] **依赖漏洞扫描**: Snyk / Dependabot
- [ ] **Penetration Testing**: 第三方渗透测试
- [ ] **Code Security Audit**: 静态分析 (Bandit/Semgrep)
- [ ] **Compliance Check**: SOC2 / GDPR / HIPAA 就绪评估

---

## 11. 附录

### 11.1 项目文件结构

```
DevSquad/
├── .devsquad_data/              # 运行时数据（gitignored）
│   └── fingerprints/
├── .github/                     # GitHub 配置
│   └── dependabot.yml
├── config/                      # 配置文件
│   ├── samples/                 # 配置模板
│   │   ├── env.production
│   │   ├── nginx.conf
│   │   └── *.service
│   ├── alerts.yaml
│   ├── deployment.yaml
│   └── llm_optimization.yaml
├── docs/                        # 文档
│   ├── spec/                    # 技术规范（本文件）
│   ├── guide/                   # 使用指南
│   ├── i18n/                    # 国际化 (EN/CN/JP)
│   ├── roles/                   # 角色模板
│   ├── testing/                 # 测试策略
│   └── _archive/                # 历史归档
├── examples/                    # 示例代码
│   ├── quick_start.py
│   ├── quick_demo.py
│   └── full_project_workflow.py
├── helm/                        # Kubernetes Charts
│   └── devsquad/
├── scripts/                     # 核心代码
│   ├── cli.py                   # CLI 入口
│   ├── api_server.py            # REST API
│   ├── mcp_server.py            # MCP Server
│   ├── dashboard.py             # Web Dashboard
│   ├── auth.py                  # 认证管理
│   ├── collaboration/           # 协作引擎 (113+ files)
│   │   ├── coordinator.py
│   │   ├── dispatcher.py
│   │   ├── worker.py
│   │   ├── scratchpad.py
│   │   ├── models.py            # 数据模型 (1215行)
│   │   ├── consensus.py
│   │   ├── permission_guard.py
│   │   ├── input_validator.py
│   │   ├── llm_backend.py
│   │   ├── llm_cache.py
│   │   ├── anchor_checker.py   # V3.6.0
│   │   ├── retrospective.py     # V3.6.0
│   │   └── ... (107 more files)
│   ├── api/                     # API 路由
│   │   └── routes/
│   └── cli/                     # CLI 工具
├── skills/                      # 原子技能 (6个)
│   ├── dispatch/
│   ├── intent/
│   ├── retrospective/
│   ├── review/
│   ├── security/
│   └── test/
├── templates/                   # 模板
│   └── concerns/
├── tests/                       # 测试套件 (65 files)
│   ├── contract/
│   └── test_*.py
├── .devsquad.yaml               # 项目配置
├── .env.example                 # 环境变量模板
├── .dockerignore
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml
├── CHANGELOG.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── Dockerfile                   # 多阶段构建
├── docker-compose.yml
├── EXAMPLES.md
├── GUIDE.md
├── INSTALL.md
├── LICENSE                      # MIT
├── README*.md                   # EN/CN/JP
├── SKILL.md / SKILL_CN.md
├── pyproject.toml               # 项目元数据
├── requirements.txt
├── requirements-dev.txt
└── skill-manifest.yaml          # Skill 元数据
```

### 11.2 版本历史

| 版本 | 日期 | 重要变更 | 成熟度 |
|------|------|----------|--------|
| **V4.0.11** | 2026-07-14 | 全面文档审核(57 issues 修复)、health_check 版本硬编码修复、CI 覆盖率门禁启用、模块数统一 185+、活文档机制建立 | **8.9/10** |
| **V4.0.10** | 2026-07-13 | redis_url 凭据泄露防护、health_check bug 修复、依赖同步、CI 3.12 矩阵、pre-commit ruff 版本对齐 | **8.8/10** |
| **V4.0.0** | 2026-07-07 | MAJOR 版本升级：Loop Engineering + UI/UX 巡检 + 对抗验证 + DAG 可视化 + 自主迭代 + 插件热加载 (6 大特性) | **8.6/10** |
| **V3.10.0** | 2026-07-01 | PonytailRuleInjector (7-rung laziness ladder) + ContentRouter+SmartCrusher (6-type 结构感知压缩) + Coordinator SMART-first 集成 | **8.3/10** |
| **V3.9.2** | 2026-06-30 | Auto LLM fallback + Dashboard 拆分 (1087→8 模块) + SQLite dispatch audit + P0 安全修复 (PBKDF2) | **7.5/10** |
| **V3.9.0** | 2026-06-22 | CodeKnowledgeGraph (SQLite) + YagniChecker + PromptDials + RedesignAuditor 三阶段简化审计 + DispatchRBAC + DispatchAuditLogger | **7.2/10** |
| **V3.8.0** | 2026-06-21 | Two-Stage Review Gate + Severity Router + Judge Agent + Micro-Task Planner + Content Cache | **7.0/10** |
| **V3.7.2** | 2026-06-16 | EventBus + Dispatcher 拆分 (1660→706 行, -57%) + f-string logger 清理 + broad except 收窄 | **6.8/10** |
| **V3.7.0** | 2026-06-15 | RoleSkillLoader + PM 方法论 Skills (5 SKILL.md) + SKILL.md 安全扫描 | **6.5/10** |
| **V3.6.7** | 2026-05-20 | Enterprise功能+E2E测试+代码质量优化 | **65%** |
| **V3.6.1** | 2026-05-20 | 代码质量工程完成，文档统一，发布就绪 | **94% Production** |
| **V3.6.0** | 2026-05-18 | Anchor Checker, Retrospective Engine, Feedback Loop | 90% Stable |
| **V3.5.0** | 2026-04-27 | Skillify, Warmup Manager, Memory Bridge | 85% Beta |
| **V3.2.0** | 2026-04-15 | Consensus Enhancement, Adaptive Role Selector | 78% Alpha |
| **V3.0.0** | 2026-04-01 | 重构为三层架构，FastAPI 集成 | 70% Alpha |
| **V2.x** | 2026-03 | 初始版本，基础协作功能 | 50% Experimental |

### 11.3 依赖关系图

```
DevSquad Core Dependencies
│
├── Required (必须)
│   ├── pyyaml>=6.0           # 配置解析
│   ├── fastapi>=0.100.0      # Web 框架
│   ├── uvicorn>=0.23.0       # ASGI 服务器
│   └── pydantic>=2.0         # 数据验证
│
├── Optional - LLM Backend
│   ├── openai>=1.0           # GPT-4/GPT-3.5
│   ├── anthropic>=0.18       # Claude
│   └── moka-ai>=1.0          # Moka AI (V4.0.7+)
│
├── Optional - Integrations
│   ├── carrymem>=0.2.8        # CarryMem 记忆系统
│   ├── mcp>=0.9               # MCP 协议支持
│   └── psutil>=5.9            # 系统监控
│
├── Optional - Visualization
│   ├── streamlit>=1.28.0      # Dashboard UI
│   └── jupyter>=1.0           # Notebook 支持
│
└── Development (开发依赖)
    ├── pytest>=7.0            # 测试框架
    ├── pytest-asyncio>=0.21   # 异步测试
    ├── pytest-cov>=4.1        # 覆盖率
    ├── ruff>=0.4.0            # Linting
    ├── mypy>=1.0              # 类型检查
    ├── black>=23.0            # 代码格式化
    └── flake8>=6.0            # 额外 Linting
```

### 11.4 术语表 (Glossary)

| 术语 | 英文 | 定义 |
|------|------|------|
| **调度器** | Dispatcher | 多智能体任务的统一入口和协调器 |
| **协调器** | Coordinator | 负责任务分解、Worker 分配、结果汇总 |
| **工作者** | Worker | 执行具体任务的工作单元，绑定一个角色 |
| **共享记忆板** | Scratchpad | Worker 之间交换信息的共享数据结构 |
| **共识引擎** | ConsensusEngine | 实现多 Worker 投票决策的组件 |
| **锚定检查** | Anchor Checking | 验证执行过程是否偏离原始目标的机制 |
| **回顾分析** | Retrospective | 任务完成后总结经验教训的过程 |
| **门禁** | Gate | 质量控制点，必须满足才能进入下一阶段 |
| **技能** | Skill | 原子化的功能单元，~50行代码 |
| **角色** | Role | 专业领域的 AI 助手身份（如架构师、测试专家） |
| **控制论** | Cybernetics | 反馈控制系统理论，用于自我调节和优化 |
| **反合理化** | Anti-Rationalization | 防止 AI 为错误决策寻找借口的心理机制 |
| **意图映射** | Intent Workflow Mapping | 将自然语言任务自动匹配到工作流的机制 |
| **生命周期** | Lifecycle | 从需求到发布的完整软件交付流程 |
| **MCP** | Model Context Protocol | AI Agent 之间的标准化通信协议 |

### 11.5 参考链接

| 资源 | URL |
|------|-----|
| **GitHub 仓库** | https://github.com/lulin70/DevSquad |
| **PyPI 页面** | https://pypi.org/project/devsquad/ |
| **问题追踪** | https://github.com/lulin70/DevSquad/issues |
| **成熟度报告** | [MATURITY_ASSESSMENT.md](../MATURITY_ASSESSMENT.md) |
| **快速开始** | [INSTALL.md](../INSTALL.md) |
| **使用指南** | [GUIDE.md](../GUIDE.md) |
| **示例代码** | [EXAMPLES.md](../EXAMPLES.md) |
| **贡献指南** | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| **更新日志** | [CHANGELOG.md](../CHANGELOG.md) |
| **英文 README** | [README.md](../README.md) |
| **中文 README** | [README-CN.md](../README-CN.md) |
| **日文 README** | [README-JP.md](../README-JP.md) |

### 11.6 许可证信息

```
MIT License

Copyright (c) 2024-2026 DevSquad Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

**文档结束**

> **维护者**: DevSquad Team
> **审核状态**: ✅ 已批准 (V4.0.11 活文档 — 7 角色共识)
> **下次更新**: 每次版本发布时同步更新所有数据点
> **反馈渠道**: https://github.com/lulin70/DevSquad/issues
