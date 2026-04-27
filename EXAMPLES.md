# DevSquad 使用示例

> 最后验证: 2026-04-27, DevSquad V3.3.0, backend=openai, model=moka/claude-sonnet-4-6

## 快速开始

```bash
# Mock 模式（默认）— 无需 API Key
python3 scripts/cli.py dispatch -t "设计用户认证系统"

# 真实 AI 输出 — 先设置环境变量
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.moka-ai.com/v1"
export OPENAI_MODEL="moka/claude-sonnet-4-6"
python3 scripts/cli.py dispatch -t "设计用户认证系统" --backend openai

# 指定角色（短 ID: arch/pm/test/coder/ui/infra/sec）
python3 scripts/cli.py dispatch -t "设计用户认证系统" -r arch pm test --backend openai

# 流式输出（实时查看 LLM 响应）
python3 scripts/cli.py dispatch -t "设计用户认证系统" -r arch --backend openai --stream

# Dry-run（模拟不执行）
python3 scripts/cli.py dispatch -t "设计用户认证系统" --dry-run
```

## 真实输出示例

### 示例 1：架构设计（单角色）

```bash
python3 scripts/cli.py dispatch \
    -t "设计一个带 OAuth2 和 2FA 的用户认证系统" \
    -r arch --backend openai
```

**真实输出** (验证于 2026-04-24, 91s, architect 角色):

```
# OAuth2 + 2FA 用户认证系统架构设计

## 核心发现

1. **分层隔离是安全基础** - OAuth2 授权层与 2FA 验证层必须独立部署，
   避免单点攻击面，token 存储与验证逻辑物理隔离
2. **性能与安全的平衡点** - Redis 集群缓存 token（TTL 15min）+
   数据库持久化 refresh token（30天），配合 rate limiting 防暴力破解
```

### 示例 2：多角色协作

```bash
python3 scripts/cli.py dispatch \
    -t "为 SaaS 平台构建实时聊天功能" \
    -r arch pm test --backend openai
```

**真实输出** (验证于 2026-04-24, 144s, 3 个角色):

- **架构师**: WebSocket + Redis Pub/Sub 架构方案，支持百万级并发，
  延迟 <50ms，消息持久化与实时传输解耦
- **产品经理**: 实时聊天功能 PRD，核心业务价值（提升协作效率、增强平台粘性），
  目标用户（B端SaaS团队协作场景）
- **测试专家**: 测试方案，核心风险点（WebSocket 稳定性、消息延迟 <500ms、
  并发负载），数据一致性多层验证，安全合规早期介入

### 示例 3：安全审计

```bash
python3 scripts/cli.py dispatch \
    -t "对处理用户支付和个人数据的 REST API 进行安全审计" \
    -r sec --backend openai
```

**真实输出** (验证于 2026-04-24, 48s, security 角色):

```
I'll conduct a comprehensive security audit for your REST API handling
payments and personal data. Since I don't have access to your actual
codebase, I'll provide an executable audit framework with...
```

### 示例 4：流式输出（V3.3.0 新增）

```bash
python3 scripts/cli.py dispatch \
    -t "设计微服务电商后端" \
    -r arch --backend openai --stream
```

流式模式下，LLM 响应会实时逐块输出到终端，无需等待完整响应。
适合长时间生成的内容，可以提前看到结果并随时中断。

### 示例 5：共识模式

```bash
python3 scripts/cli.py dispatch \
    -t "为分析平台选择数据库" \
    -r arch sec \
    --mode consensus
```

共识模式在角色意见不一致时强制投票。每个角色投加权票，否决权受尊重，
死锁时可升级人工裁决。

### 示例 6：JSON 输出（自动化集成）

```bash
python3 scripts/cli.py dispatch \
    -t "审查代码库性能问题" \
    -r arch coder \
    --format json
```

JSON 输出是机器可读格式，适合 CI/CD 流水线或后续处理。

## Docker 使用

```bash
# 构建镜像
docker build -t devsquad .

# Mock 模式运行
docker run devsquad dispatch -t "设计认证系统"

# 带 API Key 运行
docker run -e OPENAI_API_KEY="sk-..." devsquad dispatch -t "设计认证系统" --backend openai

# 交互式终端
docker run -it devsquad /bin/bash
```

## 配置文件使用

创建 `~/.devsquad.yaml`:

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

优先级: 环境变量 > 配置文件 > 默认值

```bash
# 配置文件设置后，无需每次指定 --backend
python3 scripts/cli.py dispatch -t "设计认证系统"
# 自动使用配置文件中的 openai 后端
```

## 系统命令

```bash
# 列出所有可用角色
python3 scripts/cli.py roles

# 显示系统状态
python3 scripts/cli.py status

# JSON 格式列出角色
python3 scripts/cli.py roles --format json

# 显示版本
python3 scripts/cli.py --version    # 3.3.0
```

## Python API 示例

### 基础调度（带真实 LLM 后端）

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
result = disp.dispatch(
    "设计用户认证系统",
    roles=["architect", "pm", "tester"],
    mode="auto",
)

print(result.summary)
print(result.to_markdown())
disp.shutdown()
```

### Mock 模式（无需 API Key）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch(
    "设计用户认证系统",
    roles=["architect", "pm", "tester"],
)

print(result.summary)
disp.shutdown()
```

### 流式输出（Python API）

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend("openai", api_key=os.environ["OPENAI_API_KEY"])
disp = MultiAgentDispatcher(llm_backend=backend)

# 使用流式 Worker
from scripts.collaboration.worker import Worker
worker = Worker(role="architect", backend=backend, stream=True)
# Worker 会实时打印 LLM 响应块

result = disp.dispatch("设计认证系统", roles=["architect"])
disp.shutdown()
```

### 使用配置管理器

```python
from scripts.collaboration.config_loader import ConfigManager

config_mgr = ConfigManager()
config = config_mgr.load()
print(f"Backend: {config.backend}")
print(f"Model: {config.model}")
print(f"Timeout: {config.timeout}")
```

### 使用检查点管理器

```python
from scripts.collaboration.checkpoint_manager import CheckpointManager

ckpt_mgr = CheckpointManager(storage_dir="/tmp/checkpoints")

# 从调度结果创建检查点
checkpoint = ckpt_mgr.create_checkpoint_from_dispatch(dispatch_result)

# 列出所有检查点
checkpoints = ckpt_mgr.list_checkpoints()

# 从检查点恢复
restored = ckpt_mgr.load_checkpoint(checkpoint.checkpoint_id)
```

## 角色参考

| 角色 | CLI ID | 别名 | 最适合 |
|------|--------|------|--------|
| 架构师 | `arch` | `architect` | 系统设计、技术选型、性能/安全/数据架构 |
| 产品经理 | `pm` | `product-manager` | 需求分析、用户故事、验收标准 |
| 安全专家 | `sec` | `security` | 威胁建模、漏洞审计、合规检查 |
| 测试专家 | `test` | `tester`, `qa` | 测试策略、质量保证、边界用例 |
| 编码员 | `coder` | `solo-coder`, `dev` | 功能实现、代码审查、性能优化 |
| 运维工程师 | `infra` | `devops` | CI/CD、容器化、监控、基础设施 |
| UI 设计师 | `ui` | `ui-designer` | UX 流程、交互设计、无障碍 |

## CLI 选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--task`, `-t` | string | 必填 | 任务描述 |
| `--roles`, `-r` | list | auto | 角色（短 ID: arch/pm/test/coder/ui/infra/sec） |
| `--mode`, `-m` | enum | auto | 执行模式: auto/parallel/sequential/consensus |
| `--backend`, `-b` | enum | mock | LLM 后端: mock/trae/openai/anthropic |
| `--base-url` | string | env | 自定义 API 地址（或 OPENAI_BASE_URL 环境变量） |
| `--model` | string | env | 模型名（或 OPENAI_MODEL/ANTHROPIC_MODEL 环境变量） |
| `--stream` | flag | false | 实时流式输出 LLM 响应（需 --backend） |
| `--format`, `-f` | enum | markdown | 输出: markdown/json/compact/structured/detailed |
| `--dry-run` | flag | false | 模拟不执行 |
| `--quick`, `-q` | flag | false | 使用 quick_dispatch（3 种格式） |
| `--action-items` | flag | false | 包含 H/M/L 优先级行动项 |
| `--timing` | flag | false | 包含执行时间数据 |
| `--persist-dir` | string | auto | 自定义 scratchpad 目录 |
| `--no-warmup` | flag | false | 禁用启动预热 |
| `--no-compression` | flag | false | 禁用上下文压缩 |
| `--skip-permission` | flag | false | 跳过权限检查 |
| `--no-memory` | flag | false | 禁用记忆桥接 |
| `--no-skillify` | flag | false | 禁用技能学习 |
| `--permission-level` | enum | DEFAULT | PLAN/DEFAULT/AUTO/BYPASS |

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI 兼容后端的 API Key | `--backend openai` 时必需 |
| `OPENAI_BASE_URL` | 自定义 API 端点（如 `https://api.moka-ai.com/v1`） | 可选 |
| `OPENAI_MODEL` | 模型名（如 `gpt-4`, `moka/claude-sonnet-4-6`） | 可选 |
| `ANTHROPIC_API_KEY` | Anthropic Claude 的 API Key | `--backend anthropic` 时必需 |
| `ANTHROPIC_MODEL` | 模型名（如 `claude-sonnet-4-20250514`） | 可选 |
| `DEVSQUAD_LLM_BACKEND` | 默认后端（mock/openai/anthropic） | 可选 |
| `DEVSQUAD_LOG_LEVEL` | 日志级别 | 可选 |

## MCP 服务器（用于 OpenClaw / Cursor）

```bash
# 安装 MCP 包（可选）
pip install mcp

# stdio 模式启动
python3 scripts/mcp_server.py

# SSE 模式启动
python3 scripts/mcp_server.py --port 8080
```

暴露 6 个工具: `multiagent_dispatch`, `multiagent_quick`, `multiagent_roles`,
`multiagent_status`, `multiagent_analyze`, `multiagent_shutdown`。
