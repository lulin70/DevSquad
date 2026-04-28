# DevSquad 使用说明

> **版本**: V3.3.0 | **最后更新**: 2026-04-28

DevSquad 是一个多角色 AI 任务编排器，能将单个任务自动调度到合适的专家角色组合，通过并行协作和共识决策，输出结构化分析报告。

## 核心功能

### 7 个核心角色

| 角色 | CLI ID | 别名 | 职责 |
|------|--------|------|------|
| 架构师 | `architect` | `arch` | 系统架构设计、技术选型 |
| 产品经理 | `pm` | `product-manager` | 需求分析、用户价值定义 |
| 安全专家 | `security` | `sec` | 安全审计、威胁分析 |
| 测试专家 | `tester` | `test` | 测试策略、质量保障 |
| 开发者 | `coder` | `solo-coder`, `dev` | 功能实现、代码审查 |
| DevOps | `devops` | `infra` | 部署架构、CI/CD |
| UI 设计师 | `ui` | `ui-designer` | 界面设计、用户体验 |

### 核心特性

- **智能角色匹配**: 基于中英文关键词自动匹配最合适的角色组合
- **并行协作**: ThreadPoolExecutor 并行执行多个角色
- **共识决策**: 加权投票 + 否决权 + 升级机制
- **输入验证**: XSS/SQL 注入/提示注入检测（16 种模式）
- **真实 LLM 输出**: 支持 OpenAI / Anthropic / Mock 三种后端
- **流式输出**: 实时查看 AI 分析过程
- **检查点恢复**: CheckpointManager 保存状态，支持断点续传
- **多语言**: `--lang zh/en/ja` 切换输出语言

## 快速开始

### 1. Mock 模式（无需 API Key）

```bash
# 自动匹配角色
python3 scripts/cli.py dispatch -t "Design user authentication system"

# 指定角色
python3 scripts/cli.py dispatch -t "Implement login feature" -r coder

# 多角色协作
python3 scripts/cli.py dispatch -t "Design microservices architecture" -r architect devops security

# 共识模式
python3 scripts/cli.py dispatch -t "Review code security" --mode consensus
```

### 2. 真实 AI 输出（需要 API Key）

```bash
# 配置 OpenAI
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "Design auth system" --backend openai

# 配置 Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
python3 scripts/cli.py dispatch -t "Design auth system" --backend anthropic

# 流式输出
python3 scripts/cli.py dispatch -t "Analyze security risks" --backend openai --stream
```

### 3. pip 安装后使用

```bash
pip install -e .
devsquad dispatch -t "Design user authentication system"
devsquad status
devsquad roles
devsquad --version
```

## CLI 命令参考

```bash
python3 scripts/cli.py dispatch -t <task>       # 执行任务
python3 scripts/cli.py status                    # 查看状态
python3 scripts/cli.py roles                     # 列出角色
python3 scripts/cli.py --version                 # 显示版本
```

### dispatch 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-t, --task` | 任务描述 | 必填 |
| `-r, --roles` | 角色（空格分隔） | 自动匹配 |
| `--mode` | 执行模式: auto/parallel/sequential/consensus | auto |
| `--backend` | LLM 后端: mock/openai/anthropic | mock |
| `--model` | 模型名称 | gpt-4 / claude-sonnet-4-20250514 |
| `--base-url` | 自定义 API 端点 | - |
| `-f, --format` | 输出格式: markdown/json/compact/structured/detailed | markdown |
| `--stream` | 启用流式输出 | false |
| `--lang` | 输出语言: zh/en/ja | 自动检测 |
| `--strict` | 严格模式（阻止提示注入） | false |

## 使用场景

- **架构设计**: `dispatch -t "Design microservices" -r architect devops`
- **安全审计**: `dispatch -t "Security review" -r security`
- **代码审查**: `dispatch -t "Review code quality" -r coder tester --mode consensus`
- **需求分析**: `dispatch -t "Analyze user requirements" -r pm`
- **全流程协作**: `dispatch -t "Build e-commerce system" -r architect pm coder tester devops security`

## 配置

详见 [CONFIGURATION.md](CONFIGURATION.md)

- **环境变量**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEVSQUAD_LLM_BACKEND`
- **配置文件**: `~/.devsquad.yaml`
- **优先级**: 环境变量 > 配置文件 > 默认值

## 技术要求

- **Python 3.9+**（纯 Python，无编译依赖）
- **跨平台**: macOS / Linux / Windows 10+
- **IDE 集成**: Trae IDE / Claude Code / Cursor (MCP) / 终端

## 文档资源

- [README.md](../../README.md) - 项目概述和快速开始
- [INSTALL.md](../../INSTALL.md) - 安装和配置指南
- [SKILL.md](../../SKILL.md) - Skill 集成说明
- [CLAUDE.md](../../CLAUDE.md) - Claude Code 集成
- [CONFIGURATION.md](CONFIGURATION.md) - 配置指南

## GitHub 仓库

https://github.com/lulin70/DevSquad

## 许可证

MIT License - 详见 [LICENSE](../../LICENSE) 文件
