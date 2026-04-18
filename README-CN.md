# DevSquad — 多智能体软件开发团队

<p align="center">
  <strong>按需组建 AI 驱动的专业开发团队。</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-41%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.3-2026--04--17-orange" />
</p>

---

## DevSquad 是什么？

DevSquad 将**单个 AI 编程助手转化为多角色专业开发团队**。不再是单个 AI 处理你的全部任务，而是自动调度到最合适的专家角色组合——架构师、产品经理、编码员、测试工程师、安全审查员等——然后通过共享工作区编排它们的并行协作，通过共识投票解决冲突，最终交付统一的结构化报告。

**把它想象成按需组建的虚拟开发团队，由像真实工程师一样协作的 AI 智能体驱动。**

```
你: "设计一个微服务电商后端"
         │
         ▼
┌─────────────────┐
│  意图分析 ──→ 自动匹配: 架构师 + 运维 + 安全
└────────┬────────┘
         ▼
┌──────────┬──────────┬──────────┐
│  架构师   │   运维    │  安全专家 │
│ (系统设计) │(基础设施) │(威胁建模) │
└────┬──────┴────┬─────┴────┬────┘
     └────────────┼───────────┘
                  ▼
      ┌──────────────────┐
      │    共享工作板      │ ← 实时同步的黑板
      │  (Scratchpad)     │
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │   共识引擎        │ ← 加权投票 + 否决权
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │  结构化报告       │ ← 发现 + 行动项 (高/中/低)
      └──────────────────┘
```

## 快速开始

### 前置要求

- **Python 3.9+**（纯 Python，无编译依赖）
- **操作系统**: macOS / Linux / **Windows 10+**
- 无需外部依赖（所有集成均使用优雅降级）

详细安装说明（含 Windows）请参见 [**INSTALL.md**](INSTALL.md)

### 三种使用方式

**方式一：CLI 命令行（推荐）**

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

python3 scripts/cli.py dispatch -t "设计用户认证系统"
python3 scripts/cli.py status
python3 scripts/cli.py roles
```

**方式二：Python API**

```python
import sys
sys.path.insert(0, '/path/to/DevSquad')
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("设计 RESTful 用户管理接口")
print(result.to_markdown())
disp.shutdown()
```

**方式三：快速调度（3 种输出格式）**

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()

# 结构化报告（默认表格格式）
result = disp.quick_dispatch(task, output_format="structured")

# 紧凑模式（每角色一行）
result = disp.quick_dispatch(task, output_format="compact")

# 详细模式（完整发现 + 行动项）
result = disp.quick_dispatch(task, output_format="detailed",
                              include_action_items=True)

disp.shutdown()
```

## 10 个内置角色

| 角色 | 适用场景 |
|------|---------|
| `architect` | 系统设计、技术选型、API 设计 |
| `pm` | 需求分析、用户故事、验收标准 |
| `coder` | 功能实现、代码生成、重构 |
| `tester` | 测试策略、边界情况、覆盖率 |
| `ui` | UX 流程、交互设计、无障碍性 |
| `devops` | CI/CD 流水线、部署、监控 |
| `security` | 威胁建模、漏洞审计 |
| `data` | 数据建模、分析、迁移 |
| `reviewer` | 代码审查、最佳实践 |
| `optimizer` | 性能优化、缓存策略 |

**自动匹配**: 未指定角色时，调度器根据任务意图自动匹配。

## 16 个核心模块

| 模块 | 用途 |
|------|------|
| **MultiAgentDispatcher** | 统一入口——一次调用完成所有操作 |
| **Coordinator** | 全局编排：分解 → 分配 → 收集 → 决策 |
| **Scratchpad** | 共享黑板，Worker 间实时通信 |
| **Worker** | 角色执行器——每个角色独立实例 |
| **ConsensusEngine** | 加权投票 + 否决权 + 人工升级 |
| **BatchScheduler** | 并行/串行混合调度，自动安全检测 |
| **ContextCompressor** | 4 级压缩防止上下文溢出 |
| **PermissionGuard** | 4 级安全门禁（PLAN → DEFAULT → AUTO → BYPASS） |
| **Skillifier** | 从成功模式中学习，自动生成新技能 |
| **WarmupManager** | 3 层启动预加载（冷启动 < 300ms） |
| **MemoryBridge** | 跨会话记忆（7 种类型、TF-IDF、遗忘曲线） |
| **MCEAdapter** | 记忆分类引擎集成（v0.4，支持多租户） |
| **WorkBuddyClawSource** | 外部知识桥接（倒排索引搜索、AI 新闻流） |
| **PromptAssembler** | 动态提示词构建（3 变体 × 5 风格） |
| **PromptVariantGenerator** | A/B 测试闭环提示词优化 |
| **TestQualityGuard** | 自动化测试质量审计 |

## 跨平台兼容性

DevSquad 原生支持多种 AI 编程环境：

| 平台 | 集成方式 | 状态 |
|------|---------|------|
| **Trae IDE** | `skill-manifest.yaml` 原生 Skill | ✅ 主要平台 |
| **Claude Code** | `CLAUDE.md` + `.claude/skills/` 自定义 Skill | ✅ 支持 |
| **OpenClaw** | MCP Server (`scripts/mcp_server.py`，6 个工具) | ✅ 支持 |
| **终端 / 任意 IDE** | CLI (`scripts/cli.py`) 或 Python 导入 | ✅ 通用 |

### MCP Server（适用于 OpenClaw / Cursor / 任何 MCP 客户端）

```bash
pip install mcp          # 可选
python3 scripts/mcp_server.py              # stdio 模式
python3 scripts/mcp_server.py --port 8080  # SSE 模式
```

暴露 6 个工具：`multiagent_dispatch`、`multiagent_quick`、`multiagent_roles`、
`multiagent_status`、`multiagent_analyze`、`multiagent_shutdown`。

## 外部集成

| 组件 | 状态 | 降级方案 |
|------|------|---------|
| **MCE v0.4**（记忆分类引擎） | 可选的多租户/权限支持 | 不可用时优雅降级 |
| **WorkBuddy Claw** | 外部知识库只读桥接 | 路径不存在时跳过 |

所有集成都可选——DevSquad 可完全独立运行。

## 运行测试

```bash
cd /path/to/DevSquad

# 核心协作测试
python3 -m pytest scripts/collaboration/ -v
# 预期: ~41 个测试用例，全部通过

# 快速状态检查
python3 scripts/cli.py status
# 预期: {"name": "DevSquad", "status": "ready", ...}

# 干跑验证
python3 scripts/cli.py dispatch -t "测试任务" --dry-run
```

## 使用示例

### 场景一：架构设计会话

```
用户: "设计一个微服务电商后端"
→ DevSquad 自动匹配: 架构师 + 运维 + 安全
→ 输出: 技术栈建议 + 服务边界划分 + 安全模型
```

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("设计一个微服务电商后端")
print(result.to_markdown())
# → 结构化报告，含发现、冲突和高/中/低优先级行动项
disp.shutdown()
```

### 场景二：安全聚焦代码审查

```python
# 指定特定角色进行聚焦审查
result = disp.quick_dispatch(
    "审查 auth.py 的安全漏洞",
    output_format="detailed",
    include_action_items=True,
)
# → 安全发现 + 测试缺口 + 改进建议
```

### 场景三：全栈分析

```python
# 自动匹配模式 —— 让 DevSquad 选择合适的团队
result = disp.dispatch("评估项目的生产就绪状态")
# → 多角色评估 + 共识决策结果
```

### 场景四：紧凑输出（终端/管道）

```bash
python3 scripts/cli.py quick -t "优化数据库查询性能" -f compact
# → 每角色一行摘要，机器友好格式
```

### 场景五：JSON 输出（集成对接）

```bash
python3 scripts/cli.py dispatch -t "分析 API 接口面" -f json
# → 可被下游工具、CI/CD 流水线或仪表盘解析
```

### 场景六：高级编程用法

```python
from scripts.collaboration import (
    Coordinator, Scratchpad, Worker, ConsensusEngine,
    MemoryBridge, MemoryType,
)

# 创建协作系统
scratchpad = Scratchpad()
coordinator = Coordinator(scratchpad=scratchpad)

# 规划多角色任务
plan = coordinator.plan_task(
    "设计用户认证系统",
    [{"role_id": "architect"}, {"role_id": "product-manager"}]
)
print(f"任务数: {plan.total_tasks}")

# 记忆桥接查询
bridge = MemoryBridge()
result = bridge.recall(MemoryQuery(query_text="微服务架构"))
print(f"召回记忆: {result.total_found} 条")
```

## 项目结构

```
DevSquad/
├── scripts/
│   ├── cli.py                    # 主 CLI 入口
│   ├── mcp_server.py             # MCP Server (OpenClaw/Cursor)
│   ├── trae_agent.py             # 传统包装器 (/dss 命令)
│   ├── trae_agent_dispatch_v2.py # 核心调度器（传统）
│   └── collaboration/            # ★ 16 个核心模块
│       ├── dispatcher.py         # MultiAgentDispatcher
│       ├── coordinator.py        # 全局编排器
│       ├── scratchpad.py         # 共享工作板
│       ├── worker.py             # 角色执行器
│       ├── consensus.py          # 加权投票 + 否决
│       ├── memory_bridge.py      # 跨会话记忆
│       ├── mce_adapter.py        # MCE v0.4 适配器
│       └── *_test.py             # 测试套件 (~41 用例)
├── SKILL.md                      # 英文 Skill 手册
├── SKILL-CN.md                   # 中文 Skill 手册
├── SKILL-JP.md                   # 日文 Skill 手册
├── CLAUDE.md                     # Claude Code 项目指令
├── INSTALL.md                    # 安装指南（Unix + Windows）
├── CHANGELOG.md                  # 完整版本历史
└── docs/                         # 架构规范、计划文档
```

## 核心理念

> **"一个 AI 是工具，十个 AI 协作者是团队。"**

软件开发本质上是多学科的。没有任何单一视角能媲美一支协调良好、各具专长的团队的质量。DevSquad 让这样的团队按需可用，在数秒内为任何软件任务组建。

## 版本历史

| 日期 | 版本 | 要点 |
|------|------|------|
| 2026-04-17 | **V3.3** | 品牌重塑 → DevSquad、WorkBuddy Claw 集成、跨平台（CLI/MCP/ClaudeCode）、MAS→DSS |
| 2026-04-17 | V3.2 | E2E Demo、MCE 适配器、调度器 UX 增强、交付工作流铁律 |
| 2026-04-16 | V3.1 | 提示词优化系统（A/B 变体测试） |
| 2026-04-16 | V3.0 | 完全重构 —— Coordinator/Worker/Scratchpad 架构 |
| 2026年3月 | V2.x | 双层上下文、Vibe Coding、MCE 集成、代码地图可视化 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

## 链接

| 链接 | URL |
|------|-----|
| **GitHub（本仓库）** | https://github.com/lulin70/DevSquad |
| **原始 / 上游仓库** | https://github.com/weiransoft/DevSquad |
| **安装指南** | [INSTALL.md](INSTALL.md) |
| **Skill 手册** | [SKILL.md](SKILL.md) / [SKILL-CN.md](SKILL-CN.md) / [SKILL-JP.md](SKILL-JP.md) |
| **英文 Readme** | [README.md](README.md) |
| **日文 Readme** | [README-JP.md](README-JP.md) |
