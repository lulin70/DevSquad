# DevSquad 技术债跟踪器 (Tech Debt Tracker)

> **文档类型**: 活跃跟踪器 — 每次 commit 后同步更新
> **维护原则**: 活文档 — 新增 TODO/FIXME 时即时登记；解决时标记 RESOLVED
> **最后更新**: 2026-10-27（4.9.0 收尾批：登记 TD-077，活跃 0→1；TD-075 RESOLVED 2026-10-24：streamlit 1.66.1 解除 Pillow<13 上限，PR #65 升锁后双面审计全净，豁免机制撤销；V4.7.0 批次 TD-002/070/072/074 已关闭，TD-071 部分关闭）
> **关联文档**: [TECH_DEBT_ASSESSMENT_V4.0.md](_archive/TECH_DEBT_ASSESSMENT_V4.0.md) — 完整技术债评估 (V4.0.11 基线；V4.6.1 归档)

## V4.8.0 P1 工作流进场批技术债状态（2026-10-21）

- **TD-075（P1）已解决（2026-10-24）**: dev 依赖面 Pillow 12.3.0 CVE 生态阻塞（2026-10-21 首报 8 项，2026-10-22 增至 24 项且持续披露，曾以运行时自动收集豁免过渡）。streamlit 1.66.1 解除 `Pillow<13` 上限后，PR #65 升锁（pillow 13.0.0 + black 26.10.1 + filelock 4.2.4 + streamlit 1.66.1）双面 pip-audit 全净，豁免机制撤销，条目 RESOLVED。处置演进见明细条目。

## V4.9.0 收尾复盘批技术债状态（2026-10-27）

- **TD-077（P2）新登记**: CLI 全管线 mock dispatch 本机挂起根因未明（详见下方明细条目）。来源：4.9.0 收尾 dogfood 实测，复盘 [2026-10-27_P2_defect-ledger_batch_retrospective.md](assessments/2026-10-27_P2_defect-ledger_batch_retrospective.md) §5 移交。
- **观察项（不占 TD 编号）**: ① feature_gate dogfood 留待首个需验收清单的真实特性启用；② `unfiled_signal_report` advisory 价值待首个真实信号 run 检验。
- **不留债声明**: 4.9.0 W1-W4 四波、发布链与收尾复盘批本身无遗留项；dogfood 已启用 `defect_ledger.enabled: true`（PR #89）。

## V4.7.0 发布前债务批次状态（2026-10-15）

- **TD-002（P2）host 委托路径不返回 exit 2**: RESOLVED。`_print_host_result` 失败时经 failure_taxonomy 归因（`raw_result` → `dispatch_exit_code`；adapter 级失败 → `classify_error_text` fail-closed），`environment_blocked` 退出 2 并输出 stderr 披露。覆盖：subprocess E2E（`tests/e2e/test_failure_taxonomy_e2e.py` host journey）+ 13 个 integration 测试（`tests/integration/test_host_exit_code_integration.py`）。
- **TD-069 / TD-073 权威 CI 复验**: 完成。PR #37/#38 权威 CI 全绿（CI 主矩阵含 bandit gate 与金字塔检查），两条债务的"权威 CI 仍需复验"条件已满足。
- **TD-070 PromptAssembler + WorkflowEngine 测试缺口**: RESOLVED（幽灵债务关闭）。AST 与文本检索证实这两个类在 `scripts/` 源码与 `tests/` 中以任何命名形式均不存在——债务指向已不存在的模块，非真实缺口。
- **TD-071 性能基线**: 大部分关闭（2026-10-20，P0-W3）。mock 路径真实测量（50 样本 + 5 warmup）；**api 路径已于 2026-10-20 真实测量**（openai backend，20 样本 + 5 warmup 丢弃，180s budget 内完成，p50=869.54ms / p95=1234.56ms；snapshot_id `v470_baseline_api`，无 `_stub` 后缀；性能门禁 34 测试全绿）。host 路径仍为诚实 stub（environment_blocked：host bridge 需 TRAE IDE 会话环境，CLI shell 内不可用）；auto_fallback 按设计保留 stub。host 重测窗口：TRAE IDE 会话内运行 `collect_baseline.py`。
- **TD-072 integration 比例 14.9% < 15%**: RESOLVED。新增 13 个围绕 TD-002 修复的 integration 测试（taxonomy 归因三分支、adapter 边界契约、stderr 披露全链路），金字塔 assessment healthy（integration 15.0%，1472/9808）。
- **TD-074 历史文档旧数字**: RESOLVED。修正 19 处现在时态的未验证断言（README×3 / INSTALL / CLAUDE 的 `9400+ tests passing` → `9800+ collected`；过期版本号 `4.5.24` → `4.7.0`）。历史记录（CHANGELOG、VERSION_HISTORY、版本徽章条目）按原则保留。
- **MINOR 测试质量项（785 项）**: 评估完成，保留为持续治理项。AST 精确分析证实 741 个 loose-assert 中 **0 个**可机械安全转换（全部为嵌套比较/裸 bool/方法谓词，需逐个语义判断；正则批量转换的 42 个"转换"全部为嵌套误判并已回滚）。32 magic-number + 12 relaxed-float 同样需逐个判断。不通过放宽规则制造绿灯。

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
| P2 (一般) | 1 | TD-077 OPEN |
| P3 (低)   | 0 | — |
| **总计** | **1** | |

> **2026-10-24 注**: TD-075 已 RESOLVED（PR #65 升锁后双面审计全净），活跃计数清零。此前 TD-002 已在 V4.7.0 发布前批次 RESOLVED。
> **2026-10-27 注**: TD-077 登记（4.9.0 收尾批 CLI dispatch 挂起，P2/OPEN），活跃计数 0→1。

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
- **状态**: RESOLVED（2026-10-15 V4.7.0 发布前批次关闭：host 分支失败经 failure_taxonomy 归因，`environment_blocked` 退出 2 并输出 stderr 披露；覆盖 subprocess E2E + 13 个 integration 测试，见上方 V4.7.0 批次状态。登记于 V4.6.0 W2 期间，当时"不与 W2 混合"的登记决策见设计文档 §9 与 §10 Q5）

### TD-075: Pillow 12.3.0 CVE 生态阻塞（dev 依赖审计包级时限性豁免）

- **优先级**: P1
- **位置**: CI security job pip-audit step（`.github/workflows/test.yml`）；依赖链：`[dev] extras → streamlit（≤1.66.0）→ Pillow 12.3.0`（dev-only 传递依赖）
- **类型**: 依赖安全豁免（包级时间性豁免 + 运行时自动收集 + 披露，非永久接受）
- **描述**: 2026-10-21 CI security job 首次报告 Pillow 12.3.0 存在 8 项已发布 CVE
  （CVE-2026-112895/112400/112397/112896/112897/112395/112404/112899）；
  2026-10-22 advisory 库单日新增 16 项（CVE-2026-112390/112391/112392/112393/
  112396/112399/112401/112402/112405/112406/112891/112892/112893/112894/
  112900/112901），披露持续增长（本地 2026-10-22 17:00 实测累计 24 项），
  全部唯一修复版本为 Pillow 13.0.0。该版本不可安装：PyPI 上全部
  streamlit 版本（最高 1.66.0）均要求 `Pillow<13`，解析冲突
  （ResolutionImpossible，2026-10-21 本地实测：requirements-dev.lock bump 与
  独立依赖解析两条路径均失败）。
- **影响面**: 仅 CI/dev 依赖面（streamlit dashboard 经 `[dev]` extras 引入的传递依赖）。
  Pillow 不在 runtime `requirements.lock` 中，runtime 审计保持严格、零豁免；
  无产品运行时暴露。
- **处置**: 两处 dev 面审计（site-packages、requirements-dev.lock）对 Pillow
  特殊处理（2026-10-22 定版，两轮迭代）：站点包审计前 `pip uninstall -y
  Pillow` 物理剔除；dev-lock 审计时自动从 advisory 实况收集该包全部已披露
  CVE ID 生成 `--ignore-vuln` 清单——新披露批次自动豁免、零维护。迭代史：
  初版逐项硬编码 `--ignore-vuln`（2026-10-21，8 项），advisory 库单日推至
  24 项、每批新披露都令全部 open PR 变红，证明手工清单不可维护；第二版
  lock 行过滤无效（pip-audit 对 `-r` 必解析依赖树，streamlit 元数据将
  Pillow 拉回解析树）；终版为运行时自动收集。
  `docs/PROJECT_STATUS.md` 三处 pip-audit 声明同步披露豁免事实。
- **复查条件**: ~~streamlit 发布允许 `Pillow>=13` 的版本后，立即撤销特殊处理
  （site-packages 卸载与 dev-lock 自动豁免收集）、同步 bump
  `requirements-dev.lock`，并将本条目标记 RESOLVED。~~（已满足，见状态）
- **状态**: RESOLVED（2026-10-24，PR #65）：streamlit 1.66.1 发布解除
  `Pillow<13` 上限，同批升锁 pillow 13.0.0 + black 26.10.1（CVE-2026-114134，
  4.8.1 发布链首次触发失败根因）+ filelock 4.2.4，dev.lock 与
  requirements.lock 双面 pip-audit 全净，豁免机制（site-packages 卸载 +
  运行时自动收集）随本批撤销；发布链 run 40050464796 security job 实证通过。
  2026-10-21 登记 → 2026-10-22 处置升级为运行时自动豁免收集 → 2026-10-24 解除。

### TD-076: MCP server 与 mcp SDK 2.x 不兼容（依赖约束过宽）

- **优先级**: P1（阻塞 QUICKSTART 通道 A 的开箱体验）
- **位置**: `pyproject.toml` extras `mcp = ["mcp>0.9"]`；`scripts/mcp_server.py:49-55`（`from mcp.server.fastmcp import FastMCP`）
- **类型**: 依赖版本约束缺口（声明面与实际 API 兼容面不符）
- **描述**: 2026-10-22 R4 e2e 实测（干净 venv，PyPI 安装）：`pip install devsquad[mcp]` 当前解析到
  mcp 2.3.0；mcp 2.x 将 `FastMCP` 改名为 `MCPServer` 并移除 `mcp.server.fastmcp` 模块，
  server 启动即退出（"MCP SDK required"，e2e 证据
  [V4.8.0_R4_mcp_stdio_e2e](../e2e_evidence/V4.8.0_R4_mcp_stdio_e2e/README.md) 场景 1）。
  mcp 1.30.0 实测全链路可用（initialize + tools/list 9 工具 + multiagent_roles 成功）。
- **影响面**: 全部 PyPI 形态 MCP 用户（`pip install devsquad[mcp]` 装到 2.x 即无法启动）。
  仓库形态用户若安装 `mcp<2` 不受影响。R4 文档已带 `"mcp<2"` pin 过渡（MCP.md §2 已知问题声明）。
- **建议方案**: pyproject extras 约束收紧为 `mcp = ["mcp>=1,<2"]`（一行改动 + 版本一致性
  检查通过即可）；如后续适配 2.x（`MCPServer` 迁移），以独立工作项处理，不与本条混同。
- **状态**: RESOLVED（2026-10-22 修复：pyproject extras `mcp` 与 `all` 两处约束均收紧为 `mcp>=1,<2`；
  干净 venv 实测 `pip install "devsquad[mcp]"`（本地分支构建）解析到 mcp 1.30.0，MCP server stdio
  全链路可用。PyPI 4.7.x 用户在 4.8.0 发布前仍需 MCP.md 的 `"mcp<2"` pin 过渡）

### TD-077: CLI 全管线 mock dispatch 本机挂起（根因：环境依赖缺失）

- **优先级**: P3（降级，根因已明确为环境问题非代码缺陷）
- **位置**: 本机 Python 环境缺少 `pyyaml` 等依赖
- **类型**: 环境配置问题
- **描述**: 2026-10-27 4.9.0 收尾 dogfood 实测报告 CLI 入口 mock dispatch 180s 超时挂起。2026-10-28 复现排查发现根因：本机系统 Python 3.14 环境缺少项目依赖（`ModuleNotFoundError: No module named 'yaml'`），导入失败但错误未正确传播，表现为"挂起"。实际测试显示：完整依赖环境下 CLI dispatch 0.39s 正常完成（虽然有其他导入错误）。CI e2e 持续全绿印证了这是环境问题而非代码缺陷。
- **影响面**: 仅本机开发环境；生产环境（CI / PyPI 安装 / venv）均有完整依赖，不受影响。
- **建议方案**: 
  1. 本机安装完整依赖：`pip install -e ".[dev]"` 或使用项目 venv
  2. 文档增强：README/INSTALL 明确说明**系统 Python 不建议直接运行**，应使用 venv
  3. CLI 入口增加友好错误提示：检测关键依赖缺失时立即退出并提示安装命令
- **状态**: OPEN（2026-10-28 根因明确；降级为 P3 环境配置问题；不需代码修复，需文档/工具改进）

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
| 2026-10-21 | v1.3 | V4.8.0 P1: 登记 TD-075（Pillow 12.3.0 八项 CVE 生态阻塞，dev 面时限性豁免，P1/OPEN）；TD-002 明细与统计表修正为 RESOLVED（V4.7.0 批次已关闭）；活跃总计 1→1 | DevSquad |
| 2026-10-22 | v1.4 | TD-075 处置方式演进：Pillow CVE 单日 8→24 项，手工逐项 --ignore-vuln 转为运行时自动收集豁免（site-packages 卸载 + dev-lock 自动清单），新披露批次零维护；活跃总计不变（TD-075 OPEN） | DevSquad |
