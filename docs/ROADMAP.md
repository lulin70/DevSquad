# DevSquad Roadmap

> **文档类型**: 战略演进路线图 (Strategic Roadmap)
> **维护原则**: 活文档 — 每个版本发布时同步更新；P2 学习项随 V4.1.0 PRD 评估结果登记。
> **关联文档**:
> - [V43_ROADMAP_PROPOSAL.md](planning/V43_ROADMAP_PROPOSAL.md) — V4.3 统一推进方案 v1.1（7-Role 共识达成）
> - [V4.1.0_PRD_Matt_Skills_Fusion.md](prd/V4.1.0_PRD_Matt_Skills_Fusion.md) — 28 项借鉴范围（P0/P1/P2）
> - [V4.0.11_Matt_Pocock_Skills_Evaluation.md](audits/V4.0.11_Matt_Pocock_Skills_Evaluation.md) — Matt 21 技能评估
> - [V4.1.0_UIUX_Skills_Evaluation.md](audits/V4.1.0_UIUX_Skills_Evaluation.md) — taste-skill / impeccable UI/UX 评估
> - [ROADMAP_V3.7-V4.0.md](ROADMAP_V3.7-V4.0.md) — V3.7-V4.0 历史路线图

---

## 目录

1. [V4.2+ Roadmap（Matt Pocock 工程理念学习项）— 全部落地](#v42-roadmapmatt-pocock-工程理念学习项)
2. [V4.3+ Roadmap（UI/UX Skills 学习项）— 全部落地](#v43-roadmapuiux-skills-学习项)
3. [V4.3+ Roadmap（精细化升级 — 7-Role 共识达成）](#v43-roadmap精细化升级--7-role-共识达成)
4. [已落地条目](#已落地条目)

---

## V4.2+ Roadmap（Matt Pocock 工程理念学习项）

> 来源：V4.1.0 PRD §3.3 P2 学习项（Matt 4 项中 P2-3 git-guardrails 已于 V4.1.0 落地）。
> **状态: 全部落地 ✅** — P2-1/P2-2/P2-4 于 V4.2.1 实现（commit 1fc94aa）。

| ID | 名称 | 状态 | 落地版本 |
|----|------|------|----------|
| P2-1 | PrototypeSkill | ✅ 已落地 | V4.2.1 |
| P2-2 | TeachSkill | ✅ 已落地 | V4.2.1 |
| P2-3 | git-guardrails | ✅ 已落地 | V4.1.0 |
| P2-4 | pre-commit hooks | ✅ 已落地 | V4.2.1 |

详见 [已落地条目](#已落地条目)。

---

## V4.3+ Roadmap（UI/UX Skills 学习项）

> 来源：V4.1.0 PRD §3.4 UI/UX P2 学习项（4 项中 P2-UI-4 4pt 网格间距检测可作为 P1 扩展先行落地，其余 3 项登记于此）。
> **状态: 全部落地 ✅** — P2-UI-1/P2-UI-2/P2-UI-3 于 V4.2.1 实现（commit 1fc94aa），版本保持 4.2.x。

| ID | 名称 | 状态 | 落地版本 |
|----|------|------|----------|
| P2-UI-1 | CLI 命令词表 | ✅ 已落地 | V4.2.1 |
| P2-UI-2 | Live Browser 模式 | ✅ 已落地 | V4.2.1 |
| P2-UI-3 | 6 Meta-skills 分层 | ✅ 已落地 | V4.2.1 |

详见 [已落地条目](#已落地条目)。

---

## V4.3+ Roadmap（精细化升级 — 7-Role 共识达成 + 用户确认）

> 来源：整合技术债跟踪 + pickle→JSON 迁移 + 上游 TraeMultiAgentSkill v2.6-v2.8 启发
> **状态: IMPLEMENTED ✅** — V4.2.9 预发布完成 + Phase 1/2/3 全部落地，升 V4.3.0 正式版
> **基线版本**: V4.2.1 (commit 1fc94aa)
> **目标版本**: V4.2.9 (预发布) → **V4.3.0 (正式版，2026-07-25 发布)**
> **详细方案**: [V43_ROADMAP_PROPOSAL.md](planning/V43_ROADMAP_PROPOSAL.md) v1.2（用户确认合并 V4.3.1→V4.3.0）
> **Phase 1-3 评审**: [P1-7 DependencyHallucinationChecker](analysis/2026-07-25_P1-7_dependency_hallucination_review.md) | [P1-8 OutputValidator](analysis/2026-07-25_P1-8_output_validator_review.md) | [P3 Phase 3](analysis/2026-07-25_P3_phase3_review.md)

### V4.3.0 范围（MINOR — 功能新增，含原 V4.3.1 内容）

| ID | 名称 | 优先级 | 状态 | 来源 |
|----|------|--------|------|------|
| P0-1 | pickle dead code 删除 + fallback 安全收紧 | P0 | ✅ 已实施 | pickle 迁移 |
| P0-2 | `todo_drift_monitor.py` + CI 阻塞 + PR template | P0 | ✅ 已实施 | 技术债监控 |
| P1-1 | Ponytail lite/full 双模式 + DebtCollector + RequirementTracer | P1 | ✅ 已实施 | 上游 v2.6 |
| P1-4 | LoopKernel RollbackStrategy + 累计上下文 + 独立硬上限 | P1 | ✅ 已实施 | 上游 v2.8.1 |
| P1-5 | UIUXAnalyzer 子项审计 + 按需补全（升级自 P2-3） | P1 | ✅ 已实施 | 上游 v2.7 |
| P1-6 | Dashboard 状态可视化（Ponytail 模式/Loop 回退/Plugin 热加载） | P1 | ✅ 已实施 | UI Designer 共识 |
| P2-1 | pickle fallback 完全移除（从 V4.3.1 并入） | P2 | ✅ 已实施 | 用户确认合并 |
| P2-2 | Autonomous SmartConfirmation 文档补全 | P2 | ✅ 已关闭（V4.5.10 裁决） | 上游 v2.6 文档对齐 |
| P2-4 | V4.3 发布文档同步 + 版本升级到 V4.2.9 | P2 | ✅ 已实施 | 文档先行铁律 |

> **P2-2 V4.5.10 裁决说明（2026-08-30）**: SmartConfirmation 模块（`scripts/collaboration/autonomous/smart_confirmation.py`）自 V4.3.0 起已实现并被 `loop_controller.py` / `git_driver.py` 消费；"上游 v2.6 文档对齐"的诉求已被 V4.5.x 的 SKILL.md Honest Disclosure 框架取代（能力边界诚实披露优于逐项功能文档对齐）。条目关闭，不再单独补写文档。

### V4.3.0 版本策略（用户确认）

- **V4.2.9** (PATCH 预发布): 全部 P0 + P1 + P2 代码 + 文档同步完成，通过 E2E 测试 + 真实用户模拟测试，等待用户确认
- **V4.3.0** (MINOR 正式版): 用户确认 V4.2.9 后，升 MINOR 号发布
- **P2-1 已并入 V4.3.0**（用户指示合并推进，不再单独 V4.3.1）
- 遵循 SemVer 规则: MINOR 递增仅用于向后兼容的功能新增

### P3 待真实需求（暂不实施）

| ID | 名称 | 原优先级 | 降级原因 |
|----|------|----------|----------|
| P3-1 | Dynamic Workflows 6 模式库 | P1-2 | 与 Non-Goals 矛盾；无真实消费者，违反 YAGNI |
| P3-2 | PluginHotLoader 轮询文档对齐 | P1-3 | 现有 `reload_if_changed()` 已实现，gap 分析错误 |

### 7-Role 共识调整摘要（10 项）

1. P1-2 Dynamic Workflows 降级为 P3（PM+Coder+Architect）
2. P1-3 PluginHotLoader 轮询降级为 P3 文档项（Architect+DevOps）
3. P1-1 Ponytail 简化：删 ultra，保留 7 步梯（Coder+Tester）
4. P0-1 pickle 安全收紧 + 观察期 30→7-14 天（Security）
5. P0-2 改名 `todo_drift_monitor` + regex 扩展 + 阻塞（Security+Architect+DevOps）
6. P2-3 UIUX 升级为 P1-5（UI Designer）
7. 新增 P1-6 Dashboard 状态可视化（UI Designer）
8. 修正 `check_doc_consistency.sh` → `check_config_consistency.py`（DevOps）
9. 发布策略：V4.2.9 预发布 → V4.3.0 正式版（用户确认合并 V4.3.1→V4.3.0）
10. LoopKernel 回退独立硬上限 `rollback_max_iterations`（Architect）

---

## 已落地条目

> 记录已从 ROADMAP 转为正式实现的 P2 学习项。

### P2-1: PrototypeSkill (Matt prototype) — ✅ V4.2.1 已落地

- **ID**: P2-1
- **来源**: Matt Pocock [prototype skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/prototype)
- **学习点**: 快速原型验证能力 — 在投入完整实现前，先产出可运行的最小原型，验证假设
- **落地版本**: V4.2.1 (commit 1fc94aa)
- **落地方式**: 新建 `skills/prototype/handler.py` + `skill-manifest.yaml`。`PrototypeSkill` 支持 UI/logic/API 三类原型生成，复用 `MicroTaskPlanner` vertical-slice 模式；与 `Skillifier` 协调（artifacts vs pattern extraction，无职责重叠）
- **API**: `generate(hypothesis, prototype_type, constraints)` → files + validation_steps + estimated_effort; `validate(prototype_result, actual_outcome)` → hypothesis_confirmed + confidence + should_proceed_to_full_impl
- **测试**: `tests/test_prototype_skill.py`（28 测试）

### P2-2: TeachSkill (Matt teach) — ✅ V4.2.1 已落地

- **ID**: P2-2
- **来源**: Matt Pocock [teach skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/teach)
- **学习点**: DevSquad onboarding 场景 — 引导新用户理解 7 角色协作模型、生命周期阶段、Iron Rules
- **落地版本**: V4.2.1 (commit 1fc94aa)
- **落地方式**: 新建 `skills/teach/handler.py` + `skill-manifest.yaml`。`TeachSkill` 提供 8 主题课程（overview/seven_roles/lifecycle/iron_rules/sub_skills/glossary/quickstart/full_curriculum），3 级用户水平（beginner/intermediate/advanced），3 语言（zh/en/ja）。内容源自 SKILL.md（非 memory）。区别于 `grilling`（P0-7 需求采集），TeachSkill 是知识传递
- **API**: `teach(topic, user_level, lang)`, `assess(topic, user_answers)`, `curriculum(user_level)`
- **测试**: `tests/test_teach_skill.py`（57 测试）

### P2-3: git-guardrails (Matt git-guardrails) — ✅ V4.1.0 已落地

- **ID**: P2-3
- **来源**: Matt Pocock [git-guardrails](https://github.com/mattpocock/skills/tree/main/skills/engineering/git-guardrails)
- **学习点**: git 命令分类 — 标记危险 git 操作（force push, reset --hard, clean -f 等）
- **落地版本**: V4.1.0
- **落地方式**: `scripts/collaboration/operation_classifier.py` 新增 `OperationClassifier.classify_git_command(command: str) -> str` 方法，复用现有 ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN 三级分类体系
- **分类规则**:
  - FORBIDDEN: `git push --force/-f/--force-with-lease` 到 main/master、`git reset --hard`、`git clean -f/-fd/-fx`、`git branch -D`、`git rebase -i`
  - NEEDS_REVIEW: `git push`（非 force 或到非保护分支）、`git merge`、`git rebase`（非交互）、`git cherry-pick`、`git commit --amend`、`git stash drop`、`git branch -d`
  - ALWAYS_SAFE: `git status`/`log`/`diff`/`show`/`add`/`fetch`/`pull`（非 rebase）/`branch`（列出）/`checkout`（非 orphan）/`stash`（非 drop/pop）
- **测试**: `tests/test_git_guardrails.py`（50+ 测试用例）
- **关联**: [V4.1.0_PRD_Matt_Skills_Fusion.md](prd/V4.1.0_PRD_Matt_Skills_Fusion.md) §3.3

### P2-4: pre-commit hooks (Matt setup-pre-commit) — ✅ V4.2.1 已落地

- **ID**: P2-4
- **来源**: Matt Pocock [setup-pre-commit skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/setup-pre-commit)
- **学习点**: pre-commit hooks 集成 — 在 commit 前自动执行 ruff/mypy/pytest 等检查
- **落地版本**: V4.2.1 (commit 1fc94aa)
- **落地方式**: 新建 `scripts/check_dependency_lock.py`，验证 `.pre-commit-config.yaml` hook 版本与 `requirements-dev.lock` 一致。PyPI-backed hooks（ruff/black）按 rev tag 比较；`language: system` hooks（mypy）按 `--version` 输出比较；非 PyPI hooks（pre-commit-hooks）跳过。已集成到 `.pre-commit-config.yaml` local hook 和 `.github/workflows/test.yml` lint job
- **关键教训**: 必须使用 `requirements-dev.lock` 锁定 hook 工具版本，避免不同环境间行为漂移（project_memory: "pre-commit hooks 版本陈旧是 CI 漂移的根本原因"）
- **测试**: `tests/test_check_dependency_lock.py`（34 测试）

### P2-UI-1: CLI 命令词表 (impeccable 23 Commands) — ✅ V4.2.1 已落地

- **ID**: P2-UI-1
- **来源**: [pbakaus/impeccable](https://github.com/pbakaus/impeccable) — 23 Commands 词表
- **学习点**: CLI 命令词表 — impeccable 定义了 23 个分类命令词，作为 CLI 交互的统一词汇框架
- **落地版本**: V4.2.1 (commit 1fc94aa)
- **落地方式**: 新建 `scripts/collaboration/cli_command_classifier.py`。`CLICommandClassifier` 将 DevSquad CLI 命令映射到 impeccable 23 命令词表（7 类: create/review/navigate/configure/execute/maintain/stop）。AST-based 命令发现（无 import 副作用）。审计发现 12 个 CLI 命令，25% 对齐；建议使用 argparse aliases（非 rename）添加同义词
- **API**: `classify(command)`, `audit_cli()`, `suggest_command(intent)`
- **测试**: `tests/test_cli_command_classifier.py`（61 测试）

### P2-UI-2: Live Browser 模式 (impeccable Live Browser) — ✅ V4.2.1 已落地

- **ID**: P2-UI-2
- **来源**: [pbakaus/impeccable](https://github.com/pbakaus/impeccable) — Live Browser 模式
- **学习点**: Live Browser 模式 — impeccable 通过 live browser 实时迭代 UI，边审查边修改
- **落地版本**: V4.2.1 (commit 1fc94aa)
- **落地方式**: 新建 `scripts/collaboration/dashboard_live_mode.py`。提供实时 UI 审查迭代闭环：`start_session(url, target_views, review_axes)` → `review(session)` → `suggest_fixes(session, issues)` → `re_review(session)` → `end_session(session)`。借鉴 impeccable "实时反馈" 理念，与 V4.1.0 `UIUXAnalyzer` + `TasteDials` 协同
- **API**: `start_session`, `review`, `suggest_fixes`, `re_review`, `end_session`
- **测试**: `tests/test_dashboard_live_mode.py`（28 测试）

### P2-UI-3: 6 Meta-skills 分层 (taste-skill) — ✅ V4.2.1 已落地

- **ID**: P2-UI-3
- **来源**: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) — 6 Meta-skills 分层
- **学习点**: Meta-skills 分层 — taste-skill 采用 6 层 meta-skill 架构组织技能
- **落地版本**: V4.2.1 (commit 1fc94aa)
- **落地方式**: 新建 `scripts/collaboration/meta_skill_layering.py`。`MetaSkillGrouper` 将扁平 skill 注册表组织为 6 层架构: foundation（intent+teach）/ orchestration（dispatch）/ quality（review+test+security）/ evolution（retrospective+prototype）/ governance（reserved）/ integration（reserved）。支持 progressive disclosure（beginner → advanced 逐层暴露）。与 `standardized_role_template.py` 的 progressive disclosure 协调
- **API**: `group_skills(skill_names)`, `get_layer(layer_name)`, `get_progressive_disclosure(user_level)`, `suggest_layer_for_skill(name, desc)`, `audit_layering()`
- **测试**: `tests/test_meta_skill_layering.py`（27 测试）

---

> **文档结束**
>
> **版本**: V1.3.0
> **创建日期**: 2026-07-15
> **最后更新**: 2026-07-25 — V4.3.1 PATCH 发布：BenchmarkRegressionChecker (P1-1) + OutputValidator base64/Unicode 检测 (P1-2) + E2E-01/03/08 脱 xfail (P1-3) 全部落地，8110 tests passed (local; CI authoritative)（原 V4.4.0 三项待办提前到 V4.3.1 完成）
> **基线版本**: V4.2.1
> **维护者**: DevSquad Team
> **下次更新**: V4.4.0 规划启动时（Autonomous Loop Enhancement + Multi-LLM Voting）
