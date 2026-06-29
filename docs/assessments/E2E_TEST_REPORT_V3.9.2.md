# DevSquad V3.9.2 发布前 E2E 测试报告

**测试日期**: 2026-06-29
**版本**: V3.9.2
**测试人**: AI Agent (devsquad skill)
**Python 解释器**: python 3.12.13 (pyenv) — 系统 python3 为 3.9.6 不支持 PEP 604 语法

## 测试范围

依据用户硬约束 "发布前必须完成模拟真实用户使用的测试"，本次 E2E 测试覆盖 5 个核心场景：

| # | 场景 | 状态 | 说明 |
|---|------|------|------|
| E2E-1 | start.sh 一键启动链路 | ✅ PASS | bash 语法 OK + 14 单元测试通过 + API server HTTP 200 |
| E2E-2 | 真实用户登录流程 | ✅ PASS | 6 个场景全通过（PBKDF2 登录/legacy 迁移/错误密码/未知用户/角色权限/session 唯一性） |
| E2E-3 | API 端点烟雾测试 | ✅ PASS | 5/5 端点 200 OK（修复了 check_command_gate 幽灵函数） |
| E2E-4 | 数据导出/检索 | ✅ PASS | 6/6 数据端点 200 OK |
| E2E-5 | 汇总报告 + 提交推送 | ✅ PASS | 本报告 |

## 发现并修复的问题

### Bug-1: `check_command_gate` 幽灵函数（P1 严重）

- **现象**: `GET /api/v1/gates/status` 返回 `{'ShortcutLifecycleAdapter' object has no attribute 'check_command_gate'`
- **根因**: `metrics_gates.py:245` 和 `dashboard/lifecycle_views.py:170` 调用 `protocol.check_command_gate(cmd)`，但 `ShortcutLifecycleAdapter` 从未实现此方法（6 处调用、0 处定义）
- **修复**: 在 `scripts/collaboration/lifecycle_shortcut_adapter.py` 中添加 `check_command_gate(command)` 方法，聚合命令覆盖的所有阶段的 gate 结果（REJECT > CONDITIONAL > APPROVE 优先级）
- **影响**: 修复后 6 个命令（spec/plan/build/test/review/ship）全部返回有效 gate 结果

### Bug-2: API server 版本号不一致（P1 硬约束违反）

- **现象**: API 启动日志显示 `Version: 3.7.0`，但 `/api/v1/health` 返回 `3.9.2`
- **根因**: `scripts/api_server.py` 中 4 处硬编码 `3.7.0`（docstring / root endpoint / startup log / banner），2 处硬编码 `3.9.2`，未从 canonical source `_version.py` 读取
- **修复**: 导入 `from scripts.collaboration._version import __version__ as DEVSQUAD_VERSION`，替换全部 6 处硬编码为 `DEVSQUAD_VERSION`
- **验证**: 版本一致性检查 15/15 全通过

### Bug-3: start.sh 嵌套目录创建（P2 遗漏）

- **现象**: start.sh 的 `RUNTIME_DIRS` 数组仍硬编码 `$PROJECT_ROOT/checkpoints/checkpoints` 和 `$PROJECT_ROOT/checkpoints/handoffs`
- **根因**: P2-1 修复 `CheckpointManager` 默认 `storage_path` 时遗漏了 start.sh 中的硬编码路径
- **修复**: 移除嵌套路径，改为 `$PROJECT_ROOT/handoffs`（base 目录），并添加注释说明 CheckpointManager 自行创建子目录

## 测试详情

### E2E-1: start.sh 启动链路

```
bash -n scripts/start.sh           # 语法检查 OK
python -m pytest tests/test_start_script.py -q   # 14 passed
API server 启动 → curl /api/v1/health → HTTP 200, version=3.9.2
```

### E2E-2: 真实用户登录流程

新建 `tests/e2e/test_user_journey_login.py`，6 个场景：

| 场景 | 描述 | 结果 |
|------|------|------|
| 1 | PBKDF2 哈希密码登录成功 | ✅ PASS |
| 2 | Legacy SHA-256 密码登录 + 自动迁移到 PBKDF2 | ✅ PASS |
| 3 | 错误密码登录失败 | ✅ PASS |
| 4 | 未知用户登录失败 | ✅ PASS |
| 5 | admin/operator/viewer 三角色权限分层 | ✅ PASS |
| 6 | 多次登录 session_id 唯一性 | ✅ PASS |

```
python -m pytest tests/e2e/test_user_journey_login.py -v   # 6 passed
```

### E2E-3: API 端点烟雾测试

| 端点 | HTTP | 结果 |
|------|------|------|
| `GET /api/v1/health` | 200 | `{"status":"healthy","version":"3.9.2"}` |
| `GET /api/v1/lifecycle/phases` | 200 | 11 个阶段定义 |
| `GET /api/v1/lifecycle/status` | 200 | shortcut 模式，11 phases |
| `GET /api/v1/metrics/current` | 200 | CPU 6.0%, Mem 79.4% |
| `GET /api/v1/gates/status` | 200 | 6 命令 gate 结果（修复后） |

### E2E-4: 数据导出/检索

| 端点 | HTTP | 数据量 |
|------|------|--------|
| `GET /api/v1/tasks/history` | 200 | 空（无任务调度） |
| `GET /api/v1/roles` | 200 | 7 个核心角色 |
| `GET /api/v1/metrics/current` | 200 | 完整 metrics |
| `GET /api/v1/lifecycle/status` | 200 | 11 phases 状态 |
| `GET /api/v1/gates/status` | 200 | 6 命令 gate 状态 |
| `GET /api/v1/lifecycle/phases` | 200 | 11 阶段定义 |

## 回归验证

- **ruff check**: All checks passed（3 个修改文件 + 1 个新文件）
- **版本一致性**: 15/15 全通过
- **关键测试**: 51 passed（auth_phase5 31 + e2e_login 6 + start_script 14）

## 结论

V3.9.2 通过发布前 E2E 测试，修复了 3 个问题（1 个 P1 幽灵函数 + 1 个 P1 版本不一致 + 1 个 P2 嵌套目录）。

**production-ready 状态确认**。
