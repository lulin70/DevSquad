---
name: multi-agent-team
slug: multi-agent-team
description: 基于任务类型动态调度到合适的智能体角色（架构师、产品经理、测试专家、独立开发者、UI 设计师）。支持多智能体协作、共识机制、完整项目生命周期管理、规范驱动开发、代码走读审查和项目理解能力。支持中英文双语。v2.3 新增多角色代码走读与审查功能。
---

# Multi-Agent Team Dispatcher (AI-Enhanced)

基于任务类型和上下文，自动调度到最合适的智能体角色（架构师、产品经理、测试专家、Solo Coder、UI 设计师）。

**v2.3 新增**:
- 🚀 代码走读与审查：多角色协作分析，生成统一代码地图和审查报告
- 🗺️ 代码地图 Workspace 支持：支持一个 workspace 包含多个项目
- 📊 文档对齐引擎：多角色分析结果对齐，生成共识代码地图
- 📋 任务可视化页面：实时展现各角色任务状态、进度、依赖关系、交接过程
- 🎨 3D 代码地图可视化：基于 Three.js 的交互式代码结构可视化，支持流动动画和主题切换
- ✅ 文档与代码一致性检查：审查报告中新增文档与代码差异检查清单

## 多语言支持 (Multi-Language Support)

### 语言识别规则
**自动识别用户语言**:
- 用户使用中文 → 所有响应使用中文
- 用户使用英文 → 所有响应使用英文
- 用户混合使用 → 以首次使用的语言为准
- 用户明确要求切换 → 立即切换到目标语言

### 响应语言规则
**所有输出必须使用用户相同的语言**:
- 角色定义和 Prompt
- 状态更新和进度提示
- 审查报告和问题清单
- 错误信息和成功提示
- 文档和注释

**示例**:
```
用户（中文）: "设计系统架构"
AI（中文）: "📋 已接收任务，开始分析..."

用户（English）: "Design system architecture"
AI (English): "📋 Task received, starting analysis..."
```

### 角色名称映射
**中文 → 英文**:
- 架构师 → Architect
- 产品经理 → Product Manager
- 测试专家 → Test Expert
- 独立开发者 → Solo Coder
- UI 设计师 → UI Designer

## 核心能力

### AI 增强能力 (v2.1 新增)

1. **AI 语义理解驱动的角色匹配**: 使用大模型理解任务的深层语义，而非简单关键词匹配
2. **可解释的智能决策**: 提供匹配原因和置信度评分，决策过程透明可解释
3. **上下文感知的智能推理**: 基于历史经验和领域知识进行智能推理
4. **自然语言交互界面**: 支持自然语言对话，理解用户意图

### 基础能力

1. **智能角色调度**: 根据任务描述自动识别需要的角色
2. **多角色协同**: 组织多个角色共同完成复杂任务
3. **上下文感知**: 根据项目阶段和历史上下文选择角色
4. **共识机制**: 组织多角色评审和决策
5. **自动继续**: 思考次数超限后自动保存进度并继续执行
6. **任务管理**: 完整的任务生命周期管理和进度追踪
7. **代码地图生成**: 自动生成项目代码结构映射
8. **项目理解**: 快速读取项目文档和代码，生成项目理解文档
9. **规范驱动开发**: 基于项目规范和文档进行开发
10. **七阶段标准工作流程**: 需求分析→架构设计→测试设计→任务分解→开发实现→测试验证→发布评审
11. **UI 设计**: 创建独特、生产级的 UI 界面，避免通用的 AI "slop" 美学
12. **自我进化**: 从任务执行中学习、记录错误和改进，持续优化自身性能

## 快速开始

### 基础使用
```bash
# 自动调度（推荐）
python3 scripts/trae_agent_dispatch.py \
    --task "设计系统架构"

# 指定角色
python3 scripts/trae_agent_dispatch.py \
    --task "实现功能" \
    --agent solo_coder

# 多角色共识
python3 scripts/trae_agent_dispatch.py \
    --task "启动新项目" \
    --consensus true
```

### 完整项目流程
```bash
# 启动完整项目（自动执行 7 个阶段）
python3 scripts/trae_agent_dispatch.py \
    --task "启动项目：安全浏览器广告拦截功能" \
    --project-full-lifecycle
```

### AI 增强模式 (v2.1 新增)
```bash
# 使用 AI 语义匹配（默认）
python3 scripts/trae_agent_dispatch.py \
    --task "设计微服务架构，支持高并发和弹性扩展" \
    --agent auto  # AI 会自动匹配最合适的角色

# 查看 AI 匹配结果和解释
python3 scripts/trae_agent_dispatch.py \
    --task "实现用户认证和权限管理" \
    --agent auto \
    --explain  # 显示 AI 匹配原因和置信度

# 使用传统关键词匹配（向后兼容）
python3 scripts/trae_agent_dispatch.py \
    --task "编写单元测试" \
    --agent test_expert \
    --match-strategy keyword
```

## AI 集成说明 (v2.1)

### AI 能力

#### 1. 语义理解
- **深层语义分析**: 理解任务的真实意图，而非表面关键词
- **上下文感知**: 基于历史经验和领域知识理解任务
- **多义词消歧**: 准确理解多义词在特定上下文中的含义

**示例**:
```
任务："设计一个高可用的系统"
AI 理解：
- "高可用" → 需要冗余设计、故障转移、负载均衡
- "系统" → 可能是分布式系统、微服务架构
推荐角色：架构师 (置信度：92%)
```

#### 2. 智能匹配
- **多维度评分**: 能力匹配 (50%) + 技能匹配 (30%) + 语义相关 (20%)
- **可解释结果**: 提供详细的匹配原因和推理过程
- **置信度评估**: 0-1 的置信度评分，辅助决策

**匹配策略**:
- `ai_enhanced`: AI 增强混合匹配（推荐，默认）
- `semantic`: 纯 AI 语义匹配
- `keyword`: 传统关键词匹配
- `hybrid`: 传统混合匹配

#### 3. 代码审查
- **质量评估**: 代码结构、可读性、可维护性
- **性能分析**: 性能瓶颈、优化建议
- **安全检查**: 常见安全漏洞检测
- **最佳实践**: 行业标准和最佳实践建议

#### 4. 知识问答
- **技术咨询**: 解答技术问题
- **架构建议**: 提供架构设计建议
- **工具推荐**: 推荐合适的工具和库

### AI 配置

在 `skill-manifest.yaml` 中配置 AI 参数：

```yaml
ai_integration:
  enabled: true
  provider: trae_ai_assistant
  features:
    - semantic_matching
    - intelligent_reasoning
    - context_understanding
  config:
    max_tokens: 4096
    temperature: 0.7
    top_p: 0.9
    use_cache: true
    fallback_to_keyword: true
```

### 性能优化

- **缓存机制**: 相同请求直接返回缓存结果
- **降级策略**: AI 不可用时自动降级到关键词匹配
- **批量处理**: 支持批量请求，减少 API 调用次数

## 角色介绍

### 1. 架构师 (Architect)
**职责**: 设计系统性、前瞻性、可落地、可验证的架构

**触发关键词**: 架构、设计、选型、审查、性能、瓶颈、模块、接口、部署

**典型任务**:
- 项目启动阶段的架构设计
- 关键代码的架构审查和代码评审
- 技术难题攻关和性能优化

### 2. 产品经理 (Product Manager)
**职责**: 定义用户价值清晰、需求明确、可落地、可验收的产品

**触发关键词**: 需求、PRD、用户故事、竞品、市场、调研、验收、UAT、体验

**典型任务**:
- 产品需求定义和 PRD 编写
- 用户故事地图和验收标准定义
- 竞品分析

### 3. 测试专家 (Test Expert)
**职责**: 确保全面、深入、自动化、可量化的质量保障

**触发关键词**: 测试、质量、验收、自动化、性能测试、缺陷、评审、门禁

**典型任务**:
- 测试策略制定和测试用例设计
- 自动化测试方案
- 质量评估和测试报告

### 4. 独立开发者 (Solo Coder)
**职责**: 编写完整、高质量、可维护、可测试的代码

**触发关键词**: 实现、开发、代码、修复、优化、重构、单元测试、文档

**典型任务**:
- 功能实现和单元测试编写
- 代码重构和优化
- 开发文档编写

### 5. UI 设计师 (UI Designer)
**职责**: 创建独特、生产级的 UI 界面，具有高设计质量，避免通用的 AI "slop" 美学

**触发关键词**: UI设计、界面设计、前端设计、视觉设计、UI/UX、UI原型、界面美化、UI优化、UI重构

**典型任务**:
- Web 组件、页面、应用的 UI 设计
- UI 原型和视觉稿创建
- UI 美化和视觉优化
- 设计系统和设计规范制定
- UI 组件库设计

## 七阶段标准工作流程

```
阶段 1: 需求分析（产品经理）
    ↓ 评审通过
阶段 2: 架构设计（架构师）
    ↓ 评审通过
阶段 3: UI 设计（UI 设计师）
    ↓ 评审通过
阶段 4: 测试设计（测试专家）
    ↓ 评审通过
阶段 5: 任务分解（独立开发者）
    ↓
阶段 6: 开发实现（独立开发者）
    ↓
阶段 7: 测试验证（测试专家）
    ↓
阶段 8: 发布评审（多角色）
```

### 自动触发规则（v2.4.2 新增）

**系统会自动识别以下任务并启动项目全生命周期模式：**

| 触发关键词 | 示例任务 |
|-----------|---------|
| 项目生命周期 | "使用项目生命周期模式开发用户管理模块" |
| 全生命周期 | "全生命周期开发支付功能" |
| 完整流程 | "完整流程实现订单系统" |
| 启动项目 | "启动项目：电商平台" |
| 新项目 | "新项目开发博客系统" |
| 从头开始 | "从头开始开发一个API服务" |
| 完整功能 | "完整功能开发用户认证系统" |
| 端到端 | "端到端实现数据同步功能" |
| 全流程 | "全流程开发报表模块" |

**自动触发后系统将：**
1. 识别意图类型为 `PROJECT_LIFECYCLE`
2. 自动启动 8 阶段标准工作流程
3. 按顺序调度各角色执行任务
4. 生成完整的交付物

**手动触发方式：**
```bash
# 方式1：使用 /mas 命令
/mas lifecycle 开发用户管理模块

# 方式2：使用命令行参数
python3 scripts/trae_agent_dispatch.py \
    --task "开发用户管理模块" \
    --project-full-lifecycle
```

**绝对禁止**：
❌ 未经过设计阶段直接开始编码
❌ 文档未编写或未完成就开始开发
❌ 未经过设计评审直接实施
❌ 使用通用的 AI 美学（AI slop）

## 高级功能

### 代码走读与审查 (v2.3)

```bash
# 执行真正的多角色协作代码走读（使用 Trae Agent 调度）
python3 scripts/multi_role_collaborative_analyzer.py /path/to/project --workspace /workspace

# 简化的多角色代码走读
python3 scripts/multi_role_code_walkthrough.py /path/to/project --workspace /workspace
```

**真正的多角色协作分析流程**:

1. **阶段一：项目扫描**
   - 递归扫描项目目录
   - 识别源代码文件、配置文件、文档文件
   - 统计项目基本信息
   - 检测技术栈和框架
   - 识别项目模块

2. **阶段二：调用 Trae Agent 调度**
   - 使用 `trae_agent_dispatch_v2.py` 分发任务
   - 每个角色使用专属 prompt 模板
   - 角色包括：架构师、产品经理、独立开发者、UI 设计师、测试专家
   - 各角色独立执行真实分析

3. **阶段三：文档对齐**
   - 收集各角色分析结果
   - 识别共识点与差异点
   - 合并统一的代码地图
   - 生成代码走读审查报告

**输出文档**:

| 文档 | 内容 |
|------|------|
| `<project>-ALIGNED-CODE-MAP.md` | 统一代码地图：项目概览、架构分层、多角色分析结果、对齐结果 |
| `<project>-CODE-REVIEW-REPORT.md` | 代码走读审查报告：审查概述、架构评审、代码质量评估、文档一致性检查、改进建议 |

**代码地图内容** (核心结构，不含审查风险):
- 项目概览
- 架构视图
- 代码结构
- 多角色视角摘要
- 分析共识

**审查报告内容** (含风险和建议):
- 审查概览
- 架构评审
- 代码质量评估
- 多角色共识
- **文档与代码一致性检查清单** ← v2.3 新增
- 改进建议
- 附录

### 3D 代码地图可视化 (v2.3)

```bash
# 全局 skill 安装后，在 workspace 中使用
~/.trae/skills/docs/code-map-visualizer.html
```

**功能特性**:
- **Three.js 3D 引擎**：完整 3D 场景渲染，支持拖拽旋转、滚轮缩放
- **前后端分层展示**：前端层（蓝色）、后端层（红色）、共享层（灰色）
- **真实调用链路**：节点间的连线连接到实际代码节点
- **动态流动效果**：边使用虚线动画 + 流动粒子
- **深色/浅色主题**：一键切换

**JSON v2.0 数据结构**:

生成命令：
```bash
python3 scripts/code_map_generator_v2.py /path/to/project --visual
```

输出文件：`{project-name}-VISUAL-MAP.json`

```json
{
  "version": "2.0",
  "project": {
    "name": "项目名",
    "frontend": { "layers": ["frontend-ui", "frontend-service", "frontend-store"] },
    "backend": { "layers": ["api", "service", "domain", "data", "middleware"] }
  },
  "layers": [
    { "id": "frontend-ui", "name": "前端UI层", "side": "frontend" },
    { "id": "api", "name": "API层", "side": "backend" },
    { "id": "service", "name": "业务逻辑层", "side": "backend" }
  ],
  "nodes": [
    {
      "id": "file:path/to/file.py",
      "type": "file",
      "name": "文件名",
      "layerId": "service",
      "side": "backend",
      "calls": ["file:other.py"],
      "calledBy": []
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "file:a.py",
      "target": "file:b.py",
      "type": "calls",
      "protocol": "local"
    }
  ]
}
```

**节点类型**:
- `module`: 模块节点
- `file`: 文件节点
- `class`: 类节点
- `function`: 函数/方法节点

**边类型**:
- `calls`: 方法调用
- `imports`: 导入关系
- `http`: HTTP API 调用（前后端通信）
- `layer-calls`: 层级间典型调用

**交互功能**:
- 点击展开/折叠模块、类、函数
- 双击函数高亮调用链路
- 调用链路面板展示关键流程
- 点击节点显示详情（层级、端、调用关系）

### 任务可视化页面 (v2.3)

```bash
# 全局 skill 安装后，在 workspace 中使用
~/.trae/skills/docs/task-visualizer.html
```

**功能特性**:
- **概览统计面板**：总任务数、待开始、进行中、已完成、被阻塞
- **角色任务卡片**：任务列表、状态、进度
- **任务依赖关系**：显示任务间的依赖和阻塞关系
- **任务交接记录时间线**：记录角色间的任务交接过程
- **Canvas 绘制协同关系图**：展示角色间的协作网络
- **定时刷新机制**：自动从 JSON 文件加载最新任务数据（默认30秒）

**交互功能**:
- 点击任务卡片查看详情
- 查看任务依赖和交接记录
- 实时更新任务状态

**Workspace 安装说明**:
安装 skill 后，可视化文件会自动符号链接到 `~/.trae/skills/docs/` 目录，在任意 workspace 中都可直接打开使用。

### 代码地图生成

```bash
python3 scripts/code_map_generator_v2.py /path/to/project --workspace /workspace

# 输出: <project>-CODE_MAP.md
```

### 项目理解

```bash
python3 scripts/project_understanding.py /path/to/project
```

### 规范驱动开发
```bash
python3 scripts/spec_tools.py init
python3 scripts/spec_tools.py analyze
python3 scripts/spec_tools.py update --spec-file SPEC.md
```

## 文档结构

```
docs/
├── project-understanding/  # 项目理解文档
├── spec/                   # 规范驱动开发文档
├── architect/              # 架构师文档
├── product-manager/        # 产品经理文档
├── tester/                 # 测试专家文档
├── solo-coder/              # 独立开发者文档
├── ui-designer/            # UI 设计师文档
└── devops/                 # DevOps 工程师文档
```

## 故障排查

### 角色识别错误
```bash
# 明确指定角色
python3 scripts/trae_agent_dispatch.py \
    --task "..." \
    --agent architect
```

### 共识未触发
```bash
# 显式要求共识
python3 scripts/trae_agent_dispatch.py \
    --task "..." \
    --consensus true
```

## 扩展开发

### 添加新角色
1. 在 `roles.json` 中添加角色配置
2. 更新关键词列表
3. 调整调度规则

### 自定义调度规则
修改 `AgentDispatcher.analyze_task()` 方法。

## 总结

Trae Multi-Agent Dispatcher 提供了：
- ✅ 智能角色识别
- ✅ 多角色协同
- ✅ 上下文感知
- ✅ 完整项目流程
- ✅ 紧急任务处理
- ✅ UI 设计（避免 AI slop）
- ✅ 自我进化能力

通过智能调度，减少用户干预，提升协作效率！
