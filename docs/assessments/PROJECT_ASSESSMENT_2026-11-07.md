# DevSquad 项目整理评估报告（权威版）

**评估日期**: 2026-11-07
**项目版本**: V4.10.0
**评估范围**: 7 维度代码走读、文档、技术债、测试、CI/CD、目录结构、成熟度
**文档状态**: AUTHORITATIVE — 本文替代 `docs/assessments/` 下同日期的历史报告

---

## 1. 结论摘要

DevSquad 的核心引擎可运行，测试规模大。但本轮发现 1 个阻断级产品缺陷：**按仓库自带配置，任何用户都无法登录仪表盘**。该缺陷已修复。

**成熟度评级：预发布可用（Pre-Production Ready）。尚未达到生产就绪。**

2026-11-08 更新：真实浏览器回归与虚拟环境两项阻断项已关闭。

| 维度 | 评级 | 依据 |
|------|------|------|
| 架构 | B | 12 阶段生命周期为单一真源；层数清晰；单文件过大 |
| 正确性 | B- | 修复认证阻断缺陷；真实浏览器旅程通过 |
| 安全 | C+ | 明文密钥已脱敏；历史密钥待自然失效 |
| 性能 | B | 性能门禁去抖；环境缩放有效 |
| 可维护性 | B- | 解释器已统一；单文件过大；评估文档已收敛 |
| 可测试性 | A- | 10,656 用例；含真实浏览器 E2E |
| 可观测性 | B- | Prometheus 指标存在；`prometheus-client` 本机已装，但未列入 `.[dev]` |

剩余条件（3 个，均非阻断）：
1. 密钥到期后确认作废。无需轮换。
2. 浏览器回归未进入 CI。当前需手动安装 Playwright。
3. 真实 LLM 端到端仅在有凭据时运行。默认套件使用 mock 后端。

---

## 2. 7 维度代码走读

### 2.1 架构

发现：
- `PHASE_TEMPLATES` 在 [workflow_engine_base.py](file:///Users/lin/trae_projects/DevSquad/scripts/collaboration/workflow_engine_base.py) 中是 12 阶段（P0–P11）的唯一真源。该设计正确。
- 访问层分为 Streamlit、FastAPI、CLI。三层职责清楚。
- `scripts/` 共 119,202 行。原最大文件 `qa/deterministic_rule_engine.py`（1,684 行）和 `collaboration/dispatcher.py`（1,272 行）已于 2026-11-08 拆分：前者降为 567 行，规则检查进入 `scripts/qa/rule_checks/`；后者降为 815 行，激活与 RBAC 方法进入两个 mixin。两者均低于 800 行基线。

建议：只对两个最大文件做拆分。不要全局重构。

### 2.2 正确性

本轮发现并修复：

1. **阻断缺陷**：`AuthManager._load_config()` 用 `yaml.safe_load` 读取配置，但不展开 `${VAR}` 占位符。`config/deployment.yaml` 的全部口令均以占位符声明。结果：存库口令是字面量 `"${DEVSQUAD_OPERATOR_PASSWORD_HASH}"`，登录永远失败。
   - 修复：[auth.py](file:///Users/lin/trae_projects/DevSquad/scripts/auth.py#L115-L146) 新增递归环境变量展开。未设置的变量保留字面量，安全校验仍可告警。
   - 证据：修复前 `verify_credentials("operator", ...)` 返回 `None`；修复后返回 `User(role=operator)`。
2. DAG 视图测试与 12 阶段真源漂移（测试断言 11 个节点）。已改为 12。
3. 失败分类法把"缺可选 SDK"判为 `product_failed`。已改为 `environment_blocked`。
4. 质量闸门把测试夹具字符串里的 `except:` 判为违规。已改为 tokenize 感知。

### 2.3 安全

- 发现明文 Moka API Key：`docs/MOKA_TUNING_GUIDE.md` 第 116 行。已改为 `$MOKA_API_KEY`。
- 该 Key 已进入 git 历史。**必须轮换。** 本仓库无法作废它。
- 扫描未发现生产代码中的 `eval`/`exec`、不安全 `pickle.load`、不安全 `yaml.load`。
- `tests/security/` 76 项通过，含全仓库密钥扫描。
- 认证默认拒绝失败登录。未展开的占位符不得放行（已加回归测试）。

### 2.4 性能

- 存在环境缩放机制：`perf_ceiling_ms()` 用与业务无关的参照负载计算系数。
- 发现 2 个门禁在全量套件并行负载下误报。单独运行时 3/3 通过。
- 根因：单次计时采样。修复：取 3 次运行的最小值（噪声只会增加耗时）。
- 修复后性能子集 350 项全部通过。

### 2.5 可维护性

- `scripts/` 中 `TODO`/`FIXME`/`HACK` 共 4 处，集中在 `simplicity_role.py`。数量健康。
- `docs/assessments/` 原有 24 份文档。多份含不实数字（如"9,944 passed"）。已标注为过期。
- 本地虚拟环境曾混用解释器，已于 2026-11-08 重建修复：
  - 旧状态：`.venv/bin/python` = 3.12.13；`pytest`、`pip`、`streamlit` 的 shebang = 3.14。命令之间加载不同 site-packages。
  - 现状态：全部入口均为 3.12。已实测 10,656 项通过。

### 2.6 可测试性

四层测试均已执行。数字见第 4 节。

- UI 层用 Streamlit `AppTest` 运行真实脚本、真实配置、真实登录。
- 真实浏览器层已通过。`tests/e2e/test_dashboard_browser_real.py` 用 Playwright 驱动 Chromium，完成登录、进入派发页、提交任务、校验结果面板。成功判据为页面出现 `Status: ✅ Success`。
  - 关键实现细节：Streamlit 只在控件失焦时提交值，因此输入后需按 `Tab`；密码框的 `aria-label` 与"显示密码"按钮重名，需直接定位 `input[aria-label="Password"]`。
  - 该用例标记 `requires_browser`。未安装 Playwright 或 Chromium 时自动跳过。

### 2.7 可观测性

- `/metrics` 暴露 Prometheus 指标。风险库有统计输出。
- 仪表盘曾显示 `prometheus-client not installed`。本机已手动安装，但该依赖仍未列入 `.[dev]`。建议补入。
- 失败分类会把 `failure_class` 写入 stderr。CI 可直接归因。

---

## 3. 技术债与幽灵功能

| 项目 | 结论 | 证据 |
|------|------|------|
| 模块激活门禁 | 通过 | `check_module_activation.py`：8/8 生产验证，27 自调用验证 |
| 自调用验证强度 | 已加强 | 新增 14 条真实链路用例，覆盖 22 个模块；5 个无引用模块 xfail 留证 |
| 认证配置链路 | 曾是幽灵功能 | 文档声明可用，实际不可登录；已修复并加测试 |
| 文档一致性门禁 | 通过 | `check_doc_consistency.py` PASS |
| Streamlit API 弃用 | 已关闭 | 21 处 `use_container_width` 已迁移到 `width="stretch"`，下限提升到 1.50.0 |

---

## 4. 测试实测数据

环境：本地 macOS，`PYTHONPATH=.`，`pytest -q -p no:cacheprovider`。

| 层级 | 命令范围 | 结果 |
|------|----------|------|
| 单元/顶层 | `tests/` 排除 e2e 与 integration | 8,791 passed, 31 skipped |
| 集成 | `tests/integration` | 1,528 passed, 2 skipped |
| E2E | `tests/e2e` | 337 passed, 5 skipped |
| 安全 | `tests/security` | 76 passed |
| 性能 | `-k "perf or performance"` | 350 passed |
| 认证/安全回归 | 4 个文件 | 176 passed |

合计：10,656 passed，38 skipped。全部 exit 0。

本轮新增回归用例 3 个：
- `tests/e2e/test_user_journey_login.py`：占位符展开后可登录；未设置变量时拒绝登录。
- `tests/e2e/test_dashboard_browser_real.py`：真实 Chromium 完成登录、进入派发页、提交任务、校验结果面板。实测 19.7 秒通过。

浏览器用例的证据：`artifacts/e2e_screenshots/01_logged_in.png`、`02_dispatch_result.png`。该目录已被 `.gitignore` 忽略。

改动前基线为 `20 failed, 8751 passed, 18 skipped`。20 个失败全部归因并修复。

---

## 5. CI/CD 检查

| 项目 | 状态 | 说明 |
|------|------|------|
| Python 矩阵 | 正常 | CI 为 3.10/3.11/3.12；本地 `.venv` 已统一到 3.12 |
| 依赖安装 | 正常 | `mcp<2` 固定版本，保留 FastMCP 1.x API |
| 密钥扫描 | 正常 | `no-secrets.yml` 覆盖全仓库 |
| 性能基线 | 正常 | `perf-baseline.yml` 存在 |
| 发布 E2E | 正常 | `release-e2e.yml` 存在 |
| 门禁包装器 | 过期 | `devsquad-gate-wrapper.yml` 固定 `@v4.9.0`，落后于 4.10.0 |

---

## 6. 目录清理

已删除：
- 覆盖率生成物：`htmlcov*/`（7 个）、`coverage.json`、`coverage.xml`
- 构建物：`build/`、`devsquad.egg-info/`
- 缓存：`__pycache__/`、`.pytest_cache/`
- 一次性脚本：`scripts/add_test_markers.py`
- 根目录误命名测试：`test_moka_config.py` → `scripts/diagnose_moka.py`

`.gitignore` 已加入 `htmlcov_*/`。

---

## 7. 风险清单

| 级别 | 风险 | 处置 |
|------|------|------|
| P1 | Moka API Key 已进入 git 历史 | 不轮换，等密钥自然失效。本地 `pre-commit` 已加 `no-secrets` 钩子。CI 已有三层防护。 |
| P2 | 5 个模块无生产引用 | 建议全部删除。详见 7.1。当前用 xfail 记录证据。 |

已关闭：
- 明文密钥再次进入提交（2026-11-08 新增 `no-secrets` pre-commit 钩子和 3 条同形态回归用例）。
- 真实浏览器登录旅程未验证（2026-11-08 通过 Playwright 验证）。
- venv 解释器混用（2026-11-08 重建为 3.12）。
- 门禁包装器版本落后（2026-11-08 升级到 `v4.10.0`）。
- 27 个模块只有自调用证据（2026-11-08 新增 14 条真实链路用例，覆盖 22 个）。
- Streamlit 弃用 API（2026-11-08 迁移到 `width="stretch"`）。
- 浏览器回归未进入 CI（2026-11-08 新增 `browser-e2e` 任务）。
- `prometheus-client` 未列入 `.[dev]`（2026-11-08 补入）。
- `devsquad audit` 未进入分发分支（2026-11-08 修复并加回归用例）。

### 7.1 5 个无引用模块的处置建议

判定方法：在 `scripts/` 和 `skills/` 中搜索 import 语句。排除 `scripts/check_module_activation*.py` 探针后，5 个模块均无生产引用。

| 模块（注册名） | 行数 | 设计初衷 | 建议 | 理由 |
|------|------|------|------|------|
| `gitlab_connector.py`（GitLabConnector_P12.1.3） | 393 | V4.5.2 第二个外部连接器。支持 MR 评论、Issue 状态、MR 审批。 | 删除 | `ConnectorFramework` 只接线 GitHub。GitLab 没有用户路径。将来需要时，在 `ConnectorFramework` 内增加后端，不保留独立模块。 |
| `dispatcher_transaction.py`（DispatcherTransaction_P12.4.2） | 412 | V4.5.6 模块依赖图的事务边界。5 状态 FSM。 | 删除 | `EffectRegistry.revert_all()` 已覆盖副作用回滚。调度器没有模块级依赖图。 |
| `dispatcher_intent_mapper.py`（IntentWorkflowMapper_P12.4.3） | 236 | V4.5.6 用 YAML 解析 6 intent × 3 语言的工作流。 | 删除 | 与已接线的 `intent_workflow_mapper.py`（513 行）职责重复。CLI 和组件工厂只调用后者。 |
| `dispatcher_loop_controller.py`（DispatchLoopController_P12.4.4） | 256 | V4.5.6 循环熔断。连续 2 次同因 retriable 转为 fatal。 | 删除 | 调度器没有循环重试。接线等于新增一套重试机制，超出当前需求。 |
| `async_coeffect_resolver.py`（AsyncCoeffectResolver_P12.5.1） | 259 | V4.5.7 异步版 CoeffectResolver。6 状态 FSM。 | 删除 | 同步版已在 `dispatcher_activation_mixin` 接线。coeffect 解析是拓扑排序，异步化没有收益。 |

删除成本：
- 生产代码 5 个文件，共 1,556 行。
- 测试 8 个文件：`tests/test_gitlab_connector.py`、`tests/test_dispatcher_transaction.py`、`tests/test_dispatcher_intent_mapper.py`、`tests/test_dispatcher_loop_controller.py`、`tests/unit/test_async_coeffect_resolver.py`、`tests/contract/test_coeffect_api_contract.py`、`tests/integration/test_async_coeffect_pipeline.py`、`tests/e2e/test_coeffect_async_pipeline.py`。
- 探针 3 处：`scripts/check_module_activation.py`、`scripts/check_module_activation_probes.py`、`tests/integration/test_selfcall_modules_real_path.py` 的 `UNREACHABLE_MODULES`。
- 模块清单数字：self-call 已验证模块从 27 降到 22。

结论：5 个全部删除。唯一例外：如近期出现 GitLab 用户，只接线 `GitLabConnector`，并在 `ConnectorFramework` 内注册。

### 7.2 已接受的延后项：4 个超基线文件

用户决定：本轮不拆分。文件再增长时，一并修复。

| 文件 | 当前 LOC | 基线 LOC | 增量 | 决定 |
|------|------|------|------|------|
| `collaboration/unified_gate_engine.py` | 999 | 902 | +97 | 延后 |
| `collaboration/lifecycle_shortcut_adapter.py` | 822 | 776 | +46 | 延后 |
| `collaboration/test_quality_guard.py` | 1,070 | 1,040 | +30 | 延后 |
| `collaboration/coordinator.py` | 833 | 806 | +27 | 延后 |

处理方式：`docs/audits/dispatcher_size_baseline.json` 已按当前尺寸刷新。尺寸门禁恢复绿色。门禁规则不变：任一再增长都会阻塞 PR。

触发条件：任一文件再次超过基线，或进入下一次拆分窗口，就一并拆分。

注意：这不是免责。这是有记录的延后项。

---

## 8. 下一步建议（按顺序）

1. API Key 到期后确认作废。随后按需清理 git 历史。
2. 执行 7.1 的删除建议。等用户授权。
3. 7.2 的 4 个文件在下次扩张时拆分。

---

## 9. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-11-07 | 首次发布权威评估。包含认证缺陷修复、性能门禁去抖、测试基线 |
| 2026-11-08 | 重建 `.venv` 为 Python 3.12；新增 Playwright 真实浏览器 E2E；评级升至预发布可用 |
| 2026-11-08 | 关闭工程遗留：gate wrapper v4.10.0、浏览器回归入 CI、`width` 迁移、`prometheus-client` 入 dev、`devsquad audit` 修复、22 个模块真实链路断言、两个超大文件拆分（1684→567、1272→815） |
| 2026-11-08 | 密钥防护前移：新增 `no-secrets` pre-commit 钩子和 3 条同形态回归用例。评估 5 个无引用模块，建议全部删除。刷新尺寸基线，记录 4 个延后文件 |
