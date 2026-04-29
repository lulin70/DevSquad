# DevSquad — 多角色 AI 任务编排器

<p align="center">
  <strong>一个任务 → 多角色 AI 协作 → 一个结论</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-129%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.3.0-2026--04--27-orange" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
</p>

---

## DevSquad 是什么？

DevSquad 将**单个 AI 任务转化为多角色 AI 协作**。自动将你的任务分派到最合适的专家角色组合——架构师、产品经理、编码员、测试工程师、安全审查员、运维工程师——通过共享工作区编排并行协作，通过加权共识投票解决冲突，最终交付统一的结构化报告。

```
你: "设计一个微服务电商后端"
         │
         ▼
┌─────────────────┐
│  输入验证  ──→ 安全检查 (XSS, SQL注入, Prompt注入)
└────────┬────────┘
         ▼
┌─────────────────┐
│  角色匹配  ──→ 自动匹配: 架构师 + 运维 + 安全
└────────┬────────┘
         ▼
┌──────────┬──────────┬──────────┐
│  架构师   │  运维     │  安全     │   ← ThreadPoolExecutor 并行执行
│ (设计)    │ (基础设施)│ (威胁)    │
└────┬──────┴────┬─────┴────┬────┘
     └────────────┼───────────┘
                  ▼
      ┌──────────────────┐
      │    共享工作区      │ ← 实时同步的协作黑板
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │   共识引擎         │ ← 加权投票 + 否决权 + 升级
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │   结构化报告       │ ← 发现 + 行动项 (高/中/低)
      └──────────────────┘
```

## 快速开始

### 安装

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 方式 A: 直接运行（无需安装）
python3 scripts/cli.py dispatch -t "设计用户认证系统"

# 方式 B: pip 安装
pip install -e .
devsquad dispatch -t "设计用户认证系统"
```

### 3 种使用方式

**1. CLI（推荐）**

```bash
# Mock 模式（默认）— 无需 API Key
python3 scripts/cli.py dispatch -t "设计用户认证系统"

# 真实 AI 输出 — 先设置环境变量
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "设计认证系统" --backend openai

# 指定角色（短 ID: arch/pm/test/coder/ui/infra/sec）
python3 scripts/cli.py dispatch -t "设计认证系统" -r arch sec --backend openai

# 实时流式输出
python3 scripts/cli.py dispatch -t "设计认证系统" -r arch --backend openai --stream

# 其他命令
python3 scripts/cli.py status          # 系统状态
python3 scripts/cli.py roles           # 列出可用角色
python3 scripts/cli.py --version       # 显示版本 (3.3.0)
```

**2. Python API**

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Mock 模式（默认）
disp = MultiAgentDispatcher()
result = disp.dispatch("设计 REST API 用户管理系统")
print(result.to_markdown())
disp.shutdown()

# 使用 LLM 后端
from scripts.collaboration.llm_backend import create_backend
backend = create_backend("openai", api_key="sk-...", base_url="https://api.openai.com/v1")
disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("设计认证系统", roles=["architect", "security"])
print(result.summary)
disp.shutdown()
```

**3. MCP 服务器（用于 Cursor / 任何 MCP 客户端）**

```bash
pip install mcp
python3 scripts/mcp_server.py              # stdio 模式
python3 scripts/mcp_server.py --port 8080  # SSE 模式
```

## 7 个核心角色

| 角色 | CLI ID | 别名 | 权重 | 最适合 |
|------|--------|------|------|--------|
| 架构师 | `arch` | `architect` | 1.5 | 系统设计、技术选型、性能/安全架构 |
| 产品经理 | `pm` | `product-manager` | 1.2 | 需求分析、用户故事、验收标准 |
| 安全专家 | `sec` | `security` | 1.1 | 威胁建模、漏洞审计、合规检查 |
| 测试专家 | `test` | `tester`, `qa` | 1.0 | 测试策略、质量保证、边界用例 |
| 编码员 | `coder` | `solo-coder`, `dev` | 1.0 | 功能实现、代码审查、性能优化 |
| 运维工程师 | `infra` | `devops` | 1.0 | CI/CD、容器化、监控、基础设施 |
| UI 设计师 | `ui` | `ui-designer` | 0.9 | UX 流程、交互设计、无障碍 |

**自动匹配**：如果不指定角色，调度器会根据任务关键词自动匹配。

## 核心特性

### 安全
- **输入验证器**：XSS、SQL 注入、命令注入、HTML 注入检测
- **Prompt 注入防护**：16 种注入模式（忽略先前指令、越狱、DAN 模式、系统提示提取等）
- **API Key 安全**：仅使用环境变量，绝不通过命令行参数或日志泄露
- **权限守卫**：4 级安全门（PLAN → DEFAULT → AUTO → BYPASS）

### 性能
- **ThreadPoolExecutor**：多角色分派的真实并行执行
- **LLM 缓存**：基于 TTL 的 LRU 缓存 + 磁盘持久化（60-80% 成本降低）
- **LLM 重试**：指数退避 + 熔断器 + 多后端降级
- **流式输出**：通过 `--stream` 实时逐块输出 LLM 响应

### 可靠性
- **检查点管理器**：SHA256 完整性校验、交接文档、自动清理
- **工作流引擎**：任务→工作流自动拆分、步骤执行、断点恢复
- **任务完成检查器**：DispatchResult/ScheduleResult 完成度跟踪
- **共识引擎**：加权投票 + 否决权 + 人工升级

### 开发者体验
- **配置文件**：`~/.devsquad.yaml` + 环境变量覆盖
- **Docker 支持**：`docker build -t devsquad .`
- **GitHub Actions CI**：Python 3.9-3.12 矩阵测试
- **pip 可安装**：`pip install -e .` + 可选依赖

## 配置

创建 `~/.devsquad.yaml`：

```yaml
devsquad:
  backend: openai
  base_url: https://api.openai.com/v1
  model: gpt-4
  timeout: 120
  output_format: structured
  strict_validation: false
  checkpoint_enabled: true
  cache_enabled: true
  log_level: WARNING
```

或使用环境变量（优先级更高）：

```bash
export DEVSQUAD_BACKEND=openai
export DEVSQUAD_BASE_URL=https://api.openai.com/v1
export DEVSQUAD_MODEL=gpt-4
export OPENAI_API_KEY=sk-...
```

## 运行测试

```bash
# 核心测试（129 个）
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py -v

# 快速冒烟测试
python3 scripts/cli.py --version    # 3.3.0
python3 scripts/cli.py status       # 系统就绪
python3 scripts/cli.py roles        # 列出 7 个角色
```

## 文档

| 文档 | 说明 |
|------|------|
| [INSTALL.md](INSTALL.md) | 安装指南 |
| [EXAMPLES.md](EXAMPLES.md) | 真实使用示例 |
| [SKILL.md](SKILL.md) | 技能手册 |
| [README.md](README.md) | English README |
| [README-JP.md](README-JP.md) | 日本語説明 |

## 版本历史

| 日期 | 版本 | 亮点 |
|------|------|------|
| 2026-04-27 | **V3.3.0** | 真实 LLM 后端、ThreadPoolExecutor 并行、输入验证+Prompt注入防护、检查点管理、工作流引擎、流式输出、Docker、CI、配置文件、CarryMem集成、129 单元测试 |
| 2026-04-17 | V3.2 | E2E Demo、MCE 适配器 |
| 2026-04-16 | V3.0 | 完整重设计 — Coordinator/Worker/Scratchpad 架构 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
