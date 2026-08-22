# DevSquad ROADMAP — P12 联动推进（V4.5.2 体验打磨 + V4.5.3 / V4.5.4 / V4.5.5）

> **Document Type**: Implementation Roadmap (P12)
> **Created**: 2026-08-22
> **Status**: 🟡 IN PROGRESS
> **Baseline**: V4.5.1 (commit 33ec5ac) + P11 运维物料
> **Target**: V4.5.2 (体验打磨) → V4.5.3 (Artifacts+Effect) → V4.5.4 (Fiber+Coeffect) → V4.5.5 (atomic+意图加载)
> **决策参考**: [V4.4.2_ROADMAP.md §4](V4.4.2_ROADMAP.md) 4.5.x 收拢序列 + 用户 2026-08-22 选型确认

---

## 1. 选型回顾（用户决策 2026-08-22）

按用户 P12 选型，**4 个迭代批次按依赖序联动推进**：

| 优先级 | 迭代 | 主打 | 状态 |
|--------|------|------|------|
| 1 (近期) | **V4.5.2 体验打磨** | MOKA provider + devsquad metrics CLI + GitLab connector stub | 🟡 |
| 2 | **V4.5.3** | Finished Work Artifacts + DispatchEffect revert() | 🟡 |
| 3 | **V4.5.4** | Module Fiber 状态机 + Coeffect 依赖声明 | 🟡 |
| 4 (远期) | **V4.5.5** | Dispatch atomic 事务 + IntentWorkflowMapper 按意图加载 | 🟡 |

每批独立过门禁：Anti-Ghost + 全量回归 + E2E + ruff/mypy + doc_consistency。

---

## 2. 迭代依赖图

```
P12.1 V4.5.2 体验打磨  (补完 V4.5.2 → 真发布)
    ↓
P12.2 V4.5.3 Artifacts + Effect  ← 依赖 Effect 模型承载副作用
    ↓
P12.3 V4.5.4 Fiber + Coeffect     ← 依赖 Artifacts 副作用模型 + 模块生命周期
    ↓
P12.4 V4.5.5 atomic + 意图加载    ← 依赖 Fiber 状态 + Coeffect 解析
```

---

## 3. P12.1 V4.5.2 体验打磨（最近一批）

**目标**：让 V4.5.2 真正"用起来"——补完 LLM provider 矩阵 + 提供运维可观察入口 + 第二个 connector。

### 3.1 范围

| ID | 项目 | 类型 | 说明 |
|----|------|------|------|
| P12.1.1 | **MokaAIBackend** 独立化 | 新增 | 把当前 `OpenAIBackend(MOKA_API_KEY)` 抽成显式 `MokaAIBackend`（base_url=https://api.moka.ai/v1，model=moka-gpt-5.5）。3 单元测试 + 1 集成测试 |
| P12.1.2 | **devsquad metrics CLI** | 新增 | `devsquad metrics [--format text/json]`：打印 V4.5.2 8 个 Prometheus 指标当前值。10 单元测试 |
| P12.1.3 | **GitLab Connector stub** | 新增 | 复用 V4.5.1 Connector Protocol，实现 `GitLabConnector`（api/cli/simulation 三模式同 GitHub）。10 单元测试 + 5 E2E |
| P12.1.4 | **Provider 自检命令** | 新增 | `devsquad doctor --provider moka/openai/anthropic`：连通自检 + 报告延迟 + 报告模型清单。5 单元测试 |
| P12.1.5 | **mock→real 一键切换** | 增强 | `devsquad backend set moka` / `devsquad backend set openai` CLI 子命令，写入 `~/.devsquad/config.yaml`。8 单元测试 |

### 3.2 验收

- ✅ Anti-Ghost：`MokaAIBackend._call_counter > 0` + `devsquad metrics` 命中 8 指标
- ✅ pytest 全量回归（8392+ 测试无回归）
- ✅ ruff/mypy 0 errors
- ✅ doc_consistency 11/11 PASS
- ✅ 真实 MOKA E2E（tag-only 触发）

### 3.3 交付文件

- `scripts/collaboration/moka_backend.py`（新增）
- `scripts/collaboration/gitlab_connector.py`（新增）
- `scripts/cli_metrics.py`（新增）
- `scripts/cli_doctor.py`（新增）
- `scripts/cli_backend.py`（新增）
- 5 个对应 test 文件

---

## 4. P12.2 V4.5.3 Artifacts + Effect

**目标**：从"报告"到"交付物" + 副作用可撤销。

### 4.1 范围

| ID | 项目 | 类型 | 说明 |
|----|------|------|------|
| P12.2.1 | **ArtifactStore** | 新增 | `artifacts/{session_id}/{role}/{filename}` 命名空间 + JSON manifest + .gitignore 自动忽略 |
| P12.2.2 | **Worker 写 artifact** | 增强 | 7 角色 worker 完成后产出 PRD/补丁/测试/报告等实际工件，写入 ArtifactStore。Anti-Ghost：`_call_counter > 0` |
| P12.2.3 | **DispatchEffect Protocol** | 新增 | `apply(ctx) → EffectOutcome`, `revert() → EffectOutcome`。revert 幂等 |
| P12.2.4 | **EffectRegistry** | 新增 | dispatch 失败时按 LIFO 自动回滚所有已应用 effect |
| P12.2.5 | **Artifact ↔ Effect 绑定** | 增强 | 每次 artifact 写入记 effect，删除/重命名可回滚 |

### 4.2 验收

- ✅ 模拟真实用户 E2E（dispatch 失败 → 验证 artifact 被 revert）
- ✅ Anti-Ghost 5/5 新模块激活
- ✅ 全量回归

### 4.3 交付文件

- `scripts/collaboration/artifact_store.py`（新增）
- `scripts/collaboration/dispatch_effect.py`（新增）
- `scripts/collaboration/effect_registry.py`（新增）
- 角色 worker 6 文件（修改）
- 6 个测试文件

---

## 5. P12.3 V4.5.4 Fiber + Coeffect

**目标**：模块状态可观测 + 依赖可解析。

### 5.1 范围

| ID | 项目 | 类型 | 说明 |
|----|------|------|------|
| P12.3.1 | **Module Fiber 状态机** | 新增 | 5 状态：Inactive / Activating / Active / Deactivating / Failed；模块生命周期状态机 |
| P12.3.2 | **Coeffect 协议** | 新增 | `depends_on(...)` 声明依赖；dispatcher 启动时按拓扑序激活 |
| P12.3.3 | **状态观测 CLI** | 新增 | `devsquad modules status` 打印所有模块 Fiber 当前状态 |
| P12.3.4 | **激活失败处理** | 增强 | Coeffect 解析失败 → 优雅降级（不影响主流程） |

### 5.2 验收

- ✅ 状态机迁移测试（5 状态 × 4 转移 × 3 模块 = 60 cases）
- ✅ Anti-Ghost 5/5
- ✅ 全量回归

### 5.3 交付文件

- `scripts/collaboration/module_fiber.py`（新增）
- `scripts/collaboration/coeffect.py`（新增）
- `scripts/cli_modules.py`（新增）
- 5 个测试文件

---

## 6. P12.4 V4.5.5 atomic + 意图加载

**目标**：dispatch 事务一致性 + 按需动态加载。

### 6.1 范围

| ID | 项目 | 类型 | 说明 |
|----|------|------|------|
| P12.4.1 | **dispatch(atomic=True)** | 增强 | 全部 worker 成功才 commit，否则触发 EffectRegistry revert |
| P12.4.2 | **IntentWorkflowMapper** | 新增 | 任务描述 → 意图（code/test/refactor/docs/...） → 动态加载对应工作流模块 |
| P12.4.3 | **IntentWorkflowRegistry** | 新增 | 意图 ↔ workflow 注册表；启动 lazy import |
| P12.4.4 | **意图识别 E2E** | 新增 | 5 意图 × 3 任务描述 = 15 E2E |

### 6.2 验收

- ✅ 事务原子性测试（部分失败 → revert 全部）
- ✅ 意图识别 F1 ≥ 0.85
- ✅ Anti-Ghost
- ✅ 全量回归

### 6.3 交付文件

- `scripts/collaboration/intent_mapper.py`（新增）
- `scripts/collaboration/intent_registry.py`（新增）
- 调度器 3 文件（修改）
- 5 个测试文件

---

## 7. 总体验收（V4.5.2 → V4.5.5）

### 7.1 版本与文档

- VERSION：4.5.1 → 4.5.2（体验打磨）→ 4.5.3 → 4.5.4 → 4.5.5
- 每批 VERSION_HISTORY.md / CHANGELOG.md 同步
- 每批 ROADMAP.md 状态行更新
- 每批 release_notes/V{VER}_RELEASE_NOTES.md 新建

### 7.2 出口条件（4 批全部完成时）

- ✅ 8392+ → 8500+ 测试无回归
- ✅ ruff/mypy 0 errors
- ✅ doc_consistency 11/11
- ✅ 5 模块 + 体验打磨 + Artifacts + Fiber + Intent 全部 `_call_counter > 0`
- ✅ 真实 LLM E2E（mock→real→atomic）覆盖
- ✅ 模拟真实用户测试

### 7.3 V4.6.0 收拢（下一步，未在本 P12 范围）

- 反思模块（外部 comment-positioning）
- Benchmark（50 repos / 200 PR）
- Kanban 视图
- 多语言扩展（JP/KO/ES/FR）
- mutmut mutation testing 试点

---

## 8. 风险与回退

| 风险 | 影响 | 缓解 |
|------|------|------|
| MOKA API 不稳定 | P12.1 体验打磨延期 | simulation 模式兜底 + 5 分钟超时 |
| Effect revert 部分失败 | 副作用残留 | revert() 幂等 + 失败记 warning 不阻塞 + 定期 reconciler |
| Fiber 状态机回归 | 模块激活断裂 | 增量不改 `_call_counter`，全量回归覆盖 |
| 意图识别 F1 低 | 加载错误模块 | 保守起步（白名单 + 关键词 + LLM），失败 fallback 全加载 |
| atomic 事务性能 | dispatch 慢 | 仅 `atomic=True` 启用，否则保持现状 |

---

## 9. 时间预估

> **注**: 仅供规划参考，不作为承诺。

| 迭代 | 估时 |
|------|------|
| P12.1 V4.5.2 体验打磨 | ~1 个工作单元 |
| P12.2 V4.5.3 Artifacts + Effect | ~2 个工作单元 |
| P12.3 V4.5.4 Fiber + Coeffect | ~2 个工作单元 |
| P12.4 V4.5.5 atomic + 意图加载 | ~2 个工作单元 |
| **合计** | ~7 个工作单元 |

---

> **Document End**
>
> **Version**: V1.0.0
> **Created**: 2026-08-22
> **Next Update**: 完成 P12.1 后刷新批次状态