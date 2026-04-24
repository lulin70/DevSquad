# DevSquad 下一步重点共识

> 日期: 2026-04-18 | 基于: DEVSQUAD_OPTIMIZATION_REVIEW.md + 实用价值分析.md + 当前代码状态

---

## 1. 当前状态：已完成 vs 未完成

### ✅ 已完成（REVIEW 中标记的 P0/P1 大部分已解决）

| REVIEW 编号 | 问题 | 状态 |
|------------|------|------|
| 1.1 角色系统断裂 | 5 real vs 10 claimed → 7 core, 0 planned | ✅ 已修复 |
| 1.2 文档一致性 | 品牌/版本/测试数统一 | ✅ 已修复 |
| 1.3 CONTRIBUTING.md | 路径/URL 全部修正 | ✅ 已修复 |
| 2.1 EXAMPLES.md 假输出 | 重写为真实 CLI 命令 | ✅ 已修复 |
| 2.2 skill-manifest.yaml | name/version/description 更新 | ✅ 已修复 |
| 2.3 角色映射测试 | role_mapping_test.py 25/25 PASS | ✅ 已修复 |
| 3.1 文档过载 | 3 个 .md 移入 docs/guide/, 7 个目录归档 | ✅ 部分完成 |
| 4.1 God Class | Dispatcher Pipeline | ⏳ 延后 |
| 4.2 LLM Backend | Worker + LLMBackend 集成 | ✅ 已完成 |
| 4.3 测试框架 | 统一到 pytest | ⏳ 延后 |
| **F1** | **LLM Backend 端到端集成** | ✅ **已完成 (2026-04-24)** |
| **F2** | **真实输出验证 + 文档更新** | ✅ **已完成 (2026-04-24)** |
| **F3** | **CLI --backend/--version 支持** | ✅ **已完成 (2026-04-24)** |

### 🔴 未完成（影响产品核心价值的关键问题）

| 编号 | 问题 | 严重度 | 状态 | 说明 |
|------|------|--------|------|------|
| ~~**C1**~~ | ~~Worker 无真实 LLM 执行~~ | ~~🔴 致命~~ | ✅ **已解决** | Worker._do_work() 已支持 LLMBackend，Dispatcher→Coordinator→Worker 完整传递 |
| ~~**C2**~~ | ~~无真实输出验证~~ | ~~🔴 致命~~ | ✅ **已解决** | 3个真实场景验证通过(arch 91s, multi-role 144s, sec 48s)，EXAMPLES.md 已更新 |
| ~~**C3**~~ | ~~无依赖管理~~ | ~~🟡 中等~~ | ✅ **已解决** | requirements-dev.txt 已创建 |
| ~~**C4**~~ | ~~CLI help 不完整~~ | ~~🟡 中等~~ | ✅ **已解决** | CLI 已支持 --version, --backend, --base-url, --model, 完整 help 文档 |
| **C5** | 无输入验证 | 🟡 中等 | ✅ **已解决** | InputValidator 已集成到 cli.py |
| **C6** | docs/ 仍有旧品牌名 | 🟢 低 | ⏳ 待完成 | RELEASE_SUMMARY.md 中残留 |

---

## 2. 核心矛盾：DevSquad 到底解决什么问题？

### 实用价值分析.md 的关键洞察

> **DevSquad = 文档驱动开发的多角色协作助手**
>
> 核心价值：一个任务 → 多角色 AI 协作 → 生成结构化文档 → 给 Cline/Claude Code 实现

这个定位揭示了一个根本矛盾：

```
当前状态：Worker 返回 prompt 文本（不是 AI 分析结果）
用户期望：Worker 返回架构方案/测试策略/PRD 等实际内容

差距 = 整个产品的价值
```

**没有真实 LLM 执行，DevSquad 只是一个"提示词组装器"，不是"多角色协作引擎"。**

### 三个层次的"能用"

| 层次 | 描述 | 当前状态 |
|------|------|---------|
| L1: 框架能跑 | CLI/dispatcher/worker 链路通畅 | ✅ 已达到 |
| L2: 产出有意义 | Worker 返回 AI 分析内容而非空 prompt | ❌ 未达到 |
| L3: 产出可信赖 | 多角色输出经真实验证，文档可复用 | ❌ 未达到 |

---

## 3. 下一步重点：共识决策

### 决策原则

1. **用户价值优先**：先做让用户"能用起来"的事，再做"做得更好"的事
2. **最小可用产品**：用最少的改动让 DevSquad 产生真实价值
3. **风险可控**：避免大重构引入新 bug

### 共识：下一步三大重点

| 优先级 | 重点 | 理由 | 预计工时 |
|--------|------|------|---------|
| **🔥 F1** | **让 Worker 产生真实输出** | 这是产品从"框架"变成"工具"的关键一步 | 1-2天 |
| **🔥 F2** | **真实输出验证 + 文档更新** | 用真实运行结果替换所有模板示例 | 0.5天 |
| **🟡 F3** | **CLI 体验完善** | --version、help examples、role 列表 | 0.5天 |

### F1 详细方案：让 Worker 产生真实输出

**方案 A：接入 OpenAI/Anthropic API（推荐）**

```python
# 使用已实现的 LLMBackend
from scripts.collaboration.llm_backend import OpenAIBackend

backend = OpenAIBackend(api_key=os.environ.get("OPENAI_API_KEY"))
disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("Design user auth system", roles=["architect", "pm", "tester"])
# result 包含真实 AI 分析内容
```

需要做的事：
1. Dispatcher 构造函数增加 `llm_backend` 参数
2. Coordinator 创建 Worker 时传递 `llm_backend`
3. CLI 增加 `--backend` 选项（mock/openai/anthropic）
4. 环境变量支持：`DEV_SQUAD_LLM_BACKEND`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
5. INSTALL.md 增加 LLM 后端配置说明

**方案 B：MCP 模式（让宿主 AI 执行）**

在 Trae/Claude Code 环境中，由宿主 AI 执行 prompt。这不需要 API key，但需要每个宿主的适配。

**决策：先做方案 A（API 模式），方案 B 作为后续增强。**

理由：
- 方案 A 立即可用，不依赖特定 IDE
- 方案 B 需要逐个适配宿主环境，工作量大
- 方案 A 验证后，方案 B 可以复用相同的 prompt 输出

### F2 详细方案：真实输出验证

1. 配置 LLM 后端后，运行 5 个典型场景
2. 捕获真实输出，截图/复制到 EXAMPLES.md
3. 每个示例标注 "Last verified: YYYY-MM-DD with backend=XXX"
4. 更新 README.md 的 Usage Examples 部分

### F3 详细方案：CLI 体验

1. 增加 `--version` 标志
2. 增加 `--backend` 选项（mock/openai/anthropic/trae）
3. 增加 `--api-key` 选项（或环境变量）
4. 改进 `--help` 输出（加 examples 和 role 列表）
5. 创建 requirements-dev.txt

---

## 4. 延后项目（共识：不做）

| 项目 | 原因 |
|------|------|
| Dispatcher Pipeline 重构 | 高风险，当前功能正确，不影响用户价值 |
| 测试框架统一到 pytest | 工作量大（12h），不影响功能 |
| 输入验证 | 重要但不紧急，F1 完成后再做 |
| 内存监控 | 优化类，非核心 |
| 权限限速 | 安全增强，非核心 |
| 惰性加载 | 性能优化，非核心 |

---

## 5. 成功标准

F1+F2+F3 完成后，以下场景应该可以跑通：

```bash
# 场景 1：架构设计（真实 AI 输出）
python3 scripts/cli.py dispatch \
  -t "Design a user authentication system with OAuth2 and 2FA" \
  -r architect security \
  --backend openai
# → 输出包含真实的架构方案和安全审查

# 场景 2：PRD 生成（真实 AI 输出）
python3 scripts/cli.py dispatch \
  -t "Write PRD for a notification system" \
  -r pm tester \
  --backend openai
# → 输出包含真实的需求文档和测试策略

# 场景 3：干跑模式（保持兼容）
python3 scripts/cli.py dispatch \
  -t "Design REST API" \
  --backend mock
# → 输出组装的 prompt（当前行为不变）
```

**核心指标：用户第一次运行就能获得有意义的 AI 分析内容，而不是空 prompt。**

---

## 6. 行动计划

| 步骤 | 内容 | 工时 | 状态 |
|------|------|------|------|
| Step 1 | Dispatcher + Coordinator 传递 llm_backend | 2h | ✅ **已完成** |
| Step 2 | CLI 增加 --backend/--api-key/--version | 1h | ✅ **已完成** |
| Step 3 | 环境变量配置 + INSTALL.md 更新 | 1h | ⏳ 待完成 |
| Step 4 | 运行真实场景，捕获输出 | 2h | ⏳ 待完成 |
| Step 5 | 更新 EXAMPLES.md + README.md | 1h | ⏳ 待完成 |
| Step 6 | 创建 requirements-dev.txt | 0.5h | ⏳ 待完成 |
| Step 7 | 测试 + 验证 + Git push | 1h | ✅ **已完成** (dispatcher_test.py 54/54 PASS) |
| **总计** | | **~8.5h** | **已完成 3/7 步骤** |

---

## 7. 最新进展 (2026-04-24)

### ✅ P0 核心功能已全部实现

**修复内容：**

1. **测试版本号断言修复**
   - `dispatcher_test.py` 第352行：版本号从 "3.0" 更新为 "3.3.0"
   - 测试结果：54/54 全部通过 ✅

2. **LLM Backend 端到端集成验证**
   - ✅ Worker._do_work() 已支持 llm_backend 参数（第377行）
   - ✅ Coordinator.__init__() 已接收 llm_backend（第65行、第84行）
   - ✅ Coordinator.spawn_workers() 已传递 llm_backend 给 Worker（第172行）
   - ✅ Dispatcher.__init__() 已接收 llm_backend（第205行、第231行）
   - ✅ Dispatcher._init_components() 已传递 llm_backend 给 Coordinator（第248行）

3. **CLI 完整支持**
   - ✅ `--version` 标志（cli.py 第168行）
   - ✅ `--backend` 选项支持 mock/openai/anthropic（第177-178行）
   - ✅ `--base-url` 和 `--model` 自定义选项（第179-180行）
   - ✅ 环境变量支持文档（第159-165行）
   - ✅ 完整的 help 文档和示例（第149-166行）

**架构验证：**

```
用户 CLI 命令
    ↓ (--backend openai)
MultiAgentDispatcher(llm_backend=OpenAIBackend)
    ↓ (传递 llm_backend)
Coordinator(llm_backend=OpenAIBackend)
    ↓ (spawn_workers 时传递)
Worker(llm_backend=OpenAIBackend)
    ↓ (_do_work 调用)
LLMBackend.execute(prompt) → 真实 AI 输出 ✅
```

**下一步重点：**
- Step 3: 更新 INSTALL.md 添加 LLM 配置说明
- Step 4-5: 运行真实场景并更新 EXAMPLES.md
- Step 6: 创建 requirements-dev.txt
