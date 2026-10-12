# DevSquad 技术债跟踪器 (Tech Debt Tracker)

> **文档类型**: 活跃跟踪器 — 每次 commit 后同步更新
> **维护原则**: 活文档 — 新增 TODO/FIXME 时即时登记；解决时标记 RESOLVED
> **最后更新**: 2026-10-12（V4.6.0 W2 技术债登记：TD-002）
> **关联文档**: [TECH_DEBT_ASSESSMENT_V4.0.md](_archive/TECH_DEBT_ASSESSMENT_V4.0.md) — 完整技术债评估 (V4.0.11 基线；V4.6.1 归档)

## V4.6.0 W2 技术债状态

- **新登记**: TD-002（P2）—— host 委托路径不返回 exit 2。来源：`docs/planning/V4.6.0_W2_DESIGN.md` §9 实施期审计项。
- **不留债声明**: W2 的 P2-a / P2-b 本身无遗留项——两侧均有测试覆盖（`tests/unit/test_judge_verdict.py`、`tests/unit/test_ci_pr_comment_workflow.py`）并有真实 PR 验证（设计 §6.2）。TD-002 是 W2 期间**发现**的既有缺口，不在 W2 变更范围内（Surgical Changes），故登记而非混合修复。

## V4.5.20 W1 技术债状态

- **C9/C10 覆盖度与失败归因**: RESOLVED。同步/异步执行、DispatchResult、CLI JSON/Markdown 和非零退出语义已统一，并由 unit、integration、subprocess E2E 与模拟真实用户测试覆盖。
- **P2-4 provider key 隔离**: RESOLVED。根因是本地 `.env` 在删除变量后重新注入 provider key，导致测试意外走真实 provider；测试现在显式置空/禁用 dotenv 加载，入口行为与 CI mock 模式一致。
- **Black 全仓格式失败**: RESOLVED。根因是 Black 未接入阻断 CI/pre-commit 门禁，历史格式漂移长期未被发现；已采用 `ruff format` 作为唯一格式化门禁并完成全仓 reformat。
- **当前未关闭的结构性债务**: D9（测试质量检测器对源码格式的脆弱耦合）和 D10（两个因 reformat 首次超过 800 行的文件拆分）仍登记在 PRD 中，未在本批扩大范围处理。

## V4.5.11 技术债状态

- **活跃 P0/P1 技术债**: 0
- **已裁决关闭**: SQLite risk store（P2-1，维持 JSON-only long-term，重立项条件见 `docs/prd/V4.5.10_PRD.md` §6）
- **V4.5.11 已修复**（V4.5.10 全部顺延项收官）:
  - `_LegacyRiskStoreProxy` / `_RISK_STORE` 已删除（Breaking，测试迁移为 FileRiskStore 直读）
  - `Worker.execute`/`aexecute` 双实现合并为 `_do_work_async` 单实现（`_ado_work` 删除）
  - risks CLI 输出统一（`RISK_FIELD_ORDER` 规范字段序，add 与 list/show/export 同构）
  - bridge 日志无界增长（`PRUNE_MAX_FILES` 保留策略，默认 100）
- **剩余顺延**: 无（V4.5.12 收官：基于上游 TraeMultiAgentSkill v2.8.4 协议与本地 TRAE IDE 3.3.95 真实监听方联调证据框架落地；SQLite 重立项条件监控以 stats + Prometheus alert 双轨交付，裁决维持 JSON-only long-term；`--severity` 已完全退役）

## 范围说明

本跟踪器专注于 `scripts/` 目录下 Python 源码中的 **TODO/FIXME/HACK/XXX/WORKAROUND** 标记的活跃跟踪。
对于更广泛的技术债（架构、测试覆盖、`type: ignore`、文档、God Class 等），
请参阅上方关联的 [TECH_DEBT_ASSESSMENT_V4.0.md](_archive/TECH_DEBT_ASSESSMENT_V4.0.md)。

> **重要**: V4.0.11 评估基线 (TECH_DEBT_ASSESSMENT_V4.0.md §一) 已确认：
> 项目在 V4.0.0 时 TODO/FIXME 数为 1 (非实际问题)，V4.0.11 已清理至 0。
> 本跟踪器作为持续活文档，用于后续新增标记的即时登记。

## 统计概览

| 优先级 | 数量 | 状态 |
|--------|------|------|
| P0 (阻断) | 0 | — |
| P1 (重要) | 0 | — |
| P2 (一般) | 1 | OPEN (TD-002) |
| P3 (低)   | 0 | — |
| **总计** | **1** | |

> **扫描说明**: 运行 `grep -rn "TODO\|FIXME\|HACK" scripts/ --include="*.py" | grep -v "test\|__pycache__"`
> 共返回 18 行匹配。经逐行分析，其中 17 行为**技术债检测工具自身的实现代码**
> （regex 模式、enum 常量、docstring 描述），并非真正的 TODO 标记；
> 仅 1 行为实际注释中包含这些关键字（且为描述性段落标题，非可执行 TODO）。
> 详见下方「扫描方法与排除项」章节。

## 技术债明细

### TD-001: tech_debt_manager.py 描述性段落注释

- **优先级**: P3
- **位置**: `scripts/collaboration/tech_debt_manager.py:477`
- **类型**: 描述性注释（非真实 TODO 标记）
- **描述**: 第 477 行注释 `# TODO/FIXME/HACK comments` 是 `_detect_all` 方法中一段
  代码的段落标题，用于说明其下方 `self._detect_todos(...)` 调用会检测源码中的
  TODO/FIXME/HACK 注释。该注释**不是**待办事项标记，而是检测逻辑的功能描述，
  会被简单的关键字扫描误判为 TODO。
- **建议方案**: 无需修改。该注释准确描述了代码意图，保留有助于可读性。
  V4.3.0 P0-2 todo_drift_monitor 已采用注释感知正则 (`#\s*(TODO|...)(?=[\s:]|$)`)，
  此描述性注释 (`# TODO/FIXME/HACK comments`) 因 TODO 后跟 `/` 不再被误报。
- **状态**: RESOLVED (V4.3.0 P0-2 — todo_drift_monitor 注释感知正则上线后自动消解)

### TD-002: host 委托路径不返回 exit 2（环境阻断无法区分）

- **优先级**: P2
- **位置**: `scripts/cli_dispatch.py:277-285`（`_print_host_result` 返回 0/1）与 `scripts/cli_dispatch.py:425-427`（`cmd_dispatch` 在 host 适配器分支直接 `return dispatch_result`）
- **类型**: 契约缺口（C19 覆盖不全）
- **描述**: C19 承诺「`environment_blocked` 与 `product_failed` 在 CLI 上以退出码 2/1 区分」。
  真实 LLM 路径满足此承诺（`dispatch_exit_code`）。但 host 适配器分支在 `_execute_dispatch`
  内直接 `_print_host_result(...)` 并返回其 0/1，绕过了 `dispatch_exit_code`，因此 host 桥
  不可用时（应属 `environment_blocked`）只得到 exit 1。
- **影响面**: 仅 host 委托路径（无 API key 的委托模式）。真实 LLM CI 与非委托调用不受影响。
  `!= 0` 判定仍然正确（两种失败都非零），只有「区分 1 与 2」的调用方受影响。
- **建议方案**: 让 host 分支经 `failure_taxonomy` 归因后再决定退出码（例如对
  `HostBridgeUnavailable` 类错误走 `exit_code_for_exception`），并补一条 subprocess 级 E2E
  断言 host 桥缺失时 exit 为 2。
- **状态**: OPEN（V4.6.0 W2 期间发现；不与 W2 混合，见设计文档 §9 与 §10 Q5）

## 扫描方法与排除项

### 扫描命令

```bash
cd /Users/lin/trae_projects/DevSquad && grep -rn "TODO\|FIXME\|HACK" scripts/ --include="*.py" | grep -v "test\|__pycache__"
```

### 17 行非 TODO 匹配项分类（已排除）

为避免误导，下表列出其余 17 行匹配的性质，说明为何不计入技术债：

| #  | 位置                                        | 性质     | 说明 |
|----|---------------------------------------------|----------|------|
| 1  | `context_compressor.py:53`                  | Enum 常量 | `TODO = "todo"` — MemoryCategory 枚举成员定义 |
| 2  | `context_compressor.py:220`                 | 列表元素 | `"TODO"` — 类别列表成员 |
| 3  | `context_compressor.py:446`                 | 业务逻辑 | `m.category == MemoryCategory.TODO` — 过滤 TODO 类记忆 |
| 4  | `context_compressor.py:617`                 | 业务逻辑 | `return MemoryCategory.TODO` — 返回枚举值 |
| 5  | `tech_debt_manager.py:427`                  | Regex 模式 | `TODO_PATTERN = re.compile(...)` — 检测器模式定义 |
| 6  | `tech_debt_manager.py:442`                  | Docstring | 描述检测器功能 |
| 7  | `tech_debt_manager.py:601`                  | Docstring | `"""Detect TODO/FIXME/HACK comments."""` |
| 8  | `tech_debt_manager.py:603`                  | 业务逻辑 | `self.TODO_PATTERN.finditer(source)` — 调用检测器 |
| 9  | `tech_debt_manager.py:606`                  | 业务逻辑 | 严重度判定 `tag in ("FIXME", "HACK")` |
| 10 | `tech_debt_manager.py:818`                  | Docstring | 描述公共 API 功能 |
| 11 | `review_checkers.py:52`                     | Regex 模式 | `("todo_left", re.compile(r"\b(?:TODO\|FIXME\|XXX\|HACK)\b"))` |
| 12 | `review_checkers.py:542`                    | Docstring | `"""Check for TODO/FIXME, print debugging, etc."""` |
| 13 | `standardized_role_template.py:509`         | Regex 模式 | `re.findall(r"(?i)\b(TODO\|FIXME\|DEPRECATED\|OUTDATED)\b", ...)` |
| 14 | `standardized_role_template.py:515`         | 描述字符串 | f-string 输出 sediment marker 计数 |
| 15 | `redesign_checkers.py:273`                  | Docstring | `"""Detect functions whose body is only pass/TODO/..."""` |
| 16 | `redesign_checkers.py:278`                  | Regex 模式 | 占位函数检测正则 |
| 17 | `redesign_checkers.py:287`                  | 描述字符串 | f-string 报告占位函数 |

> **结论**: 上述 17 行均为技术债检测工具自身的实现代码（检测器、枚举、报告生成），
> 不构成待办事项。DevSquad 内建的 TODO 检测能力
> （`tech_debt_manager.py` / `review_checkers.py` / `redesign_checkers.py`）
> 本身即是项目成熟度的一部分，其代码自然包含对关键字的引用。

## 维护流程

1. **新增 TODO/FIXME 时**: 开发者在 `scripts/` 下新增此类标记时，须即时在本文件登记新条目 (TD-XXX)，并填写优先级、位置、描述、建议方案。
2. **解决 TODO 时**: 将对应条目状态改为 `RESOLVED` 并保留历史记录（不删除条目），在「变更历史」记录解决日期。
3. **定期扫描**: 每次发布前运行上述扫描命令，核对跟踪器与实际代码一致；剔除检测逻辑误报。
4. **优先级标准**:
   - **P0 (阻断)**: 影响功能正确性/安全性 — 必须在发布前解决
   - **P1 (重要)**: 影响可维护性/性能 — 应在当前迭代解决
   - **P2 (一般)**: 代码质量改进 — 计划在下一迭代解决
   - **P3 (低)**: 可有可无的优化 — 按需解决

## 变更历史

| 日期       | 版本 | 变更                                                                     | 负责人   |
|------------|------|--------------------------------------------------------------------------|----------|
| 2026-07-24 | v1.0 | 初始创建；完成 `scripts/` 目录全量扫描，登记 1 项 P3 (INFORMATIONAL) | DevSquad |
| 2026-07-24 | v1.1 | V4.3.0 P0-2: todo_drift_monitor 注释感知正则上线，TD-001 自动消解标记为 RESOLVED；总计 0→0 | DevSquad |
| 2026-10-12 | v1.2 | V4.6.0 W2: 登记 TD-002（host 委托路径不返回 exit 2，P2/OPEN）；总计 0→1 | DevSquad |
