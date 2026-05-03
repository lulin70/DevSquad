# DevSquad 快速参考 (V3.6.0-Prod)

> **版本**: V3.6.0-Prod | **最后更新**: 2026-05-03
>
> 所有 DevSquad 命令、选项和 API 的快速参考。
> **生产就绪**: 认证 ✅ | API ✅ | 告警 ✅ | 历史记录 ✅

## 角色映射

| 角色 | CLI ID | 别名 |
|------|--------|------|
| 架构师 | `architect` | `arch` |
| 产品经理 | `pm` | `product-manager` |
| 安全专家 | `security` | `sec` |
| 测试专家 | `tester` | `test` |
| 开发者 | `coder` | `solo-coder`, `dev` |
| DevOps | `devops` | `infra` |
| UI 设计师 | `ui` | `ui-designer` |

## CLI 命令

```bash
python3 scripts/cli.py dispatch -t "task"              # 自动匹配
python3 scripts/cli.py dispatch -t "task" -r architect  # 指定角色
python3 scripts/cli.py dispatch -t "task" --mode consensus  # 共识模式
python3 scripts/cli.py dispatch -t "task" --backend openai   # OpenAI
python3 scripts/cli.py dispatch -t "task" --stream           # 流式输出
python3 scripts/cli.py dispatch -t "task" --lang zh          # 中文输出
python3 scripts/cli.py status                             # 状态
python3 scripts/cli.py roles                              # 列出角色
python3 scripts/cli.py --version                          # 版本
```

## 输出格式

| 格式 | 说明 |
|------|------|
| `markdown` | Markdown（默认） |
| `json` | JSON 结构化 |
| `compact` | 精简版 |
| `structured` | 结构化报告 |
| `detailed` | 详细报告 |

## LLM 后端

| 后端 | 环境变量 | 默认模型 |
|------|---------|---------|
| mock | 无需配置 | - |
| openai | `OPENAI_API_KEY` | gpt-4 |
| anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |

## 多语言

| `--lang` | 输出语言 |
|----------|---------|
| `zh` | 中文 |
| `en` | English |
| `ja` | 日本語 |
| (不指定) | 自动检测 |

## 配置优先级

环境变量 > `~/.devsquad.yaml` > 默认值
